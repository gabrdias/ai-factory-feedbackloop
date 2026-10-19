# Auditoria de dependências (SCA)

Dependência vulnerável é segredo vazado em câmera lenta: o código está "certo" e mesmo assim há uma porta aberta. Por isso, depois de travar todas as versões (lição do incidente do `httpx`, ver [post-mortem](../post-mortem-2026-09-21.md)), a auditoria de vulnerabilidades virou rotina automática.

## 1. Como roda

| O quê | Onde | Quando |
|---|---|---|
| `pip-audit -r requirements.txt --no-deps --disable-pip` | Job "Auditoria de dependências (pip-audit)" em [`.github/workflows/ci-cd.yml`](../../.github/workflows/ci-cd.yml) | Em todo push e **toda segunda-feira** (cron) |
| Lock completo de versões, inclusive transitivas | [`requirements.in`](../../requirements.in) → `requirements.txt` (`uv pip compile --universal --python-version 3.12`) | Ao mudar uma dependência |

O job roda **em paralelo e não bloqueia o deploy**: uma CVE publicada na véspera não pode impedir um hotfix, mas deixa o workflow vermelho, visível para quem olha o repositório. Quando fica vermelho, o procedimento é atualizar o pacote e regenerar o lock.

## 2. Achado desta etapa

Primeira execução do `pip-audit` sobre o lock herdado do protótipo:

| Pacote | Versão herdada | Achados | Corrigido em |
|---|---|---:|---|
| `pillow` (transitiva do Streamlit) | 11.3.0 | 18 | 12.1.1 a 12.3.0 |
| `streamlit` | 1.40.0 | 2 | 1.53.1 / 1.54.0 |
| `python-dotenv` | 1.0.1 | 1 | 1.2.2 |
| `pytest` (desenvolvimento) | 8.3.3 | 1 | 9.0.3 |
| **Total** | | **22** | |

Ação: atualizar para `streamlit 1.66.0`, `pillow 12.3.0`, `python-dotenv 1.2.4` e `pytest 9.1.1` (commit `fix: atualizar dependencias com vulnerabilidades conhecidas (pip-audit)`).

Resultado depois: `No known vulnerabilities found`. A suíte de testes (incluindo o clique real no botão, via `AppTest`) passou sem alterações de comportamento; a única mudança de código foi remover `use_container_width`, depreciado.

## 3. O que ficou de fora, e por quê

- `openai==1.50.0` e `httpx==0.27.2` continuam fixados nas versões já validadas em produção na Etapa 1. O `pip-audit` não aponta vulnerabilidade conhecida nelas hoje; a atualização do SDK é um item de manutenção com teste próprio, não um conserto de segurança.
- `pip-audit` só conhece vulnerabilidades **publicadas**. Não substitui revisão de código nem o `gitleaks`.

## 3.1 Como reproduzir

```bash
uv venv --python 3.12 .venv-audit
uv pip install --python .venv-audit/Scripts/python.exe pip-audit==2.10.1
.venv-audit/Scripts/pip-audit.exe -r requirements.txt --no-deps --disable-pip
```
