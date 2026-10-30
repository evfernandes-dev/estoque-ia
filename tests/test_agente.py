import json
from datetime import date

from estoque_ia.agente import Agente, ClienteOllama, ErroAgente, criar_agente
from estoque_ia.config import Config
from estoque_ia.esquemas import EXECUTORES, FERRAMENTAS_SCHEMA, executar_ferramenta
from tests.fakes import FakeOllama, resposta_ferramenta, resposta_texto


def test_resposta_direta_sem_ferramenta(conn):
    llm = FakeOllama([resposta_texto("Tudo ok")])
    ag = Agente(conn, llm, modelo="m", hoje=date(2026, 6, 15))

    r = ag.perguntar("oi")

    assert r.texto == "Tudo ok"
    assert len(r.ferramentas_usadas) == 0
    assert len(llm.chamadas) == 1


def test_fluxo_tool_call(conn):
    llm = FakeOllama(
        [
            resposta_ferramenta("itens_vencendo", {"dias": 30}),
            resposta_texto("Vencem 4"),
        ]
    )

    ag = Agente(conn, llm, modelo="m", hoje=date(2026, 6, 15))
    r = ag.perguntar("O que vence?")

    assert r.texto == "Vencem 4"
    assert len(r.ferramentas_usadas) == 1
    assert r.ferramentas_usadas[0].nome == "itens_vencendo"

    msgs = llm.chamadas[1]["messages"]

    assert msgs[1]["role"] == "assistant"
    assert msgs[2]["role"] == "tool"

    data = json.loads(msgs[2]["content"])
    assert data["total_lotes"] == 4


def test_duas_tool_calls_na_mesma_resposta(conn):
    llm = FakeOllama(
        [
            {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "itens_vencidos",
                                "arguments": {},
                            }
                        },
                        {
                            "function": {
                                "name": "abaixo_do_minimo",
                                "arguments": {},
                            }
                        },
                    ],
                }
            },
            resposta_texto("Consulta concluida"),
        ]
    )

    ag = Agente(conn, llm, modelo="m", hoje=date(2026, 6, 15))
    ag.perguntar("Consulte os itens")

    mensagens = llm.chamadas[1]["messages"]
    mensagens_tool = [m for m in mensagens if m["role"] == "tool"]

    assert len(mensagens_tool) == 2


def test_erros_ferramenta_continuam(conn):
    llm = FakeOllama(
        [
            resposta_ferramenta("naoexiste", {}),
            resposta_texto("Fim"),
        ]
    )

    ag = Agente(conn, llm, modelo="m", hoje=date(2026, 6, 15))
    r = ag.perguntar("x")

    assert r.ferramentas_usadas[0].erro is True
    assert ag.cliente.chamadas[1]["messages"][2]["role"] == "tool"
    assert ag.cliente.chamadas[1]["messages"][2]["content"]
    assert ag.cliente.chamadas[0]["tools"] == FERRAMENTAS_SCHEMA


def test_limite_iteracoes(conn):
    llm = FakeOllama([resposta_ferramenta("itens_vencidos", {}) for _ in range(10)])

    ag = Agente(
        conn,
        llm,
        modelo="m",
        max_iteracoes=3,
        hoje=date(2026, 6, 15),
    )

    r = ag.perguntar("x")

    assert r.incompleta is True
    assert len(llm.chamadas) == 3


def test_perguntas_invalidas(conn):
    llm = FakeOllama([])
    ag = Agente(conn, llm, modelo="m", hoje=date(2026, 6, 15))

    try:
        ag.perguntar("")
        raise AssertionError
    except ValueError:
        pass

    try:
        ag.perguntar("a" * 1001)
        raise AssertionError
    except ValueError:
        pass

    assert len(llm.chamadas) == 0


def test_system_tem_data_e_regras(conn):
    llm = FakeOllama([resposta_texto("ok")])
    ag = Agente(conn, llm, modelo="m", hoje=date(2026, 6, 15))

    ag.perguntar("x")

    system = llm.chamadas[0]["system"]

    assert "2026-06-15" in system
    assert "somente leitura" in system
    assert "nunca inventar" in system


def test_esquemas_e_executores_coerentes():
    assert set(EXECUTORES.keys()) == set([t["name"] for t in FERRAMENTAS_SCHEMA])

    for ferramenta in FERRAMENTAS_SCHEMA:
        for req in ferramenta["input_schema"].get("required", []):
            assert req in ferramenta["input_schema"]["properties"]

    json.dumps(FERRAMENTAS_SCHEMA)


def test_executar_ferramenta_todas(conn):
    for nome in EXECUTORES:
        if nome == "buscar_medicamento":
            executar_ferramenta(
                conn,
                nome,
                {"nome": "dipirona"},
                hoje=date(2026, 6, 15),
            )
        elif nome in ["itens_vencendo", "sem_saida"]:
            executar_ferramenta(
                conn,
                nome,
                {"dias": 30},
                hoje=date(2026, 6, 15),
            )
        elif nome == "consumo_medio":
            executar_ferramenta(
                conn,
                nome,
                {"nome": "Losartana", "meses": 3},
                hoje=date(2026, 6, 15),
            )
        else:
            executar_ferramenta(
                conn,
                nome,
                {},
                hoje=date(2026, 6, 15),
            )


def test_criar_agente_sem_banco(tmp_path):
    cfg = Config(
        db_path=tmp_path / "naoexiste.db",
        modelo="llama3.2:1b",
        ollama_base_url="http://localhost:11434",
        max_iteracoes=5,
    )

    try:
        criar_agente(cfg)
        raise AssertionError
    except ErroAgente:
        pass


def test_cliente_ollama_chamadas(monkeypatch):
    class FakeHTTPResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self):
            return json.dumps({"message": {"role": "assistant", "content": "ok"}}).encode("utf-8")

    captura = {}

    def fake_urlopen(request, timeout):
        captura["request"] = request
        captura["timeout"] = timeout
        return FakeHTTPResponse()

    monkeypatch.setattr("estoque_ia.agente.urlopen", fake_urlopen)

    cli = ClienteOllama(base_url="http://localhost:11434")

    r = cli.criar_mensagem(
        model="llama3.2:1b",
        system="sistema",
        messages=[{"role": "user", "content": "oi"}],
        tools=FERRAMENTAS_SCHEMA,
        max_tokens=100,
    )

    assert r["message"]["content"] == "ok"

    requisicao = captura["request"]

    assert requisicao.full_url == "http://localhost:11434/api/chat"
    assert captura["timeout"] == 120

    payload = json.loads(requisicao.data.decode("utf-8"))

    assert payload["model"] == "llama3.2:1b"
    assert payload["stream"] is False
    assert payload["messages"][0]["role"] == "system"
    assert payload["messages"][1]["role"] == "user"
    assert payload["tools"][0]["function"]["name"] == FERRAMENTAS_SCHEMA[0]["name"]
