"""
Script para encontrar correspondência por similaridade para o código 9L2.1
"""

import os
import sys
from difflib import SequenceMatcher

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_ROOT, "app", ".env"))
except ImportError:
    pass

from app.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, noload
from app.models.question import Question
from app.models.skill import Skill

OLD_DESCRIPTION_9L2_1 = "Analisar elementos constitutivos de textos pertencentes ao domínio literário."
OLD_CODE = "9L2.1"
QUESTION_ID = "bbf5b943-2ad7-4468-ac5e-675bc34a0eff"

def similarity_ratio(str1: str, str2: str) -> float:
    """Calcula a similaridade entre duas strings (0.0 a 1.0)."""
    return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()

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
    print(f"BUSCAR CORRESPONDÊNCIA POR SIMILARIDADE PARA: {OLD_CODE}")
    print("=" * 80)
    print(f"Descrição antiga: {OLD_DESCRIPTION_9L2_1}")
    print()
    
    # Buscar todas as skills de Português (subject_id do 9º ano)
    skills = session.query(Skill).options(noload(Skill.grades)).all()
    
    best_matches = []
    
    for skill in skills:
        score = similarity_ratio(OLD_DESCRIPTION_9L2_1, skill.description)
        best_matches.append({
            'id': str(skill.id),
            'code': skill.code,
            'description': skill.description,
            'subject_id': skill.subject_id,
            'score': score
        })
    
    # Ordenar por score
    best_matches.sort(key=lambda x: x['score'], reverse=True)
    
    print("TOP 10 CORRESPONDÊNCIAS POR SIMILARIDADE:")
    print("-" * 80)
    
    for idx, match in enumerate(best_matches[:10], 1):
        print(f"\n{idx}. Score: {match['score']*100:.2f}%")
        print(f"   Code: {match['code']}")
        print(f"   Description: {match['description'][:120]}...")
        print(f"   Subject ID: {match['subject_id']}")
    
    # Atualizar com a melhor correspondência se score > 70%
    if best_matches and best_matches[0]['score'] > 0.70:
        print("\n" + "=" * 80)
        print("ATUALIZAR QUESTÃO COM A MELHOR CORRESPONDÊNCIA?")
        print("=" * 80)
        
        best = best_matches[0]
        print(f"\nMelhor correspondência: {best['code']} ({best['score']*100:.2f}%)")
        print(f"Descrição: {best['description']}")
        
        question = session.query(Question).filter_by(id=QUESTION_ID).first()
        if question:
            print(f"\nQuestão encontrada: {question.id}")
            print(f"Skill atual: {question.skill}")
            print(f"Skill nova: {best['id']}")
            
            question.skill = best['id']
            session.commit()
            print("\n✓ Questão atualizada com sucesso!")
        else:
            print("\n✗ Questão não encontrada")
    else:
        print("\n⚠️ Nenhuma correspondência com score > 70% encontrada")
    
    session.close()

if __name__ == "__main__":
    main()
