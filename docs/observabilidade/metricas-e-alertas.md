# Observabilidade: traces, cinco métricas, limiares e alertas

**Dashboard:** *(link público preenchido no [README](../../README.md#observabilidade))*. O JSON importável está em [`observabilidade/dashboard-feedbackloop.json`](../../observabilidade/dashboard-feedbackloop.json) e é **gerado** por [`scripts/gerar_dashboard.py`](../../scripts/gerar_dashboard.py). Decisão de ferramenta: [ADR-003](../adr/0003-observabilidade-opentelemetry-grafana-cloud.md).

## 1. Como os dados chegam

```
App Streamlit (feedbackloop/)  ──OTLP/HTTP──▶  Grafana Cloud (São Paulo)  ──▶  Dashboard + Alertas ──e-mail──▶ AI Engineer
   spans + métricas + log JSON                    Tempo (traces) · Mimir (métricas)
```

* A instrumentação fica em [`feedbackloop/observabilidade.py`](../../feedbackloop/observabilidade.py); o cliente do provedor em [`feedbackloop/llm.py`](../../feedbackloop/llm.py) registra cada chamada.
* **Privacidade por desenho, testada:** nenhum span, métrica ou log contém texto de resposta, nome ou token (`test_nenhum_span_nem_log_contem_dado_pessoal`, `test_o_token_nunca_aparece_em_span_metrica_nem_log`).
* Todo ponto de métrica leva o rótulo `ambiente` (`dev`, `prod`, `benchmark`), então o mesmo dashboard e o mesmo alerta servem a todos os ambientes.

## 2. Traces e spans

Um trace por análise, cobrindo o fluxo real, inclusive através das threads da concorrência (o contexto é propagado):

```
analise                                  (respostas, workers, cache, resultado)
├── pii.sanitizar                        (entidades mascaradas por tipo: só contagens)
├── classificar.lote
│   └── classificar.resposta  × N        (cache hit ou miss)
│       └── llm.chamada                  (modelo, tokens de entrada e saída, custo, tipo de erro)
└── resumo.gerar
    └── llm.chamada
```

Onde ver: Grafana → **Explore** → fonte `-traces` (Tempo) → *Search* → `service.name = feedbackloop`. Teste que garante a hierarquia: `test_trace_da_analise_tem_a_hierarquia_esperada_mesmo_com_threads`.

## 3. As cinco métricas essenciais, os limiares e por que cada um

Os limiares vêm de duas fontes que declaro: **(a)** heurística de experiência do usuário e de orçamento, e **(b)** o que foi **medido** nesta etapa. Revisar com dados do piloto real.

Preço usado no custo: **US$ 0,75 por 1 milhão de tokens de entrada e US$ 4,50 por 1 milhão de saída** (`gpt-5.4-mini`, tarifa padrão, contexto curto; fonte: página de preços da OpenAI, lida em 19/10/2026). Configurado por `LLM_PRECO_ENTRADA_USD_POR_MTOK` e `LLM_PRECO_SAIDA_USD_POR_MTOK`.

| # | Métrica | Instrumento (Prometheus) | Verde | Amarelo | Vermelho | Por que esse limite |
|---|---|---|---|---|---|---|
| 1 | **Latência** da análise de 36 respostas (p50 / p95 / p99) | `feedbackloop_analise_duracao_seconds_bucket` | p50 ≤ 8 s · p95 ≤ 20 s · p99 ≤ 30 s | p50 ≤ 15 s · p95 ≤ 30 s · p99 ≤ 60 s | acima | Análise em lote, mas o analista fica olhando a tela: 10 s é o limite clássico de atenção; 30 s é o máximo tolerável sem feedback. **Medido** ([relatório](../otimizacao/otimizacao-concorrencia-e-cache.md)): a versão sequencial tinha p50 = 32,3 s e p95 = 36,4 s (**vermelho**); a otimizada, p50 = 6,8 s e p95 = 7,2 s (**verde**). Os limites existem para detectar **regressão**. |
| 2 | **Custo** por análise de 36 respostas | `feedbackloop_llm_custo_usd_total` ÷ `feedbackloop_analises_total` | ≤ US$ 0,015 | ≤ US$ 0,03 | acima | **Medido:** ≈ US$ 0,009 por análise (≈ 6.400 tokens de entrada e ≈ 880 de saída). A meta é ~1,7x o medido: se triplicar, mudou o prompt, o modelo ou há laço de tentativas. Orçamento: US$ 120/mês no total; reservando metade para IA, cabem ≈ 6.600 análises/mês antes de estourar. |
| 3 | **Erro**: taxa de falha das chamadas ao provedor | `feedbackloop_llm_chamadas_total{resultado="erro"}` ÷ total | < 2% | 2% a 5% | ≥ 5% (dashboard); **alerta a partir de 20%** | O retry do SDK (3 tentativas com backoff) já absorve falhas isoladas, então erro que sobra é sistêmico. 2% ≈ uma chamada em uma análise de 37. O alerta é mais alto (20%) para não acordar ninguém por 1 chamada ruim. |
| 4 | **Volume**: análises e respostas processadas | `feedbackloop_analises_total`, `feedbackloop_respostas_total` | informativo | > 50 análises/h | > 100 análises/h (**alerta P3**) | Dá contexto aos demais números. O piloto espera dezenas por dia; 100/h custa < US$ 1/h mas é ~11x o esperado: possível abuso ou laço. |
| 5 | **Qualidade**: respostas "Não classificado" e fragmentação de temas | `feedbackloop_qualidade_nao_classificadas_total` ÷ `feedbackloop_respostas_total`; `feedbackloop_qualidade_fragmentacao_temas_*` | < 5% não classificadas · fragmentação ≤ 70% | 5% a 10% · 70% a 85% | acima | Não há como medir "qualidade do resumo" sem rubrica humana. Uso dois **proxies automáticos**: (a) o JSON do modelo não pôde ser lido (mudança de prompt ou modelo quebrou o contrato); (b) fragmentação = temas distintos ÷ respostas (100% = cada resposta virou um tema e a agregação não serve a ninguém). Era a dor documentada pelo autor original ("30 respostas, 25 temas"). **Medido:** 23 a 24 temas distintos em 36 respostas (**64% a 67%**) nas 15 execuções do benchmark local ([dados](../benchmarks/benchmark-real.json): 24 temas em 14 delas e 23 em uma). A **meta de produto (≤ 35%) não é atingida hoje**; por isso o limiar do dashboard (verde até 70%, amarelo até 85%) é de **detecção de piora** sobre a linha de base, não uma aprovação. Reduzir isso é a dívida de qualidade mais clara (candidata: taxonomia fixa de temas, ver [relatório de otimização](../otimizacao/otimizacao-concorrencia-e-cache.md), próximos passos) |

Cada limiar aparece com a cor correspondente nas caixas do dashboard; a descrição de cada painel repete a meta.

## 4. Alertas

Fonte de verdade: [`observabilidade/alertas.yaml`](../../observabilidade/alertas.yaml). **Alerta sem ação é ruído**: cada regra tem prioridade, público, canal e ação.

| Prioridade | Significado | Tempo de resposta |
|---|---|---|
| **P1** | Funcionalidade principal fora do ar para todos, em produção | Agir na hora |
| **P2** | Funcionalidade principal degradada | Mesmo dia útil, em até 1 h |
| **P3** | Qualidade, custo ou desempenho fora da meta | Vira tarefa; resolver no ciclo da semana |

| Regra | Prioridade | Condição | Público | Canal | Ação | Estado |
|---|---|---|---|---|---|---|
| `FL-ERRO-LLM`: provedor de IA falhando | **P2** (P1 se ≥ 90% por 10 min em prod) | > 20% das chamadas falham em 5 min, com ≥ 5 chamadas | AI Engineer de plantão; escalar para a Head de People Analytics se passar de 1 h ou virar P1 | E-mail (`ai-eng-oncall-email`) | [Runbook](runbook.md), seção FL-ERRO-LLM | **Configurada e testada ao vivo** ([simulado](simulado-de-alerta-2026-10-19.md)) |
| `FL-LATENCIA-P95`: análise lenta | P3 | p95 > 30 s na última hora, com ≥ 3 análises | AI Engineer | E-mail | [Runbook](runbook.md) | Definida; ainda não criada no Grafana |
| `FL-VOLUME-ANOMALO`: volume anormal | P3 | > 100 análises/h em prod | AI Engineer | E-mail | [Runbook](runbook.md) | Definida; ainda não criada no Grafana |

### O que faz o alerta principal disparar (e o que aprendemos)

* **Dispara quando** mais de 20% das chamadas ao provedor falham numa janela de 5 minutos, com pelo menos 5 chamadas, por 1 minuto seguido. Causas típicas: **chave recusada**, créditos esgotados, provedor fora do ar.
* **Provado em 19/10/2026:** com uma chave inválida no dev, o e-mail de disparo chegou **≈ 1 min 25 s** depois da primeira falha. O simulado também achou três limites reais: o e-mail caiu em **spam**, a configuração de "sem dados" gerava **ruído** (corrigida), e a regra **se resolve sozinha sem tráfego**, mesmo com a chave ainda quebrada. Detalhes em [simulado-de-alerta-2026-10-19.md](simulado-de-alerta-2026-10-19.md).

## 5. Limites conhecidos desta observabilidade

* **Percentis de histograma são aproximados** (interpolados dentro do bucket). Os buckets foram refinados em torno dos valores reais (1 s entre 3 e 10 s, 10 s entre 40 e 90 s); o relatório de otimização usa valores exatos do benchmark e o dashboard como confirmação.
* **Primeira análise após cada reinício do serviço** não entra nos percentis (um histograma que nasce já com valor perde o primeiro incremento no `increase()`); ela serve de aquecimento. Os **contadores** têm ponto zero de partida e **são** contados.
* **O serviço gratuito do Render dorme** sem uso: sem tráfego não há métricas, e o alerta baseado em tráfego não vê falhas.
* Retenção de 14 dias no plano gratuito do Grafana Cloud.
