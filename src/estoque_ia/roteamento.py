import re

from estoque_ia.seed import MEDICAMENTOS
from estoque_ia.texto import normalizar

# Os nomes são normalizados uma vez só. Assim a gente não repete esse trabalho
# a cada pergunta e o match fica previsível.
_NOMES_ORDENADOS = tuple(
    sorted(
        ((normalizar(linha.split("|", 1)[0]), linha.split("|", 1)[0]) for linha in MEDICAMENTOS),
        key=lambda item: len(item[0]),
        reverse=True,
    )
)

PADROES_INJECAO = [
    r"ignore (suas|as) (regras|instrucoes|orientacoes)",
    r"\bapague\b",
    r"\bdelete\b",
    r"\bdrop\b",
    r"\bsenha\b",
    r"\bcredencia",
    r"\btoken\b",
]

PADROES_FORA_DE_ESCOPO = [
    r"\bcapital\b",
    r"\bpresidente\b",
    r"\bclima\b",
    r"\btempo hoje\b",
    r"\bprevisao do tempo\b",
    r"\bquem ganhou\b",
    r"\bfutebol\b",
    r"\bpiada\b",
    r"\bfilme\b",
    r"\bmusica\b",
]

PADROES_CLINICOS = [
    r"\b(dose|doses|dosagem|dosagens|posologia|posologias)\b",
    r"\b(como tomar|como usar|como aplicar)\b",
    r"\b(quantas vezes ao dia|quantas vezes por dia|de quantas em quantas horas)\b",
    r"\b(prescricao|prescricoes|prescrever|receitar|receita medica)\b",
    r"\b(diagnostico|diagnosticos|diagnosticar)\b",
    r"\b(estou sentindo|estou com dor|sintomas? de)\b",
    r"\b(o que tomar|o que e bom para|indicacao terapeutica|indicado para)\b",
    r"\b(efeito colateral|efeitos colaterais|contraindicacao|contraindicacoes)\b",
    r"\b(interacao medicamentosa|gravida pode|gestante pode|lactante pode)\b",
]


def _limitar(valor: int, minimo: int, maximo: int) -> int:
    return max(minimo, min(maximo, valor))


def _nome_conhecido(pergunta_normalizada: str) -> str | None:
    for nome_normalizado, nome_original in _NOMES_ORDENADOS:
        if nome_normalizado in pergunta_normalizada:
            return nome_original
    return None


def detectar_roteamento(pergunta: str) -> tuple[str, dict] | None:
    """Atalho para perguntas frequentes; devolve ferramenta e argumentos."""
    q = normalizar(pergunta)

    # A ordem importa: vencimento ganha de busca por nome, senão "Paracetamol
    # vencendo" cairia na busca e não na lista de vencimentos.
    if (
        re.search(r"venc\w+\s+(nos\s+)?proxim", q)
        or ("vence" in q and "proxim" in q)
        or ("vencendo" in q)
    ):
        dias = 30
        match_dias = re.findall(r"(\d+)\s*dias", q)
        match_semanas = re.findall(r"(\d+)\s*semana", q)

        if match_dias:
            dias = int(match_dias[0])
        elif match_semanas:
            dias = int(match_semanas[0]) * 7
        elif "duas semanas" in q:
            dias = 14
        elif "uma semana" in q:
            dias = 7
        elif "tres semanas" in q:
            dias = 21
        elif "quatro semanas" in q:
            dias = 28

        return ("itens_vencendo", {"dias": _limitar(dias, 1, 365)})

    if "ja venc" in q or (re.search(r"vencid\w*", q) and "proxim" not in q and "vencendo" not in q):
        return ("itens_vencidos", {})

    if "abaixo" in q and "minim" in q:
        return ("abaixo_do_minimo", {})

    if "resum" in q:
        return ("resumo_estoque", {})

    if "parad" in q or "sem said" in q:
        match_dias = re.findall(r"(\d+)\s*dias", q)
        dias = int(match_dias[0]) if match_dias else 90
        return ("sem_saida", {"dias": _limitar(dias, 1, 365)})

    if "consumo" in q or "autonomia" in q:
        match_meses = re.search(r"(\d+)\s*mes", q)
        meses = int(match_meses[1]) if match_meses else 3
        nome = _nome_conhecido(q) or pergunta.strip()
        return ("consumo_medio", {"nome": nome, "meses": _limitar(meses, 1, 12)})

    nome = _nome_conhecido(q)
    if nome:
        return ("buscar_medicamento", {"nome": nome})

    return None


def detectar_injecao(pergunta: str) -> str | None:
    pn = normalizar(pergunta)
    for padrao in PADROES_INJECAO:
        if re.search(padrao, pn):
            return (
                "Nao posso executar instrucoes que tentem alterar dados ou obter "
                "credenciais. Este agente e somente leitura e consulta apenas o estoque."
            )
    return None


def detectar_fora_de_escopo(pergunta: str) -> str | None:
    pn = normalizar(pergunta)
    for padrao in PADROES_FORA_DE_ESCOPO:
        if re.search(padrao, pn):
            return (
                "Sou um assistente exclusivo para controle e consulta de estoque "
                "farmacêutico. Não posso responder a perguntas fora do escopo do estoque "
                "da farmácia."
            )
    return None


def detectar_recusa_clinica(pergunta: str) -> str | None:
    pn = normalizar(pergunta)
    for padrao in PADROES_CLINICOS:
        if re.search(padrao, pn):
            return (
                "Sou um assistente exclusivo para controle e consulta de estoque "
                "farmacêutico. Não forneço orientações clínicas, diagnóstico, prescrição, "
                "indicação terapêutica, dosagem ou posologia. Por favor, consulte um médico "
                "ou farmacêutico para orientações clínicas."
            )
    return None
