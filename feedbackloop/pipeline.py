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

import contextvars
import json
import re
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from opentelemetry.trace import Status, StatusCode

from . import observabilidade as obs
from .pii import PIIDetectadaError, sanitizar, sanitizar_lote

# Mude quando mudar o prompt de classificação: entra na chave do cache, para não
# servir classificações feitas com um prompt antigo.
VERSAO_PROMPT = "classificacao-v1"
NAO_CLASSIFICADO = "Não classificado"

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

class AnaliseFalhouError(RuntimeError):
    """Todas as chamadas ao provedor falharam; não há resultado útil para mostrar."""

    def __init__(self, tipo_erro: str):
        super().__init__(f"Todas as chamadas ao provedor de IA falharam ({tipo_erro}).")
        self.tipo_erro = tipo_erro


def _pedir_classificacao(cliente, texto_sanitizado: str) -> dict:
    bruto = cliente.completar(
        system=SYSTEM_CLASSIFICACAO,
        user=f"Resposta da pesquisa:\n\"\"\"\n{texto_sanitizado}\n\"\"\"",
        temperatura=0.0,
    )
    return parse_classificacao(bruto)


def classificar_resposta(cliente, resposta: str, *, sanitizar_pii: bool = True) -> dict:
    """Classifica UMA resposta: devolve {"tema", "sentimento"}.

    LGPD: a resposta é sanitizada (nomes, CPF, e-mail, telefone...) ANTES de ir para o
    prompt. Além disso, o ClienteLLM real bloqueia o envio se ainda restar PII.
    """
    texto = sanitizar(resposta).texto if sanitizar_pii else resposta
    return _pedir_classificacao(cliente, texto)


def gerar_resumo_llm(
    cliente,
    top_temas: list[tuple[str, int]],
    contagem_sentimentos: dict,
) -> str:
    """Pede pro LLM o texto qualitativo (leitura + ações).

    Só recebe AGREGADOS (temas com contagem e distribuição de sentimento), nunca o texto
    das respostas. Os nomes de tema também passam pela sanitização, por precaução.
    """
    temas_fmt = "\n".join(f"- {sanitizar(t).texto}: {q}" for t, q in top_temas) or "- (nenhum)"
    sent_fmt = ", ".join(f"{k}={v}" for k, v in contagem_sentimentos.items())
    user = (
        f"Principais temas (tema: contagem):\n{temas_fmt}\n\n"
        f"Distribuição de sentimento: {sent_fmt}\n\n"
        "Gere o resumo executivo e as ações recomendadas."
    )
    token = obs.operacao_corrente.set("resumo")
    try:
        return cliente.completar(system=SYSTEM_RESUMO, user=user, temperatura=0.3)
    finally:
        obs.operacao_corrente.reset(token)


@dataclass
class ResultadoAnalise:
    total: int
    classificacoes: list[dict] = field(default_factory=list)
    top_temas: list[tuple[str, int]] = field(default_factory=list)
    contagem_sentimentos: dict = field(default_factory=dict)
    resumo: str = ""
    avisos: list[str] = field(default_factory=list)
    metricas: dict = field(default_factory=dict)


def _classificar_uma(cliente, texto: str, cache, modelo: str) -> dict:
    """Classifica uma resposta já sanitizada. Nunca levanta: erro vira 'Não classificado'."""
    with obs.tracer().start_as_current_span("classificar.resposta") as span:
        chave = None
        if cache is not None:
            chave = cache.chave(texto, modelo, VERSAO_PROMPT)
            achado = cache.obter(chave)
            if achado is not None:
                obs.inst().cache_consultas.add(1, obs.attrs(resultado="hit"))
                span.set_attribute("feedbackloop.cache", "hit")
                return {**achado, "origem": "cache"}
            obs.inst().cache_consultas.add(1, obs.attrs(resultado="miss"))
            span.set_attribute("feedbackloop.cache", "miss")
        try:
            dado = _pedir_classificacao(cliente, texto)
        except PIIDetectadaError:
            span.set_attribute("feedbackloop.erro", "pii_bloqueada")
            return {"tema": NAO_CLASSIFICADO, "sentimento": "neutro", "origem": "erro", "erro": "pii_bloqueada"}
        except Exception as exc:  # erro do provedor: degrada só esta resposta
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, type(exc).__name__))
            return {"tema": NAO_CLASSIFICADO, "sentimento": "neutro", "origem": "erro", "erro": type(exc).__name__}
        if chave is not None and dado["tema"] != NAO_CLASSIFICADO:
            cache.guardar(chave, dado["tema"], dado["sentimento"])
        return {**dado, "origem": "llm"}


