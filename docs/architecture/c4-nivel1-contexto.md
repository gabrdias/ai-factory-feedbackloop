# C4 — Nível 1: Diagrama de Contexto

Mostra o sistema FeedbackLoop na sua fronteira mais ampla: quem usa e com quem ele conversa fora dela.

```mermaid
flowchart TD
    Analista["👤 Analista de RH<br/><i>Pessoa</i><br/>Colaborador da área de RH de uma<br/>empresa cliente da FeedbackLoop"]

    Sistema["📊 FeedbackLoop — Survey Insights<br/><i>Sistema de Software</i><br/>Agrupa respostas abertas de pesquisas de<br/>clima por tema, classifica sentimento e<br/>gera um resumo executivo com ações"]

    OpenAI["🤖 OpenAI API<br/><i>Sistema Externo</i><br/>Serviço de LLM (Chat Completions)<br/>usado para classificação e geração de texto"]

    Analista -- "Envia respostas (texto colado, CSV ou<br/>dados de exemplo) e lê o resumo executivo<br/>[HTTPS]" --> Sistema
    Sistema -- "Classifica cada resposta e solicita o<br/>resumo executivo<br/>[HTTPS / REST, Chat Completions API]" --> OpenAI

    style Sistema fill:#1168bd,color:#ffffff,stroke:#0b4884
    style OpenAI fill:#999999,color:#ffffff,stroke:#6b6b6b
    style Analista fill:#08427b,color:#ffffff,stroke:#052c52
```

## Elementos

| Elemento | Tipo | Descrição |
|---|---|---|
| Analista de RH | Pessoa | Usuário final. Acessa a URL pública pelo navegador; não precisa de conta nem instalação local. |
| FeedbackLoop — Survey Insights | Sistema de software (o sistema em construção) | Aplicação web que recebe respostas abertas e devolve um resumo executivo com temas, sentimento e ações recomendadas. |
| OpenAI API | Sistema externo | Único sistema externo do qual o FeedbackLoop depende para funcionar. Recebe o texto das respostas — ver [auditoria](../auditoria-prototipo.md) sobre a lacuna de anonimização antes do envio. |

## Fora do diagrama, por decisão consciente

Não há sistema de autenticação, banco de dados externo, fila de mensagens ou sistema de billing nesta versão — o protótipo é intencionalmente de sessão única, sem persistência (ver [auditoria do protótipo](../auditoria-prototipo.md), seção 2.5). O diagrama reflete o sistema real, não um estado futuro aspiracional.
