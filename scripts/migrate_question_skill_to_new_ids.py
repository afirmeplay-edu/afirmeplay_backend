"""
Script para migrar question.skill de IDs antigos para IDs novos.

Problema:
  question.skill contém UUIDs antigos de skills que não existem mais.
  Com a recriação da tabela skills, os códigos permanecem mas os IDs mudaram.

Solução:
  1. Parsear skills.sql (backup dos IDs antigos) para obter old_id -> code
  2. Buscar skills atuais no banco: (code, subject_id) -> new_id
  3. Para cada questão, substituir old_id por new_id em question.skill

Uso:
    python scripts/migrate_question_skill_to_new_ids.py
"""

import os
import sys
import re
from typing import Dict, Optional, Tuple
from difflib import SequenceMatcher

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

SKILLS_SQL_PATH = os.path.join(PROJECT_ROOT, "skills.sql")

# Regex para extrair (uuid, code, description) de cada linha de valor no SQL
# Exemplo: ('uuid'::uuid,'CODE','description',...)
UUID_CODE_DESC_PATTERN = re.compile(
    r"\('([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})'::uuid,'([^']+)','([^']*)'",
    re.IGNORECASE
)

# Regex para validar se uma string parece um UUID
UUID_PATTERN = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)


def similarity_ratio(str1: str, str2: str) -> float:
    """Calcula a similaridade entre duas strings (0.0 a 1.0)."""
    return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()


def parse_skills_sql() -> Tuple[Dict[str, str], Dict[str, str]]:
    """
    Parseia skills.sql e retorna dois dicionários:
    - {old_id: code}
    - {old_id: description}
    Normaliza os UUIDs (lowercase, sem {}).
    """
    logger.info("\n" + "=" * 70)
    logger.info("PARSE skills.sql")
    logger.info("=" * 70)
    
    old_id_to_code = {}
    old_id_to_desc = {}
    
    with open(SKILLS_SQL_PATH, encoding="utf-8", errors="ignore") as f:
        for line_num, line in enumerate(f, start=1):
            matches = UUID_CODE_DESC_PATTERN.findall(line)
            for uuid_str, code, description in matches:
                normalized_uuid = uuid_str.lower().strip()
                old_id_to_code[normalized_uuid] = code.strip()
                old_id_to_desc[normalized_uuid] = description.strip()
    
    logger.info("  Mapeamentos extraídos: %s", len(old_id_to_code))
    return old_id_to_code, old_id_to_desc


def load_current_skills(session):
    """
    Carrega as skills atuais do banco e retorna três dicionários:
    - code_subject_to_id: {(code, subject_id): skill_id}
    - code_to_id_fallback: {code: skill_id} (primeiro encontrado)
    - all_skills: lista de (skill_id, code, description, subject_id) para busca por similaridade
    """
    from app.models.skill import Skill
    from sqlalchemy.orm import noload
    
    logger.info("\n" + "=" * 70)
    logger.info("CARREGAR SKILLS ATUAIS")
    logger.info("=" * 70)
    
    skills = session.query(Skill).options(noload(Skill.grades)).all()
    
    code_subject_to_id = {}
    code_to_id_fallback = {}
    all_skills = []
    
    for skill in skills:
        key = (skill.code, skill.subject_id)
        code_subject_to_id[key] = str(skill.id)
        
        if skill.code not in code_to_id_fallback:
            code_to_id_fallback[skill.code] = str(skill.id)
        
        all_skills.append((str(skill.id), skill.code, skill.description, skill.subject_id))
    
    logger.info("  Skills atuais carregadas: %s", len(skills))
    logger.info("  Mapeamentos (code, subject_id) -> id: %s", len(code_subject_to_id))
    logger.info("  Mapeamentos code -> id (fallback): %s", len(code_to_id_fallback))
    
    return code_subject_to_id, code_to_id_fallback, all_skills


def normalize_uuid(value: str) -> str:
    """Remove {} e converte para lowercase."""
    return value.strip().replace('{', '').replace('}', '').lower()


def is_uuid(value: str) -> bool:
    """Verifica se a string parece um UUID."""
    return UUID_PATTERN.match(normalize_uuid(value)) is not None


