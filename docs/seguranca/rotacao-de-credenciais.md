# Rotação de credenciais

Procedimento para trocar cada segredo do projeto **sem derrubar o serviço** e sem deixar a credencial antiga viva. Cada execução é anotada em [`registro-de-rotacoes.md`](registro-de-rotacoes.md), sem nunca escrever o valor do segredo.

## 1. Inventário de segredos

Regra de ouro: **um segredo diferente por ambiente** (local, dev, prod). Se uma chave vaza, o estrago fica restrito a um ambiente e a revogação não derruba os outros.

| Segredo | Para quê | Onde vive | Um por ambiente? | Validade (rotação planejada) | Se vazar |
|---|---|---|---|---|---|
| `OPENAI_API_KEY` | Chamar o provedor de IA | Render (`feedbackloop-dev`, `feedbackloop-prod`) e `.env` local | **Sim: 3 chaves** (`feedbackloop-local-…`, `-dev-…`, `-prod-…`) | 90 dias | Custo indevido e abuso da conta |
| `GRAFANA_TOKEN` (+ `GRAFANA_INSTANCE_ID`, que **não** é segredo) | Enviar traces e métricas ao Grafana Cloud | Render (dev e prod) | **Sim: 2 tokens** (`feedbackloop-dev`, `feedbackloop-prod`) | 90 dias | Alguém injeta métricas falsas e consome a cota; **não** dá acesso a dados de respondentes (a telemetria não os contém) |
| `RENDER_DEPLOY_HOOK` | O GitHub Actions dispara o deploy | GitHub → Settings → Environments (`development`, `production`) | **Sim: 1 por ambiente** | 90 dias (ou em qualquer suspeita) | Qualquer pessoa com a URL dispara um deploy da branch configurada |
| `GITHUB_TOKEN` do Actions | Leitura do repositório no CI | Gerado automaticamente por execução | — | Efêmero (expira ao fim do job) | Não se aplica |

Variáveis que **não** são segredo e podem aparecer em documentos: `APP_URL`, `OTEL_EXPORTER_OTLP_ENDPOINT`, `GRAFANA_INSTANCE_ID`, `LLM_MAX_WORKERS`, `CACHE_TTL_DIAS`.

## 2. Princípios

1. **Nunca** em código, log, span, commit, print, vídeo ou conversa. Colar só no campo do Render/GitHub ou no `.env` local.
2. **Criar a nova antes de matar a antiga.** Ordem: criar → trocar → verificar → revogar. Assim não há indisponibilidade.
3. **Privilégio mínimo.** Token do Grafana só com escopos de escrita de telemetria; nunca um token de administrador.
4. **Nome com data** (`feedbackloop-prod-2026-10`): quem olha o painel do provedor sabe qual é a chave, de quando é e se está atrasada.
5. **Evidência sem segredo:** o registro guarda data, ambiente, resultado da verificação e o que foi revogado. Nunca o valor.

## 3. Rotação planejada — `OPENAI_API_KEY`

Pré-requisito: acesso ao painel da OpenAI (Settings → API keys), ao Render e ao `.env` local.

1. **Criar** a nova chave do ambiente, com nome datado (ex.: `feedbackloop-dev-2026-10`). Copiar na hora (só aparece uma vez).
2. **Trocar no ambiente de desenvolvimento primeiro:** Render → `feedbackloop-dev` → Environment → editar `OPENAI_API_KEY` → *Save, rebuild, and deploy*.
3. **Verificar o dev:** o health check responde `200` (`/_stcore/health`) **e** uma análise de teste com os dados sintéticos termina sem erro de autenticação. Se falhar, a chave antiga continua válida: corrija e repita, sem pressa.
4. **Trocar em produção** repetindo 2 e 3 em `feedbackloop-prod`, com a chave `-prod-`.
5. **Atualizar o `.env` local** com a chave `-local-` (arquivo ignorado pelo Git; `git check-ignore -v .env` confirma).
6. **Revogar a chave antiga** no painel da OpenAI (Revoke), só depois que dev e prod passaram na verificação.
7. **Confirmar que a antiga morreu:** uma chamada com a chave revogada deve devolver `401`. Não é preciso guardar a chave para isso; o painel mostra a data de último uso e o status "revogada".
8. **Registrar** em [`registro-de-rotacoes.md`](registro-de-rotacoes.md).

