# ⚠️ AVISO — Dados sintéticos

Todas as respostas em `respostas-pesquisa-exemplo.csv` são **100% fictícias**,
geradas para fins de demonstração e teste do protótipo FeedbackLoop.

- **Nenhuma** resposta veio de uma pesquisa de clima real.
- **Nenhum** funcionário real está representado aqui.
- Os **nomes de pessoas** que aparecem em algumas respostas (Marcos Antunes,
  Carolina Mendes, João Pereira, Fernanda Lima) são **inventados** e foram
  incluídos **de propósito** para servir de material didático sobre LGPD.

## Por que tem nomes no meio do texto?

Porque é exatamente isso que acontece numa pesquisa de clima de verdade: a
pessoa que responde cita o nome do gestor, de um colega, de quem saiu. Esse é
o cenário que o time precisa aprender a tratar.

> No protótipo atual esses nomes vão **crus** para o provedor de IA, sem nenhuma
> anonimização. Isso é uma **dívida técnica plantada** (ver README → "Dívida
> técnica herdada", item LGPD). **Não é assim que deve ficar em produção.**

## Se você for substituir por dados reais

1. **Não** suba respostas reais identificáveis sem anonimizar antes.
2. Garanta base legal e finalidade definida (LGPD, art. 7º e art. 6º).
3. Confirme o tratamento com a área de Privacidade/DPO antes.

— Rafael (início deste ano)
