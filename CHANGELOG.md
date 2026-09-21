# Changelog

## [v0.3.0] - 2026-09-21
- Auditoria do protótipo, matriz de decisão de stack, ADR-001 e ADR-002 (`docs/`)
- Diagramas C4 (níveis 1 e 2) em `docs/architecture/`
- Smoke tests 1 e 2 offline (`tests/test_smoke.py`) e smoke test 3 de URL pública (`scripts/smoke_test_deploy.py`)
- Pipeline de CI/CD via GitHub Actions (`.github/workflows/ci-cd.yml`): testes + gitleaks + deploy automático no Render
- Configuração de deploy (`render.yaml`) com ambientes de desenvolvimento e produção separados
- README v1: problema, solução, arquitetura, deploy e ambientes
- fix: `httpx` fixado (incompatibilidade real com o SDK da OpenAI, descoberta em produção) + teste de regressão
- Rollback testado em produção, com evidências e post-mortem (`docs/post-mortem-2026-09-21.md`)

## [v0.2]
- Pipeline movido pro pacote `feedbackloop/` (separação UI x lógica)
- Interface de LLM mockável (`feedbackloop/llm.py`) + testes offline em `tests/`
- Resumo executivo agora junta números calculados em código + texto do modelo
- 36 respostas sintéticas de exemplo em `data/` (com nomes fake pra lição de LGPD)

## [v0.1]
- Versão inicial do protótipo FeedbackLoop Survey Insights
- Streamlit + um modelo GPT pequeno da OpenAI
- Classificação de tema + sentimento por resposta e resumo executivo (Rafael)
