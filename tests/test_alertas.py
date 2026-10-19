# Alertas "como código": toda regra precisa de prioridade, público, canal e ação (alerta sem ação é
# ruído), e as consultas só podem citar métricas que existem no código.

import re
from pathlib import Path

from tests.test_dashboard import metricas_prometheus_expostas

RAIZ = Path(__file__).resolve().parent.parent
ARQUIVO = RAIZ / "observabilidade" / "alertas.yaml"
CAMPOS_OBRIGATORIOS = ("prioridade", "publico", "canal", "acao", "consulta", "condicao", "justificativa_do_limiar")


def regras() -> list[str]:
    texto = ARQUIVO.read_text(encoding="utf-8")
    corpo = texto.split("\nregras:\n", 1)[1]
    return [b for b in re.split(r"\n  - id: ", "\n" + corpo.rstrip())[1:] if b.strip()]


def test_ha_ao_menos_um_alerta_definido():
    assert len(regras()) >= 1


def test_toda_regra_tem_prioridade_publico_canal_e_acao():
    for bloco in regras():
        nome = bloco.splitlines()[0]
        for campo in CAMPOS_OBRIGATORIOS:
            assert re.search(rf"^    {campo}:", bloco, re.MULTILINE), f"regra {nome} sem '{campo}'"
        prioridade = re.search(r"^    prioridade: (\S+)", bloco, re.MULTILINE).group(1)
        assert prioridade in {"P1", "P2", "P3"}


def test_consultas_dos_alertas_so_usam_metricas_que_existem():
    expostas = metricas_prometheus_expostas()
    usadas = set(re.findall(r"feedbackloop_[a-z0-9_]+", ARQUIVO.read_text(encoding="utf-8")))
    assert usadas, "nenhuma métrica citada"
    assert usadas <= expostas, f"métricas inexistentes: {sorted(usadas - expostas)}"


def test_alerta_de_erro_nao_depende_de_rotulo_imprevisivel():
    # O ponto zero de partida só cobre séries com rótulos previsíveis (ver Instrumentos.aquecer).
    bloco = next(b for b in regras() if b.startswith("FL-ERRO-LLM"))
    assert "tipo_erro" not in bloco.split("consulta:", 1)[1].split("condicao:", 1)[0]
