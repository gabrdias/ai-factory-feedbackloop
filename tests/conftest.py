# Isolamento dos testes: nunca usar o .env real, nunca exportar telemetria de verdade e
# nunca gravar o cache dentro do repositório.
import os
import sys
from pathlib import Path

# precisa vir ANTES de qualquer import de feedbackloop (config lê o .env ao ser importada)
os.environ["FEEDBACKLOOP_IGNORAR_DOTENV"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402
import streamlit as st  # noqa: E402


@pytest.fixture(autouse=True)
def ambiente_de_teste(tmp_path, monkeypatch):
    monkeypatch.setenv("CACHE_DB_PATH", str(tmp_path / "cache.sqlite3"))
    monkeypatch.setenv("APP_ENV", "teste")
    for var in ("OTEL_EXPORTER_OTLP_ENDPOINT", "OTEL_EXPORTER_OTLP_HEADERS", "OPENAI_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    st.cache_resource.clear()
    yield
    st.cache_resource.clear()
