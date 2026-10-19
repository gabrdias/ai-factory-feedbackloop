# Changelog

## [v1.0.0] - 2026-10-19 (Etapa 2: segurança, LGPD, observabilidade e otimização)

### Segurança
- Trio sagrado verificado por testes (`.env` ignorado, `.env.example` só com placeholders, toda variável lida pelo código documentada); gitleaks no histórico completo, `pip-audit` e execução semanal agendada
- Um segredo por ambiente (3 chaves de API, 2 tokens do Grafana, 1 deploy hook por ambiente), `sync: false` no `render.yaml`
- Procedimento de rotação de credenciais (`docs/seguranca/`), executado em 19/10/2026 com um incidente real no prod (401 por revogação precoce), post-mortem e botão "Testar conexão com o provedor"

### LGPD
- Sanitização de PII antes de toda chamada ao LLM, com trava final (fail-closed) e resumo alimentado só por agregados (`feedbackloop/pii.py`); recall medido: 100% nas categorias cobertas, 87,5% no total, preservação de termos legítimos de 95,9%
- Prévia de privacidade no app (texto original ao lado do mascarado)
- Mapa de dados pessoais com base legal por ponto de coleta, política de retenção com mecanismo real (purga + botão de exclusão), documento de transferência internacional (`docs/lgpd/`)

### Observabilidade
- OpenTelemetry (traces e métricas) para o Grafana Cloud, sem texto de resposta nem dado pessoal na telemetria
- Cinco métricas essenciais com limiares justificados, dashboard versionado (`observabilidade/`) e o alerta `FL-ERRO-LLM` (P2) testado ao vivo, com runbook

### Otimização
- Classificação em paralelo (`LLM_MAX_WORKERS`, padrão 8) e cache com TTL (`CACHE_TTL_DIAS`, padrão 30)
- Medido: p50 de 32,3 s para 6,8 s (−79%) e 2,7 s com cache quente (−92%) no dev; replicado localmente (30,4 s, 6,1 s, 2,8 s); custo por análise inalterado pela concorrência (≈ US$ 0,0087)
- Relatório com limitações e trade-offs: `docs/otimizacao/`

### Documentação
- README v1.0 (LGPD, observabilidade, otimizações, troubleshooting), C4 atualizado, ADR-003 a ADR-005, status da auditoria

### Outras mudanças
- Mensagens de erro por tipo de falha do provedor; falha de uma resposta não derruba a análise
- Aceita apelidos comuns para a coluna do CSV; `OPENAI_MODEL` passa a ter efeito

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
