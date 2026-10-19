# Dashboard e alertas "como código": o que está versionado tem que ser o que o script gera, e
# toda métrica citada numa consulta tem que existir de verdade no código da aplicação.

import json
import re
from pathlib import Path

from feedbackloop.observabilidade import Instrumentos
from scripts.gerar_dashboard import DESTINO, gerar

RAIZ = Path(__file__).resolve().parent.parent
UNIDADES = {"s": "seconds"}


class MedidorFalso:
    """Captura os instrumentos criados, sem OpenTelemetry de verdade."""

    def __init__(self):
        self.criados = []  # (tipo, nome, unidade)

    def create_counter(self, nome, unit="", description=""):
        self.criados.append(("counter", nome, unit))
        return self

    def create_histogram(self, nome, unit="", description=""):
        self.criados.append(("histogram", nome, unit))
        return self


def metricas_prometheus_expostas() -> set[str]:
    """Aplica a tradução OTel -> Prometheus do Grafana Cloud (pontos viram _, unidade e _total)."""
    falso = MedidorFalso()
    Instrumentos(falso)
    nomes = set()
    for tipo, nome, unidade in falso.criados:
        base = nome.replace(".", "_")
        if unidade:
            base += "_" + UNIDADES.get(unidade, unidade)
        if tipo == "counter":
            nomes.add(base + "_total")
        else:
            nomes.update({base + "_bucket", base + "_count", base + "_sum"})
    return nomes


def expressoes(dashboard: dict) -> list[str]:
    return [t["expr"] for p in dashboard["panels"] for t in p.get("targets", [])]


def test_o_json_versionado_e_exatamente_o_que_o_script_gera():
    versionado = json.loads(DESTINO.read_text(encoding="utf-8"))
    assert versionado == gerar(), "rode `python scripts/gerar_dashboard.py` e commite o resultado"


def test_toda_metrica_das_consultas_existe_no_codigo():
    expostas = metricas_prometheus_expostas()
    usadas = set()
    for expr in expressoes(gerar()):
        usadas |= set(re.findall(r"feedbackloop_[a-z0-9_]+", expr))
    assert usadas, "nenhuma métrica encontrada nas consultas"
    assert usadas <= expostas, f"métricas inexistentes no código: {sorted(usadas - expostas)}"


def test_os_nomes_batem_com_os_que_o_grafana_cloud_realmente_listou():
    # Lista copiada do navegador de métricas do Grafana Cloud (dev, 19/10/2026), antes de o preço
    # do modelo estar configurado (por isso ainda não havia custo_usd, pii_bloqueios nem cache_purgados).
    vistas = {
        "feedbackloop_analise_duracao_seconds_bucket", "feedbackloop_analises_total",
        "feedbackloop_cache_consultas_total", "feedbackloop_llm_chamadas_total",
        "feedbackloop_llm_duracao_seconds_bucket", "feedbackloop_llm_tokens_total",
        "feedbackloop_pii_entidades_total", "feedbackloop_qualidade_fragmentacao_temas_bucket",
        "feedbackloop_qualidade_nao_classificadas_total", "feedbackloop_respostas_total",
    }
    assert vistas <= metricas_prometheus_expostas()


def test_dashboard_tem_filtro_de_ambiente_e_os_paineis_das_cinco_metricas():
    d = gerar()
    nomes = {v["name"] for v in d["templating"]["list"]}
    assert {"datasource", "ambiente"} <= nomes
    titulos = " | ".join(p["title"] for p in d["panels"])
    for essencial in ("Latência p50", "Latência p95", "Latência p99", "Custo", "Erro", "Volume", "Qualidade"):
        assert essencial in titulos, essencial
    assert all('ambiente=~"$ambiente"' in e for e in expressoes(d))  # nenhuma consulta ignora o filtro
    ids = [p["id"] for p in d["panels"]]
    assert len(ids) == len(set(ids))


def test_dashboard_so_usa_prometheus_para_poder_ser_compartilhado_publicamente():
    # O Grafana não permite painéis do Tempo em dashboards compartilhados externamente.
    for p in gerar()["panels"]:
        if p["type"] != "text":
            assert p["datasource"]["type"] == "prometheus"
