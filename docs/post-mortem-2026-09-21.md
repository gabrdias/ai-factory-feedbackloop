# Post-mortem — 21/09/2026

**Serviço:** `feedbackloop-prod` (produção)
**Duração total de impacto:** ~17 minutos (09:37–09:54, horário de Brasília)
**Severidade:** baixa (piloto sem usuários externos ainda; funcionalidade de análise indisponível para quem clicasse em "Analisar respostas")

Este documento cobre dois problemas do mesmo dia: um **incidente real**, descoberto sem querer ao testar o primeiro deploy, e uma **regressão simulada de propósito**, usada para exercitar rollback. Nenhum dos dois teve origem em erro de uma pessoa específica — o objetivo aqui é entender causa e melhorar o processo, não apontar culpado.

## Linha do tempo

| Hora (BRT) | Evento |
|---|---|
| ~09:37 | Deploy de uma nova funcionalidade (slider de quantidade de temas) em produção. CI passou normalmente. |
| ~09:40 | Ao testar manualmente o botão "Analisar respostas", encontrado um erro **não relacionado à funcionalidade nova**: `TypeError: Client.__init__() got an unexpected keyword argument 'proxies'`, dentro de `feedbackloop/llm.py`. |
| 09:41 | Diagnóstico: `httpx` (dependência transitiva do SDK da OpenAI) não estava fixado no `requirements.txt`. O Render instalou uma versão do `httpx` incompatível com `openai==1.50.0`. **Esse bug provavelmente estava em produção desde o primeiro deploy**, sem nenhum smoke test capaz de detectá-lo. |
| 09:42 | Deploy da correção: `httpx==0.27.2` fixado, mais a correção da ordem do slider (definido antes do bloco do botão) e um novo teste de regressão que constrói o `ClienteLLM()` sem chamar a rede. |
| 09:43 | Confirmado em produção: o erro mudou de `TypeError` (bug de dependência) para `RateLimitError: insufficient_quota` — prova de que o código passou a alcançar a API de verdade. A causa desse segundo erro é a conta da OpenAI sem créditos, não é um bug de código (ver "Ações de acompanhamento"). |
| 09:46 | **Regressão simulada de propósito**, como exercício de rollback da Etapa 1: um commit de "refactor" reintroduz só o problema de ordenação do slider (`quantidade_temas` definido depois do bloco que o usa). CI passa normalmente — nenhum smoke test clica no botão "Analisar". |
| 09:47 | Deploy do commit com a regressão sobe ao ar. |
| ~09:50 | Bug reproduzido manualmente em produção: `UnboundLocalError: cannot access local variable 'quantidade_temas'`. Evidência salva em [`docs/incidente-2026-09-21/evidencia-erro-producao.txt`](incidente-2026-09-21/evidencia-erro-producao.txt). |
| 09:53 | Rollback executado no painel do Render, do deploy do commit `0424cff` de volta para o `cdc9211` (o último deploy saudável). Evidência: [`docs/incidente-2026-09-21/evidencia-rollback-render.png`](incidente-2026-09-21/evidencia-rollback-render.png). |
| 09:54 | Confirmado em produção: o erro voltou a ser `RateLimitError` (esperado, de billing), não mais `UnboundLocalError` — rollback bem-sucedido. |

## Impacto

Durante as janelas acima, qualquer pessoa que clicasse em "Analisar respostas" em produção via um erro em vez do resumo executivo. Como o piloto ainda não tem usuários externos reais, o impacto prático foi zero — mas o cenário é exatamente o que aconteceria com um cliente-piloto de verdade.

## Causa raiz

**Incidente real (dependência):** o `requirements.txt` herdado do protótipo fixava só as dependências diretas (`streamlit`, `openai`, `pandas`, `python-dotenv`, `pytest`), não as transitivas. Uma atualização do `httpx` (usado internamente pelo SDK da OpenAI) removeu um parâmetro que `openai==1.50.0` ainda esperava poder passar. Isso nunca foi pego porque **nenhum dos smoke tests originais chegava a construir o `ClienteLLM()`** — o smoke test 1 não clica no botão de análise (evitar chamada de API real no CI), e o smoke test 2 chama o pipeline diretamente, sem passar pelo cliente real.

**Regressão simulada:** um commit de refactor moveu a definição do slider (`st.slider(...)`) para depois do bloco que já usa a variável — erro de ordenação de código clássico, que só se manifesta quando o botão é clicado com uma chave de API configurada (é exatamente o mesmo ponto cego dos smoke tests: nenhum deles clica no botão).

## O que funcionou bem

- O pipeline de CI/CD funcionou exatamente como desenhado: testes rodaram em segundos, o deploy só aconteceu depois de tudo verde, e o smoke test 3 confirmou a URL pública no ar após cada deploy.
- O Render manteve histórico de deploys navegável, com rollback de um clique — a recuperação em si levou menos de um minuto depois de identificado o deploy bom.
- A separação de ambientes (dev/prod com secrets diferentes) significou que nada disso afetou o ambiente de desenvolvimento.

## O que não funcionou / lições aprendidas

- **Nenhum smoke test exercitava o caminho real de "clicar em Analisar".** Os três smoke tests desta etapa cobrem: app sobe sem erro, pipeline processa CSV real, URL pública responde. Nenhum cobre "o botão principal do produto funciona de ponta a ponta". Isso deixou passar dois bugs diferentes no mesmo dia.
- **Dependências transitivas não fixadas são um risco real**, não só teórico — este incidente não foi hipotético, aconteceu de verdade no primeiro deploy.
- Um teste de regressão (`test_cliente_llm_constroi_sem_erro_de_dependencia`) foi adicionado depois do incidente real, mas **antes** da regressão simulada — e mesmo assim não pegou a regressão do slider, porque testa uma coisa diferente (construção do cliente, não o fluxo do botão). Isso confirma que cobertura de teste precisa ser pensada por *caminho de uso*, não só por função isolada.

## Ações de acompanhamento

| Ação | Status |
|---|---|
| Fixar `httpx==0.27.2` no `requirements.txt` | ✅ Feito (commit `cdc9211`) |
| Adicionar teste que constrói `ClienteLLM()` sem chamada de rede | ✅ Feito (commit `cdc9211`) |
| Adicionar créditos/billing na conta da OpenAI usada em produção | ⬜ Pendente — ação fora do código, precisa ser feita na conta da OpenAI |
| Adicionar um smoke test que simule o clique em "Analisar respostas" com um `ClienteLLM` mockado via injeção de dependência | ⬜ Backlog — exige pequeno refactor em `app.py` para permitir injetar o cliente (hoje ele é instanciado direto dentro de `main()`); registrado para a próxima etapa |
| Revisar o `requirements.txt` por outras dependências transitivas sensíveis não fixadas | ⬜ Backlog |
