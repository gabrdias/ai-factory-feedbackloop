# Runbook de alertas

Para quem recebe o e-mail do alerta. Objetivo: em menos de 10 minutos saber **o que quebrou, quem é afetado e qual o primeiro passo**. Definições dos alertas: [`observabilidade/alertas.yaml`](../../observabilidade/alertas.yaml). Métricas e limiares: [`metricas-e-alertas.md`](metricas-e-alertas.md).

## Antes de tudo (30 segundos)

1. Abra o dashboard do ambiente que disparou (campo **ambiente** no topo) e olhe a janela das últimas 1 a 3 horas.
2. Confirme que o app responde: abrir a URL pública e o endpoint `/_stcore/health` (deve responder `ok`).
3. Veja o que mudou: houve deploy ou troca de chave recentemente? (GitHub Actions e Render → Events). **Se o problema começou junto com um deploy, o rollback é a primeira medida** e a correção do código vem logo depois: o rollback sozinho se desfaz no próximo deploy automático (lição de 21/09, [post-mortem](../post-mortem-2026-09-21.md)).

## FL-ERRO-LLM (P2): provedor de IA falhando

Olhe o painel **"Erro: falhas do provedor por tipo"** (ou a consulta `sum by (tipo_erro) (increase(feedbackloop_llm_erros_total[10m]))`).

| Tipo dominante | Significa | Primeiro passo | Quem decide |
|---|---|---|---|
| `AuthenticationError` | Chave de API recusada (revogada, trocada errada ou expirada) | Conferir `OPENAI_API_KEY` **daquele** ambiente no Render. Se foi uma rotação, seguir o [procedimento](../seguranca/rotacao-de-credenciais.md) (a chave nova tem que estar no Render **antes** de revogar a antiga) | AI Engineer |
| `RateLimitError` | Créditos esgotados ou limite do provedor | Verificar saldo e limites no painel da OpenAI; adicionar créditos | AI Engineer, com Financeiro se precisar de verba |
| `APITimeoutError` / `APIConnectionError` | Rede ou instabilidade do provedor | Checar a página de status do provedor; o retry do SDK já tenta 3 vezes; aguardar | AI Engineer |
| Outro | Erro novo | Abrir um trace no Grafana (Explore > Tempo, serviço `feedbackloop`, filtrar spans com erro) e ler a exceção do span `llm.chamada` | AI Engineer |

**Mitigação para o usuário:** o app já mostra uma mensagem clara quando todas as chamadas falham (não mostra traceback) e não grava nada. Não há perda de dados a recuperar.

**Escalar para P1** se em **prod** a taxa ficar em 90% ou mais por 10 minutos: avisar a Head de People Analytics, avisar os clientes-piloto que a análise está indisponível e considerar rollback do último deploy.

**Como confirmar a resolução:** rodar uma análise de teste com os dados sintéticos no ambiente afetado; o painel de erro deve parar de crescer e o alerta volta a "Normal" quando a janela de 5 min esvaziar.

## FL-LATENCIA-P95 (P3): análise lenta

1. Conferir **LLM_MAX_WORKERS** e **CACHE_HABILITADO** no ambiente (a barra lateral do app mostra "Chamadas em paralelo" e "Cache"). Valor 1 em produção é o comportamento anterior à otimização.
2. Ver o painel **"Latência da análise"** e o de **"Chamadas ao LLM por resultado"**: muitas falhas com retry aumentam a duração.
3. Comparar o tamanho da planilha: a duração cresce com o número de respostas.
4. Se foi regressão de código, abrir tarefa com o commit suspeito (o app mostra o commit em execução na barra lateral).

## Depois de qualquer incidente real

Registrar um post-mortem curto, sem culpados, no padrão de [`docs/post-mortem-2026-09-21.md`](../post-mortem-2026-09-21.md): linha do tempo com horários comprovados, causa, o que funcionou, o que não funcionou e ações.
