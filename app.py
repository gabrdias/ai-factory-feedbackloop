# FeedbackLoop — Survey Insights
# App de análise EM LOTE de respostas abertas de pesquisa de clima.
# Roda com: streamlit run app.py
#
# Etapa 2: o app agora (1) mascara dados pessoais ANTES de qualquer envio ao provedor
# de IA e mostra o que será enviado, (2) mede cada análise (latência, tokens, custo) e
# (3) usa concorrência + cache. Regra de negócio em feedbackloop/, aqui só a UI.

import io

import pandas as pd
import streamlit as st

from feedbackloop import config as configuracao
from feedbackloop import observabilidade as obs
from feedbackloop.cache import CacheClassificacao, iniciar_purga_periodica
from feedbackloop.llm import ClienteLLM
from feedbackloop.pii import sanitizar_lote
from feedbackloop.pipeline import AnaliseFalhouError, analisar

# arquivo de exemplo que já vem no repo (dados sintéticos)
CSV_EXEMPLO = "data/respostas-pesquisa-exemplo.csv"
COLUNA_RESPOSTA = "resposta"
COLUNAS_ALTERNATIVAS = ("comentario", "comentário", "comentarios", "texto", "resposta_aberta", "respostas")

MENSAGENS_DE_ERRO = {
    "AuthenticationError": "O provedor recusou a chave de API deste ambiente. Confira a variável OPENAI_API_KEY.",
    "PermissionDeniedError": "O provedor recusou a chave de API deste ambiente. Confira a variável OPENAI_API_KEY.",
    "RateLimitError": "Limite de uso ou créditos do provedor de IA esgotados. Tente de novo mais tarde.",
    "APITimeoutError": "O provedor de IA não respondeu a tempo. Tente de novo.",
    "APIConnectionError": "Não consegui conectar ao provedor de IA. Tente de novo.",
}


def _achar_coluna(df: pd.DataFrame):
    nomes = {str(c).strip().casefold(): c for c in df.columns}
    for candidato in (COLUNA_RESPOSTA, *COLUNAS_ALTERNATIVAS):
        if candidato.casefold() in nomes:
            return nomes[candidato.casefold()]
    return None


def carregar_respostas_do_csv(conteudo) -> list[str]:
    """Lê um CSV e devolve a lista de respostas da coluna esperada (ou de um apelido comum)."""
    df = pd.read_csv(conteudo)
    coluna = _achar_coluna(df)
    if coluna is None:
        st.error(
            f"O CSV precisa ter uma coluna chamada '{COLUNA_RESPOSTA}' "
            f"(ou {', '.join(repr(c) for c in COLUNAS_ALTERNATIVAS[:3])}). "
            f"Colunas encontradas: {list(df.columns)}"
        )
        return []
    return [str(x) for x in df[coluna].dropna().tolist()]


@st.cache_resource(show_spinner=False)
def _inicializar():
    cfg = configuracao.carregar()
    obs.configurar(ambiente=cfg.ambiente, versao=cfg.versao)
    cache = None
    if cfg.cache_habilitado:
        cache = CacheClassificacao(cfg.cache_db_path, cfg.cache_ttl_dias)
        iniciar_purga_periodica(cache)  # retenção: apaga o que passou do TTL, agora e a cada hora
    return cfg, cache


def _barra_lateral(cfg, cache):
    """Desenha a barra lateral e devolve (chamadas_em_paralelo, usar_cache)."""
    with st.sidebar:
        st.header("Operação")
        st.caption(f"Ambiente: **{cfg.ambiente}** · versão {cfg.versao}" + (f" · commit `{cfg.commit}`" if cfg.commit else ""))
        st.write(f"Modelo: `{cfg.modelo}`")
        if cache is None:
            st.write("Cache: desligado")
        else:
            st.write(f"Cache: ligado (validade {cfg.cache_ttl_dias} dias, {cache.contar()} entradas)")
            st.caption("Guarda só um hash do texto já mascarado e o tema/sentimento. Nunca o texto.")
            if st.button("Excluir cache agora", key="limpar_cache"):
                st.success(f"{cache.limpar()} entradas removidas.")
        with st.expander("Avançado: medir otimizações"):
            workers = st.number_input(
                "Chamadas em paralelo", min_value=1, max_value=16, value=cfg.max_workers, step=1, key="workers",
                help="1 = sequencial (como era antes da Etapa 2). Mais paralelo = menos tempo, mais chamadas simultâneas ao provedor.",
            )
            usar_cache = st.checkbox(
                "Usar cache", value=cache is not None, disabled=cache is None, key="usar_cache",
                help="Desligue para medir o custo e a latência sem cache.",
            )
        if cfg.dashboard_url:
            st.markdown(f"[Painel de observabilidade]({cfg.dashboard_url})")
    return int(workers), bool(usar_cache and cache is not None)


