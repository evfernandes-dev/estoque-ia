import sqlite3
from datetime import date

from estoque_ia.db import conectar, criar_schema
from estoque_ia.seed import ABAIXO_MINIMO, SEM_SAIDA, VENCENDO_EM_30, VENCIDOS, popular

HOJE = date(2026, 6, 15)


def test_tabelas_existem(conn):
    cur = conn.cursor()
    for t in ["medicamentos", "lotes", "movimentacoes"]:
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (t,))
        assert cur.fetchone() is not None


def test_fk_invalida_gera_integrityerror(conn):
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO lotes(medicamento_id,numero_lote,quantidade,validade) "
            "VALUES(999,'X',1,'2026-01-01')"
        )
        conn.commit()
        raise AssertionError
    except sqlite3.IntegrityError:
        conn.rollback()


def test_tipo_invalido_movimentacao_gera_integrityerror(conn):
    cur = conn.cursor()
    cur.execute("SELECT id FROM medicamentos LIMIT 1")
    mid = cur.fetchone()["id"]
    try:
        cur.execute(
            "INSERT INTO movimentacoes(medicamento_id,tipo,quantidade,data) VALUES(?,?,?,?)",
            (mid, "errado", 1, HOJE.isoformat()),
        )
        conn.commit()
        raise AssertionError
    except sqlite3.IntegrityError:
        conn.rollback()


def test_exatamente_30_medicamentos(conn):
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as c FROM medicamentos")
    assert cur.fetchone()["c"] == 30


def test_abaixo_do_minimo(conn):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT m.nome, m.estoque_minimo, COALESCE(SUM(l.quantidade), 0) as total
        FROM medicamentos m
        LEFT JOIN lotes l ON l.medicamento_id = m.id
        GROUP BY m.id
        """
    )
    abaixo = []
    for row in cur.fetchall():
        if row["total"] < row["estoque_minimo"]:
            abaixo.append(row["nome"])
    assert set(ABAIXO_MINIMO).issubset(set(abaixo))


def test_vencendo_em_ate_30_dias(conn):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT m.nome
        FROM lotes l
        JOIN medicamentos m ON m.id = l.medicamento_id
        WHERE l.validade >= ? AND l.validade <= ?
        """,
        (HOJE.isoformat(), date.fromordinal(HOJE.toordinal() + 30).isoformat()),
    )
    nomes = {row["nome"] for row in cur.fetchall()}
    for n in VENCENDO_EM_30:
        assert n in nomes


def test_lotes_vencidos_com_estoque(conn):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT m.nome
        FROM lotes l
        JOIN medicamentos m ON m.id = l.medicamento_id
        WHERE l.validade < ? AND l.quantidade > 0
        """,
        (HOJE.isoformat(),),
    )
    nomes = {row["nome"] for row in cur.fetchall()}
    for n in VENCIDOS:
        assert n in nomes


def test_sem_saida_ha_pelo_menos_90_dias(conn):
    cur = conn.cursor()
    for nome in SEM_SAIDA:
        cur.execute("SELECT id FROM medicamentos WHERE nome=?", (nome,))
        mid = cur.fetchone()["id"]
        cur.execute(
            "SELECT MAX(data) as ultima FROM movimentacoes WHERE medicamento_id=? AND tipo='saida'",
            (mid,),
        )
        ultima = cur.fetchone()["ultima"]
        assert ultima is not None
        assert (HOJE - date.fromisoformat(ultima)).days >= 90


def test_nenhuma_movimentacao_futura(conn):
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as c FROM movimentacoes WHERE data > ?", (HOJE.isoformat(),))
    assert cur.fetchone()["c"] == 0


def test_determinismo_mesma_semente(conn):
    c1 = conectar(":memory:")
    criar_schema(c1)
    popular(c1, HOJE, semente=42)
    dump1 = "\n".join(c1.iterdump())
    c1.close()
    c2 = conectar(":memory:")
    criar_schema(c2)
    popular(c2, HOJE, semente=42)
    dump2 = "\n".join(c2.iterdump())
    c2.close()
    assert dump1 == dump2


def test_sementes_diferentes_geram_dumps_diferentes():
    c1 = conectar(":memory:")
    criar_schema(c1)
    popular(c1, HOJE, semente=42)
    dump1 = "\n".join(c1.iterdump())
    c1.close()
    c2 = conectar(":memory:")
    criar_schema(c2)
    popular(c2, HOJE, semente=43)
    dump2 = "\n".join(c2.iterdump())
    c2.close()
    assert dump1 != dump2
