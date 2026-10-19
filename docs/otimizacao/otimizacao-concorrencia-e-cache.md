# Relatório de otimização: chamadas em paralelo e cache com prazo de validade

* Decisão e alternativas descartadas: [ADR-005](../adr/0005-otimizacao-concorrencia-e-cache.md)
* Dados brutos (uma linha por execução): [`docs/benchmarks/dev-2026-10-19.raw.json`](../benchmarks/dev-2026-10-19.raw.json)
* Como as tabelas abaixo são calculadas: `python scripts/consolidar_medicoes_dev.py` (todo número deste relatório sai desse arquivo; há um teste que confere)

## 1. O problema, com número

O pipeline herdado classificava **uma resposta por vez** e, no fim, pedia o resumo: **37 chamadas ao LLM em fila** para uma planilha de 36 respostas. Na tela, isso significava cerca de meio minuto com o app parado. Reanalisar a mesma planilha pagava tudo de novo.

O limite definido para o produto ([métricas e alertas](../observabilidade/metricas-e-alertas.md)) é p95 de 30 s por análise. O "antes" medido ficou **acima** desse limite.

## 2. O que mudou

| Mudança | Onde | Parâmetro |
|---|---|---|
| Classificações em paralelo (pool de threads, ordem preservada) | `feedbackloop/pipeline.py` | `LLM_MAX_WORKERS` (padrão 8; a barra lateral permite 1 a 16) |
| Cache de classificação em SQLite com TTL | `feedbackloop/cache.py` | `CACHE_TTL_DIAS` (padrão 30, teto 90) |

`workers = 1` com cache desligado reproduz exatamente o comportamento anterior, então o "antes" e o "depois" foram medidos com **o mesmo código**, mudando só dois controles da interface.

## 3. Como foi medido

* **Ambiente:** DEV no Render (plano gratuito), commit `0c99d43`, modelo `gpt-5.4-mini`, planilha de exemplo com 36 respostas sintéticas, em 19/10/2026.
* **Instrumento:** os campos que o próprio app mostra após cada análise (Duração do pipeline, chamadas, tokens, custo), lidos por [`scripts/coletor_medicoes_navegador.js`](../../scripts/coletor_medicoes_navegador.js). O dashboard do Grafana (painéis "Antes e depois") recebe as mesmas medições por OpenTelemetry, separadas pelos rótulos `workers` e `cache`.
* **Protocolo:** 6 execuções por configuração; **a primeira é aquecimento e foi descartada** (a primeira observação de uma série nova não entra nos percentis do dashboard). Estatísticas sobre **5 execuções** por cenário. Percentil por posto mais próximo: com n = 5, p95 e p99 são o máximo observado e **não são estimativas de cauda**.
* **Controles extras** (3 execuções cada, sem aquecimento): `Bc` repete o cenário B horas depois, para descartar que o provedor estivesse mais rápido naquele momento; `Cf` mede a execução **fria** com cache ligado (cache limpo antes de cada execução), para isolar o custo de gravar no cache.

## 4. Resultados

### 4.1 Latência da análise (segundos)

| Cenário | n | p50 | p95 | p99 | média | mín | máx |
|---|---:|---:|---:|---:|---:|---:|---:|
| **A. Antes:** 1 em paralelo, sem cache | 5 | **32.3** | 36.4 | 36.4 | 31.9 | 27.9 | 36.4 |
| **B. Depois (concorrência):** 8 em paralelo, sem cache | 5 | **6.8** | 7.2 | 7.2 | 6.8 | 6.5 | 7.2 |
| **C. Depois (concorrência + cache):** reanálise com cache quente | 5 | **2.7** | 3.0 | 3.0 | 2.8 | 2.6 | 3.0 |
| Bc. Controle posterior do B | 3 | 7.1 | 7.7 | 7.7 | 7.0 | 6.2 | 7.7 |
| Cf. Cache ligado, execução fria | 3 | 7.3 | 8.8 | 8.8 | 7.7 | 7.0 | 8.8 |

| Cenário | Redução do p50 | Aceleração (p50) | Redução da média |
|---|---:|---:|---:|
| B (só concorrência) | **79%** | 4.8x | 79% |
| C (concorrência + cache quente) | **92%** | 12.0x | 91% |

Leitura:

* **A concorrência sozinha** leva a análise de ≈ 32 s para ≈ 7 s e **tira o p95 do estado "acima do limite de 30 s"** (36.4 s no antes, 7.2 s no depois).
* **O cache** só vale para **reanálise da mesma planilha**; numa pesquisa nova, a execução é fria (Cf) e o ganho é o da concorrência.
* O controle `Bc` (7.1 s) mostra que o ganho de B não foi um momento de sorte do provedor.

### 4.2 Custo e volume por análise

