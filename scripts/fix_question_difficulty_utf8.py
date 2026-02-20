"""
Corrige valores de difficulty_level na tabela question que ficaram
corrompidos por UTF-8 (ex: B??sico -> Básico, Abaixo do B??sico -> Abaixo do Básico).
"""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_ROOT, "app", ".env"))
except ImportError:
    pass

from app.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.models.question import Question


def get_db_session():
    database_url = Config.SQLALCHEMY_DATABASE_URI
    kwargs = {}
    if "postgresql" in (database_url or ""):
        kwargs["client_encoding"] = "utf8"
    engine = create_engine(database_url, **kwargs)
    return sessionmaker(bind=engine)()


def main():
    session = get_db_session()

    # Mapeamento: valor corrompido -> valor correto (UTF-8)
    corrections = [
        ("B??sico", "Básico"),
        ("Abaixo do B??sico", "Abaixo do Básico"),
        ("Avan??ado", "Avançado"),
        # Variantes possíveis (um único ? ou outros encodings)
        ("B?sico", "Básico"),
        ("Abaixo do B?sico", "Abaixo do Básico"),
        ("Avan?ado", "Avançado"),
    ]

    print("\n" + "=" * 60)
    print("CORREÇÃO DE difficulty_level (UTF-8) NA TABELA question")
    print("=" * 60)

    # Listar valores distintos atuais que parecem corrompidos
    distinct = session.execute(
        text("SELECT DISTINCT difficulty_level FROM question WHERE difficulty_level IS NOT NULL")
    ).fetchall()
    distinct_values = [row[0] for row in distinct]

    corrupted = [v for v in distinct_values if v and ("??" in v or ("sico" in v and "ásico" not in v and "B" in v))]
    if corrupted:
        print("\nValores possivelmente corrompidos encontrados:", corrupted)

    total_updated = 0
    for wrong, correct in corrections:
        result = session.execute(
            text("UPDATE question SET difficulty_level = :correct WHERE difficulty_level = :wrong"),
            {"correct": correct, "wrong": wrong},
        )
        if result.rowcount and result.rowcount > 0:
            print(f"  Corrigido: '{wrong}' -> '{correct}' ({result.rowcount} questões)")
            total_updated += result.rowcount

    # Abaixo do B??sico primeiro (pattern mais específico), depois B??sico sozinho
    r_abaixo = session.execute(
        text("UPDATE question SET difficulty_level = 'Abaixo do Básico' WHERE difficulty_level LIKE 'Abaixo do B%' AND difficulty_level NOT LIKE '%ásico'")
    )
    if r_abaixo.rowcount and r_abaixo.rowcount > 0:
        print(f"  Corrigido (Abaixo do B... sem á): {r_abaixo.rowcount} questões -> 'Abaixo do Básico'")
        total_updated += r_abaixo.rowcount

    r_basico = session.execute(
        text("UPDATE question SET difficulty_level = 'Básico' WHERE difficulty_level LIKE 'B%sico' AND difficulty_level NOT LIKE '%ásico' AND difficulty_level NOT LIKE 'Abaixo%'")
    )
    if r_basico.rowcount and r_basico.rowcount > 0:
        print(f"  Corrigido (B...sico sem á): {r_basico.rowcount} questões -> 'Básico'")
        total_updated += r_basico.rowcount

    if total_updated > 0:
        session.commit()
        print(f"\nTotal de questões atualizadas: {total_updated}")
        print("Commit realizado.")
    else:
        print("\nNenhum registro com valor corrompido encontrado. Nada alterado.")

    session.close()
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
