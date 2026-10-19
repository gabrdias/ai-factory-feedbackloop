from feedbackloop import config


def test_padroes_sem_nenhuma_variavel(monkeypatch):
    for var in ("APP_ENV", "RENDER_SERVICE_NAME", "OPENAI_MODEL", "LLM_MAX_WORKERS", "CACHE_HABILITADO",
                "LLM_PRECO_ENTRADA_USD_POR_MTOK", "LLM_PRECO_SAIDA_USD_POR_MTOK", "CACHE_TTL_DIAS", "CACHE_DB_PATH"):
        monkeypatch.delenv(var, raising=False)
    cfg = config.carregar()
    assert cfg.ambiente == "local"
    assert cfg.modelo == "gpt-5.4-mini"
    assert cfg.max_workers == 8
    assert cfg.cache_habilitado is True
    assert cfg.cache_ttl_dias == 30  # abaixo do teto de 90 dias do BRIEFING.md
    assert cfg.preco_entrada_usd_por_mtok is None and cfg.preco_saida_usd_por_mtok is None


def test_ambiente_e_deduzido_do_nome_do_servico_no_render(monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.setenv("RENDER_SERVICE_NAME", "feedbackloop-prod")
    assert config.carregar().ambiente == "prod"
    monkeypatch.setenv("RENDER_SERVICE_NAME", "feedbackloop-dev")
    assert config.carregar().ambiente == "dev"
    monkeypatch.setenv("APP_ENV", "staging")  # explícito vence
    assert config.carregar().ambiente == "staging"


def test_ambiente_tambem_e_deduzido_pela_branch_e_pelo_host_do_render(monkeypatch):
    for var in ("APP_ENV", "RENDER_SERVICE_NAME", "RENDER_EXTERNAL_HOSTNAME", "RENDER_EXTERNAL_URL", "RENDER_GIT_BRANCH", "RENDER"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("RENDER_GIT_BRANCH", "develop")
    assert config.carregar().ambiente == "dev"
    monkeypatch.setenv("RENDER_GIT_BRANCH", "main")
    assert config.carregar().ambiente == "prod"
    monkeypatch.delenv("RENDER_GIT_BRANCH")
    monkeypatch.setenv("RENDER_EXTERNAL_HOSTNAME", "feedbackloop-dev-6yzb.onrender.com")
    assert config.carregar().ambiente == "dev"
    monkeypatch.delenv("RENDER_EXTERNAL_HOSTNAME")
    monkeypatch.setenv("RENDER", "true")
    assert config.carregar().ambiente == "render"  # no Render, mas sem pista de qual serviço


def test_commit_em_execucao_vem_do_render(monkeypatch):
    monkeypatch.setenv("RENDER_GIT_COMMIT", "0123456789abcdef")
    assert config.carregar().commit == "0123456"


def test_valores_invalidos_caem_no_padrao_em_vez_de_quebrar(monkeypatch):
    monkeypatch.setenv("LLM_MAX_WORKERS", "muitos")
    monkeypatch.setenv("LLM_PRECO_ENTRADA_USD_POR_MTOK", "caro")
    cfg = config.carregar()
    assert cfg.max_workers == 8
    assert cfg.preco_entrada_usd_por_mtok is None


def test_modelo_e_workers_vem_do_ambiente(monkeypatch):
    monkeypatch.setenv("OPENAI_MODEL", "outro-modelo")
    monkeypatch.setenv("LLM_MAX_WORKERS", "1")
    monkeypatch.setenv("CACHE_HABILITADO", "false")
    cfg = config.carregar()
    assert (cfg.modelo, cfg.max_workers, cfg.cache_habilitado) == ("outro-modelo", 1, False)
