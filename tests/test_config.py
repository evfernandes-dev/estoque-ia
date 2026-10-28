from pathlib import Path

from estoque_ia.config import carregar_config


def test_valores_padrao(monkeypatch):
    monkeypatch.delenv("ESTOQUE_DB_PATH", raising=False)
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("MAX_ITERACOES", raising=False)
    config = carregar_config()
    assert config.db_path == Path("data/estoque.db")
    assert config.modelo == "claude-sonnet-5-5"
    assert config.api_key is None
    assert config.max_iteracoes == 5


def test_sobrescrita_por_variavel_de_ambiente(monkeypatch):
    monkeypatch.setenv("ESTOQUE_DB_PATH", "meu/estoque.db")
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-haiku")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-teste")
    monkeypatch.setenv("MAX_ITERACOES", "10")
    config = carregar_config()
    assert config.db_path == Path("meu/estoque.db")
    assert config.modelo == "claude-haiku"
    assert config.api_key == "sk-teste"
    assert config.max_iteracoes == 10


def test_ausencia_de_chave_sem_erro(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    config = carregar_config()
    assert config.api_key is None


def test_max_iteracoes_invalido_gera_valueerror(monkeypatch):
    monkeypatch.setenv("MAX_ITERACOES", "abc")
    try:
        carregar_config()
        raise AssertionError("Deveria ter gerado ValueError")
    except ValueError as exc:
        assert "numero inteiro" in str(exc).lower() or "inteiro" in str(exc).lower()
