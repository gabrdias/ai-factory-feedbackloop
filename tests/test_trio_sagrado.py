# O "trio sagrado" (.env, .gitignore, .env.example) e a higiene de segredos, como testes.
# Evidência para docs/seguranca/ e para o CI: nada de chave no código, tudo documentado.

import re
import subprocess
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PADRAO_CHAVE = re.compile(r"(sk-[A-Za-z0-9_\-]{20,}|AIza[0-9A-Za-z_\-]{30,}|glc_[A-Za-z0-9+/=]{20,})")


def git(*args):
    return subprocess.run(["git", *args], cwd=RAIZ, capture_output=True, text=True)


def test_gitignore_ignora_o_env_real_mas_nao_o_exemplo():
    assert git("check-ignore", "-q", ".env").returncode == 0
    assert git("check-ignore", "-q", ".env.local").returncode == 0
    assert git("check-ignore", "-q", ".env.example").returncode == 1  # exemplo PRECISA ser versionado
    assert git("check-ignore", "-q", ".cache/feedbackloop.sqlite3").returncode == 0


def test_env_real_nao_esta_versionado():
    versionados = git("ls-files").stdout.split()
    assert ".env" not in versionados
    assert ".env.example" in versionados


def test_env_example_so_tem_placeholders():
    texto = (RAIZ / ".env.example").read_text(encoding="utf-8")
    assert not PADRAO_CHAVE.search(texto), ".env.example parece conter uma chave real"
    for linha in texto.splitlines():
        if linha.strip().startswith("OPENAI_API_KEY="):
            assert linha.split("=", 1)[1].strip() in {"sk-...", ""}


def test_nenhum_arquivo_versionado_tem_cara_de_chave_de_api():
    suspeitos = []
    for nome in git("ls-files").stdout.split():
        caminho = RAIZ / nome
        if caminho.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".sqlite3"}:
            continue
        try:
            conteudo = caminho.read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError):
            continue
        if PADRAO_CHAVE.search(conteudo):
            suspeitos.append(nome)
    assert suspeitos == [], f"possível chave em: {suspeitos}"


def test_toda_variavel_lida_pelo_codigo_esta_documentada_no_env_example():
    exemplo = (RAIZ / ".env.example").read_text(encoding="utf-8")
    documentadas = set(re.findall(r"^#?\s*([A-Z][A-Z0-9_]+)=", exemplo, re.MULTILINE))

    lidas = set()
    arquivos = [RAIZ / "app.py", *sorted((RAIZ / "feedbackloop").glob("*.py"))]
    padroes = [
        r'os\.getenv\(\s*"([A-Z][A-Z0-9_]+)"',
        r'os\.environ(?:\.get)?\[\s*"([A-Z][A-Z0-9_]+)"',
        r'os\.environ\.get\(\s*"([A-Z][A-Z0-9_]+)"',
        r'_(?:inteiro|decimal_opcional|booleano)\(\s*"([A-Z][A-Z0-9_]+)"',
    ]
    for arq in arquivos:
        codigo = arq.read_text(encoding="utf-8")
        for padrao in padroes:
            lidas.update(re.findall(padrao, codigo))

    fornecidas_pela_plataforma = {  # o Render define sozinho em runtime
        "RENDER", "RENDER_SERVICE_NAME", "RENDER_EXTERNAL_HOSTNAME", "RENDER_EXTERNAL_URL",
        "RENDER_GIT_BRANCH", "RENDER_GIT_COMMIT",
    }
    so_para_testes = {"FEEDBACKLOOP_IGNORAR_DOTENV"}
    lidas -= fornecidas_pela_plataforma | so_para_testes
    lidas |= {"OTEL_EXPORTER_OTLP_HEADERS"}  # lida pela biblioteca do exportador, não pelo nosso código
    assert lidas, "o teste não encontrou nenhuma variável; o padrão de busca quebrou"
    assert lidas <= documentadas, f"faltam no .env.example: {sorted(lidas - documentadas)}"
