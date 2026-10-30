import sqlite3
from pathlib import Path

SCHEMA = """CREATE TABLE IF NOT EXISTS medicamentos (
    id INTEGER PRIMARY KEY,
    nome TEXT NOT NULL UNIQUE,
    concentracao TEXT NOT NULL,
    categoria TEXT NOT NULL,
    estoque_minimo INTEGER NOT NULL CHECK(estoque_minimo >= 0)
);

CREATE TABLE IF NOT EXISTS lotes (
    id INTEGER PRIMARY KEY,
    medicamento_id INTEGER NOT NULL REFERENCES medicamentos(id),
    numero_lote TEXT NOT NULL,
    quantidade INTEGER NOT NULL CHECK(quantidade >= 0),
    validade TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS movimentacoes (
    id INTEGER PRIMARY KEY,
    medicamento_id INTEGER NOT NULL REFERENCES medicamentos(id),
    tipo TEXT NOT NULL CHECK(tipo IN ('entrada','saida')),
    quantidade INTEGER NOT NULL CHECK(quantidade > 0),
    data TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_lotes_medicamento ON lotes(medicamento_id);
CREATE INDEX IF NOT EXISTS idx_lotes_validade ON lotes(validade);
CREATE INDEX IF NOT EXISTS idx_mov_medicamento_data ON movimentacoes(medicamento_id, data);
"""


def criar_schema(conn: sqlite3.Connection) -> None:
    """Cria tabelas e índices; pode rodar mais de uma vez sem quebrar."""
    conn.executescript(SCHEMA)


def conectar(caminho: str | Path, somente_leitura: bool = False) -> sqlite3.Connection:
    """Abre o SQLite com Row e foreign keys ligadas.

    Com somente_leitura=True a URI mode=ro impede qualquer escrita até no
    nível do driver, não é só convenção do código.
    """
    caminho_str = str(caminho)

    if somente_leitura:
        uri = f"file:{Path(caminho_str).as_posix()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
    else:
        # O seed pode rodar em uma pasta que ainda não existe.
        Path(caminho_str).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(caminho_str)

    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn
