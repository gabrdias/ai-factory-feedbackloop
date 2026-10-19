# Avaliação da sanitização de PII

Gerado por `python scripts/avaliar_pii.py --gravar` em 2026-10-19 sobre 88 textos rotulados em `tests/data/pii_avaliacao.jsonl`.

**Como ler.** *Recall* = fração dos dados pessoais anotados que **não sobram** na saída (um nome composto só conta como removido se nenhuma parte relevante sobrar). *Preservação* = fração dos termos legítimos (ferramentas, lugares, empresas) que **continuam** na saída.

| Categoria | Itens | Recall | Preservação | Itens sem falha |
|---|---:|---:|---:|---:|
| Nome comum (no léxico), completo ou só o primeiro | 14 | 100.0% | — | 14/14 |
| Nome fora do léxico, com cargo/título antes (ex.: "gerente Wanderley") | 8 | 100.0% | 100.0% | 8/8 |
| Nome fora do léxico + sobrenome comum | 5 | 100.0% | — | 5/5 |
| E-mail | 5 | 100.0% | 100.0% | 5/5 |
| CPF (formatado ou só dígitos válidos) | 4 | 100.0% | 100.0% | 4/4 |
| Telefone (com/sem DDD, +55) | 6 | 100.0% | 100.0% | 6/6 |
| @usuário | 3 | 100.0% | 100.0% | 3/3 |
| Matrícula, RG, CEP, CNPJ, crachá, registro | 6 | 100.0% | 100.0% | 6/6 |
| Vários tipos no mesmo texto | 4 | 100.0% | 100.0% | 4/4 |
| Sem PII, com ferramentas/lugares/empresas que NÃO podem ser trocados | 22 | — | 100.0% | 22/22 |
| Nome raro sem nenhuma pista de contexto (lacuna conhecida) | 5 | 0.0% | — | 0/5 |
| Nome escrito em minúsculas (lacuna conhecida) | 4 | 0.0% | — | 0/4 |
| Palavra que também é nome (ex.: "Marcos importantes"; falso positivo esperado) | 2 | — | 0.0% | 0/2 |

- **Recall nas categorias que a regra se compromete a cobrir:** 100.0%
- **Recall geral (incluindo lacunas conhecidas):** 87.5%
- **Preservação de termos legítimos (geral):** 95.9%

## Falhas observadas

| # | Categoria | O que aconteceu | Saída |
|---:|---|---|---|
| 28 | nome_sem_pista | sobrou: `Ozanir` | Ontem a Ozanir me disse que o orçamento foi cortado. |
| 29 | nome_sem_pista | sobrou: `Genivaldo` | Cobraram isso do Genivaldo na reunião e ele ficou sem reação. |
| 30 | nome_sem_pista | sobrou: `Ubiratan` | Quem decide tudo é o Ubiratan, o resto do time só executa. |
| 31 | nome_sem_pista | sobrou: `Zuleide`, `Eronildes` | Zuleide e Eronildes combinaram tudo por fora, sem avisar o time. |
| 32 | nome_sem_pista | sobrou: `Gessica` | Falei com a Gessica e ela confirmou o atraso. |
| 33 | nome_minusculo | sobrou: `marcos antunes` | o gerente marcos antunes muda tudo toda semana |
| 34 | nome_minusculo | sobrou: `carolina mendes` | falei com a carolina mendes e ela concordou |
| 35 | nome_minusculo | sobrou: `joão pereira` | joão pereira é o único que escuta o time |
| 36 | nome_minusculo | sobrou: `ricardo alves` | ricardo alves não responde ninguém |
| 83 | negativo_ambiguo | trocou termo legítimo: `Marcos importantes` | [PESSOA_1] importantes do projeto foram esquecidos pela liderança. |
| 84 | negativo_ambiguo | trocou termo legítimo: `Clara demais` | [PESSOA_1] demais a diferença de tratamento entre as áreas. |

## Como interpretar com honestidade

- O léxico de nomes é genérico e **não** inclui os nomes de `nome_gatilho`, `nome_sobrenome`, `nome_sem_pista` e `nome_minusculo`; essas categorias medem generalização de verdade.
- A lista de sobrenomes comuns contém os sobrenomes usados em `nome_sobrenome`; essa categoria mede a regra "nome desconhecido + sobrenome comum", não sobrenomes raros.
- O conjunto foi escrito pelo próprio autor da regra (antes das regras), tem poucos itens por categoria e é sintético. Serve para detectar regressões e dimensionar limites, não para garantir desempenho em dados reais de clientes.
- Identificação **indireta** ("a única gerente do financeiro de Joinville") não é coberta por nenhuma regra: por isso a saída continua sendo tratada como dado pessoal (ver `docs/lgpd/mapa-de-dados-pessoais.md`).
