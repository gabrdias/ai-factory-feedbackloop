# Auditoria do Protótipo — FeedbackLoop

**Data:** 2026-09-21
**Autor:** Gabriel Dias (AI Engineer Pleno, assumindo a célula Pulse)
**Escopo:** estado do repositório `ai-factory-feedbackloop` no commit herdado de Rafael Crispim, antes de qualquer alteração feita nesta etapa.

## 1. O que existe hoje (baseline)

O protótipo é um app Streamlit de página única (`app.py`) que:

1. Recebe respostas abertas de pesquisa de clima (texto colado, CSV ou dados de exemplo).
2. Classifica cada resposta em tema + sentimento via LLM (`feedbackloop/llm.py` + `feedbackloop/pipeline.py`).
3. Agrega os resultados e gera um resumo executivo com ações recomendadas.

Pontos positivos que já reduzem o trabalho desta etapa:

- **Separação limpa entre UI e lógica.** `app.py` só cuida de Streamlit; toda a regra de negócio está em `feedbackloop/pipeline.py`.
- **Cliente LLM isolado atrás de uma interface mínima** (`ClienteLLM.completar`), o que já torna o pipeline testável sem chamar a API real.
- **Testes offline existentes** (`tests/test_pipeline.py`), cobrindo as funções puras de parsing/agregação e o fluxo ponta a ponta com um cliente mockado.
- **Dívida técnica já documentada pelo autor anterior** em três lugares (`README.md`, `docs/notas-rafael.md`, comentários `# TODO` / `# planted` no código), o que facilita auditar sem arqueologia.
- **Dados de exemplo sintéticos, com aviso explícito** (`data/AVISO-DADOS-SINTETICOS.md`) sobre por que há nomes fictícios no meio das respostas.
- `.env.example` e `.gitignore` já existem e cobrem os casos básicos (não versionam `.env` nem segredos).

## 2. Lacunas identificadas

### 2.1 Segurança e segredos

- `feedbackloop/llm.py:35` lê `OPENAI_API_KEY` direto do ambiente, sem fallback — comportamento correto (falha explícita), mas sem mensagem amigável fora do `app.py`.
- Não há rotação de segredo documentada. O `.env.example` já avisa "peça pro Rafael... ah, ele saiu": a chave usada localmente por Rafael precisa ser tratada como comprometida e rotacionada antes de qualquer deploy.
- Uma verificação manual do histórico (`git log -p --all`) não encontrou chave real commitada, mas isso ainda não substitui uma varredura formal com `gitleaks` antes de tornar o repositório público — item obrigatório do enunciado.

### 2.2 LGPD / Privacidade (risco mais alto do protótipo)

- `feedbackloop/pipeline.py:154-165` (`classificar_resposta`) envia a resposta **crua** para o prompt do LLM, incluindo qualquer nome de pessoa presente no texto. Não há NER, regex ou qualquer anonimização antes do envio.
- `app.py:39-44` mostra um aviso visual, mas **não bloqueante** — o usuário pode ignorar e enviar dados reais mesmo assim.
- O `BRIEFING.md` exige que "nenhum dado identificável pode entrar em prompt sem anonimização" e define retenção máxima de 90 dias para logs — nenhum dos dois está implementado no código.
- Não há definição de base legal/finalidade registrada em nenhum artefato técnico (só na prosa do briefing).

### 2.3 Qualidade e testes

- Os testes cobrem bem parsing, agregação e o fluxo com mock, mas **não avaliam a qualidade do conteúdo gerado pelo modelo** — não existe conjunto de validação nem rubrica de qualidade do resumo.
- Não há taxonomia fixa de temas: o modelo pode inventar um tema novo por resposta, pulverizando a agregação (relatado pelo próprio Rafael em `docs/notas-rafael.md`).
- Falha de parsing do JSON do LLM cai silenciosamente em `"Não classificado"` / `"neutro"` (`pipeline.py:63-81`) — protege o pipeline de quebrar, mas mascara problemas de qualidade sem alertar ninguém.

### 2.4 Observabilidade

- Nenhum log estruturado, nenhuma métrica de custo, latência ou taxa de erro.
- Nenhum rastro de quantas chamadas de LLM cada análise fez (o próprio código comenta o custo estimado, mas isso não é medido em tempo de execução).

### 2.5 Persistência e custo

- Nenhuma persistência: fechar a aba perde o resultado (`app.py:101-105`).
- Nenhum cache: `analisar()` faz uma chamada de LLM por resposta + uma do resumo, toda vez que o botão é clicado — reanalisar a mesma planilha paga duas vezes (`pipeline.py:193-201`, confirmado nas notas de Rafael: ~US$0,40 em 15 execuções de 36 respostas).
- Nenhum limite de tamanho de entrada: uma planilha grande pode gerar custo inesperado sem qualquer aviso prévio.

### 2.6 Deploy e operação

- Roda só localmente (`streamlit run app.py`). Não há Dockerfile, workflow de CI, nem configuração de nenhuma plataforma de hospedagem.
- Nenhuma separação entre ambiente de desenvolvimento e produção.
- `CHANGELOG.md` já existe e está atualizado até v0.2, mas não há tags Git nem GitHub Release publicado.

### 2.7 Robustez / tratamento de erro

- `app.py:16` hardcoda o nome da coluna esperada no CSV (`"resposta"`). Uma planilha do RH com coluna `"comentario"`, por exemplo, quebra (já reconhecido pelo autor anterior nas suas notas).
- Nenhum tratamento específico para erro de rede, timeout ou rate limit da API da OpenAI — uma falha da API sobe sem mensagem clara para quem está usando o app.
- `feedbackloop/llm.py:19` tem o modelo hardcoded (`MODELO_PADRAO`); a variável `OPENAI_MODEL` já existe comentada no `.env.example`, mas ainda não tem efeito nenhum no código.

