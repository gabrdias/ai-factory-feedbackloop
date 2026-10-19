# ADR-003: Instrumentar com OpenTelemetry e enviar para o Grafana Cloud (região São Paulo)

* Status: aceita
* Data: 2026-10-19

## Contexto e problema

A Etapa 2 pede que o sistema deixe de "falhar em silêncio": traces com spans do fluxo real, cinco métricas essenciais (latência p50/p95/p99, custo, erro, volume e qualidade), um alerta funcional com prioridade, público e canal, e um dashboard linkado no README cujos números batam com o relatório. O prototipo não tinha nenhum log, métrica ou rastro (ver [auditoria](../auditoria-prototipo.md), seção 2.4), e o incidente de 19/10 mostrou o custo disso: a produção ficou sem funcionar e **nada avisou** ([post-mortem](../post-mortem-2026-10-19-rotacao-de-chave.md)).

Restrições: orçamento de US$ 120/mês total (hospedagem + LLM), time de uma pessoa, dados de respondentes **não** podem ir para a telemetria, e a hospedagem escolhida (Render, plano gratuito) tem disco efêmero e dorme por inatividade.

## Motivadores da decisão

* Precisa cobrir **trace e spans**, não só logs soltos (critério "Autônomo" da rubrica).
* O dashboard precisa sobreviver a reinícios do serviço: métricas guardadas **fora** da instância.
* Precisa de alertas por e-mail sem servidor próprio.
* Custo zero ou muito baixo no piloto.
* Privacidade: nada de texto de resposta nem dado pessoal na telemetria; idealmente os dados ficam no Brasil.
* Não ficar preso a um fornecedor: instrumentação em padrão aberto.

## Opções consideradas

* **OpenTelemetry + Grafana Cloud (plano gratuito)**
* Langfuse Cloud (observabilidade específica de LLM)
* Métricas nativas do Render + logs
* Prometheus + Grafana + Tempo auto-hospedados
* Sentry (erros) ou Datadog

## Resultado da decisão

Opção escolhida: **OpenTelemetry (SDK Python, exportação OTLP/HTTP) enviando para o Grafana Cloud**, na região **São Paulo** (`prod-sa-east-1`).

* A **instrumentação é padrão aberto**: trocar de backend é mudar duas variáveis de ambiente, não reescrever código.
* Traces e métricas ficam no Grafana Cloud (Tempo e Mimir), fora do disco efêmero; o plano gratuito retém 14 dias e permite 10 mil séries ativas e 50 GB de traces por mês, folga larga para o piloto.
* Alertas, dashboard e contact point por e-mail vêm no mesmo produto, sem servidor próprio.
* A região São Paulo mantém a telemetria no Brasil (um problema a menos na [análise de transferência internacional](../lgpd/transferencia-internacional.md)).
* Dashboard e alertas estão **versionados como código** (`observabilidade/`), com testes que impedem divergência com o código da aplicação.

### Consequências positivas

* Um trace por análise mostra `analise` → `pii.sanitizar` → `classificar.lote` → `classificar.resposta` → `llm.chamada` → `resumo.gerar`, inclusive através das threads da concorrência.
* O alerta de erro provou funcionar de ponta a ponta no simulado de incidente (ver [métricas e alertas](../observabilidade/metricas-e-alertas.md)).
* Privacidade por desenho e **testada**: nenhum span, métrica ou log carrega texto, nome ou token.

### Consequências negativas e trade-offs aceitos

* **Dependência de uma conta e de um token externo** (mais um segredo para rotacionar; ver [rotação](../seguranca/rotacao-de-credenciais.md)).
* **Percentis de histograma são aproximados**: o valor é interpolado dentro do bucket. Descobrimos isso ao ver "p95 = 9,8 s" para duas análises de 7,9 s e 7,0 s; os buckets foram refinados, e o relatório de otimização usa os valores exatos do benchmark e cita o dashboard como confirmação.
* **Séries que nascem já com valor perdem o primeiro incremento** no `increase()` do Prometheus. Mitigado com um ponto zero de partida nos contadores (`Instrumentos.aquecer`); para histogramas a primeira análise após cada reinício serve de aquecimento e não é medida.
* O plano gratuito limita a 14 dias de retenção e 3 usuários; o dashboard público (se disponível no plano) só aceita painéis do Prometheus, então traces entram como captura de tela.
* O app envia métricas a cada 15 s por uma thread; num serviço que dorme, métricas dos últimos segundos antes de dormir podem se perder.

## Prós e contras das opções descartadas

### Langfuse Cloud

* Bom, porque: feito para LLM (tokens, custo, scores de qualidade nativos), UI de traces excelente.
* Ruim, porque: não tem alerta nativo equivalente ao que a rubrica pede, o dashboard não é compartilhável da mesma forma e a instrumentação seria específica da ferramenta. Pode ser **somado** depois, já que OTel exporta para vários destinos.

### Métricas nativas do Render + logs

* Bom, porque: zero configuração.
* Ruim, porque: mede o servidor (CPU, memória, requisições HTTP), não a análise. O Streamlit usa WebSocket, então a latência HTTP não é a latência da análise; não há custo, qualidade nem traces; e o histórico é curto.

### Prometheus + Grafana + Tempo auto-hospedados

* Bom, porque: controle total e custo de licença zero.
* Ruim, porque: precisaria de servidor persistente (o plano gratuito do Render não tem disco durável nem fica de pé), mais uma coisa para operar e proteger, num time de uma pessoa.

### Sentry ou Datadog

* Bom, porque: Sentry é ótimo para exceções; Datadog cobre tudo.
* Ruim, porque: Sentry não mede latência, custo e qualidade como métricas de negócio; Datadog sai do orçamento do piloto.

## Mais informações

* Instrumentação: [`feedbackloop/observabilidade.py`](../../feedbackloop/observabilidade.py)
* Dashboard e alertas como código: [`observabilidade/`](../../observabilidade/)
* Limiares e alertas: [`docs/observabilidade/metricas-e-alertas.md`](../observabilidade/metricas-e-alertas.md)
