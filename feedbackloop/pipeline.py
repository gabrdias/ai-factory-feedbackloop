# Pipeline de análise de respostas abertas de pesquisa de clima.
# (Rafael)
#
# Fluxo (análise EM LOTE, não é chatbot):
#   1. classificar()  -> pra cada resposta, o LLM devolve {tema, sentimento}
#   2. agregar        -> conta temas e sentimentos (funções puras, testáveis)
#   3. resumir        -> o LLM gera um resumo executivo + ações recomendadas
#
# Separei de propósito as funções PURAS (parse_*, contar_*, montar_resumo) das
# que chamam o LLM (classificar_resposta, gerar_resumo, analisar). As puras dá
# pra testar offline sem mockar nada; as outras a gente mocka o cliente.

import json
import re
from collections import Counter
from dataclasses import dataclass, field

# Os três rótulos de sentimento que a gente aceita. Qualquer coisa fora disso
# o parser joga pra "neutro" (decisão preguiçosa, mas evita quebrar o pipeline).
SENTIMENTOS_VALIDOS = ("positivo", "neutro", "negativo")

SYSTEM_CLASSIFICACAO = """Você é um analista de RH especialista em clima organizacional.
Recebe UMA resposta aberta de uma pesquisa de engajamento de funcionários (em português do Brasil).
Sua tarefa: (1) identificar o TEMA principal em poucas palavras (ex: "Carga de trabalho",
"Liderança", "Remuneração", "Reconhecimento", "Ferramentas", "Home office", "Comunicação");
(2) classificar o SENTIMENTO como exatamente um entre: positivo, neutro, negativo.

Responda SOMENTE com um JSON no formato:
{"tema": "<tema curto>", "sentimento": "<positivo|neutro|negativo>"}
"""

SYSTEM_RESUMO = """Você é um consultor de people analytics.
Recebe um agregado de uma pesquisa de clima: principais temas com contagem e a
distribuição de sentimentos. Escreva, em português do Brasil, um RESUMO EXECUTIVO
curto (3 a 5 frases) para a liderança e, em seguida, de 3 a 5 AÇÕES RECOMENDADAS
objetivas. Seja direto e prático.
"""


# ---------------------------------------------------------------------------
# Funções PURAS (sem LLM) — fáceis de testar
# ---------------------------------------------------------------------------

def parse_sentimento(bruto: str) -> str:
    """Normaliza a string de sentimento devolvida pelo modelo.

    Aceita variações ("Positivo", "NEGATIVO ", "neutra") e cai pra "neutro"
    quando não reconhece. Nunca levanta exceção.
    """
    if not bruto:
        return "neutro"
    texto = bruto.strip().lower()
    # pega a primeira palavra-chave que aparecer
    if "positiv" in texto:
        return "positivo"
    if "negativ" in texto:
        return "negativo"
    if "neutr" in texto:
        return "neutro"
    return "neutro"


def parse_classificacao(bruto: str) -> dict:
    """Extrai {"tema", "sentimento"} do texto cru do LLM.

    Tenta achar um bloco JSON mesmo se vier embrulhado em ```json ... ```.
    Se não der pra parsear, devolve tema "Não classificado" e sentimento neutro.
    """
    tema = "Não classificado"
    sentimento_bruto = ""

    trecho = _extrair_json(bruto)
    if trecho is not None:
        try:
            dado = json.loads(trecho)
            tema = str(dado.get("tema", tema)).strip() or tema
            sentimento_bruto = str(dado.get("sentimento", ""))
        except (json.JSONDecodeError, AttributeError):
            pass

    return {"tema": tema, "sentimento": parse_sentimento(sentimento_bruto)}


def _extrair_json(texto: str):
    """Devolve a substring que parece um objeto JSON, ou None."""
    if not texto:
        return None
    # remove cercas de código markdown se existirem
    sem_cerca = re.sub(r"```(?:json)?", "", texto)
    inicio = sem_cerca.find("{")
    fim = sem_cerca.rfind("}")
    if inicio == -1 or fim == -1 or fim < inicio:
        return None
    return sem_cerca[inicio : fim + 1]


def contar_temas(temas: list[str]) -> list[tuple[str, int]]:
    """Agrega uma lista de temas em [(tema, contagem), ...] do maior pro menor.

    Em empate, desempata por ordem alfabética (pra saída determinística).
    """
    contagem = Counter(t for t in temas if t)
    return sorted(contagem.items(), key=lambda kv: (-kv[1], kv[0]))


