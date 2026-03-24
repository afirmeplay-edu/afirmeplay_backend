"""
Script para upload completo das habilidades BNCC (partes 1, 2 e 3).

Faz upsert (insert ou update) das habilidades de:
- Arte, Educação Física (parte 1)
- Língua Inglesa, Ciências (parte 2)
- História, Geografia, Ensino Religioso (parte 3)

Uso:
    python scripts/upload_bncc_completo.py
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

JSON_FILES = [
    os.path.join(PROJECT_ROOT, "scripts", "bncc_parte1.json"),
    os.path.join(PROJECT_ROOT, "scripts", "bncc_parte2.json"),
    os.path.join(PROJECT_ROOT, "scripts", "bncc_parte3.json"),
]


def parse_series(series_str: str):
    """
    Converte o campo 'series' ou 'series_aplicaveis' em lista de grade_ids.

    Exemplos:
      "1º ano"          → [grade_id_1]
      "1º ao 5º ano"    → [grade_id_1..5]
      "6º ao 9º ano"    → [grade_id_6..9]
      "6º e 7º anos"    → [grade_id_6, grade_id_7]
      "1º Ano"          → [grade_id_1]
      "1º e 2º Ano"     → [grade_id_1, grade_id_2]
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


def load_all_skills_data():
    """
    Carrega os 3 JSONs e retorna lista de (subject_id, codigo, descricao, [grade_ids])
    """
    all_entries = []
    
    for json_file in JSON_FILES:
        with open(json_file, encoding="utf-8") as f:
            data = json.load(f)
        
        # Detectar chave raiz (pode ser bncc_habilidades_parte_1, _2 ou _3)
        root_key = list(data.keys())[0]
        bncc_data = data[root_key]
        
        for disciplina in bncc_data["disciplinas"]:
            subject_name = disciplina["nome"]
            subject_id = SUBJECT_IDS.get(subject_name)
            
            if not subject_id:
                logger.warning("Subject desconhecido (ignorado): %s", subject_name)
                continue
            
            # Processar habilidades_compartilhadas
            for grupo in disciplina.get("habilidades_compartilhadas", []):
                series_aplicaveis = grupo.get("series_aplicaveis", "")
                grade_ids = parse_series(series_aplicaveis)
                
                for hab in grupo.get("habilidades", []):
                    codigo = hab["codigo"].strip()
                    descricao = hab["descricao"].strip()
                    all_entries.append((subject_id, codigo, descricao, grade_ids))
            
            # Processar habilidades_unicas_por_serie
            for serie_grupo in disciplina.get("habilidades_unicas_por_serie", []):
                serie = serie_grupo.get("serie", "")
                grade_ids = parse_series(serie)
                
                for hab in serie_grupo.get("habilidades", []):
                    codigo = hab["codigo"].strip()
                    descricao = hab["descricao"].strip()
                    all_entries.append((subject_id, codigo, descricao, grade_ids))
    
    return all_entries


def main():
    logger.info("\n" + "=" * 70)
    logger.info("UPLOAD BNCC COMPLETO – UPSERT")
    logger.info("=" * 70)
    
    from sqlalchemy import text
    from app.models.skill import Skill
    from sqlalchemy.orm import noload
    from uuid import UUID
    
    session = get_db_session()
    
    try:
        logger.info("\nCarregando habilidades dos 3 JSONs...")
        entries = load_all_skills_data()
        logger.info("  Total de habilidades a processar: %s", len(entries))
        
        inseridas = 0
        atualizadas = 0
        erros = 0
        
        for subject_id, codigo, descricao, grade_ids in entries:
            try:
                # Buscar skill existente
                skill = (
                    session.query(Skill)
                    .options(noload(Skill.grades))
                    .filter_by(code=codigo, subject_id=subject_id)
                    .first()
                )
                
                if skill:
                    # Update
                    skill.description = descricao
                    atualizadas += 1
                    action = "Atualizada"
                else:
                    # Insert
                    skill = Skill(code=codigo, description=descricao, subject_id=subject_id)
                    session.add(skill)
                    inseridas += 1
                    action = "Inserida "
                
                session.flush()
                
                # Recriar skill_grade (sempre)
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
                
                # Log resumido (apenas primeiras/últimas e múltiplos de 50)
                total_processed = inseridas + atualizadas
                if total_processed <= 20 or total_processed % 50 == 0 or total_processed == len(entries):
                    logger.info(
                        "  [%s/%s] [%s] %s",
                        total_processed,
                        len(entries),
                        action,
                        codigo,
                    )
            
            except Exception as e:
                logger.error("  ERRO em %s: %s", codigo, e)
                session.rollback()
                erros += 1
                continue
        
        logger.info("\nCommit final...")
        session.commit()
        logger.info("Commit realizado.")
        session.close()
        
        logger.info("\n" + "=" * 70)
        logger.info("RELATÓRIO FINAL")
        logger.info("  Inseridas:  %s", inseridas)
        logger.info("  Atualizadas:%s", atualizadas)
        logger.info("  Total:      %s", inseridas + atualizadas)
        logger.info("  Erros:      %s", erros)
        logger.info("=" * 70 + "\n")
    
    except Exception as e:
        logger.error("ERRO GERAL: %s", e)
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
