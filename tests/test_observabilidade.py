# Observabilidade: spans, hierarquia (inclusive com threads), as cinco métricas e privacidade.
# Usa exportadores em memória; nada sai da máquina.

import dataclasses
import types

import pytest
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from feedbackloop import config as configuracao
from feedbackloop import observabilidade as obs
from feedbackloop.cache import CacheClassificacao
from feedbackloop.llm import ClienteLLM
from feedbackloop.pii import PIIDetectadaError
from feedbackloop.pipeline import AnaliseFalhouError, analisar


# --- Stub do SDK da OpenAI --------------------------------------------------------------

class _Resposta:
    def __init__(self, texto, tok_in, tok_out):
        self.choices = [types.SimpleNamespace(message=types.SimpleNamespace(content=texto))]
        self.usage = types.SimpleNamespace(prompt_tokens=tok_in, completion_tokens=tok_out)


class OpenAIFalso:
    def __init__(self, erro=None):
        self.erro = erro
        self.chamadas = 0
        self.chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.chamadas += 1
        if self.erro:
            raise self.erro
        sistema = kwargs["messages"][0]["content"]
        if "analista de RH" in sistema:
            return _Resposta('{"tema": "Liderança", "sentimento": "negativo"}', 100, 20)
        return _Resposta("Resumo.", 300, 80)


def cliente_com(openai_falso, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "valor-falso-de-teste")
    cfg = dataclasses.replace(
        configuracao.carregar(), preco_entrada_usd_por_mtok=1.0, preco_saida_usd_por_mtok=4.0
    )
    cliente = ClienteLLM(cfg=cfg)
    cliente._client = openai_falso
    return cliente


@pytest.fixture
def telemetria():
    spans = InMemorySpanExporter()
    leitor = InMemoryMetricReader()
    obs.configurar(ambiente="teste", versao="t", span_processors=[SimpleSpanProcessor(spans)],
                   metric_readers=[leitor], forcar=True)
    yield spans, leitor
    obs.configurar(ambiente="local", versao="0", forcar=True)


def pontos(leitor):
    saida = {}
    for rm in leitor.get_metrics_data().resource_metrics:
        for sm in rm.scope_metrics:
            for m in sm.metrics:
                saida.setdefault(m.name, []).extend(m.data.data_points)
    return saida


def soma(lista, **filtro):
    return sum(p.value for p in lista if all(p.attributes.get(k) == v for k, v in filtro.items()))


# --- Chamada ao LLM ---------------------------------------------------------------------

def test_chamada_registra_span_tokens_custo_e_latencia(telemetria, monkeypatch):
    spans, leitor = telemetria
    cliente = cliente_com(OpenAIFalso(), monkeypatch)
    cliente.completar("analista de RH", "A carga de trabalho é alta.")

    [span] = spans.get_finished_spans()
    assert span.name == "llm.chamada"
    assert span.attributes["gen_ai.usage.input_tokens"] == 100
    assert span.attributes["gen_ai.usage.output_tokens"] == 20
    assert span.attributes["feedbackloop.custo_usd"] == pytest.approx((100 * 1.0 + 20 * 4.0) / 1e6)

    m = pontos(leitor)
    assert soma(m["feedbackloop.llm.chamadas"], resultado="ok") == 1
    assert soma(m["feedbackloop.llm.tokens"], tipo="entrada") == 100
    assert soma(m["feedbackloop.llm.tokens"], tipo="saida") == 20
    assert soma(m["feedbackloop.llm.custo_usd"]) == pytest.approx(0.00018)
    assert m["feedbackloop.llm.duracao"][0].count == 1


def test_erro_do_provedor_vira_metrica_de_erro_e_span_com_status_de_erro(telemetria, monkeypatch):
    spans, leitor = telemetria
    cliente = cliente_com(OpenAIFalso(erro=TimeoutError("lento")), monkeypatch)
    with pytest.raises(TimeoutError):
        cliente.completar("analista de RH", "texto")

    [span] = spans.get_finished_spans()
    assert span.status.status_code == StatusCode.ERROR
    assert span.attributes["feedbackloop.tipo_erro"] == "TimeoutError"
    m = pontos(leitor)
    assert soma(m["feedbackloop.llm.chamadas"], resultado="erro", tipo_erro="TimeoutError") == 1


def test_trava_de_pii_bloqueia_antes_de_chamar_o_provedor(telemetria, monkeypatch):
    _, leitor = telemetria
    falso = OpenAIFalso()
    cliente = cliente_com(falso, monkeypatch)
    with pytest.raises(PIIDetectadaError):
        cliente.completar("analista de RH", "me liga no (11) 98765-4321")
    assert falso.chamadas == 0
    assert soma(pontos(leitor)["feedbackloop.pii.bloqueios"]) == 1


# --- Traces da análise ------------------------------------------------------------------

