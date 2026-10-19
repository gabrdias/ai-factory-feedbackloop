"""Configuração central, lida do ambiente.

Em produção (Render) as variáveis vêm do painel da plataforma, uma por serviço.
Localmente vêm do arquivo `.env` (nunca versionado; modelo em `.env.example`).
Nenhum segredo tem valor padrão no código.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

from . import __version__

if os.getenv("FEEDBACKLOOP_IGNORAR_DOTENV") != "1":
    load_dotenv(override=False)

_VERDADEIRO = {"1", "true", "sim", "yes", "on"}


def _inteiro(nome: str, padrao: int) -> int:
    try:
        return int(os.getenv(nome, "").strip() or padrao)
    except ValueError:
        return padrao


def _decimal_opcional(nome: str) -> float | None:
    bruto = os.getenv(nome, "").strip()
    try:
        return float(bruto) if bruto else None
    except ValueError:
        return None


def _booleano(nome: str, padrao: bool) -> bool:
    bruto = os.getenv(nome)
    return padrao if bruto is None else bruto.strip().lower() in _VERDADEIRO


def _detectar_ambiente() -> str:
    """APP_ENV manda; senão deduz das variáveis que o Render injeta (nome do serviço, host, branch)."""
    explicito = os.getenv("APP_ENV", "").strip().lower()
    if explicito:
        return explicito
    pistas = " ".join(
        os.getenv(v, "").lower()
        for v in ("RENDER_SERVICE_NAME", "RENDER_EXTERNAL_HOSTNAME", "RENDER_EXTERNAL_URL")
    )
    branch = os.getenv("RENDER_GIT_BRANCH", "").strip().lower()
    if "prod" in pistas or branch == "main":
        return "prod"
    if "dev" in pistas or branch == "develop":
        return "dev"
    return "render" if os.getenv("RENDER", "").lower() == "true" else "local"


@dataclass(frozen=True)
class Config:
    ambiente: str
    modelo: str
    max_workers: int
    timeout_s: float
    max_retries: int
    cache_habilitado: bool
    cache_ttl_dias: int
    cache_db_path: str
    preco_entrada_usd_por_mtok: float | None
    preco_saida_usd_por_mtok: float | None
    dashboard_url: str
    versao: str
    commit: str


def carregar() -> Config:
    return Config(
        ambiente=_detectar_ambiente(),
        modelo=os.getenv("OPENAI_MODEL", "").strip() or "gpt-5.4-mini",
        max_workers=max(1, _inteiro("LLM_MAX_WORKERS", 8)),
        timeout_s=float(_decimal_opcional("LLM_TIMEOUT_S") or 30.0),
        max_retries=max(0, _inteiro("LLM_MAX_RETRIES", 3)),
        cache_habilitado=_booleano("CACHE_HABILITADO", True),
        cache_ttl_dias=max(1, _inteiro("CACHE_TTL_DIAS", 30)),
        cache_db_path=os.getenv("CACHE_DB_PATH", "").strip() or ".cache/feedbackloop.sqlite3",
        preco_entrada_usd_por_mtok=_decimal_opcional("LLM_PRECO_ENTRADA_USD_POR_MTOK"),
        preco_saida_usd_por_mtok=_decimal_opcional("LLM_PRECO_SAIDA_USD_POR_MTOK"),
        dashboard_url=os.getenv("DASHBOARD_URL", "").strip(),
        versao=__version__,
        commit=os.getenv("RENDER_GIT_COMMIT", "").strip()[:7],
    )
