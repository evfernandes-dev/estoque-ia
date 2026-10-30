import unicodedata


def normalizar(texto: str | None) -> str:
    """Deixa o texto comparável: sem acento, sem caixa e sem espaços sobrando."""
    if not texto:
        return ""
    # NFKD separa a letra do acento; depois a gente joga fora só os acentos.
    decomposto = unicodedata.normalize("NFKD", str(texto))
    sem_acento = "".join(c for c in decomposto if not unicodedata.combining(c))
    return sem_acento.strip().casefold()
