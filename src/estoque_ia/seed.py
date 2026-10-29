import argparse
import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from estoque_ia.config import carregar_config
from estoque_ia.db import conectar, criar_schema

MEDICAMENTOS = [
    "Dipirona|500 mg|Analgésico",
    "Paracetamol|500 mg|Analgésico",
    "Ibuprofeno|600 mg|Anti-inflamatório",
    "Diclofenaco|50 mg|Anti-inflamatório",
    "Losartana|50 mg|Anti-hipertensivo",
    "Captopril|25 mg|Anti-hipertensivo",
    "Enalapril|10 mg|Anti-hipertensivo",
    "Atenolol|50 mg|Anti-hipertensivo",
    "Anlodipino|5 mg|Anti-hipertensivo",
    "Hidroclorotiazida|25 mg|Diurético",
    "Furosemida|40 mg|Diurético",
    "Metformina|850 mg|Antidiabético",
    "Glibenclamida|5 mg|Antidiabético",
    "Insulina NPH|100 UI/mL|Antidiabético",
    "Sinvastatina|20 mg|Estatina",
    "Omeprazol|20 mg|Gastroprotetor",
    "Amoxicilina|500 mg|Antibiótico",
    "Azitromicina|500 mg|Antibiótico",
    "Cefalexina|500 mg|Antibiótico",
    "Metronidazol|250 mg|Antibiótico",
    "Fluconazol|150 mg|Antifúngico",
    "Nistatina|100.000 UI/mL|Antifúngico",
    "Albendazol|400 mg|Antiparasitário",
    "Prednisona|20 mg|Corticoide",
    "Dexametasona|4 mg|Corticoide",
    "Loratadina|10 mg|Antialérgico",
    "Salbutamol|100 mcg|Broncodilatador",
    "Ácido fólico|5 mg|Suplemento",
    "Sulfato ferroso|40 mg|Suplemento",
    "Propranolol|40 mg|Anti-hipertensivo",
]

ABAIXO_MINIMO = {"Dipirona", "Amoxicilina", "Insulina NPH"}
VENCENDO_EM_30 = {"Paracetamol", "Losartana", "Omeprazol", "Metformina"}
VENCIDOS = {"Ibuprofeno", "Nistatina"}
SEM_SAIDA = {"Albendazol", "Fluconazol", "Cefalexina"}


def _gerar_numero_lote(rng: random.Random) -> str:
    return "L" + "".join(str(rng.randint(0, 9)) for _ in range(6))


