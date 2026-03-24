"""
Script para sincronizar skill_grade a partir dos JSONs de habilidades.

Garante que cada skill tenha em skill_grade exatamente os grade_ids definidos nos JSONs.
Corrige vínculos errados e adiciona os faltantes.

Fontes:
- scripts/organizacao_matematica_novo.json (1º-5º e 6º-9º)
- scripts/organizacao_matematica_anos_finais.json (6º-9º)
- scripts/habilidades_portugues_data.json (1º-5º)
- scripts/habilidades_portugues_anos_finais_data.json (6º-9º)
- scripts/habilidades_educacao_infantil.json (Grupos 3-5 e Suportes 1-3)

Uso:
    python scripts/sync_skill_grade_from_jsons.py
"""

import json
import os
import re
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_ROOT, "app", ".env"))
except ImportError:
    pass

import logging
from uuid import UUID
from typing import Dict, List, Tuple, Optional

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# IDs das disciplinas
MATEMATICA_ID = "44f3421e-ca84-4fe5-a449-a3d9bfa3db3d"
PORTUGUES_ID = "4d29b4f1-7bd7-42c0-84d5-111dc7025b90"
EI_SUBJECT_ID = None

# Mapeamento nome → grade_id (fornecido pelo usuário)
GRADE_IDS = {
    "Grupo 3": "35e6701a-87b9-4c46-82e5-44aa3458dd60",
    "Grupo 4": "15c413c1-c044-43df-a118-c8cd22281ade",
    "Grupo 5": "b3f73bca-27a7-4c86-8856-949056773776",
    "Suporte 1": "c40d2301-6afc-4c52-94df-6a9856970f6e",
    "Suporte 2": "0498b94e-a0de-483a-ad8e-a82f72abf128",
    "Suporte 3": "2e45c0f2-a979-475a-8f29-9576a837400b",
    "1º Ano": "391ed6e8-fc45-46f8-8e4c-065005d2329f",
    "2º Ano": "74821122-e632-4301-b6f5-42b92b802a55",
    "3º Ano": "ea1ed64b-c9f5-4156-93b2-497ecf9e0d84",
    "4º Ano": "b8cdea4d-22fe-4647-a9f3-c575eb82c514",
    "5º Ano": "f5688bb2-9624-487f-ab1f-40b191c96b76",
    "6º Ano": "75bea034-3427-4e98-896d-23493d36a84e",
    "7º Ano": "4128c187-5e33-4ff9-a96d-e7eb9ddbe04e",
    "8º Ano": "b6760b9b-2758-4d14-a650-c3a30c0aeb3b",
    "9º Ano": "3c68a0b5-9613-469e-8376-6fb678c60363",
}


def get_db_session():
    """Sessão do banco (igual aos outros scripts)."""
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


# ============================================================================
# PARSING FUNCTIONS
# ============================================================================

def parse_series_aplicaveis(text: str) -> List[str]:
    """
    Extrai nomes de séries de texto como "1º, 2º, 3º, 4º e 5º Ano".
    Retorna lista como ["1º Ano", "2º Ano", "3º Ano", "4º Ano", "5º Ano"].
    """
    if not text or not text.strip():
        return []
    anos = re.findall(r"(\d+º)", text)
    return [f"{ano} Ano" for ano in anos]


def parse_comment_portuguese(comment: str) -> List[str]:
    """
    Parseia campo 'comment' de português: "Compartilhada: 1º, 2º e 3º Ano" ou "Única: 5º Ano".
    Retorna lista de nomes de série (ex.: ["1º Ano", "2º Ano", "3º Ano"]).
    """
    if not comment or not comment.strip():
        return []
    part = comment.split(":", 1)[-1] if ":" in comment else comment
    anos = re.findall(r"(\d+º)", part)
    return [f"{ano} Ano" for ano in anos]


