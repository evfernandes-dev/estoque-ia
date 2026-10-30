from datetime import date

import pytest

from estoque_ia.db import conectar, criar_schema
from estoque_ia.seed import popular

HOJE = date(2026, 6, 15)


@pytest.fixture
def conn():
    c = conectar(":memory:")
    criar_schema(c)
    popular(c, HOJE)
    try:
        yield c
    finally:
        c.close()
