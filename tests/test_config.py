from pathlib import Path

from estoque_ia.config import carregar_config


def test_valores_padrao(monkeypatch):
    monkeypatch.delenv("ESTOQUE_DB_PATH", raising=False)
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("API_TOKEN", raising=False)
    monkeypatch.delenv("MAX_ITERACOES", raising=False)

    config = carregar_config()

    assert config.db_path == Path("data/estoque.db")
    assert config.modelo == "llama3.2:1b"
    assert config.ollama_base_url == "http://localhost:11434"
    assert config.api_token is None
    assert config.max_iteracoes == 5


def test_sobrescrita_por_variavel_de_ambiente(monkeypatch):
    monkeypatch.setenv("ESTOQUE_DB_PATH", "meu/estoque.db")
    monkeypatch.setenv("OLLAMA_MODEL", "llama3.2:1b")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434/")
    monkeypatch.setenv("API_TOKEN", "abc123")
    monkeypatch.setenv("MAX_ITERACOES", "10")

    config = carregar_config()

    assert config.db_path == Path("meu/estoque.db")
    assert config.modelo == "llama3.2:1b"
    assert config.ollama_base_url == "http://localhost:11434"
    assert config.api_token == "abc123"
    assert config.max_iteracoes == 10


def test_ausencia_de_token_sem_erro(monkeypatch):
    monkeypatch.delenv("API_TOKEN", raising=False)

    config = carregar_config()

    assert config.api_token is None


def test_max_iteracoes_invalido_gera_valueerror(monkeypatch):
    monkeypatch.setenv("MAX_ITERACOES", "abc")

    try:
        carregar_config()
        raise AssertionError("Deveria ter gerado ValueError")
    except ValueError as exc:
        assert "inteiro" in str(exc).lower()


def test_max_iteracoes_zero_gera_valueerror(monkeypatch):
    monkeypatch.setenv("MAX_ITERACOES", "0")

    try:
        carregar_config()
        raise AssertionError("Deveria ter gerado ValueError")
    except ValueError as exc:
        assert "maior que zero" in str(exc).lower()


def test_api_token(monkeypatch):
    monkeypatch.delenv("API_TOKEN", raising=False)
    cfg = carregar_config()
    assert cfg.api_token is None

    monkeypatch.setenv("API_TOKEN", "")
    cfg2 = carregar_config()
    assert cfg2.api_token is None

    monkeypatch.setenv("API_TOKEN", "abc123")
    cfg3 = carregar_config()
    assert cfg3.api_token == "abc123"