def _executar(funcao, itens: list, max_workers: int) -> list:
    """Aplica `funcao` a cada item, preservando a ordem. Com workers > 1 usa threads."""
    if max_workers <= 1 or len(itens) <= 1:
        return [funcao(item) for item in itens]
    with ThreadPoolExecutor(max_workers=min(max_workers, len(itens)), thread_name_prefix="classif") as pool:
        # copy_context leva para a thread o span pai (OpenTelemetry) e o acumulador de consumo.
        futuros = [pool.submit(contextvars.copy_context().run, funcao, item) for item in itens]
        return [f.result() for f in futuros]


def analisar(
    cliente,
    respostas: list[str],
    top_n: int = 8,
    *,
    max_workers: int = 1,
    cache=None,
    modelo: str = "",
    sanitizar_pii: bool = True,
) -> ResultadoAnalise:
    """Pipeline ponta a ponta.

    `cliente` tem o método `.completar(system, user, temperatura)` (nos testes, um mock).
    Os parâmetros opcionais controlam as otimizações da Etapa 2; os padrões
    (`max_workers=1`, `cache=None`) reproduzem o comportamento sequencial original,
    que é o "antes" das medições em docs/otimizacao/.
    """
    inicio = time.perf_counter()
    uso = obs.UsoAnalise()
    token_uso = obs.uso_corrente.set(uso)
    try:
        respostas_limpas = [r.strip() for r in respostas if r and r.strip()]
        with obs.tracer().start_as_current_span("analise") as raiz:
            raiz.set_attribute("feedbackloop.respostas", len(respostas_limpas))
            raiz.set_attribute("feedbackloop.workers", max_workers)
            raiz.set_attribute("feedbackloop.cache_habilitado", cache is not None)
            raiz.set_attribute("feedbackloop.modelo", modelo)
            try:
                resultado = _analisar(
                    cliente, respostas_limpas, top_n, max_workers, cache, modelo, sanitizar_pii, uso, inicio
                )
            except AnaliseFalhouError as exc:
                raiz.set_status(Status(StatusCode.ERROR, exc.tipo_erro))
                _registrar_metricas_da_analise(
                    "erro", time.perf_counter() - inicio, len(respostas_limpas), 0, 0.0, Counter()
                )
                raise
            raiz.set_attribute("feedbackloop.resultado", "parcial" if resultado.avisos else "ok")
            return resultado
    finally:
        obs.uso_corrente.reset(token_uso)