| Cenário | Chamadas ao LLM | Tokens de entrada | Tokens de saída | Custo estimado (US$) |
|---|---:|---:|---:|---:|
| A | 37 | 6372 | 873 | 0.0087 |
| B | 37 | 6372 | 878 | 0.0087 |
| C (cache quente) | 1 | 199 | 315 | 0.0015 |

* **A concorrência não muda o custo:** são as mesmas 37 chamadas e os mesmos tokens. O ganho vem de **esperar menos, não de fazer menos**.
* **O cache elimina as 36 classificações** de uma reanálise: sobra a chamada do resumo (que depende dos agregados), com custo ≈ 83% menor. O cache **não guarda o texto da resposta**, só `{tema, sentimento}`.
* Preço usado: US$ 0,75 por milhão de tokens de entrada e US$ 4,50 por milhão de saída (variáveis `LLM_PRECO_*`). O custo é **estimado** a partir dos tokens que a API informa, não é fatura.
* Nas execuções C, dos 5 registros, 4 têm chamadas/tokens/custo confiáveis; no registro 2 esses campos foram lidos antes de a tela terminar de atualizar (ver §6) e ficaram de fora da média desses campos.

### 4.3 Qualidade: o que foi e o que não foi medido

Medido nestas execuções (distribuição de sentimento positivo/neutro/negativo e lista dos 8 principais temas):

| Cenário | Mesma distribuição de sentimento (12/1/23) |
|---|---|
| A (1 em paralelo) | 5 de 5 execuções |
| B (8 em paralelo) | 4 de 5 execuções (uma deu 13/0/23) |
| C (cache) | 5 de 5 (o cache devolve o mesmo resultado, por construção) |

* **O LLM não é 100% determinístico, mesmo com temperatura 0.** A lista de temas também muda levemente entre execuções do **mesmo** cenário A (por exemplo "Home office", "Clima organizacional" e "Burocracia" disputam a última vaga). Ou seja, existe uma variação de base que não vem da otimização.
* **O que isso permite afirmar:** não há sinal de degradação sistemática de qualidade; a diferença de B em 1 de 5 execuções é do tamanho da variação já vista entre execuções A.
* **Concordância resposta a resposta:** não saía destas execuções pela interface; foi medida na replicação local da seção 4.5 (sentimento 100%, tema 95,0% contra o baseline, e 96,5% quando o cenário A é comparado com ele mesmo).

### 4.4 Conferência com o dashboard do Grafana (fonte independente)

Captura dos painéis "Antes e depois" ([imagem](../observabilidade/evidencias/dashboard-antes-e-depois-2026-10-19.png); ambiente `dev`, janela das medições, 19/10/2026), comparada com as tabelas acima:

| Painel (rótulos `workers` / `cache`) | Grafana p50 | Grafana p95 | Análises contadas | Esta tabela |
|---|---:|---:|---:|---|
| 1 em paralelo, cache off | 31.7 s | 39.2 s | 5 | A: p50 32.3 s, máx 36.4 s, n = 5 |
| 8 em paralelo, cache off | 6.7 s | 7.8 s | 8 | B + Bc: n = 5 + 3 = 8; mediana das 8 = 6.8 s, máx 7.7 s |
| 8 em paralelo, cache on | 3.5 s | 8.7 s | 8 | C + Cf: n = 5 + 3 = 8 (**5 reanálises quentes + 3 frias**); mediana das 8 = 3.0 s, máx 8.8 s |

* **As contagens batem exatamente** (5, 8 e 8): o dashboard viu as mesmas execuções que o coletor, e a primeira de cada configuração foi realmente descartada nos dois.
* **Os percentis diferem porque o Grafana interpola dentro das faixas (buckets) do histograma, e dá para reproduzir o número exato:** no cenário A, 2 execuções ficam na faixa 20 a 30 s (27.9 e 29.3) e 3 na faixa 30 a 40 s (32.3, 33.6 e 36.4). O p50 interpolado é 30 + 10 × (2,5 − 2) / 3 = **31.7 s** e o p95 é 30 + 10 × (4,75 − 2) / 3 = **39.2 s**, exatamente o que o painel mostra. A faixa larga faz o painel superestimar a cauda (39.2 s contra o máximo real de 36.4 s); **a tabela 4.1 é a fonte dos números citados**, e o painel confirma contagens e ordem de grandeza.
* **O painel "8 em paralelo, cache on" mistura reanálises quentes (≈ 2,7 s) com execuções frias (≈ 7 a 9 s, do controle Cf)**, e por isso mostra p50 = 3.5 s e p95 = 8.7 s. Ele **não** representa o cache quente sozinho; o número do cache quente é o da tabela 4.1 (p50 = 2.7 s, n = 5). Em produção o painel terá a mesma mistura, proporcional à taxa de reanálise: é assim que ele deve ser lido.

