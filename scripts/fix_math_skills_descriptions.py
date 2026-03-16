"""
Script de CORREÇÃO: ajusta descrição e subject_id das habilidades de Matemática
conforme organizacao_matematica_anos_finais.json.

Regras:
- Habilidades de Português (subject_id = Português): NÃO são alteradas.
- Habilidades de Matemática (subject_id = Matemática): descrição atualizada para a do JSON.
- Habilidade com code do JSON mas subject_id errado (outro ou null): corrige subject_id
  para Matemática e descrição para a do JSON.

Uso:
  python scripts/fix_math_skills_descriptions.py         # executa a correção
  python scripts/fix_math_skills_descriptions.py --dry-run   # só mostra o que seria feito
"""

import argparse
import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_ROOT, "app", ".env"))
except ImportError:
    pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MATEMATICA_ID = "44f3421e-ca84-4fe5-a449-a3d9bfa3db3d"
PORTUGUES_ID = "4d29b4f1-7bd7-42c0-84d5-111dc7025b90"


def load_math_expected():
    """Carrega código -> descrição esperada do JSON de matemática (anos finais)."""
    path = os.path.join(SCRIPT_DIR, "organizacao_matematica_anos_finais.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    expected = {}
    for block in data.get("habilidades_compartilhadas", []):
        for h in block.get("habilidades", []):
            code = (h.get("codigo") or "").strip()
            desc = (h.get("descricao") or "").strip()
            if code:
                expected[code] = desc
    for block in data.get("habilidades_unicas_por_serie", []):
        for h in block.get("habilidades", []):
            code = (h.get("codigo") or "").strip()
            desc = (h.get("descricao") or "").strip()
            if code:
                expected[code] = desc
    return expected


def get_db_session():
    from app.config import Config
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    database_url = Config.SQLALCHEMY_DATABASE_URI
    if not database_url:
        raise RuntimeError("SQLALCHEMY_DATABASE_URI não configurada")
    kwargs = {}
    if "postgresql" in (database_url or ""):
        kwargs["client_encoding"] = "utf8"
    engine = create_engine(database_url, **kwargs)
    Session = sessionmaker(bind=engine)
    return Session()


def main():
    parser = argparse.ArgumentParser(description="Corrige descrição e subject_id das habilidades de Matemática.")
    parser.add_argument("--dry-run", action="store_true", help="Apenas mostra o que seria alterado, sem gravar.")
    args = parser.parse_args()
    dry_run = args.dry_run

    print("=" * 70)
    print("CORREÇÃO: habilidades de Matemática (descrição + subject_id)")
    print("Fonte: organizacao_matematica_anos_finais.json")
    if dry_run:
        print(">>> MODO DRY-RUN: nenhuma alteração será gravada.")
    print("=" * 70)

    expected = load_math_expected()
    codes_json = list(expected.keys())
    print(f"\nCódigos no JSON: {len(codes_json)}")

    session = get_db_session()
    from app.models.skill import Skill
    from app.models.subject import Subject

    subjects = {s.id: s.name for s in session.query(Subject).filter(Subject.id.in_([MATEMATICA_ID, PORTUGUES_ID])).all()}
    mat_name = subjects.get(MATEMATICA_ID, "Matemática")
    pt_name = subjects.get(PORTUGUES_ID, "Português")

    skills_with_code = session.query(Skill).filter(Skill.code.in_(codes_json)).all()

    # Não mexer em nenhuma com subject_id = Português
    to_process = [s for s in skills_with_code if str(s.subject_id) != PORTUGUES_ID]
    skipped_pt = len(skills_with_code) - len(to_process)
    if skipped_pt:
        print(f"Ignoradas (Português, não alteramos): {skipped_pt}")

    updated_desc = 0
    updated_subject_id = 0
    already_ok = 0

    for s in to_process:
        code = s.code
        desc_esperada = expected.get(code)
        if desc_esperada is None:
            continue
        desc_banco = (s.description or "").strip()
        subject_banco = str(s.subject_id) if s.subject_id else None
        need_desc = desc_banco != desc_esperada
        need_subject = subject_banco != MATEMATICA_ID

        if not need_desc and not need_subject:
            already_ok += 1
            continue

        if dry_run:
            if need_subject:
                print(f"  [dry-run] id={s.id} code={code} subject_id {subject_banco or 'NULL'} -> {MATEMATICA_ID}")
            if need_desc:
                print(f"  [dry-run] id={s.id} code={code} descrição -> do JSON")
            if need_desc:
                updated_desc += 1
            if need_subject:
                updated_subject_id += 1
            continue

        if need_subject:
            s.subject_id = MATEMATICA_ID
            updated_subject_id += 1
        if need_desc:
            s.description = desc_esperada
            updated_desc += 1

    if not dry_run and (updated_desc or updated_subject_id):
        session.commit()
        print(f"\nCommit realizado.")

    print(f"\nResumo:")
    print(f"  Já corretas (nenhuma alteração): {already_ok}")
    print(f"  Descrição atualizada: {updated_desc}")
    print(f"  subject_id corrigido para Matemática: {updated_subject_id}")

    if dry_run and (updated_desc or updated_subject_id):
        print("\nExecute sem --dry-run para aplicar as alterações.")
    elif dry_run:
        print("\nNada a alterar.")

    session.close()
    print("\nFim.")


if __name__ == "__main__":
    main()
