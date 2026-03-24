"""
Script único que:
1. Conecta ao banco com UTF-8 forçado (evita ??? por encoding).
2. Remove duplicatas: uma linha por (code, subject_id); atualiza question.skill e apaga o resto.
3. Sincroniza descrições a partir dos JSON (Matemática + Português), corrigindo "???".

Fontes: organizacao_matematica_novo.json (+ anos_finais), habilidades_portugues_data.json,
        habilidades_portugues_anos_finais_data.json, habilidades_portugues_9ano_extras.json.

Uso:
    python scripts/fix_skills_full.py
"""

import json
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from uuid import UUID

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MATEMATICA_ID = "44f3421e-ca84-4fe5-a449-a3d9bfa3db3d"
GRADE_5_ANO = "f5688bb2-9624-487f-ab1f-40b191c96b76"
GRADE_9_ANO = "3c68a0b5-9613-469e-8376-6fb678c60363"


def get_engine_utf8():
    """Engine com UTF-8 forçado para PostgreSQL (evita ??? nas descrições)."""
    from app.config import Config
    from sqlalchemy import create_engine

    url = Config.SQLALCHEMY_DATABASE_URI
    if not url:
        logger.error("❌ DATABASE_URL não configurada")
        sys.exit(1)
    # Forçar encoding UTF-8 na conexão (dialect keyword para psycopg2)
    kwargs = {}
    if "postgresql" in (url or ""):
        kwargs["client_encoding"] = "utf8"
    engine = create_engine(url, **kwargs)
    return engine


