import argparse
import sys

from estoque_ia.agente import ErroClienteLLM, criar_agente
from estoque_ia.config import carregar_config
from estoque_ia.esquemas import FERRAMENTAS_SCHEMA

ERRO_OLLAMA = "Erro ao consultar o Ollama. Verifique se ele está em execução."


def _imprimir_resposta(resposta, mostrar_ferramentas: bool) -> None:
    print(resposta.texto)

    if not mostrar_ferramentas:
        return

    nomes = ", ".join(chamada.nome for chamada in resposta.ferramentas_usadas) or "nenhuma"
    print(f"[ferramentas: {nomes}]")


def main(argv: list[str] | None = None) -> int:
    """CLI: 0 ok, 1 pergunta inválida, 2 config/banco, 3 erro do Ollama."""
    parser = argparse.ArgumentParser(prog="estoque-ia")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_perg = sub.add_parser("perguntar")
    p_perg.add_argument("texto")
    p_perg.add_argument("--mostrar-ferramentas", action="store_true")

    p_chat = sub.add_parser("chat")
    p_chat.add_argument("--mostrar-ferramentas", action="store_true")

    sub.add_parser("ferramentas")

    args = parser.parse_args(argv)

    if args.cmd == "ferramentas":
        # Esse comando não precisa de banco nem de Ollama; serve de documentação.
        for ferramenta in FERRAMENTAS_SCHEMA:
            nome = ferramenta["name"]
            descricao = ferramenta.get("description", "")
            print(f"- {nome}: {descricao}")
        return 0

    try:
        agente = criar_agente(carregar_config())
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if args.cmd == "perguntar":
        try:
            resposta = agente.perguntar(args.texto)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        except ErroClienteLLM:
            print(ERRO_OLLAMA, file=sys.stderr)
            return 3

        _imprimir_resposta(resposta, args.mostrar_ferramentas)
        return 0

    if args.cmd == "chat":
        while True:
            try:
                linha = input("voce> ")
            except (EOFError, KeyboardInterrupt):
                break

            if linha.strip().lower() in ("sair", "exit"):
                break

            if not linha.strip():
                continue

            try:
                resposta = agente.perguntar(linha)
            except ValueError as exc:
                print(str(exc), file=sys.stderr)
                continue
            except ErroClienteLLM:
                print(ERRO_OLLAMA, file=sys.stderr)
                continue

            _imprimir_resposta(resposta, args.mostrar_ferramentas)

        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
