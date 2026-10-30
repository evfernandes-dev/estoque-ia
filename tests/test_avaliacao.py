import json
from pathlib import Path

from estoque_ia.avaliacao import (
    avaliar_offline,
    avaliar_online,
    carregar_casos,
    gerar_relatorio_markdown,
    main,
)
from tests.fakes import FakeOllama, resposta_ferramenta, resposta_texto

RAIZ = Path(__file__).resolve().parents[1]
CASOS = RAIZ / "avaliacao" / "casos.json"


def test_casos_reais_carregam():
    casos = carregar_casos(CASOS)
    assert len(casos) == 12
    assert len({caso["id"] for caso in casos}) == 12


def test_avaliacao_offline_passa_em_todos():
    resultados = avaliar_offline(carregar_casos(CASOS))
    assert all(resultado["passou"] for resultado in resultados)


def test_carregar_casos_rejeita_ferramenta_desconhecida(tmp_path):
    caminho = tmp_path / "casos.json"
    caminho.write_text(
        json.dumps(
            [
                {
                    "id": "x",
                    "pergunta": "x",
                    "ferramenta_esperada": "inexistente",
                    "argumentos_esperados": {},
                    "fatos_ferramenta": [],
                    "termos_resposta": [],
                }
            ]
        ),
        encoding="utf-8",
    )
    try:
        carregar_casos(caminho)
        raise AssertionError("deveria falhar")
    except ValueError:
        pass


def test_carregar_casos_rejeita_id_repetido(tmp_path):
    caso = {
        "id": "x",
        "pergunta": "x",
        "ferramenta_esperada": None,
        "argumentos_esperados": {},
        "fatos_ferramenta": [],
        "termos_resposta": [],
    }
    caminho = tmp_path / "casos.json"
    caminho.write_text(json.dumps([caso, dict(caso)]), encoding="utf-8")
    try:
        carregar_casos(caminho)
        raise AssertionError("deveria falhar")
    except ValueError:
        pass


def test_carregar_casos_rejeita_campo_faltando(tmp_path):
    caminho = tmp_path / "casos.json"
    caminho.write_text(json.dumps([{"id": "x"}]), encoding="utf-8")
    try:
        carregar_casos(caminho)
        raise AssertionError("deveria falhar")
    except ValueError:
        pass


def test_avaliacao_online_ferramenta_certa_passa():
    caso = {
        "id": "vencendo",
        "pergunta": "O que vence nos proximos 30 dias?",
        "ferramenta_esperada": "itens_vencendo",
        "argumentos_esperados": {"dias": 30},
        "fatos_ferramenta": [],
        "termos_resposta": ["Paracetamol"],
    }
    cliente = FakeOllama(
        [
            resposta_ferramenta("itens_vencendo", {"dias": 30}),
            resposta_texto("Encontrei Paracetamol e Losartana."),
        ]
    )
    resultados = avaliar_online([caso], cliente, "fake", usar_roteamento=False)
    assert resultados[0]["passou"]
    assert resultados[0]["ferramentas"] == ["itens_vencendo"]


def test_avaliacao_online_ferramenta_errada_falha():
    caso = {
        "id": "vencidos",
        "pergunta": "Quais lotes ja venceram?",
        "ferramenta_esperada": "itens_vencidos",
        "argumentos_esperados": {},
        "fatos_ferramenta": [],
        "termos_resposta": [],
    }
    cliente = FakeOllama(
        [
            resposta_ferramenta("buscar_medicamento", {"nome": "ibuprofeno"}),
            resposta_texto("Ibuprofeno."),
        ]
    )
    resultados = avaliar_online([caso], cliente, "fake", usar_roteamento=False)
    assert not resultados[0]["passou"]
    assert any("ferramenta" in falha for falha in resultados[0]["falhas"])


def test_avaliacao_online_caso_nulo_com_ferramenta_falha():
    caso = {
        "id": "fora",
        "pergunta": "Qual a capital da Franca?",
        "ferramenta_esperada": None,
        "argumentos_esperados": {},
        "fatos_ferramenta": [],
        "termos_resposta": [],
    }
    cliente = FakeOllama(
        [
            resposta_ferramenta("resumo_estoque", {}),
            resposta_texto("Nao sei."),
        ]
    )
    resultados = avaliar_online([caso], cliente, "fake", usar_roteamento=False)
    assert not resultados[0]["passou"]
    assert "ferramenta usada quando nao esperada" in resultados[0]["falhas"]


def test_avaliacao_online_termo_ausente_falha():
    caso = {
        "id": "busca",
        "pergunta": "Quanto temos de Dipirona?",
        "ferramenta_esperada": "buscar_medicamento",
        "argumentos_esperados": {"nome": "dipirona"},
        "fatos_ferramenta": [],
        "termos_resposta": ["Dipirona"],
    }
    cliente = FakeOllama(
        [
            resposta_ferramenta("buscar_medicamento", {"nome": "dipirona"}),
            resposta_texto("Encontrei o item."),
        ]
    )
    resultados = avaliar_online([caso], cliente, "fake", usar_roteamento=False)
    assert not resultados[0]["passou"]
    assert any("termo ausente" in falha for falha in resultados[0]["falhas"])


def test_relatorio_tem_taxa_e_uma_linha_por_caso():
    resultados = avaliar_offline(carregar_casos(CASOS))
    relatorio = gerar_relatorio_markdown(resultados, "offline", "offline")
    assert "Taxa de acerto" in relatorio
    for caso in carregar_casos(CASOS):
        assert f"| {caso['id']} |" in relatorio


def test_main_offline_retorna_zero():
    assert main(["--casos", str(CASOS)]) == 0


def test_main_online_sem_ollama_retorna_dois(monkeypatch):
    class ClienteIndisponivel:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("Ollama indisponivel")

    monkeypatch.setattr("estoque_ia.avaliacao.ClienteOllama", ClienteIndisponivel)
    assert main(["--casos", str(CASOS), "--online"]) == 2


def test_main_grava_relatorio(tmp_path):
    saida = tmp_path / "avaliacao.md"
    assert main(["--casos", str(CASOS), "--saida", str(saida)]) == 0
    assert saida.exists()
    assert "Taxa de acerto" in saida.read_text(encoding="utf-8")
