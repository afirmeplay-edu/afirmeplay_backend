"""
Adiciona as colunas edition_number e edition_series na tabela competitions
se não existirem. Corrige o erro ao deletar avaliações/testes:
  column competitions.edition_number does not exist
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


def main():
    database_url = Config.SQLALCHEMY_DATABASE_URI
    if not database_url:
        print("ERRO: DATABASE_URL não configurada.")
        sys.exit(1)
    kwargs = {}
    if "postgresql" in database_url:
        kwargs["client_encoding"] = "utf8"
    engine = create_engine(database_url, **kwargs)

    with engine.connect() as conn:
        # Verificar se a tabela competitions existe
        r = conn.execute(text("""
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'competitions'
        """))
        if r.scalar() is None:
            print("A tabela 'competitions' não existe neste banco. Nada a fazer.")
            print("(O erro ao deletar avaliações ocorre no banco onde a tabela existe mas faltam as colunas.)")
            return

        # Verificar e adicionar edition_number
        r = conn.execute(text("""
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'competitions' AND column_name = 'edition_number'
        """))
        if r.scalar() is None:
            print("Adicionando coluna competitions.edition_number...")
            conn.execute(text("ALTER TABLE public.competitions ADD COLUMN edition_number INTEGER NULL"))
            conn.commit()
            print("  OK")
        else:
            print("Coluna edition_number já existe.")

        # Verificar e adicionar edition_series
        r = conn.execute(text("""
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'competitions' AND column_name = 'edition_series'
        """))
        if r.scalar() is None:
            print("Adicionando coluna competitions.edition_series...")
            conn.execute(text("ALTER TABLE public.competitions ADD COLUMN edition_series VARCHAR NULL"))
            conn.commit()
            print("  OK")
        else:
            print("Coluna edition_series já existe.")

    print("\nConcluído. Tente deletar a avaliação novamente.")


if __name__ == "__main__":
    main()
