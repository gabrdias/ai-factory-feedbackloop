# Post-mortem — 19/10/2026: prod com chave revogada após a rotação

**Serviço:** `feedbackloop-prod`
**Severidade:** baixa na prática (piloto sem usuários externos); **alta no potencial**: a funcionalidade principal ficou indisponível em produção e **nenhum alerta enxergou**.
**Natureza:** incidente **real**, descoberto pela etapa "verificar" do procedimento de rotação. Sem culpados: o procedimento estava escrito, mas faltava uma forma barata de provar o que estava em execução.

## O que aconteceu

Ao executar a rotação planejada de `OPENAI_API_KEY` ([registro R-001](seguranca/registro-de-rotacoes.md)), a chave antiga do **prod** foi revogada, mas o serviço de produção **continuou usando a chave antiga** e passou a devolver `401 Your API key has been invalidated`. Foi detectado quando o responsável pelo teste clicou em "Analisar respostas" no prod como passo de verificação, e a tela mostrou `AuthenticationError`.

## Linha do tempo

Fuso de Brasília. `≈` = informado de memória; as demais horas vêm do relógio da máquina que executou o teste ou de eventos verificáveis.

| Hora | Evento | Fonte |
|---|---|---|
| ≈ 08:47 a ≈ 08:49 | Criadas as 3 chaves novas (local, dev e prod, nessa ordem, ~1 min entre si) | informado |
| não registrado | Chave nova colada no Render e chave antiga revogada na OpenAI. O `dev` foi corrigido; no `prod` a variável foi salva **sem novo deploy**, então a instância em execução seguiu com o valor antigo | informado + inferência (o dev funcionou, o prod não) |
| 09:34:43 | Teste de verificação no prod (clique em "Analisar respostas") | relógio local |
| ≈ 09:35 | A tela mostra `AuthenticationError ... token_invalidated`. Incidente detectado | observação |
| não registrado | Responsável executa *Save, rebuild, and deploy* no prod | informado |
| 09:38:27 | Novo teste no prod: a análise **completa com sucesso** (chave nova ativa) | relógio local |

**Janela de indisponibilidade:** da revogação (depois de ≈ 08:49, hora exata não registrada) até o deploy corrigido (antes de 09:38), ou seja, no mínimo ≈ 46 minutos, durante os quais ninguém tentou usar o prod.

## Causa raiz (três fatores)

1. **Salvar a variável não aplica a variável.** No Render, *Save changes* só grava; a instância em execução continua com o valor antigo até um novo deploy.
2. **A chave antiga foi revogada antes de provar que o prod usava a nova.** O procedimento diz "verificar, só então revogar", mas não havia uma verificação rápida da instância em execução.
3. **O alerta não podia ver o prod.** O prod ainda rodava a versão da Etapa 1 (v0.3.0), sem telemetria. O alerta `FL-ERRO-LLM` cobre `dev` e `prod`, mas só enxerga ambientes que enviam métricas. Se um usuário real tivesse clicado, ninguém seria avisado.

## O que funcionou

- A etapa de **verificação** do procedimento pegou o problema em minutos, antes de qualquer usuário.
- A mensagem do provedor era clara (`token_invalidated`), e o runbook já listava `AuthenticationError` como primeiro caso.
- Como o dev tinha sido corrigido e instrumentado, a rotação "do lado certo" ficou comprovada com dados (análises de 09:09 em diante).

## O que não funcionou

- Ordem de execução diferente da escrita: revogar antes de verificar o prod.
- Nenhuma forma barata de testar a chave **da instância em execução**: o único jeito era rodar uma análise inteira (37 chamadas).
- O prod ficar sem observabilidade tornou o incidente invisível para o alerta.

## Ações

| Ação | Status |
|---|---|
| Aplicar a chave nova no prod com deploy | ✅ Feito (verificado às 09:38) |
| Botão **"Testar conexão com o provedor"** na barra lateral do app: uma chamada mínima (≈ US$ 0,00001) que prova que **aquela instância** tem chave válida | ✅ Feito (`feat: botão de teste de conexão`) |
| Procedimento de rotação passa a exigir: deploy, **clicar em Testar conexão em cada ambiente** e só depois revogar | ✅ Feito (`docs/seguranca/rotacao-de-credenciais.md`, seção 3) |
| Promover a versão com telemetria para o prod (release v1.0.0), para o alerta cobrir o prod de verdade | ✅ Feito em 2026-10-19 (commit `a6b87e2`, tag `v1.0.0`; CI/CD e smoke test passaram) |
| Repetir um simulado de alerta **também no prod** depois da promoção | ⬜ Pendente |
