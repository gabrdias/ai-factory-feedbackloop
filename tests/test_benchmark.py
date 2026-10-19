# O benchmark (modo simulado) tem que ser reproduzível e coerente; o modo real usa a mesma mecânica.

from scripts.benchmark import executar, percentil
from scripts.relatorio_benchmark import gerar


def test_percentil_por_posto_mais_proximo():
    xs = [10, 20, 30, 40, 50]
    assert percentil(xs, 50) == 30
    assert percentil(xs, 95) == 50  # com 5 amostras, p95 = máximo
    assert percentil(xs, 99) == 50
    assert percentil([7], 99) == 7


def test_benchmark_simulado_mostra_o_ganho_da_concorrencia_e_do_cache():
    dados = executar(repeticoes=2, workers=6, simulado=True, latencia_simulada=0.02, limite=12,
                     cenarios=["A_sequencial_sem_cache", "B_concorrente_sem_cache", "C_concorrente_com_cache_quente"])
    a, b, c = (dados["cenarios"][k]["resumo"]["p50_s"] for k in
               ("A_sequencial_sem_cache", "B_concorrente_sem_cache", "C_concorrente_com_cache_quente"))
    assert b < a * 0.6   # 12 chamadas sequenciais vs 6 em paralelo
    assert c < b         # com cache só o resumo vai ao provedor

    execs_c = dados["cenarios"]["C_concorrente_com_cache_quente"]["execucoes"]
    assert all(e["cache_hits"] == 12 and e["chamadas_llm"] == 0 for e in execs_c) or all(e["cache_hits"] == 12 for e in execs_c)
    # a otimização não pode mudar o resultado
    for nome in ("B_concorrente_sem_cache", "C_concorrente_com_cache_quente"):
        for e in dados["cenarios"][nome]["execucoes"]:
            assert e["concordancia_tema_vs_baseline"] == 1.0
            assert e["concordancia_sentimento_vs_baseline"] == 1.0
    assert dados["meta"]["modo"] == "simulado"


def test_relatorio_markdown_nao_quebra_e_marca_o_modo():
    dados = executar(repeticoes=1, workers=4, simulado=True, latencia_simulada=0.0, limite=4,
                     cenarios=["A_sequencial_sem_cache", "B_concorrente_sem_cache"])
    texto = gerar(dados)
    assert "modo **simulado**" in texto
    assert "A_sequencial_sem_cache" in texto and "B_concorrente_sem_cache" in texto
    assert "Latência SIMULADA" in texto
