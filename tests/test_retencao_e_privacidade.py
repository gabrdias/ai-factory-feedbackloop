# Retenção (cenário reproduzível) e privacidade da plataforma, como testes.

import tomllib
from pathlib import Path

from scripts.retencao import demo

RAIZ = Path(__file__).resolve().parent.parent


def test_cenario_de_retencao_apaga_so_o_que_passou_do_prazo():
    r = demo()
    assert r["antes"] == 3                      # gravadas há 95, 31 e 5 dias
    assert r["removidas_na_purga"] == 2         # 95 e 31 dias passam do TTL de 30
    assert r["restantes"] == 1 and r["a_de_5_dias_sobreviveu"] is True
    assert r["removidas_na_segunda_purga"] == 0  # idempotente
    assert r["depois_da_limpeza"] == 0


def test_ttl_padrao_respeita_o_teto_de_90_dias_do_briefing():
    from feedbackloop import config

    assert config.carregar().cache_ttl_dias <= 90


def test_streamlit_nao_envia_estatisticas_de_uso_ao_fabricante():
    cfg = tomllib.loads((RAIZ / ".streamlit" / "config.toml").read_text(encoding="utf-8"))
    assert cfg["browser"]["gatherUsageStats"] is False
    assert not (RAIZ / ".streamlit" / "secrets.toml").exists()
