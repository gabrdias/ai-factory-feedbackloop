# Matriz de Decisão de Stack — Escolha do Protótipo

**Data:** 2026-09-21

Este documento formaliza a escolha do protótipo **FeedbackLoop** entre os oito disponíveis na Etapa 1. Os critérios e pesos abaixo foram definidos **antes** de eu atribuir qualquer nota às opções — só depois de fechar os pesos é que li os oito READMEs/briefings com atenção e pontuei cada um. Isso evita que a matriz vire um espelho de uma preferência que eu já tinha.

## 1. Critérios e pesos (definidos antes das notas)

| # | Critério | Peso | Por que esse peso |
|---|---|---|---|
| C1 | **Viabilidade de deploy público em ~6 semanas** | 25% | É o entregável mais concreto e mensurável da Etapa 1 (URL pública + CI/CD funcionando). Um protótipo que exige infraestrutura pesada para simplesmente "subir" consome o tempo que deveria ir para hardening. |
| C2 | **Risco regulatório/ético embutido no domínio** | 20% | Alguns domínios (saúde, jurídico, seleção de currículos) carregam risco alto mesmo com poucas linhas de código erradas. Prefiro um risco que eu consiga mitigar dentro do prazo, não um que exija parecer jurídico para operar com segurança mínima. |
| C3 | **Maturidade do código herdado** | 20% | Dívida técnica *documentada de propósito* (o exercício do enunciado) é diferente de dívida *estrutural* (arquitetura confusa, sem testes, sem separação de camadas). A segunda consome tempo que não gera aprendizado do que a etapa quer ensinar. |
| C4 | **Amplitude de aprendizado técnico coberto** | 15% | Quero uma stack em que eu pratique o ciclo completo pedido pelo enunciado — testes, pipeline, deploy, CI/CD, versionamento — não só uma fatia dele. |
| C5 | **Independência de plataformas de terceiros fora do meu controle** | 10% | Projetos low-code (n8n/Make) dependem de contas externas, cotas e uma interface visual mais difícil de versionar em Git e revisar em PR. Isso não os desqualifica, mas pesa contra em um projeto solo com prazo curto. |
| C6 | **Clareza do valor de negócio para a demonstração em vídeo** | 10% | O vídeo de 3-5 min precisa mostrar valor de forma direta; domínios muito sensíveis (saúde, jurídico) são mais difíceis de demonstrar publicamente sem parecer negligente com dado real. |

Notas de 1 (fraco) a 5 (forte) por critério; pontuação final = média ponderada pelos pesos acima.

## 2. Avaliação das oito opções

| Projeto | Stack | C1 (25%) | C2 (20%) | C3 (20%) | C4 (15%) | C5 (10%) | C6 (10%) | **Nota final** |
|---|---|---|---|---|---|---|---|---|
| iLog | n8n + LLM + Slack | 3 | 4 | 3 | 3 | 2 | 4 | 3,20 |
| SaúdeJá | Jupyter + LightGBM | 2 | 2 | 2 | 3 | 5 | 3 | 2,55 |
| CopyForge | CrewAI + Streamlit | 4 | 3 | 2 | 3 | 5 | 4 | 3,35 |
| TalentoBR | FastAPI + Streamlit + LLM | 3 | 2 | 2 | 5 | 5 | 3 | 3,10 |
| VendeMais | Make.com (espelho n8n) | 4 | 4 | 3 | 1 | 1 | 4 | 3,05 |
| JurisFlow | n8n + LLM + Slack | 3 | 1 | 1 | 3 | 2 | 2 | 2,00 |
| VozDoCliente | Make.com (espelho n8n) | 4 | 3 | 2 | 1 | 1 | 4 | 2,65 |
| **FeedbackLoop** | **Streamlit + LLM** | **5** | **3** | **5** | **5** | **5** | **4** | **4,50** |

## 3. Justificativa das notas mais decisivas

- **FeedbackLoop em C1 (5):** app Python de container único, sem dependência de webhook externo nem de plataforma visual — Streamlit é literalmente feito para publicar rápido.
- **FeedbackLoop em C3 (5):** é o único, junto com TalentoBR, com testes offline reais já cobrindo lógica de negócio; mas ao contrário do TalentoBR, não carrega viés discriminatório documentado como dívida não mitigada.
- **JurisFlow no fundo da lista:** combina o pior de C2 e C3 ao mesmo tempo — chave de API commitada no JSON do workflow **e** dado coberto por sigilo profissional. É o único caso em que a dívida técnica cruza para incidente de segurança real, não hipotético.
- **VendeMais e VozDoCliente penalizados em C4/C5:** o enunciado é claro que, nesses projetos, "você é RevOps, não programa" — o que é uma ótima experiência de produto, mas entrega menos da prática de engenharia (testes, pipeline, CI) que o restante da disciplina exige.
- **SaúdeJá penalizado em C1/C2/C3:** dado de saúde é categoria especial da LGPD por definição legal (não por escolha de produto), e o artefato herdado é um notebook, não uma aplicação — o trabalho de estruturação antes mesmo de pensar em deploy é maior que nos demais.

## 4. Decisão

**FeedbackLoop** vence com folga (4,50 vs. 3,35 do segundo colocado, CopyForge), e não apenas no critério de facilidade — vence também em maturidade do código herdado e amplitude de aprendizado, que eram os critérios de maior peso combinado (45%). A decisão formal, com alternativas descartadas e consequências, está registrada em [ADR-001](adr/0001-escolha-do-prototipo-e-stack.md).
