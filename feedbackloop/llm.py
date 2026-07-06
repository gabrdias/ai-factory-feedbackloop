# Interface fina com o LLM.
# (Rafael)
#
# A graça aqui é que TODO o resto do código só conhece o método `.completar()`.
# Isso deixa o pipeline testável sem chamar a API de verdade: nos testes a gente
# passa um cliente fake (um dublê) que devolve respostas fixas. Ver tests/.
#
# Hoje só tem implementação pra OpenAI. Pra trocar pro Claude
# (um modelo Haiku da Anthropic) seria mais ou menos:
#
#     from anthropic import Anthropic
#     resp = Anthropic().messages.create(model="<modelo-haiku-da-anthropic>", ...)
#
# ...mas não cheguei a fazer. Fica de TODO pra quem assumir.

import os

# TODO: modelo hardcoded. Devia vir do .env junto com temperatura. (Rafael)
MODELO_PADRAO = "gpt-5.4-mini"


class ClienteLLM:
    """Wrapper minimalista em cima do SDK da OpenAI.

    O construtor já lê a chave do ambiente sem nenhum fallback bonitinho:
    se não tiver OPENAI_API_KEY setada, quebra na hora. (planted: segredo cru)
    """

    def __init__(self, modelo: str = MODELO_PADRAO):
        # import tardio: assim os testes conseguem importar o módulo sem ter
        # o pacote openai instalado nem chave configurada.
        from openai import OpenAI

        self.modelo = modelo
        self._client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    def completar(self, system: str, user: str, temperatura: float = 0.2) -> str:
        """Manda um par (system, user) e devolve o texto da resposta."""
        completion = self._client.chat.completions.create(
            model=self.modelo,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperatura,
        )
        return completion.choices[0].message.content or ""