def contar_sentimentos(sentimentos: list[str]) -> dict:
    """Conta sentimentos garantindo as três chaves sempre presentes."""
    base = {s: 0 for s in SENTIMENTOS_VALIDOS}
    for s in sentimentos:
        rotulo = parse_sentimento(s)
        base[rotulo] += 1
    return base


def montar_resumo(
    top_temas: list[tuple[str, int]],
    contagem_sentimentos: dict,
    texto_llm: str,
    total: int,
) -> str:
    """Junta o cabeçalho determinístico (números) com o texto gerado pelo LLM.

    A ideia é não confiar só no LLM pros números: a parte de contagem é montada
    aqui, em código, e o texto qualitativo vem do modelo.
    """
    linhas = []
    linhas.append(f"# Resumo executivo — Pesquisa de clima ({total} respostas)\n")

    linhas.append("## Distribuição de sentimento")
    for rotulo in SENTIMENTOS_VALIDOS:
        qtd = contagem_sentimentos.get(rotulo, 0)
        pct = (qtd / total * 100) if total else 0
        linhas.append(f"- {rotulo.capitalize()}: {qtd} ({pct:.0f}%)")
    linhas.append("")

    linhas.append("## Principais temas")
    if top_temas:
        for tema, qtd in top_temas:
            linhas.append(f"- {tema}: {qtd}")
    else:
        linhas.append("- (nenhum tema identificado)")
    linhas.append("")

    linhas.append("## Leitura e ações recomendadas")
    linhas.append(texto_llm.strip() if texto_llm else "(sem texto do modelo)")

    return "\n".join(linhas)


# ---------------------------------------------------------------------------
# Funções que CHAMAM o LLM (recebem um cliente com .completar(system, user))
# ---------------------------------------------------------------------------

def classificar_resposta(cliente, resposta: str) -> dict:
    """Classifica UMA resposta: devolve {"tema", "sentimento"}.

    ATENÇÃO LGPD: a `resposta` vai crua pro prompt, podendo conter nomes de
    pessoas e queixas identificáveis. Não tem anonimização aqui. (planted)
    """
    bruto = cliente.completar(
        system=SYSTEM_CLASSIFICACAO,
        user=f"Resposta da pesquisa:\n\"\"\"\n{resposta}\n\"\"\"",
        temperatura=0.0,
    )
    return parse_classificacao(bruto)


def gerar_resumo_llm(
    cliente,
    top_temas: list[tuple[str, int]],
    contagem_sentimentos: dict,
) -> str:
    """Pede pro LLM o texto qualitativo (leitura + ações)."""
    temas_fmt = "\n".join(f"- {t}: {q}" for t, q in top_temas) or "- (nenhum)"
    sent_fmt = ", ".join(f"{k}={v}" for k, v in contagem_sentimentos.items())
    user = (
        f"Principais temas (tema: contagem):\n{temas_fmt}\n\n"
        f"Distribuição de sentimento: {sent_fmt}\n\n"
        "Gere o resumo executivo e as ações recomendadas."
    )
    return cliente.completar(system=SYSTEM_RESUMO, user=user, temperatura=0.3)


@dataclass
class ResultadoAnalise:
    total: int
    classificacoes: list[dict] = field(default_factory=list)
    top_temas: list[tuple[str, int]] = field(default_factory=list)
    contagem_sentimentos: dict = field(default_factory=dict)
    resumo: str = ""


def analisar(cliente, respostas: list[str], top_n: int = 8) -> ResultadoAnalise:
    """Pipeline ponta a ponta.

    Recebe a lista de respostas abertas e um `cliente` com método
    `.completar(system, user, temperatura)`. Nos testes esse cliente é um mock.

    NOTA DE CUSTO (planted): isto faz 1 chamada de LLM POR RESPOSTA + 1 do
    resumo, toda vez que roda. Sem cache, sem batch real. 40 respostas = 41
    chamadas. Reanalisar a mesma planilha duas vezes paga duas vezes.
    """
    respostas_limpas = [r.strip() for r in respostas if r and r.strip()]

    classificacoes = []
    for resp in respostas_limpas:
        c = classificar_resposta(cliente, resp)
        c["resposta"] = resp
        classificacoes.append(c)

    top_temas = contar_temas([c["tema"] for c in classificacoes])[:top_n]
    contagem = contar_sentimentos([c["sentimento"] for c in classificacoes])

    texto = gerar_resumo_llm(cliente, top_temas, contagem)
    resumo = montar_resumo(top_temas, contagem, texto, len(respostas_limpas))

    return ResultadoAnalise(
        total=len(respostas_limpas),
        classificacoes=classificacoes,
        top_temas=top_temas,
        contagem_sentimentos=contagem,
        resumo=resumo,
    )
