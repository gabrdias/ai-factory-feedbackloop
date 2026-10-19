#!/usr/bin/env python3
"""Operação da política de retenção e exclusão (docs/lgpd/politica-de-retencao-e-exclusao.md).

    python scripts/retencao.py status    # quantas entradas há no cache e qual o prazo (TTL)
    python scripts/retencao.py purgar    # apaga só o que passou do prazo (é o que o app faz sozinho a cada hora)
    python scripts/retencao.py limpar    # apaga TUDO (exclusão sob demanda; pede confirmação, ou use --sim)
    python scripts/retencao.py demo      # cenário reproduzível: mostra a purga funcionando com um relógio simulado

O `demo` não toca no cache real: usa um banco temporário e prova, com números, que entradas de
5, 31 e 95 dias, com prazo de 30 dias, resultam em 2 apagadas e 1 mantida.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from feedbackloop import config as configuracao  # noqa: E402
from feedbackloop.cache import CacheClassificacao  # noqa: E402

DIA = 86400


def _cache_real() -> CacheClassificacao:
    cfg = configuracao.carregar()
    return CacheClassificacao(cfg.cache_db_path, cfg.cache_ttl_dias)


def demo() -> dict:
    """Cenário reproduzível da retenção. Devolve os números observados."""
    agora = [1_000_000_000.0]
    with tempfile.TemporaryDirectory() as tmp:
        cache = CacheClassificacao(str(Path(tmp) / "demo.sqlite3"), ttl_dias=30, agora=lambda: agora[0])
        idades_dias = (95, 31, 5)
        chaves = []
        for dias in idades_dias:
            agora[0] = 1_000_000_000.0 - dias * DIA  # grava "no passado"
            chave = cache.chave(f"resposta-{dias}-dias", "modelo", "v1")
            cache.guardar(chave, "Tema", "neutro")
            chaves.append(chave)
        agora[0] = 1_000_000_000.0  # "hoje"
        antes = cache.contar()
        removidas_1 = cache.purgar_expirados()
        restantes = cache.contar()
        removidas_2 = cache.purgar_expirados()  # idempotente
        sobrou_a_de_5_dias = cache.obter(chaves[2]) is not None
        limpas = cache.limpar()
        depois_de_limpar = cache.contar()
    return {
        "ttl_dias": 30,
        "idades_dias": idades_dias,
        "antes": antes,
        "removidas_na_purga": removidas_1,
        "restantes": restantes,
        "removidas_na_segunda_purga": removidas_2,
        "a_de_5_dias_sobreviveu": sobrou_a_de_5_dias,
        "removidas_na_limpeza_total": limpas,
        "depois_da_limpeza": depois_de_limpar,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("comando", choices=["status", "purgar", "limpar", "demo"])
    ap.add_argument("--sim", action="store_true", help="não pedir confirmação no comando 'limpar'")
    args = ap.parse_args()

    if args.comando == "demo":
        r = demo()
        print("Cenário: prazo (TTL) de 30 dias; entradas gravadas há 95, 31 e 5 dias.")
        print(f"  entradas antes da purga ........ {r['antes']}")
        print(f"  removidas pela purga ........... {r['removidas_na_purga']}  (as de 95 e 31 dias)")
        print(f"  restantes ...................... {r['restantes']}  (a de 5 dias sobreviveu: {r['a_de_5_dias_sobreviveu']})")
        print(f"  removidas numa 2ª purga ........ {r['removidas_na_segunda_purga']}  (idempotente)")
        print(f"  removidas pela limpeza total ... {r['removidas_na_limpeza_total']}  -> sobram {r['depois_da_limpeza']}")
        ok = (r["antes"], r["removidas_na_purga"], r["restantes"], r["removidas_na_segunda_purga"]) == (3, 2, 1, 0)
        print("RESULTADO:", "OK, retenção funcionando como documentado." if ok else "FALHOU")
        return 0 if ok else 1

    cache = _cache_real()
    if args.comando == "status":
        print(f"entradas no cache: {cache.contar()} | prazo (TTL): {cache.ttl_dias} dias")
    elif args.comando == "purgar":
        print(f"removidas (vencidas): {cache.purgar_expirados()} | restantes: {cache.contar()}")
    elif args.comando == "limpar":
        if not args.sim and input(f"Apagar TODAS as {cache.contar()} entradas? [digite 'sim'] ").strip().lower() != "sim":
            print("Cancelado.")
            return 1
        print(f"removidas: {cache.limpar()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