### 4.5 Replicação local com `scripts/benchmark.py` (outra máquina, outra rede, com concordância por resposta)

Para não depender de uma única medição, repeti o experimento no computador do autor, com chamadas reais, pelo script versionado (`python scripts/benchmark.py --repeticoes 5`, commit `e896f9a`, 19/10/2026). Dados brutos: [`benchmark-real.json`](../benchmarks/benchmark-real.json). Aqui **as 5 execuções de cada cenário entram** (o script não descarta a primeira nos cenários A e B; o cache do cenário C é aquecido por uma execução à parte).

| Cenário | n | p50 (s) | p95 (s) | média (s) | Redução do p50 | Chamadas | Custo por análise (US$)* |
|---|---:|---:|---:|---:|---:|---:|---:|
| A. 1 em paralelo, sem cache | 5 | 30.4 | 33.4 | 30.8 | (referência) | 37 | 0.0088 |
| B. 8 em paralelo, sem cache | 5 | 6.1 | 6.5 | 6.1 | **80,0%** | 37 | 0.0088 |
| C. 8 em paralelo, cache quente | 5 | 2.8 | 3.0 | 2.8 | **90,8%** | 1 | 0.0017 |

\* O script não calcula custo sem as variáveis `LLM_PRECO_*` no `.env` local (saiu `n/d`). Os valores acima foram calculados por mim a partir dos tokens medidos (média de 6372 de entrada e 890 de saída no cenário A) com US$ 0,75 e US$ 4,50 por milhão de tokens.

As duas medições independentes concordam: p50 de **32.3 s → 6.8 s → 2.7 s** no dev e **30.4 s → 6.1 s → 2.8 s** localmente, com reduções de 79% e 80% (concorrência) e de 92% e 91% (cache quente). O resultado local é um pouco mais rápido que o do dev, como esperado (o dev roda no plano gratuito do Render).

**Concordância resposta a resposta com o baseline** (a 1ª execução do cenário A; as classificações são comparadas uma a uma nas 36 respostas):

| Comparação | Sentimento | Tema |
|---|---:|---:|
| A contra A (execuções 2 a 5; **variação natural do LLM**) | 100% em todas | 96,5% (94,4%, 97,2%, 94,4%, 100%) |
| B contra o baseline (execuções 1 a 5) | 100% em todas | 95,0% (mín. 91,7%) |
| C contra o baseline | 97,2% | 97,2% |

Leitura honesta:

* **Sentimento: nenhuma diferença** entre sequencial e concorrente em 5 de 5 execuções. A única divergência de sentimento (1 resposta em 36, 97,2%) está no cenário C, e vem do cache: ele foi preenchido por uma execução que já divergia do baseline nessa resposta e depois devolve sempre o mesmo resultado (as 5 reanálises são idênticas entre si).
* **Tema:** o tema é texto livre do LLM e a comparação é por igualdade exata, então sinônimos ("Home office" e "Trabalho remoto") contam como discordância. Mesmo A contra A diverge em 0 a 2 respostas de 36. B diverge em 1 a 3 de 36 (média 1,8) contra 0 a 2 (média 1,25) de A contra A. **A diferença de 1,5 ponto percentual entre B e A contra A é do tamanho da variação entre execuções com n = 5; não dá para afirmar nem descartar um efeito pequeno.** O mecanismo não sugere causa: a concorrência não altera o prompt nem a temperatura, só a ordem em que as respostas chegam.
* O baseline é uma execução do próprio LLM, **não uma verdade rotulada por pessoas**. Isto mede **consistência**, não **correção** dos temas e sentimentos.

## 5. Trade-offs (o que se paga por esse ganho)

1. **Mais chamadas simultâneas aumentam o risco de limite de taxa (HTTP 429).** Com 8 chamadas em paralelo e ≈ 6 mil tokens por análise, o piloto está longe do limite; com várias pessoas usando ao mesmo tempo, não sabemos. Mitigação: teto de 16 workers e retry com backoff do SDK (`LLM_MAX_RETRIES=3`). A análise continua mesmo se algumas respostas falharem. **Não foi testado sob carga de várias pessoas.**
2. **O cache só ajuda quando a mesma resposta se repete.** Em pesquisa nova, 100% de erros de cache.
3. **O disco do Render gratuito é efêmero e o serviço dorme sem uso:** o cache some a cada deploy e reinício. No uso real, o acerto será menor do que no teste (que ocorreu com o serviço aceso e sem deploy no meio).
4. **Cache = mais um lugar com dado derivado de resposta de pessoa.** Por isso: não guarda texto, tem chave por hash do texto **já mascarado**, TTL de 30 dias, purga horária e botão "Excluir cache agora" ([política de retenção](../lgpd/politica-de-retencao-e-exclusao.md)).
5. **Duas respostas diferentes que mascaram para o mesmo texto compartilham a classificação.** Aceito: o nome mascarado não deveria mudar o tema.
6. **Custo de gravar no cache em execução fria:** Cf (p50 7.3 s) versus B (6.8 s) e Bc (7.1 s). A diferença é de ≈ 0,2 a 0,5 s, **dentro da variação entre execuções** com n = 3. Não há evidência de custo relevante, mas também n = 3 não permite afirmar que seja zero.

