"""Sanitização (pseudonimização) de dados pessoais antes de qualquer envio ao LLM.

Princípio (BRIEFING.md, LGPD): nenhum dado identificável entra em prompt sem
tratamento. Este módulo substitui por marcadores (`[PESSOA_1]`, `[EMAIL]`, ...)
tudo o que consegue reconhecer como dado pessoal direto:

- identificadores estruturados: e-mail, CPF, CNPJ, RG, matrícula, CEP, telefone,
  URL e @usuário (regex, com validação de dígitos no CPF);
- nomes de pessoas: léxico de nomes comuns + pistas de contexto (cargo ou título
  antes do nome) + sobrenome comum depois de um nome capitalizado.

LIMITAÇÕES CONHECIDAS (medidas em docs/lgpd/avaliacao-sanitizacao-pii.md):
nomes raros sem nenhuma pista de contexto, nomes escritos todo em minúsculas e
identificação indireta (cargo + local + situação) NÃO são detectados. Por isso o
resultado continua sendo tratado como dado pessoal na documentação de LGPD.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass

from ._lexico_nomes import PRIMEIROS_NOMES, SOBRENOMES


def _norm(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFD", texto.casefold())
    return "".join(c for c in sem_acento if unicodedata.category(c) != "Mn")


_PRIMEIROS = frozenset(_norm(n) for n in PRIMEIROS_NOMES)
_SOBRENOMES = frozenset(_norm(n) for n in SOBRENOMES)

# Palavras que, logo antes de uma palavra Capitalizada, indicam que ela é um nome.
_GATILHOS = frozenset(
    {
        "gerente", "gestor", "gestora", "chefe", "lider", "diretor", "diretora",
        "supervisor", "supervisora", "coordenador", "coordenadora", "analista",
        "colega", "presidente", "ceo", "cfo", "cto", "coo", "vp", "head",
        "padrinho", "madrinha", "mentor", "mentora", "chamado", "chamada",
    }
)
_TITULOS = frozenset(
    {"sr", "sra", "srta", "dr", "dra", "prof", "profa", "dona", "seu", "senhor", "senhora"}
)
_PARTICULAS = frozenset({"de", "da", "do", "dos", "das"})
_PREFIXOS_LUGAR = frozenset({"sao", "santa", "santo", "san"})
_BIGRAMAS_LUGAR = frozenset({("joao", "pessoa"), ("presidente", "prudente")})
# Palavras Capitalizadas que nunca fazem parte de um nome (evita absorvê-las).
_STOP_CAP = frozenset(
    {
        "o", "a", "os", "as", "eu", "ele", "ela", "mas", "e", "que", "se", "nao",
        "muito", "hoje", "ontem", "quando", "porque", "pois", "como", "na", "no",
        "em", "um", "uma", "isso", "essa", "esse", "minha", "meu", "sempre", "nunca",
        "tambem", "mesmo", "ainda", "ja", "entao", "sobre", "para", "por", "com",
        "sem", "tem", "foi", "era", "sao", "esta", "depois", "antes", "gostaria",
        "falta", "faltam", "geral", "regional", "senior", "pleno", "junior",
    }
)

_TOKEN = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ]+(?:[-'’][A-Za-zÀ-ÖØ-öø-ÿ]+)*")
_GAP_ESPACO = re.compile(r"^\s*$")
_GAP_TITULO = re.compile(r"^\.?\s+$")

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_URL = re.compile(r"(?:https?://|www\.)[^\s<>\"']+", re.IGNORECASE)
_CNPJ = re.compile(r"(?<!\d)\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}(?!\d)")
_CPF_FORMATADO = re.compile(r"(?<!\d)\d{3}\.\d{3}\.\d{3}-\d{2}(?!\d)")
_CPF_PURO = re.compile(r"(?<![\d.\-/])\d{11}(?![\d\-/])")
_RG = re.compile(r"(\bRG\b[\s:.nº°-]*)(\d[\d.\-xX]{5,})", re.IGNORECASE)
_ROTULO_ID = re.compile(
    r"(\b(?:matr[íi]cula|crach[áa]|registro|id)\b\s*(?:n[ºo°.]?\s*)?[:#-]?\s*)(\d{3,})",
    re.IGNORECASE,
)
_CEP = re.compile(r"(?<![\d-])\d{5}-\d{3}(?![\d-])")
_TELEFONE = re.compile(
    r"(?<![\w\[])(?:\+?55[\s.-]?)?(?:\(\s?\d{2}\s?\)|\d{2})[\s.-]?9?\d{4}[\s.-]?\d{4}(?![\w\]])"
)
_TELEFONE_LOCAL = re.compile(r"(?<![\w-])9?\d{4}-\d{4}(?![\w-])")
_HANDLE = re.compile(r"(?<![\w@.])@[A-Za-z0-9_][A-Za-z0-9_.]{2,}")


@dataclass(frozen=True)
class ResultadoSanitizacao:
    texto: str
    entidades: dict  # tipo -> quantidade (nunca guarda o valor original)

    @property
    def total(self) -> int:
        return sum(self.entidades.values())


class PIIDetectadaError(ValueError):
    """Lançada quando um texto prestes a ser enviado ao LLM ainda contém PII."""


def _cpf_valido(digitos: str) -> bool:
    if len(digitos) != 11 or digitos == digitos[0] * 11:
        return False
    for tamanho in (9, 10):
        soma = sum(int(d) * peso for d, peso in zip(digitos[:tamanho], range(tamanho + 1, 1, -1)))
        digito = (soma * 10) % 11 % 10
        if digito != int(digitos[tamanho]):
            return False
    return True


def _pares_de_anos(trecho: str) -> bool:
    grupos = re.findall(r"\d+", trecho)
    return len(grupos) >= 2 and all(len(g) == 4 and g[:2] in ("19", "20") for g in grupos[-2:])


def _sanitizar_estruturados(texto: str, contagem: Counter) -> str:
    def trocar(padrao, marcador, texto_atual, validar=None):
        def _sub(m):
            if validar is not None and not validar(m.group(0)):
                return m.group(0)
            contagem[marcador] += 1
            return f"[{marcador}]"

        return padrao.sub(_sub, texto_atual)

    def trocar_rotulado(padrao, marcador, texto_atual):
        def _sub(m):
            contagem[marcador] += 1
            return f"{m.group(1)}[{marcador}]"

        return padrao.sub(_sub, texto_atual)

    texto = trocar(_EMAIL, "EMAIL", texto)
    texto = trocar(_URL, "URL", texto)
    texto = trocar(_CNPJ, "CNPJ", texto)
    texto = trocar(_CPF_FORMATADO, "CPF", texto)
    texto = trocar_rotulado(_RG, "RG", texto)
    texto = trocar_rotulado(_ROTULO_ID, "MATRICULA", texto)
    texto = trocar(_CEP, "CEP", texto)
    texto = trocar(_CPF_PURO, "CPF", texto, validar=_cpf_valido)
    texto = trocar(_TELEFONE, "TELEFONE", texto, validar=lambda t: not _pares_de_anos(t))
    texto = trocar(_TELEFONE_LOCAL, "TELEFONE", texto)
    texto = trocar(_HANDLE, "USUARIO", texto)
    return texto


def _comeca_nome(texto: str, toks: list, i: int) -> bool:
    palavra = toks[i].group()
    if not palavra[0].isupper():
        return False
    chave = _norm(palavra)
    primeiro = _norm(re.split(r"[-'’]", palavra)[0])
    anterior = _norm(toks[i - 1].group()) if i > 0 else ""
    espaco_ant = texto[toks[i - 1].end():toks[i].start()] if i > 0 else ""
    seguinte = _norm(toks[i + 1].group()) if i + 1 < len(toks) else ""

    if anterior in _PREFIXOS_LUGAR and _GAP_ESPACO.match(espaco_ant):
        return False  # São Paulo, Santa Maria, Santo André...
    if (anterior, chave) in _BIGRAMAS_LUGAR:
        return False
    if (chave, seguinte) in _BIGRAMAS_LUGAR:
        return False
    if chave in _STOP_CAP:
        return False
    if primeiro in _PRIMEIROS:
        return True
    if anterior in _GATILHOS and _GAP_ESPACO.match(espaco_ant):
        return True
    if anterior in _TITULOS and _GAP_TITULO.match(espaco_ant):
        return True
    if i + 1 < len(toks):
        espaco_seg = texto[toks[i].end():toks[i + 1].start()]
        prox = toks[i + 1].group()
        if (
            _GAP_ESPACO.match(espaco_seg)
            and prox[0].isupper()
            and _norm(prox) in _SOBRENOMES
            and anterior not in _PREFIXOS_LUGAR
        ):
            return True  # nome desconhecido + sobrenome comum
    return False


def _sanitizar_nomes(texto: str, contagem: Counter) -> str:
    toks = list(_TOKEN.finditer(texto))
    trocas = []  # (inicio, fim, chave_do_primeiro_nome)
    i = 0
    while i < len(toks):
        if not _comeca_nome(texto, toks, i):
            i += 1
            continue
        ultimo = i
        j = i + 1
        while j < len(toks) and (j - i) < 5:
            if not _GAP_ESPACO.match(texto[toks[ultimo].end():toks[j].start()]):
                break
            palavra = toks[j].group()
            norm = _norm(palavra)
            if norm in _PARTICULAS:
                if (
                    j + 1 < len(toks)
                    and _GAP_ESPACO.match(texto[toks[j].end():toks[j + 1].start()])
                    and toks[j + 1].group()[0].isupper()
                ):
                    ultimo = j + 1
                    j += 2
                    continue
                break
            if palavra[0].isupper() and norm not in _STOP_CAP:
                ultimo = j
                j += 1
                continue
            break
        trocas.append((toks[i].start(), toks[ultimo].end(), _norm(re.split(r"[-'’]", toks[i].group())[0])))
        i = ultimo + 1

    if not trocas:
        return texto

    # Numera na ordem de aparição; a mesma pessoa citada de novo mantém o número.
    ids: dict[str, int] = {}
    for _, _, chave in trocas:
        ids.setdefault(chave, len(ids) + 1)
    saida = texto
    for inicio, fim, chave in reversed(trocas):
        saida = saida[:inicio] + f"[PESSOA_{ids[chave]}]" + saida[fim:]
        contagem["PESSOA"] += 1
    return saida


def sanitizar(texto: str) -> ResultadoSanitizacao:
    """Devolve o texto com os dados pessoais reconhecidos trocados por marcadores."""
    if not texto:
        return ResultadoSanitizacao(texto=texto or "", entidades={})
    contagem: Counter = Counter()
    saida = _sanitizar_estruturados(texto, contagem)
    saida = _sanitizar_nomes(saida, contagem)
    return ResultadoSanitizacao(texto=saida, entidades=dict(contagem))


def sanitizar_lote(textos: list[str]) -> tuple[list[str], Counter]:
    """Sanitiza vários textos e soma as contagens por tipo de entidade."""
    total: Counter = Counter()
    saida = []
    for texto in textos:
        r = sanitizar(texto)
        saida.append(r.texto)
        total.update(r.entidades)
    return saida, total


def contem_pii(texto: str) -> bool:
    """True se ainda restar algo reconhecível como dado pessoal no texto."""
    return sanitizar(texto).total > 0


def garantir_sem_pii(texto: str) -> None:
    """Última barreira antes do provedor: bloqueia se restar PII reconhecível."""
    r = sanitizar(texto)
    if r.total:
        tipos = ", ".join(sorted(r.entidades))
        raise PIIDetectadaError(f"Texto com PII ainda reconhecível ({tipos}); envio bloqueado.")
