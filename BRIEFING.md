# Briefing Oficial — FeedbackLoop

**Empresa:** FeedbackLoop Tecnologia Ltda. (fictícia)
**Missão:** Transformar o que o time sente em decisão de gestão.
**Tamanho:** ~80 colaboradores, startup de people analytics em estágio Series A,
sede em Florianópolis (SC), clientes em todo o Brasil.
**Área:** Produto — célula "Pulse" (analytics de pesquisas de clima e engajamento)

---

## Sua nova função

Olá, e bem-vinda(o) à FeedbackLoop!

Eu sou a **Beatriz Furtado**, a Bia, Head de People Analytics e responsável pela
célula Pulse. Você está assumindo a vaga de **AI Engineer Pleno** no time que
constrói os recursos de IA que entram no nosso produto.

A vaga é nova. Antes de você, quem tocava a parte de IA sozinho era o **Rafael
Crispim**, Data Analyst que virou meio que "o cara de IA" sem nunca ter sido
contratado pra isso. O Rafael saiu há duas semanas — foi pra uma outra startup —
e deixou um protótipo funcional, mas órfão. É aí que você entra.

---

## Contexto do problema

Nosso produto já analisa muito bem as perguntas **fechadas** de pesquisa de
clima (notas de 0 a 10, múltipla escolha). O problema é o **texto livre**: as
perguntas abertas, onde a pessoa escreve o que realmente pensa.

Hoje os nossos clientes (áreas de RH de outras empresas) recebem **centenas a
milhares** de respostas abertas por pesquisa e não têm como ler tudo. Um analista
de RH passa **dias** lendo comentário por comentário, e mesmo assim a leitura é
subjetiva e não escala. É o nosso maior pedido de feature e o maior gargalo de
percepção de valor do produto.

O Rafael atacou isso com um protótipo que usa LLM pra **agrupar as respostas por
tema, classificar o sentimento e gerar um resumo executivo** com ações
recomendadas. Ele demonstrou pra dois clientes-piloto em janeiro e a reação foi
ótima — mas nunca saiu da máquina dele.

---

## Estado atual do protótipo

- Stack: Python (Streamlit + um modelo GPT pequeno da OpenAI)
- Roda localmente, com `streamlit run app.py`
- Lógica isolada no pacote `feedbackloop/`, com interface de LLM mockável
- Tem testes offline (pytest), mas só da lógica — nada que avalie a qualidade do
  resumo gerado
- Sem persistência, sem cache, sem deploy, sem CI, sem observabilidade
- **LGPD não foi endereçada**: respostas com nomes de pessoas vão cruas pro LLM
- Documentação esparsa em `docs/notas-rafael.md` e no README

Considere isto **dívida técnica herdada**. Não jogue fora — **refatore.**

---

## Expectativas em 12 semanas

1. **Semana 3 — Auditoria e baseline:** rodar localmente, mapear o que existe,
   documentar a arquitetura real e propor um plano de evolução. Definir a
   taxonomia de temas (hoje o modelo inventa tema a cada resposta).
2. **Semana 6 — Hardening + LGPD:** anonimização de PII antes do prompt, logging
   e tratamento de erro, cache pra não reprocessar a mesma planilha, e um
   conjunto de validação pra medir qualidade do resumo (não dá pra evoluir o que
   não se mede).
3. **Semana 9 — Deploy controlado:** ambiente de staging acessível ao time de
   Produto e a 1 cliente-piloto, persistência das análises, monitoramento básico
   de custo e latência, conformidade LGPD documentada.
4. **Semana 12 — Piloto em produção:** liberar a análise de respostas abertas pra
   um grupo selecionado de clientes, com acompanhamento de custo por pesquisa e
   coleta de feedback de qualidade.

---

## Restrições

- **Orçamento de infra/IA:** **US$ 120/mês** na fase de piloto (inclui LLM,
  eventuais embeddings e hosting). É startup, o caixa é curto — otimize custo
  desde já (cache não é luxo, é sobrevivência).
- **Provedores permitidos:** OpenAI, Anthropic, Google (modelos via API).
  Hospedagem em Streamlit Cloud, Hugging Face Spaces, Render ou Vercel.
- **LGPD:** respostas de pesquisa são dados de funcionários dos nossos clientes —
  podem conter nomes e queixas identificáveis. **Nenhum dado identificável pode
  entrar em prompt sem anonimização.** Defina finalidade, base legal e prazo de
  retenção (máx. 90 dias para logs). Quando em dúvida, fala comigo e com o
  jurídico antes.
- **Idioma:** PT-BR no produto. Documentação técnica pode ser bilíngue.

Conte com a gente. Qualquer dúvida, me chama.

— Beatriz Furtado (Bia)
Head de People Analytics, FeedbackLoop
