# Simulado de incidente: o alerta `FL-ERRO-LLM` disparando de verdade (dev, 19/10/2026)

Objetivo: provar que o alerta **dispara de verdade**, chega a quem deve e leva a uma ação, e descobrir o que ele **não** faz bem, antes de um incidente real. Escolhi o incidente mais provável e já visto uma vez em produção ([post-mortem de 19/10](../post-mortem-2026-10-19-rotacao-de-chave.md)): **chave de API recusada pelo provedor**.

## Método

1. No Render, `feedbackloop-dev` → Environment, `OPENAI_API_KEY` trocada por um valor inválido, com *Save, rebuild, and deploy*. (Ação do responsável, às 09:42.)
2. Com o deploy no ar, uma análise com os dados sintéticos gera 36 chamadas ao provedor, todas recusadas (HTTP 401).
3. Observar: mensagem no app, estado da regra no Grafana, e-mail recebido.
4. Recuperar seguindo o [runbook](runbook.md) e a [rotação de credenciais](../seguranca/rotacao-de-credenciais.md), e confirmar com o botão "Testar conexão".

## Linha do tempo (fuso de Brasília)

| Hora | Evento | Fonte |
|---|---|---|
| 09:42 | Chave inválida colocada no dev; deploy iniciado | informado |
| 09:43:23 | O CI conclui o deploy de um commit da `develop` (concorrente ao deploy manual) | GitHub Actions |
| entre 09:43 e 09:46 | O botão "Testar conexão" ainda respondeu **"a chave deste ambiente é válida"**: a instância antiga seguia no ar enquanto a nova subia. Depois, o mesmo botão passou a mostrar **"O provedor recusou a chave de API deste ambiente"** | observação no navegador |
| **09:46:37** | **Início do incidente simulado:** análise disparada; as 36 chamadas são recusadas. O app mostra a mensagem amigável, **sem traceback** | relógio local |
| 09:47:50 | Grafana cria a instância do alerta (`ambiente=dev`, estado *Pending*) | aba *Instances* ([print](evidencias/alerta-firing-instancias.png)) |
| **09:48** | **E-mail `[FIRING:1] FeedbackLoop: provedor de IA falhando (dev, P2)`** | Gmail ([print](evidencias/alerta-emails-recebidos.png)) |
| 09:48 e depois | Regra em **Firing**, com rótulos `prioridade=P2` e `servico=feedbackloop`, taxa de falha em 100% | [print da regra](evidencias/alerta-firing-regra.png) |
| 09:51 e 09:52 | Dois e-mails extras `DatasourceNoData` (RESOLVED e FIRING): **ruído** | Gmail |
| **09:53** | E-mail `[RESOLVED]`: a regra se resolveu sozinha, **com a chave ainda quebrada** | Gmail |
| 10:01 | Recuperação iniciada: chave nova instalada no dev, deploy iniciado | informado |
| **10:06:00** | Recuperação confirmada: o botão "Testar conexão" mostra **"Provedor respondeu em 2,2 s: a chave deste ambiente é válida"**. Uma tentativa às 10:02:48 ainda mostrou "chave recusada" (o deploy levou ≈ 4 min desde as 10:01) | relógio local |

**Tempo da falha até o e-mail de disparo: cerca de 1 min 25 s** (09:46:37 → 09:48; o e-mail tem resolução de minuto). O desenho explica: a regra avalia a cada 1 minuto, espera 1 minuto em *Pending* e usa a janela de 5 minutos.

## O que funcionou

* O app **degradou bem**: mensagem clara, nada de traceback, nenhum dado perdido.
* O alerta **disparou, com prioridade (P2), serviço e ambiente nos rótulos**, apontando para o runbook, e foi entregue ao canal configurado.
* O tipo do erro (`AuthenticationError`) apareceu no painel "Erro: falhas do provedor por tipo", que é exatamente onde o runbook manda olhar primeiro.
* O botão "Testar conexão" mostrou o estado **da instância em execução**, inclusive a transição entre a instância antiga e a nova.

## O que deu errado (achados)

| # | Achado | Gravidade | Ação |
|---|---|---|---|
| 1 | **O e-mail caiu na caixa de Spam** do Gmail na primeira entrega | Alta para um canal P2/P1 | Marcar como "não é spam" e criar filtro; **e-mail sozinho é um canal frágil**. Para produção real, adicionar um segundo canal (chat do time ou serviço de plantão) |
| 2 | A regra tratava **"sem dados" como alerta** (`Alert state if no data = No Data`), gerando dois e-mails `DatasourceNoData` de ruído | Média (alerta ruidoso vira alerta ignorado) | Corrigido: *no data* = `Normal`, *execution error* = `Error` (os dois campos estavam invertidos) |
| 3 | A regra **se resolveu sozinha às 09:53 com a chave ainda quebrada**: ela exige ≥ 5 chamadas na janela de 5 min; sem tráfego, a falha fica invisível | **Alta (limitação de desenho)** | Documentado. Mitigação possível: um canário que chame o provedor periodicamente. Limitado aqui porque o plano gratuito do Render dorme sem tráfego; fica como melhoria futura |
| 4 | Quase 4 minutos entre salvar a variável e o app refletir a mudança (deploy do Render) | Baixa | Já tratado: o procedimento exige "Save, rebuild, and deploy" e o teste de conexão em cada ambiente |

## Evidências

* [`alerta-firing-regra.png`](evidencias/alerta-firing-regra.png): regra `FeedbackLoop: provedor de IA falhando` em **Firing**, com a consulta e o gráfico da taxa de falha subindo a 100%.
* [`alerta-firing-instancias.png`](evidencias/alerta-firing-instancias.png): instância `ambiente=dev` em **Alerting**, criada às 09:47:50, destino `ai-eng-oncall-email`.
* [`alerta-emails-recebidos.png`](evidencias/alerta-emails-recebidos.png): os e-mails FIRING (09:48) e RESOLVED (09:53), mais o ruído `DatasourceNoData` (09:51 e 09:52).

## Recuperação

A recuperação foi, na prática, uma **rotação de chave** no estado de emergência (seção 6 do [procedimento](../seguranca/rotacao-de-credenciais.md)):

1. Chave nova `feedbackloop-dev-2026-10b` criada na OpenAI e colada no `OPENAI_API_KEY` do dev (10:01), com *Save, rebuild, and deploy*.
2. **Verificação na instância em execução** com o botão "Testar conexão": às 10:02:48 ainda recusada (deploy em andamento); às **10:06:00, válida**.
3. Tempo total de indisponibilidade **do dev neste exercício: de 09:46 a 10:06 (≈ 20 min)**, dos quais ≈ 15 min foram decorrência de eu manter a falha de propósito para capturar as evidências. Em um incidente real, com a chave nova à mão, o caminho é: criar, colar, deploy (≈ 4 min), testar.

Resultado: o procedimento funcionou; o botão "Testar conexão" se mostrou a ferramenta certa para provar a recuperação *da instância que está no ar*.
