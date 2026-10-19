# App Streamlit: fluxo real do botão "Analisar" (ponto cego do incidente de 21/09/2026,
# ver docs/post-mortem-2026-09-21.md) + privacidade na tela + erros amigáveis.

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "app.py")


class ClienteFalso:
    modelo = "modelo-falso"

    def completar(self, system, user, temperatura=0.2):
        if "analista de RH" in system:
            return '{"tema": "Carga de trabalho", "sentimento": "negativo"}'
        return "Leitura do modelo falso. Ação 1. Ação 2."


def app_pronto(monkeypatch, cliente=ClienteFalso):
    monkeypatch.setattr("feedbackloop.llm.ClienteLLM", cliente)
    return AppTest.from_file(APP, default_timeout=30).run()


def textos(elementos):
    return [e.value for e in elementos]


def test_clique_em_analisar_mostra_resultado_sem_erro(monkeypatch):
    at = app_pronto(monkeypatch)
    assert not at.exception
    at.button(key="analisar").click().run()

    assert not at.exception, at.exception
    assert any("Resumo executivo" in t for t in textos(at.markdown))
    assert any("Leitura do modelo falso" in t for t in textos(at.markdown))
    assert len(at.dataframe) >= 1
    assert len(at.metric) == 4


def test_slider_de_temas_e_lido_antes_do_clique(monkeypatch):
    # Regressão do UnboundLocalError de 21/09/2026: o slider tem que existir antes do botão.
    at = app_pronto(monkeypatch)
    at.slider[0].set_value(3).run()
    at.button(key="analisar").click().run()
    assert not at.exception, at.exception


def test_tela_informa_o_que_foi_mascarado_antes_do_envio(monkeypatch):
    at = app_pronto(monkeypatch)
    mensagens = textos(at.success)
    assert any("mascarou" in m and "4" in m for m in mensagens)  # 4 nomes no CSV de exemplo
    # por padrão não mostra o texto original ao lado
    assert len(at.checkbox) == 1 and at.checkbox[0].value is False


def test_tabela_de_resultado_mostra_o_texto_ja_mascarado(monkeypatch):
    at = app_pronto(monkeypatch)
    at.button(key="analisar").click().run()
    tabela = at.dataframe[-1].value
    juntos = " ".join(tabela["resposta"])
    assert "Marcos" not in juntos and "Antunes" not in juntos
    assert "[PESSOA_1]" in juntos


def test_sem_chave_de_api_mostra_aviso_claro_e_nao_quebra():
    at = AppTest.from_file(APP, default_timeout=30).run()  # sem monkeypatch: ClienteLLM real
    at.button(key="analisar").click().run()
    assert not at.exception
    assert any("OPENAI_API_KEY" in t for t in textos(at.error))


def test_provedor_recusando_a_chave_mostra_mensagem_amigavel(monkeypatch):
    class AuthenticationError(Exception):
        pass

    class ClienteRecusado:
        modelo = "x"

        def completar(self, system, user, temperatura=0.2):
            raise AuthenticationError("401")

    at = app_pronto(monkeypatch, ClienteRecusado)
    at.button(key="analisar").click().run()
    assert not at.exception
    assert any("recusou a chave" in t for t in textos(at.error))


def test_botao_excluir_cache_apaga_as_entradas(monkeypatch):
    at = app_pronto(monkeypatch)
    at.button(key="analisar").click().run()
    at.slider[0].set_value(5).run()  # nova execução: a barra lateral passa a mostrar o cache cheio
    assert any("36 entradas" in t for t in textos(at.sidebar.markdown))
    at.button(key="limpar_cache").click().run()
    assert any("36 entradas removidas" in t for t in textos(at.sidebar.success))


def test_csv_com_coluna_comentario_tambem_funciona(monkeypatch, tmp_path):
    # Dívida documentada por Rafael: a coluna "resposta" era fixa e quebrava com "comentario".
    import io

    import pandas as pd

    from app import carregar_respostas_do_csv

    csv = io.StringIO("id,Comentario\n1,Gosto do time\n2,Salário baixo\n")
    assert carregar_respostas_do_csv(csv) == ["Gosto do time", "Salário baixo"]
    assert pd.read_csv(io.StringIO("a\n1\n")).shape == (1, 1)
