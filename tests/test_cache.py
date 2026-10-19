# Cache de classificações: TTL, purga (retenção), exclusão sob demanda e o que NÃO é guardado.

import sqlite3
import time

from feedbackloop.cache import CacheClassificacao, iniciar_purga_periodica

DIA = 86400


class Relogio:
    def __init__(self, t=1_000_000.0):
        self.t = t

    def __call__(self):
        return self.t

    def avancar_dias(self, dias):
        self.t += dias * DIA


def test_guardar_e_obter(tmp_path):
    cache = CacheClassificacao(tmp_path / "c.db", ttl_dias=30)
    chave = cache.chave("texto", "modelo-x", "v1")
    assert cache.obter(chave) is None
    cache.guardar(chave, "Liderança", "negativo")
    assert cache.obter(chave) == {"tema": "Liderança", "sentimento": "negativo"}
    assert cache.contar() == 1


def test_chave_muda_com_texto_modelo_e_versao_do_prompt():
    chaves = {
        CacheClassificacao.chave("a", "m1", "v1"),
        CacheClassificacao.chave("b", "m1", "v1"),
        CacheClassificacao.chave("a", "m2", "v1"),
        CacheClassificacao.chave("a", "m1", "v2"),
    }
    assert len(chaves) == 4


def test_entrada_vencida_nao_e_devolvida_e_e_apagada(tmp_path):
    relogio = Relogio()
    cache = CacheClassificacao(tmp_path / "c.db", ttl_dias=30, agora=relogio)
    chave = cache.chave("texto", "m", "v1")
    cache.guardar(chave, "Salário", "negativo")
    relogio.avancar_dias(29)
    assert cache.obter(chave) is not None
    relogio.avancar_dias(2)  # 31 dias > TTL de 30
    assert cache.obter(chave) is None
    assert cache.contar() == 0


def test_purga_remove_so_o_que_venceu(tmp_path):
    relogio = Relogio()
    cache = CacheClassificacao(tmp_path / "c.db", ttl_dias=30, agora=relogio)
    velha = cache.chave("velha", "m", "v1")
    cache.guardar(velha, "A", "neutro")
    relogio.avancar_dias(20)
    nova = cache.chave("nova", "m", "v1")
    cache.guardar(nova, "B", "positivo")
    relogio.avancar_dias(15)  # velha tem 35 dias, nova tem 15
    assert cache.purgar_expirados() == 1
    assert cache.obter(velha) is None
    assert cache.obter(nova) == {"tema": "B", "sentimento": "positivo"}


def test_limpar_apaga_tudo_sob_demanda(tmp_path):
    cache = CacheClassificacao(tmp_path / "c.db")
    for i in range(5):
        cache.guardar(cache.chave(str(i), "m", "v1"), "T", "neutro")
    assert cache.limpar() == 5
    assert cache.contar() == 0


def test_o_texto_da_resposta_nunca_e_gravado_em_disco(tmp_path):
    caminho = tmp_path / "c.db"
    cache = CacheClassificacao(caminho)
    segredo = "A gerente [PESSOA_1] cobra metas absurdas no setor de Joinville"
    cache.guardar(cache.chave(segredo, "m", "v1"), "Liderança", "negativo")
    bruto = caminho.read_bytes()
    assert b"Joinville" not in bruto and b"metas absurdas" not in bruto
    colunas = [c[1] for c in sqlite3.connect(caminho).execute("PRAGMA table_info(classificacao)")]
    assert colunas == ["chave", "tema", "sentimento", "criado_em"]


def test_purga_periodica_roda_sozinha_e_para(tmp_path):
    relogio = Relogio()
    cache = CacheClassificacao(tmp_path / "c.db", ttl_dias=1, agora=relogio)
    cache.guardar(cache.chave("x", "m", "v1"), "T", "neutro")
    relogio.avancar_dias(2)
    thread, parar = iniciar_purga_periodica(cache, intervalo_s=0.05)
    prazo = time.time() + 3
    while cache.contar() and time.time() < prazo:
        time.sleep(0.02)
    parar.set()
    thread.join(timeout=2)
    assert cache.contar() == 0
    assert not thread.is_alive()
