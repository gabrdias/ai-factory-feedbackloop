# ADR-002: Publicar a aplicação no Render, com serviços separados de desenvolvimento e produção

* Status: aceita
* Data: 2026-09-21

## Contexto e problema

O `BRIEFING.md` aprova quatro plataformas de hospedagem para o piloto: Streamlit Community Cloud, Hugging Face Spaces, Render ou Vercel, dentro de um orçamento de US$ 120/mês (infra + LLM). A Etapa 1 exige, especificamente: uma URL pública estável que não dependa da máquina do estudante; um pipeline de CI/CD em que um push na branch principal dispare o deploy sozinho; ambientes de desenvolvimento e produção **realmente** separados, com secrets diferentes em cada um; e um rollback **testado**, com evidência de execução (print ou log) — não apenas descrito.

Este ADR decide qual dessas quatro plataformas usar e como estruturar a separação de ambientes.

## Motivadores da decisão

* Precisa produzir evidência real de rollback (print ou log de execução), não apenas documentação do processo.
* Precisa suportar dois ambientes com secrets distintos sem gambiarra (ex.: duas contas, duas branches com o mesmo secret, etc.).
* Precisa de deploy automático a partir de push no GitHub, compatível com GitHub Actions.
* Precisa rodar um processo Python de longa duração (servidor Streamlit com WebSocket), não uma função serverless efêmera.
* Precisa caber confortavelmente no orçamento de US$ 120/mês, mesmo usando a camada gratuita, já que o piloto não tem tráfego que justifique custo de infraestrutura pago ainda.

## Opções consideradas

* Streamlit Community Cloud
* Hugging Face Spaces
* Render
* Vercel

## Resultado da decisão

Opção escolhida: **Render**, com dois Web Services distintos — `feedbackloop-dev` (branch `develop`) e `feedbackloop-prod` (branch `main`) — cada um com seu próprio grupo de variáveis de ambiente (`OPENAI_API_KEY` diferente em cada um), porque é a única das quatro opções aprovadas que oferece nativamente: (1) histórico de deploys navegável na própria interface, com um botão de **rollback de um clique** para qualquer deploy anterior bem-sucedido — o que produz a evidência de execução exigida sem processo manual inventado só para a entrega; e (2) múltiplos serviços com grupos de variáveis de ambiente independentes por serviço, o que torna a separação dev/prod real (contas, URLs e secrets diferentes), em vez de um único app alternando configuração.

### Consequências positivas

* Rollback vira um clique + print da tela de histórico de deploys — evidência trivial de gerar e impossível de "encenar" sem de fato ter acontecido.
* GitHub Actions pode rodar testes e smoke tests antes de disparar o deploy (via *deploy hook* do Render), em vez de deixar o Render fazer deploy de código que não passou no CI.
* Dois serviços = dois secrets = zero risco de um ambiente vazar a chave do outro.
* Camada gratuita do Render cobre o piloto sem custo, deixando os US$ 120/mês inteiros de folga para o LLM.

### Consequências negativas / trade-offs aceitos

* A camada gratuita do Render "dorme" após um período de inatividade; o primeiro acesso depois disso pode levar dezenas de segundos para responder. Aceitável para um piloto de baixo tráfego; documentado no README como limitação conhecida, com upgrade para o plano pago (dentro do orçamento de US$ 120/mês) como próximo passo se o uso crescer.
* Render exige que o Streamlit seja iniciado com flags específicas (porta vinda de `$PORT`, endereço `0.0.0.0`) — pequeno ajuste de configuração em relação a rodar `streamlit run app.py` localmente.

## Prós e contras das opções descartadas

### Streamlit Community Cloud

* Bom, porque: é a plataforma "nativa" para apps Streamlit, com deploy por push já embutido, sem sequer precisar de GitHub Actions para essa parte.
* Ruim, porque: não tem um mecanismo de rollback de um clique na interface — "voltar" para uma versão anterior exigiria reverter o commit e dar push de novo, o que confunde o próprio histórico de versionamento em vez de ser uma operação de rollback isolada e demonstrável.

### Hugging Face Spaces

* Bom, porque: também nativo para apps desse tipo, com seu próprio versionamento de arquivos (baseado em Git) e camada gratuita generosa.
* Ruim, porque: separar dev/prod exigiria dois Spaces distintos geridos manualmente fora do fluxo padrão de CI/CD do GitHub Actions, e o rollback pela interface de "Files and versions" é menos direto de demonstrar como uma operação única e clara do que o histórico de deploys do Render.

### Vercel

* Bom, porque: excelente para CI/CD automático e ambientes de preview por branch.
* Ruim, porque: seu modelo é orientado a funções serverless e frontends estáticos/Next.js; um servidor Streamlit com conexão WebSocket de longa duração não se encaixa bem nesse modelo sem contornos que fugiriam do "evoluir, não reescrever".

## Mais informações

A configuração concreta (arquivo `render.yaml`, workflow de GitHub Actions e passo a passo de setup dos dois serviços) está descrita no README do repositório e será versionada junto com o código nesta mesma etapa.
