# Post-mortem — 21/09/2026

**Serviço:** `feedbackloop-prod` (produção)
**Duração do impacto (horário de Brasília):** bug de dependência — desde o primeiro deploy até 09:42; regressão simulada — 09:47 a 09:54 (7 min) e uma recorrência de ~12 min (≈09:58 a ≈10:10, estimada a partir dos pushes e do deploy da correção)
**Severidade:** baixa (piloto sem usuários externos ainda; funcionalidade de análise indisponível para quem clicasse em "Analisar respostas")

Este documento cobre dois problemas do mesmo dia: um **incidente real**, descoberto sem querer ao testar o primeiro deploy, e uma **regressão simulada de propósito**, usada para exercitar rollback. Nenhum dos dois teve origem em erro de uma pessoa específica — o objetivo aqui é entender causa e melhorar o processo, não apontar culpado.

## Linha do tempo

Fontes: horários de commit (`git log`) e histórico de deploys do Render (print em [`docs/incidente-2026-09-21/evidencia-rollback-render.png`](incidente-2026-09-21/evidencia-rollback-render.png)). Horários marcados como *estimado* não têm registro exato e foram inferidos dos eventos vizinhos.

| Hora (BRT) | Evento | Fonte |
|---|---|---|
| 09:35 | Commit `3a9a2c5`: nova funcionalidade (slider de quantidade de temas) com a variável definida *depois* do bloco que a usa. CI passa e o deploy sobe. | commit |
| 09:35–09:41 | Ao testar o botão "Analisar respostas" em produção, aparece um erro **sem relação com a funcionalidade nova**: `TypeError: Client.__init__() got an unexpected keyword argument 'proxies'`, dentro de `feedbackloop/llm.py`. Diagnóstico: `httpx` (dependência transitiva do SDK da OpenAI) não estava fixado e o Render instalou uma versão incompatível com `openai==1.50.0`. **Provavelmente existia desde o primeiro deploy**, porque nenhum smoke test construía o cliente de verdade. | observação manual (hora exata não registrada) |
| 09:41–09:42 | Commit `cdc9211` corrige os dois problemas (fixa `httpx==0.27.2`, move o slider para antes do botão e adiciona teste de regressão que constrói o `ClienteLLM()`). Deploy live às 09:42. | commit + Render |
| após 09:42 | Em produção o erro muda de `TypeError` para `RateLimitError: insufficient_quota` (conta da OpenAI sem créditos). Isso prova que o código passou a alcançar a API; o problema restante era de billing, não de código. | observação manual (hora exata não registrada) |
| 09:46–09:47 | **Regressão simulada de propósito** (exercício de rollback da Etapa 1): commit `0424cff` ("refactor") move o slider de volta para depois do botão. CI passa (nenhum teste clica no botão). Deploy live às 09:47. | commit + Render |
| 09:50–09:51 | Bug reproduzido em produção (`UnboundLocalError: cannot access local variable 'quantidade_temas'`). Evidência em [`docs/incidente-2026-09-21/evidencia-erro-producao.txt`](incidente-2026-09-21/evidencia-erro-producao.txt). Commit `d2cac5d` (só documentação) também faz deploy. | commit + Render |
| 09:53–09:54 | **Rollback** no painel do Render, do deploy `0424cff` de volta para o `cdc9211`. Live às 09:54. Em produção o erro volta a ser o de billing, não mais o `UnboundLocalError`. | Render |
| 09:57 | Commits `b706332` e `1506a4b` (post-mortem e preparação da release) empurrados para `main`. Cada push dispara o CI/CD, que reimplanta o **HEAD da branch** — e o HEAD ainda continha o bug do `0424cff`. **O rollback foi desfeito sozinho.** Deploy da recorrência: ≈09:58 (*estimado*). | commits |
| entre 09:58 e 10:08 | A pessoa que testa o app em produção reporta o mesmo `UnboundLocalError` (print enviado). Hora exata do relato não registrada. | relato do usuário |
| 10:08 | Commit `6baf705` corrige a ordenação do slider **no código**, não só na infraestrutura. Deploy da correção: ≈10:10 (*estimado*); durante a troca de instância o serviço respondeu 502 por alguns segundos. | commit |
| 10:09 | Commit `161d144` registra neste post-mortem a lição "rollback de infra não substitui correção no código". | commit |
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
- **Rollback de infraestrutura não é a mesma coisa que corrigir o código.** O rollback no Render reverteu o *deploy ativo*, mas o commit com o bug (`0424cff`) continuou sendo o HEAD de `main`. O próximo push disparou o CI/CD normalmente, que reimplantou esse HEAD — e o bug voltou sozinho, sem ninguém reintroduzi-lo de propósito. Um rollback só é duradouro se for acompanhado (na hora, ou logo em seguida) de um commit que corrige o problema na fonte — senão ele sobrevive só até o próximo deploy automático.

## Ações de acompanhamento

| Ação | Status |
|---|---|
| Fixar `httpx==0.27.2` no `requirements.txt` | ✅ Feito (commit `cdc9211`) |
| Adicionar teste que constrói `ClienteLLM()` sem chamada de rede | ✅ Feito (commit `cdc9211`) |
| Corrigir a ordenação do slider na fonte (não só via rollback de infra) | ✅ Feito (commit `6baf705`) |
| Adicionar créditos/billing na conta da OpenAI usada em produção | ⬜ Pendente — ação fora do código, precisa ser feita na conta da OpenAI |
| Adicionar um smoke test que simule o clique em "Analisar respostas" com um `ClienteLLM` mockado via injeção de dependência | ⬜ Backlog — exige pequeno refactor em `app.py` para permitir injetar o cliente (hoje ele é instanciado direto dentro de `main()`); registrado para a próxima etapa |
| Revisar o `requirements.txt` por outras dependências transitivas sensíveis não fixadas | ⬜ Backlog |
