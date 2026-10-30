import argparse
import json
import sqlite3
from datetime import date
from pathlib import Path

from estoque_ia.agente import Agente, ClienteLLM, ClienteOllama
from estoque_ia.config import carregar_config
from estoque_ia.db import conectar, criar_schema
from estoque_ia.esquemas import EXECUTORES, executar_ferramenta
from estoque_ia.seed import popular
from estoque_ia.texto import normalizar

DATA_AVALIACAO = date(2026, 6, 15)


def criar_banco_avaliacao() -> sqlite3.Connection:
    """Banco em memória com os mesmos casos plantados dos testes."""
    conn = conectar(":memory:")
    criar_schema(conn)
    popular(conn, DATA_AVALIACAO)
    return conn


def carregar_casos(caminho: str | Path) -> list[dict]:
    p = Path(caminho)
    with p.open("r", encoding="utf-8") as f:
        dados = json.load(f)

    if not isinstance(dados, list):
        raise ValueError("casos.json deve ser uma lista")

    ids = set()

    for caso in dados:
        for campo in [
            "id",
            "pergunta",
            "ferramenta_esperada",
            "argumentos_esperados",
            "fatos_ferramenta",
            "termos_resposta",
        ]:
            if campo not in caso:
                raise ValueError("campo obrigatorio faltando")

        if caso["id"] in ids:
            raise ValueError("ids unicos")

        ids.add(caso["id"])
        ferramenta = caso["ferramenta_esperada"]

        if ferramenta is not None and ferramenta not in EXECUTORES:
            raise ValueError("ferramenta desconhecida")

    return dados


def avaliar_offline(casos: list[dict]) -> list[dict]:
    """Valida ferramentas e dados sem chamar LLM nenhum."""
    conn = criar_banco_avaliacao()
    resultados = []

    for caso in casos:
        falhas = []

        if caso["ferramenta_esperada"] is not None:
            nome = caso["ferramenta_esperada"]
            argumentos = caso.get("argumentos_esperados") or {}

            try:
                resultado_json = executar_ferramenta(
                    conn,
                    nome,
                    argumentos,
                    hoje=DATA_AVALIACAO,
                )
                resultado_normalizado = normalizar(resultado_json)

                for fato in caso.get("fatos_ferramenta") or []:
                    if normalizar(fato) not in resultado_normalizado:
                        falhas.append(f"fato ausente: {fato}")

            except Exception as exc:
                falhas.append(str(exc))

        passou = len(falhas) == 0

        resultados.append(
            {
                "id": caso["id"],
                "passou": passou,
                "falhas": falhas,
                "ferramentas": (
                    [caso["ferramenta_esperada"]] if caso["ferramenta_esperada"] else []
                ),
                "resposta": "",
            }
        )

    return resultados


def avaliar_online(
    casos: list[dict],
    cliente: ClienteLLM,
    modelo: str,
    usar_roteamento: bool = True,
) -> list[dict]:
    """Roda o agente de verdade e mede ferramenta, argumentos e resposta."""
    conn = criar_banco_avaliacao()
    agente = Agente(
        conn,
        cliente,
        modelo,
        hoje=DATA_AVALIACAO,
        usar_roteamento=usar_roteamento,
    )
    resultados = []

    for caso in casos:
        falhas = []

        try:
            resposta = agente.perguntar(caso["pergunta"])
        except Exception as exc:
            resultados.append(
                {
                    "id": caso["id"],
                    "passou": False,
                    "falhas": [str(exc)],
                    "ferramentas": [],
                    "resposta": "",
                }
            )
            continue

        usadas = [chamada.nome for chamada in resposta.ferramentas_usadas]

        if caso["ferramenta_esperada"] is None:
            if usadas:
                falhas.append("ferramenta usada quando nao esperada")
        else:
            ferramenta_esperada = caso["ferramenta_esperada"]

            if ferramenta_esperada not in usadas:
                falhas.append("ferramenta esperada nao usada")
            else:
                for chamada in resposta.ferramentas_usadas:
                    if chamada.nome == ferramenta_esperada:
                        esperados = caso.get("argumentos_esperados") or {}

                        for chave, valor in esperados.items():
                            if chave not in chamada.argumentos:
                                falhas.append(f"argumento faltando: {chave}")
                                break

                            argumento = normalizar(chamada.argumentos[chave])
                            esperado = normalizar(valor)

                            if esperado not in argumento and argumento not in esperado:
                                if str(chamada.argumentos[chave]) != str(valor):
                                    falhas.append(f"argumento incorreto: {chave}")
                                    break
                        break

        if any(chamada.erro for chamada in resposta.ferramentas_usadas):
            falhas.append("chamada com erro")

        resposta_normalizada = normalizar(resposta.texto)

        for termo in caso.get("termos_resposta") or []:
            if normalizar(termo) not in resposta_normalizada:
                falhas.append(f"termo ausente: {termo}")

        if resposta.incompleta:
            falhas.append("resposta incompleta")

        resultados.append(
            {
                "id": caso["id"],
                "passou": len(falhas) == 0,
                "falhas": falhas,
                "ferramentas": usadas,
                "resposta": resposta.texto,
            }
        )

    return resultados


def gerar_relatorio_markdown(resultados: list[dict], modelo: str, modo: str) -> str:
    total = len(resultados)
    passou = sum(1 for resultado in resultados if resultado["passou"])
    taxa = (passou / total * 100) if total else 0

    linhas = [
        f"# Avaliacao do agente - {modo}",
        "",
        f"- Data: {date.today().isoformat()}",
        f"- Modelo: {modelo}",
        f"- Taxa de acerto: {passou} de {total} ({taxa:.1f}%)",
        "",
        "| id | passou | ferramentas usadas | falhas |",
        "|---|---|---|---|",
    ]

    for resultado in resultados:
        ferramentas = ", ".join(resultado.get("ferramentas") or [])
        falhas = "; ".join(resultado.get("falhas") or [])
        status = "sim" if resultado["passou"] else "nao"

        linhas.append(f"| {resultado['id']} | {status} | {ferramentas} | {falhas} |")

    return "\n".join(linhas) + "\n"


def main(argv: list[str] | None = None) -> int:
    """Retorna 0 se tudo passou, 1 se algo falhou e 2 se a config quebrou."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--casos", default="avaliacao/casos.json")
    parser.add_argument("--online", action="store_true")
    parser.add_argument(
        "--sem-roteamento",
        action="store_true",
        help="mede o LLM puro, sem o roteador deterministico",
    )
    parser.add_argument("--saida", default=None)
    args = parser.parse_args(argv)

    try:
        casos = carregar_casos(args.casos)
    except Exception as exc:
        print(str(exc))
        return 2

    modelo = "offline"

    modo = "offline"

    if not args.online:
        # Offline valida dados e ferramentas; não precisa de modelo nem rede.
        resultados = avaliar_offline(casos)
    else:
        try:
            config = carregar_config()
            cliente = ClienteOllama(base_url=config.ollama_base_url)
            modelo = config.modelo
            resultados = avaliar_online(
                casos,
                cliente,
                modelo,
                usar_roteamento=not args.sem_roteamento,
            )
            modo = "online" if not args.sem_roteamento else "online (LLM puro)"
        except Exception as exc:
            print(str(exc))
            return 2

    relatorio = gerar_relatorio_markdown(resultados, modelo, modo)

    print(relatorio)

    if args.saida:
        caminho = Path(args.saida)
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text(relatorio, encoding="utf-8")

    return 0 if all(resultado["passou"] for resultado in resultados) else 1


if __name__ == "__main__":
    raise SystemExit(main())
