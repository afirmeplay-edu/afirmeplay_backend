"""
Remove todas as habilidades (skills) do banco:
1. Limpa a coluna skill das questões (question.skill = NULL)
2. Apaga todos os registros da tabela skills

Uso (na raiz do projeto):
    python scripts/truncate_all_skills.py
"""

import os
import sys
from pathlib import Path

# Garantir que o .env seja carregado do projeto (app/.env)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / "app" / ".env")

from sqlalchemy import text, create_engine

QUESTION_BATCH_SIZE = 100
SKILL_BATCH_SIZE = 50

def main():
    print("Iniciando script...", flush=True)
    url = os.getenv("DATABASE_URL")
    if not url:
        print("ERRO: DATABASE_URL nao encontrada. Verifique app/.env", flush=True)
        sys.exit(1)
    # Mostrar qual banco (mascarar senha)
    try:
        from urllib.parse import urlparse, urlunparse
        p = urlparse(url)
        if p.password:
            netloc = p.hostname or ""
            if p.port:
                netloc += f":{p.port}"
            safe = urlunparse((p.scheme, netloc, p.path or "", "", "", ""))
        else:
            safe = url
    except Exception:
        safe = url[:50] + "..." if len(url) > 50 else url
    print("Banco:", safe, flush=True)
    print("Conectando...", flush=True)
    engine = create_engine(
        url,
            # Contar antes
        connect_args={"connect_timeout": 60} if "postgresql" in url else {},
        pool_pre_ping=True,
    )
    
    conn = None
    try:
        conn = engine.connect()
        
        # Contar antes
        n_skills = conn.execute(text("SELECT COUNT(*) FROM skills")).scalar()
        n_questions = conn.execute(text("SELECT COUNT(*) FROM question WHERE skill IS NOT NULL")).scalar()
        print(f"\n{'='*60}")
        print(f"ESTADO ATUAL DO BANCO:")
        print(f"  - Skills na tabela: {n_skills}")
        print(f"  - Questoes com skill preenchido: {n_questions}")
                trans = conn.begin()
        print(f"{'='*60}")
        
        if n_skills == 0 and n_questions == 0:
        confirm = input("Digite 'SIM' para continuar: ").strip().upper()
        if confirm != "SIM":
            print("Cancelado pelo usuario.")
            return
            print("\nNada para apagar. Banco ja esta limpo.")
            return
        
        print(f"\nVOCE VAI APAGAR {n_skills} HABILIDADES E LIMPAR {n_questions} QUESTOES.")
        
        # Se --yes foi passado como argumento, pula confirmação
        auto_confirm = len(sys.argv) > 1 and sys.argv[1] == "--yes"
        if not auto_confirm:
            confirm = input("Digite 'SIM' para continuar (ou use --yes): ").strip().upper()
            if confirm != "SIM":
                print("Cancelado pelo usuario.")
                return
        else:
            print("Auto-confirmado (--yes). Prosseguindo...")
        
        # ---- Fase 1: UPDATE question.skill em lotes ----
                trans = conn.begin()
        if n_questions > 0:
            print(f"\nFase 1: Limpando question.skill em lotes de {QUESTION_BATCH_SIZE}...", flush=True)
            total_updated = 0
            batch_num = 0
            while True:
                try:
                    r = conn.execute(text(f"""
                        UPDATE question SET skill = NULL
                        WHERE id IN (
                            SELECT id FROM question WHERE skill IS NOT NULL LIMIT {QUESTION_BATCH_SIZE}
                        )
                    """))
                    conn.commit()
                    if r.rowcount == 0:
                        break
                    total_updated += r.rowcount
                    batch_num += 1
                    print(f"  Lote {batch_num}: {r.rowcount} questoes atualizadas (total: {total_updated})", flush=True)
                except Exception as e:
                    conn.rollback()
                    raise e
            print(f"  Total de questoes limpas: {total_updated}", flush=True)
        
        # ---- Fase 2: DELETE skills em lotes ----
        if n_skills > 0:
            print(f"\nFase 2: Apagando skills em lotes de {SKILL_BATCH_SIZE}...", flush=True)
            total_deleted = 0
            batch_num = 0
            while True:
                try:
                    r = conn.execute(text(f"""
                        DELETE FROM skills
                        WHERE id IN (SELECT id FROM skills LIMIT {SKILL_BATCH_SIZE})
                    """))
                    conn.commit()
                    if r.rowcount == 0:
                        break
                    total_deleted += r.rowcount
                    batch_num += 1
                    if batch_num % 3 == 0:
                        print(f"  Lote {batch_num}: removidas {total_deleted} skills...", flush=True)
                except Exception as e:
                    conn.rollback()
                    raise e
            print(f"  Total de skills removidas: {total_deleted}", flush=True)
        
        # Verificar final
        n_skills_final = conn.execute(text("SELECT COUNT(*) FROM skills")).scalar()
        n_questions_final = conn.execute(text("SELECT COUNT(*) FROM question WHERE skill IS NOT NULL")).scalar()
        print(f"\nDepois: {n_skills_final} skills, {n_questions_final} questoes com skill")
        print("Concluido.")
        
    except Exception as e:
        print(f"\nERRO: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    main()