## 4. Rotação planejada — `GRAFANA_TOKEN`

1. Grafana Cloud → Connections → OpenTelemetry (ou Administration → Access policies): gerar novo token com o mesmo escopo.
2. Render → Environment → atualizar `GRAFANA_TOKEN` do serviço → *Save, rebuild, and deploy*.
3. Verificar: após a reinicialização, os dados do ambiente voltam a chegar no Grafana (Explore → métrica `feedbackloop_analises_total` aumenta depois de uma análise de teste).
4. Revogar o token antigo na tela de tokens e registrar.

## 5. Rotação planejada — `RENDER_DEPLOY_HOOK`

1. Render → serviço → Settings → Deploy Hook → *Regenerate*.
2. GitHub → Settings → Environments → (`development` ou `production`) → atualizar o secret `RENDER_DEPLOY_HOOK`.
3. Verificar: re-executar o workflow (Actions → *Re-run all jobs*); o job "Deploy" tem que ficar verde.
4. Registrar. O hook anterior deixa de valer assim que o novo é gerado.

## 6. Procedimento de emergência (suspeita ou confirmação de vazamento)

Aqui a ordem **inverte**: primeiro estancar, depois consertar.

1. **Revogar já** a credencial exposta (aceitando indisponibilidade breve naquele ambiente).
2. **Criar a nova** e instalar conforme as seções 3 a 5.
3. **Medir o estrago:** painel de uso da OpenAI (picos de custo no período), histórico do Grafana, e `gitleaks detect` no repositório para saber se o segredo foi para o Git.
4. **Se foi para o Git:** a credencial já está revogada, então o risco principal acabou; avaliar se vale limpar o histórico (o enunciado trata chave no histórico como falha grave, então limpar é recomendado) e rodar o gitleaks no histórico inteiro.
5. **Avisar** o controlador se houver qualquer chance de dado pessoal exposto (ver [política de retenção, seção de incidentes](../lgpd/politica-de-retencao-e-exclusao.md)).
6. **Post-mortem** sem culpados, no padrão de [`docs/post-mortem-2026-09-21.md`](../post-mortem-2026-09-21.md).

**Sinais que disparam a emergência:** gitleaks vermelho no CI; e-mail do provedor sobre chave exposta; pico de custo; alerta de erro 401/429 sem mudança de código.

## 7. O que impede o vazamento em primeiro lugar (controles automáticos)

| Controle | Onde | Evidência |
|---|---|---|
| `.env` ignorado, `.env.example` só com placeholders | `.gitignore`, `.env.example` | `tests/test_trio_sagrado.py` (roda em todo push) |
| Varredura de segredos no histórico completo | `gitleaks` no CI, a cada push e toda segunda | Job "Testes + verificação de segredos" |
| Nenhum arquivo versionado com formato de chave de API | teste automatizado | `test_nenhum_arquivo_versionado_tem_cara_de_chave_de_api` |
| Toda variável lida pelo código está documentada | teste automatizado | `test_toda_variavel_lida_pelo_codigo_esta_documentada_no_env_example` |
| Token nunca vai para span, métrica ou log | teste automatizado | `test_o_token_nunca_aparece_em_span_metrica_nem_log` |
| Segredos de produção só no painel da plataforma, valores `sync: false` no `render.yaml` | `render.yaml` | Arquivo versionado sem nenhum valor |

## 8. Calendário

Rotação planejada a cada **90 dias**, a partir da data do último registro. A próxima fica anotada em [`registro-de-rotacoes.md`](registro-de-rotacoes.md).
