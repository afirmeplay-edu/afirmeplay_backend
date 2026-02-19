"""
Identifica habilidades duplicadas no banco (mesmo code + subject_id) e remove as
cópias, mantendo apenas uma por grupo. Atualiza referências em question.skill
para apontar para o id que será mantido, para não quebrar questões.

Depois de rodar, suba novamente as habilidades com o script de upload para
garantir descrição (e grade_id) corretas, sem duplicar.

Uso:
    python scripts/remove_duplicate_skills.py           # modo dry-run (só lista)
    python scripts/remove_duplicate_skills.py --apply   # aplica exclusões
"""

import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def get_db_session():
    from app.config import Config
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    url = Config.SQLALCHEMY_DATABASE_URI
    if not url:
        logger.error("❌ DATABASE_URL não configurada")
        sys.exit(1)
    engine = create_engine(url)
    return sessionmaker(bind=engine)()


def find_duplicates(session):
    """Retorna dict: (code, subject_id) -> list de Skill (ordenados por id; primeiro = manter)."""
    from app.models.skill import Skill

    all_skills = session.query(Skill).order_by(Skill.id).all()
    by_key = defaultdict(list)
    for s in all_skills:
        key = (s.code or "").strip(), (s.subject_id or "").strip()
        if key[0] and key[1]:
            by_key[key].append(s)

    return {k: v for k, v in by_key.items() if len(v) > 1}


def main():
    apply = "--apply" in sys.argv
    if not apply:
        logger.info("Modo dry-run (somente listar). Use --apply para excluir duplicatas.\n")

    session = get_db_session()
    from app.models.skill import Skill
    from app.models.question import Question

    duplicates = find_duplicates(session)
    if not duplicates:
        logger.info("Nenhuma duplicata encontrada (code + subject_id).")
        return

    total_dup_rows = sum(len(v) for v in duplicates.values())
    total_to_remove = total_dup_rows - len(duplicates)  # manter 1 por grupo
    logger.info(f"Encontrados {len(duplicates)} grupos duplicados ({total_dup_rows} linhas, {total_to_remove} a remover).\n")

    ids_to_delete = []
    id_to_keep = {}  # deleted_id -> keep_id (para atualizar question.skill)
    norm_to_keep = {}  # norm(deleted_id) -> keep_id (para buscar em question.skill)

    for (code, subject_id), skills in sorted(duplicates.items()):
        keep = skills[0]
        to_remove = skills[1:]
        logger.info(f"  {code} (subject {subject_id[:8]}...): manter {keep.id}, remover {len(to_remove)}")
        for s in to_remove:
            ids_to_delete.append(s.id)
            sid_str = str(s.id)
            id_to_keep[sid_str] = keep.id
            norm_to_keep[sid_str.strip("{}").lower()] = keep.id

    if not apply:
        logger.info(f"\nTotal de linhas a remover: {len(ids_to_delete)}. Rode com --apply para aplicar.")
        return

    # Atualizar question.skill: quem aponta para um id que será deletado passa a apontar para o id mantido
    def norm(s):
        return (s or "").strip().strip("{}").lower()

    # Carregar todas as questões com skill uma única vez
    questions = session.query(Question).filter(Question.skill.isnot(None)).all()
    logger.info(f"Verificando {len(questions)} questões com skill...")
    updated_questions = 0
    for q in questions:
        if not q.skill:
            continue
        raw = (q.skill or "").strip()
        parts = [p.strip().strip("{}") for p in raw.split(",") if p.strip()]
        if not parts:
            continue
        new_parts = []
        for p in parts:
            keep_id = norm_to_keep.get(norm(p)) or id_to_keep.get(p) or id_to_keep.get(p.strip("{}"))
            if keep_id is not None:
                new_parts.append(str(keep_id))
            else:
                new_parts.append(p)
        # Remover duplicatas preservando ordem
        seen = set()
        unique = []
        for x in new_parts:
            k = norm(x)
            if k not in seen:
                seen.add(k)
                unique.append(x)
        if unique != parts:
            q.skill = ",".join(unique) if len(unique) > 1 else unique[0]
            updated_questions += 1

    if updated_questions:
        logger.info(f"\nAtualizadas {updated_questions} questões (skill apontando para id mantido).")

    # Remover habilidades duplicadas (bulk delete por SQL para garantir que execute)
    from sqlalchemy import text
    deleted = 0
    for sid in ids_to_delete:
        try:
            session.execute(text("DELETE FROM skills WHERE id = :id"), {"id": str(sid)})
            deleted += 1
        except Exception as e:
            logger.warning(f"Erro ao remover {sid}: {e}")
    session.commit()
    logger.info(f"Removidas {deleted} habilidades duplicadas. Commit realizado.")
    logger.info("\nPróximo passo: rode o upload de matemática para corrigir descrições sem duplicar:")
    logger.info("  python scripts/upload_math_skills_from_organizacao.py")


if __name__ == "__main__":
    main()
