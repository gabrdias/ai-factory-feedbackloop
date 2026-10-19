#!/usr/bin/env python3
"""Benchmark reproduzível das otimizações (concorrência e cache).

Mede o MESMO pipeline em cenários diferentes, sobre o CSV de exemplo:

  A_sequencial_sem_cache         antes: 1 chamada por vez, sem cache (comportamento da Etapa 1)
  B_concorrente_sem_cache        depois: N chamadas em paralelo
  C_concorrente_com_cache_quente depois: N em paralelo + cache já preenchido (reanálise da planilha)

Por execução registra duração, chamadas, tokens, custo, erros, cache e a CONCORDÂNCIA da
classificação com a primeira execução do cenário A (prova de que a otimização não muda o resultado).

Uso (API real; usa a OPENAI_API_KEY do .env e gasta alguns centavos):
    python scripts/benchmark.py --repeticoes 5 --saida docs/benchmarks/benchmark-real.json
Uso sem chave (latência simulada; só demonstra a mecânica, NÃO vale como medição real):
    python scripts/benchmark.py --simulado --repeticoes 3 --limite 12
Relatório em Markdown a partir de um JSON:
    python scripts/relatorio_benchmark.py docs/benchmarks/benchmark-real.json
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import platform
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
os.environ.setdefault("APP_ENV", "benchmark")  # rótulo próprio nos dashboards

from feedbackloop import config as configuracao  # noqa: E402
from feedbackloop import observabilidade as obs  # noqa: E402
from feedbackloop.cache import CacheClassificacao  # noqa: E402
from feedbackloop.pipeline import AnaliseFalhouError, analisar  # noqa: E402

CSV_EXEMPLO = RAIZ / "data" / "respostas-pesquisa-exemplo.csv"

CENARIOS = {
    "A_sequencial_sem_cache": {"descricao": "antes: sequencial, sem cache", "workers": 1, "cache": False, "aquecer": False},
    "B_concorrente_sem_cache": {"descricao": "depois: concorrente, sem cache", "workers": None, "cache": False, "aquecer": False},
    "C_concorrente_com_cache_quente": {"descricao": "depois: concorrente + cache quente", "workers": None, "cache": True, "aquecer": True},
}


def percentil(valores: list[float], p: float) -> float:
    """Percentil por posto mais próximo (nearest-rank). Com poucas amostras p95 e p99 = máximo."""
    ordenados = sorted(valores)
    return ordenados[max(0, math.ceil(p / 100 * len(ordenados)) - 1)]


def carregar_respostas(limite: int | None) -> list[str]:
    with CSV_EXEMPLO.open(encoding="utf-8") as f:
        respostas = [linha["resposta"] for linha in csv.DictReader(f)]
    return respostas[:limite] if limite else respostas


class ClienteSimulado:
    """Só para demonstrar a mecânica sem chave. Os tempos NÃO são medição real."""

    modelo = "simulado"

    def __init__(self, latencia_s: float):
        self.latencia_s = latencia_s

    def completar(self, system, user, temperatura=0.2):
        time.sleep(self.latencia_s)
        if "analista de RH" in system:
            return '{"tema": "Carga de trabalho", "sentimento": "negativo"}'
        return "Resumo simulado."


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=RAIZ, capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:
        return ""


def _concordancia(ref: list[dict], atual: list[dict], campo: str) -> float:
    if not ref or len(ref) != len(atual):
        return 0.0
    return round(sum(1 for a, b in zip(ref, atual) if a[campo] == b[campo]) / len(ref), 4)


def _resumir(duracoes: list[float]) -> dict:
    return {
        "n": len(duracoes),
        "p50_s": round(percentil(duracoes, 50), 3),
        "p95_s": round(percentil(duracoes, 95), 3),
        "p99_s": round(percentil(duracoes, 99), 3),
        "media_s": round(sum(duracoes) / len(duracoes), 3),
        "min_s": round(min(duracoes), 3),
        "max_s": round(max(duracoes), 3),
    }


def executar(repeticoes: int, workers: int, simulado: bool, latencia_simulada: float,
             limite: int | None, cenarios: list[str]) -> dict:
    cfg = configuracao.carregar()
    obs.configurar(ambiente=cfg.ambiente, versao=cfg.versao)
    respostas = carregar_respostas(limite)

    if simulado:
        cliente = ClienteSimulado(latencia_simulada)
        modelo = "simulado"
    else:
        from feedbackloop.llm import ClienteLLM

        cliente = ClienteLLM()
        modelo = cliente.modelo

    referencia: list[dict] = []
    saida_cenarios = {}
    for nome in cenarios:
        spec = CENARIOS[nome]
        n_workers = spec["workers"] or workers
        with tempfile.TemporaryDirectory() as tmp:
            cache = CacheClassificacao(str(Path(tmp) / "bench.sqlite3"), ttl_dias=1) if spec["cache"] else None
            if spec["aquecer"]:
                analisar(cliente, respostas, max_workers=n_workers, cache=cache, modelo=modelo)
            execucoes = []
            for i in range(repeticoes):
                try:
                    r = analisar(cliente, respostas, max_workers=n_workers, cache=cache, modelo=modelo)
                except AnaliseFalhouError as exc:
                    execucoes.append({"execucao": i + 1, "falhou": exc.tipo_erro})
                    continue
                if nome.startswith("A") and not referencia:
                    referencia = r.classificacoes
                m = r.metricas
                execucoes.append({
                    "execucao": i + 1,
                    "duracao_s": m["duracao_s"],
                    "chamadas_llm": m["chamadas_llm"],
                    "erros_llm": m["erros_llm"],
                    "cache_hits": m["cache_hits"],
                    "tokens_entrada": m["tokens_entrada"],
                    "tokens_saida": m["tokens_saida"],
                    "custo_usd": m["custo_usd"],
                    "nao_classificadas": m["nao_classificadas"],
                    "temas_distintos": m["temas_distintos"],
                    "concordancia_sentimento_vs_baseline": _concordancia(referencia, r.classificacoes, "sentimento"),
                    "concordancia_tema_vs_baseline": _concordancia(referencia, r.classificacoes, "tema"),
                })
        validas = [e for e in execucoes if "duracao_s" in e]
        saida_cenarios[nome] = {
            "descricao": spec["descricao"],
            "workers": n_workers,
            "cache": spec["cache"],
            "execucoes": execucoes,
            "resumo": _resumir([e["duracao_s"] for e in validas]) if validas else None,
        }

    obs.forcar_envio()
    try:
        import openai

        versao_openai = openai.__version__
    except Exception:
        versao_openai = ""
    return {
        "meta": {
            "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "modo": "simulado" if simulado else "real",
            "modelo": modelo,
            "respostas": len(respostas),
            "repeticoes": repeticoes,
            "workers_nos_cenarios_concorrentes": workers,
            "versao_app": cfg.versao,
            "commit": _git("rev-parse", "--short", "HEAD"),
            "commit_sujo": bool(_git("status", "--porcelain", "--", "feedbackloop", "app.py")),
            "python": platform.python_version(),
            "openai_sdk": versao_openai,
            "preco_entrada_usd_por_mtok": cfg.preco_entrada_usd_por_mtok,
            "preco_saida_usd_por_mtok": cfg.preco_saida_usd_por_mtok,
            "observacao": (
                "Latência SIMULADA: serve só para demonstrar a mecânica." if simulado else
                "Chamadas reais ao provedor, da máquina de quem executou (a rede entra na medição)."
            ),
        },
        "cenarios": saida_cenarios,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repeticoes", type=int, default=5)
    ap.add_argument("--workers", type=int, default=8, help="paralelismo dos cenários B e C")
    ap.add_argument("--simulado", action="store_true", help="não chama a API; latência simulada")
    ap.add_argument("--latencia-simulada", type=float, default=0.8)
    ap.add_argument("--limite", type=int, default=None, help="usa só as N primeiras respostas")
    ap.add_argument("--cenarios", nargs="+", default=list(CENARIOS), choices=list(CENARIOS))
    ap.add_argument("--saida", type=Path, default=None, help="arquivo .json de saída")
    args = ap.parse_args()

    resultado = executar(args.repeticoes, args.workers, args.simulado, args.latencia_simulada,
                         args.limite, args.cenarios)
    texto = json.dumps(resultado, ensure_ascii=False, indent=2)
    if args.saida:
        args.saida.parent.mkdir(parents=True, exist_ok=True)
        args.saida.write_text(texto, encoding="utf-8")
        print(f"Gravado em {args.saida}", file=sys.stderr)
    print(texto)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
