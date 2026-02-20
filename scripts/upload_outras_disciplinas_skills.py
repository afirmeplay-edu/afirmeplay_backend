"""
Script para upload das habilidades BNCC de outras disciplinas:
Arte, Educação Física, Língua Inglesa, Ciências, História, Geografia, Ensino Religioso.

Uso:
    python scripts/upload_outras_disciplinas_skills.py
"""

import os
import sys
import re
import json

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_ROOT, "app", ".env"))
except ImportError:
    pass

import logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Mapeamento subject name → subject_id
# ---------------------------------------------------------------------------
SUBJECT_IDS = {
    "Arte":             "2fec15b8-75d9-4dab-95e5-6bee4e8e8cbf",
    "Educação Física":  "3b393985-82d5-46e7-9b5a-6270bedf77ab",
    "Língua Inglesa":   "fde6213e-1efe-4eb6-b766-d4335e7caee5",
    "Ciências":         "f077ebd9-0588-404c-81d5-02534b92ba2f",
    "História":         "7af40699-ebf8-457f-9dd9-2cec2dca8cef",
    "Geografia":        "24710a67-1fbf-40b6-83fb-ef9f5bad5df1",
    "Ensino Religioso": "8687630b-09b0-4d2e-ba3c-096125160e42",
}

# ---------------------------------------------------------------------------
# Mapeamento de número do ano → grade_id
# ---------------------------------------------------------------------------
GRADE_IDS = {
    1: "391ed6e8-fc45-46f8-8e4c-065005d2329f",
    2: "74821122-e632-4301-b6f5-42b92b802a55",
    3: "ea1ed64b-c9f5-4156-93b2-497ecf9e0d84",
    4: "b8cdea4d-22fe-4647-a9f3-c575eb82c514",
    5: "f5688bb2-9624-487f-ab1f-40b191c96b76",
    6: "75bea034-3427-4e98-896d-23493d36a84e",
    7: "4128c187-5e33-4ff9-a96d-e7eb9ddbe04e",
    8: "b6760b9b-2758-4d14-a650-c3a30c0aeb3b",
    9: "3c68a0b5-9613-469e-8376-6fb678c60363",
}

JSON_FILE = os.path.join(PROJECT_ROOT, "scripts", "habilidades_outras_disciplinas.json")


def parse_series(series_str: str):
    """
    Converte o campo 'series' em lista de grade_ids.

    Exemplos:
      "1º ano"          → [grade_id_1]
      "1º ao 5º ano"    → [grade_id_1..5]
      "6º ao 9º ano"    → [grade_id_6..9]
      "6º e 7º anos"    → [grade_id_6, grade_id_7]
      "2º ano"          → [grade_id_2]
    """
    s = series_str.lower()
    nums = [int(x) for x in re.findall(r"(\d+)º", s)]

    if not nums:
        return []

    # "X ao Y" → intervalo
    if "ao" in s and len(nums) >= 2:
        grades = list(range(nums[0], nums[-1] + 1))
    # "X e Y" → específicos
    elif "e" in s:
        grades = nums
    # único
    else:
        grades = [nums[0]]

    return [GRADE_IDS[n] for n in grades if n in GRADE_IDS]


def get_db_session():
    from app.config import Config
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    database_url = Config.SQLALCHEMY_DATABASE_URI
    if not database_url:
        logger.error("DATABASE_URL não encontrada")
        sys.exit(1)
    kwargs = {}
    if "postgresql" in (database_url or ""):
        kwargs["client_encoding"] = "utf8"
    engine = create_engine(database_url, **kwargs)
    return sessionmaker(bind=engine)()


def main():
    logger.info("\n" + "=" * 70)
    logger.info("UPLOAD HABILIDADES BNCC – OUTRAS DISCIPLINAS")
    logger.info("=" * 70)

    from sqlalchemy import text
    from app.models.skill import Skill
    from sqlalchemy.orm import noload
    from uuid import UUID

    session = get_db_session()

    with open(JSON_FILE, encoding="utf-8") as f:
        data = json.load(f)

    habilidades_bncc = data["habilidades_bncc"]

    total_inseridas = 0
    total_atualizadas = 0
    total_erros = 0

    for subject_name, habilidades in habilidades_bncc.items():
        subject_id = SUBJECT_IDS.get(subject_name)
        if not subject_id:
            logger.warning("Subject desconhecido (ignorado): %s", subject_name)
            continue

        logger.info("\n--- %s (subject_id: %s) ---", subject_name, subject_id)

        for h in habilidades:
            code = h["codigo"].strip()
            description = h["descricao"].strip()
            grade_ids = parse_series(h.get("series", ""))

            try:
                # Buscar skill existente
                skill = (
                    session.query(Skill)
                    .options(noload(Skill.grades))
                    .filter_by(code=code, subject_id=subject_id)
                    .first()
                )

                if skill:
                    skill.description = description
                    total_atualizadas += 1
                    action = "Atualizada"
                else:
                    skill = Skill(code=code, description=description, subject_id=subject_id)
                    session.add(skill)
                    total_inseridas += 1
                    action = "Inserida "

                session.flush()

                # Sincronizar skill_grade
                if grade_ids:
                    session.execute(
                        text("DELETE FROM skill_grade WHERE skill_id = :sid"),
                        {"sid": skill.id},
                    )
                    for gid in grade_ids:
                        session.execute(
                            text(
                                "INSERT INTO skill_grade (skill_id, grade_id) "
                                "VALUES (:sid, :gid) ON CONFLICT DO NOTHING"
                            ),
                            {"sid": skill.id, "gid": UUID(gid)},
                        )

                logger.info(
                    "  [%s] %s  → %s",
                    action,
                    code,
                    ", ".join(str(g) for g in grade_ids) if grade_ids else "sem grade",
                )

            except Exception as e:
                logger.error("  ERRO em %s: %s", code, e)
                session.rollback()
                total_erros += 1
                continue

    logger.info("\nCommit final...")
    session.commit()
    logger.info("Commit realizado.")
    session.close()

    logger.info("\n" + "=" * 70)
    logger.info("RELATÓRIO FINAL")
    logger.info("  Inseridas:  %s", total_inseridas)
    logger.info("  Atualizadas:%s", total_atualizadas)
    logger.info("  Erros:      %s", total_erros)
    logger.info("=" * 70 + "\n")


if __name__ == "__main__":
    main()
