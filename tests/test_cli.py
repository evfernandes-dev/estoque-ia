from datetime import date

import pytest

from estoque_ia import cli
from estoque_ia.agente import Agente, ErroAgente, ErroClienteLLM
from tests.fakes import FakeOllama


@pytest.fixture
def agente(conn):
    return Agente(
        conn,
        FakeOllama([]),
        modelo="fake",
        hoje=date(2026, 6, 15),
    )


def test_perguntar(monkeypatch, capsys, agente):
    monkeypatch.setattr(cli, "criar_agente", lambda config: agente)

    assert cli.main(["perguntar", "Quais itens estão abaixo do mínimo?"]) == 0
    assert "Dipirona" in capsys.readouterr().out


def test_perguntar_mostra_ferramentas(monkeypatch, capsys, agente):
    monkeypatch.setattr(cli, "criar_agente", lambda config: agente)

    assert (
        cli.main(["perguntar", "O que vence nos próximos 30 dias?", "--mostrar-ferramentas"]) == 0
    )
    assert "[ferramentas: itens_vencendo]" in capsys.readouterr().out


def test_chat_responde_e_sai(monkeypatch, capsys, agente):
    monkeypatch.setattr(cli, "criar_agente", lambda config: agente)
    respostas = iter(["O que vence nos próximos 30 dias?", "sair"])
    monkeypatch.setattr("builtins.input", lambda _: next(respostas))

    assert cli.main(["chat"]) == 0
    assert "Paracetamol" in capsys.readouterr().out


def test_chat_ignora_linha_vazia(monkeypatch, capsys, agente):
    monkeypatch.setattr(cli, "criar_agente", lambda config: agente)
    respostas = iter(["", "sair"])
    monkeypatch.setattr("builtins.input", lambda _: next(respostas))

    assert cli.main(["chat"]) == 0


def test_chat_encerra_com_eof(monkeypatch, agente):
    monkeypatch.setattr(cli, "criar_agente", lambda config: agente)

    def eof(_):
        raise EOFError

    monkeypatch.setattr("builtins.input", eof)

    assert cli.main(["chat"]) == 0


def test_ferramentas_nao_precisa_de_banco(monkeypatch, capsys):
    def nao_deveria_chamar(config):
        raise AssertionError("não deveria criar agente")

    monkeypatch.setattr(cli, "criar_agente", nao_deveria_chamar)

    assert cli.main(["ferramentas"]) == 0
    saida = capsys.readouterr().out
    assert "buscar_medicamento" in saida
    assert "resumo_estoque" in saida


def test_pergunta_invalida_retorna_um(monkeypatch, capsys, agente):
    monkeypatch.setattr(cli, "criar_agente", lambda config: agente)

    assert cli.main(["perguntar", "   "]) == 1
    assert "Traceback" not in capsys.readouterr().err


def test_erro_de_configuracao_retorna_dois(monkeypatch, capsys):
    def erro(config):
        raise ErroAgente("sem banco")

    monkeypatch.setattr(cli, "criar_agente", erro)

    assert cli.main(["perguntar", "oi"]) == 2
    assert "sem banco" in capsys.readouterr().err


def test_erro_do_ollama_retorna_tres(monkeypatch, capsys, conn):
    class ClienteComErro(FakeOllama):
        def criar_mensagem(self, **kwargs):
            raise ErroClienteLLM("fora do ar")

    agente = Agente(conn, ClienteComErro([]), modelo="fake", hoje=date(2026, 6, 15))
    monkeypatch.setattr(cli, "criar_agente", lambda config: agente)

    assert cli.main(["perguntar", "Oi"]) == 3
    erro = capsys.readouterr().err
    assert "Ollama" in erro
    assert "Traceback" not in erro
