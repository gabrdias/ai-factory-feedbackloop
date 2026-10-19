"""O relatório de otimização só pode citar números que saem dos dados brutos."""

from pathlib import Path

from scripts.consolidar_medicoes_dev import consolidar

RAIZ = Path(__file__).resolve().parent.parent
RELATORIO = (RAIZ / "docs" / "otimizacao" / "otimizacao-concorrencia-e-cache.md").read_text(encoding="utf-8")
ADR = (RAIZ / "docs" / "adr" / "0005-otimizacao-concorrencia-e-cache.md").read_text(encoding="utf-8")


def test_tabela_de_latencia_do_relatorio_bate_com_os_dados_brutos():
    res = consolidar()
    for nome in ("A", "B", "C", "Bc", "Cf"):
        d = res[nome]["duracao"]
        for chave in ("p50", "p95", "p99", "media", "min", "max"):
            assert str(d[chave]) in RELATORIO, f"{nome}.{chave}={d[chave]} ausente do relatório"


def test_reducoes_citadas_batem_com_os_dados_brutos():
    res = consolidar()
    a = res["A"]["duracao"]["p50"]
    for nome in ("B", "C"):
        p50 = res[nome]["duracao"]["p50"]
        assert f"{(1 - p50 / a) * 100:.0f}%" in RELATORIO
        assert f"{a / p50:.1f}x" in RELATORIO
        assert f"{(1 - p50 / a) * 100:.0f}%" in ADR


def test_custo_por_analise_do_relatorio_bate_com_os_dados_brutos():
    res = consolidar()
    for nome in ("A", "B", "C"):
        assert f"{res[nome]['custo_usd']:.4f}".replace(".", ",") in ADR or f"{res[nome]['custo_usd']:.4f}" in RELATORIO
        assert str(res[nome]["chamadas_por_analise"]).rstrip("0").rstrip(".") in RELATORIO


def test_primeira_execucao_de_cada_cenario_e_descartada():
    res = consolidar()
    assert res["A"]["duracao"]["n"] == 5 and res["B"]["duracao"]["n"] == 5 and res["C"]["duracao"]["n"] == 5
    # o outlier frio (17,5 s) é o aquecimento do cenário C e não pode contaminar o máximo
    assert res["C"]["duracao"]["max"] < 5


def test_replicacao_local_do_relatorio_bate_com_o_benchmark_real():
    import json
    from statistics import mean

    dados = json.loads((RAIZ / "docs" / "benchmarks" / "benchmark-real.json").read_text(encoding="utf-8"))["cenarios"]
    a = dados["A_sequencial_sem_cache"]
    p50_a = a["resumo"]["p50_s"]
    for nome in ("B_concorrente_sem_cache", "C_concorrente_com_cache_quente"):
        p50 = dados[nome]["resumo"]["p50_s"]
        assert f"{(1 - p50 / p50_a) * 100:.1f}%".replace(".", ",") in RELATORIO
    a_contra_a = [e["concordancia_tema_vs_baseline"] for e in a["execucoes"][1:]]
    b = [e["concordancia_tema_vs_baseline"] for e in dados["B_concorrente_sem_cache"]["execucoes"]]
    assert f"{mean(a_contra_a) * 100:.1f}%".replace(".", ",") in RELATORIO
    assert f"{mean(b) * 100:.1f}%".replace(".", ",") in RELATORIO
