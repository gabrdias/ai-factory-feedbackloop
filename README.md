# FeedbackLoop — Survey Insights

![CI/CD](https://github.com/gabrdias/ai-factory-feedbackloop/actions/workflows/ci-cd.yml/badge.svg)
![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)

> Projeto didático da disciplina **AI Factory: Build, Deploy and Showcase**. **v1.0 (Etapa 2): segurança, LGPD, observabilidade e otimização medida.**
> Mantido por **Gabriel Dias** ([@gabrdias](https://github.com/gabrdias)), a partir do protótipo herdado de Rafael Crispim.

## Problema

O produto da FeedbackLoop já analisa bem as perguntas **fechadas** de pesquisas de clima (notas, múltipla escolha). O gargalo é o **texto livre**: clientes de RH recebem centenas a milhares de respostas abertas por pesquisa e não têm como ler tudo. Um analista passa dias lendo comentário por comentário, de forma subjetiva e sem escalar. É o maior pedido de feature e o maior gargalo de percepção de valor do produto.

Para virar produto, o protótipo precisava resolver três problemas: **dado de pessoa** (as respostas citam gestores e colegas pelo nome e iam cruas para um provedor no exterior), **dinheiro real a cada chamada de IA** e **falha em silêncio** (sem métrica, sem alerta).

## Solução

Uma aplicação web que recebe respostas abertas em lote (colar texto, subir CSV ou usar dados de exemplo) e devolve:

1. **Agrupamento por tema** (carga de trabalho, liderança, salário etc.)
2. **Classificação de sentimento** por resposta (positivo / neutro / negativo)
3. **Resumo executivo** com os principais temas e ações recomendadas

É análise em lote, não é chatbot: entram N respostas, sai um relatório. Na v1.0, antes de qualquer envio ao provedor de IA, **o app mascara os dados pessoais** e mostra ao analista, lado a lado, o que foi enviado.

## URL pública

| Ambiente | URL | Branch |
|---|---|---|
| Produção | [feedbackloop-prod-bx3u.onrender.com](https://feedbackloop-prod-bx3u.onrender.com) | `main` |
| Desenvolvimento | [feedbackloop-dev-6yzb.onrender.com](https://feedbackloop-dev-6yzb.onrender.com) | `develop` |

O serviço gratuito do Render dorme sem uso: o primeiro acesso pode levar cerca de um minuto para acordar.

## Como rodar localmente

```bash
git clone https://github.com/gabrdias/ai-factory-feedbackloop.git
cd ai-factory-feedbackloop
python -m venv .venv                 # Python 3.12
source .venv/bin/activate            # Windows (PowerShell): .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env                 # Windows (PowerShell): Copy-Item .env.example .env
# edite o .env e coloque a sua OPENAI_API_KEY (o arquivo é ignorado pelo Git)
streamlit run app.py
```

Abra no navegador, escolha **"Usar dados de exemplo"** (36 respostas sintéticas) e clique em **Analisar respostas**. Marque **"Comparar com o texto original"** para ver o que foi mascarado.

Testes (todos offline, nenhum chama a API real, 95 no total):

```bash
pytest -q
```

Todas as variáveis de ambiente estão documentadas, com valor padrão, em [`.env.example`](.env.example).

## Arquitetura

```
Analista ──HTTPS──▶ Web App (Streamlit, Render) ──texto MASCARADO──▶ OpenAI API
                        │  ├─ sanitização de PII (antes de qualquer envio)
                        │  ├─ pipeline com 8 chamadas em paralelo
                        │  └─ cache SQLite (hash + tema + sentimento, TTL 30 dias)
                        └──OTLP: traces e métricas, sem dado pessoal──▶ Grafana Cloud ──e-mail──▶ AI Engineer
```

| Arquivo | Responsabilidade |
|---|---|
| `app.py` | UI do Streamlit, prévia de privacidade, controles, botão de teste de conexão |
| `feedbackloop/pii.py` | Sanitização de dados pessoais e trava final |
| `feedbackloop/pipeline.py` | Classificação (em paralelo), agregação e resumo |
| `feedbackloop/llm.py` | Cliente do provedor: timeout, retry, custo e erro por chamada |
| `feedbackloop/cache.py` | Cache com prazo de validade e purga |
| `feedbackloop/observabilidade.py` | OpenTelemetry: spans, métricas, log JSON |
| `feedbackloop/config.py` | Toda a configuração, vinda do ambiente |
| `scripts/` | Benchmark, avaliação de PII, retenção, geração do dashboard |
| `observabilidade/` | Dashboard (JSON importável) e definição dos alertas |

Diagramas C4 (contexto e contêineres, com as fronteiras de dados): [`docs/architecture/`](docs/architecture/).

## Decisões de arquitetura

| Documento | Conteúdo |
|---|---|
| [Auditoria do protótipo](docs/auditoria-prototipo.md) | Lacunas do código herdado e **situação de cada uma após a Etapa 2** |
| [Matriz de decisão de stack](docs/decisao-stack.md) | Comparação dos 8 protótipos disponíveis, critérios e pesos |
| [ADR-001](docs/adr/0001-escolha-do-prototipo-e-stack.md) | Escolha do FeedbackLoop e alternativas descartadas |
| [ADR-002](docs/adr/0002-plataforma-de-deploy.md) | Escolha do Render como plataforma de deploy |
| [ADR-003](docs/adr/0003-observabilidade-opentelemetry-grafana-cloud.md) | OpenTelemetry + Grafana Cloud |
| [ADR-004](docs/adr/0004-sanitizacao-de-pii-por-regras.md) | Sanitização de PII por regras, comparada com NER (spaCy), com medição |
| [ADR-005](docs/adr/0005-otimizacao-concorrencia-e-cache.md) | Chamadas em paralelo e cache com prazo de validade |

## Segurança e segredos

**O trio sagrado:**

| Peça | Papel | Garantia automática |
|---|---|---|
| `.env` | Segredos reais de quem roda localmente | Ignorado pelo Git (`.gitignore`); `git check-ignore -v .env` confirma |
| `.gitignore` | Impede commitar `.env`, caches e bancos locais | Teste em `tests/test_trio_sagrado.py` |
| `.env.example` | Modelo versionado, **só com placeholders** | Teste: toda variável que o código lê está documentada nele |

* **Um segredo diferente por ambiente.** Três chaves de API (local, dev, prod), dois tokens do Grafana, um deploy hook por ambiente. Em dev e prod, os valores ficam só no painel do Render (`sync: false` no [`render.yaml`](render.yaml)).
* **Varredura contínua:** [gitleaks](https://github.com/gitleaks/gitleaks) no histórico completo a cada push e toda segunda; `pip-audit` nas dependências ([resultado](docs/seguranca/auditoria-de-dependencias.md)); teste que reprova qualquer arquivo versionado com formato de chave de API.
* **O token nunca aparece** em span, métrica ou log (teste automatizado).

### Rotação de credenciais

Procedimento documentado, na ordem **criar a nova → trocar → verificar na instância em execução → só então revogar a antiga**: [`docs/seguranca/rotacao-de-credenciais.md`](docs/seguranca/rotacao-de-credenciais.md). Inclui o procedimento de emergência (aqui a ordem inverte: revoga primeiro). Cada execução fica em [`registro-de-rotacoes.md`](docs/seguranca/registro-de-rotacoes.md), sem nunca registrar o valor da chave.

**Foi executado de verdade em 19/10/2026**, nos três ambientes, e **deu errado do jeito certo**: a chave antiga do prod foi revogada antes de eu provar que a instância usava a nova (o "Save changes" do Render só grava, não reinicia), e o prod respondeu 401 por alguns minutos. A verificação pegou, o procedimento foi corrigido e o app ganhou o botão **"Testar conexão com o provedor"**: [post-mortem](docs/post-mortem-2026-10-19-rotacao-de-chave.md).

## LGPD

Documentação técnica, **não parecer jurídico**. Os pontos que dependem do jurídico estão listados como pendência.

| Tema | O que foi feito | Documento |
|---|---|---|
| **Papéis** | Clientes são controladores; a FeedbackLoop é operadora; OpenAI, Render e Grafana são suboperadores | [Mapa de dados pessoais](docs/lgpd/mapa-de-dados-pessoais.md) |
| **Onde há dado pessoal e base legal** | 8 pontos de coleta mapeados (P1 a P8), cada um com titulares, finalidade, base legal, retenção e controle técnico. Base: **legítimo interesse (art. 7º, IX)**; consentimento **não** é usado (relação de trabalho) | [Mapa de dados pessoais](docs/lgpd/mapa-de-dados-pessoais.md) |
| **Minimização antes do LLM** | Nomes, e-mail, telefone, CPF e similares viram marcadores antes de **toda** chamada; o resumo só recebe agregados; uma **trava final bloqueia o envio** se restar PII reconhecível | [ADR-004](docs/adr/0004-sanitizacao-de-pii-por-regras.md) |
| **Quanto a sanitização acerta (medido)** | Recall **100%** nas categorias que a regra cobre e **87,5%** no conjunto total; termos legítimos preservados em **95,9%**. **Nomes raros sem pista de contexto e nomes em minúsculas passam.** Por isso o texto mascarado continua sendo tratado como dado pessoal | [Avaliação](docs/lgpd/avaliacao-sanitizacao-pii.md) |
| **Retenção e exclusão** | Texto da resposta: só na memória da sessão. Cache: hash + tema + sentimento, **30 dias** (teto do briefing: 90), purga na subida e a cada hora, botão **"Excluir cache agora"**. Cenário reproduzível: `python scripts/retencao.py demo` | [Política de retenção](docs/lgpd/politica-de-retencao-e-exclusao.md) |
| **Transferência internacional** | Texto mascarado vai à OpenAI (EUA); art. 33, II. **O texto original passa pela memória do Render**, porque a sanitização roda dentro do app: documentado, com a região a confirmar | [Transferência internacional](docs/lgpd/transferencia-internacional.md) |
| **Direitos do titular e incidentes** | Encaminhamento ao controlador; plano de resposta a incidente | [Política de retenção](docs/lgpd/politica-de-retencao-e-exclusao.md) |

**Dados de teste, demonstração e vídeo são 100% sintéticos.** Pendências que exigem decisão humana ou jurídica (DPA do provedor, LIA por cliente, RIPD, Encarregado, região do Render): P-1 a P-6 no mapa de dados.

## Observabilidade

**Dashboard (Grafana Cloud):** [LINK_DO_DASHBOARD](LINK_DO_DASHBOARD) · definição versionada em [`observabilidade/dashboard-feedbackloop.json`](observabilidade/dashboard-feedbackloop.json) (gerada por `scripts/gerar_dashboard.py`). Os números do dashboard conferem com o [relatório de otimização](docs/otimizacao/otimizacao-concorrencia-e-cache.md#44-conferência-com-o-dashboard-do-grafana-fonte-independente), inclusive as contagens de análises.

Cada análise gera **um trace** (`analise → pii.sanitizar, classificar.lote → classificar.resposta → llm.chamada, resumo.gerar`) e métricas, enviados por OpenTelemetry. **Nenhum span, métrica ou log contém texto de resposta, nome ou token** (testes automatizados).

### As cinco métricas e seus limiares

| Métrica | Verde / limiar | Por que esse número | Valor medido |
|---|---|---|---|
| **Latência** (p50 / p95 / p99 por análise de 36 respostas) | p50 ≤ 8 s, p95 ≤ 20 s, p99 ≤ 30 s | 10 s é o limite clássico de atenção; 30 s é o máximo tolerável sem feedback | p50 **6,8 s**, p95 7,2 s (antes: 32,3 s e 36,4 s) |
| **Custo** por análise | ≤ US$ 0,015 (amarelo até US$ 0,03) | ≈ 1,7x o custo medido; se triplicar, mudou o prompt, o modelo ou há laço de tentativas | **US$ 0,0087** (≈ 6.372 tokens de entrada e ≈ 880 de saída) |
| **Erro** (falha das chamadas ao provedor) | < 2% (amarelo até 5%) | O retry do SDK já absorve falha isolada; o que sobra é sistêmico | 0 erros nas execuções de teste |
| **Volume** (análises e respostas) | informativo; > 100 análises/h = alerta P3 | O piloto espera dezenas por dia; 100/h é ≈ 11x o esperado | n/a (piloto) |
| **Qualidade** (proxies) | < 5% "Não classificado"; fragmentação de temas ≤ 70% (detecção de piora) | Sem rubrica humana, uso dois proxies automáticos | 0% não classificadas; fragmentação **64% a 67%** (**meta de produto ≤ 35% não atingida**) |

Detalhes, fórmulas e fontes de cada limiar: [`docs/observabilidade/metricas-e-alertas.md`](docs/observabilidade/metricas-e-alertas.md).

### O alerta

| | |
|---|---|
| **Regra** | `FL-ERRO-LLM`: provedor de IA falhando |
| **Dispara quando** | mais de **20%** das chamadas ao provedor falham em **5 minutos**, com pelo menos 5 chamadas, por 1 minuto seguido |
| **Prioridade** | **P2** (funcionalidade principal degradada; resposta no mesmo dia útil, em até 1 h) |
| **Público** | AI Engineer de plantão; escalar para a Head de People Analytics se passar de 1 h |
| **Canal** | E-mail (contact point `ai-eng-oncall-email`) |
| **Ação** | [Runbook](docs/observabilidade/runbook.md), com a seção da regra |

**Testado ao vivo em 19/10/2026:** com uma chave inválida no dev, o e-mail de disparo chegou cerca de **1 min 25 s** após a primeira falha. O simulado achou três limites reais (o e-mail caiu no **spam**, a configuração de "sem dados" gerava **ruído**, e a regra **se resolve sozinha** sem tráfego mesmo com a chave ainda quebrada): [simulado, com capturas](docs/observabilidade/simulado-de-alerta-2026-10-19.md).

Duas regras P3 (`FL-LATENCIA-P95`, `FL-VOLUME-ANOMALO`) estão **definidas** em [`observabilidade/alertas.yaml`](observabilidade/alertas.yaml), mas **ainda não foram criadas** no Grafana.

## Otimização medida: chamadas em paralelo e cache

**Problema:** a análise fazia 37 chamadas ao modelo, **uma depois da outra** (p50 de 32,3 s, acima do limite de 30 s do produto), e reanalisar pagava tudo de novo. **Mudança:** pool de 8 chamadas em paralelo (`LLM_MAX_WORKERS`) e cache com prazo de validade (`CACHE_TTL_DIAS`).

Medido no ambiente dev (n = 5 por cenário; a 1ª execução de cada um é aquecimento e foi descartada) e **replicado localmente** com `scripts/benchmark.py`:

| Cenário | p50 no dev | p50 local | Chamadas ao LLM | Custo por análise |
|---|---:|---:|---:|---:|
| **Antes:** 1 em paralelo, sem cache | 32,3 s | 30,4 s | 37 | US$ 0,0087 |
| **Depois:** 8 em paralelo | **6,8 s** (−79%) | 6,1 s (−80%) | 37 | US$ 0,0087 |
| **Depois + cache quente** (reanálise) | **2,7 s** (−92%) | 2,8 s (−91%) | 1 | US$ 0,0015 |

**Trade-offs (sem esconder):**

* O ganho vem de **esperar menos, não de fazer menos**: o custo por análise da concorrência é o mesmo. Só o cache reduz custo, e só em reanálise da mesma planilha.
* **Qualidade:** o sentimento ficou idêntico ao baseline em todas as execuções concorrentes. O tema variou em 95,0% de concordância, contra 96,5% quando o cenário *antigo* é comparado com ele mesmo: diferença dentro do ruído natural do LLM, com n = 5. Isto mede **consistência**, não **correção** (não há rótulos humanos).
* Mais chamadas simultâneas aumentam o risco de limite de taxa (429); **não foi testado sob carga de vários usuários**.
* O disco do Render gratuito é efêmero: o cache some a cada deploy, então em produção ele ajuda menos do que no teste.
* Uma execução fria isolada levou 17,5 s e **não identifiquei a causa**; está registrada, não escondida.

Relatório completo (tabelas, limitações, defeito do coletor, como reproduzir): [`docs/otimizacao/otimizacao-concorrencia-e-cache.md`](docs/otimizacao/otimizacao-concorrencia-e-cache.md). Dados brutos em [`docs/benchmarks/`](docs/benchmarks/).

## Troubleshooting

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| App em produção responde **401 / "chave recusada"** depois de trocar a chave | No Render, *Save changes* só grava o valor; a instância continua com a chave antiga até um novo deploy | Usar **Save, rebuild, and deploy** e confirmar com o botão **"Testar conexão com o provedor"** na barra lateral. **Só revogue a chave antiga depois** |
| O script de benchmark ou o app local falha com `AuthenticationError` | O `.env` ainda tem o placeholder `sk-...` ou uma chave copiada incompleta | Gerar uma chave nova, colar inteira (sem aspas) na linha `OPENAI_API_KEY=` do `.env` |
| `.venv\Scripts\python.exe` "não é reconhecido" | O terminal está na pasta de cima | `cd ai-factory-feedbackloop` antes de rodar |
| Dashboard mostra **"sem dados"** ou 0 | Nenhuma análise na janela de tempo; seletor de `ambiente` errado; ou o serviço dormiu | Rodar uma análise no app, ajustar a janela e o `ambiente`. A **primeira análise após cada reinício** é aquecimento e não entra nos percentis |
| O alerta disparou e o **e-mail não chegou** | Caiu no spam do Gmail | Procurar em Spam e marcar "não é spam"; o simulado documenta esse caso |
| Uma resposta aparece como **"Não classificado"** sem erro do provedor | A trava final achou dado pessoal reconhecível que a sanitização não mascarou e **bloqueou o envio daquela resposta** (a métrica `feedbackloop_pii_bloqueios_total` conta isso) | Comportamento intencional (fail-closed): só aquela resposta é afetada. Remova o dado pessoal do texto e reanalise |
| Muitas respostas em **"Não classificado"** | Falha do provedor, JSON inválido do modelo ou bloqueio da trava de PII | Ver o alerta `FL-ERRO-LLM` e o [runbook](docs/observabilidade/runbook.md); reduzir "chamadas em paralelo" se houver limite de taxa |
| Cache sempre vazio em produção | O disco do plano gratuito é efêmero (deploy e reinício zeram) | Esperado. Ver as limitações em [Otimização](#otimização-medida-chamadas-em-paralelo-e-cache) |
| Primeiro acesso demora cerca de 1 minuto | O Render gratuito dorme sem uso | Aguardar; não é falha |
| `httpx` / `proxies` na subida (herdado da Etapa 1) | Incompatibilidade do SDK da OpenAI com versões novas do `httpx` | O `httpx` está fixado em `requirements.in` com teste de regressão |

## Testes e qualidade

* **95 testes offline** (`pytest -q`), entre eles: o trio sagrado, nenhum prompt enviado ao LLM contém PII, nenhum span ou log contém dado pessoal, o cenário de retenção apaga só o que passou do prazo, a hierarquia dos spans mesmo com threads, e o relatório de otimização bate com os dados brutos.
* **Smoke test de deploy** (`scripts/smoke_test_deploy.py`): HTTP GET em `/_stcore/health` da URL pública depois do deploy.
* **Avaliação da sanitização:** `python scripts/avaliar_pii.py` (conjunto sintético escrito antes das regras; mede recall e preservação por categoria).

## Deploy e CI/CD

Pipeline em [`.github/workflows/ci-cd.yml`](.github/workflows/ci-cd.yml), com três jobs (e uma execução agendada toda segunda-feira, 09:00 em Brasília, que reaudita dependências e segredos):

1. **`test`** (toda branch e PR para `main`): `pytest -q` e `gitleaks` no histórico completo.
2. **`auditoria-dependencias`**: `pip-audit` nas versões travadas.
3. **`deploy`** (só em push para `main` ou `develop`, e só se `test` passar): dispara o deploy no Render via *deploy hook*, aguarda o serviço subir e roda o smoke test contra a URL pública.

Hospedagem no [Render](https://render.com) ([ADR-002](docs/adr/0002-plataforma-de-deploy.md)), configurada em [`render.yaml`](render.yaml): dois Web Services com `autoDeploy: false`, para que só vá ao ar o que passou no CI. Cada push em `develop` reinicia o dev (cerca de 3 a 4 minutos), o que zera cache e aquecimento.

### Configuração manual (uma vez)

| Onde | O quê |
|---|---|
| GitHub → Settings → Environments | `development` e `production`, cada um com o secret `RENDER_DEPLOY_HOOK` e a variável `APP_URL` do serviço correspondente |
| Render, em cada serviço | `OPENAI_API_KEY` (uma chave diferente por serviço), `GRAFANA_INSTANCE_ID`, `GRAFANA_TOKEN` (um token por serviço), `OTEL_EXPORTER_OTLP_ENDPOINT`, `LLM_PRECO_ENTRADA_USD_POR_MTOK` e `LLM_PRECO_SAIDA_USD_POR_MTOK` |

## Ambientes

| | Desenvolvimento | Produção |
|---|---|---|
| Branch | `develop` | `main` |
| Serviço no Render | `feedbackloop-dev` | `feedbackloop-prod` |
| `OPENAI_API_KEY` e `GRAFANA_TOKEN` | Próprios, no serviço `feedbackloop-dev` | Próprios, no serviço `feedbackloop-prod` |
| Rótulo `ambiente` na telemetria | `dev` | `prod` |
| Quem aciona o deploy | Push em `develop` (GitHub Actions) | Push em `main` (GitHub Actions) |

## Limitações conhecidas e dívida técnica

* **Sanitização de PII não é perfeita** (87,5% no conjunto medido); identificação indireta não é coberta. O texto mascarado segue sendo tratado como dado pessoal.
* **Fragmentação de temas alta** (64% a 67%, meta ≤ 35%): sem taxonomia fixa. Candidato a próximo experimento, junto com *batch prompting*.
* **Qualidade medida só como consistência**, sem rótulos humanos.
* **Sem persistência do resultado** da análise e sem limite de tamanho de entrada.
* Região do serviço no Render a confirmar e pendências formais de LGPD (P-1 a P-6).
* Detalhe, com risco priorizado e status: [`docs/auditoria-prototipo.md`](docs/auditoria-prototipo.md).

## Versionamento

Conventional commits (`feat:`, `fix:`, `docs:` etc.). Releases seguem [SemVer](https://semver.org/lang/pt-BR/) e ficam em [`CHANGELOG.md`](CHANGELOG.md) e nas [GitHub Releases](https://github.com/gabrdias/ai-factory-feedbackloop/releases).

## Origem do projeto

Este projeto nasceu como protótipo de Rafael Crispim, Data Analyst da FeedbackLoop Tecnologia (empresa fictícia, material didático), que demonstrou a ideia a dois clientes-piloto e depois saiu da empresa. Notas técnicas originais dele seguem preservadas em [`docs/notas-rafael.md`](docs/notas-rafael.md) por transparência e contexto histórico.

## Licença

[MIT](LICENSE)
