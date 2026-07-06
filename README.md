# FeedbackLoop — Survey Insights

Oi! Aqui é o Rafael. Esse é o app que a gente usa pra analisar as **respostas
abertas** das pesquisas de clima — aquelas perguntas de texto livre tipo "o que
você mudaria na empresa?". O RH colava tudo numa planilha e lia uma por uma na
mão. Doía. Esse protótipo faz o trabalho pesado:

1. **agrupa por tema** (carga de trabalho, liderança, salário, etc.)
2. **marca o sentimento** de cada resposta (positivo / neutro / negativo)
3. **gera um resumo executivo** com os principais temas + ações recomendadas

É análise **em lote**, não é chatbot. Você joga 40 respostas, ele cospe um
relatório. Só isso.

## Como rodar

1. Clona o repo
2. Instala as deps: `pip install -r requirements.txt` (tem streamlit, openai,
   pandas, python-dotenv e pytest)
3. Cria um `.env` com a chave da OpenAI (copia do `.env.example`)
4. `streamlit run app.py`
5. Abre no browser, escolhe "Usar dados de exemplo" e clica em **Analisar**.

Pra rodar os testes (esses **não** chamam a API, pode rodar à vontade):

```
pytest -q
```

## Como o código tá organizado

- `app.py` — só a UI do Streamlit (entrada de dados + exibição)
- `feedbackloop/llm.py` — interface fina com o LLM. É **mockável** de propósito:
  o resto do código só conhece o método `.completar()`. Nos testes a gente passa
  um cliente fake.
- `feedbackloop/pipeline.py` — o coração: classificação, agregação e resumo.
  Separei as funções puras (parse/contagem/resumo) das que chamam o LLM.
- `data/` — 36 respostas sintéticas de exemplo. **Leia o
  `data/AVISO-DADOS-SINTETICOS.md`.**
- `tests/` — pytest, tudo offline.

## Sobre os dados

Os exemplos em `data/respostas-pesquisa-exemplo.csv` são **inventados**. Botei
**nomes fake de gente** no meio de algumas respostas DE PROPÓSITO (tipo "o
gerente Marcos Antunes muda tudo toda semana"), porque é o que acontece de
verdade numa pesquisa — e porque vocês vão precisar lidar com isso (ver dívida
técnica de LGPD lá embaixo).

## Observações

- Usei um modelo GPT pequeno da OpenAI porque é barato. Dá pra trocar pro Claude
  (um modelo Haiku da Anthropic, pequeno e rápido) — deixei o esqueleto comentado no `feedbackloop/llm.py`.
- O modelo tá **hardcoded** no código. Tem uma linha no `.env.example` pra isso
  mas ela ainda não faz nada (me julguem).
- Anotações mais cruas minhas tão em `docs/notas-rafael.md`.

## Dívida técnica herdada

Não joga fora, **refatora**. Eu sei que tem buraco. Tá tudo aqui, de propósito,
documentado pra vocês atacarem:

1. **LGPD — nomes não anonimizados.** As respostas vão **cruas** pro provedor de
   IA, com nomes de pessoas e queixas identificáveis dentro. Não tem NER, não tem
   regex, não tem nada. O app só mostra um aviso amarelo (que ninguém lê). Isso
   precisa de anonimização ANTES do prompt. Falar com a Bia e com jurídico.
2. **Sem persistência.** Fechou a aba, perdeu a análise. Nada é salvo — nem o
   resultado, nem histórico. Não dá pra comparar a pesquisa deste trimestre com
   a do anterior.
3. **Sem cache — reanalisa tudo toda vez (= custo).** Cada clique em "Analisar"
   refaz 1 chamada de LLM por resposta + 1 do resumo. Mesma planilha clicada
   duas vezes = paga duas vezes. Não tem memoização nem hash do input.
4. **Sem deploy / sem CI.** Roda só na máquina local. Não tem pipeline, não tem
   Docker, não tem GitHub Actions rodando os testes.
5. **Sem observabilidade.** Nenhum log, nenhuma métrica, nenhum rastro de quanto
   custou cada análise ou quanto tempo levou. Quando der ruim, boa sorte
   descobrindo o porquê.
6. **Qualidade do resumo não é avaliada.** Não tem conjunto de validação, nem
   rubrica, nem teste de regressão de prompt. A gente não sabe se o resumo está
   bom — só "pareceu ok na tela". O modelo também tende a inventar tema novo pra
   cada resposta, pulverizando a agregação (sem taxonomia fixa).

(Os testes em `tests/` cobrem a **lógica** — parsing, contagem, montagem do
resumo e o fluxo ponta a ponta com LLM mockado. Eles **não** avaliam a
qualidade do conteúdo gerado pelo modelo. Isso é o item 6.)

Qualquer dúvida, a Bia tem meu contato.

— Rafael (início deste ano)