## 3. Risco priorizado (impacto × urgência para esta etapa)

| Lacuna | Impacto se ignorada | Urgência na Etapa 1 |
|---|---|---|
| LGPD — nomes crus no prompt | Alto (dado sensível de terceiros, exposição a provedor externo) | Documentar agora; **mitigação técnica fica para a Semana 6**, conforme roadmap do briefing |
| Segredo local possivelmente exposto | Alto (chave comprometida = custo/abuso) | Rotacionar **antes** de qualquer deploy |
| Sem CI/CD, sem deploy, sem ambientes separados | Alto (é o núcleo do que a Etapa 1 avalia) | **Resolver agora** |
| Sem cache / sem persistência | Médio (custo cresce com uso, mas dentro do orçamento no piloto) | Registrar como dívida conhecida; resolver na Semana 6 |
| Taxonomia de tema instável / sem avaliação de qualidade | Médio (afeta valor percebido, não afeta operação) | Registrar; resolver na Semana 6 |
| Coluna de CSV hardcoded | Baixo-médio (quebra previsível, mensagem de erro já existe) | Backlog |

## 4. Fora do escopo desta etapa

Por decisão consciente (e alinhada ao roteiro de 12 semanas do `BRIEFING.md`), esta etapa **não** implementa: anonimização de PII, cache, persistência de resultados, taxonomia fixa de temas nem avaliação automatizada de qualidade do resumo. O foco da Etapa 1 é sair de "funciona no meu notebook" para "está publicado, versionado e eu sei operar" — a dívida de produto (itens 2.2 a 2.5, exceto segredo/rotação) é tratada explicitamente como backlog documentado, não como silêncio.

## 5. Situação após a Etapa 2 (atualizado em 2026-10-19)

As seções 1 a 4 descrevem o protótipo **como foi herdado** e foram mantidas como registro. Esta tabela diz o que mudou, com a evidência. "Parcial" e "não tratado" aparecem de propósito.

| Lacuna (seção) | Situação | Evidência |
|---|---|---|
| 2.1 Segredo local possivelmente exposto, sem rotação documentada | **Tratado** | Rotação executada em 19/10/2026 nos três ambientes, com um incidente real e corrigido: [procedimento](seguranca/rotacao-de-credenciais.md), [registro](seguranca/registro-de-rotacoes.md), [post-mortem](post-mortem-2026-10-19-rotacao-de-chave.md); gitleaks e pip-audit em todo push |
| 2.1 Mensagem amigável quando falta a chave | **Tratado** | Tela de erro no app e botão "Testar conexão com o provedor" |
| 2.2 Nomes crus no prompt (LGPD) | **Parcial** | Sanitização antes de toda chamada, com trava final: [ADR-004](adr/0004-sanitizacao-de-pii-por-regras.md). Medido: recall **100%** nas categorias cobertas e **87,5%** no conjunto total; nomes raros sem pista e nomes em minúsculas **passam** ([avaliação](lgpd/avaliacao-sanitizacao-pii.md)). A saída continua tratada como dado pessoal |
| 2.2 Base legal, finalidade e retenção | **Tratado, com pendências formais** | [Mapa de dados pessoais](lgpd/mapa-de-dados-pessoais.md), [política de retenção](lgpd/politica-de-retencao-e-exclusao.md), [transferência internacional](lgpd/transferencia-internacional.md). Pendências que exigem validação jurídica estão listadas lá (P-1 a P-6, T-1 a T-3) |
| 2.3 Falha de parsing sem alerta | **Tratado** | Métrica de qualidade "% não classificadas" no dashboard; falha de uma resposta vira "Não classificado" com aviso na tela |
| 2.3 Taxonomia fixa de temas | **Não tratado** | Medida a fragmentação: 23 a 24 temas em 36 respostas (64 a 67%); meta de produto (≤ 35%) não atingida ([métricas](observabilidade/metricas-e-alertas.md)) |
| 2.3 Avaliação de qualidade do resumo | **Parcial** | Medida a **consistência** entre execuções (sentimento 100%, tema 95%), não a **correção** contra rótulos humanos ([relatório](otimizacao/otimizacao-concorrencia-e-cache.md)) |
| 2.4 Observabilidade | **Tratado** | Traces, cinco métricas, dashboard e alerta testado ao vivo: [ADR-003](adr/0003-observabilidade-opentelemetry-grafana-cloud.md), [métricas e alertas](observabilidade/metricas-e-alertas.md) |
| 2.5 Sem cache | **Tratado** | Cache com TTL: [ADR-005](adr/0005-otimizacao-concorrencia-e-cache.md); a reanálise cai de 32 s para 2,7 s (cache quente) |
| 2.5 Sem persistência de resultados | **Não tratado** | Só o cache de classificações (sem texto) persiste; o resultado da análise continua só na sessão |
| 2.5 Sem limite de tamanho de entrada | **Não tratado** | Planilha grande ainda gera custo proporcional sem aviso prévio |
| 2.6 Sem CI/CD, ambientes, release | **Tratado na Etapa 1** | [README](../README.md#deploy-e-cicd), release v0.3.0 |
| 2.7 Coluna do CSV fixa | **Tratado** | O app aceita apelidos comuns (`comentario`, `texto`, ...) e explica o erro |
| 2.7 Erro de rede, timeout, limite de taxa | **Tratado** | Timeout e retry com backoff, mensagens por tipo de erro, degradação por resposta |
| 2.7 Modelo fixo no código | **Tratado** | `OPENAI_MODEL` tem efeito (`feedbackloop/config.py`) |
