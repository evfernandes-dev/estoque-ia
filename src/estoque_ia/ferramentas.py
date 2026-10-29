import sqlite3
import unicodedata
from datetime import date, timedelta


class ErroFerramenta(ValueError):
    pass


def _normalizar(texto: str) -> str:
    if texto is None:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(texto))
    sem_acento = "".join(c for c in nfkd if not unicodedata.combining(c))
    return sem_acento.casefold()


def _hoje(h: date | None = None) -> date:
    if h is None:
        return date.today()
    return h


def buscar_medicamento(conn: sqlite3.Connection, nome: str, hoje: date | None = None) -> dict:
    hoje = _hoje(hoje)
    if nome is None or str(nome).strip() == "":
        raise ErroFerramenta("Nome do medicamento nao pode estar vazio")
    if not isinstance(nome, str):
        raise ErroFerramenta("Nome do medicamento deve ser um texto")
    alvo = _normalizar(nome)
    cur = conn.cursor()
    cur.execute("SELECT id, nome, concentracao, categoria, estoque_minimo FROM medicamentos")
    candidatos = []
    for row in cur.fetchall():
        if alvo in _normalizar(row["nome"]):
            candidatos.append(dict(row))
    total_correspondencias = len(candidatos)
    candidatos = candidatos[:5]
    resultado_meds = []
    for med in candidatos:
        med_id = med["id"]
        cur.execute(
            "SELECT COALESCE(SUM(quantidade), 0) as total FROM lotes WHERE medicamento_id = ?",
            (med_id,),
        )
        estoque_atual = cur.fetchone()["total"]
        situacao = "abaixo do minimo" if estoque_atual < med["estoque_minimo"] else "adequado"
        cur.execute(
            "SELECT numero_lote, quantidade, validade FROM lotes WHERE medicamento_id = ? ORDER BY validade",
            (med_id,),
        )
        lotes = []
        for lote in cur.fetchall():
            validade_d = date.fromisoformat(lote["validade"])
            dias_para_vencer = (validade_d - hoje).days
            lotes.append(
                {
                    "numero_lote": lote["numero_lote"],
                    "quantidade": lote["quantidade"],
                    "validade": lote["validade"],
                    "dias_para_vencer": dias_para_vencer,
                }
            )
        resultado_meds.append(
            {
                "id": med["id"],
                "nome": med["nome"],
                "concentracao": med["concentracao"],
                "categoria": med["categoria"],
                "estoque_minimo": med["estoque_minimo"],
                "estoque_atual": estoque_atual,
                "situacao": situacao,
                "lotes": lotes,
            }
        )
    if not resultado_meds:
        return {"encontrado": False, "total_correspondencias": 0, "medicamentos": []}
    return {
        "encontrado": True,
        "total_correspondencias": total_correspondencias,
        "medicamentos": resultado_meds,
    }


def itens_vencendo(conn: sqlite3.Connection, dias: int = 30, hoje: date | None = None) -> dict:
    hoje = _hoje(hoje)
    if not isinstance(dias, int) or isinstance(dias, bool) or dias < 1 or dias > 365:
        raise ErroFerramenta("dias deve ser um inteiro entre 1 e 365")
    data_limite = hoje + timedelta(days=dias)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT m.nome as medicamento, m.concentracao, l.numero_lote, l.quantidade, l.validade
        FROM lotes l
        JOIN medicamentos m ON m.id = l.medicamento_id
        WHERE l.quantidade > 0 AND l.validade >= ? AND l.validade <= ?
        ORDER BY l.validade, m.nome
        """,
        (hoje.isoformat(), data_limite.isoformat()),
    )
    itens = []
    for row in cur.fetchall():
        validade_d = date.fromisoformat(row["validade"])
        itens.append(
            {
                "medicamento": row["medicamento"],
                "concentracao": row["concentracao"],
                "numero_lote": row["numero_lote"],
                "quantidade": row["quantidade"],
                "validade": row["validade"],
                "dias_restantes": (validade_d - hoje).days,
            }
        )
    return {
        "dias": dias,
        "data_limite": data_limite.isoformat(),
        "total_lotes": len(itens),
        "itens": itens,
    }


def itens_vencidos(conn: sqlite3.Connection, hoje: date | None = None) -> dict:
    hoje = _hoje(hoje)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT m.nome as medicamento, m.concentracao, l.numero_lote, l.quantidade, l.validade
        FROM lotes l
        JOIN medicamentos m ON m.id = l.medicamento_id
        WHERE l.quantidade > 0 AND l.validade < ?
        ORDER BY l.validade ASC, m.nome ASC
        """,
        (hoje.isoformat(),),
    )
    itens = []
    for row in cur.fetchall():
        validade_d = date.fromisoformat(row["validade"])
        itens.append(
            {
                "medicamento": row["medicamento"],
                "concentracao": row["concentracao"],
                "numero_lote": row["numero_lote"],
                "quantidade": row["quantidade"],
                "validade": row["validade"],
                "dias_vencido": (hoje - validade_d).days,
            }
        )
    return {"total_lotes": len(itens), "itens": itens}


