# Pacote feedbackloop — pipeline de análise de respostas abertas de pesquisa.
# (Rafael)
#
# A ideia é manter a regra de negócio aqui dentro e deixar o app.py só com a UI.
# Quase consegui. Quase. (ver README, seção dívida técnica)

from .pipeline import (
    analisar,
    classificar_resposta,
    contar_sentimentos,
    contar_temas,
    montar_resumo,
    parse_classificacao,
    parse_sentimento,
)

__all__ = [
    "analisar",
    "classificar_resposta",
    "contar_sentimentos",
    "contar_temas",
    "montar_resumo",
    "parse_classificacao",
    "parse_sentimento",
]
