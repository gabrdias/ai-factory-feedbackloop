# FeedbackLoop — Survey Insights

![CI/CD](https://github.com/gabrdias/ai-factory-feedbackloop/actions/workflows/ci-cd.yml/badge.svg)
![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)

> Projeto didático da disciplina **AI Factory: Build, Deploy and Showcase** — Etapa 1.
> Mantido por **Gabriel Dias** ([@gabrdias](https://github.com/gabrdias)), a partir do protótipo herdado de Rafael Crispim.

> Testado ao vivo no vídeo de demonstração da Etapa 1, gravado em 21/09/2026.

## Problema

O produto da FeedbackLoop já analisa bem as perguntas **fechadas** de pesquisas de clima (notas, múltipla escolha). O gargalo é o **texto livre**: clientes de RH recebem centenas a milhares de respostas abertas por pesquisa e não têm como ler tudo — um analista passa dias lendo comentário por comentário, de forma subjetiva e sem escalar. É o maior pedido de feature e o maior gargalo de percepção de valor do produto.

## Solução

Uma aplicação web que recebe respostas abertas em lote (colar texto, subir CSV ou usar dados de exemplo) e devolve:

1. **Agrupamento por tema** (carga de trabalho, liderança, salário etc.)
2. **Classificação de sentimento** por resposta (positivo / neutro / negativo)
3. **Resumo executivo** com os principais temas e ações recomendadas

É análise em lote, não é chatbot: entram N respostas, sai um relatório.

## URL pública

| Ambiente | URL | Branch |
|---|---|---|
| Produção | [feedbackloop-prod-bx3u.onrender.com](https://feedbackloop-prod-bx3u.onrender.com) | `main` |
| Desenvolvimento | [feedbackloop-dev-6yzb.onrender.com](https://feedbackloop-dev-6yzb.onrender.com) | `develop` |

## Como rodar localmente

```bash
git clone https://github.com/gabrdias/ai-factory-feedbackloop.git
cd ai-factory-feedbackloop
pip install -r requirements.txt
cp .env.example .env   # preencha OPENAI_API_KEY
streamlit run app.py
```

Abra no navegador, escolha **"Usar dados de exemplo"** e clique em **Analisar**.

Rodar os testes (todos offline, não chamam a API real):

```bash
pytest -q
```

## Arquitetura

- `app.py` — só a UI do Streamlit (entrada de dados + exibição).
- `feedbackloop/llm.py` — interface fina com o LLM (`ClienteLLM.completar`), mockável de propósito.
- `feedbackloop/pipeline.py` — o núcleo: classificação, agregação e resumo. Funções puras separadas das que chamam o LLM.
- `data/` — 36 respostas sintéticas de exemplo (ver `data/AVISO-DADOS-SINTETICOS.md`).
- `tests/` — smoke tests e testes de pipeline, todos offline com LLM mockado.

Diagramas C4 (contexto e contêineres): [`docs/architecture/`](docs/architecture/).

## Decisões de arquitetura

| Documento | Conteúdo |
|---|---|
| [Auditoria do protótipo](docs/auditoria-prototipo.md) | Lacunas identificadas no código herdado, por categoria e risco |
| [Matriz de decisão de stack](docs/decisao-stack.md) | Comparação dos 8 protótipos disponíveis, critérios e pesos |
| [ADR-001](docs/adr/0001-escolha-do-prototipo-e-stack.md) | Escolha do FeedbackLoop e alternativas descartadas |
| [ADR-002](docs/adr/0002-plataforma-de-deploy.md) | Escolha do Render como plataforma de deploy |

## Testes e qualidade

Três smoke tests, cobrindo desde a lógica até a URL pública em produção:

1. **`tests/test_smoke.py::test_app_streamlit_sobe_sem_erro`** — a aplicação Streamlit sobe de ponta a ponta sem lançar exceção (usa `streamlit.testing.v1.AppTest`).
2. **`tests/test_smoke.py::test_pipeline_processa_o_csv_de_exemplo_real`** — o pipeline completo processa o CSV de exemplo real do repositório, com LLM mockado.
3. **`scripts/smoke_test_deploy.py`** — depois do deploy, faz um HTTP GET no endpoint de saúde do Streamlit (`/_stcore/health`) da URL pública e confirma resposta `200`. Roda automaticamente no workflow de deploy, não no `pytest -q` local.

`tests/test_pipeline.py` cobre a lógica de negócio em mais detalhe (parsing, agregação, casos de borda).

## Deploy e CI/CD

Pipeline em [`.github/workflows/ci-cd.yml`](.github/workflows/ci-cd.yml), com dois jobs:

1. **`test`** (toda branch e PR para `main`): instala dependências, roda `pytest -q` e verifica segredos vazados com [gitleaks](https://github.com/gitleaks/gitleaks).
2. **`deploy`** (só em push para `main` ou `develop`, e só se `test` passar): dispara o deploy no Render via *deploy hook*, aguarda o serviço subir e roda o smoke test 3 contra a URL pública.

A plataforma de hospedagem é o [Render](https://render.com) (ver [ADR-002](docs/adr/0002-plataforma-de-deploy.md)), configurada via [`render.yaml`](render.yaml): dois Web Services (`feedbackloop-dev` e `feedbackloop-prod`), cada um com `autoDeploy: false` — o deploy só acontece pelo GitHub Actions, nunca direto do push, para garantir que só vai pro ar o que passou no CI.

### Configuração necessária (uma vez, feita manualmente)

No GitHub, em **Settings → Environments**, criar dois ambientes:

| Ambiente do GitHub | Branch | Secret `RENDER_DEPLOY_HOOK` | Variável `APP_URL` |
|---|---|---|---|
| `development` | `develop` | Deploy Hook do serviço `feedbackloop-dev` (Render → Settings → Deploy Hook) | URL pública do `feedbackloop-dev` |
| `production` | `main` | Deploy Hook do serviço `feedbackloop-prod` | URL pública do `feedbackloop-prod` |

No Render, em cada um dos dois serviços, configurar `OPENAI_API_KEY` manualmente (Environment → Add Environment Variable) — **com uma chave diferente em cada serviço**.

## Ambientes

| | Desenvolvimento | Produção |
|---|---|---|
| Branch | `develop` | `main` |
| Serviço no Render | `feedbackloop-dev` | `feedbackloop-prod` |
| Segredo `OPENAI_API_KEY` | Próprio, configurado no serviço `feedbackloop-dev` | Próprio, configurado no serviço `feedbackloop-prod` |
| Quem aciona o deploy | Push em `develop` (via GitHub Actions) | Push em `main` (via GitHub Actions) |

## Segurança e segredos

- Nenhum segredo é commitado: `.env` está no `.gitignore`, e `.env.example` traz só um placeholder.
- Toda chave usada localmente pelo autor anterior do protótipo foi tratada como comprometida e **rotacionada** antes deste repositório se tornar público.
- O histórico completo do Git foi verificado com [`gitleaks`](https://github.com/gitleaks/gitleaks) antes da publicação, e o mesmo scanner roda em todo push via GitHub Actions.

## Dívida técnica conhecida

Herdada do protótipo e **ainda não resolvida nesta etapa** — mitigação técnica planejada para a Semana 6 do roteiro do time (ver `BRIEFING.md`):

- Respostas vão **sem anonimização** para o provedor de LLM (LGPD — ver aviso no próprio app).
- Sem cache: reprocessa tudo a cada análise (custo linear com o uso).
- Sem persistência: fechar a aba perde o resultado.
- Sem taxonomia fixa de temas nem avaliação automatizada de qualidade do resumo.

Detalhe completo, com risco priorizado: [`docs/auditoria-prototipo.md`](docs/auditoria-prototipo.md).

## Versionamento

Conventional commits (`feat:`, `fix:`, `docs:` etc.) desde a adoção do projeto. Releases seguem [SemVer](https://semver.org/lang/pt-BR/) e ficam documentadas em [`CHANGELOG.md`](CHANGELOG.md) e nas [GitHub Releases](https://github.com/gabrdias/ai-factory-feedbackloop/releases) do repositório.

## Origem do projeto

Este projeto nasceu como protótipo de Rafael Crispim, Data Analyst da FeedbackLoop Tecnologia (empresa fictícia, material didático), que demonstrou a ideia a dois clientes-piloto e depois saiu da empresa. Notas técnicas originais dele seguem preservadas em [`docs/notas-rafael.md`](docs/notas-rafael.md) por transparência e contexto histórico.

## Licença

[MIT](LICENSE)
