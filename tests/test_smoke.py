# Smoke tests 1 e 2 — rodam offline, fazem parte do `pytest -q` normal.
# O smoke test 3 (URL pública em produção) fica em scripts/smoke_test_deploy.py,
# porque depende de rede e de um deploy já existir — não faz sentido no CI
# offline que roda em toda branch. Ver README, seção "Deploy e CI/CD".

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from streamlit.testing.v1 import AppTest  # noqa: E402

from app import CSV_EXEMPLO, carregar_respostas_do_csv  # noqa: E402
from feedbackloop.pipeline import analisar  # noqa: E402


class ClienteFakeSmoke:
    """Dublê de LLM só para o smoke test — nunca chama a API real."""

    def __init__(self):
        self.chamadas = 0

    def completar(self, system, user, temperatura=0.2):
        self.chamadas += 1
        if "analista de RH" in system:
            return '{"tema": "Carga de trabalho", "sentimento": "negativo"}'
        return "Resumo de smoke test."


# ---------------------------------------------------------------------------
# Smoke test 1: a aplicação Streamlit sobe sem lançar exceção
# ---------------------------------------------------------------------------

def test_app_streamlit_sobe_sem_erro():
    """Garante que `app.py` roda de ponta a ponta (import + script) sem quebrar.

    Isso pega, por exemplo: erro de import, exceção na renderização da UI,
    ou dependência faltando no requirements.txt — exatamente o tipo de coisa
    que quebraria o deploy em produção sem avisar antes.
    """
    at = AppTest.from_file(str(Path(__file__).resolve().parent.parent / "app.py"))
    at.run(timeout=30)

    assert not at.exception, f"App lançou exceção ao rodar: {at.exception}"
    assert len(at.title) == 1
    assert "FeedbackLoop" in at.title[0].value


# ---------------------------------------------------------------------------
# Smoke test 2: pipeline ponta a ponta usando o CSV de exemplo REAL do repo
# (os testes de tests/test_pipeline.py usam respostas inline; este usa o
# arquivo de dados de verdade, então também valida que o CSV está íntegro)
# ---------------------------------------------------------------------------

def test_pipeline_processa_o_csv_de_exemplo_real():
    respostas = carregar_respostas_do_csv(CSV_EXEMPLO)
    assert len(respostas) > 0, "CSV de exemplo não pode estar vazio"

    fake = ClienteFakeSmoke()
    resultado = analisar(fake, respostas)

    assert resultado.total == len(respostas)
    assert resultado.resumo
    assert "Resumo de smoke test" in resultado.resumo
    # 1 chamada de classificação por resposta + 1 chamada de resumo
    assert fake.chamadas == len(respostas) + 1