def test_trace_da_analise_tem_a_hierarquia_esperada_mesmo_com_threads(telemetria, monkeypatch):
    spans, _ = telemetria
    cliente = cliente_com(OpenAIFalso(), monkeypatch)
    analisar(cliente, [f"Resposta {i} sobre liderança" for i in range(6)], max_workers=4)

    finalizados = spans.get_finished_spans()
    por_nome = {}
    for s in finalizados:
        por_nome.setdefault(s.name, []).append(s)
    assert len({s.context.trace_id for s in finalizados}) == 1  # tudo no mesmo trace

    [raiz] = por_nome["analise"]
    assert raiz.parent is None
    for nome in ("pii.sanitizar", "classificar.lote", "resumo.gerar"):
        [filho] = por_nome[nome]
        assert filho.parent.span_id == raiz.context.span_id
    [lote] = por_nome["classificar.lote"]
    assert len(por_nome["classificar.resposta"]) == 6
    assert all(s.parent.span_id == lote.context.span_id for s in por_nome["classificar.resposta"])
    pais_das_chamadas = {s.parent.span_id for s in por_nome["llm.chamada"]}
    ids_resposta = {s.context.span_id for s in por_nome["classificar.resposta"]}
    [resumo] = por_nome["resumo.gerar"]
    assert pais_das_chamadas == ids_resposta | {resumo.context.span_id}  # 6 chamadas + 1 do resumo
    assert len(por_nome["llm.chamada"]) == 7


def test_nenhum_span_nem_log_contem_dado_pessoal(telemetria, monkeypatch, capsys):
    spans, _ = telemetria
    cliente = cliente_com(OpenAIFalso(), monkeypatch)
    analisar(
        cliente,
        ["O gerente Marcos Antunes (marcos@empresa.com, 11 98765-4321) cobra demais, CPF 529.982.247-25."],
        max_workers=2,
    )
    proibidos = ["Marcos", "Antunes", "marcos@empresa.com", "98765-4321", "529.982.247-25"]
    texto_dos_spans = " ".join(
        str(v) for s in spans.get_finished_spans() for v in list(s.attributes.values()) + [s.name]
    )
    saida = capsys.readouterr().out
    for p in proibidos:
        assert p not in texto_dos_spans
        assert p not in saida


# --- As cinco métricas essenciais -------------------------------------------------------

def test_metricas_essenciais_existem_com_o_rotulo_de_ambiente(telemetria, monkeypatch, tmp_path):
    _, leitor = telemetria
    cliente = cliente_com(OpenAIFalso(), monkeypatch)
    cache = CacheClassificacao(tmp_path / "c.db")
    analisar(cliente, ["Meu chefe Ricardo Alves é injusto", "Gosto do time"], cache=cache, modelo="m")
    m = pontos(leitor)

    esperadas = {
        "feedbackloop.analise.duracao",          # latência (p50/p95/p99 vêm do histograma)
        "feedbackloop.llm.duracao",              # latência por chamada
        "feedbackloop.llm.custo_usd",            # custo
        "feedbackloop.llm.tokens",               # custo (insumo)
        "feedbackloop.llm.chamadas",             # volume + erro (resultado ok|erro)
        "feedbackloop.analises",                 # volume
        "feedbackloop.respostas",                # volume
        "feedbackloop.qualidade.nao_classificadas",  # qualidade
        "feedbackloop.qualidade.fragmentacao_temas",  # qualidade
        "feedbackloop.pii.entidades",
        "feedbackloop.cache.consultas",
    }
    assert esperadas <= set(m)
    for nome in esperadas:
        assert all(p.attributes["ambiente"] == "teste" for p in m[nome]), nome
    assert soma(m["feedbackloop.respostas"]) == 2
    assert soma(m["feedbackloop.analises"], resultado="ok") == 1
    assert soma(m["feedbackloop.pii.entidades"], tipo="PESSOA") == 1
    assert soma(m["feedbackloop.cache.consultas"], resultado="miss") == 2


def test_histograma_de_duracao_tem_buckets_para_p95_e_p99(telemetria, monkeypatch):
    _, leitor = telemetria
    cliente = cliente_com(OpenAIFalso(), monkeypatch)
    analisar(cliente, ["a b c"])
    [ponto] = pontos(leitor)["feedbackloop.analise.duracao"]
    assert ponto.explicit_bounds == (0.5, 1, 2, 5, 10, 15, 20, 30, 45, 60, 90, 120, 180)
    assert ponto.count == 1


def test_analise_que_falha_por_completo_conta_como_erro(telemetria, monkeypatch):
    spans, leitor = telemetria
    cliente = cliente_com(OpenAIFalso(erro=ConnectionError("fora do ar")), monkeypatch)
    with pytest.raises(AnaliseFalhouError):
        analisar(cliente, ["a", "b"], max_workers=2)
    m = pontos(leitor)
    assert soma(m["feedbackloop.analises"], resultado="erro") == 1
    assert soma(m["feedbackloop.llm.chamadas"], resultado="erro") >= 2
    raiz = next(s for s in spans.get_finished_spans() if s.name == "analise")
    assert raiz.status.status_code == StatusCode.ERROR
