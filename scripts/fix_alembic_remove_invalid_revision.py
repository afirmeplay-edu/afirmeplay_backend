"""
Remove da tabela alembic_version a revision que não existe mais no projeto.

Use quando aparecer: Can't locate revision identified by 'recreate_test_questions_table'

Isso permite que `flask db upgrade` rode de novo (o Alembic consegue carregar o grafo).

Execute uma vez, depois rode: flask db upgrade
"""
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Revision que está no banco mas não existe mais nos arquivos
INVALID_REVISION = "recreate_test_questions_table"

def main():
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(PROJECT_ROOT, "app", ".env"))
    except ImportError:
        pass

    from app import create_app
    from app import db
    from sqlalchemy import text

    app = create_app()
    with app.app_context():
        try:
            r = db.session.execute(
                text("SELECT version_num FROM alembic_version WHERE version_num = :v"),
                {"v": INVALID_REVISION},
            )
            rows = r.fetchall()
            if rows:
                db.session.execute(
                    text("DELETE FROM alembic_version WHERE version_num = :v"),
                    {"v": INVALID_REVISION},
                )
                db.session.commit()
                print(f"Removida a revision '{INVALID_REVISION}' de alembic_version.")
                print("Agora rode: flask db upgrade")
                return
        except Exception as e:
            db.session.rollback()
            print(f"Erro ao acessar alembic_version: {e}")
            raise

        print(f"Nenhuma linha com version_num = '{INVALID_REVISION}' encontrada.")
        print("Conteúdo atual de alembic_version:")
        try:
            r = db.session.execute(text("SELECT version_num FROM alembic_version"))
            for row in r:
                print(" ", row[0])
        except Exception as e:
            print(" ", e)


if __name__ == "__main__":
    main()
