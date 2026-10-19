# Transferência internacional de dados (LGPD, arts. 33 a 36)

> Documentação técnica; **não é parecer jurídico**. Os pontos marcados como **pendência** precisam de confirmação do jurídico ou do Encarregado antes de qualquer dado real.

**A dica do enunciado vale integralmente aqui:** toda chamada de LLM é transferência internacional (OpenAI, Anthropic e Google processam fora do Brasil). Mas há mais de um trecho em que o dado atravessa a fronteira, e a sanitização não protege todos.

## 1. Por onde o dado passa

```
Navegador do analista de RH  ──(TLS)──▶  App no Render  ──(TLS, texto JÁ mascarado)──▶  OpenAI
     (Brasil)                         (região do serviço)                                  (EUA)
                                              │
                                              └──(TLS, só contagens e durações)──▶  Grafana Cloud
                                                                                    (São Paulo, sa-east-1)
```

| # | Trecho | O que viaja | Destino | Atravessa a fronteira? |
|---|---|---|---|---|
| T1 | Navegador → app no **Render** | **Texto original**, antes do mascaramento (a sanitização acontece **dentro** do app) | Servidor do Render, na região do serviço | **Sim**, se a região for fora do Brasil (o Render não oferece região no Brasil entre as que usamos: ver pendência T-1) |
| T2 | App → **OpenAI** | Texto **já mascarado** (nomes, e-mail, CPF, telefone trocados por marcadores) | EUA | **Sim** |
| T3 | App → **Grafana Cloud** | Contagens, durações, tokens, tipos de PII mascarados. **Nenhum texto nem dado pessoal** | São Paulo (`prod-sa-east-1`) | **Não** para fins de dado pessoal: a telemetria não contém dado pessoal e fica em território nacional |

**Consequência importante, descoberta ao documentar:** a máscara protege **T2**, mas **não T1**. O texto original chega à memória do servidor no exterior antes de ser mascarado. Isso não é um defeito de implementação: com Streamlit a lógica roda no servidor. As medidas abaixo reduzem o risco de T1; só um host no Brasil ou mascaramento no navegador o eliminam (ver seção 5).

## 2. Fundamento legal (art. 33)

A LGPD só permite a transferência internacional em hipóteses taxativas. Para este produto, a hipótese cabível é o **art. 33, II: garantias de cumprimento dos princípios e dos direitos do titular, oferecidas e comprovadas pelo controlador**, por meio de **cláusulas contratuais** (específicas ou **cláusulas-padrão**), normas corporativas globais ou selos/certificações. A ANPD regulamentou as cláusulas-padrão contratuais na Resolução CD/ANPD nº 19/2024 (conferir o texto vigente com o jurídico). **Consentimento específico (art. 33, VIII) não é a base adotada**, pelo mesmo motivo do mapa de dados: numa relação de trabalho ele dificilmente é livre.

Papéis: a **controladora** é o cliente (o RH que aplica a pesquisa) e é dela a obrigação de comprovar as garantias; a FeedbackLoop, como **operadora**, deve (a) usar suboperadores com contrato que ofereça as garantias, (b) informar ao cliente quem são e onde processam, e (c) aplicar as medidas técnicas.

## 3. Lista de suboperadores (informar ao cliente)

| Suboperador | Função | País de processamento | Dados | Contrato / garantia (art. 33, II) | Status |
|---|---|---|---|---|---|
| **OpenAI** | Classificar e resumir | EUA | Texto mascarado | DPA do provedor; verificar se incorpora as cláusulas-padrão da ANPD e os termos de retenção/não treinamento da API vigentes | **Pendência T-2** |
| **Render** | Hospedar o app | Região do serviço (confirmar) | Texto original em memória, IP de quem acessa | DPA do Render | **Pendência T-1** |
| **Grafana Labs** (Grafana Cloud) | Telemetria | Brasil (`sa-east-1`) | Sem dado pessoal | Termos do serviço; sem dado pessoal, a exigência é mínima | OK para o piloto |
| **GitHub** | Código e CI | EUA | Nenhum dado de respondente (só código e dados sintéticos) | n/a | Fora do escopo |

## 4. Medidas técnicas aplicadas (o que reduz o risco enquanto o contrato não está fechado)

1. **Minimização antes da saída:** sanitização antes de toda chamada ao provedor, mais trava final que bloqueia se restar PII reconhecível. Medida: 100% nas categorias cobertas e 87,5% no total ([avaliação](avaliacao-sanitizacao-pii.md)).
2. **O resumo só leva agregados:** o segundo prompt nunca contém texto de resposta.
3. **Nada persiste no Render:** o texto original vive só na memória da sessão; o cache guarda hash do texto **já mascarado** e o resultado, nunca texto ([retenção](politica-de-retencao-e-exclusao.md)).
4. **TLS** em todos os trechos; nenhum dado em URL; sem cookies próprios e com a telemetria do Streamlit desligada.
5. **Telemetria sem conteúdo**, verificada por teste automatizado.
6. **Dados sintéticos em todos os ambientes** desta etapa.

## 5. Decisão, pendências e alternativas

**Decisão registrada:** o piloto usa **somente dados sintéticos** até as pendências T-1 e T-2 estarem fechadas. Para dado real de cliente, a transferência exige, antes: DPA/cláusulas-padrão assinadas com OpenAI e Render, região e retenção confirmadas por escrito e parecer do jurídico.

| # | Pendência | Como fechar |
|---|---|---|
| T-1 | Confirmar a **região do serviço no Render** (Settings → Region) e o DPA do Render | Anotar a região aqui; se estiver nos EUA ou na Europa, T1 é transferência e precisa de garantia contratual |
| T-2 | Confirmar no DPA da OpenAI: retenção dos dados da API, não uso para treino e cláusulas-padrão da ANPD | Jurídico / Encarregado |
| T-3 | Avaliar hospedagem **no Brasil** ou mascaramento **no navegador** para eliminar T1 | Decisão de arquitetura (futura ADR); o custo é reescrever a camada web, fora do escopo desta etapa |

**Alternativas já aprovadas no briefing:** Anthropic e Google também processam fora do Brasil, então trocar de provedor não elimina T2; só muda o contrato. A troca é barata de implementar (o cliente do provedor está isolado em [`feedbackloop/llm.py`](../../feedbackloop/llm.py)).
