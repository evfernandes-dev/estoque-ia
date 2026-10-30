import json
from typing import Any


def data_br(valor: Any) -> str:
    """Converte uma data ISO em DD/MM/AAAA para a conversa ficar legível."""
    if not valor:
        return "-"
    try:
        ano, mes, dia = str(valor).split("-")
    except ValueError:
        # Se vier algo fora do padrão, melhor mostrar cru do que quebrar a resposta.
        return str(valor)
    return f"{dia}/{mes}/{ano}"


def formatar_dados_ferramenta(nome: str, dados: dict) -> str:
    """Transforma o JSON da ferramenta em texto curto para o usuário."""
    if not isinstance(dados, dict):
        return json.dumps(dados, ensure_ascii=False)

    if nome == "itens_vencendo":
        itens = dados.get("itens") or []
        if not itens:
            return "Nenhum lote vencendo no período informado."
        linhas = [
            f"Itens vencendo em até {dados.get('dias')} dias "
            f"(limite: {data_br(dados.get('data_limite'))}):"
        ]
        for item in itens:
            linhas.append(
                f"- {item.get('medicamento')} ({item.get('concentracao')}): "
                f"lote {item.get('numero_lote')} | quantidade {item.get('quantidade')} | "
                f"validade {data_br(item.get('validade'))} | "
                f"dias restantes {item.get('dias_restantes')}"
            )
        return "\n".join(linhas)

    if nome == "itens_vencidos":
        itens = dados.get("itens") or []
        if not itens:
            return "Nenhum lote vencido com estoque."
        linhas = ["Lotes vencidos com estoque:"]
        for item in itens:
            linhas.append(
                f"- {item.get('medicamento')} ({item.get('concentracao')}): "
                f"lote {item.get('numero_lote')} | quantidade {item.get('quantidade')} | "
                f"validade {data_br(item.get('validade'))} | "
                f"dias vencido {item.get('dias_vencido')}"
            )
        return "\n".join(linhas)

    if nome == "abaixo_do_minimo":
        itens = dados.get("itens") or []
        if not itens:
            return "Nenhum medicamento abaixo do estoque mínimo."
        linhas = ["Medicamentos abaixo do mínimo:"]
        for item in itens:
            linhas.append(
                f"- {item.get('medicamento')} ({item.get('concentracao')}): "
                f"atual {item.get('estoque_atual')} | mínimo {item.get('estoque_minimo')} | "
                f"falta {item.get('falta')}"
            )
        return "\n".join(linhas)

    if nome == "buscar_medicamento":
        if not dados.get("encontrado"):
            return "Medicamento não encontrado."
        linhas = []
        for med in dados.get("medicamentos") or []:
            situacao = "abaixo do mínimo" if "abaixo" in str(med.get("situacao")) else "adequado"
            linhas.append(
                f"- {med.get('nome')} ({med.get('concentracao')}), {med.get('categoria')}: "
                f"estoque atual {med.get('estoque_atual')} (mínimo {med.get('estoque_minimo')}), "
                f"situação {situacao}"
            )
            for lote in med.get("lotes") or []:
                dias = lote.get("dias_para_vencer")
                if isinstance(dias, int) and dias < 0:
                    prazo = f"vencido há {-dias} dias"
                else:
                    prazo = f"dias para vencer {dias}"
                linhas.append(
                    f"  lote {lote.get('numero_lote')} | "
                    f"quantidade {lote.get('quantidade')} | "
                    f"validade {data_br(lote.get('validade'))} | {prazo}"
                )
        return "\n".join(linhas) if linhas else "Medicamento não encontrado."

    if nome == "consumo_medio":
        if not dados.get("encontrado"):
            return "Medicamento não encontrado."
        if dados.get("ambiguo"):
            opcoes = ", ".join(dados.get("opcoes") or [])
            return f"Busca ambígua. Opções: {opcoes}"
        linhas = [f"Consumo médio de {dados.get('medicamento')} ({dados.get('meses')} meses):"]
        linhas.append(f"- Total de saídas: {dados.get('total_saidas')}")
        linhas.append(f"- Média mensal: {dados.get('media_mensal')}")
        linhas.append(f"- Estoque atual: {dados.get('estoque_atual')}")
        autonomia = dados.get("autonomia_dias")
        linhas.append(
            f"- Autonomia estimada (dias): {autonomia if autonomia is not None else 'N/A'}"
        )
        return "\n".join(linhas)

    if nome == "sem_saida":
        itens = dados.get("itens") or []
        if not itens:
            return "Nenhum medicamento sem saída no período."
        linhas = [f"Medicamentos sem saída há {dados.get('dias')} dias:"]
        for item in itens:
            linhas.append(
                f"- {item.get('medicamento')}: estoque atual {item.get('estoque_atual')} | "
                f"última saída {data_br(item.get('ultima_saida'))} | "
                f"dias sem saída {item.get('dias_sem_saida')}"
            )
        return "\n".join(linhas)

    if nome == "resumo_estoque":
        return (
            "Resumo do estoque:\n"
            f"- Total de medicamentos: {dados.get('total_medicamentos')}\n"
            f"- Total de lotes: {dados.get('total_lotes')}\n"
            f"- Abaixo do mínimo: {dados.get('abaixo_do_minimo')}\n"
            f"- Lotes vencendo em 30 dias: {dados.get('lotes_vencendo_30_dias')}\n"
            f"- Lotes vencidos: {dados.get('lotes_vencidos')}\n"
            f"- Sem saída há 90 dias: {dados.get('sem_saida_90_dias')}"
        )

    return json.dumps(dados, ensure_ascii=False)
