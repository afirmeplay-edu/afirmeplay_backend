"""Remove uma avaliação (test) do banco por ID e todos os registros relacionados."""

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

TEST_ID = "81718cf8-1ed5-4245-b3bf-f816b38a1b90"

# Ordem: tabelas que referenciam test_id (com schema public)
STEPS = [
    ("UPDATE public.competitions SET test_id = NULL WHERE test_id = :tid", "Competições desvinculadas"),
    ("DELETE FROM public.student_answers WHERE test_id = :tid", None),
    ("DELETE FROM public.student_test_olimpics WHERE test_id = :tid", None),
    ("DELETE FROM public.physical_test_answers WHERE physical_form_id IN (SELECT id FROM public.physical_test_forms WHERE test_id = :tid)", None),
    ("DELETE FROM public.physical_test_forms WHERE test_id = :tid", None),
    ("DELETE FROM public.form_coordinates WHERE test_id = :tid", None),
    ("DELETE FROM public.evaluation_results WHERE test_id = :tid", None),
    ("DELETE FROM public.report_aggregates WHERE test_id = :tid", None),
    ("DELETE FROM public.test_sessions WHERE test_id = :tid", None),
    ("DELETE FROM public.class_test WHERE test_id = :tid", None),
    ("DELETE FROM public.test_questions WHERE test_id = :tid", None),
    ("DELETE FROM public.test WHERE id = :tid", "Avaliação apagada"),
]


def main():
    database_url = Config.SQLALCHEMY_DATABASE_URI
    if not database_url:
        print("ERRO: DATABASE_URL não configurada.")
        sys.exit(1)
    kwargs = {}
    if "postgresql" in database_url:
        kwargs["client_encoding"] = "utf8"
    engine = create_engine(database_url, **kwargs)

    for sql, msg in STEPS:
        try:
            with engine.begin() as conn:
                conn.execute(text("SET search_path TO public"))
                result = conn.execute(text(sql), {"tid": TEST_ID})
                if msg:
                    print(msg)
                if "DELETE FROM public.test WHERE" in sql:
                    if result.rowcount:
                        print(f"Avaliação {TEST_ID} apagada com sucesso.")
                    else:
                        print(f"Nenhuma linha em test com id {TEST_ID} (pode já ter sido apagada).")
        except Exception as e:
            if "does not exist" in str(e) or "UndefinedTable" in str(e):
                pass  # tabela não existe neste banco
            else:
                print(f"Erro em um passo (ignorado): {e}")
    print("Concluído.")


if __name__ == "__main__":
    main()
