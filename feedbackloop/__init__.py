# Pacote feedbackloop — pipeline de análise de respostas abertas de pesquisa.
#
# A regra de negócio fica aqui dentro; o app.py só cuida da UI.

__version__ = "1.0.0"

from .pii import sanitizar, sanitizar_lote  # noqa: E402
from .pipeline import (  # noqa: E402
    analisar,
    classificar_resposta,
    contar_sentimentos,
    contar_temas,
    montar_resumo,
    parse_classificacao,
    parse_sentimento,
)

__all__ = [
    "__version__",
    "analisar",
    "classificar_resposta",
    "contar_sentimentos",
    "contar_temas",
    "montar_resumo",
    "parse_classificacao",
    "parse_sentimento",
    "sanitizar",
    "sanitizar_lote",
]