def popular(conn: sqlite3.Connection, hoje: date, semente: int = 42) -> None:
    rng = random.Random(semente)
    cur = conn.cursor()
    try:
        for linha in MEDICAMENTOS:
            nome, concentracao, categoria = linha.split("|")
            minimo = rng.choice([x * 10 for x in range(4, 31)])
            cur.execute(
                "INSERT INTO medicamentos(nome,concentracao,categoria,estoque_minimo) VALUES(?,?,?,?)",
                (nome, concentracao, categoria, minimo),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    meds = {row["nome"]: dict(row) for row in cur.execute("SELECT * FROM medicamentos")}
    try:
        for nome, med in meds.items():
            med_id = med["id"]
            minimo = med["estoque_minimo"]
            if nome in ABAIXO_MINIMO:
                alvo = int(minimo * rng.uniform(0.3, 0.7))
                q1 = max(0, alvo // 2)
                q2 = alvo - q1
                for qtd in [q1, q2]:
                    if qtd <= 0:
                        continue
                    cur.execute(
                        "INSERT INTO lotes(medicamento_id,numero_lote,quantidade,validade) VALUES(?,?,?,?)",
                        (
                            med_id,
                            _gerar_numero_lote(rng),
                            qtd,
                            (hoje + timedelta(days=rng.randint(200, 400))).isoformat(),
                        ),
                    )
            elif nome in VENCENDO_EM_30:
                total = int(minimo * rng.uniform(1.6, 2.2))
                cur.execute(
                    "INSERT INTO lotes(medicamento_id,numero_lote,quantidade,validade) VALUES(?,?,?,?)",
                    (
                        med_id,
                        _gerar_numero_lote(rng),
                        total,
                        (hoje + timedelta(days=rng.randint(5, 30))).isoformat(),
                    ),
                )
            elif nome in VENCIDOS:
                total = int(minimo * rng.uniform(1.6, 2.2))
                cur.execute(
                    "INSERT INTO lotes(medicamento_id,numero_lote,quantidade,validade) VALUES(?,?,?,?)",
                    (
                        med_id,
                        _gerar_numero_lote(rng),
                        total,
                        (hoje - timedelta(days=rng.randint(1, 60))).isoformat(),
                    ),
                )
            elif nome in SEM_SAIDA:
                lotes_cnt = rng.randint(1, 2)
                total = int(minimo * rng.uniform(1.8, 2.5))
                restante = total
                for i in range(lotes_cnt):
                    if i == lotes_cnt - 1:
                        qtd = restante
                    else:
                        qtd = restante // 2
                        restante -= qtd
                    cur.execute(
                        "INSERT INTO lotes(medicamento_id,numero_lote,quantidade,validade) VALUES(?,?,?,?)",
                        (
                            med_id,
                            _gerar_numero_lote(rng),
                            qtd,
                            (hoje + timedelta(days=rng.randint(200, 500))).isoformat(),
                        ),
                    )
            else:
                lotes_cnt = rng.randint(1, 3)
                total = int(minimo * rng.uniform(1.5, 3.0))
                restante = total
                for i in range(lotes_cnt):
                    if i == lotes_cnt - 1:
                        qtd = restante
                    else:
                        qtd = max(1, restante // (lotes_cnt - i))
                        restante -= qtd
                    cur.execute(
                        "INSERT INTO lotes(medicamento_id,numero_lote,quantidade,validade) VALUES(?,?,?,?)",
                        (
                            med_id,
                            _gerar_numero_lote(rng),
                            qtd,
                            (hoje + timedelta(days=rng.randint(120, 720))).isoformat(),
                        ),
                    )
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    try:
        cur.execute("SELECT id, nome, estoque_minimo FROM medicamentos")
        meds_list = cur.fetchall()
        for med in meds_list:
            med_id = med["id"]
            nome = med["nome"]
            minimo = med["estoque_minimo"]
            if nome in SEM_SAIDA:
                r2 = random.Random(semente + med_id)
                ultima_saida = hoje - timedelta(days=r2.randint(100, 150))
                d = hoje - timedelta(days=180)
                while d <= ultima_saida:
                    qtd = max(1, int(minimo * r2.uniform(0.03, 0.12)))
                    cur.execute(
                        "INSERT INTO movimentacoes(medicamento_id,tipo,quantidade,data) VALUES(?,?,?,?)",
                        (med_id, "saida", qtd, d.isoformat()),
                    )
                    d += timedelta(days=7)
                for meses_atras in range(6, 12):
                    d2 = hoje - timedelta(days=30 * meses_atras)
                    if d2 > ultima_saida:
                        continue
                    qtd = max(1, int(minimo * 0.3))
                    cur.execute(
                        "INSERT INTO movimentacoes(medicamento_id,tipo,quantidade,data) VALUES(?,?,?,?)",
                        (med_id, "entrada", qtd, d2.isoformat()),
                    )
                continue
            r = random.Random(semente + med_id)
            d = hoje - timedelta(days=180)
            while d <= hoje:
                qtd = max(1, int(minimo * r.uniform(0.03, 0.12)))
                cur.execute(
                    "INSERT INTO movimentacoes(medicamento_id,tipo,quantidade,data) VALUES(?,?,?,?)",
                    (med_id, "saida", qtd, d.isoformat()),
                )
                d += timedelta(days=7)
            for meses_atras in range(1, 7):
                d2 = hoje - timedelta(days=30 * meses_atras)
                if d2 > hoje:
                    continue
                qtd = max(1, int(minimo * r.uniform(0.2, 0.4)))
                cur.execute(
                    "INSERT INTO movimentacoes(medicamento_id,tipo,quantidade,data) VALUES(?,?,?,?)",
                    (med_id, "entrada", qtd, d2.isoformat()),
                )
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=None)
    parser.add_argument("--semente", type=int, default=42)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    if args.db is None:
        args.db = carregar_config().db_path

    db_path = Path(args.db)
    if db_path.exists() and not args.force:
        print("Arquivo ja existe. Use --force para sobrescrever.")
        raise SystemExit(1)

    if db_path.exists() and args.force:
        db_path.unlink()

    conn = conectar(db_path)
    criar_schema(conn)
    hoje = date.today()
    popular(conn, hoje, semente=args.semente)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as c FROM medicamentos")
    c_m = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) as c FROM lotes")
    c_l = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) as c FROM movimentacoes")
    c_mv = cur.fetchone()["c"]
    print(f"Medicamentos: {c_m}, Lotes: {c_l}, Movimentacoes: {c_mv}")
    conn.close()


if __name__ == "__main__":
    main()
