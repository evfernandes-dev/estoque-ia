import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    db_path: Path
    modelo: str
    ollama_base_url: str
    max_iteracoes: int
    api_token: str | None = None


def carregar_config() -> Config:
    """Lê o .env uma vez; variável de ambiente já definida tem prioridade."""
    load_dotenv()

    # Caminho relativo é resolvido a partir da pasta onde o comando rodou.
    db_path = Path(os.environ.get("ESTOQUE_DB_PATH", "data/estoque.db"))

    modelo = os.environ.get("OLLAMA_MODEL", "llama3.2:1b").strip()
    if not modelo:
        modelo = "llama3.2:1b"

    ollama_base_url = (
        os.environ.get(
            "OLLAMA_BASE_URL",
            "http://localhost:11434",
        )
        .strip()
        .rstrip("/")
    )

    if not ollama_base_url:
        ollama_base_url = "http://localhost:11434"

    # Token vazio no .env é o mesmo que "sem token".
    api_token = os.environ.get("API_TOKEN") or None

    max_iteracoes_raw = os.environ.get("MAX_ITERACOES", "5")

    try:
        max_iteracoes = int(max_iteracoes_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("MAX_ITERACOES deve ser um numero inteiro valido") from exc

    if max_iteracoes < 1:
        raise ValueError("MAX_ITERACOES deve ser maior que zero")

    return Config(
        db_path=db_path,
        modelo=modelo,
        ollama_base_url=ollama_base_url,
        max_iteracoes=max_iteracoes,
        api_token=api_token,
    )
