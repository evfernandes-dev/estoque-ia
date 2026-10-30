from estoque_ia.texto import normalizar


def test_normalizar_remove_acento_e_caixa():
    assert normalizar("Ácido Fólico") == "acido folico"


def test_normalizar_remove_espacos_das_bordas():
    assert normalizar("  Dipirona  ") == "dipirona"


def test_normalizar_entrada_vazia():
    assert normalizar(None) == ""
    assert normalizar("") == ""
