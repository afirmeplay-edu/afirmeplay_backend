# -*- coding: utf-8 -*-
"""
Relatório consolidado multi-seleção — contrato matricial escola × série.

Todas as sessões usam o mesmo padrão:
  linhas = escolas | colunas = series_colunas (root) | TX. GERAL por linha | MÉDIAS DA REDE.

═══════════════════════════════════════════════════════════════════════════════
⚠️⚠️⚠️ REGRA OBRIGATÓRIA: NÃO EXISTE MÉDIA PONDERADA NESTE SISTEMA ⚠️⚠️⚠️
═══════════════════════════════════════════════════════════════════════════════

TODA agregação de valores (nota, proficiência, distribuição, taxa de participação)
acima do nível TURMA deve usar MÉDIA HIERÁRQUICA com PESO IGUAL entre unidades
do mesmo nível.

Hierarquia (sempre esta ordem):
1. TURMA → média aritmética dos alunos da turma
2. SÉRIE → média das médias das turmas (peso igual por turma)
3. ESCOLA → média das médias das séries (peso igual por série)
4. MUNICÍPIO → média das médias das escolas (peso igual por escola)

NUNCA:
- Somar contagens e dividir pelo total (média ponderada por número de alunos)
- Ponderar pelo número de turmas, alunos ou escolas
- Usar AVG SQL para consolidar acima do nível turma

SEMPRE:
- Calcular percentuais/médias por unidade
- Tirar média aritmética simples dos percentuais/médias

Referência: hierarchical_mean_grade_and_proficiency (school_equal_weight_means.py)
Documentação: docs/FONTE_DA_VERDADE_CALCULOS_RESULTADOS.md (§7)

═══════════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from sqlalchemy import cast
from sqlalchemy.dialects.postgresql import VARCHAR
from sqlalchemy.orm import joinedload

from app import db
from app.models.answerSheetGabarito import AnswerSheetGabarito
from app.models.answerSheetResult import AnswerSheetResult
from app.models.city import City
from app.models.classTest import ClassTest
from app.models.evaluationResult import EvaluationResult
from app.models.question import Question
from app.models.school import School
from app.models.skill import Skill
from app.models.student import Student
from app.models.studentAnswer import StudentAnswer
from app.models.studentClass import Class
from app.models.subject import Subject
from app.models.test import Test
from app.report_analysis.answer_sheet_report_builder import (
    question_skills_map_for_answer_sheet,
)
from app.routes.answer_sheet_evaluation_listing import (
    answer_sheet_target_classes_visible_for_user,
)
from app.routes.report_routes import _obter_disciplinas_avaliacao, _obter_nome_curso
from app.services.evaluation_calculator import EvaluationCalculator
from app.services.evaluation_result_snapshot import (
    merge_participant_student_ids,
    query_evaluation_results_for_stats,
)
from app.utils.decimal_helpers import round_to_two_decimals
from app.utils.school_equal_weight_means import (
    hierarchical_mean_from_subject_rows,
    hierarchical_mean_grade_and_proficiency,
)

logger = logging.getLogger(__name__)

GERAL_KEY = "GERAL"
FAIXAS = ("abaixo_do_basico", "basico", "adequado", "avancado")
_SUBJECT_NAME_CACHE: Dict[str, str] = {}

# Educação Especial: grade = "Suporte N"; o ano escolar vive em class.name ("- 1º ANO").
_SUPORTE_GRADE_RE = re.compile(r"^suporte\s*([123])$", re.IGNORECASE)
_ANO_IN_CLASS_NAME_RE = re.compile(r"(?P<n>\d+)\s*[ºo°]?\s*ano", re.IGNORECASE)


def _series_identity_for_class(co: Class) -> Tuple[str, str]:
    """
    Identidade da coluna série no consolidado.

    Para turmas de Suporte 1/2/3 com ano no nome (ex.: "- 1º ANO"), separa colunas
    "Suporte 1 1º Ano", "Suporte 1 2º Ano", etc. Demais grades seguem grade.id/name.
    """
    grade = getattr(co, "grade", None)
    grade_id = str(grade.id) if grade and getattr(grade, "id", None) is not None else "_sem_serie"
    grade_name = (getattr(grade, "name", None) if grade else None) or "Sem série"

    m_sup = _SUPORTE_GRADE_RE.match(str(grade_name).strip())
    if not m_sup:
        return grade_id, grade_name

    class_name = (getattr(co, "name", None) or "").strip()
    m_ano = _ANO_IN_CLASS_NAME_RE.search(class_name)
    if not m_ano:
        return grade_id, grade_name

    n = int(m_ano.group("n"))
    serie_nome = f"{grade_name.strip()} {n}º Ano"
    serie_id = f"{grade_id}::{n}"
    return serie_id, serie_nome


def _series_sort_key(serie_nome: str) -> Tuple[Any, ...]:
    """Ordena colunas Suporte N Mº Ano de forma natural; demais por nome."""
    text = (serie_nome or "").strip()
    m = re.match(r"^suporte\s*([123])\s+(\d+)\s*[ºo°]?\s*ano", text, re.IGNORECASE)
    if m:
        return (0, int(m.group(1)), int(m.group(2)), text.upper())
    m2 = re.match(r"^suporte\s*([123])$", text, re.IGNORECASE)
    if m2:
        return (0, int(m2.group(1)), 0, text.upper())
    return (1, 0, 0, text.upper())


def parse_csv_ids(raw: Optional[str], param_name: str = "ids") -> List[str]:
    if not raw or not str(raw).strip():
        raise ValueError(f"Parâmetro {param_name} é obrigatório (IDs separados por vírgula).")
    ids = [x.strip() for x in str(raw).split(",") if x.strip()]
    if not ids:
        raise ValueError(f"Parâmetro {param_name} inválido.")
    return ids


def _escola_eh_especifica(escola: Optional[str]) -> bool:
    return bool(escola and str(escola).strip().lower() not in ("all", ""))


def _classification_bucket(classification: Optional[str]) -> str:
    t = (classification or "").strip().lower()
    if "abaixo" in t:
        return "abaixo_do_basico"
    if "avançado" in t or "avancado" in t:
        return "avancado"
    if "adequado" in t:
        return "adequado"
    if "básico" in t or "basico" in t:
        return "basico"
    return "basico"


def _empty_distribution() -> Dict[str, int]:
    return {k: 0 for k in FAIXAS}


def _mean_numeric(values: List[float]) -> float:
    if not values:
        return 0.0
    return round_to_two_decimals(sum(values) / len(values))


def _dedupe_digital_by_test_student(rows: List[EvaluationResult]) -> List[EvaluationResult]:
    best: Dict[Tuple[str, str], EvaluationResult] = {}
    for r in rows:
        key = (str(r.test_id), str(r.student_id))
        prev = best.get(key)
        if prev is None:
            best[key] = r
            continue
        r_ca = getattr(r, "calculated_at", None)
        p_ca = getattr(prev, "calculated_at", None)
        if r_ca and (p_ca is None or r_ca > p_ca):
            best[key] = r
    return list(best.values())


def _dedupe_answer_sheet_by_gabarito_student(rows: List[AnswerSheetResult]) -> List[AnswerSheetResult]:
    best: Dict[Tuple[str, str], AnswerSheetResult] = {}
    for r in rows:
        key = (str(r.gabarito_id), str(r.student_id))
        prev = best.get(key)
        if prev is None:
            best[key] = r
            continue
        ta, tb = r.corrected_at, prev.corrected_at
        if ta is not None and tb is None:
            best[key] = r
        elif ta is None and tb is not None:
            continue
        elif ta is not None and tb is not None and ta > tb:
            best[key] = r
        elif str(r.id) >= str(prev.id):
            best[key] = r
    return list(best.values())


def _professor_restrict_class_ids(user: dict) -> Optional[Set[Any]]:
    role = (user.get("role") or "").lower()
    if role != "professor":
        return None
    try:
        from app.permissions.utils import get_teacher_classes

        return set(get_teacher_classes(user.get("id")) or [])
    except Exception:
        return set()


def _build_escopo_calculo(municipio_id: str, escola_id: Optional[str]) -> Dict[str, Any]:
    if escola_id:
        return {"tipo": "escola", "municipio_id": municipio_id, "escola_id": escola_id}
    return {"tipo": "municipio", "municipio_id": municipio_id}


def _subject_id_to_name_map(test: Test) -> Dict[str, str]:
    out: Dict[str, str] = {}
    if test.subject_rel and test.subject:
        out[str(test.subject)] = test.subject_rel.name
    raw = test.subjects_info

    # Formato legado/esperado: {"Português": {"id": "..."}}
    if raw and isinstance(raw, dict):
        for name, info in raw.items():
            out[str(name)] = str(name)
            if isinstance(info, dict):
                sid = info.get("id") or info.get("subject_id")
                if sid:
                    out[str(sid)] = str(name)

    # Formato observado em produção: ["<subject_id>", "<subject_id>"]
    elif raw and isinstance(raw, list):
        subject_ids = [str(x).strip() for x in raw if x is not None and str(x).strip()]
        miss_ids = [sid for sid in subject_ids if sid not in _SUBJECT_NAME_CACHE]
        if miss_ids:
            for subj in Subject.query.filter(Subject.id.in_(miss_ids)).all():
                _SUBJECT_NAME_CACHE[str(subj.id)] = subj.name
        for sid in subject_ids:
            if sid in _SUBJECT_NAME_CACHE:
                out[sid] = _SUBJECT_NAME_CACHE[sid]
    return out


def _disciplinas_from_test(test: Test) -> Set[str]:
    return set(_obter_disciplinas_avaliacao(test))


def _disciplinas_from_gabarito(gab: AnswerSheetGabarito) -> Set[str]:
    names: Set[str] = set()
    cfg = gab.blocks_config or {}
    for block in (cfg.get("topology") or {}).get("blocks") or []:
        subj = (block.get("subject_name") or "").strip()
        if subj:
            names.add(subj)
    if not names:
        names.add("Disciplina Geral")
    return names


# ---------------------------------------------------------------------------
# Índice de escopo escola × série
# ---------------------------------------------------------------------------


@dataclass
class ScopeIndex:
    series_colunas: List[Dict[str, str]]
    escolas: List[Dict[str, str]]
    classes_by_cell: Dict[Tuple[str, str], Set[str]]
    class_to_cell: Dict[str, Tuple[str, str]]
    students_by_class: Dict[str, List[Student]]
    series_items: List[Tuple[str, str, str, str, str]] = field(default_factory=list)


@dataclass
class ConsolidatedScopeContext:
    """Escopo da escola (linhas) vs município (medias_da_rede) para comparativo."""

    scope_linhas: ScopeIndex
    scope_rede: ScopeIndex
    series_colunas: List[Dict[str, str]]
    comparativo_municipio: bool
    escola_id: Optional[str] = None


def _build_scope_index(
    classes: List[Class],
    students_by_class: Dict[str, List[Student]],
    item_id_by_class: Optional[Dict[str, str]] = None,
) -> ScopeIndex:
    """Monta índice (escola_id, serie_id) → turmas a partir das classes do escopo."""
    grade_meta: Dict[str, Tuple[str, str]] = {}
    school_meta: Dict[str, str] = {}
    classes_by_cell: Dict[Tuple[str, str], Set[str]] = defaultdict(set)
    class_to_cell: Dict[str, Tuple[str, str]] = {}
    series_items: List[Tuple[str, str, str, str, str]] = []

    for co in classes:
        if not co or not co.school_id:
            continue
        escola_id = str(co.school_id)
        serie_id, serie_nome = _series_identity_for_class(co)
        escola_nome = (co.school.name if co.school else None) or "Escola"
        school_meta[escola_id] = escola_nome
        grade_meta[serie_id] = (serie_id, serie_nome)
        cid = str(co.id)
        cell = (escola_id, serie_id)
        classes_by_cell[cell].add(cid)
        class_to_cell[cid] = cell
        iid = (item_id_by_class or {}).get(cid, "")
        if iid:
            series_items.append((escola_id, escola_nome, serie_id, serie_nome, iid))

    series_colunas = [
        {"serie_id": gid, "serie_nome": gname}
        for gid, gname in sorted(grade_meta.values(), key=lambda x: _series_sort_key(x[1]))
    ]
    escolas = [
        {"escola_id": sid, "escola_nome": sname}
        for sid, sname in sorted(school_meta.items(), key=lambda x: x[1].upper())
    ]
    return ScopeIndex(
        series_colunas=series_colunas,
        escolas=escolas,
        classes_by_cell=dict(classes_by_cell),
        class_to_cell=class_to_cell,
        students_by_class=students_by_class,
        series_items=series_items,
    )


def _students_in_cell(scope: ScopeIndex, escola_id: str, serie_id: str) -> Set[str]:
    cids = scope.classes_by_cell.get((escola_id, serie_id), set())
    out: Set[str] = set()
    for cid in cids:
        for st in scope.students_by_class.get(cid, []):
            out.add(str(st.id))
    return out


def _student_in_cell(scope: ScopeIndex, student_id: str, escola_id: str, serie_id: str) -> bool:
    return student_id in _students_in_cell(scope, escola_id, serie_id)


def _class_ids_in_cell(scope: ScopeIndex, escola_id: str, serie_id: str) -> Set[str]:
    return scope.classes_by_cell.get((escola_id, serie_id), set())


def _build_series_aplicadas(
    class_items: List[Tuple[str, str, str, str, str]],
) -> List[Dict[str, Any]]:
    tree: Dict[str, Dict[str, Any]] = {}
    for sid, sname, gid, gname, item_id in class_items:
        if sid not in tree:
            tree[sid] = {"escola_id": sid, "escola_nome": sname, "series": {}}
        series = tree[sid]["series"]
        if gid not in series:
            series[gid] = {"serie_id": gid, "serie_nome": gname, "itens": set()}
        series[gid]["itens"].add(item_id)
    out: List[Dict[str, Any]] = []
    for sch in sorted(tree.values(), key=lambda x: (x.get("escola_nome") or "").upper()):
        series_list = []
        for s in sorted(sch["series"].values(), key=lambda x: _series_sort_key(x.get("serie_nome") or "")):
            series_list.append(
                {"serie_id": s["serie_id"], "serie_nome": s["serie_nome"], "itens": sorted(s["itens"])}
            )
        out.append({"escola_id": sch["escola_id"], "escola_nome": sch["escola_nome"], "series": series_list})
    return out


# ---------------------------------------------------------------------------
# Matriz genérica
# ---------------------------------------------------------------------------


def _empty_matriz() -> Dict[str, Any]:
    return {"linhas": [], "medias_da_rede": {"por_serie": [], "taxa_geral": None}}


def _build_numeric_matriz(
    scope_linhas: ScopeIndex,
    cell_fn: Callable[[str, str], Optional[float]],
    *,
    scope_rede: Optional[ScopeIndex] = None,
    cell_fn_rede: Optional[Callable[[str, str], Optional[float]]] = None,
    series_colunas: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """
    ⚠️ HIERARQUIA CORRETA PARA TAXA_GERAL MUNICIPAL ⚠️
    
    Constrói matriz numérica (nota/proficiência/taxa participação) com hierarquia:
    
    1. CÉLULA (escola × série) → cell_fn retorna média da turma/célula
    2. LINHA (escola) → taxa_geral_escola = média das séries (peso igual por série)
    3. COLUNA (série) → por_serie = média das escolas (peso igual por escola)
    4. REDE → taxa_geral = MÉDIA DAS COLUNAS (por_serie), NÃO das linhas
    
    CORRETO: taxa_geral = média de por_serie (hierarquia série → município)
    ERRADO:  taxa_geral = média das escolas (hierarquia escola → município)
              ↑ daria mais peso a escolas com mais séries (média ponderada)
    """
    cols = series_colunas or scope_linhas.series_colunas
    rede_scope = scope_rede or scope_linhas
    rede_fn = cell_fn_rede or cell_fn

    if not scope_linhas.escolas or not cols:
        return _empty_matriz()

    linhas: List[Dict[str, Any]] = []
    for esc in scope_linhas.escolas:
        eid = esc["escola_id"]
        valores: List[Optional[float]] = []
        row_nums: List[float] = []
        for col in cols:
            sid = col["serie_id"]
            if (eid, sid) not in scope_linhas.classes_by_cell:
                valores.append(None)
                continue
            val = cell_fn(eid, sid)
            if val is None:
                valores.append(None)
            else:
                fv = float(val)
                valores.append(fv)
                row_nums.append(fv)
        linhas.append(
            {
                "escola_id": eid,
                "escola_nome": esc["escola_nome"],
                "valores_por_serie": valores,
                # ✅ CORRETO: taxa_geral_escola = média hierárquica das séries (peso igual)
                "taxa_geral_escola": _mean_numeric(row_nums),
            }
        )

    # ✅ CORRETO: por_serie = média das escolas por cada série (peso igual por escola)
    por_serie: List[Optional[float]] = []
    for col in cols:
        sid = col["serie_id"]
        col_vals: List[float] = []
        for esc in rede_scope.escolas:
            eid = esc["escola_id"]
            if (eid, sid) not in rede_scope.classes_by_cell:
                continue
            v = rede_fn(eid, sid)
            if v is not None:
                col_vals.append(float(v))
        por_serie.append(_mean_numeric(col_vals) if col_vals else None)

    # ✅ CORRETO: taxa_geral = média hierárquica das séries (peso igual por série)
    # Hierarquia: Série → Município (não Escola → Município)
    # Isso garante que cada série tenha peso igual, independente de quantas escolas têm aquela série
    taxa_geral_municipal = _mean_numeric([v for v in por_serie if v is not None])

    return {
        "linhas": linhas,
        "medias_da_rede": {
            "por_serie": por_serie,
            "taxa_geral": taxa_geral_municipal,
        },
    }


def _dist_to_percentuais(dist: Dict[str, int]) -> Dict[str, float]:
    total = sum(dist.get(k, 0) for k in FAIXAS)
    if total <= 0:
        return {k: 0.0 for k in FAIXAS}
    return {k: round_to_two_decimals(100.0 * dist.get(k, 0) / total) for k in FAIXAS}


def _mean_distrib_percentuais(dists: List[Dict[str, int]]) -> Dict[str, float]:
    """
    ⚠️ REGRA OBRIGATÓRIA: NÃO EXISTE MÉDIA PONDERADA NESTE SISTEMA ⚠️
    
    Calcula média HIERÁRQUICA dos percentuais de distribuição.
    Cada distribuição (série ou escola) tem PESO IGUAL, independente do número de alunos.
    
    Processo:
    1. Converte cada distribuição de contagens para percentuais
    2. Tira média aritmética simples dos percentuais por faixa
    
    Nunca some contagens antes de calcular percentuais - isso gera média ponderada!
    """
    if not dists:
        return {k: 0.0 for k in FAIXAS}
    pcts_list = [_dist_to_percentuais(d) for d in dists]
    return {k: _mean_numeric([p[k] for p in pcts_list]) for k in FAIXAS}


def _school_row_percentuais_for_rede(
    rede_scope: ScopeIndex,
    cols: List[Dict[str, str]],
    cell_fn: Callable[[str, str], Optional[Dict[str, int]]],
) -> List[Dict[str, float]]:
    """
    ⚠️ REGRA OBRIGATÓRIA: NÃO EXISTE MÉDIA PONDERADA NESTE SISTEMA ⚠️
    
    Retorna PERCENTUAIS médios por escola (não contagens somadas).
    
    Para cada escola:
    1. Coleta distribuições de cada série
    2. Converte cada série em percentuais
    3. Calcula média dos percentuais (peso igual por série)
    
    NUNCA retorna contagens somadas - isso geraria média ponderada pelo número de alunos.
    Hierarquia: série → escola (peso igual entre séries da mesma escola).
    """
    out: List[Dict[str, float]] = []
    for esc in rede_scope.escolas:
        eid = esc["escola_id"]
        cell_dists: List[Dict[str, int]] = []
        for col in cols:
            sid = col["serie_id"]
            if (eid, sid) not in rede_scope.classes_by_cell:
                continue
            d = cell_fn(eid, sid)
            if d and sum(d.values()) > 0:
                cell_dists.append(d)
        if not cell_dists:
            continue
        # ✅ CORRETO: média dos percentuais (peso igual por série)
        escola_pct = _mean_distrib_percentuais(cell_dists)
        out.append(escola_pct)
    return out


def _build_distribuicao_matriz(
    scope_linhas: ScopeIndex,
    cell_fn: Callable[[str, str], Optional[Dict[str, int]]],
    *,
    scope_rede: Optional[ScopeIndex] = None,
    cell_fn_rede: Optional[Callable[[str, str], Optional[Dict[str, int]]]] = None,
    series_colunas: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    cols = series_colunas or scope_linhas.series_colunas
    rede_scope = scope_rede or scope_linhas
    rede_fn = cell_fn_rede or cell_fn
    empty_rede = {
        "por_serie": [],
        "taxa_geral": {
            "percentuais": {k: 0.0 for k in FAIXAS},
            "contagens": _empty_distribution(),
            "total_registros": 0,
        },
        "media_da_rede_nivel": None,
    }

    if not scope_linhas.escolas or not cols:
        return {"linhas": [], "medias_da_rede": empty_rede}

    linhas: List[Dict[str, Any]] = []
    for esc in scope_linhas.escolas:
        eid = esc["escola_id"]
        valores: List[Optional[Dict[str, Any]]] = []
        cell_dists: List[Dict[str, int]] = []
        for col in cols:
            sid = col["serie_id"]
            if (eid, sid) not in scope_linhas.classes_by_cell:
                valores.append(None)
                continue
            dist = cell_fn(eid, sid)
            if not dist or sum(dist.values()) == 0:
                valores.append(None)
                continue
            total = sum(dist.values())
            valores.append(
                {
                    "contagens": dict(dist),
                    "percentuais": _dist_to_percentuais(dist),
                    "total_registros": total,
                }
            )
            cell_dists.append(dist)
        # ✅ CORRETO: média hierárquica dos percentuais (peso igual por série)
        taxa_pct = _mean_distrib_percentuais(cell_dists)
        # Calcular contagens totais da escola (apenas para exibição, NÃO para calcular percentuais)
        merged = _empty_distribution()
        for d in cell_dists:
            for k in FAIXAS:
                merged[k] += d.get(k, 0)
        linhas.append(
            {
                "escola_id": eid,
                "escola_nome": esc["escola_nome"],
                "valores_por_serie": valores,
                "taxa_geral_escola": {
                    "percentuais": taxa_pct,
                    "contagens": merged,
                    "total_registros": sum(merged.values()),
                },
            }
        )

    por_serie: List[Optional[Dict[str, Any]]] = []
    for col in cols:
        sid = col["serie_id"]
        col_dists: List[Dict[str, int]] = []
        for esc in rede_scope.escolas:
            eid = esc["escola_id"]
            if (eid, sid) not in rede_scope.classes_by_cell:
                continue
            d = rede_fn(eid, sid)
            if d and sum(d.values()) > 0:
                col_dists.append(d)
        if not col_dists:
            por_serie.append(None)
        else:
            # Calcular contagens totais da série (apenas para exibição, NÃO para calcular percentuais)
            merged = _empty_distribution()
            for d in col_dists:
                for k in FAIXAS:
                    merged[k] += d.get(k, 0)
            por_serie.append(
                {
                    # ✅ CORRETO: média hierárquica dos percentuais (peso igual por escola)
                    "percentuais": _mean_distrib_percentuais(col_dists),
                    "contagens": merged,
                    "total_registros": sum(merged.values()),
                }
            )

    rede_school_pcts = _school_row_percentuais_for_rede(rede_scope, cols, rede_fn)
    # ✅ CORRETO: média dos percentuais médios por escola (peso igual por escola)
    taxa_rede_pct = {k: _mean_numeric([p[k] for p in rede_school_pcts]) for k in FAIXAS} if rede_school_pcts else {k: 0.0 for k in FAIXAS}
    
    # Calcular contagens totais da rede (apenas para exibição, NÃO para calcular percentuais)
    rede_merged = _empty_distribution()
    for esc in rede_scope.escolas:
        eid = esc["escola_id"]
        for col in cols:
            sid = col["serie_id"]
            if (eid, sid) not in rede_scope.classes_by_cell:
                continue
            d = rede_fn(eid, sid)
            if d and sum(d.values()) > 0:
                for k in FAIXAS:
                    rede_merged[k] += d.get(k, 0)

    return {
        "linhas": linhas,
        "medias_da_rede": {
            "por_serie": por_serie,
            "taxa_geral": {
                "percentuais": taxa_rede_pct,
                "contagens": rede_merged,
                "total_registros": sum(rede_merged.values()),
            },
            "media_da_rede_nivel": None,
        },
    }


def _matriz_kwargs(ctx: ConsolidatedScopeContext) -> Dict[str, Any]:
    if not ctx.comparativo_municipio:
        return {}
    return {
        "scope_rede": ctx.scope_rede,
        "series_colunas": ctx.series_colunas,
    }


def _section_geral_e_disciplinas(
    ctx: ConsolidatedScopeContext,
    all_disciplines: Set[str],
    build_for_discipline: Callable[[Optional[str]], Dict[str, Any]],
) -> Dict[str, Any]:
    por_disc = {d: build_for_discipline(d) for d in sorted(all_disciplines)}
    return {GERAL_KEY: build_for_discipline(None), "por_disciplina": por_disc}


def _scope_context_from_single(scope: ScopeIndex, escola_id: Optional[str] = None) -> ConsolidatedScopeContext:
    return ConsolidatedScopeContext(
        scope_linhas=scope,
        scope_rede=scope,
        series_colunas=scope.series_colunas,
        comparativo_municipio=False,
        escola_id=escola_id,
    )


def _scope_context_dual(
    scope_linhas: ScopeIndex,
    scope_rede: ScopeIndex,
    escola_id: str,
) -> ConsolidatedScopeContext:
    return ConsolidatedScopeContext(
        scope_linhas=scope_linhas,
        scope_rede=scope_rede,
        series_colunas=scope_rede.series_colunas,
        comparativo_municipio=True,
        escola_id=escola_id,
    )


# ---------------------------------------------------------------------------
# Sessões: frequência, médias, acertos, distribuição
# ---------------------------------------------------------------------------


def _digital_participants_in_cell(
    scope: ScopeIndex,
    results: List[EvaluationResult],
    escola_id: str,
    serie_id: str,
    discipline: Optional[str],
    tests_by_id: Dict[str, Test],
    subject_has_disc: Optional[Dict[str, Set[str]]] = None,
) -> Set[str]:
    stu_ids = _students_in_cell(scope, escola_id, serie_id)
    if not stu_ids:
        return set()
    out: Set[str] = set()
    for r in results:
        sid = str(r.student_id)
        if sid not in stu_ids:
            continue
        if discipline is None:
            out.add(sid)
            continue
        test = tests_by_id.get(str(r.test_id))
        if not test:
            continue
        if subject_has_disc and discipline not in (subject_has_disc.get(str(r.test_id)) or set()):
            continue
        if r.subject_results and isinstance(r.subject_results, dict):
            id_map = _subject_id_to_name_map(test)
            for subj_key, block in r.subject_results.items():
                if not isinstance(block, dict):
                    continue
                if id_map.get(str(subj_key), str(subj_key)) == discipline:
                    out.add(sid)
                    break
    return out


def _build_frequencia_section_digital(
    ctx: ConsolidatedScopeContext,
    results_linhas: List[EvaluationResult],
    results_rede: List[EvaluationResult],
    tests_by_id: Dict[str, Test],
    all_disciplines: Set[str],
) -> Dict[str, Any]:
    subject_has_disc: Dict[str, Set[str]] = {tid: _disciplinas_from_test(t) for tid, t in tests_by_id.items()}
    mk = _matriz_kwargs(ctx)

    def _freq_cell(
        scope: ScopeIndex,
        results: List[EvaluationResult],
        escola_id: str,
        serie_id: str,
        discipline: Optional[str],
    ) -> Optional[float]:
        if (escola_id, serie_id) not in scope.classes_by_cell:
            return None
        mat = len(_students_in_cell(scope, escola_id, serie_id))
        if mat == 0:
            return None
        part = len(
            _digital_participants_in_cell(
                scope, results, escola_id, serie_id, discipline, tests_by_id, subject_has_disc
            )
        )
        return round_to_two_decimals(100.0 * part / mat)

    def _build_one(discipline: Optional[str]) -> Dict[str, Any]:
        kw = dict(mk)
        if ctx.comparativo_municipio:
            kw["cell_fn_rede"] = lambda e, s: _freq_cell(ctx.scope_rede, results_rede, e, s, discipline)
        return _build_numeric_matriz(
            ctx.scope_linhas,
            lambda e, s: _freq_cell(ctx.scope_linhas, results_linhas, e, s, discipline),
            **kw,
        )

    return _section_geral_e_disciplinas(ctx, all_disciplines, _build_one)


def _build_frequencia_section_answer_sheet(
    ctx: ConsolidatedScopeContext,
    results_linhas: List[AnswerSheetResult],
    results_rede: List[AnswerSheetResult],
    all_disciplines: Set[str],
) -> Dict[str, Any]:
    mk = _matriz_kwargs(ctx)

    def _participants(
        scope: ScopeIndex,
        results: List[AnswerSheetResult],
        escola_id: str,
        serie_id: str,
        discipline: Optional[str],
    ) -> Set[str]:
        cids = _class_ids_in_cell(scope, escola_id, serie_id)
        out: Set[str] = set()
        for r in results:
            st = r.student
            if not st or not st.class_id or str(st.class_id) not in cids:
                continue
            if discipline is None:
                out.add(str(r.student_id))
                continue
            pbs = r.proficiency_by_subject or {}
            if isinstance(pbs, dict):
                for _sid, block in pbs.items():
                    if isinstance(block, dict) and (block.get("subject_name") or "").strip() == discipline:
                        out.add(str(r.student_id))
                        break
        return out

    def _freq_cell(
        scope: ScopeIndex,
        results: List[AnswerSheetResult],
        escola_id: str,
        serie_id: str,
        discipline: Optional[str],
    ) -> Optional[float]:
        if (escola_id, serie_id) not in scope.classes_by_cell:
            return None
        mat = len(_students_in_cell(scope, escola_id, serie_id))
        if mat == 0:
            return None
        part = len(_participants(scope, results, escola_id, serie_id, discipline))
        return round_to_two_decimals(100.0 * part / mat)

    def _build_one(discipline: Optional[str]) -> Dict[str, Any]:
        kw = dict(mk)
        if ctx.comparativo_municipio:
            kw["cell_fn_rede"] = lambda e, s: _freq_cell(ctx.scope_rede, results_rede, e, s, discipline)
        return _build_numeric_matriz(
            ctx.scope_linhas,
            lambda e, s: _freq_cell(ctx.scope_linhas, results_linhas, e, s, discipline),
            **kw,
        )

    return _section_geral_e_disciplinas(ctx, all_disciplines, _build_one)


def _filter_digital_results_in_cell(
    scope: ScopeIndex,
    results: List[EvaluationResult],
    escola_id: str,
    serie_id: str,
) -> List[EvaluationResult]:
    stu_ids = _students_in_cell(scope, escola_id, serie_id)
    return [r for r in results if str(r.student_id) in stu_ids]


def _filter_answer_sheet_in_cell(
    scope: ScopeIndex,
    results: List[AnswerSheetResult],
    escola_id: str,
    serie_id: str,
) -> List[AnswerSheetResult]:
    cids = _class_ids_in_cell(scope, escola_id, serie_id)
    out: List[AnswerSheetResult] = []
    for r in results:
        st = r.student
        if st and st.class_id and str(st.class_id) in cids:
            out.append(r)
    return out


def _subject_rows_from_digital_result(
    r: EvaluationResult,
    test: Optional[Test],
    discipline: Optional[str],
) -> List[Dict[str, Any]]:
    if discipline is None:
        return [{"student_id": r.student_id, "grade": float(r.grade or 0), "proficiency": float(r.proficiency or 0)}]
    rows: List[Dict[str, Any]] = []
    id_map = _subject_id_to_name_map(test) if test else {}
    if r.subject_results and isinstance(r.subject_results, dict):
        for sk, block in r.subject_results.items():
            if not isinstance(block, dict):
                continue
            name = id_map.get(str(sk), str(sk))
            if name == discipline:
                rows.append(
                    {
                        "student_id": r.student_id,
                        "grade": float(block.get("grade") or 0),
                        "proficiency": float(block.get("proficiency") or 0),
                    }
                )
    return rows


def _subject_rows_from_answer_sheet(
    r: AnswerSheetResult,
    discipline: Optional[str],
) -> List[Dict[str, Any]]:
    if discipline is None:
        return [{"student_id": r.student_id, "grade": float(r.grade or 0), "proficiency": float(r.proficiency or 0)}]
    rows: List[Dict[str, Any]] = []
    pbs = r.proficiency_by_subject or {}
    if isinstance(pbs, dict):
        for _sid, block in pbs.items():
            if not isinstance(block, dict):
                continue
            name = (block.get("subject_name") or str(_sid)).strip()
            if name == discipline:
                rows.append(
                    {
                        "student_id": r.student_id,
                        "grade": float(block.get("grade") or 0),
                        "proficiency": float(block.get("proficiency") or 0),
                    }
                )
    return rows


def _build_medias_section_digital(
    ctx: ConsolidatedScopeContext,
    results_linhas: List[EvaluationResult],
    results_rede: List[EvaluationResult],
    tests_by_id: Dict[str, Test],
    all_disciplines: Set[str],
    field: str,
    course_name: str = "Anos Iniciais",
    has_matematica: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    ⚠️ MÉDIA HIERÁRQUICA (NÃO PONDERADA) ⚠️
    
    Hierarquia para medias_da_rede.taxa_geral:
    1. TURMA → média das proficiências dos alunos; nota = calculate_grade(média_prof)
    2. SÉRIE → média das turmas/escolas (peso igual por escola que tem a série)
    3. MUNICÍPIO → média das séries (peso igual por série)
    
    NUNCA calcular média das escolas para obter taxa_geral, pois escolas com mais
    séries teriam mais peso (média ponderada).
    """
    mk = _matriz_kwargs(ctx)

    def _media_cell(
        scope: ScopeIndex,
        results: List[EvaluationResult],
        escola_id: str,
        serie_id: str,
        discipline: Optional[str],
    ) -> Optional[float]:
        cell_results = _filter_digital_results_in_cell(scope, results, escola_id, serie_id)
        if not cell_results:
            return None
        if discipline is None:
            mg, mp = hierarchical_mean_grade_and_proficiency(
                cell_results,
                "turma",
                course_name=course_name,
                has_matematica=has_matematica,
            )
            return round_to_two_decimals(mg if field == "grade" else mp)
        srows: List[Dict[str, Any]] = []
        for r in cell_results:
            test = tests_by_id.get(str(r.test_id))
            srows.extend(_subject_rows_from_digital_result(r, test, discipline))
        if not srows:
            return None
        mg, mp, _ = hierarchical_mean_from_subject_rows(
            srows,
            "turma",
            course_name=course_name,
            subject_name=discipline or "GERAL",
            has_matematica=has_matematica,
        )
        return round_to_two_decimals(mg if field == "grade" else mp)

    def _build_one(discipline: Optional[str]) -> Dict[str, Any]:
        kw = dict(mk)
        if ctx.comparativo_municipio:
            kw["cell_fn_rede"] = lambda e, s: _media_cell(ctx.scope_rede, results_rede, e, s, discipline)
        return _build_numeric_matriz(
            ctx.scope_linhas,
            lambda e, s: _media_cell(ctx.scope_linhas, results_linhas, e, s, discipline),
            **kw,
        )

    return _section_geral_e_disciplinas(ctx, all_disciplines, _build_one)


