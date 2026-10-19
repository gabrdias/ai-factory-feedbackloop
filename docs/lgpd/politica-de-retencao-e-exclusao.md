# Política de retenção e exclusão

Princípio: **guardar o mínimo, pelo menor tempo, e provar que apaga.** A LGPD manda eliminar os dados quando a finalidade é alcançada (arts. 15 e 16) e o `BRIEFING.md` fixa **90 dias como teto** para logs. Aqui, cada prazo tem um **mecanismo que o executa** e uma **evidência** que qualquer pessoa consegue reproduzir; prazo sem mecanismo não conta.

## 1. Prazos e mecanismos

| Dado | Onde fica | Prazo máximo | Mecanismo que executa | Como comprovar |
|---|---|---|---|---|
| Texto das respostas (original e mascarado) | Memória da sessão do Streamlit | Duração da sessão | **Arquitetura**: nenhum código grava o texto em disco, banco ou log | `test_o_texto_da_resposta_nunca_e_gravado_em_disco`; `test_nenhum_span_nem_log_contem_dado_pessoal` |
| Cache de classificações (hash + tema + sentimento) | SQLite no disco do serviço (`CACHE_DB_PATH`) | **30 dias** (`CACHE_TTL_DIAS`; o código aceita no máximo o que o operador configurar, padrão abaixo do teto de 90) | (1) `purgar_expirados()` ao iniciar o app e **a cada hora** numa thread ([`feedbackloop/cache.py`](../../feedbackloop/cache.py)); (2) entrada vencida é apagada ao ser lida; (3) **botão "Excluir cache agora"**; (4) disco efêmero do Render: todo deploy/reinício recomeça vazio | **Cenário reproduzível:** `python scripts/retencao.py demo` (abaixo); testes `test_cache.py`; evento `cache.purga` nos logs |
| Telemetria (traces e métricas) | Grafana Cloud | 14 dias (plano gratuito; confirmar na stack) | Retenção da plataforma; o conteúdo já nasce sem dado pessoal | Teste de privacidade da telemetria; captura da configuração da stack |
| Logs da aplicação | Render (stdout) | Definido pelo Render; **nunca acima de 90 dias** | Retenção da plataforma; conteúdo restrito a contagens | Mesmo teste de privacidade |
| Logs de acesso (IP) | Render | Definido pelo Render | Retenção da plataforma (a FeedbackLoop não trata) | Documentação da plataforma |

## 2. O mecanismo, em execução (cenário reproduzível)

```bash
python scripts/retencao.py demo
```

Saída real:

```
Cenário: prazo (TTL) de 30 dias; entradas gravadas há 95, 31 e 5 dias.
  entradas antes da purga ........ 3
  removidas pela purga ........... 2  (as de 95 e 31 dias)
  restantes ...................... 1  (a de 5 dias sobreviveu: True)
  removidas numa 2ª purga ........ 0  (idempotente)
  removidas pela limpeza total ... 1  -> sobram 0
RESULTADO: OK, retenção funcionando como documentado.
```

O cenário roda com relógio simulado num banco temporário (não toca no cache real) e também é um teste automatizado (`test_cenario_de_retencao_apaga_so_o_que_passou_do_prazo`), executado em todo push pelo CI.

Operação no cache real: `python scripts/retencao.py status | purgar | limpar`.

## 3. Exclusão sob demanda

- **Cache inteiro:** botão "Excluir cache agora" na barra lateral do app, ou `python scripts/retencao.py limpar --sim`. Registra o evento `cache.limpeza_total` (só a quantidade, nunca conteúdo).
- **Pedido de titular (art. 18):** a FeedbackLoop é operadora e encaminha ao controlador (o cliente) em até **2 dias úteis**. Não existe base de respondentes para consultar ou corrigir; o único dado que persiste é o cache, que não guarda texto e é apagável por completo.

## 4. Incidentes de segurança (art. 48)

1. **Detectar:** alerta da [observabilidade](../observabilidade/metricas-e-alertas.md), gitleaks no CI, relato.
2. **Conter:** [rotacionar a credencial](../seguranca/rotacao-de-credenciais.md), desligar o serviço afetado se necessário.
3. **Avaliar:** quais dados e quantos titulares, com base nos logs/traces (que não têm conteúdo, então a avaliação é por volume e janela de tempo).
4. **Comunicar:** ao controlador **sem demora**, para que ele decida sobre a comunicação à ANPD e aos titulares, conforme o regulamento de comunicação de incidentes vigente da ANPD (Resolução CD/ANPD nº 15/2024 — conferir o texto atual com o jurídico).
5. **Registrar:** post-mortem sem culpados, no padrão de [`docs/post-mortem-2026-09-21.md`](../post-mortem-2026-09-21.md).

## 5. Limites honestos

- O disco do Render gratuito é efêmero: isso **ajuda** a retenção (apaga sozinho) mas significa que o cache não sobrevive a reinícios; o ganho de custo do cache em produção depende do tempo que o serviço fica de pé. Ver [otimizações](../otimizacao/otimizacao-concorrencia-e-cache.md).
- A retenção dos logs e da telemetria na plataforma depende do plano contratado; ao subir de plano, rever esta tabela.
