# Testes do pipeline — TODOS offline. Nunca chamam a API de verdade.
# Roda com: pytest -q
#
# Estratégia: as funções puras (parse/contagem/resumo) testamos direto;
# as que chamam o LLM recebem um cliente FAKE (dublê) que devolve respostas
# fixas conforme o system prompt. Assim dá pra testar o fluxo ponta a ponta
# sem gastar 1 centavo nem precisar de chave. (Rafael deixou isso encaminhado!)

import os
import sys

# garante que o pacote feedbackloop seja encontrado rodando da raiz do projeto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from feedbackloop.pipeline import (  # noqa: E402
    analisar,
    classificar_resposta,
    contar_sentimentos,
    contar_temas,
    montar_resumo,
    parse_classificacao,
    parse_sentimento,
)


# ---------------------------------------------------------------------------
# Dublês de LLM (mocks) — implementam só .completar(system, user, temperatura)
# ---------------------------------------------------------------------------

class ClienteFake:
    """Decide a resposta olhando o system prompt.

    - Se for o prompt de classificação, devolve um JSON fixo.
    - Se for o prompt de resumo, devolve um texto fixo.
    Também conta quantas vezes foi chamado (pra checar custo/nº de chamadas).
    """

    def __init__(self, tema="Carga de trabalho", sentimento="negativo"):
        self.tema = tema
        self.sentimento = sentimento
        self.chamadas = 0

    def completar(self, system, user, temperatura=0.2):
        self.chamadas += 1
        if "analista de RH" in system:
            return f'{{"tema": "{self.tema}", "sentimento": "{self.sentimento}"}}'
        return "Resumo de teste. Ação 1. Ação 2. Ação 3."


# ---------------------------------------------------------------------------
# 1) Parser de sentimento (função pura)
# ---------------------------------------------------------------------------

def test_parse_sentimento_normaliza_variacoes():
    assert parse_sentimento("Positivo") == "positivo"
    assert parse_sentimento(" NEGATIVO ") == "negativo"
    assert parse_sentimento("neutra") == "neutro"
    # entrada que não bate com nada cai pra neutro, sem quebrar
    assert parse_sentimento("sei la") == "neutro"
    assert parse_sentimento("") == "neutro"


def test_parse_classificacao_extrai_json_com_cerca_markdown():
    bruto = '```json\n{"tema": "Liderança", "sentimento": "Negativo"}\n```'
    dado = parse_classificacao(bruto)
    assert dado["tema"] == "Liderança"
    assert dado["sentimento"] == "negativo"

    # lixo total -> fallback seguro
    ruim = parse_classificacao("nada de json aqui")
    assert ruim["tema"] == "Não classificado"
    assert ruim["sentimento"] == "neutro"


# ---------------------------------------------------------------------------
# 2) Agregação / contagem (funções puras)
# ---------------------------------------------------------------------------

def test_contar_temas_ordena_por_frequencia_e_desempata_alfabetico():
    temas = ["Salário", "Carga", "Salário", "Carga", "Salário", "Ferramentas"]
    resultado = contar_temas(temas)
    assert resultado[0] == ("Salário", 3)
    assert resultado[1] == ("Carga", 2)
    assert resultado[2] == ("Ferramentas", 1)
    # ignora strings vazias
    assert contar_temas(["", "", "X"]) == [("X", 1)]


def test_contar_sentimentos_sempre_tem_as_tres_chaves():
    contagem = contar_sentimentos(["positivo", "positivo", "negativo"])
    assert contagem == {"positivo": 2, "neutro": 0, "negativo": 1}
    # lista vazia ainda devolve as três chaves zeradas
    assert contar_sentimentos([]) == {"positivo": 0, "neutro": 0, "negativo": 0}


# ---------------------------------------------------------------------------
# 3) Montador de resumo (função pura)
# ---------------------------------------------------------------------------

def test_montar_resumo_inclui_numeros_e_texto_do_llm():
    top = [("Carga de trabalho", 3), ("Salário", 2)]
    sent = {"positivo": 1, "neutro": 1, "negativo": 3}
    resumo = montar_resumo(top, sent, "Texto qualitativo do modelo.", total=5)

    assert "5 respostas" in resumo
    assert "Carga de trabalho: 3" in resumo
    assert "Negativo: 3 (60%)" in resumo
    assert "Texto qualitativo do modelo." in resumo


# ---------------------------------------------------------------------------
# 4) classificar_resposta com cliente mockado
# ---------------------------------------------------------------------------

def test_classificar_resposta_usa_o_cliente_mockado():
    fake = ClienteFake(tema="Remuneração", sentimento="negativo")
    dado = classificar_resposta(fake, "O salário está baixo.")
    assert dado == {"tema": "Remuneração", "sentimento": "negativo"}
    assert fake.chamadas == 1


# ---------------------------------------------------------------------------
# 5) Smoke test ponta a ponta com LLM mockado
# ---------------------------------------------------------------------------

def test_analisar_ponta_a_ponta_offline():
    fake = ClienteFake(tema="Carga de trabalho", sentimento="negativo")
    respostas = [
        "Trabalho demais.",
        "  ",  # vazio: deve ser descartado
        "Não aguento mais hora extra.",
        "Sobrecarga total.",
    ]
    resultado = analisar(fake, respostas)

    # descartou a resposta em branco
    assert resultado.total == 3
    assert len(resultado.classificacoes) == 3
    # todas caíram no mesmo tema (mock fixo)
    assert resultado.top_temas[0] == ("Carga de trabalho", 3)
    assert resultado.contagem_sentimentos["negativo"] == 3
    # cada classificação carrega o texto original
    assert "resposta" in resultado.classificacoes[0]
    # custo: 3 classificações + 1 resumo = 4 chamadas
    assert fake.chamadas == 4
    # o resumo final junta tudo
    assert "Carga de trabalho: 3" in resultado.resumo
    assert "Resumo de teste" in resultado.resumo