def normalize_math_code(code: str, is_anos_iniciais: bool) -> str:
    """
    Normaliza código de matemática:
    - Anos iniciais (1º-5º): D1-D28 → EF15_D1 a EF15_D28
    - Anos finais (6º-9º): mantém D1-D37 e códigos EF06/07/08/09
    """
    if not code:
        return code
    code = code.strip()
    if is_anos_iniciais and re.match(r"^D(\d+)$", code):
        num = int(re.match(r"^D(\d+)$", code).group(1))
        if 1 <= num <= 28:
            return f"EF15_D{num}"
    return code


def normalize_ei_code(codigo: str) -> str:
    """Normaliza código EI: E101 -> EI01, E102 -> EI02, E103 -> EI03."""
    if not codigo:
        return codigo
    s = codigo.strip()
    for wrong, right in [("E101", "EI01"), ("E102", "EI02"), ("E103", "EI03")]:
        if s.upper().startswith(wrong):
            s = right + s[len(wrong):]
            break
    return s


def get_ei_grade_ids_for_code(code: str) -> List[str]:
    """Retorna lista de grade_id para código EI (EI01 -> Grupo 3 + Suporte 1, etc.)."""
    code = normalize_ei_code(code).upper()
    if code.startswith("EI01"):
        return [GRADE_IDS["Grupo 3"], GRADE_IDS["Suporte 1"]]
    elif code.startswith("EI02"):
        return [GRADE_IDS["Grupo 4"], GRADE_IDS["Suporte 2"]]
    elif code.startswith("EI03"):
        return [GRADE_IDS["Grupo 5"], GRADE_IDS["Suporte 3"]]
    return []


# ============================================================================
# LOAD JSONS
# ============================================================================

def load_json(filename: str):
    """Carrega JSON do diretório scripts."""
    path = os.path.join(SCRIPT_DIR, filename)
    if not os.path.exists(path):
        logger.warning("Arquivo não encontrado: %s", filename)
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ============================================================================
# BUILD MAPPINGS FROM EACH SOURCE
# ============================================================================

def build_math_mapping() -> Dict[Tuple[Optional[str], str], List[str]]:
    """
    Constrói mapeamento de matemática: (MATEMATICA_ID, code) -> [grade_id, ...].
    Lê organizacao_matematica_novo.json (1º-5º e opcionalmente 6º-9º) e
    organizacao_matematica_anos_finais.json.
    """
    mapping = {}
    
    # 1º-5º
    data_novo = load_json("organizacao_matematica_novo.json")
    if data_novo:
        org_1_5 = data_novo.get("organizacao_habilidades_matematica", data_novo)
        
        # Compartilhadas 1º-5º
        for group in org_1_5.get("habilidades_compartilhadas", []):
            series_text = group.get("series_aplicaveis", "")
            grade_names = parse_series_aplicaveis(series_text)
            grade_ids = [GRADE_IDS[name] for name in grade_names if name in GRADE_IDS]
            
            for h in group.get("habilidades", []):
                code = (h.get("codigo") or "").strip()
                if not code:
                    continue
                code = normalize_math_code(code, is_anos_iniciais=True)
                key = (MATEMATICA_ID, code)
                if key not in mapping:
                    mapping[key] = []
                for gid in grade_ids:
                    if gid not in mapping[key]:
                        mapping[key].append(gid)
        
        # Únicas 5º ano
        for block in org_1_5.get("habilidades_unicas_por_serie", []):
            serie = block.get("serie", "")
            grade_names = parse_series_aplicaveis(serie)
            grade_ids = [GRADE_IDS[name] for name in grade_names if name in GRADE_IDS]
            
            for h in block.get("habilidades", []):
                code = (h.get("codigo") or "").strip()
                if not code:
                    continue
                code = normalize_math_code(code, is_anos_iniciais=True)
                key = (MATEMATICA_ID, code)
                if key not in mapping:
                    mapping[key] = []
                for gid in grade_ids:
                    if gid not in mapping[key]:
                        mapping[key].append(gid)
    
    # 6º-9º (pode estar em organizacao_matematica_novo ou separado)
    org_6_9 = None
    if data_novo:
        org_6_9 = data_novo.get("organizacao_habilidades_matematica_anos_finais")
    if not org_6_9:
        data_anos_finais = load_json("organizacao_matematica_anos_finais.json")
        if data_anos_finais:
            org_6_9 = data_anos_finais
    
    if org_6_9:
        # Compartilhadas 6º-9º
        for group in org_6_9.get("habilidades_compartilhadas", []):
            series_text = group.get("series_aplicaveis", "")
            grade_names = parse_series_aplicaveis(series_text)
            grade_ids = [GRADE_IDS[name] for name in grade_names if name in GRADE_IDS]
            
            for h in group.get("habilidades", []):
                code = (h.get("codigo") or "").strip()
                if not code:
                    continue
                code = normalize_math_code(code, is_anos_iniciais=False)
                key = (MATEMATICA_ID, code)
                if key not in mapping:
                    mapping[key] = []
                for gid in grade_ids:
                    if gid not in mapping[key]:
                        mapping[key].append(gid)
        
        # Únicas 9º ano
        for block in org_6_9.get("habilidades_unicas_por_serie", []):
            serie = block.get("serie", "")
            grade_names = parse_series_aplicaveis(serie)
            grade_ids = [GRADE_IDS[name] for name in grade_names if name in GRADE_IDS]
            
            for h in block.get("habilidades", []):
                code = (h.get("codigo") or "").strip()
                if not code:
                    continue
                code = normalize_math_code(code, is_anos_iniciais=False)
                key = (MATEMATICA_ID, code)
                if key not in mapping:
                    mapping[key] = []
                for gid in grade_ids:
                    if gid not in mapping[key]:
                        mapping[key].append(gid)
    
    return mapping


