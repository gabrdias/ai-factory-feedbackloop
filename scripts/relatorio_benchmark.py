#!/usr/bin/env python3
"""Transforma o JSON do benchmark em tabelas Markdown (sem inventar nenhum número).

Uso:
    python scripts/relatorio_benchmark.py docs/benchmarks/benchmark-real.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from statistics import mean


def _media(execucoes: list[dict], campo: str):
    valores = [e[campo] for e in execucoes if campo in e]
    return mean(valores) if valores else None


def gerar(dados: dict) -> str:
    meta, cen = dados["meta"], dados["cenarios"]
    linhas = [
        f"Fonte: `benchmark` de {meta['gerado_em']} · modo **{meta['modo']}** · modelo `{meta['modelo']}` · "
        f"{meta['respostas']} respostas · {meta['repeticoes']} execuções por cenário · "
        f"commit `{meta['commit']}`{' (com alterações locais)' if meta.get('commit_sujo') else ''} · "
        f"workers nos cenários concorrentes: {meta['workers_nos_cenarios_concorrentes']}.",
        "",
        f"> {meta['observacao']}",
        "",
        "### Latência da análise completa (segundos)",
        "",
        "| Cenário | n | p50 | p95 | p99 | média | mín | máx |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for nome, c in cen.items():
        r = c["resumo"]
        if not r:
            linhas.append(f"| {nome} | 0 | falhou | | | | | |")
            continue
        linhas.append(f"| {nome} | {r['n']} | {r['p50_s']} | {r['p95_s']} | {r['p99_s']} | {r['media_s']} | {r['min_s']} | {r['max_s']} |")

    base = cen.get("A_sequencial_sem_cache", {}).get("resumo")
    if base:
        linhas += ["", "### Ganho em relação ao cenário A (p50)", "", "| Cenário | p50 (s) | Redução | Aceleração |", "|---|---:|---:|---:|"]
        for nome, c in cen.items():
            r = c["resumo"]
            if not r or nome.startswith("A"):
                continue
            if not base["p50_s"] or not r["p50_s"]:
                linhas.append(f"| {nome} | {r['p50_s']} | n/d | n/d |")
                continue
            red = (1 - r["p50_s"] / base["p50_s"]) * 100
            linhas.append(f"| {nome} | {r['p50_s']} | {red:.1f}% | {base['p50_s'] / r['p50_s']:.1f}x |")

    linhas += ["", "### Custo, volume e qualidade (média por análise)", "",
               "| Cenário | Chamadas ao LLM | Tokens entrada | Tokens saída | Custo (US$) | Erros | Cache hits | Concordância de sentimento | Concordância de tema |",
               "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for nome, c in cen.items():
        ex = c["execucoes"]
        custo = _media(ex, "custo_usd")
        custo_txt = f"{custo:.5f}" if custo else "n/d"
        linhas.append(
            f"| {nome} | {_fmt(_media(ex, 'chamadas_llm'))} | {_fmt(_media(ex, 'tokens_entrada'))} | "
            f"{_fmt(_media(ex, 'tokens_saida'))} | {custo_txt} | {_fmt(_media(ex, 'erros_llm'))} | "
            f"{_fmt(_media(ex, 'cache_hits'))} | {_pct(_media(ex, 'concordancia_sentimento_vs_baseline'))} | "
            f"{_pct(_media(ex, 'concordancia_tema_vs_baseline'))} |"
        )
    falhas = [(n, e) for n, c in cen.items() for e in c["execucoes"] if "falhou" in e]
    if falhas:
        linhas += ["", "Execuções que falharam: " + ", ".join(f"{n}#{e['execucao']} ({e['falhou']})" for n, e in falhas)]
    return "\n".join(linhas) + "\n"


def _fmt(x):
    return "—" if x is None else f"{x:.1f}".rstrip("0").rstrip(".")


def _pct(x):
    return "—" if x is None else f"{x * 100:.1f}%"


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    print(gerar(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))))
