"""
Script para subir habilidades da Educação Infantil (Grupo 3 a 5 e Suporte 1 a 3).
Sem apagar nem duplicar: se a habilidade já existir (code + subject_id), atualiza a descrição;
caso contrário, cria. subject_id = None e sem vincular grades (você ajusta depois).

Fonte: scripts/habilidades_educacao_infantil.json

Uso (rodar manualmente na raiz do projeto):
    python scripts/upload_educacao_infantil_skills.py
"""

import json
import os
import re
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Garantir variáveis de ambiente (igual a outros scripts que usam app.config)
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_ROOT, "app", ".env"))
except ImportError:
    pass

import logging

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SUBJECT_ID_EI = None  # Educação Infantil sem disciplina específica


def normalize_code(codigo: str) -> str:
    """Normaliza código: E101 -> EI01, E102 -> EI02, E103 -> EI03."""
    if not codigo:
        return codigo
    s = (codigo or "").strip()
    for wrong, right in [("E101", "EI01"), ("E102", "EI02"), ("E103", "EI03")]:
        if s.upper().startswith(wrong) or re.match(rf"^{re.escape(wrong)}", s, re.I):
            s = right + s[len(wrong):]
            break
    return s


def load_habilidades():
    """Carrega habilidades do JSON."""
    path = os.path.join(SCRIPT_DIR, "habilidades_educacao_infantil.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("educacao_infantil", {}).get("habilidades", [])


def build_entries():
    """Monta lista de entradas: code, description, subject_id=None, grade_id=None."""
    habilidades = load_habilidades()
    by_code = {}
    for h in habilidades:
        codigo_raw = (h.get("codigo") or "").strip()
        desc = (h.get("descricao") or "").strip()
        if not codigo_raw or not desc:
            continue
        code = normalize_code(codigo_raw)
        if code not in by_code:
            by_code[code] = {
                "code": code,
                "description": desc,
                "subject_id": SUBJECT_ID_EI,
                "grade_id": None,
            }
    return list(by_code.values())


def get_db_session():
    """Sessão do banco (igual ao script de matemática)."""
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
    Sobe habilidades da Educação Infantil.
    Se já existir (code + subject_id): só atualiza description.
    Se não existir: cria. Não toca em grades (evita skill_grade).
    """
    logger.info("\n" + "=" * 70)
    logger.info("UPLOAD HABILIDADES EDUCAÇÃO INFANTIL (Grupo 3-5 e Suporte 1-3)")
    logger.info("=" * 70)

    logger.info("\nCarregando habilidades_educacao_infantil.json...")
    habilidades = build_entries()
    logger.info("Total de habilidades a processar: %s", len(habilidades))

    if not habilidades:
        logger.warning("Nenhuma habilidade no JSON. Verifique o arquivo.")
        return

    from app.models.skill import Skill
    from sqlalchemy.orm import noload

    stats = {"updated": 0, "created": 0, "errors": 0, "skipped": 0}
    session = get_db_session()

    try:
        logger.info("\n" + "=" * 70)
        logger.info("PROCESSANDO HABILIDADES")
        logger.info("=" * 70 + "\n")

        for idx, hab in enumerate(habilidades, 1):
            code = hab.get("code")
            description = hab.get("description")
            subject_id = hab.get("subject_id")

            if not code or not description:
                logger.warning("  [%s/%s] Sem code ou description, pulando...", idx, len(habilidades))
                stats["skipped"] += 1
                continue

            try:
                # noload(grades) evita JOIN com skill_grade (tabela pode não existir)
                skill = (
                    session.query(Skill)
                    .options(noload(Skill.grades))
                    .filter_by(code=code, subject_id=subject_id)
                    .first()
                )

                if skill:
                    skill.description = description
                    stats["updated"] += 1
                    logger.info("  [%s/%s] Atualizada: %s", idx, len(habilidades), code)
                else:
                    skill = Skill(code=code, description=description, subject_id=subject_id)
                    session.add(skill)
                    session.flush()
                    stats["created"] += 1
                    logger.info("  [%s/%s] Criada: %s", idx, len(habilidades), code)

            except Exception as e:
                logger.error("  Erro em %s: %s", code, e)
                stats["errors"] += 1

        logger.info("\nSalvando alterações no banco...")
        session.commit()
        logger.info("Commit realizado.")

        logger.info("\n" + "=" * 70)
        logger.info("RELATÓRIO")
        logger.info("=" * 70)
        logger.info("  Total processado: %s", len(habilidades))
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
