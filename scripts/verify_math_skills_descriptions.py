"""
Script de VERIFICAÇÃO (somente leitura): confere se as habilidades de Matemática
no banco têm as descrições corretas conforme organizacao_matematica_anos_finais.json.

Hipótese: um script anterior atualizou por code e trocou a descrição das habilidades
de matemática pela de português (deixando matemática com descrição errada).

- Habilidades de Português: consideradas corretas (não alteramos).
- Habilidades de Matemática: devem ter descrição igual ao JSON de matemática.

NÃO ALTERA NADA NO BANCO. Apenas consulta e imprime relatório.
Uso: python scripts/verify_math_skills_descriptions.py
"""

import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_ROOT, "app", ".env"))
except ImportError:
    pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MATEMATICA_ID = "44f3421e-ca84-4fe5-a449-a3d9bfa3db3d"
PORTUGUES_ID = "4d29b4f1-7bd7-42c0-84d5-111dc7025b90"


def load_math_expected():
    """Carrega código -> descrição esperada do JSON de matemática (anos finais)."""
    path = os.path.join(SCRIPT_DIR, "organizacao_matematica_anos_finais.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    expected = {}
    for block in data.get("habilidades_compartilhadas", []):
        for h in block.get("habilidades", []):
            code = (h.get("codigo") or "").strip()
            desc = (h.get("descricao") or "").strip()
            if code:
                expected[code] = desc
    for block in data.get("habilidades_unicas_por_serie", []):
        for h in block.get("habilidades", []):
            code = (h.get("codigo") or "").strip()
            desc = (h.get("descricao") or "").strip()
            if code:
                expected[code] = desc
    return expected


def get_db_session():
    from app.config import Config
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    database_url = Config.SQLALCHEMY_DATABASE_URI
    if not database_url:
        raise RuntimeError("SQLALCHEMY_DATABASE_URI não configurada")
    kwargs = {}
    if "postgresql" in (database_url or ""):
        kwargs["client_encoding"] = "utf8"
    engine = create_engine(database_url, **kwargs)
    Session = sessionmaker(bind=engine)
    return Session()


def main():
    print("=" * 70)
    print("VERIFICAÇÃO: habilidades de Matemática x organizacao_matematica_anos_finais.json")
    print("(Somente leitura — nenhuma alteração no banco)")
    print("=" * 70)

    expected = load_math_expected()
    print(f"\nCódigos de matemática no JSON: {len(expected)}")

    session = get_db_session()
    from app.models.skill import Skill
    from app.models.subject import Subject

    # Nomes das disciplinas para o relatório
    subjects = {s.id: s.name for s in session.query(Subject).filter(Subject.id.in_([MATEMATICA_ID, PORTUGUES_ID])).all()}
    mat_name = subjects.get(MATEMATICA_ID, "Matemática")
    pt_name = subjects.get(PORTUGUES_ID, "Português")

    # Habilidades no banco com code que existe no JSON (podem ser matemática ou português)
    codes_json = list(expected.keys())
    skills_with_code = session.query(Skill).filter(Skill.code.in_(codes_json)).all()

    math_skills = [s for s in skills_with_code if str(s.subject_id) == MATEMATICA_ID]
    pt_skills = [s for s in skills_with_code if str(s.subject_id) == PORTUGUES_ID]
    other_skills = [s for s in skills_with_code if str(s.subject_id) not in (MATEMATICA_ID, PORTUGUES_ID)]

    print(f"\nNo banco (code presente no JSON):")
    print(f"  - {len(math_skills)} habilidades com subject_id = Matemática ({MATEMATICA_ID})")
    print(f"  - {len(pt_skills)} habilidades com subject_id = Português ({PORTUGUES_ID})")
    if other_skills:
        print(f"  - {len(other_skills)} habilidades de outra disciplina")

    # Verificar: matemática com descrição diferente do JSON = errada (provavelmente descrição de português)
    erradas = []
    corretas = []
    sem_no_json = []  # matemática com code que não está no JSON (ex.: EF15_D1)

    for s in math_skills:
        code = s.code
        desc_banco = (s.description or "").strip()
        desc_esperada = expected.get(code)
        if desc_esperada is None:
            sem_no_json.append((code, desc_banco))
            continue
        if desc_banco != desc_esperada:
            erradas.append({
                "id": str(s.id),
                "code": code,
                "desc_banco": desc_banco[:80] + "..." if len(desc_banco) > 80 else desc_banco,
                "desc_esperada": desc_esperada[:80] + "..." if len(desc_esperada) > 80 else desc_esperada,
            })
        else:
            corretas.append(code)

    print("\n" + "=" * 70)
    print("RESULTADO DA VERIFICAÇÃO (habilidades de MATEMÁTICA)")
    print("=" * 70)
    print(f"  Corretas (descrição igual ao JSON): {len(corretas)}")
    print(f"  Erradas (descrição diferente do JSON): {len(erradas)}")
    print(f"  Matemática com code não presente no JSON (anos finais): {len(sem_no_json)}")

    if erradas:
        print("\n--- HABILIDADES DE MATEMÁTICA COM DESCRIÇÃO ERRADA (amostra até 20) ---")
        for i, e in enumerate(erradas[:20]):
            print(f"\n  [{i+1}] code={e['code']} id={e['id']}")
            print(f"      No banco:    {e['desc_banco']}")
            print(f"      Esperado:   {e['desc_esperada']}")
        if len(erradas) > 20:
            print(f"\n  ... e mais {len(erradas) - 20} habilidades erradas.")
        print("\nConclusão: o erro PROCEDE. Há habilidades de matemática com descrição incorreta.")
    else:
        print("\nNenhuma habilidade de matemática (com code no JSON) está com descrição diferente do JSON.")
        if math_skills:
            print("Conclusão: dentro do escopo do JSON de anos finais, as descrições estão corretas.")
        else:
            print("(Não há habilidades de matemática no banco com codes do JSON de anos finais.)")

    if sem_no_json:
        print(f"\n(Matemática com code fora do JSON anos finais: {len(sem_no_json)} — ex.: 1º-5º ou outro arquivo)")

    session.close()
    print("\nFim da verificação.")


if __name__ == "__main__":
    main()
