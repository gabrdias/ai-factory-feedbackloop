#!/usr/bin/env python3
"""Smoke test 3 — verifica se a URL pública publicada está respondendo.

Ao contrário dos smoke tests 1 e 2 (tests/test_smoke.py, offline), este
depende de rede e de um deploy já existir. Por isso não roda em `pytest -q`:
é chamado pelo workflow de deploy (.github/workflows/ci-cd.yml) logo depois
que o Render termina de subir o serviço.

Uso:
    python scripts/smoke_test_deploy.py <URL_BASE>

Exemplo:
    python scripts/smoke_test_deploy.py https://feedbackloop-prod.onrender.com
"""

import sys
import time
import urllib.error
import urllib.request

TENTATIVAS = 5
ESPERA_ENTRE_TENTATIVAS_SEGUNDOS = 15


def checar_saude(base_url: str) -> bool:
    health_url = f"{base_url.rstrip('/')}/_stcore/health"

    for tentativa in range(1, TENTATIVAS + 1):
        try:
            with urllib.request.urlopen(health_url, timeout=15) as resp:
                status = resp.status
                body = resp.read().decode(errors="replace").strip()
            print(f"[tentativa {tentativa}/{TENTATIVAS}] GET {health_url} -> {status} ({body!r})")
            if status == 200:
                return True
        except (urllib.error.URLError, TimeoutError) as exc:
            print(f"[tentativa {tentativa}/{TENTATIVAS}] falhou: {exc}")

        if tentativa < TENTATIVAS:
            time.sleep(ESPERA_ENTRE_TENTATIVAS_SEGUNDOS)

    return False


def main() -> None:
    if len(sys.argv) != 2:
        print("Uso: python scripts/smoke_test_deploy.py <URL_BASE>")
        sys.exit(2)

    base_url = sys.argv[1]
    print(f"Checando saúde de: {base_url}")

    if checar_saude(base_url):
        print("OK: aplicação respondendo em produção/staging.")
        sys.exit(0)

    print(f"FALHOU: {base_url}/_stcore/health não respondeu 200 após {TENTATIVAS} tentativas.")
    sys.exit(1)


if __name__ == "__main__":
    main()