def _entrada_de_dados() -> list[str]:
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
        arquivo = st.file_uploader(f"CSV com uma coluna '{COLUNA_RESPOSTA}'", type=["csv"])
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
        with st.expander("Ver respostas originais"):
            st.write(respostas)
    return respostas


def _previa_de_privacidade(respostas: list[str]) -> None:
    st.markdown("### 2) Privacidade: o que vai para o provedor de IA")
    sanitizadas, entidades = sanitizar_lote(respostas)
    total = sum(entidades.values())
    if total:
        por_tipo = ", ".join(f"{qtd} {tipo.lower()}" for tipo, qtd in sorted(entidades.items()))
        st.success(f"Antes de qualquer envio, o app mascarou **{total}** dado(s) pessoal(is): {por_tipo}.")
    else:
        st.info("Nenhum dado pessoal reconhecível nesta planilha.")
    st.caption(
        "O provedor de IA processa fora do Brasil (transferência internacional, ver docs/lgpd). "
        "A máscara reconhece nomes comuns, CPF, e-mail, telefone e similares; não é garantia de 100%. "
        "Não suba dados reais sem acordo com o controlador."
    )

    mudadas = [(o, s) for o, s in zip(respostas, sanitizadas) if o != s]
    if mudadas:
        comparar = st.checkbox("Comparar com o texto original (mostra os dados originais na tela)", value=False)
        linhas = [
            {"Original": o, "Enviado ao provedor": s} if comparar else {"Enviado ao provedor": s}
            for o, s in mudadas[:10]
        ]
        with st.expander(f"Exemplos de texto mascarado ({len(mudadas)} resposta(s) alteradas)", expanded=True):
            st.dataframe(pd.DataFrame(linhas))


def _mostrar_resultado(resultado) -> None:
    for aviso in resultado.avisos:
        st.warning(aviso)

    st.markdown("### 4) Resultado")
    st.markdown(resultado.resumo)

    m = resultado.metricas
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Duração", f"{m['duracao_s']:.1f} s")
    c2.metric("Chamadas ao LLM", m["chamadas_llm"], help=f"{m['cache_hits']} respostas vieram do cache")
    c3.metric("Tokens (entrada/saída)", f"{m['tokens_entrada']}/{m['tokens_saida']}")
    c4.metric("Custo estimado", f"US$ {m['custo_usd']:.4f}" if m["custo_usd"] else "n/d",
              help="Exige LLM_PRECO_ENTRADA_USD_POR_MTOK e LLM_PRECO_SAIDA_USD_POR_MTOK configurados.")

    st.markdown("#### Detalhe por resposta (texto como foi enviado ao provedor)")
    tabela = pd.DataFrame(resultado.classificacoes)[["resposta", "tema", "sentimento", "origem"]]
    st.dataframe(tabela)

    st.caption(
        "Este resultado não é salvo em lugar nenhum. O único dado que persiste é o cache "
        "(hash + tema + sentimento), que expira sozinho."
    )


def main():
    st.set_page_config(page_title="FeedbackLoop — Insights", page_icon="📊")
    cfg, cache = _inicializar()
    workers, usar_cache = _barra_lateral(cfg, cache)

    st.title("📊 FeedbackLoop — Survey Insights")
    st.caption(
        "Cole ou suba as respostas abertas da pesquisa de clima. "
        "A gente agrupa por tema, marca o sentimento e gera um resumo executivo."
    )

    respostas = _entrada_de_dados()
    if respostas:
        _previa_de_privacidade(respostas)

    st.markdown("### 3) Análise")
    quantidade_temas = st.slider("Quantidade de temas no resumo", 3, 15, 8)

    if st.button("Analisar respostas", type="primary", disabled=not respostas, key="analisar"):
        # cria o cliente real só na hora de rodar (precisa da OPENAI_API_KEY)
        try:
            cliente = ClienteLLM()
        except KeyError:
            st.error("OPENAI_API_KEY não configurada. Veja o .env.example.")
            return

        try:
            with st.spinner("Classificando as respostas e montando o resumo..."):
                resultado = analisar(
                    cliente,
                    respostas,
                    top_n=quantidade_temas,
                    max_workers=workers,
                    cache=cache if usar_cache else None,
                    modelo=getattr(cliente, "modelo", cfg.modelo),
                )
        except AnaliseFalhouError as exc:
            st.error(MENSAGENS_DE_ERRO.get(exc.tipo_erro, f"Erro do provedor de IA ({exc.tipo_erro})."))
            return

        _mostrar_resultado(resultado)


if __name__ == "__main__":
    main()
