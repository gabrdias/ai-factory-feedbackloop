# Interface fina com o LLM.
#
# TODO o resto do código só conhece o método `.completar()`. Isso deixa o pipeline
# testável sem chamar a API de verdade: nos testes se passa um cliente fake.
#
# Etapa 2: este é o ÚNICO ponto por onde texto sai do sistema para o provedor, então
# é aqui que ficam (1) a trava final de PII, (2) a instrumentação de cada chamada
# (span + latência + tokens + custo + erro) e (3) timeout/retry.
#
# Para trocar de provedor (ex.: Claude Haiku da Anthropic) basta outra classe com o
# mesmo método `.completar()`; ver docs/adr/0001-escolha-do-prototipo-e-stack.md.

import os
import time

from . import config as configuracao
from . import observabilidade as obs
from .pii import PIIDetectadaError, garantir_sem_pii

MODELO_PADRAO = "gpt-5.4-mini"  # sobrescrito por OPENAI_MODEL


class ClienteLLM:
    """Wrapper em cima do SDK da OpenAI, instrumentado e com trava de PII."""

    def __init__(self, modelo: str | None = None, cfg: "configuracao.Config | None" = None):
        # import tardio: os testes importam o módulo sem ter chave configurada.
        from openai import OpenAI

        self._cfg = cfg or configuracao.carregar()
        self.modelo = modelo or self._cfg.modelo or MODELO_PADRAO
        # Sem valor padrão para a chave: se faltar, quebra na hora (KeyError tratado no app).
        # `max_retries` do SDK já faz backoff exponencial com jitter em 408/409/429/5xx.
        self._client = OpenAI(
            api_key=os.environ["OPENAI_API_KEY"],
            timeout=self._cfg.timeout_s,
            max_retries=self._cfg.max_retries,
        )

    def _custo(self, tokens_entrada: int, tokens_saida: int) -> float:
        pe, ps = self._cfg.preco_entrada_usd_por_mtok, self._cfg.preco_saida_usd_por_mtok
        if pe is None or ps is None:
            return 0.0
        return (tokens_entrada * pe + tokens_saida * ps) / 1_000_000

    def completar(self, system: str, user: str, temperatura: float = 0.2) -> str:
        """Manda um par (system, user) e devolve o texto da resposta."""
        operacao = obs.operacao_corrente.get()
        base = obs.attrs(operacao=operacao)

        try:
            garantir_sem_pii(user)
        except PIIDetectadaError:
            obs.inst().pii_bloqueios.add(1, base)
            raise

        with obs.tracer().start_as_current_span("llm.chamada") as span:
            span.set_attribute("gen_ai.system", "openai")
            span.set_attribute("gen_ai.operation.name", "chat")
            span.set_attribute("gen_ai.request.model", self.modelo)
            span.set_attribute("feedbackloop.operacao", operacao)
            inicio = time.perf_counter()
            try:
                completion = self._client.chat.completions.create(
                    model=self.modelo,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    temperature=temperatura,
                )
            except Exception as exc:
                duracao = time.perf_counter() - inicio
                tipo = type(exc).__name__
                span.set_attribute("feedbackloop.tipo_erro", tipo)
                i = obs.inst()
                i.llm_chamadas.add(1, {**base, "resultado": "erro", "tipo_erro": tipo})
                i.llm_duracao.record(duracao, {**base, "resultado": "erro"})
                uso = obs.uso_corrente.get()
                if uso is not None:
                    uso.registrar(erro=True)
                raise

            duracao = time.perf_counter() - inicio
            usage = getattr(completion, "usage", None)
            tok_in = int(getattr(usage, "prompt_tokens", 0) or 0)
            tok_out = int(getattr(usage, "completion_tokens", 0) or 0)
            custo = self._custo(tok_in, tok_out)

            span.set_attribute("gen_ai.usage.input_tokens", tok_in)
            span.set_attribute("gen_ai.usage.output_tokens", tok_out)
            span.set_attribute("feedbackloop.custo_usd", custo)

            i = obs.inst()
            i.llm_chamadas.add(1, {**base, "resultado": "ok"})
            i.llm_duracao.record(duracao, {**base, "resultado": "ok"})
            i.llm_tokens.add(tok_in, {**base, "tipo": "entrada"})
            i.llm_tokens.add(tok_out, {**base, "tipo": "saida"})
            if custo:
                i.llm_custo.add(custo, base)
            uso = obs.uso_corrente.get()
            if uso is not None:
                uso.registrar(erro=False, tokens_entrada=tok_in, tokens_saida=tok_out, custo_usd=custo)

            return completion.choices[0].message.content or ""
