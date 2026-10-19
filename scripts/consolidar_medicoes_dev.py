#!/usr/bin/env python3
"""Calcula as estatísticas do relatório de otimização a partir dos dados BRUTOS.

    python scripts/consolidar_medicoes_dev.py

Lê docs/benchmarks/dev-2026-10-19.raw.json (uma linha por execução, com horário) e imprime as
tabelas usadas em docs/otimizacao/otimizacao-concorrencia-e-cache.md. Nenhum número do relatório
deve vir de outro lugar: tudo é re-derivável deste arquivo.

Regras (as mesmas do protocolo): a 1ª execução de cada cenário é aquecimento e não entra; os
percentis são por posto mais próximo (com 5 amostras, p95 e p99 são o máximo observado).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from statistics import mean

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from scripts.benchmark import percentil  # noqa: E402

ARQUIVO = RAIZ / "docs" / "benchmarks" / "dev-2026-10-19.raw.json"


def carregar() -> dict:
    return json.loads(ARQUIVO.read_text(encoding="utf-8"))


def medidas(cenario: dict) -> list[dict]:
    return cenario["execucoes"][cenario.get("aquecimento", 0):]


def estatisticas(valores: list[float]) -> dict:
    return {
        "n": len(valores),
        "p50": percentil(valores, 50),
        "p95": percentil(valores, 95),
        "p99": percentil(valores, 99),
        "media": round(mean(valores), 2),
        "min": min(valores),
        "max": max(valores),
    }


def consolidar(dados: dict | None = None) -> dict:
    dados = dados or carregar()
    saida = {}
    for nome, c in dados["cenarios"].items():
        ms = medidas(c)
        durs = [e["d"] for e in ms]
        com_tokens = [e for e in ms if e["c"] is not None]  # descarta leituras possivelmente defasadas
        saida[nome] = {
            "rotulo": c["rotulo"],
            "duracao": estatisticas(durs),
            "chamadas_por_analise": round(mean(e["c"] for e in com_tokens), 1),
            "tokens_entrada": round(mean(e["ti"] for e in com_tokens)),
            "tokens_saida": round(mean(e["to"] for e in com_tokens)),
            "custo_usd": round(mean(e["cu"] for e in com_tokens), 4),
            "sentimento_12_1_23": f"{sum(1 for e in ms if e['s'] == '12/1/23')}/{len(ms)}",
            "execucoes_na_estatistica": len(ms),
        }
    return saida


def tabelas_md(res: dict) -> str:
    a = res["A"]["duracao"]
    linhas = [
        "| Cenário | n | p50 (s) | p95 (s) | p99 (s) | média (s) | mín (s) | máx (s) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for nome in ("A", "B", "C"):
        d = res[nome]["duracao"]
        linhas.append(f"| {res[nome]['rotulo']} | {d['n']} | {d['p50']} | {d['p95']} | {d['p99']} | {d['media']} | {d['min']} | {d['max']} |")
    for nome in ("Bc", "Cf"):
        d = res[nome]["duracao"]
        linhas.append(f"| {res[nome]['rotulo']} | {d['n']} | {d['p50']} | {d['p95']} | {d['p99']} | {d['media']} | {d['min']} | {d['max']} |")

    linhas += ["", "| Cenário | Redução do p50 | Aceleração (p50) | Redução da média |", "|---|---:|---:|---:|"]
    for nome in ("B", "C"):
        d = res[nome]["duracao"]
        linhas.append(
            f"| {nome} | {(1 - d['p50'] / a['p50']) * 100:.0f}% | {a['p50'] / d['p50']:.1f}x | {(1 - d['media'] / a['media']) * 100:.0f}% |"
        )

    linhas += ["", "| Cenário | Chamadas ao LLM por análise | Tokens entrada | Tokens saída | Custo por análise (US$) | Sentimento 12/1/23 em |", "|---|---:|---:|---:|---:|---:|"]
    for nome in ("A", "B", "C"):
        r = res[nome]
        linhas.append(f"| {nome} | {r['chamadas_por_analise']} | {r['tokens_entrada']} | {r['tokens_saida']} | {r['custo_usd']} | {r['sentimento_12_1_23']} |")
    return "\n".join(linhas) + "\n"


if __name__ == "__main__":
    resultado = consolidar()
    print(tabelas_md(resultado))
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
