import json
from datetime import date

from estoque_ia.db import conectar, criar_schema
from estoque_ia.ferramentas import (
    ErroFerramenta,
    abaixo_do_minimo,
    buscar_medicamento,
    consumo_medio,
    itens_vencendo,
    itens_vencidos,
    resumo_estoque,
    sem_saida,
)
from estoque_ia.seed import popular

HOJE = date(2026, 6, 15)


def test_buscar_medicamento_variacoes(conn):
    r1 = buscar_medicamento(conn, "dipirona", hoje=HOJE)
    assert r1["encontrado"] is True
    assert any(m["nome"] == "Dipirona" for m in r1["medicamentos"])
    r2 = buscar_medicamento(conn, "DIPIRONA", hoje=HOJE)
    assert r2["encontrado"] is True
    r3 = buscar_medicamento(conn, "dipi", hoje=HOJE)
    assert r3["encontrado"] is True


def test_buscar_acento(conn):
    r = buscar_medicamento(conn, "acido folico", hoje=HOJE)
    assert r["encontrado"] is True
    assert any(
        "folic" in m["nome"].lower()
        or "acido" in m["nome"].lower()
        or "Ácido" in m["nome"]
        or "Acido" in m["nome"]
        for m in r["medicamentos"]
    )


def test_buscar_inexistente(conn):
    r = buscar_medicamento(conn, "medicamento_que_nao_existe_xyz", hoje=HOJE)
    assert r["encontrado"] is False
    assert r["medicamentos"] == []


def test_buscar_sql_injection_sem_efeito(conn):
    r = buscar_medicamento(conn, "'; DROP TABLE medicamentos; --", hoje=HOJE)
    assert r["encontrado"] is False
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as c FROM medicamentos")
    assert cur.fetchone()["c"] == 30


def test_buscar_vazio_gera_erro(conn):
    try:
        buscar_medicamento(conn, "", hoje=HOJE)
        raise AssertionError
    except ErroFerramenta:
        pass
    try:
        buscar_medicamento(conn, "   ", hoje=HOJE)
        raise AssertionError
    except ErroFerramenta:
        pass


def test_buscar_limite_5(conn):
    r = buscar_medicamento(conn, "a", hoje=HOJE)
    assert len(r["medicamentos"]) <= 5
    assert r["total_correspondencias"] >= len(r["medicamentos"])


def test_itens_vencendo_30(conn):
    r = itens_vencendo(conn, dias=30, hoje=HOJE)
    assert r["dias"] == 30
    assert r["total_lotes"] == 4
    nomes = [i["medicamento"] for i in r["itens"]]
    for n in ["Paracetamol", "Losartana", "Omeprazol", "Metformina"]:
        assert n in nomes
    vals = [i["validade"] for i in r["itens"]]
    assert vals == sorted(vals)


def test_itens_vencendo_validacao(conn):
    for bad in [0, 366, "30"]:
        try:
            itens_vencendo(conn, dias=bad, hoje=HOJE)
            raise AssertionError
        except ErroFerramenta:
            pass


def test_itens_vencendo_365(conn):
    r = itens_vencendo(conn, dias=365, hoje=HOJE)
    assert r["total_lotes"] >= 4
    for i in r["itens"]:
        assert date.fromisoformat(i["validade"]) >= HOJE


def test_itens_vencidos(conn):
    r = itens_vencidos(conn, hoje=HOJE)
    assert r["total_lotes"] == 2
    nomes = [i["medicamento"] for i in r["itens"]]
    for n in ["Ibuprofeno", "Nistatina"]:
        assert n in nomes
    for i in r["itens"]:
        assert i["dias_vencido"] > 0


def test_abaixo_do_minimo(conn):
    r = abaixo_do_minimo(conn)
    nomes = [i["medicamento"] for i in r["itens"]]
    for n in ["Dipirona", "Amoxicilina", "Insulina NPH"]:
        assert n in nomes
    for i in r["itens"]:
        assert i["falta"] == i["estoque_minimo"] - i["estoque_atual"]


def test_consumo_medio_normal(conn):
    r = consumo_medio(conn, "Losartana", meses=3, hoje=HOJE)
    assert r["encontrado"] is True
    assert r["ambiguo"] is False
    assert r["total_saidas"] >= 0


def test_consumo_medio_validacao(conn):
    for bad in [0, 13]:
        try:
            consumo_medio(conn, "Losartana", meses=bad, hoje=HOJE)
            raise AssertionError
        except ErroFerramenta:
            pass


def test_consumo_medio_ambiguo(conn):
    r = consumo_medio(conn, "a", meses=3, hoje=HOJE)
    assert r["encontrado"] is True
    assert r["ambiguo"] is True


def test_consumo_medio_inexistente(conn):
    r = consumo_medio(conn, "naoexiste123", meses=3, hoje=HOJE)
    assert r["encontrado"] is False


def test_consumo_medio_sem_saida(conn):
    r = consumo_medio(conn, "Albendazol", meses=1, hoje=HOJE)
    assert r["encontrado"] is True
    assert r["ambiguo"] is False
    assert r["total_saidas"] == 0
    assert r["autonomia_dias"] is None


def test_sem_saida_90(conn):
    r = sem_saida(conn, dias=90, hoje=HOJE)
    nomes = [i["medicamento"] for i in r["itens"]]
    for n in ["Albendazol", "Fluconazol", "Cefalexina"]:
        assert n in nomes
    for i in r["itens"]:
        if i["dias_sem_saida"] is not None:
            assert i["dias_sem_saida"] >= 90


def test_sem_saida_validacao(conn):
    try:
        sem_saida(conn, dias=1000, hoje=HOJE)
        raise AssertionError
    except ErroFerramenta:
        pass


def test_resumo_estoque(conn):
    r = resumo_estoque(conn, hoje=HOJE)
    assert r["total_medicamentos"] == 30
    assert r["abaixo_do_minimo"] == 3
    assert r["lotes_vencendo_30_dias"] == 4
    assert r["lotes_vencidos"] == 2
    assert r["sem_saida_90_dias"] == 3


def test_somente_leitura_json(conn, tmp_path):
    db = tmp_path / "t.db"
    c2 = conectar(db)
    criar_schema(c2)
    popular(c2, HOJE)
    c2.close()
    c3 = conectar(db, somente_leitura=True)
    from estoque_ia import ferramentas as f

    r = f.resumo_estoque(c3, hoje=HOJE)
    assert json.dumps(r)
    c3.close()


def test_hoje_padrao_nao_erro(conn):
    _ = buscar_medicamento(conn, "dipirona")
