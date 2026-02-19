"""
Lista habilidades que não têm nenhuma grade associada (grade_ids vazios).
Útil após a migração para skill_grade: habilidades que tinham grade_id NULL
ficam com 0 grades; você pode então associá-las às turmas corretas (via API ou script).

Uso:
    python scripts/list_skills_without_grades.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models.skill import Skill
from app import create_app, db

def main():
    app = create_app()
    with app.app_context():
        # Skills que não têm nenhuma linha em skill_grade
        all_skills = Skill.query.all()
        without = [s for s in all_skills if not (s.grades and len(s.grades) > 0)]
        print(f"Total de habilidades: {len(all_skills)}")
        print(f"Habilidades sem nenhuma grade: {len(without)}")
        if without:
            print("\nCode | Subject ID | Description (truncada)")
            print("-" * 80)
            for s in without[:100]:
                desc = (s.description or "")[:50]
                print(f"{s.code} | {s.subject_id or 'NULL'} | {desc}")
            if len(without) > 100:
                print(f"... e mais {len(without) - 100}.")

if __name__ == "__main__":
    main()
