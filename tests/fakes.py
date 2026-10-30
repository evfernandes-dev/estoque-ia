class FakeBlock:
    def __init__(self, *args, **kwargs):
        if args:
            self.type = args[0]
        else:
            self.type = kwargs.get("type")
        for chave, valor in kwargs.items():
            setattr(self, chave, valor)
        if not hasattr(self, "type") and args:
            self.type = args[0]


class FakeResponse:
    def __init__(self, stop_reason, content):
        self.stop_reason = stop_reason
        self.content = content


class FakeLLM:
    """Formato antigo, usado em testes de roteamento."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.chamadas = []

    def criar_mensagem(self, **kwargs):
        self.chamadas.append(kwargs)
        if not self.responses:
            return FakeResponse("end_turn", [FakeBlock("text", text="Sem resposta")])
        return self.responses.pop(0)


class FakeOllama:
    """Simula o /api/chat do Ollama sem rede."""

    def __init__(self, respostas):
        self.respostas = list(respostas)
        self.chamadas = []

    def criar_mensagem(self, **kwargs):
        self.chamadas.append(kwargs)
        if not self.respostas:
            return {"message": {"role": "assistant", "content": "Sem resposta"}}
        return self.respostas.pop(0)


def resposta_texto(texto):
    return {"message": {"role": "assistant", "content": texto}}


def resposta_ferramenta(nome, argumentos):
    return {
        "message": {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"function": {"name": nome, "arguments": argumentos}}],
        }
    }
