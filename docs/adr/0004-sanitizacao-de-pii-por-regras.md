# ADR-004: Sanitizar PII com regras e léxico locais, com trava final, em vez de NER ou de depender só do contrato

* Status: aceita
* Data: 2026-10-19

## Contexto e problema

O `BRIEFING.md` é categórico: "nenhum dado identificável pode entrar em prompt sem anonimização". No protótipo, as respostas abertas iam **cruas** para o provedor de IA, com nomes de gestores e colegas dentro (o aviso amarelo "que ninguém lê" era a única barreira). O risco específico deste produto é justamente o **nome de pessoa no texto livre** (e o resto: CPF, e-mail, telefone), enviado a um provedor **fora do Brasil**.

Era preciso decidir **como** tratar, sabendo que nenhuma técnica acerta 100% e que a escolha tem custo de dependência, de falso positivo (trocar "Slack" por pessoa piora a classificação) e de latência.

## Motivadores da decisão

* Tratar **antes** de qualquer chamada, em todos os caminhos de código.
* Medir: "número sem evidência não conta" (enunciado). Precisa de conjunto rotulado e métrica reproduzível.
* Não mandar o dado pessoal para outra parte só para limpá-lo (descarta redação feita por LLM).
* Peso de implantação: o Render gratuito tem 512 MB, build lento e o projeto já teve incidente por dependência transitiva.
* Falso positivo custa qualidade (ferramentas, lugares e empresas devem sobreviver).

## Opções consideradas

* **Regras + léxico de nomes + pistas de contexto + trava final** (escolhida)
* NER do spaCy (`pt_core_news_sm`)
* Regras + NER do spaCy
* Microsoft Presidio
* Pedir ao próprio LLM para mascarar
* Não sanitizar e depender de DPA e de aviso na tela

## Resultado da decisão

Opção escolhida: **regras e léxico locais (`feedbackloop/pii.py`)**, em camadas: (1) mascaramento por regex com validação (CPF com dígito verificador, anos que não viram telefone) e por nome (léxico de nomes comuns, cargo ou título antes do nome, sobrenome comum depois de um nome capitalizado, exceção para lugares como "São Paulo"); (2) **trava final** no cliente do provedor, que **bloqueia** o envio se ainda restar PII reconhecível; (3) o resumo executivo só recebe **agregados**, nunca texto de resposta.

Evidência (mesmo conjunto rotulado de 88 textos, `tests/data/pii_avaliacao.jsonl`; [relatório](../lgpd/avaliacao-sanitizacao-pii.md); experimento em [`scripts/experimento_ner_spacy.py`](../../scripts/experimento_ner_spacy.py), resultado em [`evidencias/ner-spacy-vs-regras.json`](evidencias/ner-spacy-vs-regras.json)):

| Abordagem | Recall geral | Termos legítimos preservados | Tempo por texto | Dependência |
|---|---:|---:|---:|---|
| **Regras (escolhida)** | **87,5%** | **95,9%** | 0,06 ms | nenhuma |
| Só NER spaCy | 42,5% | 95,9% | 3,8 ms | spaCy + modelo |
| Regras + NER | 92,5% | 91,8% | 3,9 ms | spaCy + modelo |

### Consequências positivas

* Cobre 100% das categorias a que se compromete (nomes comuns, nome após cargo/título, nome + sobrenome comum, e-mail, CPF, telefone, @usuário, matrícula/RG/CEP/CNPJ) sem nenhuma dependência nova e em microssegundos.
* **Mascara de forma consistente** (`[PESSOA_1]` é a mesma pessoa no mesmo texto), preservando o sentido para a classificação.
* Testes provam que **nenhum prompt** enviado ao provedor contém os nomes do CSV de exemplo e que a mascaração é idempotente.

### Consequências negativas e trade-offs aceitos

* **Recall de 87,5% no conjunto total**: nomes raros sem pista de contexto e nomes em minúsculas passam (**0 de 9** nesses casos). Por isso a saída continua tratada como dado pessoal e há [documentação de transferência internacional](../lgpd/transferencia-internacional.md).
* **Falso positivo conhecido**: palavras que também são nomes no início de frase ("Marcos importantes do projeto") viram `[PESSOA_1]`. Medido, aceito: errar para o lado da privacidade.
* **Identificação indireta** ("a única gerente do financeiro de Joinville") não é coberta por nenhuma regra nem por NER.
* O conjunto de avaliação é sintético, pequeno e escrito pelo autor das regras: serve para detectar regressão e dimensionar limites, não para prometer desempenho em dados reais.

## Prós e contras das opções descartadas

### NER do spaCy (sozinho ou somado às regras)

* Bom, porque: pega alguns nomes sem pista de contexto e alguns em minúsculas (+5 pontos de recall somado às regras).
* Ruim, porque: sozinho é **pior** que as regras (42,5%; não pega e-mail nem CPF e erra nomes comuns); somado às regras, ganha 5 pontos de recall mas **perde 4 de preservação** (passa a trocar termos legítimos) e traz dependência pesada (build, memória, risco de nova quebra por transitiva). **Reavaliar** se um cliente exigir recall maior; fica como opção documentada.

### Microsoft Presidio

* Bom, porque: framework maduro com reconhecedores prontos.
* Ruim, porque: por baixo usa spaCy (mesmos custos), com configuração extra e suporte a português mais limitado do que o que as regras já cobrem.

### Pedir ao LLM para mascarar

* Ruim, porque: **envia o dado pessoal ao provedor para limpá-lo**, que é exatamente o que se quer evitar; além de custo, latência e resultado não determinístico.

### Não sanitizar (só DPA e aviso na tela)

* Ruim, porque: contraria o requisito do briefing e a rubrica ("PII indo crua para o LLM" zera o critério). Contrato reduz risco jurídico, não a exposição.
