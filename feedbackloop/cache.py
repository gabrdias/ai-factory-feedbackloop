"""Cache de classificações com prazo de validade (retenção) e exclusão sob demanda.

O que é guardado: `sha256(prompt_version | modelo | texto_já_sanitizado)` -> {tema, sentimento}.
Nunca o texto da resposta, nunca o texto original, nunca nomes. Mesmo assim, a entrada é
tratada como potencialmente vinculável a uma pessoa e some pelo TTL (padrão 30 dias, sempre
abaixo do teto de 90 dias do BRIEFING.md).

Mecanismos de retenção/exclusão (documentados em docs/lgpd/politica-de-retencao-e-exclusao.md):
  1. `obter()` descarta e apaga na hora uma entrada vencida;
  2. `purgar_expirados()` roda ao iniciar o app e a cada hora (`iniciar_purga_periodica`);
  3. `limpar()` apaga tudo sob demanda (botão "Excluir cache agora" da barra lateral).
"""

from __future__ import annotations

import hashlib
import logging
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path

from . import observabilidade as obs

_SCHEMA = """
CREATE TABLE IF NOT EXISTS classificacao (
    chave TEXT PRIMARY KEY,
    tema TEXT NOT NULL,
    sentimento TEXT NOT NULL,
    criado_em REAL NOT NULL
)
"""


class CacheClassificacao:
    def __init__(self, caminho: str, ttl_dias: int = 30, agora=time.time):
        self._caminho = str(caminho)
        self._ttl_s = ttl_dias * 86400
        self._agora = agora
        self._lock = threading.Lock()
        Path(self._caminho).parent.mkdir(parents=True, exist_ok=True)
        with self._conexao() as con:
            con.execute(_SCHEMA)

    @property
    def ttl_dias(self) -> int:
        return int(self._ttl_s // 86400)

    @contextmanager
    def _conexao(self):
        con = sqlite3.connect(self._caminho, timeout=10)
        try:
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()  # fechar de verdade: no Windows o arquivo ficaria travado

    @staticmethod
    def chave(texto_sanitizado: str, modelo: str, versao_prompt: str) -> str:
        bruto = f"{versao_prompt}|{modelo}|{texto_sanitizado}".encode("utf-8")
        return hashlib.sha256(bruto).hexdigest()

    def obter(self, chave: str) -> dict | None:
        with self._lock, self._conexao() as con:
            linha = con.execute(
                "SELECT tema, sentimento, criado_em FROM classificacao WHERE chave = ?", (chave,)
            ).fetchone()
            if linha is None:
                return None
            tema, sentimento, criado_em = linha
            if criado_em < self._agora() - self._ttl_s:
                con.execute("DELETE FROM classificacao WHERE chave = ?", (chave,))
                return None
            return {"tema": tema, "sentimento": sentimento}

    def guardar(self, chave: str, tema: str, sentimento: str) -> None:
        with self._lock, self._conexao() as con:
            con.execute(
                "INSERT OR REPLACE INTO classificacao (chave, tema, sentimento, criado_em) VALUES (?,?,?,?)",
                (chave, tema, sentimento, self._agora()),
            )

    def purgar_expirados(self) -> int:
        limite = self._agora() - self._ttl_s
        with self._lock, self._conexao() as con:
            removidos = con.execute("DELETE FROM classificacao WHERE criado_em < ?", (limite,)).rowcount
        if removidos:
            obs.inst().cache_purgados.add(removidos, obs.attrs())
        obs.registrar_evento("cache.purga", removidos=removidos, ttl_dias=self.ttl_dias)
        return removidos

    def limpar(self) -> int:
        with self._lock, self._conexao() as con:
            removidos = con.execute("DELETE FROM classificacao").rowcount
        obs.registrar_evento("cache.limpeza_total", removidos=removidos)
        return removidos

    def contar(self) -> int:
        with self._lock, self._conexao() as con:
            return con.execute("SELECT COUNT(*) FROM classificacao").fetchone()[0]


def iniciar_purga_periodica(cache: CacheClassificacao, intervalo_s: float = 3600.0):
    """Roda `purgar_expirados` agora e depois a cada `intervalo_s`. Devolve (thread, evento_de_parada)."""
    parar = threading.Event()

    def _laco():
        while True:
            try:
                cache.purgar_expirados()
            except Exception:  # a purga nunca pode derrubar o app
                logging.getLogger("feedbackloop").exception("falha na purga do cache")
            if parar.wait(intervalo_s):
                return

    thread = threading.Thread(target=_laco, name="purga-cache", daemon=True)
    thread.start()
    return thread, parar