def build_portuguese_mapping() -> Dict[Tuple[Optional[str], str], List[str]]:
    """
    Constrói mapeamento de português: (PORTUGUES_ID, code) -> [grade_id, ...].
    Lê habilidades_portugues_data.json (1º-5º) e habilidades_portugues_anos_finais_data.json (6º-9º).
    """
    mapping = {}
    
    # Anos iniciais (1º-5º)
    data_inicial = load_json("habilidades_portugues_data.json")
    if data_inicial:
        for h in data_inicial.get("habilidades", []):
            code = (h.get("code") or "").strip()
            comment = h.get("comment", "")
            if not code:
                continue
            
            grade_names = parse_comment_portuguese(comment)
            grade_ids = [GRADE_IDS[name] for name in grade_names if name in GRADE_IDS]
            
            key = (PORTUGUES_ID, code)
            if key not in mapping:
                mapping[key] = []
            for gid in grade_ids:
                if gid not in mapping[key]:
                    mapping[key].append(gid)
    
    # Anos finais (6º-9º)
    data_final = load_json("habilidades_portugues_anos_finais_data.json")
    if data_final:
        for h in data_final.get("habilidades", []):
            code = (h.get("code") or "").strip()
            comment = h.get("comment", "")
            if not code:
                continue
            
            grade_names = parse_comment_portuguese(comment)
            grade_ids = [GRADE_IDS[name] for name in grade_names if name in GRADE_IDS]
            
            key = (PORTUGUES_ID, code)
            if key not in mapping:
                mapping[key] = []
            for gid in grade_ids:
                if gid not in mapping[key]:
                    mapping[key].append(gid)
    
    return mapping


def build_ei_mapping() -> Dict[Tuple[Optional[str], str], List[str]]:
    """
    Constrói mapeamento de Educação Infantil: (None, code) -> [grade_id, ...].
    EI01 -> Grupo 3 + Suporte 1; EI02 -> Grupo 4 + Suporte 2; EI03 -> Grupo 5 + Suporte 3.
    """
    mapping = {}
    
    data_ei = load_json("habilidades_educacao_infantil.json")
    if data_ei:
        for h in data_ei.get("educacao_infantil", {}).get("habilidades", []):
            codigo_raw = (h.get("codigo") or "").strip()
            if not codigo_raw:
                continue
            
            code = normalize_ei_code(codigo_raw)
            grade_ids = get_ei_grade_ids_for_code(code)
            
            if grade_ids:
                key = (EI_SUBJECT_ID, code)
                if key not in mapping:
                    mapping[key] = []
                for gid in grade_ids:
                    if gid not in mapping[key]:
                        mapping[key].append(gid)
    
    return mapping


