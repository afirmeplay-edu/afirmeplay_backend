"""
Script para investigar questões específicas que ainda mostram apenas ID.
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
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.question import Question
from app.models.skill import Skill

# IDs fornecidos pelo usuário
QUESTION_IDS = [
    "da8ff008-2981-485d-a858-383f52593c4b",
    "da359cf2-6a86-4766-ac15-5b247a1db5ba",
    "beac7b0a-eb5b-4ec1-bb35-c00d3235fd3f",
    "b06258ef-c911-4d82-b005-73cca5c16703",
    "cf0401a9-59fe-4718-b738-ffe59e87cd1e",
    "37c8dabf-6c6b-4ca7-bab3-dfa027165e75",
    "ac72cb5a-f3b7-4f81-ad52-4632b2cb03fd"
]

def get_db_session():
    database_url = Config.SQLALCHEMY_DATABASE_URI
    kwargs = {}
    if "postgresql" in (database_url or ""):
        kwargs["client_encoding"] = "utf8"
    engine = create_engine(database_url, **kwargs)
    return sessionmaker(bind=engine)()

def main():
    session = get_db_session()
    
    print("\n" + "=" * 80)
    print("INVESTIGAR QUESTÕES COM IDs NO RELATÓRIO")
    print("=" * 80)
    
    for idx, question_id in enumerate(QUESTION_IDS, 1):
        print(f"\n[{idx}/{len(QUESTION_IDS)}] Questão: {question_id}")
        print("-" * 80)
        
        question = session.query(Question).filter_by(id=question_id).first()
        
        if not question:
            print("  ✗ Questão não encontrada no banco!")
            continue
        
        print(f"  Enunciado: {question.statement[:100]}...")
        print(f"  Subject ID: {question.subject_id}")
        print(f"  Skill (raw): {question.skill}")
        
        # Tentar resolver a skill
        if question.skill:
            skill_id_clean = question.skill.strip('{}')
            
            # Tentar como UUID primeiro
            skill_obj = session.query(Skill).filter_by(id=skill_id_clean).first()
            
            if skill_obj:
                print(f"  ✓ Skill encontrada por ID:")
                print(f"    Code: {skill_obj.code}")
                print(f"    Description: {skill_obj.description[:100]}...")
            else:
                # Tentar como código
                skill_obj = session.query(Skill).filter_by(code=skill_id_clean).first()
                if skill_obj:
                    print(f"  ✓ Skill encontrada por CODE:")
                    print(f"    ID: {skill_obj.id}")
                    print(f"    Code: {skill_obj.code}")
                    print(f"    Description: {skill_obj.description[:100]}...")
                else:
                    print(f"  ✗ Skill NÃO encontrada (nem por ID nem por CODE)")
                    print(f"    Tentando buscar no skills.sql...")
                    
    session.close()
    print("\n" + "=" * 80)

if __name__ == "__main__":
    main()
