from datetime import date

from fastapi.testclient import TestClient

from estoque_ia import __version__
from estoque_ia.agente import ErroClienteLLM
from estoque_ia.api import criar_app
from estoque_ia.config import Config
from estoque_ia.db import conectar, criar_schema
from estoque_ia.seed import popular


class FakeClienteAPI:
    def __init__(self, resposta="Resposta do assistente", erro=False):
        self.resposta = resposta
        self.erro = erro
        self.chamadas = []

    def criar_mensagem(self, **kwargs):
        self.chamadas.append(kwargs)
        if self.erro:
            raise ErroClienteLLM("Falha simulada na chamada ao modelo")
        return {"message": {"role": "assistant", "content": self.resposta}}


def test_saude():
    app = criar_app()
    client = TestClient(app)
    res = client.get("/saude")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "versao": __version__}


def test_raiz_serve_html():
    app = criar_app()
    client = TestClient(app)
    res = client.get("/")
    assert res.status_code == 200
    assert "text/html" in res.headers.get("content-type", "")
    assert "Estoque IA" in res.text


def test_resumo_sem_banco(tmp_path):
    banco_inexistente = tmp_path / "inexistente.db"
    cfg = Config(
        db_path=banco_inexistente,
        modelo="test-model",
        ollama_base_url="http://localhost:11434",
        max_iteracoes=5,
    )
    app = criar_app(config=cfg)
    client = TestClient(app)
    res = client.get("/resumo")
    assert res.status_code == 503
    assert "Banco nao encontrado" in res.json().get("detail", "")


def test_resumo_com_banco(tmp_path):
    db_file = tmp_path / "estoque.db"
    conn = conectar(db_file)
    criar_schema(conn)
    popular(conn, date(2026, 6, 15))
    conn.close()

    cfg = Config(
        db_path=db_file,
        modelo="test-model",
        ollama_base_url="http://localhost:11434",
        max_iteracoes=5,
    )
    app = criar_app(config=cfg)
    client = TestClient(app)
    res = client.get("/resumo")
    assert res.status_code == 200
    dados = res.json()
    assert dados["total_medicamentos"] == 30
    assert dados["total_lotes"] > 0
    assert "abaixo_do_minimo" in dados


def test_perguntar_token_invalido_ou_ausente(tmp_path):
    db_file = tmp_path / "estoque.db"
    cfg = Config(
        db_path=db_file,
        modelo="test-model",
        ollama_base_url="http://localhost:11434",
        max_iteracoes=5,
        api_token="segredo123",
    )
    app = criar_app(config=cfg)
    client = TestClient(app)

    # Sem header
    res = client.post("/perguntar", json={"pergunta": "O que vence?"})
    assert res.status_code == 401

    # Com token incorreto
    res = client.post(
        "/perguntar",
        headers={"X-API-Token": "token-errado"},
        json={"pergunta": "O que vence?"},
    )
    assert res.status_code == 401


def test_perguntar_validacao_pergunta(tmp_path):
    db_file = tmp_path / "estoque.db"
    cfg = Config(
        db_path=db_file,
        modelo="test-model",
        ollama_base_url="http://localhost:11434",
        max_iteracoes=5,
    )
    app = criar_app(config=cfg)
    client = TestClient(app)

    # Vazio
    res = client.post("/perguntar", json={"pergunta": "   "})
    assert res.status_code == 422

    # Longo demais
    res = client.post("/perguntar", json={"pergunta": "a" * 1001})
    assert res.status_code == 422


def test_perguntar_com_roteamento(tmp_path):
    db_file = tmp_path / "estoque.db"
    conn = conectar(db_file)
    criar_schema(conn)
    popular(conn, date.today())
    conn.close()

    cfg = Config(
        db_path=db_file,
        modelo="test-model",
        ollama_base_url="http://localhost:11434",
        max_iteracoes=5,
    )
    cl = FakeClienteAPI()
    app = criar_app(config=cfg, cliente=cl)
    client = TestClient(app)

    res = client.post("/perguntar", json={"pergunta": "O que vence nos proximos 30 dias?"})
    assert res.status_code == 200
    corpo = res.json()
    assert "resposta" in corpo
    assert len(corpo["ferramentas_usadas"]) == 1
    assert corpo["ferramentas_usadas"][0]["nome"] == "itens_vencendo"
    assert corpo["incompleta"] is False


def test_perguntar_erro_ollama(tmp_path):
    db_file = tmp_path / "estoque.db"
    conn = conectar(db_file)
    criar_schema(conn)
    popular(conn, date.today())
    conn.close()

    cfg = Config(
        db_path=db_file,
        modelo="test-model",
        ollama_base_url="http://localhost:11434",
        max_iteracoes=5,
    )
    cl = FakeClienteAPI(erro=True)
    app = criar_app(config=cfg, cliente=cl)
    client = TestClient(app)

    res = client.post("/perguntar", json={"pergunta": "Qualquer pergunta fora do roteamento?"})
    assert res.status_code == 502
    assert "Erro ao consultar o Ollama" in res.json().get("detail", "")