def map_skill_value(
    value: str,
    old_id_to_code: Dict[str, str],
    old_id_to_desc: Dict[str, str],
    code_subject_to_id: Dict[Tuple[str, Optional[str]], str],
    code_to_id_fallback: Dict[str, str],
    all_skills: list,
    question_subject_id: Optional[str],
    similarity_threshold: float = 0.75
) -> Tuple[str, Optional[str]]:
    """
    Mapeia um valor de skill (que pode ser old_id, code ou outro formato).
    Retorna (novo_id ou valor original, code_encontrado) se encontrado.
    Se não encontrar por código, tenta buscar por similaridade de descrição.
    """
    normalized = normalize_uuid(value)
    
    # Se não parece UUID ou não está no dump antigo, retornar como está
    if not is_uuid(value) or normalized not in old_id_to_code:
        return value, None
    
    # Pegar code e description do mapeamento antigo
    code = old_id_to_code[normalized]
    old_description = old_id_to_desc.get(normalized, "")
    
    # Buscar novo id: primeiro por (code, subject_id), senão fallback por code
    new_id = code_subject_to_id.get((code, question_subject_id))
    if not new_id:
        new_id = code_to_id_fallback.get(code)
    
    if new_id:
        return new_id, code
    
    # Se não encontrou por código, tentar por similaridade de descrição
    if old_description:
        logger.info("  Código não encontrado: %s. Tentando por similaridade de descrição...", code)
        
        best_match_id = None
        best_match_code = None
        best_match_score = 0.0
        best_match_desc = ""
        
        for skill_id, skill_code, skill_desc, skill_subject_id in all_skills:
            # Priorizar skills do mesmo subject_id se disponível
            subject_bonus = 0.05 if question_subject_id and skill_subject_id == question_subject_id else 0.0
            
            score = similarity_ratio(old_description, skill_desc) + subject_bonus
            
            if score > best_match_score:
                best_match_score = score
                best_match_id = skill_id
                best_match_code = skill_code
                best_match_desc = skill_desc
        
        if best_match_score >= similarity_threshold:
            logger.info("  ✓ Encontrada por similaridade (%.2f%%): %s", 
                       best_match_score * 100, best_match_code)
            logger.info("    OLD: %s", old_description[:100])
            logger.info("    NEW: %s", best_match_desc[:100])
            return best_match_id, best_match_code
        else:
            logger.warning("  ✗ Nenhuma correspondência similar encontrada (melhor: %.2f%% - %s)", 
                          best_match_score * 100, best_match_code)
    
    # Não encontrou skill atual
    logger.warning("  Código não encontrado: %s (old_id: %s)", code, value)
    return value, None


def update_questions(
    session,
    old_id_to_code: Dict[str, str],
    old_id_to_desc: Dict[str, str],
    code_subject_to_id: Dict[Tuple[str, Optional[str]], str],
    code_to_id_fallback: Dict[str, str],
    all_skills: list
):
    """
    Atualiza question.skill de todas as questões, substituindo old_id por new_id.
    Tenta encontrar por código primeiro, depois por similaridade de descrição.
    """
    from app.models.question import Question
    
    logger.info("\n" + "=" * 70)
    logger.info("ATUALIZAR question.skill")
    logger.info("=" * 70)
    
    questions = session.query(Question).filter(
        Question.skill.isnot(None),
        Question.skill != '',
        Question.skill != '{}'
    ).all()
    
    logger.info("  Questões com skill preenchido: %s", len(questions))
    
    total_updated = 0
    total_parts_mapped = 0
    total_parts_similar = 0
    total_parts_not_found = 0
    
    for idx, question in enumerate(questions, start=1):
        original_skill = question.skill
        
        # Split por vírgula (pode ter múltiplas skills)
        parts = [p.strip() for p in original_skill.split(',') if p.strip()]
        
        new_parts = []
        changed = False
        
        for part in parts:
            new_value, found_code = map_skill_value(
                part,
                old_id_to_code,
                old_id_to_desc,
                code_subject_to_id,
                code_to_id_fallback,
                all_skills,
                question.subject_id
            )
            new_parts.append(new_value)
            
            if new_value != part:
                changed = True
                if is_uuid(part) and normalize_uuid(part) in old_id_to_code:
                    total_parts_mapped += 1
                    if found_code:
                        # Verificar se foi por similaridade
                        old_code = old_id_to_code[normalize_uuid(part)]
                        if found_code != old_code:
                            total_parts_similar += 1
                    else:
                        total_parts_not_found += 1
        
        if changed:
            question.skill = ','.join(new_parts)
            total_updated += 1
            
            # Log primeiras 10, depois a cada 100
            if total_updated <= 10 or total_updated % 100 == 0:
                logger.info("  [%s/%s] Atualizada: %s -> %s", 
                           total_updated, len(questions), 
                           original_skill[:60] + '...' if len(original_skill) > 60 else original_skill,
                           question.skill[:60] + '...' if len(question.skill) > 60 else question.skill)
    
    logger.info("\n" + "=" * 70)
    logger.info("RELATÓRIO")
    logger.info("=" * 70)
    logger.info("  Questões analisadas: %s", len(questions))
    logger.info("  Questões atualizadas: %s", total_updated)
    logger.info("  Skills mapeadas (old -> new): %s", total_parts_mapped)
    logger.info("  Skills encontradas por similaridade: %s", total_parts_similar)
    logger.info("  Skills não encontradas: %s", total_parts_not_found)
    logger.info("=" * 70)
    
    return total_updated


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
    logger.info("MIGRAÇÃO: question.skill (OLD IDs -> NEW IDs)")
    logger.info("Com busca por similaridade de descrição")
    logger.info("=" * 70)
    
    session = None
    try:
        # 1. Parse skills.sql
        old_id_to_code, old_id_to_desc = parse_skills_sql()
        
        # 2. Conectar ao banco e carregar skills atuais
        session = get_db_session()
        code_subject_to_id, code_to_id_fallback, all_skills = load_current_skills(session)
        
        # 3. Atualizar questões
        total_updated = update_questions(
            session,
            old_id_to_code,
            old_id_to_desc,
            code_subject_to_id,
            code_to_id_fallback,
            all_skills
        )
        
        # 4. Commit
        if total_updated > 0:
            logger.info("\nCommit no banco...")
            session.commit()
            logger.info("Commit realizado.\n")
        else:
            logger.info("\nNenhuma questão foi modificada. Nada a fazer.\n")
        
        session.close()
        
    except Exception as e:
        logger.error("ERRO: %s", e, exc_info=True)
        if session:
            try:
                session.rollback()
                session.close()
            except Exception as rb_e:
                logger.error("Erro ao fazer rollback: %s", rb_e)
        raise


if __name__ == "__main__":
    main()
