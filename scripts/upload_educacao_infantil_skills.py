"""
Script para subir habilidades da Educação Infantil (Grupo 3 a 5 e Suporte 1 a 3).

Cria/atualiza apenas code, description e subject_id (sem associar grades).
As grades (Grupo 3-5 e Suporte 1-3) podem ser vinculadas depois via skill_grade.

Fonte: scripts/habilidades_educacao_infantil.json
subject_id = None (Educação Infantil sem disciplina específica).

Uso:
    python scripts/upload_educacao_infantil_skills.py
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# IDs das grades (Educação Infantil): Grupo 3 a 5 e Suporte 1 a 3
GRADE_IDS = {
    "Grupo 3": "35e6701a-87b9-4c46-82e5-44aa3458dd60",
    "Grupo 4": "15c413c1-c044-43df-a118-c8cd22281ade",
    "Grupo 5": "b3f73bca-27a7-4c86-8856-949056773776",
    "Suporte 1": "c40d2301-6afc-4c52-94df-6a9856970f6e",
    "Suporte 2": "0498b94e-a0de-483a-ad8e-a82f72abf128",
    "Suporte 3": "2e45c0f2-a979-475a-8f29-9576a837400b",
}

# EI01 -> [Grupo 3, Suporte 1], EI02 -> [Grupo 4, Suporte 2], EI03 -> [Grupo 5, Suporte 3]
CODE_PREFIX_TO_GRADES = {
    "EI01": [GRADE_IDS["Grupo 3"], GRADE_IDS["Suporte 1"]],
    "EI02": [GRADE_IDS["Grupo 4"], GRADE_IDS["Suporte 2"]],
    "EI03": [GRADE_IDS["Grupo 5"], GRADE_IDS["Suporte 3"]],
}

SUBJECT_ID_EI = None  # Educação Infantil sem disciplina específica


def normalize_code(codigo: str) -> str:
    """Normaliza código: E101 -> EI01, E102 -> EI02, E103 -> EI03."""
    if not codigo:
        return codigo
    s = (codigo or "").strip()
    for wrong, right in [("E101", "EI01"), ("E102", "EI02"), ("E103", "EI03")]:
        if s.upper().startswith(wrong) or re.match(rf"^{re.escape(wrong)}", s, re.I):
            s = right + s[len(wrong) :]
            break
    return s


def get_grade_ids_for_code(codigo: str) -> list:
    """Retorna lista de grade_id para o código (EI01 -> Grupo 3 + Suporte 1, etc.)."""
    codigo = normalize_code(codigo)
    for prefix, grade_ids in CODE_PREFIX_TO_GRADES.items():
        if codigo.upper().startswith(prefix.upper()):
            return list(grade_ids)
    return []


def load_habilidades():
    """Carrega habilidades do JSON."""
    path = os.path.join(SCRIPT_DIR, "habilidades_educacao_infantil.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("educacao_infantil", {}).get("habilidades", [])


def build_entries():
    """
    Gera lista de {code, description}. Sem grade_ids (vinculação com grades fica para depois).
    """
    habilidades = load_habilidades()
    by_code = {}
    for h in habilidades:
        codigo_raw = (h.get("codigo") or "").strip()
        desc = (h.get("descricao") or "").strip()
        if not codigo_raw or not desc:
            continue
        code = normalize_code(codigo_raw)
        if code not in by_code:
            by_code[code] = {"code": code, "description": desc}
    return list(by_code.values())


def get_db_session():
    """Sessão do banco."""
    from app.config import Config
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    database_url = Config.SQLALCHEMY_DATABASE_URI
    if not database_url:
        logger.error("DATABASE_URL não encontrada nas variáveis de ambiente")
        sys.exit(1)
    kwargs = {}
    if "postgresql" in (database_url or ""):
        kwargs["client_encoding"] = "utf8"
    engine = create_engine(database_url, **kwargs)
    Session = sessionmaker(bind=engine)
    return Session()


def upload_habilidades():
    """
    Sobe habilidades da Educação Infantil sem vincular grades (evita uso da tabela skill_grade).
    Apenas code, description, subject_id. Grades podem ser ajustadas depois.
    """
    logger.info("\n" + "=" * 70)
    logger.info("UPLOAD HABILIDADES EDUCAÇÃO INFANTIL (sem grades por enquanto)")
    logger.info("=" * 70)

    logger.info("\nCarregando habilidades_educacao_infantil.json...")
    entries = build_entries()
    logger.info("Total de habilidades a processar: %s", len(entries))

    from app.models.skill import Skill
    from sqlalchemy.orm import noload

    stats = {"updated": 0, "created": 0, "errors": 0, "skipped": 0}
    session = get_db_session()

    try:
        for idx, hab in enumerate(entries, 1):
            code = hab.get("code")
            description = hab.get("description")

            if not code or not description:
                stats["skipped"] += 1
                continue

            try:
                # noload(Skill.grades) evita JOIN com skill_grade (tabela pode não existir)
                skill = (
                    session.query(Skill)
                    .options(noload(Skill.grades))
                    .filter_by(code=code, subject_id=SUBJECT_ID_EI)
                    .first()
                )

                if skill:
                    skill.description = description
                    stats["updated"] += 1
                    if idx % 30 == 0 or idx <= 5:
                        logger.info("  [%s/%s] Atualizada: %s", idx, len(entries), code)
                else:
                    skill = Skill(code=code, description=description, subject_id=SUBJECT_ID_EI)
                    session.add(skill)
                    session.flush()
                    stats["created"] += 1
                    if idx % 30 == 0 or idx <= 5:
                        logger.info("  [%s/%s] Criada: %s", idx, len(entries), code)

            except Exception as e:
                logger.error("  Erro em %s: %s", code, e)
                stats["errors"] += 1

        logger.info("\nSalvando alterações no banco...")
        session.commit()
        logger.info("Commit realizado.")

        logger.info("\n" + "=" * 70)
        logger.info("RELATÓRIO")
        logger.info("=" * 70)
        logger.info("  Total processado: %s", len(entries))
        logger.info("  Atualizadas: %s", stats["updated"])
        logger.info("  Criadas: %s", stats["created"])
        logger.info("  Puladas: %s", stats["skipped"])
        logger.info("  Erros: %s", stats["errors"])
        logger.info("=" * 70 + "\n")

    except Exception as e:
        logger.error("ERRO: %s", e)
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    upload_habilidades()