def _build_medias_section_answer_sheet(
    ctx: ConsolidatedScopeContext,
    results_linhas: List[AnswerSheetResult],
    results_rede: List[AnswerSheetResult],
    all_disciplines: Set[str],
    field: str,
    course_name: str = "Anos Iniciais",
    has_matematica: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    ⚠️ MÉDIA HIERÁRQUICA (NÃO PONDERADA) ⚠️
    
    Hierarquia para medias_da_rede.taxa_geral:
    1. TURMA → média das proficiências dos alunos; nota = calculate_grade(média_prof)
    2. SÉRIE → média das turmas/escolas (peso igual por escola que tem a série)
    3. MUNICÍPIO → média das séries (peso igual por série)
    
    NUNCA calcular média das escolas para obter taxa_geral, pois escolas com mais
    séries teriam mais peso (média ponderada).
    """
    mk = _matriz_kwargs(ctx)

    def _media_cell(
        scope: ScopeIndex,
        results: List[AnswerSheetResult],
        escola_id: str,
        serie_id: str,
        discipline: Optional[str],
    ) -> Optional[float]:
        cell_results = _filter_answer_sheet_in_cell(scope, results, escola_id, serie_id)
        if not cell_results:
            return None
        if discipline is None:
            mg, mp = hierarchical_mean_grade_and_proficiency(
                cell_results,
                "turma",
                course_name=course_name,
                has_matematica=has_matematica,
            )
            return round_to_two_decimals(mg if field == "grade" else mp)
        srows: List[Dict[str, Any]] = []
        for r in cell_results:
            srows.extend(_subject_rows_from_answer_sheet(r, discipline))
        if not srows:
            return None
        mg, mp, _ = hierarchical_mean_from_subject_rows(
            srows,
            "turma",
            course_name=course_name,
            subject_name=discipline or "GERAL",
            has_matematica=has_matematica,
        )
        return round_to_two_decimals(mg if field == "grade" else mp)

    def _build_one(discipline: Optional[str]) -> Dict[str, Any]:
        kw = dict(mk)
        if ctx.comparativo_municipio:
            kw["cell_fn_rede"] = lambda e, s: _media_cell(ctx.scope_rede, results_rede, e, s, discipline)
        return _build_numeric_matriz(
            ctx.scope_linhas,
            lambda e, s: _media_cell(ctx.scope_linhas, results_linhas, e, s, discipline),
            **kw,
        )

    return _section_geral_e_disciplinas(ctx, all_disciplines, _build_one)


def _build_distribuicao_section_digital(
    ctx: ConsolidatedScopeContext,
    results_linhas: List[EvaluationResult],
    results_rede: List[EvaluationResult],
    tests_by_id: Dict[str, Test],
    all_disciplines: Set[str],
    course_name: str,
    has_matematica: bool,
) -> Dict[str, Any]:
    mk = _matriz_kwargs(ctx)

    def _cell_dist(
        scope: ScopeIndex,
        results: List[EvaluationResult],
        escola_id: str,
        serie_id: str,
        discipline: Optional[str],
    ) -> Optional[Dict[str, int]]:
        cell_results = _filter_digital_results_in_cell(scope, results, escola_id, serie_id)
        if not cell_results:
            return None
        dist = _empty_distribution()
        for r in cell_results:
            if discipline is None:
                dist[_classification_bucket(r.classification)] += 1
                continue
            test = tests_by_id.get(str(r.test_id))
            id_map = _subject_id_to_name_map(test) if test else {}
            if r.subject_results and isinstance(r.subject_results, dict):
                for sk, block in r.subject_results.items():
                    if isinstance(block, dict) and id_map.get(str(sk), str(sk)) == discipline:
                        dist[_classification_bucket(block.get("classification"))] += 1
        return dist if sum(dist.values()) > 0 else None

    def _build_one(discipline: Optional[str]) -> Dict[str, Any]:
        kw = dict(mk)
        if ctx.comparativo_municipio:
            kw["cell_fn_rede"] = lambda e, s: _cell_dist(ctx.scope_rede, results_rede, e, s, discipline)
        return _build_distribuicao_matriz(
            ctx.scope_linhas,
            lambda e, s: _cell_dist(ctx.scope_linhas, results_linhas, e, s, discipline),
            **kw,
        )

    out = _section_geral_e_disciplinas(ctx, all_disciplines, _build_one)
    _, mp = (
        hierarchical_mean_grade_and_proficiency(
            results_rede, "municipio", course_name=course_name, has_matematica=has_matematica
        )
        if results_rede
        else (0.0, 0.0)
    )
    out[GERAL_KEY]["medias_da_rede"]["media_da_rede_nivel"] = (
        EvaluationCalculator.determine_classification(mp, course_name, GERAL_KEY, has_matematica=has_matematica)
        if results_rede
        else None
    )
    return out


def _build_distribuicao_section_answer_sheet(
    ctx: ConsolidatedScopeContext,
    results_linhas: List[AnswerSheetResult],
    results_rede: List[AnswerSheetResult],
    all_disciplines: Set[str],
    course_name: str,
    has_matematica: bool,
) -> Dict[str, Any]:
    mk = _matriz_kwargs(ctx)

    def _cell_dist(
        scope: ScopeIndex,
        results: List[AnswerSheetResult],
        escola_id: str,
        serie_id: str,
        discipline: Optional[str],
    ) -> Optional[Dict[str, int]]:
        cell_results = _filter_answer_sheet_in_cell(scope, results, escola_id, serie_id)
        if not cell_results:
            return None
        dist = _empty_distribution()
        for r in cell_results:
            if discipline is None:
                dist[_classification_bucket(r.classification)] += 1
                continue
            pbs = r.proficiency_by_subject or {}
            if isinstance(pbs, dict):
                for _sid, block in pbs.items():
                    if isinstance(block, dict) and (block.get("subject_name") or "").strip() == discipline:
                        dist[_classification_bucket(block.get("classification"))] += 1
        return dist if sum(dist.values()) > 0 else None

    def _build_one(discipline: Optional[str]) -> Dict[str, Any]:
        kw = dict(mk)
        if ctx.comparativo_municipio:
            kw["cell_fn_rede"] = lambda e, s: _cell_dist(ctx.scope_rede, results_rede, e, s, discipline)
        return _build_distribuicao_matriz(
            ctx.scope_linhas,
            lambda e, s: _cell_dist(ctx.scope_linhas, results_linhas, e, s, discipline),
            **kw,
        )

    out = _section_geral_e_disciplinas(ctx, all_disciplines, _build_one)
    _, mp = (
        hierarchical_mean_grade_and_proficiency(
            results_rede, "municipio", course_name=course_name, has_matematica=has_matematica
        )
        if results_rede
        else (0.0, 0.0)
    )
    out[GERAL_KEY]["medias_da_rede"]["media_da_rede_nivel"] = (
        EvaluationCalculator.determine_classification(mp, course_name, GERAL_KEY, has_matematica=has_matematica)
        if results_rede
        else None
    )
    return out


# ---------------------------------------------------------------------------
# Acertos por habilidade: matriz + lista por série (uma entrada por questão)
# ---------------------------------------------------------------------------


def _series_ids_by_item(scope: ScopeIndex) -> Dict[str, Set[str]]:
    out: Dict[str, Set[str]] = defaultdict(set)
    for _eid, _en, serie_id, _sn, item_id in scope.series_items:
        if item_id:
            out[str(item_id)].add(str(serie_id))
    return dict(out)


def _question_agg_key(item_id: str, question_ref: str) -> str:
    return f"{item_id}:{question_ref}"


def _seed_question_agg_bucket(
    bucket: Dict[str, Any],
    *,
    item_id: str,
    codigo: str,
    descricao: str,
    disciplina: str,
    ordem_original: int,
    numero_questao: Any,
) -> None:
    if bucket.get("codigo"):
        return
    bucket["codigo"] = codigo
    bucket["descricao"] = descricao
    bucket["disciplina"] = disciplina
    bucket["ordem_original"] = ordem_original
    bucket["numero_questao"] = numero_questao
    bucket.setdefault("itens_origem", set()).add(str(item_id))


def _digital_question_meta(
    question: Question, test: Test, skills_dict: Dict[str, Skill]
) -> Tuple[str, str, str]:
    clean_skill = str(question.skill or "").replace("{", "").replace("}", "").strip()
    skill_obj = skills_dict.get(clean_skill) if clean_skill and clean_skill != "{}" else None
    if skill_obj:
        code = skill_obj.code or clean_skill
        desc = skill_obj.description or f"Habilidade {code}"
        if skill_obj.subject_id:
            subj = Subject.query.get(skill_obj.subject_id)
            disciplina = subj.name if subj else "Disciplina Geral"
        else:
            disciplina = "Disciplina Geral"
    else:
        code = f"Q{question.number or question.id}"
        desc = f"Questão {question.number or 'N/A'}"
        disciplina = test.subject_rel.name if test.subject_rel else "Disciplina Geral"
    return code, desc, disciplina


def _habilidades_list_from_agg(agg: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for _key, data in sorted(
        agg.items(),
        key=lambda x: (
            str(x[0]).split(":", 1)[0],
            x[1].get("ordem_original") if x[1].get("ordem_original") is not None else 999999,
            str(x[0]),
        ),
    ):
        total = int(data.get("total") or 0)
        acertos = int(data.get("acertos") or 0)
        pct = round_to_two_decimals((acertos / total * 100) if total > 0 else 0.0)
        ordem = data.get("ordem_original")
        numero = data.get("numero_questao")
        if numero is None:
            numero = ordem
        rows.append(
            {
                "numero_questao": numero,
                "ordem_original": ordem,
                "codigo": data.get("codigo") or "—",
                "descricao": data.get("descricao") or "",
                "disciplina": data.get("disciplina") or "Disciplina Geral",
                "acertos": acertos,
                "total": total,
                "percentual": float(pct),
                "itens_origem": sorted(data.get("itens_origem") or []),
            }
        )
    return rows


def _habilidades_por_serie_blocks(
    series_colunas: List[Dict[str, str]],
    agg_by_serie: Dict[str, Dict[str, Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    """Uma lista por questão em cada série (mesma habilidade pode repetir entre questões)."""
    return [
        {
            "serie_id": col["serie_id"],
            "serie_nome": col["serie_nome"],
            "habilidades": _habilidades_list_from_agg(dict(agg_by_serie.get(col["serie_id"], {}))),
        }
        for col in series_colunas
    ]


def _habilidades_por_serie_for_discipline(
    series_colunas: List[Dict[str, str]],
    agg_by_serie_disc: Dict[str, Dict[str, Dict[str, Dict[str, Any]]]],
    discipline: str,
) -> List[Dict[str, Any]]:
    per_serie: Dict[str, Dict[str, Dict[str, Any]]] = {
        col["serie_id"]: dict(agg_by_serie_disc.get(col["serie_id"], {}).get(discipline, {}))
        for col in series_colunas
    }
    return _habilidades_por_serie_blocks(series_colunas, per_serie)


def _answer_is_correct(question: Question, answer: StudentAnswer) -> bool:
    from app.services.evaluation_result_service import EvaluationResultService

    if question.question_type == "multiple_choice":
        return bool(
            EvaluationResultService.check_multiple_choice_answer(answer.answer, question.correct_answer)
        )
    if question.question_type in ("essay", "open", "discursive"):
        return bool(answer.manual_score and float(answer.manual_score or 0) > 0)
    return bool(
        answer.answer
        and str(answer.answer).strip().lower() == str(question.correct_answer or "").strip().lower()
    )


def _digital_acertos_aggregate(
    scope: ScopeIndex,
    tests_by_id: Dict[str, Test],
    test_ids: List[str],
    class_ids: List[Any],
    all_disciplines: Set[str],
) -> Tuple[
    Dict[str, Dict[str, Dict[str, Any]]],
    Dict[str, Dict[str, Dict[str, Dict[str, Any]]]],
    Dict[Optional[str], Dict[Tuple[str, str], List[int]]],
]:
    agg_by_serie: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(
        lambda: defaultdict(
            lambda: {
                "acertos": 0,
                "total": 0,
                "codigo": "",
                "descricao": "",
                "disciplina": "",
                "ordem_original": None,
                "numero_questao": None,
                "itens_origem": set(),
            }
        )
    )
    agg_by_serie_disc: Dict[str, Dict[str, Dict[str, Dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(
            lambda: defaultdict(
                lambda: {
                    "acertos": 0,
                    "total": 0,
                    "codigo": "",
                    "descricao": "",
                    "disciplina": "",
                    "ordem_original": None,
                    "numero_questao": None,
                    "itens_origem": set(),
                }
            )
        )
    )
    cell_totals: Dict[Optional[str], Dict[Tuple[str, str], List[int]]] = defaultdict(lambda: defaultdict(lambda: [0, 0]))

    if not class_ids:
        return dict(agg_by_serie), dict(agg_by_serie_disc), dict(cell_totals)

    class_id_set = {str(c) for c in class_ids}
    series_by_item = _series_ids_by_item(scope)

    for tid in test_ids:
        test = tests_by_id.get(str(tid))
        if not test or not test.questions:
            continue
        skill_ids: Set[str] = set()
        for q in test.questions:
            if q.skill and str(q.skill).strip() not in ("", "{}"):
                skill_ids.add(str(q.skill).replace("{", "").replace("}", ""))
        skills_dict = {str(s.id): s for s in Skill.query.filter(Skill.id.in_(skill_ids)).all()} if skill_ids else {}

        answers = (
            StudentAnswer.query.filter(StudentAnswer.test_id == str(tid))
            .join(Student, StudentAnswer.student_id == Student.id)
            .filter(Student.class_id.in_(class_ids))
            .all()
        )
        by_q: Dict[str, List[StudentAnswer]] = defaultdict(list)
        for a in answers:
            by_q[str(a.question_id)].append(a)

        serie_ids = series_by_item.get(str(tid), set())

        for idx, question in enumerate(test.questions, start=1):
            code, desc, disciplina = _digital_question_meta(question, test, skills_dict)
            numero = question.number if question.number is not None else idx
            agg_key = _question_agg_key(str(tid), str(question.id))

            for serie_id in serie_ids:
                _seed_question_agg_bucket(
                    agg_by_serie[serie_id][agg_key],
                    item_id=str(tid),
                    codigo=code,
                    descricao=desc,
                    disciplina=disciplina,
                    ordem_original=idx,
                    numero_questao=numero,
                )
                if disciplina in all_disciplines:
                    _seed_question_agg_bucket(
                        agg_by_serie_disc[serie_id][disciplina][agg_key],
                        item_id=str(tid),
                        codigo=code,
                        descricao=desc,
                        disciplina=disciplina,
                        ordem_original=idx,
                        numero_questao=numero,
                    )

            q_answers = by_q.get(str(question.id), [])
            for ans in q_answers:
                ok = _answer_is_correct(question, ans)
                st = Student.query.get(ans.student_id)
                if not st or not st.class_id or str(st.class_id) not in class_id_set:
                    continue
                cell = scope.class_to_cell.get(str(st.class_id))
                if not cell:
                    continue
                _eid, serie_id = cell
                b = agg_by_serie[serie_id][agg_key]
                _seed_question_agg_bucket(
                    b,
                    item_id=str(tid),
                    codigo=code,
                    descricao=desc,
                    disciplina=disciplina,
                    ordem_original=idx,
                    numero_questao=numero,
                )
                b["total"] += 1
                if ok:
                    b["acertos"] += 1
                b["itens_origem"].add(str(tid))
                if disciplina in all_disciplines:
                    bd = agg_by_serie_disc[serie_id][disciplina][agg_key]
                    _seed_question_agg_bucket(
                        bd,
                        item_id=str(tid),
                        codigo=code,
                        descricao=desc,
                        disciplina=disciplina,
                        ordem_original=idx,
                        numero_questao=numero,
                    )
                    bd["total"] += 1
                    if ok:
                        bd["acertos"] += 1
                    bd["itens_origem"].add(str(tid))
                for dk in (None, disciplina if disciplina in all_disciplines else None):
                    if dk is None or dk in all_disciplines:
                        ct = cell_totals[dk][cell]
                        ct[1] += 1
                        if ok:
                            ct[0] += 1

    return dict(agg_by_serie), dict(agg_by_serie_disc), dict(cell_totals)


def _digital_acertos_data(
    ctx: ConsolidatedScopeContext,
    tests_by_id: Dict[str, Test],
    test_ids: List[str],
    class_ids_linhas: List[Any],
    class_ids_rede: List[Any],
    all_disciplines: Set[str],
) -> Dict[str, Any]:
    agg_by_serie_l, agg_by_serie_disc_l, totals_l = _digital_acertos_aggregate(
        ctx.scope_linhas, tests_by_id, test_ids, class_ids_linhas, all_disciplines
    )
    if ctx.comparativo_municipio:
        _, _, totals_r = _digital_acertos_aggregate(
            ctx.scope_rede, tests_by_id, test_ids, class_ids_rede, all_disciplines
        )
    else:
        totals_r = totals_l

    mk = _matriz_kwargs(ctx)

    def _matriz_for(discipline: Optional[str]) -> Dict[str, Any]:
        totals_d = totals_l.get(discipline, {})

        def _cell(e: str, s: str) -> Optional[float]:
            if (e, s) not in ctx.scope_linhas.classes_by_cell:
                return None
            pair = totals_d.get((e, s))
            if not pair or pair[1] == 0:
                return None
            return round_to_two_decimals(100.0 * pair[0] / pair[1])

        kw = dict(mk)
        if ctx.comparativo_municipio:
            totals_rd = totals_r.get(discipline, {})

            def _cell_rede(e: str, s: str) -> Optional[float]:
                if (e, s) not in ctx.scope_rede.classes_by_cell:
                    return None
                pair = totals_rd.get((e, s))
                if not pair or pair[1] == 0:
                    return None
                return round_to_two_decimals(100.0 * pair[0] / pair[1])

            kw["cell_fn_rede"] = _cell_rede
        return _build_numeric_matriz(ctx.scope_linhas, _cell, **kw)

    por_disc = {
        d: {
            "matriz": _matriz_for(d),
            "por_serie": _habilidades_por_serie_for_discipline(ctx.series_colunas, agg_by_serie_disc_l, d),
        }
        for d in sorted(all_disciplines)
    }
    return {
        GERAL_KEY: {
            "matriz": _matriz_for(None),
            "por_serie": _habilidades_por_serie_blocks(ctx.series_colunas, agg_by_serie_l),
        },
        "por_disciplina": por_disc,
    }


def _answer_sheet_acertos_aggregate(
    scope: ScopeIndex,
    gabs_by_id: Dict[str, AnswerSheetGabarito],
    gabarito_ids: List[str],
    results: List[AnswerSheetResult],
    all_disciplines: Set[str],
) -> Tuple[
    Dict[str, Dict[str, Dict[str, Any]]],
    Dict[str, Dict[str, Dict[str, Dict[str, Any]]]],
    Dict[Optional[str], Dict[Tuple[str, str], List[int]]],
]:
    from app.report_analysis.answer_sheet_report_builder import (
        _fetch_skill_code_description_by_ids,
        _norm_skill_uuid_key,
    )

    agg_by_serie: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(
        lambda: defaultdict(
            lambda: {
                "acertos": 0,
                "total": 0,
                "codigo": "",
                "descricao": "",
                "disciplina": "",
                "ordem_original": None,
                "numero_questao": None,
                "itens_origem": set(),
            }
        )
    )
    agg_by_serie_disc: Dict[str, Dict[str, Dict[str, Dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(
            lambda: defaultdict(
                lambda: {
                    "acertos": 0,
                    "total": 0,
                    "codigo": "",
                    "descricao": "",
                    "disciplina": "",
                    "ordem_original": None,
                    "numero_questao": None,
                    "itens_origem": set(),
                }
            )
        )
    )
    cell_totals: Dict[Optional[str], Dict[Tuple[str, str], List[int]]] = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    series_by_item = _series_ids_by_item(scope)

    for gid in gabarito_ids:
        gab = gabs_by_id.get(str(gid))
        if not gab:
            continue
        q_skills = question_skills_map_for_answer_sheet(gab)
        correct_json = gab.correct_answers or {}
        if isinstance(correct_json, str):
            import json

            correct_json = json.loads(correct_json) or {}
        gab_map: Dict[int, str] = {}
        for k, v in (correct_json or {}).items():
            try:
                gab_map[int(k)] = str(v).upper() if v else ""
            except (TypeError, ValueError):
                continue
        skill_ids = [str(s) for sids in q_skills.values() for s in sids if s]
        code_map = _fetch_skill_code_description_by_ids(list(dict.fromkeys(skill_ids)))
        cfg = gab.blocks_config or {}
        subject_by_q: Dict[int, str] = {}
        for block in (cfg.get("topology") or {}).get("blocks") or []:
            subj = (block.get("subject_name") or "").strip() or "Disciplina Geral"
            for q in block.get("questions") or []:
                raw = q.get("q") if q.get("q") is not None else q.get("numero")
                if raw is None:
                    continue
                try:
                    subject_by_q[int(raw)] = subj
                except (TypeError, ValueError):
                    pass

        serie_ids = series_by_item.get(str(gid), set())

        def _meta_for_qn(qn: int) -> Tuple[str, str, str]:
            disciplina = subject_by_q.get(qn, "Disciplina Geral")
            sids = q_skills.get(qn) or []
            first = str(sids[0]).strip() if sids else ""
            nk = _norm_skill_uuid_key(first) if first else ""
            code, desc = code_map.get(nk, (None, None)) if first else (None, None)
            code_out = (code or "").strip() or (first if first else f"Q{qn}")
            desc_out = (desc or "").strip() or f"Questão {qn}"
            return code_out, desc_out, disciplina

        for qn in sorted(gab_map.keys()):
            code_out, desc_out, disciplina = _meta_for_qn(qn)
            agg_key = _question_agg_key(str(gid), str(qn))
            for serie_id in serie_ids:
                _seed_question_agg_bucket(
                    agg_by_serie[serie_id][agg_key],
                    item_id=str(gid),
                    codigo=code_out,
                    descricao=desc_out,
                    disciplina=disciplina,
                    ordem_original=qn,
                    numero_questao=qn,
                )
                if disciplina in all_disciplines:
                    _seed_question_agg_bucket(
                        agg_by_serie_disc[serie_id][disciplina][agg_key],
                        item_id=str(gid),
                        codigo=code_out,
                        descricao=desc_out,
                        disciplina=disciplina,
                        ordem_original=qn,
                        numero_questao=qn,
                    )

        for res in [r for r in results if str(r.gabarito_id) == str(gid)]:
            st = res.student
            if not st or not st.class_id:
                continue
            cell = scope.class_to_cell.get(str(st.class_id))
            if not cell:
                continue
            _eid, serie_id = cell
            detected = res.detected_answers or {}
            for qn, ca in gab_map.items():
                code_out, desc_out, disciplina = _meta_for_qn(qn)
                agg_key = _question_agg_key(str(gid), str(qn))
                raw = detected.get(str(qn), detected.get(qn))
                st_ans = str(raw).upper() if raw else ""
                ok = bool(ca and st_ans and st_ans == ca)
                b = agg_by_serie[serie_id][agg_key]
                _seed_question_agg_bucket(
                    b,
                    item_id=str(gid),
                    codigo=code_out,
                    descricao=desc_out,
                    disciplina=disciplina,
                    ordem_original=qn,
                    numero_questao=qn,
                )
                b["total"] += 1
                if ok:
                    b["acertos"] += 1
                b["itens_origem"].add(str(gid))
                if disciplina in all_disciplines:
                    bd = agg_by_serie_disc[serie_id][disciplina][agg_key]
                    _seed_question_agg_bucket(
                        bd,
                        item_id=str(gid),
                        codigo=code_out,
                        descricao=desc_out,
                        disciplina=disciplina,
                        ordem_original=qn,
                        numero_questao=qn,
                    )
                    bd["total"] += 1
                    if ok:
                        bd["acertos"] += 1
                    bd["itens_origem"].add(str(gid))
                for dk in (None, disciplina if disciplina in all_disciplines else None):
                    if dk is None or dk in all_disciplines:
                        ct = cell_totals[dk][cell]
                        ct[1] += 1
                        if ok:
                            ct[0] += 1

    return dict(agg_by_serie), dict(agg_by_serie_disc), dict(cell_totals)


def _answer_sheet_acertos_data(
    ctx: ConsolidatedScopeContext,
    gabs_by_id: Dict[str, AnswerSheetGabarito],
    gabarito_ids: List[str],
    results_linhas: List[AnswerSheetResult],
    results_rede: List[AnswerSheetResult],
    all_disciplines: Set[str],
) -> Dict[str, Any]:
    agg_by_serie_l, agg_by_serie_disc_l, totals_l = _answer_sheet_acertos_aggregate(
        ctx.scope_linhas, gabs_by_id, gabarito_ids, results_linhas, all_disciplines
    )
    if ctx.comparativo_municipio:
        _, _, totals_r = _answer_sheet_acertos_aggregate(
            ctx.scope_rede, gabs_by_id, gabarito_ids, results_rede, all_disciplines
        )
    else:
        totals_r = totals_l

    mk = _matriz_kwargs(ctx)

    def _matriz_for(discipline: Optional[str]) -> Dict[str, Any]:
        totals_d = totals_l.get(discipline, {})

        def _cell(e: str, s: str) -> Optional[float]:
            if (e, s) not in ctx.scope_linhas.classes_by_cell:
                return None
            pair = totals_d.get((e, s))
            if not pair or pair[1] == 0:
                return None
            return round_to_two_decimals(100.0 * pair[0] / pair[1])

        kw = dict(mk)
        if ctx.comparativo_municipio:
            totals_rd = totals_r.get(discipline, {})

            def _cell_rede(e: str, s: str) -> Optional[float]:
                if (e, s) not in ctx.scope_rede.classes_by_cell:
                    return None
                pair = totals_rd.get((e, s))
                if not pair or pair[1] == 0:
                    return None
                return round_to_two_decimals(100.0 * pair[0] / pair[1])

            kw["cell_fn_rede"] = _cell_rede
        return _build_numeric_matriz(ctx.scope_linhas, _cell, **kw)

    por_disc = {
        d: {
            "matriz": _matriz_for(d),
            "por_serie": _habilidades_por_serie_for_discipline(ctx.series_colunas, agg_by_serie_disc_l, d),
        }
        for d in sorted(all_disciplines)
    }
    return {
        GERAL_KEY: {
            "matriz": _matriz_for(None),
            "por_serie": _habilidades_por_serie_blocks(ctx.series_colunas, agg_by_serie_l),
        },
        "por_disciplina": por_disc,
    }


# ---------------------------------------------------------------------------
# Rótulos de faixa/curso (títulos narrativos do relatório)
# ---------------------------------------------------------------------------


def _build_intervalo_from_series_colunas(series_colunas: List[Dict[str, str]]) -> Optional[str]:
    nomes = [
        str(col.get("serie_nome") or "").strip()
        for col in (series_colunas or [])
        if str(col.get("serie_nome") or "").strip()
    ]
    if not nomes:
        return None
    if len(nomes) == 1:
        return nomes[0]
    return ", ".join(nomes)


def _unique_curso_nome_from_itens(itens_selecionados: List[Dict[str, Any]]) -> Optional[str]:
    nomes: Set[str] = set()
    for item in itens_selecionados or []:
        for key in ("curso_nome", "curso"):
            raw = item.get(key)
            if not raw or not str(raw).strip():
                continue
            text = str(raw).strip()
            # Ignora UUID em curso legado; curso_nome sempre é legível.
            if key == "curso" and _looks_like_uuid(text):
                continue
            nomes.add(text)
            break
    if len(nomes) == 1:
        return next(iter(nomes))
    return None


def _looks_like_uuid(value: str) -> bool:
    import re

    return bool(
        re.match(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            value,
            re.I,
        )
    )


def _build_faixa_avaliacao(
    itens_selecionados: List[Dict[str, Any]],
    series_colunas: List[Dict[str, str]],
) -> Optional[Dict[str, str]]:
    curso = _unique_curso_nome_from_itens(itens_selecionados)
    intervalo = _build_intervalo_from_series_colunas(series_colunas)
    if curso and intervalo:
        return {"titulo": f"{curso} ({intervalo})"}
    if intervalo:
        return {"titulo": intervalo}
    if curso:
        return {"titulo": curso}
    return None


def _digital_item_selecionado(test: Test) -> Dict[str, Any]:
    return {
        "id": str(test.id),
        "titulo": test.title,
        "disciplinas": sorted(_disciplinas_from_test(test)),
        "curso": test.course,
        "curso_nome": _obter_nome_curso(test),
    }


def _answer_sheet_item_selecionado(gab: AnswerSheetGabarito) -> Dict[str, Any]:
    from app.services.cartao_resposta.proficiency_by_subject import (
        course_name_and_has_matematica_for_gabarito,
    )

    course_name, _ = course_name_and_has_matematica_for_gabarito(str(gab.id))
    return {
        "id": str(gab.id),
        "titulo": gab.title,
        "disciplinas": sorted(_disciplinas_from_gabarito(gab)),
        "serie": gab.grade_name,
        "curso_nome": course_name,
    }


# ---------------------------------------------------------------------------
# Payload completo
# ---------------------------------------------------------------------------


def _assemble_payload(
    *,
    tipo_entidade: str,
    filtros: Dict[str, Any],
    itens_selecionados: List[Dict[str, Any]],
    discipline_list: List[str],
    ctx: ConsolidatedScopeContext,
    series_aplicadas: List[Dict[str, Any]],
    consolidado_frequencia: Dict[str, Any],
    consolidado_medias_nota: Dict[str, Any],
    consolidado_medias_proficiencia: Dict[str, Any],
    acertos_por_habilidade: Dict[str, Any],
    distribuicao_niveis_proficiencia: Dict[str, Any],
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "tipo_entidade": tipo_entidade,
        "filtros": filtros,
        "itens_selecionados": itens_selecionados,
        "disciplinas_disponiveis": discipline_list,
        "series_colunas": ctx.series_colunas,
        "series_aplicadas": series_aplicadas,
        "consolidado_frequencia": consolidado_frequencia,
        "consideracoes_gerais": {
            "consolidado_medias_nota": consolidado_medias_nota,
            "consolidado_medias_proficiencia": consolidado_medias_proficiencia,
            "acertos_por_habilidade": acertos_por_habilidade,
        },
        "distribuicao_niveis_proficiencia": distribuicao_niveis_proficiencia,
    }
    faixa = _build_faixa_avaliacao(itens_selecionados, ctx.series_colunas)
    if faixa:
        payload["faixa_avaliacao"] = faixa
    if ctx.comparativo_municipio:
        payload["comparativo"] = {
            "ativo": True,
            "referencia_rede": "municipio",
            "escola_id": ctx.escola_id,
        }
    return payload


def _empty_ctx() -> ConsolidatedScopeContext:
    empty_scope = ScopeIndex([], [], {}, {}, {})
    return ConsolidatedScopeContext(
        scope_linhas=empty_scope,
        scope_rede=empty_scope,
        series_colunas=[],
        comparativo_municipio=False,
    )


def _empty_matriz_section() -> Dict[str, Any]:
    return {GERAL_KEY: _empty_matriz(), "por_disciplina": {}}


def _empty_acertos_section() -> Dict[str, Any]:
    return {
        GERAL_KEY: {"matriz": _empty_matriz(), "por_serie": []},
        "por_disciplina": {},
    }


def _empty_distribuicao_section() -> Dict[str, Any]:
    return {
        GERAL_KEY: {
            "linhas": [],
            "medias_da_rede": {
                "por_serie": [],
                "taxa_geral": {
                    "percentuais": {k: 0.0 for k in FAIXAS},
                    "contagens": _empty_distribution(),
                    "total_registros": 0,
                },
                "media_da_rede_nivel": None,
            },
        },
        "por_disciplina": {},
    }


def _empty_payload(
    tipo_entidade: str,
    filtros: Dict[str, Any],
    itens: List[Dict[str, Any]],
) -> Dict[str, Any]:
    return _assemble_payload(
        tipo_entidade=tipo_entidade,
        filtros=filtros,
        itens_selecionados=itens,
        discipline_list=[GERAL_KEY],
        ctx=_empty_ctx(),
        series_aplicadas=[],
        consolidado_frequencia=_empty_matriz_section(),
        consolidado_medias_nota=_empty_matriz_section(),
        consolidado_medias_proficiencia=_empty_matriz_section(),
        acertos_por_habilidade=_empty_acertos_section(),
        distribuicao_niveis_proficiencia=_empty_distribuicao_section(),
    )


# ---------------------------------------------------------------------------
# Digital
# ---------------------------------------------------------------------------


def _fetch_digital_class_tests(
    test_ids: List[str],
    municipio_id: str,
    escola_id: Optional[str],
    restrict_class_ids: Optional[Set[Any]],
) -> List[ClassTest]:
    q = (
        ClassTest.query.filter(ClassTest.test_id.in_([str(t) for t in test_ids]))
        .join(Class, ClassTest.class_id == Class.id)
        .join(School, cast(Class._school_id, VARCHAR) == cast(School.id, VARCHAR))
        .filter(School.city_id == municipio_id)
    )
    if escola_id:
        q = q.filter(School.id == escola_id)
    if restrict_class_ids is not None:
        if not restrict_class_ids:
            return []
        q = q.filter(ClassTest.class_id.in_(list(restrict_class_ids)))
    return q.options(joinedload(ClassTest.class_).joinedload(Class.grade)).all()


def _students_by_class_for_digital(
    test_ids: List[str],
    escopo: Dict[str, Any],
    class_ids: List[Any],
) -> Dict[str, List[Student]]:
    base_students = Student.query.filter(Student.class_id.in_(class_ids)).all()
    base_ids = {str(s.id) for s in base_students}
    merged_ids = merge_participant_student_ids([str(t) for t in test_ids], escopo, class_ids, base_ids)
    all_students = (
        Student.query.options(joinedload(Student.class_).joinedload(Class.grade))
        .filter(Student.id.in_(merged_ids))
        .all()
        if merged_ids
        else []
    )
    students_by_class: Dict[str, List[Student]] = defaultdict(list)
    for st in all_students:
        if st.class_id:
            students_by_class[str(st.class_id)].append(st)
    return students_by_class


def _digital_results_for_scope(
    test_ids: List[str],
    escopo: Dict[str, Any],
    class_ids: List[Any],
) -> List[EvaluationResult]:
    base_students = Student.query.filter(Student.class_id.in_(class_ids)).all()
    base_ids = {str(s.id) for s in base_students}
    return _dedupe_digital_by_test_student(
        query_evaluation_results_for_stats([str(t) for t in test_ids], escopo, class_ids, list(base_ids)).all()
    )


def build_digital_consolidated_report(
    municipio_id: str,
    escola_param: Optional[str],
    test_ids: List[str],
    user: dict,
    permissao: dict,
) -> Dict[str, Any]:
    city = City.query.get(municipio_id)
    if not city:
        raise ValueError("Município não encontrado.")
    if permissao.get("scope") != "all" and str(user.get("city_id")) != str(city.id):
        raise PermissionError("Acesso negado a este município.")

    escola_id = str(escola_param).strip() if _escola_eh_especifica(escola_param) else None
    filtros = {
        "municipio_id": municipio_id,
        "municipio_nome": city.name,
        "escola": escola_param or "all",
        "avaliacao_ids": [str(t) for t in test_ids],
    }
    restrict = _professor_restrict_class_ids(user)
    if restrict is not None and not restrict:
        return _empty_payload("avaliacao", filtros, [])

    tests = Test.query.filter(Test.id.in_([str(t) for t in test_ids])).all()
    found = {str(t.id) for t in tests}
    missing = [t for t in test_ids if str(t) not in found]
    if missing:
        raise ValueError(f"Avaliações não encontradas: {', '.join(missing)}")
    tests_by_id = {str(t.id): t for t in tests}
    itens = [_digital_item_selecionado(t) for t in tests]

    class_tests_linhas = _fetch_digital_class_tests(test_ids, municipio_id, escola_id, restrict)
    if not class_tests_linhas:
        return _empty_payload("avaliacao", filtros, itens)

    escopo_linhas = _build_escopo_calculo(municipio_id, escola_id)
    if restrict is not None:
        escopo_linhas["restrict_class_ids"] = restrict

    class_ids_linhas = list({ct.class_id for ct in class_tests_linhas})
    students_linhas = _students_by_class_for_digital(test_ids, escopo_linhas, class_ids_linhas)
    item_by_class_linhas = {str(ct.class_id): str(ct.test_id) for ct in class_tests_linhas}
    classes_linhas = [ct.class_ for ct in class_tests_linhas if ct.class_]
    scope_linhas = _build_scope_index(classes_linhas, students_linhas, item_by_class_linhas)
    results_linhas = _digital_results_for_scope(test_ids, escopo_linhas, class_ids_linhas)

    if escola_id:
        class_tests_rede = _fetch_digital_class_tests(test_ids, municipio_id, None, restrict)
        escopo_rede = _build_escopo_calculo(municipio_id, None)
        if restrict is not None:
            escopo_rede["restrict_class_ids"] = restrict
        class_ids_rede = list({ct.class_id for ct in class_tests_rede})
        students_rede = _students_by_class_for_digital(test_ids, escopo_rede, class_ids_rede)
        item_by_class_rede = {str(ct.class_id): str(ct.test_id) for ct in class_tests_rede}
        classes_rede = [ct.class_ for ct in class_tests_rede if ct.class_]
        scope_rede = _build_scope_index(classes_rede, students_rede, item_by_class_rede)
        results_rede = _digital_results_for_scope(test_ids, escopo_rede, class_ids_rede)
        ctx = _scope_context_dual(scope_linhas, scope_rede, escola_id)
        series_aplicadas = _build_series_aplicadas(scope_rede.series_items)
    else:
        ctx = _scope_context_from_single(scope_linhas)
        scope_rede = scope_linhas
        class_ids_rede = class_ids_linhas
        results_rede = results_linhas
        series_aplicadas = _build_series_aplicadas(scope_linhas.series_items)

    all_disciplines: Set[str] = set()
    for t in tests:
        all_disciplines |= _disciplinas_from_test(t)
    discipline_list = sorted(all_disciplines) + [GERAL_KEY]
    course_name = _obter_nome_curso(tests[0]) if tests else "Anos Iniciais"
    has_mat = any("matem" in d.lower() for d in all_disciplines)

    return _assemble_payload(
        tipo_entidade="avaliacao",
        filtros=filtros,
        itens_selecionados=itens,
        discipline_list=discipline_list,
        ctx=ctx,
        series_aplicadas=series_aplicadas,
        consolidado_frequencia=_build_frequencia_section_digital(
            ctx, results_linhas, results_rede, tests_by_id, all_disciplines
        ),
        consolidado_medias_nota=_build_medias_section_digital(
            ctx, results_linhas, results_rede, tests_by_id, all_disciplines, "grade",
            course_name=course_name, has_matematica=has_mat,
        ),
        consolidado_medias_proficiencia=_build_medias_section_digital(
            ctx, results_linhas, results_rede, tests_by_id, all_disciplines, "proficiency",
            course_name=course_name, has_matematica=has_mat,
        ),
        acertos_por_habilidade=_digital_acertos_data(
            ctx, tests_by_id, test_ids, class_ids_linhas, class_ids_rede, all_disciplines
        ),
        distribuicao_niveis_proficiencia=_build_distribuicao_section_digital(
            ctx, results_linhas, results_rede, tests_by_id, all_disciplines, course_name, has_mat
        ),
    )


# ---------------------------------------------------------------------------
# Cartão resposta
# ---------------------------------------------------------------------------


def _fetch_answer_sheet_scope(
    gabarito_ids: List[str],
    municipio_id: str,
    escola_id: Optional[str],
    user: dict,
    permissao: dict,
) -> Tuple[List[AnswerSheetGabarito], List[Class], Dict[str, List[Class]]]:
    gabs = AnswerSheetGabarito.query.filter(AnswerSheetGabarito.id.in_([str(g) for g in gabarito_ids])).all()
    classes_by_gab: Dict[str, List[Class]] = {}
    all_classes: List[Class] = []
    seen: Set[str] = set()
    for gab in gabs:
        classes = answer_sheet_target_classes_visible_for_user(gab, user, permissao, municipio_id)
        if escola_id:
            classes = [c for c in classes if str(c.school_id) == str(escola_id)]
        classes_by_gab[str(gab.id)] = classes
        for c in classes:
            if str(c.id) not in seen:
                seen.add(str(c.id))
                all_classes.append(c)
    return gabs, all_classes, classes_by_gab


def _answer_sheet_results_for_classes(gabarito_ids: List[str], class_ids: List[Any]) -> List[AnswerSheetResult]:
    if not class_ids:
        return []
    from app.services.answer_sheet_result_snapshot import (
        query_answer_sheet_results_for_class_group,
    )

    out: List[AnswerSheetResult] = []
    base_ids = [
        s.id
        for s in Student.query.filter(Student.class_id.in_(class_ids)).all()
    ]
    for gid in gabarito_ids:
        out.extend(
            query_answer_sheet_results_for_class_group(str(gid), class_ids, base_ids)
            .options(
                joinedload(AnswerSheetResult.student)
                .joinedload(Student.class_)
                .joinedload(Class.grade)
            )
            .all()
        )
    return _dedupe_answer_sheet_by_gabarito_student(out)


def build_answer_sheet_consolidated_report(
    municipio_id: str,
    escola_param: Optional[str],
    gabarito_ids: List[str],
    user: dict,
    permissao: dict,
) -> Dict[str, Any]:
    city = City.query.get(municipio_id)
    if not city:
        raise ValueError("Município não encontrado.")
    if permissao.get("scope") != "all" and str(user.get("city_id")) != str(city.id):
        raise PermissionError("Acesso negado a este município.")

    escola_id = str(escola_param).strip() if _escola_eh_especifica(escola_param) else None
    filtros = {
        "municipio_id": municipio_id,
        "municipio_nome": city.name,
        "escola": escola_param or "all",
        "gabarito_ids": [str(g) for g in gabarito_ids],
    }

    gabs_linhas, all_classes_linhas, classes_by_gab_linhas = _fetch_answer_sheet_scope(
        gabarito_ids, municipio_id, escola_id, user, permissao
    )
    found = {str(g.id) for g in gabs_linhas}
    missing = [g for g in gabarito_ids if str(g) not in found]
    if missing:
        raise ValueError(f"Gabaritos não encontrados: {', '.join(missing)}")
    gabs_by_id = {str(g.id): g for g in gabs_linhas}
    itens = [_answer_sheet_item_selecionado(g) for g in gabs_linhas]

    if not all_classes_linhas:
        return _empty_payload("cartao_resposta", filtros, itens)

    class_ids_linhas = [c.id for c in all_classes_linhas]
    students_linhas: Dict[str, List[Student]] = defaultdict(list)
    for st in Student.query.filter(Student.class_id.in_(class_ids_linhas)).all():
        if st.class_id:
            students_linhas[str(st.class_id)].append(st)

    item_by_class_linhas: Dict[str, str] = {}
    for gid, cls_list in classes_by_gab_linhas.items():
        for c in cls_list:
            item_by_class_linhas[str(c.id)] = str(gid)

    scope_linhas = _build_scope_index(all_classes_linhas, students_linhas, item_by_class_linhas)
    results_linhas = _answer_sheet_results_for_classes(gabarito_ids, class_ids_linhas)

    if escola_id:
        _gabs_rede, all_classes_rede, classes_by_gab_rede = _fetch_answer_sheet_scope(
            gabarito_ids, municipio_id, None, user, permissao
        )
        class_ids_rede = [c.id for c in all_classes_rede]
        students_rede: Dict[str, List[Student]] = defaultdict(list)
        for st in Student.query.filter(Student.class_id.in_(class_ids_rede)).all():
            if st.class_id:
                students_rede[str(st.class_id)].append(st)
        item_by_class_rede: Dict[str, str] = {}
        for gid, cls_list in classes_by_gab_rede.items():
            for c in cls_list:
                item_by_class_rede[str(c.id)] = str(gid)
        scope_rede = _build_scope_index(all_classes_rede, students_rede, item_by_class_rede)
        results_rede = _answer_sheet_results_for_classes(gabarito_ids, class_ids_rede)
        ctx = _scope_context_dual(scope_linhas, scope_rede, escola_id)
        series_aplicadas = _build_series_aplicadas(scope_rede.series_items)
    else:
        ctx = _scope_context_from_single(scope_linhas)
        class_ids_rede = class_ids_linhas
        results_rede = results_linhas
        series_aplicadas = _build_series_aplicadas(scope_linhas.series_items)

    all_disciplines: Set[str] = set()
    for g in gabs_linhas:
        all_disciplines |= _disciplinas_from_gabarito(g)
    discipline_list = sorted(all_disciplines) + [GERAL_KEY]

    from app.services.cartao_resposta.proficiency_by_subject import course_name_and_has_matematica_for_gabarito

    course_name, has_mat = course_name_and_has_matematica_for_gabarito(str(gabs_linhas[0].id))

    return _assemble_payload(
        tipo_entidade="cartao_resposta",
        filtros=filtros,
        itens_selecionados=itens,
        discipline_list=discipline_list,
        ctx=ctx,
        series_aplicadas=series_aplicadas,
        consolidado_frequencia=_build_frequencia_section_answer_sheet(
            ctx, results_linhas, results_rede, all_disciplines
        ),
        consolidado_medias_nota=_build_medias_section_answer_sheet(
            ctx, results_linhas, results_rede, all_disciplines, "grade",
            course_name=course_name, has_matematica=has_mat,
        ),
        consolidado_medias_proficiencia=_build_medias_section_answer_sheet(
            ctx, results_linhas, results_rede, all_disciplines, "proficiency",
            course_name=course_name, has_matematica=has_mat,
        ),
        acertos_por_habilidade=_answer_sheet_acertos_data(
            ctx, gabs_by_id, gabarito_ids, results_linhas, results_rede, all_disciplines
        ),
        distribuicao_niveis_proficiencia=_build_distribuicao_section_answer_sheet(
            ctx, results_linhas, results_rede, all_disciplines, course_name, has_mat
        ),
    )


# ---------------------------------------------------------------------------
# Opções de filtro
# ---------------------------------------------------------------------------


def _escolas_municipio_digital(municipio_id: str, user: dict, permissao: dict) -> List[Dict[str, Any]]:
    q = School.query.filter(School.city_id == municipio_id)
    if permissao.get("scope") == "escola":
        role = (user.get("role") or "").lower()
        if role in ("diretor", "coordenador"):
            from app.models.manager import Manager

            manager = Manager.query.filter_by(user_id=user["id"]).first()
            if manager and manager.school_id:
                q = q.filter(School.id == manager.school_id)
            else:
                return []
        elif role == "professor":
            from app.models.teacher import Teacher
            from app.models.teacherClass import TeacherClass

            teacher = Teacher.query.filter_by(user_id=user["id"]).first()
            if not teacher:
                return []
            tcs = TeacherClass.query.filter_by(teacher_id=teacher.id).all()
            sids = {
                str(c.school_id)
                for c in Class.query.filter(Class.id.in_([tc.class_id for tc in tcs])).all()
                if c.school_id
            }
            if not sids:
                return []
            q = q.filter(School.id.in_(list(sids)))
    return [{"id": str(s.id), "nome": s.name} for s in q.order_by(School.name).all()]


def _periodo_response_fields(periodo_iso: Optional[str]) -> Dict[str, Any]:
    if not periodo_iso:
        return {}
    label: Optional[str] = periodo_iso
    try:
        from app.routes.evaluation_results_routes import _formatar_periodo_br

        label = _formatar_periodo_br(periodo_iso)
    except Exception:
        pass
    return {"periodo": periodo_iso, "periodo_label": label}


def get_digital_filter_options(
    estado: Optional[str],
    municipio: Optional[str],
    escola: Optional[str],
    user: dict,
    permissao: dict,
    list_avaliacoes_fn,
    list_estados_fn,
    list_municipios_fn,
    *,
    periodo_iso: Optional[str] = None,
    periodo_bounds: Optional[Tuple[datetime, datetime]] = None,
) -> Dict[str, Any]:
    response: Dict[str, Any] = {"estados": list_estados_fn(user, permissao)}
    response.update(_periodo_response_fields(periodo_iso))
    if estado:
        response["municipios"] = list_municipios_fn(estado, user, permissao)
        if municipio:
            response["escolas"] = _escolas_municipio_digital(municipio, user, permissao)
            response["avaliacoes"] = list_avaliacoes_fn(
                municipio, user, permissao, escola or "all", periodo_bounds
            )
    return response


def get_answer_sheet_filter_options(
    estado: Optional[str],
    municipio: Optional[str],
    escola: Optional[str],
    user: dict,
    permissao: dict,
    list_estados_fn,
    list_municipios_fn,
    list_gabaritos_fn,
    *,
    periodo_iso: Optional[str] = None,
) -> Dict[str, Any]:
    response: Dict[str, Any] = {"estados": list_estados_fn(user, permissao)}
    response.update(_periodo_response_fields(periodo_iso))
    if estado:
        response["municipios"] = list_municipios_fn(estado, user, permissao)
        if municipio:
            response["escolas"] = _escolas_municipio_digital(municipio, user, permissao)
            response["gabaritos"] = list_gabaritos_fn(
                str(municipio).strip(), user, permissao, escola or "all"
            )
    return response
