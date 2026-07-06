# TODO: isso aqui virou um arquivão. Devia quebrar em componentes. (Rafael)
# FeedbackLoop — Survey Insights
# App de análise EM LOTE de respostas abertas de pesquisa de clima.
# Roda com: streamlit run app.py

import io

import pandas as pd
import streamlit as st

from feedbackloop.llm import ClienteLLM
from feedbackloop.pipeline import analisar

# arquivo de exemplo que já vem no repo (dados sintéticos)
CSV_EXEMPLO = "data/respostas-pesquisa-exemplo.csv"
COLUNA_RESPOSTA = "resposta"  # hardcoded; se a planilha do RH usar outro nome, quebra


def carregar_respostas_do_csv(conteudo) -> list[str]:
    """Lê um CSV e devolve a lista de respostas da coluna esperada."""
    df = pd.read_csv(conteudo)
    if COLUNA_RESPOSTA not in df.columns:
        st.error(
            f"O CSV precisa ter uma coluna chamada '{COLUNA_RESPOSTA}'. "
            f"Colunas encontradas: {list(df.columns)}"
        )
        return []
    return [str(x) for x in df[COLUNA_RESPOSTA].dropna().tolist()]


def main():
    st.set_page_config(page_title="FeedbackLoop — Insights", page_icon="📊")
    st.title("📊 FeedbackLoop — Survey Insights")
    st.caption(
        "Cole ou suba as respostas abertas da pesquisa de clima. "
        "A gente agrupa por tema, marca o sentimento e gera um resumo executivo."
    )

    # AVISO LGPD que devia ser bloqueante, mas por enquanto é só um texto. (planted)
    st.warning(
        "⚠️ As respostas vão para o provedor de IA **sem anonimização**. "
        "Evite subir textos com nomes de pessoas até resolvermos isso. "
        "(ver README → Dívida técnica herdada)"
    )

    st.markdown("### 1) Entrada de dados")
    fonte = st.radio(
        "De onde vêm as respostas?",
        ["Colar texto (uma resposta por linha)", "Subir CSV", "Usar dados de exemplo"],
        index=2,
    )

    respostas: list[str] = []

    if fonte == "Colar texto (uma resposta por linha)":
        texto = st.text_area("Respostas (uma por linha)", height=200)
        if texto.strip():
            respostas = [linha for linha in texto.splitlines() if linha.strip()]

    elif fonte == "Subir CSV":
        arquivo = st.file_uploader(
            f"CSV com uma coluna '{COLUNA_RESPOSTA}'", type=["csv"]
        )
        if arquivo is not None:
            respostas = carregar_respostas_do_csv(io.BytesIO(arquivo.getvalue()))

    else:  # exemplo
        try:
            respostas = carregar_respostas_do_csv(CSV_EXEMPLO)
            st.info(f"Carregadas {len(respostas)} respostas sintéticas de exemplo.")
        except FileNotFoundError:
            st.error(f"Não achei {CSV_EXEMPLO}. Rode o app a partir da raiz do projeto.")

    if respostas:
        st.write(f"**{len(respostas)} respostas** prontas para análise.")
        with st.expander("Ver respostas"):
            st.write(respostas)

    st.markdown("### 2) Análise")
    if st.button("Analisar respostas", type="primary", disabled=not respostas):
        # cria o cliente real só na hora de rodar (precisa da OPENAI_API_KEY)
        try:
            cliente = ClienteLLM()
        except KeyError:
            st.error("OPENAI_API_KEY não configurada. Veja o .env.example.")
            return

        with st.spinner("Classificando resposta por resposta e montando o resumo..."):
            # sem cache: toda vez que clicar, paga tudo de novo. (planted)
            resultado = analisar(cliente, respostas)

        st.markdown("### 3) Resultado")
        st.markdown(resultado.resumo)

        st.markdown("#### Detalhe por resposta")
        tabela = pd.DataFrame(resultado.classificacoes)[
            ["resposta", "tema", "sentimento"]
        ]
        st.dataframe(tabela, use_container_width=True)

        # TODO: nada disso é persistido. Fechou a aba, perdeu o resultado. (Rafael)
        st.caption(
            "Obs.: este resultado não é salvo em lugar nenhum. "
            "Baixe se precisar (em breve... talvez)."
        )


if __name__ == "__main__":
    main()
