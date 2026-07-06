# Notas soltas — Rafael

Coisas que ficaram no meio do caminho. Quem pegar, lê antes de mexer:

- O **prompt de classificação** é genérico demais. Às vezes o modelo inventa
  tema novo pra cada resposta e a agregação fica pulverizada (30 respostas, 25
  temas). A ideia era fixar uma taxonomia de ~10 temas e pedir pro LLM escolher
  dentro dela. Não fiz. Fica a dica.

- **Custo**: o pipeline faz 1 chamada por resposta + 1 do resumo. Rodei a
  planilha de 36 respostas umas 15 vezes testando e deu uns US$ 0,40 no total
  com um modelo GPT pequeno da OpenAI. Parece pouco, mas sem cache, numa pesquisa de 2.000 pessoas
  rodada várias vezes, a conta sobe rápido. Recalcular antes de escalar.

- Pensei em usar **embeddings + clustering** (k-means) pra agrupar temas em vez
  de pedir o tema pro LLM. Seria mais barato e mais estável, mas dá mais
  trabalho e ia puxar numpy/scikit. Deixei LLM-based mesmo pra MVP.

- **Anonimização**: o certo era passar um regex de nomes / um NER antes de
  mandar pro provedor. Cheguei a rascunhar com `spacy` mas não terminei. Hoje
  vai tudo cru. Combinar com a Bia (e com jurídico) ANTES de subir dado real.

- **Avaliação**: não tenho como saber se o resumo tá bom. Não montei nenhum
  conjunto de validação nem rubrica. "Pareceu razoável na tela" não é métrica.

- **Deploy**: Streamlit Cloud resolve pro piloto, só cuidar do segredo da
  OPENAI_API_KEY (não commitar .env, óbvio). HF Spaces também serve.

- O `COLUNA_RESPOSTA` tá hardcoded como "resposta" no app.py. Se o RH mandar a
  planilha com a coluna chamada "comentario", quebra. Já aconteceu comigo.

Foi muito bom trabalhar aqui. Qualquer coisa, meu contato pessoal a Bia tem.

— Rafael (início deste ano) 👋
