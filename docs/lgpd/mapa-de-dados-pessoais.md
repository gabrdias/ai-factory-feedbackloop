# Mapa de dados pessoais — FeedbackLoop Survey Insights

> Documentação técnica da Etapa 2. **Não é parecer jurídico**: o `BRIEFING.md` pede que dúvidas de base legal passem pela Head de People Analytics e pelo jurídico antes de operar com dados reais. Os pontos que dependem disso estão marcados como **pendência** na seção 5.

## 1. Papéis (LGPD, art. 5º)

| Quem | Papel | Por quê |
|---|---|---|
| Empresas clientes da FeedbackLoop (RH) | **Controladoras** (art. 5º, VI) | Decidem aplicar a pesquisa de clima, definem a finalidade e enviam as respostas dos seus colaboradores. |
| FeedbackLoop Tecnologia | **Operadora** (art. 5º, VII) | Trata os dados em nome do cliente, seguindo as instruções dele (art. 39). Também é controladora dos *seus próprios* dados operacionais (telemetria, logs). |
| OpenAI | **Suboperadora** (processamento fora do Brasil) | Recebe o texto **já mascarado** para classificar. Ver [transferência internacional](transferencia-internacional.md). |
| **Render** (hospedagem) | Suboperador de infraestrutura | O app roda lá: o **texto original** das respostas passa pela memória do servidor (antes do mascaramento), em região fora do Brasil a confirmar. Ver [transferência internacional](transferencia-internacional.md), trecho T1. |
| Grafana Labs (telemetria, região São Paulo) | Suboperador de infraestrutura | Recebe métricas/traces **sem conteúdo de respostas** e sem dado pessoal. |

**Titulares:** (a) colaboradores que respondem à pesquisa; (b) **terceiros citados** no texto livre (gestores, colegas, ex-colegas); (c) pessoas que acessam o app (endereço IP nos logs da plataforma).

## 2. Mapa: onde há dado pessoal e com que base legal

A coluna "base legal" separa **a do controlador (cliente)**, que é quem precisa tê-la para pedir a análise, do **fundamento da FeedbackLoop** como operadora. Consentimento **não** é a base adotada: numa relação de trabalho há desequilíbrio de poder e o consentimento dificilmente seria livre (art. 5º, XII); para pesquisa de clima o caminho usual é o **legítimo interesse** (art. 7º, IX) com teste de balanceamento (art. 10).

| # | Ponto de coleta / tratamento | Dados envolvidos | Titulares | Finalidade | Base legal (art. 7º) | Retenção | Controles técnicos (com evidência) |
|---|---|---|---|---|---|---|---|
| **P1** | **Respostas abertas** coladas, enviadas em CSV ou usadas como exemplo | Texto livre. Pode conter **nomes de gestores e colegas**, contatos, relatos identificáveis e, de forma incidental, dado sensível (saúde, filiação sindical — art. 11) | Respondentes e terceiros citados | Agrupar por tema, classificar sentimento e resumir o clima para a liderança | **Controlador:** legítimo interesse (IX), com LIA e anonimato/voluntariedade da pesquisa. **Operadora:** instrução do controlador + contrato (art. 39) | **Só na memória da sessão**; nada é gravado. Some ao fechar a aba ou reiniciar o serviço | Sem persistência do resultado (teste `test_o_texto_da_resposta_nunca_e_gravado_em_disco`); TLS na plataforma |
| **P2** | **Texto enviado ao provedor de IA** (OpenAI) | O mesmo texto de P1, **depois da sanitização**: nomes, e-mail, CPF, telefone etc. viram marcadores (`[PESSOA_1]`, `[EMAIL]`…) | Os de P1 | Classificação por LLM | Mesma de P1 (controlador). **Transferência internacional:** art. 33, II (garantias contratuais), ver [documento próprio](transferencia-internacional.md) | Definida pelo provedor (ver pendência P-1) | Sanitização antes de **toda** chamada ([`feedbackloop/pii.py`](../../feedbackloop/pii.py)); trava final que **bloqueia** o envio se restar PII reconhecível; o resumo executivo só recebe **agregados**. Provas: `test_nenhum_prompt_enviado_ao_llm_contem_pii`, [avaliação medida](avaliacao-sanitizacao-pii.md) |
| **P3** | **Tela de resultado** (resumo, tema e sentimento por resposta) | Texto **mascarado** de cada resposta, temas, contagens | Os de P1 | Entregar a análise ao analista de RH | Mesma de P1 | Sessão do navegador; "este resultado não é salvo em lugar nenhum" | A tabela mostra o texto como foi enviado ao provedor, não o original |
| **P4** | **Cache de classificações** | `sha256(versão do prompt \| modelo \| texto mascarado)` + tema + sentimento + data. **Nunca o texto** | Vinculável só indiretamente | Não reclassificar (e não pagar de novo) a mesma resposta | Legítimo interesse (IX): eficiência e minimização de custo | **30 dias** (teto do briefing: 90) | Purga ao iniciar e a cada hora, expiração na leitura, botão "Excluir cache agora"; disco efêmero do Render. Ver [política de retenção](politica-de-retencao-e-exclusao.md) |
| **P5** | **Telemetria** (traces e métricas OpenTelemetry → Grafana Cloud) | Contagens, durações, tokens, custo, **tipos** de PII mascarados (ex.: "2 pessoas") e rótulo de ambiente. **Sem texto, sem nomes** | Nenhum identificável por desenho | Operar, medir custo/latência/erro e alertar | Legítimo interesse (IX); dever de segurança (arts. 6º, VII e 46) | 14 dias no plano gratuito do Grafana Cloud (teto: 90) — confirmar na stack | Teste `test_nenhum_span_nem_log_contem_dado_pessoal` varre atributos de spans e a saída de log |
| **P6** | **Logs da aplicação** (JSON em stdout, coletados pelo Render) | Eventos como `analise.concluida` com contagens e duração. Sem texto | Nenhum identificável por desenho | Diagnóstico e auditoria | Legítimo interesse (IX); art. 46 | Definida pelo Render; teto do briefing: 90 dias | Mesmo teste de P5; formato estruturado só com campos permitidos |
| **P7** | **Logs de acesso da plataforma** | **Endereço IP** e user-agent de quem abre o app | Quem acessa a URL | Segurança e disponibilidade (responsabilidade do Render) | Legítimo interesse (IX); art. 46 | Definida pelo Render | A FeedbackLoop não consulta nem cruza esses logs; nenhum login, nenhum cookie próprio |
| **P8** | **Estatísticas de uso do Streamlit** | (seriam dados de uso enviados ao fabricante) | Quem acessa a URL | — | **Não há tratamento**: desligado | — | `.streamlit/config.toml` com `gatherUsageStats = false` (teste `test_streamlit_nao_envia_estatisticas_de_uso_ao_fabricante`) |

