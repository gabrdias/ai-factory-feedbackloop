#!/usr/bin/env python3
"""Gera observabilidade/dashboard-feedbackloop.json (dashboard do Grafana "como código").

    python scripts/gerar_dashboard.py            # grava o arquivo
    python scripts/gerar_dashboard.py --stdout   # imprime

Importar no Grafana: Dashboards > New > Import > Upload JSON. O dashboard pergunta a fonte de
dados Prometheus (a que termina em "-prom") e filtra por ambiente (dev/prod/benchmark).

Limiares (verde/amarelo/vermelho) e a justificativa de cada um estão em
docs/observabilidade/metricas-e-alertas.md. Um teste garante que o JSON versionado é igual ao
que este script gera e que toda métrica das consultas existe no código.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "observabilidade" / "dashboard-feedbackloop.json"

DS = {"type": "prometheus", "uid": "${datasource}"}
A = '{ambiente=~"$ambiente"}'  # filtro de ambiente em toda consulta
R = "$__range"  # a janela inteira escolhida no seletor de tempo
RI = "$__rate_interval"

VERDE, AMARELO, VERMELHO = "green", "yellow", "red"


def passos(*pontos):
    """passos(15, 30) -> verde até 15, amarelo até 30, vermelho acima."""
    cores = [VERDE, AMARELO, VERMELHO]
    saida = [{"color": cores[0], "value": None}]
    for cor, valor in zip(cores[1:], pontos):
        saida.append({"color": cor, "value": valor})
    return saida


def quantil_janela(q: float) -> str:
    return (f"histogram_quantile({q}, sum by (le) "
            f"(increase(feedbackloop_analise_duracao_seconds_bucket{A}[{R}])))")


def quantil_serie(q: float) -> str:
    return (f"histogram_quantile({q}, sum by (le) "
            f"(rate(feedbackloop_analise_duracao_seconds_bucket{A}[{RI}])))")


def razao(numerador: str, denominador: str) -> str:
    return f"(({numerador}) or vector(0)) / ({denominador})"


def stat(pid, titulo, expr, x, y, w, unidade="short", limiares=None, casas=None, descricao="",
         legenda="", h=4, texto="value"):
    return {
        "id": pid, "type": "stat", "title": titulo, "description": descricao,
        "gridPos": {"x": x, "y": y, "w": w, "h": h}, "datasource": DS,
        "targets": [{"refId": "A", "datasource": DS, "expr": expr, "instant": True, "legendFormat": legenda}],
        "fieldConfig": {"defaults": {
            "unit": unidade, "decimals": casas, "noValue": "sem dados",
            "thresholds": {"mode": "absolute", "steps": limiares or [{"color": "blue", "value": None}]},
            "color": {"mode": "thresholds"},
        }, "overrides": []},
        "options": {"colorMode": "background", "graphMode": "none", "textMode": texto,
                    "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}},
    }


def serie(pid, titulo, consultas, x, y, w, unidade="short", h=8, descricao="", empilhado=False):
    return {
        "id": pid, "type": "timeseries", "title": titulo, "description": descricao,
        "gridPos": {"x": x, "y": y, "w": w, "h": h}, "datasource": DS,
        "targets": [{"refId": chr(65 + i), "datasource": DS, "expr": e, "legendFormat": leg}
                    for i, (e, leg) in enumerate(consultas)],
        "fieldConfig": {"defaults": {"unit": unidade, "custom": {
            "drawStyle": "bars" if empilhado else "line", "barAlignment": 0,
            "spanNulls": True, "lineWidth": 1 if empilhado else 2, "fillOpacity": 70 if empilhado else 5,
            "stacking": {"mode": "normal" if empilhado else "none", "group": "A"},
            "showPoints": "auto"}}, "overrides": []},
        "options": {"legend": {"displayMode": "list", "placement": "bottom"},
                    "tooltip": {"mode": "multi", "sort": "desc"}},
    }


def gerar() -> dict:
    inc = lambda metrica, filtro=A: f"increase({metrica}{filtro}[{R}])"  # noqa: E731
    total = lambda metrica, filtro=A: f"sum({inc(metrica, filtro)})"  # noqa: E731
    analises = total("feedbackloop_analises_total")
    chamadas = total("feedbackloop_llm_chamadas_total")
    erros = total("feedbackloop_llm_chamadas_total", '{ambiente=~"$ambiente",resultado="erro"}')
    respostas = total("feedbackloop_respostas_total")
    custo = total("feedbackloop_llm_custo_usd_total")

    painel_texto = {
        "id": 1, "type": "text", "title": "", "gridPos": {"x": 0, "y": 0, "w": 24, "h": 3},
        "options": {"mode": "markdown", "content": (
            "**FeedbackLoop — saúde do deployment.** As caixas coloridas do topo usam a janela de tempo "
            "escolhida (canto superior direito): verde = dentro da meta, amarelo = atenção, vermelho = acima do limite. "
            "Limiares e justificativas: `docs/observabilidade/metricas-e-alertas.md`. "
            "Qualquer número deste painel só vale para o(s) ambiente(s) selecionado(s) em **ambiente**. "
            "Nenhuma métrica contém texto de respostas ou dado pessoal."
        )},
    }

    paineis = [
        painel_texto,
        # --- linha 1: as cinco métricas essenciais -------------------------------------------
        stat(2, "Volume: análises", analises, 0, 3, 4, casas=0,
             descricao="Análises executadas na janela (ok + parcial + erro)."),
        stat(3, "Latência p50 (s)", quantil_janela(0.50), 4, 3, 4, "s", passos(8, 15), 1,
             "Mediana da duração da análise completa. Meta: até 8 s."),
        stat(4, "Latência p95 (s)", quantil_janela(0.95), 8, 3, 4, "s", passos(20, 30), 1,
             "95% das análises terminam até este tempo. Meta: até 20 s; limite: 30 s."),
        stat(5, "Latência p99 (s)", quantil_janela(0.99), 12, 3, 4, "s", passos(30, 60), 1,
             "Cauda longa (1 em 100). Meta: até 30 s; limite: 60 s."),
        stat(6, "Erro: taxa de falha do LLM", razao(erros, chamadas), 16, 3, 4, "percentunit", passos(0.02, 0.05), 1,
             "Chamadas ao provedor que falharam / total. Meta: abaixo de 2%; alerta P2 a partir de 20% em 2 min."),
        stat(7, "Custo por análise (US$)", f"({custo}) / ({analises}) > 0", 20, 3, 4,
             "currencyUSD", passos(0.015, 0.03), 4,
             "Custo estimado / análises de 36 respostas. Medido: ≈ US$ 0,009. Meta: até US$ 0,015; atenção acima de US$ 0,03. Sem preço configurado mostra 'sem dados'."),
        # --- linha 2: latência ao longo do tempo e volume --------------------------------------
        serie(8, "Latência da análise: p50, p95 e p99", [
            (quantil_serie(0.50), "p50"), (quantil_serie(0.95), "p95"), (quantil_serie(0.99), "p99")],
            0, 7, 12, "s", descricao="Calculada sobre a janela de taxa; com pouco tráfego a linha tem lacunas."),
        serie(9, "Volume: análises por resultado",
              [(f"sum by (resultado) (increase(feedbackloop_analises_total{A}[{RI}]))", "{{resultado}}")],
              12, 7, 6, empilhado=True),
        serie(10, "Chamadas ao LLM por resultado",
              [(f"sum by (resultado) (increase(feedbackloop_llm_chamadas_total{A}[{RI}]))", "{{resultado}}")],
              18, 7, 6, empilhado=True),
        # --- linha 3: erro, tokens e custo -----------------------------------------------------
        serie(11, "Erro: falhas do provedor por tipo",
              [(f"sum by (tipo_erro) (increase(feedbackloop_llm_erros_total{A}[{RI}]))", "{{tipo_erro}}")],
              0, 15, 8, empilhado=True,
              descricao="AuthenticationError = chave recusada; RateLimitError = limite/créditos; Timeout/Connection = rede do provedor."),
        serie(12, "Tokens consumidos",
              [(f"sum by (tipo) (increase(feedbackloop_llm_tokens_total{A}[{RI}]))", "{{tipo}}")],
              8, 15, 8, empilhado=True),
        serie(13, "Custo estimado (US$)",
              [(f"sum(increase(feedbackloop_llm_custo_usd_total{A}[{RI}]))", "custo")], 16, 15, 8, "currencyUSD"),
        # --- linha 4: qualidade, cache e privacidade -------------------------------------------
        stat(14, "Respostas processadas", respostas, 0, 23, 4, casas=0),
        stat(15, "Qualidade: % não classificadas",
             razao(total("feedbackloop_qualidade_nao_classificadas_total"), respostas), 4, 23, 5,
             "percentunit", passos(0.05, 0.10), 1,
             "Respostas que caíram em 'Não classificado' (JSON inválido, erro ou bloqueio). Meta: abaixo de 5%."),
        stat(16, "Qualidade: fragmentação de temas",
             f"sum(increase(feedbackloop_qualidade_fragmentacao_temas_sum{A}[{R}])) / "
             f"sum(increase(feedbackloop_qualidade_fragmentacao_temas_count{A}[{R}]))",
             9, 23, 5, "percentunit", passos(0.70, 0.85), 0,
             "Temas distintos / respostas. 100% = cada resposta virou um tema (agregação inútil). Linha de base medida: 64 a 67% (23 a 24 temas em 36 respostas, benchmark local). Verde até 70%, amarelo até 85%: detecta piora. A meta de produto (abaixo de 35%) ainda não é atingida."),
        stat(17, "Cache: taxa de acerto",
             razao(total("feedbackloop_cache_consultas_total", '{ambiente=~"$ambiente",resultado="hit"}'),
                   total("feedbackloop_cache_consultas_total")), 14, 23, 5, "percentunit", None, 0,
             "Respostas servidas do cache / consultas. Só sobe quando a mesma planilha é reanalisada."),
        stat(18, "PII mascarada (ocorrências)", total("feedbackloop_pii_entidades_total"), 19, 23, 5, casas=0,
             descricao="Dados pessoais trocados por marcador antes de qualquer envio ao LLM. Só contagem, nunca o valor."),
        serie(19, "Privacidade: dados mascarados por tipo",
              [(f"sum by (tipo) (increase(feedbackloop_pii_entidades_total{A}[{RI}]))", "{{tipo}}")],
              0, 27, 12, empilhado=True),
        serie(20, "Cache: acertos e erros",
              [(f"sum by (resultado) (increase(feedbackloop_cache_consultas_total{A}[{RI}]))", "{{resultado}}")],
              12, 27, 12, empilhado=True),
        # --- linha 5: antes e depois (otimização), separado por configuração ------------------
        stat(21, "Antes e depois: latência p50 por configuração",
             f"histogram_quantile(0.5, sum by (le, workers, cache) (increase(feedbackloop_analise_duracao_seconds_bucket{A}[{R}])))",
             0, 35, 12, "s", passos(8, 15), 1,
             "Mesma planilha, configurações diferentes. workers=1 e cache=off é o comportamento sequencial anterior à otimização.",
             legenda="{{workers}} em paralelo, cache {{cache}}", h=6, texto="value_and_name"),
        stat(22, "Antes e depois: latência p95 por configuração",
             f"histogram_quantile(0.95, sum by (le, workers, cache) (increase(feedbackloop_analise_duracao_seconds_bucket{A}[{R}])))",
             12, 35, 12, "s", passos(20, 30), 1,
             "Com poucas análises o p95 é praticamente o máximo observado; ver docs/otimizacao para o método.",
             legenda="{{workers}} em paralelo, cache {{cache}}", h=6, texto="value_and_name"),
        stat(23, "Antes e depois: quantas análises em cada configuração",
             f"sum by (workers, cache) (increase(feedbackloop_analise_duracao_seconds_count{A}[{R}]))",
             0, 41, 24, "short", None, 0,
             "n de cada configuração. Compare só configurações com n parecido; a primeira análise depois de cada reinício serve de aquecimento.",
             legenda="{{workers}} em paralelo, cache {{cache}}", h=4, texto="value_and_name"),
    ]

    return {
        "uid": "feedbackloop-saude",
        "title": "FeedbackLoop — Saúde do deployment",
        "tags": ["feedbackloop", "etapa-2"],
        "timezone": "browser",
        "schemaVersion": 39,
        "version": 1,
        "editable": True,
        "refresh": "1m",
        "time": {"from": "now-24h", "to": "now"},
        "templating": {"list": [
            {"name": "datasource", "label": "Fonte (Prometheus)", "type": "datasource", "query": "prometheus",
             "refresh": 1, "current": {}, "hide": 0},
            {"name": "ambiente", "label": "Ambiente", "type": "query", "datasource": DS,
             "query": {"query": "label_values(feedbackloop_analises_total, ambiente)", "refId": "ambientes"},
             "refresh": 2, "multi": True, "includeAll": True, "allValue": ".+",
             "current": {"selected": True, "text": ["All"], "value": ["$__all"]}},
        ]},
        "annotations": {"list": []},
        "panels": paineis,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stdout", action="store_true")
    args = ap.parse_args()
    texto = json.dumps(gerar(), ensure_ascii=False, indent=2) + "\n"
    if args.stdout:
        print(texto)
    else:
        DESTINO.parent.mkdir(parents=True, exist_ok=True)
        DESTINO.write_text(texto, encoding="utf-8", newline="\n")
        print(f"Gravado em {DESTINO}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