def abaixo_do_minimo(conn: sqlite3.Connection) -> dict:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT m.nome as medicamento, m.concentracao, m.estoque_minimo,
               COALESCE(SUM(l.quantidade), 0) as estoque_atual
        FROM medicamentos m
        LEFT JOIN lotes l ON l.medicamento_id = m.id
        GROUP BY m.id
        HAVING estoque_atual < m.estoque_minimo
        ORDER BY (m.estoque_minimo - estoque_atual) DESC, m.nome ASC
        """
    )
    itens = []
    for row in cur.fetchall():
        falta = row["estoque_minimo"] - row["estoque_atual"]
        itens.append(
            {
                "medicamento": row["medicamento"],
                "concentracao": row["concentracao"],
                "estoque_atual": row["estoque_atual"],
                "estoque_minimo": row["estoque_minimo"],
                "falta": falta,
            }
        )
    return {"total": len(itens), "itens": itens}


def consumo_medio(
    conn: sqlite3.Connection, nome: str, meses: int = 3, hoje: date | None = None
) -> dict:
    hoje = _hoje(hoje)
    if nome is None or str(nome).strip() == "":
        raise ErroFerramenta("Nome do medicamento nao pode estar vazio")
    if not isinstance(nome, str):
        raise ErroFerramenta("Nome do medicamento deve ser um texto")
    if not isinstance(meses, int) or isinstance(meses, bool) or meses < 1 or meses > 12:
        raise ErroFerramenta("meses deve ser um inteiro entre 1 e 12")
    busca = buscar_medicamento(conn, nome, hoje)
    if not busca["encontrado"] or busca["total_correspondencias"] == 0:
        return {"encontrado": False}
    if busca["total_correspondencias"] > 1 or len(busca["medicamentos"]) > 1:
        opcoes = [m["nome"] for m in busca["medicamentos"]]
        return {"encontrado": True, "ambiguo": True, "opcoes": opcoes}
    med = busca["medicamentos"][0]
    med_id = med["id"]
    data_ini = hoje - timedelta(days=meses * 30)
    cur = conn.cursor()
    cur.execute(
        "SELECT COALESCE(SUM(quantidade), 0) as total FROM movimentacoes WHERE medicamento_id = ? AND tipo = 'saida' AND data >= ? AND data <= ?",
        (med_id, data_ini.isoformat(), hoje.isoformat()),
    )
    total_saidas = cur.fetchone()["total"]
    media_mensal = round(total_saidas / meses, 1) if meses > 0 else 0.0
    estoque_atual = med["estoque_atual"]
    if total_saidas == 0:
        autonomia_dias = None
    else:
        autonomia_dias = int(estoque_atual / (total_saidas / (meses * 30)))
    return {
        "encontrado": True,
        "ambiguo": False,
        "medicamento": med["nome"],
        "meses": meses,
        "total_saidas": total_saidas,
        "media_mensal": media_mensal,
        "estoque_atual": estoque_atual,
        "autonomia_dias": autonomia_dias,
    }


def sem_saida(conn: sqlite3.Connection, dias: int = 90, hoje: date | None = None) -> dict:
    hoje = _hoje(hoje)
    if not isinstance(dias, int) or isinstance(dias, bool) or dias < 1 or dias > 365:
        raise ErroFerramenta("dias deve ser um inteiro entre 1 e 365")
    data_limite = hoje - timedelta(days=dias)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT m.id, m.nome as medicamento,
               COALESCE((SELECT SUM(l2.quantidade) FROM lotes l2 WHERE l2.medicamento_id = m.id), 0) as estoque_atual,
               (SELECT MAX(data) FROM movimentacoes mv WHERE mv.medicamento_id = m.id AND mv.tipo = 'saida') as ultima_saida
        FROM medicamentos m
        """
    )
    itens = []
    for row in cur.fetchall():
        if row["estoque_atual"] <= 0:
            continue
        ultima_saida = row["ultima_saida"]
        if ultima_saida is not None:
            ultima_d = date.fromisoformat(ultima_saida)
            if ultima_d >= data_limite:
                continue
            dias_sem_saida = (hoje - ultima_d).days
        else:
            dias_sem_saida = None
        itens.append(
            {
                "medicamento": row["medicamento"],
                "estoque_atual": row["estoque_atual"],
                "ultima_saida": ultima_saida,
                "dias_sem_saida": dias_sem_saida,
            }
        )
    itens.sort(key=lambda x: (x["dias_sem_saida"] is None, -(x["dias_sem_saida"] or 0)))
    return {"dias": dias, "total": len(itens), "itens": itens}


def resumo_estoque(conn: sqlite3.Connection, hoje: date | None = None) -> dict:
    hoje = _hoje(hoje)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as c FROM medicamentos")
    total_medicamentos = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) as c FROM lotes")
    total_lotes = cur.fetchone()["c"]
    abaix = abaixo_do_minimo(conn)
    venc = itens_vencendo(conn, dias=30, hoje=hoje)
    vencidos = itens_vencidos(conn, hoje=hoje)
    sem = sem_saida(conn, dias=90, hoje=hoje)
    return {
        "total_medicamentos": total_medicamentos,
        "total_lotes": total_lotes,
        "abaixo_do_minimo": abaix["total"],
        "lotes_vencendo_30_dias": venc["total_lotes"],
        "lotes_vencidos": vencidos["total_lotes"],
        "sem_saida_90_dias": sem["total"],
    }
