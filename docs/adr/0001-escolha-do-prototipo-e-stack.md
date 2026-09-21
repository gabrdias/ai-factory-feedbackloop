# ADR-001: Adotar o protótipo FeedbackLoop (Python + Streamlit + OpenAI) e evoluí-lo, em vez de reescrever ou trocar de stack

* Status: aceita
* Data: 2026-09-21

## Contexto e problema

A disciplina exige adotar um entre oito protótipos herdados, cada um com uma stack e um domínio de negócio diferentes, e evoluí-lo — nunca reescrever do zero. Antes de colocar a mão no código, é preciso decidir formalmente qual protótipo/stack adotar, com critérios definidos antes de olhar as opções (ver [matriz de decisão](../decisao-stack.md)), para que a escolha não seja apenas um espelho de preferência pessoal.

## Motivadores da decisão

* Viabilidade de publicar uma URL pública funcional dentro do prazo da Etapa 1 (entrega semana 6).
* Risco regulatório/ético do domínio de negócio, que precisa ser administrável por uma pessoa só no prazo dado.
* Maturidade do código herdado: quanto mais dívida *estrutural* (não a dívida plantada de propósito), mais tempo é gasto resgatando em vez de aprendendo o que a etapa quer ensinar.
* Amplitude do ciclo de engenharia coberto (testes, pipeline, deploy, CI/CD, versionamento).
* Independência de plataformas visuais de terceiros (n8n/Make), que são mais difíceis de versionar e revisar em Git.

## Opções consideradas

* iLog — n8n + LLM + Slack
* SaúdeJá — Jupyter + LightGBM
* CopyForge — CrewAI + Streamlit
* TalentoBR — FastAPI + Streamlit + LLM
* VendeMais — Make.com (espelho em n8n)
* JurisFlow — n8n + LLM + Slack
* VozDoCliente — Make.com (espelho em n8n)
* **FeedbackLoop — Python + Streamlit + OpenAI** (escolhida)

## Resultado da decisão

Opção escolhida: **"FeedbackLoop — Python + Streamlit + OpenAI"**, porque obteve a maior nota ponderada na matriz de decisão (4,50 de 5, contra 3,35 do segundo colocado), vencendo com folga justamente nos critérios de maior peso combinado: viabilidade de deploy (25%) e maturidade do código herdado (20%). A regra do jogo da disciplina — evoluir, não reescrever — se aplica diretamente: o código já separa UI de lógica de negócio, já tem testes offline e já documenta sua própria dívida técnica, o que permite focar o esforço desta etapa exatamente no que ela avalia (deploy, CI/CD, versionamento), em vez de primeiro precisar organizar um código confuso.

### Consequências positivas

* Deploy simples: é um único processo Python (Streamlit), sem dependência de webhook externo nem de editor visual de workflow.
* Base de testes já existente reduz o risco de regressão ao mexer no pipeline.
* Dívida técnica já está documentada pelo autor anterior (`README.md`, `docs/notas-rafael.md`), o que acelera a auditoria.
* Dado de exemplo já é sintético e documentado como tal, reduzindo o risco de expor dado real de RH durante a demonstração pública.

### Consequências negativas / trade-offs aceitos

* A lacuna de LGPD (nomes de pessoas sem anonimização antes do prompt) é real e fica **registrada, mas não resolvida nesta etapa** — a mitigação técnica está planejada para a Semana 6 do roteiro do `BRIEFING.md`, não para a Etapa 1. Isso é uma decisão consciente de escopo, não um esquecimento.
* Streamlit não separa nativamente "backend" de "frontend": qualquer evolução futura para múltiplos clientes simultâneos ou autenticação por cliente vai exigir reconsiderar a arquitetura (registrado como risco conhecido para uma ADR futura).
* O modelo de LLM está hardcoded (`gpt-5.4-mini`, OpenAI). Trocar de provedor (por exemplo, para um modelo Claude Haiku da Anthropic, já esboçado em comentário no código) segue disponível como alternativa aprovada pelo orçamento, mas não é decidida nesta ADR.

## Prós e contras das opções descartadas

### JurisFlow — n8n + LLM + Slack

* Bom, porque: domínio jurídico tem alto valor de produto percebido.
* Ruim, porque: combina o pior de dois critérios ao mesmo tempo — chave de API commitada no JSON do workflow (risco de segurança real, não hipotético) e dado coberto por sigilo profissional (risco regulatório alto). Nota final: 2,00, a mais baixa das oito.

### SaúdeJá — Jupyter + LightGBM

* Bom, porque: aprendizado interessante de ML clássico (classificação de risco).
* Ruim, porque: dado de saúde é categoria especial de dado sensível pela LGPD por definição legal, e o artefato herdado é um notebook (sem estrutura de aplicação), aumentando o trabalho antes mesmo de cogitar deploy. Nota final: 2,55.

### CopyForge — CrewAI + Streamlit

* Bom, porque: segundo colocado na matriz (3,35); stack multiagente é um bom aprendizado técnico.
* Ruim, porque: o protótipo já tem um agente revisor que entra em loop e ainda assim deixa passar alucinação factual — indício de dívida estrutural na orquestração dos agentes, não só falta de hardening.

### TalentoBR — FastAPI + Streamlit + LLM

* Bom, porque: maior amplitude de aprendizado técnico das oito opções (API + UI separadas).
* Ruim, porque: carrega viés documentado e **não mitigado** contra mulheres e candidatos acima de 50 anos, envolvendo diretamente o Art. 20 da LGPD (direito à revisão humana). É um risco ético que exige mitigação de produto, não só técnica, incompatível com o prazo da Etapa 1.

### VendeMais e VozDoCliente — Make.com (espelho em n8n)

* Bom, porque: fáceis de reativar (cenários já existem, só desligados/instáveis) e com valor de negócio fácil de demonstrar.
* Ruim, porque: papel é "RevOps, não programa" — baixa amplitude de prática de engenharia (testes, pipeline, CI) e alta dependência de uma plataforma visual de terceiros, mais difícil de versionar em Git e revisar via pull request.

### iLog — n8n + LLM + Slack

* Bom, porque: volume de negócio real e claro (4 mil reclamações/dia).
* Ruim, porque: workflow low-code, com webhook secret escrito no código — soma dependência de plataforma externa a um problema de segredo exposto.

## Mais informações

Matriz de decisão completa com critérios, pesos e notas: [`docs/decisao-stack.md`](../decisao-stack.md).