def build_full_mapping() -> Dict[Tuple[Optional[str], str], List[str]]:
    """Monta mapeamento completo de todas as fontes."""
    logger.info("\nCarregando mapeamentos dos JSONs...")
    
    math_map = build_math_mapping()
    logger.info("  Matemática: %s habilidades", len(math_map))
    
    port_map = build_portuguese_mapping()
    logger.info("  Português: %s habilidades", len(port_map))
    
    ei_map = build_ei_mapping()
    logger.info("  Educação Infantil: %s habilidades", len(ei_map))
    
    # Merge (não deve haver colisão pois subject_id é diferente)
    full_map = {}
    full_map.update(math_map)
    full_map.update(port_map)
    full_map.update(ei_map)
    
    logger.info("Total de habilidades no mapa: %s", len(full_map))
    return full_map


# ============================================================================
# SYNC SKILL_GRADE
# ============================================================================

def sync_skill_grade(session, mapping: Dict[Tuple[Optional[str], str], List[str]]):
    """
    Sincroniza skill_grade: para cada (subject_id, code) no mapping, busca a skill
    e substitui os vínculos em skill_grade pelos grade_ids do mapa.
    """
    from app.models.skill import Skill, skill_grade
    from app.models.grades import Grade
    
    stats = {"synced": 0, "not_found": 0, "errors": 0}
    
    logger.info("\n" + "=" * 70)
    logger.info("SINCRONIZANDO SKILL_GRADE")
    logger.info("=" * 70 + "\n")
    
    for idx, ((subject_id, code), grade_ids) in enumerate(mapping.items(), 1):
        try:
            # Buscar skill (sem carregar grades)
            from sqlalchemy.orm import noload
            skill = (
                session.query(Skill)
                .options(noload(Skill.grades))
                .filter_by(code=code, subject_id=subject_id)
                .first()
            )
            
            if not skill:
                stats["not_found"] += 1
                if stats["not_found"] <= 10:
                    logger.warning("  [%s/%s] Skill não encontrada no banco: %s (subject=%s)", 
                                   idx, len(mapping), code, subject_id)
                continue
            
            skill_id = skill.id
            
            # Deletar vínculos antigos em skill_grade
            session.execute(
                skill_grade.delete().where(skill_grade.c.skill_id == skill_id)
            )
            
            # Inserir novos vínculos
            if grade_ids:
                rows = [{"skill_id": skill_id, "grade_id": UUID(gid)} for gid in grade_ids]
                session.execute(skill_grade.insert(), rows)
            
            stats["synced"] += 1
            if idx % 100 == 0 or idx <= 10:
                logger.info("  [%s/%s] Sincronizada: %s (%s grades)", 
                            idx, len(mapping), code, len(grade_ids))
        
        except Exception as e:
            logger.error("  Erro em %s: %s", code, e)
            stats["errors"] += 1
    
    return stats


# ============================================================================
# MAIN
# ============================================================================

def main():
    logger.info("\n" + "=" * 70)
    logger.info("SINCRONIZAÇÃO SKILL_GRADE A PARTIR DOS JSONS")
    logger.info("=" * 70)
    
    # Construir mapeamento completo
    mapping = build_full_mapping()
    
    if not mapping:
        logger.error("Nenhuma habilidade no mapeamento. Verifique os JSONs.")
        return
    
    # Abrir sessão e sincronizar
    session = get_db_session()
    
    try:
        stats = sync_skill_grade(session, mapping)
        
        logger.info("\nCommit no banco...")
        session.commit()
        logger.info("Commit realizado.")
        
        logger.info("\n" + "=" * 70)
        logger.info("RELATÓRIO")
        logger.info("=" * 70)
        logger.info("  Total no mapa: %s", len(mapping))
        logger.info("  Sincronizadas: %s", stats["synced"])
        logger.info("  Não encontradas no banco: %s", stats["not_found"])
        logger.info("  Erros: %s", stats["errors"])
        logger.info("=" * 70 + "\n")
    
    except Exception as e:
        logger.error("ERRO: %s", e)
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
