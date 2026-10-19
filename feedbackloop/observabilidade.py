"""Observabilidade: traces/spans, métricas e log estruturado (OpenTelemetry).

O que é instrumentado (ver docs/observabilidade/metricas-e-alertas.md):
  - Traces: `analise` > `pii.sanitizar`, `classificar.lote` > `classificar.resposta` >
    `llm.chamada`, e `resumo.gerar` > `llm.chamada`.
  - As cinco métricas essenciais: latência (p50/p95/p99), custo, erro, volume e qualidade.

Regras de privacidade: nenhum texto de resposta, nome ou dado pessoal vira atributo de
span, métrica ou log. Só contagens, durações, tamanhos e nomes de tipos.

A exportação é por OTLP/HTTP e liga sozinha quando `OTEL_EXPORTER_OTLP_ENDPOINT` está
definido (Grafana Cloud em dev/prod). Sem isso, a instrumentação continua funcionando
(os números aparecem na própria tela do app), só não sai da máquina.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import sys
import threading
import time
from contextvars import ContextVar
from dataclasses import dataclass, field

from opentelemetry import trace
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.metrics.view import ExplicitBucketHistogramAggregation, View
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

NOME_DO_SERVICO = "feedbackloop"

# 1 s de resolução onde a análise otimizada opera (3 a 10 s) e 10 s onde a sequencial operava (40 a 90 s):
# o percentil de um histograma é interpolado dentro do bucket, então bucket largo = número impreciso.
_BUCKETS_ANALISE_S = (0.5, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 15, 20, 30, 40, 50, 60, 70, 80, 90, 120, 180)
_BUCKETS_LLM_S = (0.1, 0.25, 0.5, 1, 2, 3, 5, 10, 20, 30)
_BUCKETS_RAZAO = (0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)


def _cabecalhos_otlp() -> dict | None:
    """Monta o header de autenticação do Grafana Cloud a partir de duas variáveis simples.

    GRAFANA_INSTANCE_ID + GRAFANA_TOKEN  ->  Authorization: Basic base64("id:token").
    Se OTEL_EXPORTER_OTLP_HEADERS já vier pronto, o SDK o usa e esta função não interfere.
    O token nunca é registrado em log nem em span.
    """
    if os.getenv("OTEL_EXPORTER_OTLP_HEADERS"):
        return None
    instancia = os.getenv("GRAFANA_INSTANCE_ID", "").strip()
    token = os.getenv("GRAFANA_TOKEN", "").strip()
    if not (instancia and token):
        return None
    cred = base64.b64encode(f"{instancia}:{token}".encode("utf-8")).decode("ascii")
    return {"Authorization": f"Basic {cred}"}


class _Estado:
    pronto = False
    ambiente = "local"
    versao = "0"
    tracer = None
    inst = None
    provider_trace = None
    provider_metricas = None
    lock = threading.Lock()


_estado = _Estado()


@dataclass
class UsoAnalise:
    """Acumula o consumo de uma análise (seguro para várias threads)."""

    chamadas: int = 0
    erros: int = 0
    tokens_entrada: int = 0
    tokens_saida: int = 0
    custo_usd: float = 0.0
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def registrar(self, *, erro: bool, tokens_entrada: int = 0, tokens_saida: int = 0, custo_usd: float = 0.0):
        with self.lock:
            self.chamadas += 1
            self.erros += 1 if erro else 0
            self.tokens_entrada += tokens_entrada
            self.tokens_saida += tokens_saida
            self.custo_usd += custo_usd


# Propagados para as threads de trabalho via contextvars.copy_context().
uso_corrente: ContextVar[UsoAnalise | None] = ContextVar("uso_corrente", default=None)
operacao_corrente: ContextVar[str] = ContextVar("operacao_corrente", default="classificar")


class Instrumentos:
    def __init__(self, meter):
        self.analise_duracao = meter.create_histogram(
            "feedbackloop.analise.duracao", unit="s",
            description="Duração do pipeline de uma análise (classificação, agregação e resumo)",
        )
        self.llm_duracao = meter.create_histogram(
            "feedbackloop.llm.duracao", unit="s", description="Duração de cada chamada ao provedor de LLM",
        )
        self.llm_chamadas = meter.create_counter(
            "feedbackloop.llm.chamadas", description="Chamadas ao provedor de LLM (resultado ok|erro)",
        )
        self.llm_erros = meter.create_counter(
            "feedbackloop.llm.erros", description="Erros do provedor por tipo (diagnóstico; o alerta usa llm.chamadas)",
        )
        self.llm_tokens = meter.create_counter(
            "feedbackloop.llm.tokens", description="Tokens consumidos (tipo entrada|saida)",
        )
        self.llm_custo = meter.create_counter(
            "feedbackloop.llm.custo_usd", description="Custo estimado em USD (tokens x preço configurado)",
        )
        self.analises = meter.create_counter(
            "feedbackloop.analises", description="Análises executadas (resultado ok|parcial|erro)",
        )
        self.respostas = meter.create_counter(
            "feedbackloop.respostas", description="Respostas abertas processadas",
        )
        self.nao_classificadas = meter.create_counter(
            "feedbackloop.qualidade.nao_classificadas",
            description="Respostas que caíram em 'Não classificado' (falha de parsing, erro ou bloqueio)",
        )
        self.fragmentacao = meter.create_histogram(
            "feedbackloop.qualidade.fragmentacao_temas",
            description="Temas distintos / respostas por análise (1.0 = cada resposta virou um tema)",
        )
        self.pii_entidades = meter.create_counter(
            "feedbackloop.pii.entidades", description="Dados pessoais mascarados antes do LLM (por tipo)",
        )
        self.pii_bloqueios = meter.create_counter(
            "feedbackloop.pii.bloqueios", description="Chamadas bloqueadas por PII residual",
        )
        self.cache_consultas = meter.create_counter(
            "feedbackloop.cache.consultas", description="Consultas ao cache (resultado hit|miss)",
        )
        self.cache_purgados = meter.create_counter(
            "feedbackloop.cache.purgados", description="Entradas removidas por expiração (retenção)",
        )


    def aquecer(self, ambiente: str) -> None:
        """Emite um ponto ZERO para cada série de contador conhecida.

        O Prometheus calcula `increase()` entre dois pontos; uma série que nasce já valendo 1
        (ex.: a primeira análise depois de cada reinício do Render gratuito) teria esse 1
        ignorado. Com o zero de partida, o primeiro incremento passa a ser contado. Séries com
        rótulo imprevisível (ex.: o tipo de erro) ficam de fora de propósito: por isso o erro
        usado nos alertas é `llm.chamadas{resultado="erro"}`, sem esse rótulo.
        """
        a = {"ambiente": ambiente}
        for resultado in ("ok", "parcial", "erro"):
            self.analises.add(0, {**a, "resultado": resultado})
        self.respostas.add(0, a)
        self.nao_classificadas.add(0, a)
        self.cache_purgados.add(0, a)
        for resultado in ("hit", "miss"):
            self.cache_consultas.add(0, {**a, "resultado": resultado})
        for tipo in ("PESSOA", "EMAIL", "CPF", "CNPJ", "RG", "MATRICULA", "CEP", "TELEFONE", "URL", "USUARIO"):
            self.pii_entidades.add(0, {**a, "tipo": tipo})
        for operacao in ("classificar", "resumo", "teste"):
            self.pii_bloqueios.add(0, {**a, "operacao": operacao})
            self.llm_custo.add(0.0, {**a, "operacao": operacao})
            for resultado in ("ok", "erro"):
                self.llm_chamadas.add(0, {**a, "operacao": operacao, "resultado": resultado})
            for tipo in ("entrada", "saida"):
                self.llm_tokens.add(0, {**a, "operacao": operacao, "tipo": tipo})


def configurar(*, ambiente: str = "local", versao: str = "0", span_processors=None,
               metric_readers=None, forcar: bool = False) -> None:
    """Cria os providers de trace/métrica. Idempotente (use forcar=True nos testes)."""
    with _estado.lock:
        if _estado.pronto and not forcar:
            return
        recurso = Resource.create({
            "service.name": os.getenv("OTEL_SERVICE_NAME", NOME_DO_SERVICO),
            "service.version": versao,
            "deployment.environment": ambiente,
        })
        processors = list(span_processors or [])
        readers = list(metric_readers or [])
        if os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT") and not span_processors and not metric_readers:
            from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

            cabecalhos = _cabecalhos_otlp()
            processors.append(BatchSpanProcessor(OTLPSpanExporter(headers=cabecalhos)))
            intervalo = int(os.getenv("OTEL_METRIC_EXPORT_INTERVAL", "15000"))
            readers.append(
                PeriodicExportingMetricReader(OTLPMetricExporter(headers=cabecalhos), export_interval_millis=intervalo)
            )

        provider_trace = TracerProvider(resource=recurso)
        for p in processors:
            provider_trace.add_span_processor(p)

        views = [
            View(instrument_name="feedbackloop.analise.duracao",
                 aggregation=ExplicitBucketHistogramAggregation(_BUCKETS_ANALISE_S)),
            View(instrument_name="feedbackloop.llm.duracao",
                 aggregation=ExplicitBucketHistogramAggregation(_BUCKETS_LLM_S)),
            View(instrument_name="feedbackloop.qualidade.fragmentacao_temas",
                 aggregation=ExplicitBucketHistogramAggregation(_BUCKETS_RAZAO)),
        ]
        provider_metricas = MeterProvider(resource=recurso, metric_readers=readers, views=views)

        _estado.provider_trace = provider_trace
        _estado.provider_metricas = provider_metricas
        _estado.tracer = provider_trace.get_tracer(NOME_DO_SERVICO, versao)
        _estado.inst = Instrumentos(provider_metricas.get_meter(NOME_DO_SERVICO, versao))
        _estado.inst.aquecer(ambiente)
        _estado.ambiente = ambiente
        _estado.versao = versao
        _estado.pronto = True
        _configurar_log()


def _garantir() -> None:
    if not _estado.pronto:
        from . import config

        cfg = config.carregar()
        configurar(ambiente=cfg.ambiente, versao=cfg.versao)


def tracer():
    _garantir()
    return _estado.tracer


def inst() -> Instrumentos:
    _garantir()
    return _estado.inst


def ambiente() -> str:
    _garantir()
    return _estado.ambiente


def attrs(**extra) -> dict:
    """Atributos padrão de toda métrica (rótulo `ambiente`) + os extras."""
    return {"ambiente": ambiente(), **extra}


def forcar_envio() -> None:
    """Descarrega métricas/spans pendentes (útil no encerramento e nos benchmarks)."""
    if _estado.pronto:
        _estado.provider_metricas.force_flush()
        _estado.provider_trace.force_flush()


# ---------------------------------------------------------------------------
# Log estruturado (JSON, uma linha por evento) — sem dados pessoais
# ---------------------------------------------------------------------------

_logger = logging.getLogger("feedbackloop")


class _FormatoJson(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        corpo = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)) + "Z",
            "nivel": record.levelname,
            "evento": record.getMessage(),
            "ambiente": _estado.ambiente,
        }
        corpo.update(getattr(record, "campos", {}))
        ctx = trace.get_current_span().get_span_context()
        if ctx.is_valid:
            corpo["trace_id"] = format(ctx.trace_id, "032x")
        return json.dumps(corpo, ensure_ascii=False, default=str)


def _configurar_log() -> None:
    if any(getattr(h, "_feedbackloop", False) for h in _logger.handlers):
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_FormatoJson())
    handler._feedbackloop = True  # type: ignore[attr-defined]
    _logger.addHandler(handler)
    _logger.setLevel(logging.INFO)
    _logger.propagate = False


def registrar_evento(evento: str, nivel: int = logging.INFO, **campos) -> None:
    """Registra um evento estruturado. NUNCA passe texto de respostas ou dados pessoais."""
    _garantir()
    _logger.log(nivel, evento, extra={"campos": campos})
