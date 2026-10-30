from datetime import date

from estoque_ia.agente import Agente
from tests.fakes import FakeBlock, FakeLLM, FakeResponse


def test_roteamento_itens_vencendo(conn):
    llm = FakeLLM([FakeResponse("end_turn", [FakeBlock("text", text="x")])])
    ag = Agente(conn, llm, modelo="m", hoje=date(2026, 6, 15))
    r = ag.perguntar("O que vence nos próximos 30 dias?")
    assert len(r.ferramentas_usadas) == 1
    assert r.ferramentas_usadas[0].nome == "itens_vencendo"
    assert "paracetamol" in r.texto.lower() or "vencendo" in r.texto.lower()


def test_roteamento_itens_vencidos(conn):
    llm = FakeLLM([FakeResponse("end_turn", [FakeBlock("text", text="x")])])
    ag = Agente(conn, llm, modelo="m", hoje=date(2026, 6, 15))
    r = ag.perguntar("Quais lotes ja venceram?")
    assert len(r.ferramentas_usadas) == 1
    assert r.ferramentas_usadas[0].nome == "itens_vencidos"


def test_roteamento_abaixo_minimo(conn):
    llm = FakeLLM([FakeResponse("end_turn", [FakeBlock("text", text="x")])])
    ag = Agente(conn, llm, modelo="m", hoje=date(2026, 6, 15))
    r = ag.perguntar("Quais medicamentos estao abaixo do estoque minimo?")
    assert len(r.ferramentas_usadas) == 1
    assert r.ferramentas_usadas[0].nome == "abaixo_do_minimo"
