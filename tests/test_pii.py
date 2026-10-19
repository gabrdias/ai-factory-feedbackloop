# Sanitização de PII: comportamento das regras + medição contra o conjunto rotulado.
# O relatório completo sai de `python scripts/avaliar_pii.py --gravar`.

import csv
from pathlib import Path

import pytest

from feedbackloop.pii import PIIDetectadaError, contem_pii, garantir_sem_pii, sanitizar, sanitizar_lote
from scripts.avaliar_pii import CATEGORIAS_GARANTIDAS, avaliar, carregar

RAIZ = Path(__file__).resolve().parent.parent


def test_nome_e_substituido_por_marcador_consistente():
    r = sanitizar("O gerente Marcos Antunes muda tudo. Falei com o Marcos de novo e com a Carolina Mendes.")
    assert "Marcos" not in r.texto and "Antunes" not in r.texto and "Carolina" not in r.texto
    # a mesma pessoa citada de novo mantém o número
    assert r.texto.count("[PESSOA_1]") == 2
    assert "[PESSOA_2]" in r.texto
    assert r.entidades == {"PESSOA": 3}


def test_entidades_guardam_so_contagem_nunca_o_valor():
    r = sanitizar("Escreva para ana.lima@empresa.com ou ligue (11) 98765-4321.")
    assert r.entidades == {"EMAIL": 1, "TELEFONE": 1}
    assert all(isinstance(v, int) for v in r.entidades.values())
    assert "ana.lima" not in str(r.entidades)


def test_cpf_so_com_digitos_exige_digito_verificador_valido():
    assert "[CPF]" in sanitizar("meu cpf 52998224725").texto  # válido
    # 11 dígitos sem validade de CPF e sem formato de telefone: não vira CPF
    assert "[CPF]" not in sanitizar("protocolo 12345678901").texto


def test_anos_seguidos_nao_viram_telefone():
    assert sanitizar("de 12 2024 2025 não houve reajuste").texto == "de 12 2024 2025 não houve reajuste"


def test_lugares_com_nome_de_santo_nao_viram_pessoa():
    for lugar in ("São Paulo", "Santa Maria", "Santo André", "João Pessoa"):
        assert sanitizar(f"Trabalho em {lugar} há dois anos").texto == f"Trabalho em {lugar} há dois anos"


def test_texto_vazio_e_none_nao_quebram():
    assert sanitizar("").texto == ""
    assert sanitizar(None).texto == ""


def test_sanitizar_lote_soma_as_contagens():
    saida, total = sanitizar_lote(["Falei com o Pedro", "e-mail a@b.com", "sem nada"])
    assert saida[2] == "sem nada"
    assert total["PESSOA"] == 1 and total["EMAIL"] == 1


def test_trava_final_bloqueia_pii_residual():
    with pytest.raises(PIIDetectadaError):
        garantir_sem_pii("liga pra mim: (11) 98765-4321")
    garantir_sem_pii("texto já mascarado: [PESSOA_1] e [EMAIL]")  # não levanta


def test_sanitizacao_e_idempotente_em_todo_o_conjunto_de_avaliacao():
    for item in carregar():
        uma_vez = sanitizar(item["texto"]).texto
        assert not contem_pii(uma_vez), f"item {item['id']} ainda tem PII após sanitizar: {uma_vez}"
        assert sanitizar(uma_vez).texto == uma_vez


def test_nomes_do_csv_de_exemplo_nao_sobram():
    nomes = ["Marcos Antunes", "Carolina Mendes", "João Pereira", "Fernanda Lima"]
    with (RAIZ / "data" / "respostas-pesquisa-exemplo.csv").open(encoding="utf-8") as f:
        respostas = [linha["resposta"] for linha in csv.DictReader(f)]
    saida, entidades = sanitizar_lote(respostas)
    juntos = " ".join(saida)
    for nome in nomes:
        for parte in nome.split():
            assert parte not in juntos
    assert entidades["PESSOA"] == 4  # e nenhum falso positivo nas outras 32 respostas


def test_categorias_garantidas_acertam_tudo_e_nao_destroem_termos_legitimos():
    res = avaliar()
    for cat in CATEGORIAS_GARANTIDAS:
        c = res["categorias"][cat]
        assert c["pii_removidas"] == c["pii"], f"vazou PII na categoria {cat}"
        assert c["manter_ok"] == c["manter"], f"termo legítimo trocado na categoria {cat}"
    assert res["recall_garantidas"] == 1.0


def test_lacunas_conhecidas_ficam_dentro_do_documentado():
    # Piso de proteção contra regressão; os números exatos estão em docs/lgpd/avaliacao-sanitizacao-pii.md.
    res = avaliar()
    assert res["recall_geral"] >= 0.85
    assert res["preservacao_geral"] >= 0.95
