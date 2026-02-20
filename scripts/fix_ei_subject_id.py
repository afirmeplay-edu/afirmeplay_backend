"""
Script para corrigir subject_id das habilidades de Educação Infantil.

Problema: skills EI têm subject_id = None, então não aparecem no frontend quando
o filtro é por disciplina (GET /skills/subject/<subject_id>).

Solução:
1. Criar subject "Educação Infantil" se não existir
2. Atualizar todas as skills com código EI01/EI02/EI03 para usar esse subject_id

Uso:
    python scripts/fix_ei_subject_id.py
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

import logging

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


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


def main():
    logger.info("\n" + "=" * 70)
    logger.info("CORRIGIR SUBJECT_ID DAS HABILIDADES DE EDUCAÇÃO INFANTIL")
    logger.info("=" * 70)
    
    from app.models.subject import Subject
    from app.models.skill import Skill
    from sqlalchemy.orm import noload
    
    session = get_db_session()
    
    try:
        # 1) Criar ou buscar subject "Educação Infantil"
        logger.info("\nVerificando subject 'Educação Infantil'...")
        subject = session.query(Subject).filter_by(name="Educação Infantil").first()
        
        if subject:
            logger.info("  Subject já existe: %s (ID: %s)", subject.name, subject.id)
        else:
            logger.info("  Subject não existe. Criando...")
            import uuid
            subject = Subject(id=str(uuid.uuid4()), name="Educação Infantil")
            session.add(subject)
            session.flush()
            logger.info("  Criado: %s (ID: %s)", subject.name, subject.id)
        
        ei_subject_id = subject.id
        
        # 2) Buscar todas as skills EI (subject_id = None e código EI01/EI02/EI03)
        logger.info("\nBuscando skills de Educação Infantil (subject_id = None)...")
        
        # Buscar skills com subject_id = None e código começando com EI
        ei_skills = (
            session.query(Skill)
            .options(noload(Skill.grades))
            .filter(Skill.subject_id.is_(None))
            .filter(Skill.code.op('~')(r'^EI0[123]'))  # Regex: EI01, EI02, EI03
            .all()
        )
        
        logger.info("  Encontradas: %s skills EI com subject_id = None", len(ei_skills))
        
        if not ei_skills:
            logger.info("\nNenhuma skill EI para atualizar. Encerrando.")
            return
        
        # 3) Atualizar subject_id
        logger.info("\nAtualizando subject_id para '%s'...", ei_subject_id)
        
        updated = 0
        for skill in ei_skills:
            skill.subject_id = ei_subject_id
            updated += 1
            if updated <= 10 or updated % 30 == 0:
                logger.info("  [%s/%s] Atualizada: %s", updated, len(ei_skills), skill.code)
        
        logger.info("\nCommit no banco...")
        session.commit()
        logger.info("Commit realizado.")
        
        logger.info("\n" + "=" * 70)
        logger.info("RELATÓRIO")
        logger.info("=" * 70)
        logger.info("  Subject ID: %s", ei_subject_id)
        logger.info("  Skills atualizadas: %s", updated)
        logger.info("=" * 70 + "\n")
        
        logger.info("Agora o frontend pode chamar: GET /skills/subject/%s", ei_subject_id)
        logger.info("para buscar todas as habilidades de Educação Infantil.\n")
    
    except Exception as e:
        logger.error("ERRO: %s", e)
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
