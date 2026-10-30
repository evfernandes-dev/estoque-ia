import inspect
import json
from datetime import date

from estoque_ia import ferramentas

FERRAMENTAS_SCHEMA = [
    {
        "name": "buscar_medicamento",
        "description": (
            "Usar quando precisar encontrar um medicamento pelo nome ou saber estoque, "
            "lotes, situacao e validade dos lotes."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"nome": {"type": "string"}},
            "required": ["nome"],
        },
    },
    {
        "name": "itens_vencendo",
        "description": "Usar quando perguntarem sobre lotes que vencem em ate X dias.",
        "input_schema": {
            "type": "object",
            "properties": {"dias": {"type": "integer", "minimum": 1, "maximum": 365}},
            "required": [],
        },
    },
    {
        "name": "itens_vencidos",
        "description": "Usar quando perguntarem sobre lotes ja vencidos com estoque.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "abaixo_do_minimo",
        "description": "Usar quando perguntarem sobre medicamentos abaixo do estoque minimo.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "consumo_medio",
        "description": (
            "Usar quando perguntarem sobre consumo medio ou autonomia de um medicamento."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "nome": {"type": "string"},
                "meses": {"type": "integer", "minimum": 1, "maximum": 12},
            },
            "required": ["nome"],
        },
    },
    {
        "name": "sem_saida",
        "description": "Usar quando perguntarem sobre medicamentos parados sem saida ha X dias.",
        "input_schema": {
            "type": "object",
            "properties": {"dias": {"type": "integer", "minimum": 1, "maximum": 365}},
            "required": [],
        },
    },
    {
        "name": "resumo_estoque",
        "description": "Usar quando perguntarem por um resumo geral do estoque.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
]

EXECUTORES = {
    "buscar_medicamento": ferramentas.buscar_medicamento,
    "itens_vencendo": ferramentas.itens_vencendo,
    "itens_vencidos": ferramentas.itens_vencidos,
    "abaixo_do_minimo": ferramentas.abaixo_do_minimo,
    "consumo_medio": ferramentas.consumo_medio,
    "sem_saida": ferramentas.sem_saida,
    "resumo_estoque": ferramentas.resumo_estoque,
}


def _para_inteiro(valor: object) -> object:
    if isinstance(valor, bool):
        # Deixa o validador da ferramenta recusar; bool não é dia nem mês.
        return valor
    if isinstance(valor, int):
        return valor
    if isinstance(valor, float) and valor.is_integer():
        return int(valor)
    if isinstance(valor, str):
        texto = valor.strip()
        if texto.isdigit() or (texto.startswith("-") and texto[1:].isdigit()):
            return int(texto)
    return valor


def normalizar_argumentos(nome: str, argumentos: dict) -> dict:
    """Traduz pequenas variações que modelos locais costumam mandar."""
    if not isinstance(argumentos, dict):
        return {}
    args = dict(argumentos)
    # Alguns modelos embrulham tudo em {"parameters": {...}}; a gente desembrulha.
    for sub in ("parameters", "properties", "arguments", "input"):
        if sub in args and isinstance(args[sub], dict):
            args = dict(args[sub])
            break
    if nome in ("buscar_medicamento", "consumo_medio"):
        if "nome" not in args:
            for alias in (
                "medicamento",
                "remedio",
                "nome_medicamento",
                "name",
                "termo",
                "query",
                "item",
            ):
                if alias in args:
                    args["nome"] = args.pop(alias)
                    break
            if "nome" not in args and len(args) == 1:
                k = next(iter(args))
                if isinstance(args[k], str):
                    args["nome"] = args.pop(k)

    if nome in ("itens_vencendo", "sem_saida"):
        if "dias" not in args:
            for alias in ("periodo", "dias_vencimento", "d", "days"):
                if alias in args:
                    try:
                        args["dias"] = int(args.pop(alias))
                    except (ValueError, TypeError):
                        pass
                    break
            if "dias" not in args and len(args) == 1:
                k = next(iter(args))
                if isinstance(args[k], (int, float, str)):
                    try:
                        args["dias"] = int(args.pop(k))
                    except (ValueError, TypeError):
                        pass

    if nome == "consumo_medio":
        if "meses" not in args:
            for alias in ("mes", "months", "m", "periodo"):
                if alias in args:
                    try:
                        args["meses"] = int(args.pop(alias))
                    except (ValueError, TypeError):
                        pass
                    break

    if nome in ("itens_vencendo", "sem_saida") and "dias" in args:
        args["dias"] = _para_inteiro(args["dias"])

    if nome == "consumo_medio" and "meses" in args:
        args["meses"] = _para_inteiro(args["meses"])

    return args


def executar_ferramenta(
    conn,
    nome: str,
    argumentos: dict,
    hoje: date | None = None,
) -> str:
    """Valida a chamada contra a assinatura real e devolve JSON serializado."""
    if nome not in EXECUTORES:
        raise ferramentas.ErroFerramenta("Ferramenta desconhecida")
    if not isinstance(argumentos, dict):
        raise ferramentas.ErroFerramenta("Argumentos devem ser um dicionario")

    argumentos = normalizar_argumentos(nome, argumentos)
    func = EXECUTORES[nome]
    sig = inspect.signature(func)
    params = set(sig.parameters) - {"conn", "hoje"}

    # Se o modelo inventou um argumento, ele não passa daqui.
    for chave in argumentos:
        if chave not in params:
            raise ferramentas.ErroFerramenta("Argumento desconhecido")

    kwargs = dict(argumentos)
    if "hoje" in sig.parameters:
        kwargs["hoje"] = hoje

    try:
        resultado = func(conn, **kwargs)
    except TypeError as exc:
        raise ferramentas.ErroFerramenta(str(exc)) from exc

    return json.dumps(resultado, ensure_ascii=False)
