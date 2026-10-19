# ADR-005: Reduzir latência e custo com chamadas em paralelo e cache com prazo de validade

* Status: aceita
* Data: 2026-10-19

## Contexto e problema

O pipeline herdado fazia **uma chamada ao LLM por resposta, uma depois da outra**, mais uma para o resumo: 37 chamadas em fila para uma planilha de 36 respostas, o que levava mais de um minuto com a tela travada. Além disso, **reanalisar a mesma planilha pagava tudo de novo** (a dívida nº 3 do protótipo: "sem cache, reanalisa tudo toda vez"). O orçamento do piloto é de US$ 120/mês, a hospedagem é o plano gratuito do Render (disco efêmero, dorme sem uso) e **qualquer coisa que persista dado é superfície de LGPD**.

Era preciso decidir **qual otimização** atacar, sabendo que a Etapa 2 exige número antes e depois e uma discussão honesta do trade-off entre latência, custo e qualidade.

## Motivadores da decisão

* Maior ganho de latência pelo menor risco.
* **Não piorar a qualidade**: a classificação de cada resposta não pode mudar por causa da otimização (verificável).
* Sem infraestrutura nova (conta, serviço, segredo extra) no plano gratuito.
* O cache não pode guardar texto de resposta nem nada que reidentifique alguém.
* Medição reproduzível, comparando o "antes" e o "depois" com o mesmo código.

## Opções consideradas

* **Chamadas em paralelo (pool de threads) + cache local com TTL** (escolhida)
* Agrupar várias respostas por chamada (*batch prompting*)
* Embeddings + clustering (a ideia do autor original, ver `docs/notas-rafael.md`)
* Cache externo (Redis ou Postgres)
* Fallback para um segundo provedor
* Manter como está

## Resultado da decisão

Opção escolhida: **pool de threads para as classificações** (`max_workers`, padrão 8, configurável de 1 a 16) **e cache em SQLite com TTL** (padrão 30 dias, teto do briefing: 90), mais o retry com backoff exponencial do próprio SDK (`LLM_MAX_RETRIES=3`) para absorver os limites de taxa que a concorrência pode provocar.

* A concorrência **preserva a ordem** e o resultado: `max_workers=1` reproduz exatamente o comportamento antigo, o que permite medir "antes" e "depois" com o **mesmo código**, só mudando um parâmetro.
* O cache guarda `sha256(prompt_version | modelo | texto já mascarado)` e `{tema, sentimento}`. **Nunca o texto.** O texto mascarado é um dado derivado; mesmo assim vale TTL, purga horária e botão de exclusão ([política de retenção](../lgpd/politica-de-retencao-e-exclusao.md)).
* A chave inclui a **versão do prompt** e o **modelo**: mudar qualquer um invalida o cache em vez de servir classificação antiga.
* Falha de uma resposta **não derruba a análise**: ela vira "Não classificado" e a análise segue com aviso; só se **todas** falharem o app mostra erro (mensagem amigável).

Números: ver o [relatório de otimização](../otimizacao/otimizacao-concorrencia-e-cache.md).

### Consequências positivas

* O ganho de latência vem de **esperar menos, não de fazer menos**: o custo em tokens por análise é o mesmo.
* O cache elimina as 36 chamadas de classificação de uma reanálise (só o resumo, que depende dos agregados, é recalculado).
* Os controles ficam visíveis na barra lateral ("Avançado: medir otimizações"), o que torna o antes/depois demonstrável ao vivo; o dashboard separa as medições por `workers` e `cache`.

### Consequências negativas e trade-offs aceitos

* **Mais chamadas simultâneas ao provedor** aumentam o risco de limite de taxa (429). Mitigação: teto de 16 workers e o retry do SDK; se o limite for atingido, a análise ainda conclui, só mais devagar.
* **O cache só ajuda quando a mesma resposta se repete.** Numa pesquisa nova, 100% de erros de cache: o ganho vem da concorrência. O ganho do cache existe para o caso documentado de reanálise (mesma planilha, mesma configuração).
* **O disco do Render gratuito é efêmero e o serviço dorme**: o cache some a cada deploy ou reinício. Em produção real o acerto será menor do que no benchmark. Subir de plano (disco persistente) ou usar um armazenamento externo resolveria, ao custo de mais superfície de LGPD.
* **Custo de qualidade nulo, mas só para a mesma entrada:** como o cache é por texto mascarado, duas respostas diferentes que mascaram para o mesmo texto (por exemplo, só mudou o nome da pessoa) compartilham a classificação. Aceito: o nome mascarado não deveria mudar o tema.
* A temperatura 0 dá resultado praticamente determinístico, mas o LLM não é 100% determinístico; a verificação de concordância entre configurações (no benchmark) mede isso em vez de supor.

## Prós e contras das opções descartadas

### Agrupar várias respostas por chamada (*batch prompting*)

* Bom, porque: menos chamadas, menos tokens de instrução repetidos, menor custo e latência ainda menor.
* Ruim, porque: muda o prompt e o formato de saída (mais frágil de ler), mistura respostas de pessoas diferentes no mesmo contexto (a qualidade precisaria ser reavaliada) e dificulta atribuir erro a uma resposta. **Fica como próximo experimento**, com avaliação de qualidade própria.

### Embeddings + clustering

* Bom, porque: mais barato e estável que pedir o tema ao LLM; é a ideia do autor original.
* Ruim, porque: traz numpy/scikit e uma nova etapa para avaliar; muda a forma de nomear temas. Outro experimento, não uma otimização transparente.

### Cache externo (Redis, Postgres)

* Bom, porque: sobrevive a reinícios e funciona entre instâncias.
* Ruim, porque: novo serviço, nova conta, novo segredo e uma nova superfície de LGPD (um repositório compartilhado de dados derivados de respostas), sem necessidade comprovada no piloto.

### Fallback para um segundo provedor

* Bom, porque: ganha disponibilidade.
* Ruim, porque: não reduz a latência de um provedor que está funcionando, dobra o contrato e a transferência internacional (outro suboperador no exterior) e exige validar a qualidade em dois modelos.

### Manter como está

* Ruim, porque: viola o limite de latência definido para o produto (p95 de 30 s) e mantém o custo de reanálise.
