# C4 — Nível 2: Diagrama de Contêineres

Abre o sistema FeedbackLoop (a caixa azul do Nível 1). Continua sendo um monólito de um único processo; a Etapa 2 acrescentou **componentes dentro do processo** e **um armazenamento local** (o cache). *Atualizado na v1.0.*

```mermaid
flowchart TD
    Analista["👤 Analista de RH<br/><i>Pessoa</i>"]

    subgraph Boundary["Fronteira do sistema: FeedbackLoop — Survey Insights (Web Service no Render)"]
        WebApp["🖥️ Web App<br/><i>Contêiner: Python 3.12 + Streamlit</i><br/>app.py: UI, prévia de privacidade, controles"]
        Pipeline["⚙️ Pipeline<br/><i>feedbackloop/pipeline.py</i><br/>classifica em paralelo (8 threads),<br/>agrega e gera o resumo"]
        PII["🛡️ Sanitização de PII<br/><i>feedbackloop/pii.py</i><br/>mascara antes de qualquer envio;<br/>trava final (fail-closed)"]
        LLM["🔌 Cliente do LLM<br/><i>feedbackloop/llm.py</i><br/>timeout, retry, custo e erros por chamada"]
        Obs["📡 Observabilidade<br/><i>feedbackloop/observabilidade.py</i><br/>spans, métricas e log JSON, sem dado pessoal"]
        Cache[("🗄️ Cache de classificações<br/><i>SQLite em disco efêmero</i><br/>hash do texto mascarado → tema, sentimento<br/>TTL 30 dias, purga horária")]
        CSV[("📄 Dados de exemplo<br/><i>CSV estático</i><br/>36 respostas sintéticas")]
    end

    OpenAI["🤖 OpenAI API<br/><i>Sistema Externo (EUA)</i>"]
    Grafana["📈 Grafana Cloud<br/><i>Sistema Externo (São Paulo)</i><br/>Mimir, Tempo, dashboard, alertas"]

    Analista -- "Navegador [HTTPS]" --> WebApp
    WebApp -- "Lê (fonte 'dados de exemplo')" --> CSV
    WebApp --> Pipeline
    Pipeline --> PII
    Pipeline -- "consulta antes de chamar" --> Cache
    Pipeline --> LLM
    LLM -- "texto MASCARADO<br/>[HTTPS / REST]" --> OpenAI
    Pipeline -. "eventos" .-> Obs
    LLM -. "eventos" .-> Obs
    Obs -- "traces e métricas<br/>[OTLP / HTTPS]" --> Grafana

    style WebApp fill:#1168bd,color:#ffffff,stroke:#0b4884
    style Pipeline fill:#1168bd,color:#ffffff,stroke:#0b4884
    style PII fill:#1168bd,color:#ffffff,stroke:#0b4884
    style LLM fill:#1168bd,color:#ffffff,stroke:#0b4884
    style Obs fill:#1168bd,color:#ffffff,stroke:#0b4884
    style OpenAI fill:#999999,color:#ffffff,stroke:#6b6b6b
    style Grafana fill:#999999,color:#ffffff,stroke:#6b6b6b
    style Analista fill:#08427b,color:#ffffff,stroke:#052c52
    style Cache fill:#438dd5,color:#ffffff,stroke:#2c6aa8
    style CSV fill:#438dd5,color:#ffffff,stroke:#2c6aa8
```

> Em rigor de C4, Web App, Pipeline, PII, Cliente do LLM e Observabilidade são **componentes** (nível 3) do mesmo contêiner (um processo Python). Estão desenhados aqui, separados, porque é onde as fronteiras de **dados** passam: o que sai do processo e o que é gravado em disco.

## Elementos

| Elemento | Tecnologia | Responsabilidade e limite de dados |
|---|---|---|
| Web App | Python 3.12, Streamlit, `pandas` | Único deployable. Hospedado no Render ([ADR-002](../adr/0002-plataforma-de-deploy.md)). **Recebe o texto original** das respostas e o mantém só em memória, durante a sessão. |
| Sanitização de PII | Regras + léxico + pistas de contexto ([ADR-004](../adr/0004-sanitizacao-de-pii-por-regras.md)) | Troca nomes, e-mails, telefones, CPF etc. por marcadores (`[PESSOA_1]`). A **trava final** impede qualquer chamada se restar PII reconhecível. Recall medido: 100% nas categorias cobertas, 87,5% no total. |
| Pipeline | Python, `ThreadPoolExecutor` | Classificação em paralelo ([ADR-005](../adr/0005-otimizacao-concorrencia-e-cache.md)); o resumo recebe só agregados. |
| Cliente do LLM | SDK OpenAI 1.50 | Cada chamada gera span e métricas (tokens, custo, erro). A chave vem de variável de ambiente, uma por ambiente. |
| Observabilidade | OpenTelemetry SDK ([ADR-003](../adr/0003-observabilidade-opentelemetry-grafana-cloud.md)) | Exporta telemetria; **nunca** texto de resposta, nome ou token. |
| Cache de classificações | SQLite, arquivo local | Guarda `sha256(versão do prompt, modelo, texto mascarado)` → `{tema, sentimento}`. **Não guarda o texto.** TTL de 30 dias (teto 90), purga na subida e a cada hora, botão "Excluir cache agora" ([política de retenção](../lgpd/politica-de-retencao-e-exclusao.md)). O disco do Render gratuito é efêmero: o cache some a cada deploy. |
| Dados de exemplo | CSV versionado em Git | Estático e sintético. Não guarda resultado de ninguém. |

## Fronteiras de dados (o que atravessa cada seta)

| Seta | Conteúdo | Tem dado pessoal? |
|---|---|---|
| Analista → Web App | Texto original das respostas | **Sim** (pode conter nomes de terceiros) |
| Pipeline → OpenAI | Texto **mascarado** + instruções | Residual possível (lacunas medidas) |
| Web App → Grafana | Contagens, durações, tokens, custo, rótulos | Não (testado) |
| Pipeline → Cache | Hash + tema + sentimento | Não guarda texto; tratado como dado derivado |

## Por que continua sendo um monólito

Não existe API separada, banco de dados de aplicação, Redis nem fila. O cache em SQLite é um **arquivo local do mesmo processo**, escolhido para não criar um novo serviço, uma nova conta e uma nova superfície de LGPD (comparação no [ADR-005](../adr/0005-otimizacao-concorrencia-e-cache.md)). Se houver persistência de análises, este diagrama ganha um banco e uma nova ADR, não antes disso.
