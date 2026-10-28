import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    db_path: Path
    modelo: str
    api_key: str | None
    max_iteracoes: int


def carregar_config() -> Config:
    load_dotenv()
    db_path = Path(os.environ.get("ESTOQUE_DB_PATH", "data/estoque.db"))
    modelo = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5-5")
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key == "":
        api_key = None
    max_iteracoes_raw = os.environ.get("MAX_ITERACOES", "5")
    try:
        max_iteracoes = int(max_iteracoes_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("MAX_ITERACOES deve ser um numero inteiro valido") from exc
    return Config(db_path=db_path, modelo=modelo, api_key=api_key, max_iteracoes=max_iteracoes)
