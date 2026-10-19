#!/usr/bin/env python3
"""Mede a qualidade da sanitização de PII contra um conjunto rotulado.

Uso:
    python scripts/avaliar_pii.py            # imprime o resumo
    python scripts/avaliar_pii.py --gravar   # também grava docs/lgpd/avaliacao-sanitizacao-pii.{md,json}

Cada item de tests/data/pii_avaliacao.jsonl tem:
  - pii:    textos que NÃO podem sobrar na saída (recall);
  - manter: termos legítimos que NÃO podem ser trocados (preservação).
Um nome composto vaza se QUALQUER parte relevante dele sobrar na saída.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from feedbackloop.pii import sanitizar  # noqa: E402

CAMINHO_DADOS = RAIZ / "tests" / "data" / "pii_avaliacao.jsonl"
_PARTICULAS = {"de", "da", "do", "dos", "das", "e"}

# Categorias em que a regra deve acertar tudo; nas demais a lacuna é conhecida e medida.
CATEGORIAS_GARANTIDAS = (
    "nome_lexico", "nome_gatilho", "nome_sobrenome",
    "email", "cpf", "telefone", "handle", "ids", "misto", "negativo",
)
CATEGORIAS_LACUNA_CONHECIDA = ("nome_sem_pista", "nome_minusculo", "negativo_ambiguo")

DESCRICAO = {
    "nome_lexico": "Nome comum (no léxico), completo ou só o primeiro",
    "nome_gatilho": "Nome fora do léxico, com cargo/título antes (ex.: \"gerente Wanderley\")",
    "nome_sobrenome": "Nome fora do léxico + sobrenome comum",
    "nome_sem_pista": "Nome raro sem nenhuma pista de contexto (lacuna conhecida)",
    "nome_minusculo": "Nome escrito em minúsculas (lacuna conhecida)",
    "email": "E-mail",
    "cpf": "CPF (formatado ou só dígitos válidos)",
    "telefone": "Telefone (com/sem DDD, +55)",
    "handle": "@usuário",
    "ids": "Matrícula, RG, CEP, CNPJ, crachá, registro",
    "misto": "Vários tipos no mesmo texto",
    "negativo": "Sem PII, com ferramentas/lugares/empresas que NÃO podem ser trocados",
    "negativo_ambiguo": "Palavra que também é nome (ex.: \"Marcos importantes\"; falso positivo esperado)",
}


def carregar(caminho: Path = CAMINHO_DADOS) -> list[dict]:
    with caminho.open(encoding="utf-8") as f:
        return [json.loads(linha) for linha in f if linha.strip()]


def _vazou(pii: str, saida: str) -> bool:
    """True se algum pedaço relevante do dado pessoal continua na saída."""
    if re.fullmatch(r"[A-Za-zÀ-ÿ' -]+", pii):
        partes = [p for p in pii.split() if p.casefold() not in _PARTICULAS and len(p) >= 2]
        return any(re.search(rf"(?<!\w){re.escape(p)}(?!\w)", saida, re.IGNORECASE) for p in partes)
    return pii in saida


def avaliar(itens: list[dict] | None = None) -> dict:
    itens = itens if itens is not None else carregar()
    cats: dict[str, dict] = defaultdict(
        lambda: {"itens": 0, "itens_sem_falha": 0, "pii": 0, "pii_removidas": 0,
                 "manter": 0, "manter_ok": 0, "marcadores_em_negativos": 0}
    )
    falhas = []
    for item in itens:
        saida = sanitizar(item["texto"])
        c = cats[item["cat"]]
        c["itens"] += 1
        vazados = [p for p in item["pii"] if _vazou(p, saida.texto)]
        perdidos = [m for m in item["manter"] if m not in saida.texto]
        c["pii"] += len(item["pii"])
        c["pii_removidas"] += len(item["pii"]) - len(vazados)
        c["manter"] += len(item["manter"])
        c["manter_ok"] += len(item["manter"]) - len(perdidos)
        if not item["pii"]:
            c["marcadores_em_negativos"] += saida.total
        if not vazados and not perdidos:
            c["itens_sem_falha"] += 1
        else:
            falhas.append({"id": item["id"], "cat": item["cat"], "texto": item["texto"],
                           "saida": saida.texto, "vazou": vazados, "perdeu": perdidos})

    def soma(campo, categorias):
        return sum(cats[k][campo] for k in categorias if k in cats)

    garantidas = [k for k in CATEGORIAS_GARANTIDAS if k in cats]
    todas = list(cats)
    return {
        "data": date.today().isoformat(),
        "total_itens": len(itens),
        "categorias": dict(cats),
        "falhas": falhas,
        "recall_garantidas": _razao(soma("pii_removidas", garantidas), soma("pii", garantidas)),
        "recall_geral": _razao(soma("pii_removidas", todas), soma("pii", todas)),
        "preservacao_geral": _razao(soma("manter_ok", todas), soma("manter", todas)),
        "preservacao_garantidas": _razao(soma("manter_ok", garantidas), soma("manter", garantidas)),
    }


def _razao(a: int, b: int) -> float:
    return round(a / b, 4) if b else 1.0


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def relatorio_markdown(res: dict) -> str:
    linhas = [
        "# Avaliação da sanitização de PII",
        "",
        f"Gerado por `python scripts/avaliar_pii.py --gravar` em {res['data']} "
        f"sobre {res['total_itens']} textos rotulados em `tests/data/pii_avaliacao.jsonl`.",
        "",
        "**Como ler.** *Recall* = fração dos dados pessoais anotados que **não sobram** na saída "
        "(um nome composto só conta como removido se nenhuma parte relevante sobrar). "
        "*Preservação* = fração dos termos legítimos (ferramentas, lugares, empresas) que "
        "**continuam** na saída.",
        "",
        "| Categoria | Itens | Recall | Preservação | Itens sem falha |",
        "|---|---:|---:|---:|---:|",
    ]
    for cat in list(CATEGORIAS_GARANTIDAS) + list(CATEGORIAS_LACUNA_CONHECIDA):
        if cat not in res["categorias"]:
            continue
        c = res["categorias"][cat]
        rec = _pct(_razao(c["pii_removidas"], c["pii"])) if c["pii"] else "—"
        pres = _pct(_razao(c["manter_ok"], c["manter"])) if c["manter"] else "—"
        linhas.append(
            f"| {DESCRICAO.get(cat, cat)} | {c['itens']} | {rec} | {pres} | "
            f"{c['itens_sem_falha']}/{c['itens']} |"
        )
    linhas += [
        "",
        f"- **Recall nas categorias que a regra se compromete a cobrir:** {_pct(res['recall_garantidas'])}",
        f"- **Recall geral (incluindo lacunas conhecidas):** {_pct(res['recall_geral'])}",
        f"- **Preservação de termos legítimos (geral):** {_pct(res['preservacao_geral'])}",
        "",
        "## Falhas observadas",
        "",
    ]
    if not res["falhas"]:
        linhas.append("Nenhuma.")
    else:
        linhas += ["| # | Categoria | O que aconteceu | Saída |", "|---:|---|---|---|"]
        for f in res["falhas"]:
            o_que = []
            if f["vazou"]:
                o_que.append("sobrou: " + ", ".join(f"`{v}`" for v in f["vazou"]))
            if f["perdeu"]:
                o_que.append("trocou termo legítimo: " + ", ".join(f"`{v}`" for v in f["perdeu"]))
            linhas.append(f"| {f['id']} | {f['cat']} | {'; '.join(o_que)} | {f['saida']} |")
    linhas += [
        "",
        "## Como interpretar com honestidade",
        "",
        "- O léxico de nomes é genérico e **não** inclui os nomes de `nome_gatilho`, `nome_sobrenome`, "
        "`nome_sem_pista` e `nome_minusculo`; essas categorias medem generalização de verdade.",
        "- A lista de sobrenomes comuns contém os sobrenomes usados em `nome_sobrenome`; essa categoria "
        "mede a regra \"nome desconhecido + sobrenome comum\", não sobrenomes raros.",
        "- O conjunto foi escrito pelo próprio autor da regra (antes das regras), tem poucos itens por "
        "categoria e é sintético. Serve para detectar regressões e dimensionar limites, não para "
        "garantir desempenho em dados reais de clientes.",
        "- Identificação **indireta** (\"a única gerente do financeiro de Joinville\") não é coberta por "
        "nenhuma regra: por isso a saída continua sendo tratada como dado pessoal (ver "
        "`docs/lgpd/mapa-de-dados-pessoais.md`).",
        "",
    ]
    return "\n".join(linhas)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gravar", action="store_true", help="grava o relatório em docs/lgpd/")
    args = ap.parse_args()
    res = avaliar()
    md = relatorio_markdown(res)
    print(md)
    if args.gravar:
        destino = RAIZ / "docs" / "lgpd"
        destino.mkdir(parents=True, exist_ok=True)
        (destino / "avaliacao-sanitizacao-pii.md").write_text(md, encoding="utf-8")
        (destino / "avaliacao-sanitizacao-pii.json").write_text(
            json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\nGravado em {destino}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
