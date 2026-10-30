import re
from pathlib import Path

from estoque_ia.esquemas import FERRAMENTAS_SCHEMA

RAIZ = Path(__file__).resolve().parents[1]
README = RAIZ / "README.md"


def test_readme_existe():
    assert README.exists()


def test_readme_lista_todas_as_ferramentas():
    texto = README.read_text(encoding="utf-8")
    for ferramenta in FERRAMENTAS_SCHEMA:
        assert ferramenta["name"] in texto


def test_readme_tem_aviso_de_dados_ficticios():
    texto = README.read_text(encoding="utf-8").lower()
    assert "fict" in texto
    assert "dados" in texto


def test_readme_nao_contem_chave_de_api():
    texto = README.read_text(encoding="utf-8")
    assert not re.search(r"sk-ant-[A-Za-z0-9_-]+", texto)


def test_links_relativos_do_readme_existem():
    texto = README.read_text(encoding="utf-8")
    for destino in re.findall(r"\]\(([^)]+)\)", texto):
        if destino.startswith(("http://", "https://", "#", "mailto:")):
            continue
        caminho = destino.split("#", 1)[0]
        assert (RAIZ / caminho).exists(), f"Link relativo quebrado: {destino}"