## 6. Limitações e problemas encontrados na medição (sem esconder)

* **Medição no DEV, plano gratuito, uma planilha, uma tarde.** Não é um teste de carga. As conclusões valem para esse perfil.
* **Uma execução fria isolada levou 17.5 s** (a primeira do cenário C, quando o cache estava vazio sendo preenchido). Depois, 3 execuções frias repetidas deram 7.0, 7.3 e 8.8 s. **Não identifiquei a causa** (pode ser latência pontual do provedor ou da instância gratuita); ela foi descartada como aquecimento, mas fica registrada aqui e nos dados brutos, e **não** foi usada para esconder nem para inflar nada.
* **Defeito do coletor, corrigido:** na primeira versão, após detectar o fim da análise, o coletor lia os campos de uma vez; a tela do Streamlit atualiza de cima para baixo e, em pelo menos uma execução (C, registro 2), chamadas/tokens/custo foram lidos ainda do resultado anterior. Os registros afetados estão marcados com `null` nos dados brutos e fora das médias dessas colunas. O coletor passou a reler até o valor se estabilizar (as coletas `Bc` e `Cf` já usaram a versão corrigida). A **duração** vem do primeiro campo atualizado e foi conferida contra o relógio de parede, com uma exceção: no registro A3, a duração (33.6 s) ficou 1,2 s **acima** do relógio medido (32.4 s), o que não deveria ocorrer; mantive o valor porque o app é a fonte primária, e o efeito sobre a mediana é nulo (a mediana de A é o registro A4, 32.3 s).
* **Duas execuções iguais seguidas.** Os registros A1/A2 e B1/B2 têm duração e tokens idênticos. Como o relógio de parede de cada um é diferente (A: 42.8 s e 36.8 s; B: 8.6 s e 7.3 s) e o primeiro de cada cenário é descartado, aceitei os dados; se fossem leituras repetidas, o efeito seria sobre um único ponto das 5 medidas de cada cenário.
* **p95 e p99 com n = 5 são o máximo observado.** Os painéis do Grafana interpolam dentro de faixas (buckets) do histograma e por isso diferem da tabela (§4.4; no cenário A, o p95 do painel é 39.2 s contra 36.4 s medidos). O dashboard serve para acompanhar tendência; **a tabela 4.1 é a fonte dos números do vídeo e do README**.

## 7. Conclusão

* **Antes:** p50 = 32.3 s (p95 = 36.4 s, acima do limite de 30 s), 37 chamadas, ≈ US$ 0,0087 por análise.
* **Depois (concorrência):** p50 = 6.8 s (**−79%**), mesmas 37 chamadas, mesmo custo.
* **Depois (concorrência + cache quente):** p50 = 2.7 s (**−92%**), 1 chamada, ≈ US$ 0,0015 (**−83%**), válido só para reanálise.
* Replicação local independente: 30.4 s → 6.1 s (−80%) → 2.8 s (−91%).
* Qualidade: sentimento idêntico ao baseline em todas as execuções concorrentes; tema 95,0% de concordância contra 96,5% de A contra A (variação natural do LLM; diferença dentro do ruído com n = 5).

## 8. Como reproduzir

1. Medição pela interface (a mesma deste relatório): abra o app, barra lateral → "Avançado: medir otimizações", escolha as chamadas em paralelo e o cache, cole `scripts/coletor_medicoes_navegador.js` no console e rode `await window.__medir(6, 'rótulo')`. Descarte a 1ª execução.
2. Medição sem navegador, com concordância entre configurações (feita na seção 4.5): `python scripts/benchmark.py --repeticoes 5 --saida docs/benchmarks/benchmark-real.json` (precisa da sua `OPENAI_API_KEY` no `.env` local; `python scripts/relatorio_benchmark.py docs/benchmarks/benchmark-real.json` gera as tabelas); `python scripts/benchmark.py --simulado` roda sem chave, **apenas para testar o código** (sem latência real, não serve como medição).
3. Recalcular as tabelas: `python scripts/consolidar_medicoes_dev.py`.

## 9. Próximos passos

* Avaliação de qualidade **contra rótulos humanos** (hoje só se mede consistência entre execuções do próprio LLM).
* Teste de carga com vários usuários simultâneos para medir a taxa de limite (429), que não foi exercitada.
* Experimento futuro: agrupar respostas por chamada (*batch prompting*) e taxonomia fixa de temas (reduz a fragmentação de temas e a discordância por sinônimo).
