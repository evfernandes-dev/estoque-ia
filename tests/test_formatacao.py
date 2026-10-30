from estoque_ia.formatacao import data_br, formatar_dados_ferramenta


def test_data_br():
    assert data_br("2026-06-15") == "15/06/2026"
    assert data_br(None) == "-"
    assert data_br("15/06/2026") == "15/06/2026"


def test_formatar_itens_vencendo_usa_data_brasileira():
    dados = {
        "dias": 30,
        "data_limite": "2026-07-15",
        "itens": [
            {
                "medicamento": "Paracetamol",
                "concentracao": "500 mg",
                "numero_lote": "L123456",
                "quantidade": 10,
                "validade": "2026-06-23",
                "dias_restantes": 8,
            }
        ],
    }

    texto = formatar_dados_ferramenta("itens_vencendo", dados)

    assert "15/07/2026" in texto
    assert "23/06/2026" in texto
    assert "Paracetamol" in texto


def test_formatar_lista_vazia():
    texto = formatar_dados_ferramenta("itens_vencidos", {"itens": [], "total_lotes": 0})
    assert "Nenhum lote vencido" in texto
