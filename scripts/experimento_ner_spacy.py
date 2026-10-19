#!/usr/bin/env python3
"""Experimento (não faz parte da aplicação): NER do spaCy vs. regras vs. as duas juntas.

Serve de evidência para o ADR-004. Requer spaCy e o modelo `pt_core_news_sm`, que NÃO
são dependências do projeto:

    uv venv --python 3.12 C:\\vspacy
    uv pip install --python C:\\vspacy\\Scripts\\python.exe spacy \\
        "pt_core_news_sm @ https://github.com/explosion/spacy-models/releases/download/pt_core_news_sm-3.8.0/pt_core_news_sm-3.8.0-py3-none-any.whl"
    C:\\vspacy\\Scripts\\python.exe scripts/experimento_ner_spacy.py

Usa o mesmo conjunto rotulado e o mesmo critério de vazamento de scripts/avaliar_pii.py.
"""

from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import spacy  # noqa: E402

from feedbackloop.pii import sanitizar  # noqa: E402
from scripts.avaliar_pii import _vazou, carregar  # noqa: E402

NLP = spacy.load("pt_core_news_sm")


def so_ner(texto: str) -> str:
    saida = texto
    for ent in reversed(NLP(texto).ents):
        if ent.label_ == "PER":
            saida = saida[: ent.start_char] + "[PESSOA]" + saida[ent.end_char :]
    return saida


def so_regras(texto: str) -> str:
    return sanitizar(texto).texto


def regras_mais_ner(texto: str) -> str:
    return so_ner(sanitizar(texto).texto)


MODOS = {"so_regras": so_regras, "so_ner_spacy": so_ner, "regras_mais_ner": regras_mais_ner}


def main() -> None:
    itens = carregar()
    resultado = {}
    for nome, fn in MODOS.items():
        cats = defaultdict(lambda: {"pii": 0, "removidas": 0, "manter": 0, "manter_ok": 0})
        inicio = time.perf_counter()
        for item in itens:
            saida = fn(item["texto"])
            c = cats[item["cat"]]
            c["pii"] += len(item["pii"])
            c["removidas"] += sum(1 for p in item["pii"] if not _vazou(p, saida))
            c["manter"] += len(item["manter"])
            c["manter_ok"] += sum(1 for m in item["manter"] if m in saida)
        dur = time.perf_counter() - inicio
        total_pii = sum(c["pii"] for c in cats.values())
        total_rem = sum(c["removidas"] for c in cats.values())
        total_man = sum(c["manter"] for c in cats.values())
        total_ok = sum(c["manter_ok"] for c in cats.values())
        resultado[nome] = {
            "recall_geral": round(total_rem / total_pii, 4),
            "preservacao_geral": round(total_ok / total_man, 4),
            "ms_por_texto": round(dur / len(itens) * 1000, 2),
            "por_categoria": {
                k: {
                    "recall": round(v["removidas"] / v["pii"], 4) if v["pii"] else None,
                    "preservacao": round(v["manter_ok"] / v["manter"], 4) if v["manter"] else None,
                }
                for k, v in cats.items()
            },
        }
    print(json.dumps(resultado, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
