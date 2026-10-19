# Pipeline da Etapa 2: PII nunca chega ao LLM, concorrência, cache e degradação de erros.

import csv
import threading
import time
from pathlib import Path

import pytest

from feedbackloop.cache import CacheClassificacao
from feedbackloop.pii import contem_pii
from feedbackloop.pipeline import AnaliseFalhouError, analisar

RAIZ = Path(__file__).resolve().parent.parent


def respostas_do_csv():
    with (RAIZ / "data" / "respostas-pesquisa-exemplo.csv").open(encoding="utf-8") as f:
        return [linha["resposta"] for linha in csv.DictReader(f)]


class ClienteEspiao:
    """Guarda tudo que seria enviado ao provedor e responde de forma determinística."""

    def __init__(self, latencia=0.0):
        self.enviados = []
        self.latencia = latencia
        self._lock = threading.Lock()
        self.simultaneas = 0
        self.max_simultaneas = 0

    def completar(self, system, user, temperatura=0.2):
        with self._lock:
            self.enviados.append((system, user))
            self.simultaneas += 1
            self.max_simultaneas = max(self.max_simultaneas, self.simultaneas)
        try:
            if self.latencia:
                time.sleep(self.latencia)
            if "analista de RH" in system:
                tema = "Remuneração" if "salário" in user.lower() else "Liderança"
                sent = "negativo" if "não" in user.lower() else "positivo"
                return f'{{"tema": "{tema}", "sentimento": "{sent}"}}'
            return "Resumo de teste."
        finally:
            with self._lock:
                self.simultaneas -= 1


# --- LGPD: nenhuma PII chega ao provedor ------------------------------------------------

def test_nenhum_prompt_enviado_ao_llm_contem_pii():
    espiao = ClienteEspiao()
    analisar(espiao, respostas_do_csv(), max_workers=8)
    assert len(espiao.enviados) == 37  # 36 classificações + 1 resumo
    nomes = ["Marcos", "Antunes", "Carolina", "Mendes", "João", "Pereira", "Fernanda", "Lima"]
    for system, user in espiao.enviados:
        for nome in nomes:
            assert nome not in user, f"nome {nome} vazou para o provedor"
        assert not contem_pii(user)


def test_resultado_mostrado_ao_usuario_tambem_e_o_texto_mascarado():
    resultado = analisar(ClienteEspiao(), ["O gerente Marcos Antunes muda tudo."])
    assert "Marcos" not in resultado.classificacoes[0]["resposta"]
    assert resultado.metricas["pii_total"] == 1


def test_resumo_so_recebe_agregados_nunca_o_texto_das_respostas():
    espiao = ClienteEspiao()
    analisar(espiao, ["A carga de trabalho do meu setor de Joinville é insana."])
    _, user_resumo = espiao.enviados[-1]
    assert "Joinville" not in user_resumo
    assert user_resumo.startswith("Principais temas")


# --- Concorrência -----------------------------------------------------------------------

def test_concorrencia_da_o_mesmo_resultado_que_o_modo_sequencial():
    respostas = respostas_do_csv()
    seq = analisar(ClienteEspiao(), respostas, max_workers=1)
    conc = analisar(ClienteEspiao(), respostas, max_workers=8)
    assert [(c["tema"], c["sentimento"], c["resposta"]) for c in seq.classificacoes] == \
           [(c["tema"], c["sentimento"], c["resposta"]) for c in conc.classificacoes]
    assert seq.top_temas == conc.top_temas
    assert seq.contagem_sentimentos == conc.contagem_sentimentos


def test_concorrencia_realmente_reduz_o_tempo_e_respeita_o_limite_de_workers():
    respostas = [f"Resposta número {i} sobre carga de trabalho" for i in range(24)]
    lento = ClienteEspiao(latencia=0.05)
    t0 = time.perf_counter()
    analisar(lento, respostas, max_workers=1)
    sequencial = time.perf_counter() - t0
    assert lento.max_simultaneas == 1

    rapido = ClienteEspiao(latencia=0.05)
    t0 = time.perf_counter()
    analisar(rapido, respostas, max_workers=8)
    concorrente = time.perf_counter() - t0
    assert 1 < rapido.max_simultaneas <= 8
    assert concorrente < sequencial * 0.5


# --- Cache ------------------------------------------------------------------------------

def test_cache_evita_reclassificar_e_mantem_o_resultado(tmp_path):
    cache = CacheClassificacao(tmp_path / "c.db")
    respostas = respostas_do_csv()
    primeira = ClienteEspiao()
    r1 = analisar(primeira, respostas, max_workers=4, cache=cache, modelo="m")
    segunda = ClienteEspiao()
    r2 = analisar(segunda, respostas, max_workers=4, cache=cache, modelo="m")

    assert len(primeira.enviados) == 37
    assert len(segunda.enviados) == 1  # só o resumo; as 36 classificações vieram do cache
    assert r2.metricas["cache_hits"] == 36
    assert [(c["tema"], c["sentimento"]) for c in r1.classificacoes] == \
           [(c["tema"], c["sentimento"]) for c in r2.classificacoes]


def test_cache_nao_guarda_classificacao_que_falhou_no_parse(tmp_path):
    class Lixo:
        def completar(self, system, user, temperatura=0.2):
            return "isto não é json" if "analista de RH" in system else "resumo"

    cache = CacheClassificacao(tmp_path / "c.db")
    analisar(Lixo(), ["qualquer coisa"], cache=cache, modelo="m")
    assert cache.contar() == 0


def test_mudar_o_modelo_invalida_o_cache(tmp_path):
    cache = CacheClassificacao(tmp_path / "c.db")
    analisar(ClienteEspiao(), ["Meu salário é baixo"], cache=cache, modelo="modelo-a")
    outro = ClienteEspiao()
    r = analisar(outro, ["Meu salário é baixo"], cache=cache, modelo="modelo-b")
    assert r.metricas["cache_hits"] == 0


# --- Erros ------------------------------------------------------------------------------

class ClienteQueFalha:
    def __init__(self, falhar_quando):
        self.falhar_quando = falhar_quando

    def completar(self, system, user, temperatura=0.2):
        if self.falhar_quando(system, user):
            raise ConnectionError("provedor indisponível")
        if "analista de RH" in system:
            return '{"tema": "Ferramentas", "sentimento": "negativo"}'
        return "Resumo."


def test_erro_em_parte_das_respostas_vira_aviso_e_nao_derruba_a_analise():
    cliente = ClienteQueFalha(lambda s, u: "analista de RH" in s and "ruim" in u)
    resultado = analisar(cliente, ["tudo ok", "sistema ruim", "outro ok"], max_workers=3)
    assert resultado.total == 3
    assert any("1 de 3" in aviso for aviso in resultado.avisos)
    assert [c["tema"] for c in resultado.classificacoes].count("Não classificado") == 1


def test_se_todas_as_classificacoes_falham_levanta_erro_claro():
    cliente = ClienteQueFalha(lambda s, u: True)
    with pytest.raises(AnaliseFalhouError) as exc:
        analisar(cliente, ["a", "b", "c"], max_workers=3)
    assert exc.value.tipo_erro == "ConnectionError"


def test_falha_so_no_resumo_mantem_os_numeros_e_avisa():
    cliente = ClienteQueFalha(lambda s, u: "consultor de people analytics" in s)
    resultado = analisar(cliente, ["a", "b"])
    assert "Distribuição de sentimento" in resultado.resumo
    assert any("resumo" in aviso for aviso in resultado.avisos)
