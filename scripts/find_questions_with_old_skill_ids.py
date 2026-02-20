"""
Script para encontrar questões que ainda usam os IDs antigos de skills.
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
from sqlalchemy import create_engine, or_
from sqlalchemy.orm import sessionmaker
from app.models.question import Question
from app.models.skill import Skill

# Mapeamento dos IDs antigos para os códigos (do skills.sql)
OLD_SKILL_MAPPINGS = {
    "da8ff008-2981-485d-a858-383f52593c4b": "5A1.2",  # subject_id errado no backup (matemática, deveria ser português)
    "da359cf2-6a86-4766-ac15-5b247a1db5ba": "5N2.2",
    "beac7b0a-eb5b-4ec1-bb35-c00d3235fd3f": "5E2.1",
    "b06258ef-c911-4d82-b005-73cca5c16703": "LP5L2.2",
    "cf0401a9-59fe-4718-b738-ffe59e87cd1e": "LP5L2.8",
    "37c8dabf-6c6b-4ca7-bab3-dfa027165e75": "LP5L2.7",
    "ac72cb5a-f3b7-4f81-ad52-4632b2cb03fd": "9L2.1"
}

# Códigos corretos (LP -> sem prefixo, etc)
CODE_CORRECTIONS = {
    "LP5L2.2": "5L2.2",
    "LP5L2.8": "5L2.8",
    "LP5L2.7": "5L2.7",
    "5A1.2": "5A1.2",  # Este está com subject_id errado mas código correto
    "5N2.2": "5N2.2",
    "5E2.1": "5E2.1",
    "9L2.1": None  # Este código não existe no banco atual
}

def get_db_session():
    database_url = Config.SQLALCHEMY_DATABASE_URI
    kwargs = {}
    if "postgresql" in (database_url or ""):
        kwargs["client_encoding"] = "utf8"
    engine = create_engine(database_url, **kwargs)
    return sessionmaker(bind=engine)()

def normalize_uuid(uuid_str):
    """Remove {} e converte para lowercase."""
    return uuid_str.strip().replace('{', '').replace('}', '').lower()

def main():
    session = get_db_session()
    
    print("\n" + "=" * 80)
    print("BUSCAR QUESTÕES COM IDs ANTIGOS DE SKILLS")
    print("=" * 80)
    
    # Buscar todas as questões que contenham qualquer um desses IDs antigos
    questions_to_fix = []
    
    for old_id, old_code in OLD_SKILL_MAPPINGS.items():
        # Procurar questões com esse ID (com ou sem {})
        questions = session.query(Question).filter(
            or_(
                Question.skill.like(f"%{old_id}%"),
                Question.skill.like(f"%{{{old_id}}}%")
            )
        ).all()
        
        if questions:
            print(f"\n🔍 ID Antigo: {old_id}")
            print(f"   Código: {old_code}")
            print(f"   Questões encontradas: {len(questions)}")
            
            for q in questions:
                print(f"   - Questão {q.id}: skill atual = {q.skill}")
                questions_to_fix.append({
                    'question_id': str(q.id),
                    'old_skill': q.skill,
                    'old_id': old_id,
                    'old_code': old_code,
                    'subject_id': q.subject_id
                })
    
    print("\n" + "=" * 80)
    print(f"TOTAL DE QUESTÕES A CORRIGIR: {len(questions_to_fix)}")
    print("=" * 80)
    
    if questions_to_fix:
        print("\nBuscando skills atuais no banco...")
        
        for item in questions_to_fix:
            old_code = item['old_code']
            corrected_code = CODE_CORRECTIONS.get(old_code, old_code)
            
            if corrected_code is None:
                print(f"\n⚠️  Questão {item['question_id']}: código {old_code} não tem correspondente no banco atual")
                continue
            
            # Buscar skill atual por código
            skill = session.query(Skill).filter_by(code=corrected_code).first()
            
            if skill:
                item['new_skill_id'] = str(skill.id)
                item['new_code'] = skill.code
                print(f"\n✓ Questão {item['question_id']}")
                print(f"  OLD: {item['old_skill']} (código: {old_code})")
                print(f"  NEW: {skill.id} (código: {skill.code})")
            else:
                print(f"\n✗ Questão {item['question_id']}: código {corrected_code} não encontrado no banco")
        
        # Atualizar as questões
        print("\n" + "=" * 80)
        print("ATUALIZAR QUESTÕES?")
        print("=" * 80)
        
        updated_count = 0
        for item in questions_to_fix:
            if 'new_skill_id' not in item:
                continue
            
            question = session.query(Question).filter_by(id=item['question_id']).first()
            if question:
                question.skill = item['new_skill_id']
                updated_count += 1
                print(f"✓ Atualizada questão {item['question_id']}")
        
        if updated_count > 0:
            print(f"\n{updated_count} questões atualizadas. Fazendo commit...")
            session.commit()
            print("✓ Commit realizado!")
        else:
            print("\nNenhuma questão foi atualizada.")
    
    session.close()

if __name__ == "__main__":
    main()