# ---------- Matemática: mesmo que upload_math_skills_from_organizacao ----------
def load_organizacao_novo():
    path = os.path.join(SCRIPT_DIR, "organizacao_matematica_novo.json")
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_organizacao_anos_finais(data_novo=None):
    if data_novo:
        af = data_novo.get("organizacao_habilidades_matematica_anos_finais")
        if af is not None:
            return af
    path = os.path.join(SCRIPT_DIR, "organizacao_matematica_anos_finais.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def build_entries_1_5(organizacao):
    entries = []
    for group in organizacao.get("habilidades_compartilhadas", []):
        for h in group.get("habilidades", []):
            code = (h.get("codigo") or "").strip()
            desc = (h.get("descricao") or "").strip()
            if not code or not desc:
                continue
            if re.match(r"^D(\d+)$", code):
                n = int(re.match(r"^D(\d+)$", code).group(1))
                if 1 <= n <= 28:
                    code = f"EF15_D{n}"
            entries.append({"code": code, "description": desc, "subject_id": MATEMATICA_ID, "grade_id": None})
    for block in organizacao.get("habilidades_unicas_por_serie", []):
        grade_id = GRADE_5_ANO if "5º" in (block.get("serie") or "") else None
        for h in block.get("habilidades", []):
            code = (h.get("codigo") or "").strip()
            desc = (h.get("descricao") or "").strip()
            if not code or not desc:
                continue
            entries.append({"code": code, "description": desc, "subject_id": MATEMATICA_ID, "grade_id": grade_id})
    return entries


def build_entries_6_9(org):
    if not org:
        return []
    entries = []
    for group in org.get("habilidades_compartilhadas", []):
        for h in group.get("habilidades", []):
            code = (h.get("codigo") or "").strip()
            desc = (h.get("descricao") or "").strip()
            if code and desc:
                entries.append({"code": code, "description": desc, "subject_id": MATEMATICA_ID, "grade_id": None})
    for block in org.get("habilidades_unicas_por_serie", []):
        grade_id = GRADE_9_ANO if "9º" in (block.get("serie") or "") else None
        for h in block.get("habilidades", []):
            code = (h.get("codigo") or "").strip()
            desc = (h.get("descricao") or "").strip()
            if code and desc:
                entries.append({"code": code, "description": desc, "subject_id": MATEMATICA_ID, "grade_id": grade_id})
    return entries


def all_math_habilidades():
    data = load_organizacao_novo()
    org_15 = data.get("organizacao_habilidades_matematica") or data
    org_69 = load_organizacao_anos_finais(data)
    return build_entries_1_5(org_15) + build_entries_6_9(org_69)


def all_portuguese_habilidades():
    out = []
    for name in ["habilidades_portugues_data.json", "habilidades_portugues_anos_finais_data.json", "habilidades_portugues_9ano_extras.json"]:
        path = os.path.join(SCRIPT_DIR, name)
        if not os.path.exists(path):
            continue
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for h in data.get("habilidades", []):
            if h.get("code") and h.get("description"):
                out.append({
                    "code": h["code"],
                    "description": h["description"],
                    "subject_id": h.get("subject_id"),
                    "grade_id": h.get("grade_id"),
                })
    return out

    from sqlalchemy import text

def run():
    from sqlalchemy.orm import sessionmaker
    from app.models.skill import Skill
    from app.models.question import Question

    engine = get_engine_utf8()
    Session = sessionmaker(bind=engine)
    session = Session()

    # ---- 1) Remover duplicatas (manter uma por code+subject_id) ----
    logger.info("1) Buscando duplicatas (code + subject_id)...")
    all_skills = session.query(Skill.id, Skill.code, Skill.subject_id).order_by(Skill.id).all()
    by_key = defaultdict(list)
    for row in all_skills:
        sid, code, subj = row[0], str(row[1] or "").strip(), str(row[2] or "").strip()
        if code and subj:
            by_key[(code, subj)].append(sid)

    dup_groups = {k: v for k, v in by_key.items() if len(v) > 1}
    if not dup_groups:
        logger.info("   Nenhuma duplicata encontrada.")
    else:
        total_remove = sum(len(v) - 1 for v in dup_groups.values())
        logger.info(f"   Encontrados {len(dup_groups)} grupos duplicados; removendo {total_remove} linhas.")
        id_to_keep = {}
        norm_to_keep = {}
        ids_del = []
        for (code, subject_id), id_list in dup_groups.items():
            keep_id = id_list[0]
            for sid in id_list[1:]:
                ids_del.append(sid)
                id_to_keep[str(sid)] = keep_id
        for (code, subject_id), skills in dup_groups.items():
            keep = skills[0]
            for s in skills[1:]:
                id_to_keep[str(s.id)] = keep.id
                norm_to_keep[str(s.id).strip("{}").lower()] = keep.id

                norm_to_keep[str(sid).strip("{}").lower()] = keep_id

        def norm(s):
            return (s or "").strip().strip("{}").lower()

        logger.info("   Atualizando referências em question.skill...")
        questions = session.query(Question.id, Question.skill).filter(Question.skill.isnot(None)).all()
        to_update = []
        for qid, skill_val in questions:
            if not skill_val:
                continue
            parts = [p.strip().strip("{}") for p in (skill_val or "").split(",") if p.strip()]
            if not parts:
                continue
            new_parts = []
            for p in parts:
                kid = norm_to_keep.get(norm(p)) or id_to_keep.get(p)
                new_parts.append(str(kid) if kid is not None else p)
            seen = set()
            unique = []
            for x in new_parts:
                k = norm(x)
                if k not in seen:
                    seen.add(k)
                    unique.append(x)
            if unique != parts:
                new_skill = ",".join(unique) if len(unique) > 1 else unique[0]
                to_update.append({"id": qid, "skill": new_skill})
        if to_update:
            session.bulk_update_mappings(
                Question,
                [{"id": u["id"], "skill": u["skill"]} for u in to_update],
            )
            logger.info(f"   Atualizadas {len(to_update)} questões.")

        logger.info("   Removendo duplicatas (DELETE em lote)...")
        chunk = 300
        for i in range(0, len(ids_del), chunk):
            batch = ids_del[i : i + chunk]
            session.query(Skill).filter(Skill.id.in_(batch)).delete(synchronize_session=False)
        session.commit()
        logger.info(f"   Removidas {len(ids_del)} habilidades duplicadas.")

    # ---- 2) Sincronizar descrições (e grade_id) a partir dos JSON em UTF-8 ----
    logger.info("\n2) Sincronizando descrições a partir dos JSON (UTF-8)...")
    math_hab = all_math_habilidades()
    pt_hab = all_portuguese_habilidades()
    todas = math_hab + pt_hab
    logger.info(f"   Total a processar: {len(math_hab)} matemática + {len(pt_hab)} português = {len(todas)}")

    skills_by_key = {}
    for s in session.query(Skill).all():
        k = (str(s.code or "").strip(), str(s.subject_id or "").strip())
        if k[0] and k[1]:
            skills_by_key[k] = s

    updated = created = errors = 0
    for i, hab in enumerate(todas):
        if (i + 1) % 500 == 0:
            logger.info(f"   Processados {i + 1}/{len(todas)}...")
        code = hab.get("code")
        description = hab.get("description")
        subject_id = hab.get("subject_id")
        grade_id_str = hab.get("grade_id")
        if not code or not description:
            continue
        try:
            k = (str(code).strip(), str(subject_id or "").strip())
            skill = skills_by_key.get(k)
            if skill:
                skill.description = description
                if "grade_id" in hab and grade_id_str:
                    from app.models.grades import Grade
                    gu = UUID(grade_id_str)
                    grade = session.query(Grade).get(gu)
                    if grade and grade not in skill.grades:
                        skill.grades.append(grade)
                updated += 1
            else:
                from app.models.grades import Grade
                new_skill = Skill(code=code, description=description, subject_id=subject_id)
                session.add(new_skill)
                session.flush()
                if grade_id_str:
                    gu = UUID(grade_id_str)
                    grade = session.query(Grade).get(gu)
                    if grade:
                        new_skill.grades.append(grade)
                if k[0] and k[1]:
                    skills_by_key[k] = new_skill
                created += 1
        except Exception as e:
            errors += 1
            logger.warning(f"   Erro em {code}: {e}")

    session.commit()
    logger.info(f"   Atualizadas: {updated} | Criadas: {created} | Erros: {errors}")
    logger.info("\nConcluído. Verifique no banco se as descrições estão sem '???' e sem duplicatas.")


if __name__ == "__main__":
    run()
