"""
Script para subir habilidades de Matemática (1º-5º e 6º-9º) a partir dos JSONs de
organização, sem apagar nem duplicar: se a habilidade já existir no banco (code + subject_id),
atualiza apenas a descrição (e grade_id se informado); caso contrário, cria a habilidade.

Fontes:
- organizacao_matematica_novo.json (organizacao_habilidades_matematica = 1º-5º)
- organizacao_matematica_anos_finais.json OU bloco organizacao_habilidades_matematica_anos_finais
  dentro de organizacao_matematica_novo.json (6º-9º)

Uso (não executa sozinho; rodar manualmente):
    python scripts/upload_math_skills_from_organizacao.py
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from uuid import UUID

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MATEMATICA_ID = "44f3421e-ca84-4fe5-a449-a3d9bfa3db3d"
GRADE_5_ANO = "f5688bb2-9624-487f-ab1f-40b191c96b76"
GRADE_9_ANO = "3c68a0b5-9613-469e-8376-6fb678c60363"


def load_organizacao_novo():
    """Carrega organizacao_matematica_novo.json (contém 1º-5º e opcionalmente 6º-9º)."""
    path = os.path.join(SCRIPT_DIR, "organizacao_matematica_novo.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_organizacao_anos_finais(data_novo=None):
    """Carrega organização 6º-9º: do data_novo (se existir) ou de organizacao_matematica_anos_finais.json."""
    if data_novo is not None:
        af = data_novo.get("organizacao_habilidades_matematica_anos_finais")
        if af is not None:
            return af
    path = os.path.join(SCRIPT_DIR, "organizacao_matematica_anos_finais.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def build_entries_1_5(organizacao):
    """Gera lista de entradas 1º-5º: compartilhadas com grade_id null; 5º único com grade 5º.
    D1-D28 do primeiro grupo viram EF15_D1 a EF15_D28.
    """
    entries = []
    shared = organizacao.get("habilidades_compartilhadas", [])
    unicas = organizacao.get("habilidades_unicas_por_serie", [])

    for group in shared:
        grade_id = None
        for h in group.get("habilidades", []):
            code = (h.get("codigo") or "").strip()
            desc = (h.get("descricao") or "").strip()
            if not code or not desc:
                continue
            if re.match(r"^D(\d+)$", code):
                num = int(re.match(r"^D(\d+)$", code).group(1))
                if 1 <= num <= 28:
                    code = f"EF15_D{num}"
            entries.append({
                "code": code,
                "description": desc,
                "subject_id": MATEMATICA_ID,
                "grade_id": grade_id,
            })

    for block in unicas:
        serie = (block.get("serie") or "")
        grade_id = GRADE_5_ANO if "5º" in serie else None
        for h in block.get("habilidades", []):
            code = (h.get("codigo") or "").strip()
            desc = (h.get("descricao") or "").strip()
            if not code or not desc:
                continue
            entries.append({
                "code": code,
                "description": desc,
                "subject_id": MATEMATICA_ID,
                "grade_id": grade_id,
            })
    return entries


def build_entries_6_9(organizacao_anos_finais):
    """Gera lista de entradas 6º-9º: compartilhadas com grade_id null; 9º único com grade 9º.
    D1-D37 e EF06/07/08/09 permanecem com o mesmo código.
    """
    if not organizacao_anos_finais:
        return []
    entries = []
    shared = organizacao_anos_finais.get("habilidades_compartilhadas", [])
    unicas = organizacao_anos_finais.get("habilidades_unicas_por_serie", [])

    for group in shared:
        grade_id = None
        for h in group.get("habilidades", []):
            code = (h.get("codigo") or "").strip()
            desc = (h.get("descricao") or "").strip()
            if not code or not desc:
                continue
            entries.append({
                "code": code,
                "description": desc,
                "subject_id": MATEMATICA_ID,
                "grade_id": grade_id,
            })

    for block in unicas:
        serie = (block.get("serie") or "")
        grade_id = GRADE_9_ANO if "9º" in serie else None
        for h in block.get("habilidades", []):
            code = (h.get("codigo") or "").strip()
            desc = (h.get("descricao") or "").strip()
            if not code or not desc:
                continue
            entries.append({
                "code": code,
                "description": desc,
                "subject_id": MATEMATICA_ID,
                "grade_id": grade_id,
            })
    return entries


def build_all_habilidades():
    """Monta a lista única de habilidades a subir: 1º-5º + 6º-9º (sem duplicar por code)."""
    data_novo = load_organizacao_novo()
    org_1_5 = data_novo.get("organizacao_habilidades_matematica") or data_novo
    org_6_9 = load_organizacao_anos_finais(data_novo)

    list_1_5 = build_entries_1_5(org_1_5)
    list_6_9 = build_entries_6_9(org_6_9)

    # Evitar duplicata por (code, subject_id): 1º-5º usa EF15_Dx; 6º-9º usa D1-D37. Não há choque.
    return list_1_5 + list_6_9


def get_db_session():
    """Sessão do banco (reutiliza lógica do update script)."""
    from app.config import Config
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    database_url = Config.SQLALCHEMY_DATABASE_URI
    if not database_url:
        logger.error("❌ DATABASE_URL não encontrada nas variáveis de ambiente")
        sys.exit(1)
    kwargs = {}
    if "postgresql" in (database_url or ""):
        kwargs["client_encoding"] = "utf8"
    engine = create_engine(database_url, **kwargs)
    Session = sessionmaker(bind=engine)
    return Session()


def upload_habilidades():
    """
    Sobe todas as habilidades de matemática (1º-5º e 6º-9º).
    Se já existir (code + subject_id): só atualiza description (e grade_id se vier no item).
    Se não existir: cria a habilidade. Não apaga nem duplica.
    """
    logger.info("\n" + "="*70)
    logger.info("🚀 UPLOAD HABILIDADES MATEMÁTICA (1º-5º + 6º-9º) A PARTIR DA ORGANIZAÇÃO")
    logger.info("="*70)

    logger.info("\n📂 Carregando organizacao_matematica_novo.json e anos finais...")
    habilidades = build_all_habilidades()
    logger.info(f"✅ {len(habilidades)} habilidades a processar (1º-5º + 6º-9º)")

    from app.models.skill import Skill
    from app.models.grades import Grade

    stats = {"updated": 0, "created": 0, "errors": 0, "skipped": 0}
    session = get_db_session()

    try:
        logger.info("\n" + "="*70)
        logger.info("📦 PROCESSANDO HABILIDADES")
        logger.info("="*70 + "\n")

        for idx, hab in enumerate(habilidades, 1):
            code = hab.get("code")
            description = hab.get("description")
            subject_id = hab.get("subject_id")
            grade_id_str = hab.get("grade_id")
            grade_id_uuid = UUID(grade_id_str) if grade_id_str else None

            if not code or not description:
                logger.warning(f"   ⚠️  [{idx}/{len(habilidades)}] Sem code ou description, pulando...")
                stats["skipped"] += 1
                continue

            try:
                skill = session.query(Skill).filter_by(code=code, subject_id=subject_id).first()

                if skill:
                    skill.description = description
                    if grade_id_uuid:
                        grade = session.query(Grade).get(grade_id_uuid)
                        if grade and grade not in skill.grades:
                            skill.grades.append(grade)
                    stats["updated"] += 1
                    logger.info(f"   ✏️  [{idx}/{len(habilidades)}] Atualizada: {code}")
                else:
                    skill = Skill(code=code, description=description, subject_id=subject_id)
                    session.add(skill)
                    session.flush()
                    if grade_id_uuid:
                        grade = session.query(Grade).get(grade_id_uuid)
                        if grade:
                            skill.grades.append(grade)
                    stats["created"] += 1
                    grade_info = f"grade={grade_id_str[:8]}..." if grade_id_str else "grade=NULL"
                    logger.info(f"   ➕ [{idx}/{len(habilidades)}] Criada: {code} ({grade_info})")

            except Exception as e:
                logger.error(f"   ❌ [{idx}/{len(habilidades)}] Erro em {code}: {e}")
                stats["errors"] += 1

        logger.info("\n💾 Salvando alterações no banco...")
        session.commit()
        logger.info("✅ Commit realizado.")

        logger.info("\n" + "="*70)
        logger.info("📊 RELATÓRIO")
        logger.info("="*70)
        logger.info(f"  📝 Total processado: {len(habilidades)}")
        logger.info(f"  ✏️  Atualizadas (só descrição/grade): {stats['updated']}")
        logger.info(f"  ➕ Criadas: {stats['created']}")
        logger.info(f"  ⏭️  Puladas: {stats['skipped']}")
        logger.info(f"  ❌ Erros: {stats['errors']}")
        logger.info("="*70 + "\n")

    except Exception as e:
        logger.error(f"\n❌ ERRO: {e}")
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    upload_habilidades()