def _analisar(cliente, respostas_limpas, top_n, max_workers, cache, modelo, sanitizar_pii, uso, inicio):
    tracer = obs.tracer()
    total = len(respostas_limpas)

    with tracer.start_as_current_span("pii.sanitizar") as span:
        if sanitizar_pii:
            sanitizadas, entidades = sanitizar_lote(respostas_limpas)
        else:
            sanitizadas, entidades = list(respostas_limpas), Counter()
        span.set_attribute("pii.entidades_total", sum(entidades.values()))
        for tipo, qtd in entidades.items():
            span.set_attribute(f"pii.entidades.{tipo.lower()}", qtd)

    with tracer.start_as_current_span("classificar.lote") as span:
        span.set_attribute("feedbackloop.workers", max_workers)
        resultados = _executar(lambda t: _classificar_uma(cliente, t, cache, modelo), sanitizadas, max_workers)
        classificacoes = [{**r, "resposta": texto} for r, texto in zip(resultados, sanitizadas)]
        hits = sum(1 for c in classificacoes if c["origem"] == "cache")
        erros_provedor = [c["erro"] for c in classificacoes if c.get("erro") and c["erro"] != "pii_bloqueada"]
        bloqueadas = sum(1 for c in classificacoes if c.get("erro") == "pii_bloqueada")
        span.set_attribute("feedbackloop.cache_hits", hits)
        span.set_attribute("feedbackloop.erros_provedor", len(erros_provedor))

    if total and len(erros_provedor) == total:
        raise AnaliseFalhouError(Counter(erros_provedor).most_common(1)[0][0])

    top_temas = contar_temas([c["tema"] for c in classificacoes])[:top_n]
    contagem = contar_sentimentos([c["sentimento"] for c in classificacoes])

    avisos = []
    with tracer.start_as_current_span("resumo.gerar") as span:
        try:
            texto = gerar_resumo_llm(cliente, top_temas, contagem)
        except Exception as exc:  # o resumo falha sozinho; os números continuam valendo
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, type(exc).__name__))
            texto = ""
            avisos.append("O texto do resumo não pôde ser gerado pelo provedor de IA; os números abaixo estão corretos.")
    resumo = montar_resumo(top_temas, contagem, texto, total)

    if erros_provedor:
        avisos.append(f"{len(erros_provedor)} de {total} respostas não puderam ser classificadas (erro do provedor).")
    if bloqueadas:
        avisos.append(f"{bloqueadas} resposta(s) foram retidas porque ainda continham dado pessoal reconhecível.")

    nao_classificadas = sum(1 for c in classificacoes if c["tema"] == NAO_CLASSIFICADO)
    temas_distintos = len({c["tema"] for c in classificacoes})
    duracao = time.perf_counter() - inicio
    _registrar_metricas_da_analise(
        "parcial" if avisos else "ok", duracao, total, nao_classificadas,
        (temas_distintos / total) if total else 0.0, entidades,
    )

    metricas = {
        "duracao_s": round(duracao, 3),
        "respostas": total,
        "workers": max_workers,
        "chamadas_llm": uso.chamadas,
        "erros_llm": uso.erros,
        "cache_hits": hits,
        "cache_misses": (total - hits) if cache is not None else 0,
        "tokens_entrada": uso.tokens_entrada,
        "tokens_saida": uso.tokens_saida,
        "custo_usd": round(uso.custo_usd, 6),
        "pii_mascarada": dict(entidades),
        "pii_total": sum(entidades.values()),
        "nao_classificadas": nao_classificadas,
        "temas_distintos": temas_distintos,
    }
    obs.registrar_evento("analise.concluida", **{k: v for k, v in metricas.items() if k != "pii_mascarada"},
                         pii_por_tipo=metricas["pii_mascarada"])

    return ResultadoAnalise(
        total=total,
        classificacoes=classificacoes,
        top_temas=top_temas,
        contagem_sentimentos=contagem,
        resumo=resumo,
        avisos=avisos,
        metricas=metricas,
    )


def _registrar_metricas_da_analise(resultado, duracao, total, nao_classificadas, fragmentacao, entidades):
    i = obs.inst()
    base = obs.attrs(resultado=resultado)
    i.analise_duracao.record(duracao, base)
    i.analises.add(1, base)
    i.respostas.add(total, obs.attrs())
    if total:
        i.nao_classificadas.add(nao_classificadas, obs.attrs())
        i.fragmentacao.record(fragmentacao, obs.attrs())
    for tipo, qtd in entidades.items():
        i.pii_entidades.add(qtd, obs.attrs(tipo=tipo))