**Dados de teste, demonstração e vídeo:** 100% sintéticos (`data/AVISO-DADOS-SINTETICOS.md`). Nenhum dado pessoal real foi usado em nenhum ambiente desta etapa.

## 3. Riscos específicos deste protótipo (e por que o tratamento é o que é)

| Risco | Probabilidade | Impacto | Tratamento | Risco residual |
|---|---|---|---|---|
| **Nome de gestor ou colega no texto livre** ("o gerente Marcos Antunes muda tudo"). É o caso que o protótipo original ignorava (aviso amarelo "que ninguém lê") | Alta | Alto (terceiro exposto a um provedor no exterior) | Mascaramento antes do envio + trava final. Medido: **100%** nas categorias cobertas e **87,5%** no conjunto total, que inclui lacunas conhecidas | **Médio**: nomes raros sem pista de contexto e nomes em minúsculas **passam** (0 de 9 nos testes). Por isso P2 continua sendo tratado como dado pessoal |
| **Identificação indireta** ("a única gerente do financeiro de Joinville", "quem saiu em março") | Média | Alto | Nenhuma regra automática resolve. Mitigação organizacional: o resumo só mostra **agregados**; recomenda-se relatar só grupos com tamanho mínimo | **Médio**, aceito e documentado |
| **Dado sensível incidental** (saúde mental, sindicato, religião) em respostas livres | Média | Alto (art. 11) | O app **não** pede esse tipo de dado; orientação ao controlador para não induzir respostas assim | **Médio**; depende do controlador e do desenho da pesquisa |
| **Exposição pelo provedor de IA** (retenção, uso para treino) | Baixa | Alto | Texto mascarado; verificar no DPA vigente retenção e não-treinamento (pendência P-1) | A confirmar |
| **PII em logs/telemetria** | Baixa | Médio | Proibido por desenho + teste automatizado que varre spans e logs | Baixo |
| **Chave de API vazada** | Baixa | Alto (custo e abuso) | Trio sagrado, gitleaks no CI, [rotação documentada](../seguranca/rotacao-de-credenciais.md) | Baixo |

## 4. Direitos dos titulares (art. 18) na prática

Como **operadora**, a FeedbackLoop encaminha ao controlador (o cliente) qualquer pedido de titular. Tecnicamente: (a) não há base de dados de respondentes para consultar, corrigir ou portar; (b) para **eliminação**, o que existe é o cache, apagável por inteiro com um clique, por `python scripts/retencao.py limpar --sim` ou pelo prazo de 30 dias; (c) não há decisão automatizada sobre pessoas: a saída é agregada e não gera efeito sobre um indivíduo (art. 20 não se aplica a este protótipo).

## 5. Pendências (não resolvidas por código)

| # | Pendência | Responsável sugerido |
|---|---|---|
| P-1 | Confirmar no DPA vigente do provedor de IA: retenção dos dados da API, não-uso para treino e se incorpora as cláusulas-padrão da ANPD | Jurídico / Encarregado (DPO) |
| P-2 | LIA (teste de balanceamento do legítimo interesse) deve ser feita **por cliente**, pois a base é do controlador | Cliente (controlador), com apoio da FeedbackLoop |
| P-3 | Região escolhida na stack do Grafana Cloud e retenção real do plano; atualizar P5 | Engenharia |
| P-4 | Relatório de Impacto (RIPD, art. 38) formal antes do piloto com cliente real | Jurídico / Encarregado |
| P-5 | Definir o Encarregado (art. 41) e o canal de contato do titular | Diretoria |
| P-6 | Confirmar a **região do serviço no Render** e o DPA da plataforma; a sanitização acontece dentro do app, então o texto original atravessa a fronteira até o Render (ver [transferência internacional](transferencia-internacional.md), T-1) | Engenharia + Jurídico |
