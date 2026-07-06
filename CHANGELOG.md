# Changelog

## [v0.2]
- Pipeline movido pro pacote `feedbackloop/` (separação UI x lógica)
- Interface de LLM mockável (`feedbackloop/llm.py`) + testes offline em `tests/`
- Resumo executivo agora junta números calculados em código + texto do modelo
- 36 respostas sintéticas de exemplo em `data/` (com nomes fake pra lição de LGPD)

## [v0.1]
- Versão inicial do protótipo FeedbackLoop Survey Insights
- Streamlit + um modelo GPT pequeno da OpenAI
- Classificação de tema + sentimento por resposta e resumo executivo (Rafael)
