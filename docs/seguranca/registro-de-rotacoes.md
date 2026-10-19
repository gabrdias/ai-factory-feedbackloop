# Registro de rotações de credenciais

Cada linha é uma execução do [procedimento de rotação](rotacao-de-credenciais.md). **Nunca** se escreve o valor de um segredo aqui; só data, ambiente, o que foi feito e como foi verificado.

**Sobre as horas:** fuso de Brasília. Horas com `≈` foram informadas de memória pelo responsável e **não** vêm de log do sistema; horas sem `≈` vêm do relógio da máquina de quem executou o teste ou de eventos verificáveis. "Não registrado" significa que a ação foi feita e confirmada, mas ninguém anotou a hora. A fonte exata, para quem quiser conferir, é a coluna *Created* da página de chaves da OpenAI (criação e revogação) e a aba *Events* de cada serviço no Render (troca de variável e deploy).

Responsável por todas as execuções: Gabriel Dias (AI Engineer).

## R-001: rotação planejada de `OPENAI_API_KEY` (exercício da Etapa 2), 2026-10-19

| Passo | Hora | Ambiente | O que foi feito | Resultado da verificação |
|---|---|---|---|---|
| 1 | ≈ 08:47 | local | Criada a chave `feedbackloop-local-2026-10` | n/a |
| 2 | ≈ 08:48 | dev | Criada a chave `feedbackloop-dev-2026-10` | n/a |
| 3 | ≈ 08:49 | prod | Criada a chave `feedbackloop-prod-2026-10` | n/a |
| 4 | não registrado | dev | Chave nova colada no Render e deploy | **OK**: análises reais no dev a partir de 09:09 (primeira métrica recebida no Grafana às 09:09:27) |
| 5 | não registrado | prod | Chave nova colada no Render **sem novo deploy** | **FALHOU** às 09:34:43: `401 token_invalidated` (ver passo 7) |
| 6 | não registrado | dev e prod | Chave antiga revogada na OpenAI (feito antes da verificação do prod) | Foi o que expôs a falha do passo 5 |
| 7 | entre ≈ 09:35 e 09:38 | prod | *Save, rebuild, and deploy* | **OK** às 09:38:27: análise completa no prod com a chave nova |

Resultado final: as 3 chaves distintas por ambiente, a antiga revogada. O desvio de ordem (revogar antes de verificar o prod) gerou um incidente real, analisado em [post-mortem-2026-10-19-rotacao-de-chave.md](../post-mortem-2026-10-19-rotacao-de-chave.md); o procedimento foi corrigido (passos 2 a 6 de [rotacao-de-credenciais.md](rotacao-de-credenciais.md), com o botão "Testar conexão com o provedor").

## R-002: simulado de incidente do alerta (chave inválida no dev)

| Hora | Ambiente | Tipo | O que foi feito | Resultado |
|---|---|---|---|---|
| 09:42 a 10:06 | dev | Emergência **simulada** | 09:42: chave do dev trocada por valor inválido para disparar o alerta `FL-ERRO-LLM`. 10:01: chave nova `feedbackloop-dev-2026-10b` criada e instalada, conforme a seção 6 do procedimento | O alerta disparou (e-mail às 09:48, caiu em spam) e se resolveu às 09:53; recuperação confirmada às 10:06:00 com o botão "Testar conexão". Detalhes: [simulado](../observabilidade/simulado-de-alerta-2026-10-19.md) |

## Rotações de outros segredos nesta etapa

| Segredo | Situação |
|---|---|
| `GRAFANA_TOKEN` (dev) | Criado em 2026-10-19 (hora não registrada) e instalado no Render; primeira métrica recebida às 09:09:27 |
| `GRAFANA_TOKEN` (prod) | Criado em 2026-10-19 (hora não registrada), instalado no Render antes da release; o prod passou a rodar a v1.0.0 (commit `a6b87e2`) e o teste de conexão do prod respondeu "chave válida" em 1,1 s |
| `RENDER_DEPLOY_HOOK` | Não rotacionado nesta etapa (próxima rotação planejada abaixo) |

## Próxima rotação planejada

90 dias após a conclusão de R-001, ou seja, até **2027-01-17**.
