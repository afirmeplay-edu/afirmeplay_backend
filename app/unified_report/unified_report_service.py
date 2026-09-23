# -*- coding: utf-8 -*-
"""
Relatório Unificado — junta resultados de avaliação (digital/cartão) com leitura.

Dependência explícita: este service chama FluencyResultsService._build_bundle
(método interno do Alfabetômetro) para obter níveis de leitura em lote e o
mesmo denominador de ICA (% LF / presentes) que o Afirme Ler. Não altera
_build_bundle nem o scoring; apenas consome o retorno.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy.orm import joinedload

from app.afirme_ler.scoring.levels import LEVEL_LF, nivel_label
from app.afirme_ler.services.fluency_results_service import (
    FluencyResultsService,
    evaluation_year,
)
from app.afirme_ler.services.parsing import EVALUATION_KIND_LABELS
from app.models.answerSheetGabarito import AnswerSheetGabarito
from app.models.answerSheetResult import AnswerSheetResult
from app.models.city import City
from app.models.evaluationResult import EvaluationResult
from app.models.grades import Grade
from app.models.school import School
from app.models.student import Student
from app.models.studentClass import Class
from app.models.subject import Subject
from app.models.test import Test
from app.participation_report.filters import (
    build_filter_options,
    parse_id_list,
)
from app.participation_report.services import _restrict_class_ids_for_user
from app.permissions import get_user_permission_scope
from app.utils.class_label_helpers import format_grade_class_label
from app.utils.decimal_helpers import round_to_two_decimals
from app.utils.tenant_middleware import city_id_to_schema_name, set_search_path

logger = logging.getLogger(__name__)

# Rótulos curtos do relatório unificado (não alterar EVALUATION_KIND_LABELS).
_LEITURA_EDICAO_ROTULO = {
    "entrada": "Leitura de Entrada",
    "formativa": "Leitura Formativa",
    "saida": "Leitura de Saída",
}


def _ensure_tenant_schema(municipio_id: str) -> None:
    set_search_path(city_id_to_schema_name(str(municipio_id).strip()))


def _assert_municipio(user: dict, municipio_id: str, permissao: dict) -> City:
    city = City.query.get(municipio_id)
    if not city:
        raise ValueError("Município não encontrado")
    if permissao.get("scope") != "all":
        user_city = str(user.get("city_id") or user.get("tenant_id") or "")
        if user_city != str(city.id):
            raise PermissionError("Sem permissão para este município")
    return city


def _multi(args, *keys: str) -> List[str]:
    values: List[str] = []
    for key in keys:
        values.append(args.get(key) if hasattr(args, "get") else None)
        getlist = getattr(args, "getlist", None)
        if callable(getlist):
            values.extend(getlist(key))
    return parse_id_list(*values)


def build_unified_filter_options(user: dict, args) -> Dict[str, Any]:
    """
    Hierarquia de filtros da avaliação (digital/cartão) + catálogo de leitura
    (ano / edição / avaliações de leitura), no mesmo formato do Alfabetômetro.
    """
    response = build_filter_options(user, args)

    municipio = (args.get("municipio") or "").strip()
    if not municipio:
        return response

    _ensure_tenant_schema(municipio)
    try:
        catalog = FluencyResultsService.catalog(user)
    except Exception:
        logger.exception("Falha ao carregar catálogo Afirme Ler para filtros unificados")
        catalog = {
            "anos": [],
            "edicoes": [
                {"id": kind, "label": label}
                for kind, label in EVALUATION_KIND_LABELS.items()
            ],
            "avaliacoes": [],
        }

    response["leitura"] = {
        "anos": catalog.get("anos") or [],
        "edicoes": catalog.get("edicoes") or [],
        "avaliacoes": catalog.get("avaliacoes") or [],
    }
    return response


def _resolve_class_ids(
    user: dict,
    permissao: dict,
    municipio_id: str,
    escola_ids: Optional[List[str]],
    serie_ids: Optional[List[str]],
    turma_ids: Optional[List[str]],
) -> List[Any]:
    """Turmas atuais do escopo (escola/série/turma), respeitando permissão de role."""
    query = Class.query.join(School, Class.school_id == School.id).filter(
        School.city_id == str(municipio_id)
    )
    if escola_ids:
        query = query.filter(Class.school_id.in_(escola_ids))
    if serie_ids:
        query = query.filter(Class.grade_id.in_(serie_ids))
    if turma_ids:
        query = query.filter(Class.id.in_(turma_ids))

    allowed = _restrict_class_ids_for_user(user, permissao)
    if allowed is not None:
        if not allowed:
            return []
        query = query.filter(Class.id.in_(list(allowed)))

    return [row.id for row in query.with_entities(Class.id).all()]


def _turma_label(student: Student, klass: Optional[Class], grade_names: Dict[str, str]) -> str:
    if klass is None and student.class_id:
        klass = Class.query.get(student.class_id)
    if klass is None:
        return "—"
    grade_name = ""
    if klass.grade_id:
        grade_name = grade_names.get(str(klass.grade_id), "")
        if not grade_name and getattr(klass, "grade", None):
            grade_name = klass.grade.name or ""
    return format_grade_class_label(grade_name, klass.name) or (klass.name or "—")


def _subject_list_digital(test: Test) -> List[Dict[str, Any]]:
    subjects: List[Dict[str, Any]] = []
    info = test.subjects_info
    if isinstance(info, list) and info:
        ids: List[str] = []
        for item in info:
            if isinstance(item, dict):
                sid = item.get("subject_id") or item.get("id")
                if sid:
                    ids.append(str(sid))
            elif item:
                ids.append(str(item))
        if ids:
            rows = Subject.query.filter(Subject.id.in_(ids)).all()
            by_id = {str(r.id): r for r in rows}
            for sid in ids:
                subj = by_id.get(sid)
                subjects.append(
                    {
                        "id": sid,
                        "nome": (subj.name if subj else None) or sid,
                    }
                )
            return subjects
    if test.subject:
        subj = Subject.query.get(test.subject)
        subjects.append(
            {
                "id": str(test.subject),
                "nome": (subj.name if subj else None) or str(test.subject),
            }
        )
    return subjects


def _subject_list_answer_sheet(gab: AnswerSheetGabarito) -> List[Dict[str, Any]]:
    subjects: List[Dict[str, Any]] = []
    seen: Set[str] = set()
    blocks = getattr(gab, "blocks", None) or []
    if isinstance(blocks, list):
        for block in blocks:
            if not isinstance(block, dict):
                continue
            sid = block.get("subject_id")
            if not sid or str(sid) in seen:
                continue
            seen.add(str(sid))
            name = (block.get("subject_name") or "").strip()
            if not name:
                subj = Subject.query.get(str(sid))
                name = (subj.name if subj else None) or str(sid)
            subjects.append({"id": str(sid), "nome": name})
    if subjects:
        return subjects
    # Fallback: deduzir de algum resultado
    sample = AnswerSheetResult.query.filter_by(gabarito_id=gab.id).first()
    pbs = (sample.proficiency_by_subject if sample else None) or {}
    if isinstance(pbs, dict):
        for sid, data in pbs.items():
            if str(sid).lower() == "geral":
                continue
            name = ""
            if isinstance(data, dict):
                name = (data.get("subject_name") or "").strip()
            subjects.append({"id": str(sid), "nome": name or str(sid)})
    return subjects


def _metric_cell(
    value: Any,
    *,
    is_classification: bool = False,
) -> Any:
    if value is None or value == "":
        return None
    if is_classification:
        return str(value)
    try:
        return round_to_two_decimals(float(value))
    except (TypeError, ValueError):
        return None


def _subject_payload_from_map(
    subject_map: Optional[dict],
    subject_ids: List[str],
) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    raw = subject_map if isinstance(subject_map, dict) else {}
    for sid in subject_ids:
        data = raw.get(sid) or raw.get(str(sid)) or {}
        if not isinstance(data, dict):
            data = {}
        out[sid] = {
            "proficiencia": _metric_cell(data.get("proficiency")),
            "nota": _metric_cell(data.get("grade")),
            "classificacao": _metric_cell(
                data.get("classification"), is_classification=True
            ),
        }
    return out


def _geral_payload(
    proficiency: Any,
    grade: Any,
    classification: Any,
) -> Dict[str, Any]:
    return {
        "proficiencia": _metric_cell(proficiency),
        "nota": _metric_cell(grade),
        "classificacao": _metric_cell(classification, is_classification=True),
    }


def _load_eval_results_digital(
    test_id: str, student_ids: List[str]
) -> Dict[str, EvaluationResult]:
    if not student_ids:
        return {}
    rows = EvaluationResult.query.filter(
        EvaluationResult.test_id == str(test_id),
        EvaluationResult.student_id.in_(student_ids),
    ).all()
    best: Dict[str, EvaluationResult] = {}
    for row in rows:
        prev = best.get(row.student_id)
        if prev is None:
            best[row.student_id] = row
            continue
        prev_ts = prev.calculated_at
        row_ts = row.calculated_at
        if row_ts and (not prev_ts or row_ts >= prev_ts):
            best[row.student_id] = row
        elif (row.proficiency or 0) >= (prev.proficiency or 0):
            best[row.student_id] = row
    return best


def _load_eval_results_answer_sheet(
    gabarito_id: str, student_ids: List[str]
) -> Dict[str, AnswerSheetResult]:
    if not student_ids:
        return {}
    rows = AnswerSheetResult.query.filter(
        AnswerSheetResult.gabarito_id == str(gabarito_id),
        AnswerSheetResult.student_id.in_(student_ids),
    ).all()
    best: Dict[str, AnswerSheetResult] = {}
    for row in rows:
        prev = best.get(row.student_id)
        if prev is None:
            best[row.student_id] = row
            continue
        prev_ts = prev.corrected_at
        row_ts = row.corrected_at
        if row_ts and (not prev_ts or row_ts >= prev_ts):
            best[row.student_id] = row
        elif (row.proficiency or 0) >= (prev.proficiency or 0):
            best[row.student_id] = row
    return best


def _reading_cut(city: City, escola_id: Optional[str], serie_id: Optional[str], turma_id: Optional[str]) -> dict:
    return {
        "rede_id": str(city.id),
        "municipio_id": str(city.id),
        "escola_id": str(escola_id) if escola_id else None,
        "serie_id": str(serie_id) if serie_id else None,
        "turma_id": str(turma_id) if turma_id else None,
        "estudante_id": None,
        "turno": None,
        "por": None,
        "item_id": None,
    }


def _build_reading_by_student(
    user: dict,
    city: City,
    avaliacao_leitura_id: str,
    escola_id: Optional[str],
    serie_id: Optional[str],
    turma_id: Optional[str],
) -> Tuple[Any, Dict[str, Any], dict]:
    """
    Obtém scores de leitura via FluencyResultsService._build_bundle
    (mesma base do Alfabetômetro para a avaliação de leitura selecionada).
    """
    selected, _visible = FluencyResultsService._require_evaluation(
        user, {"avaliacaoId": avaliacao_leitura_id}
    )
    ano = evaluation_year(selected)
    if not ano:
        raise ValueError("Não foi possível determinar o ano da avaliação de leitura.")
    edicao = selected.evaluation_kind
    cut = _reading_cut(city, escola_id, serie_id, turma_id)
    # Dependência: FluencyResultsService._build_bundle (interno do Alfabetômetro).
    # Não alterar a assinatura/comportamento — apenas consumir o retorno.
    bundle = FluencyResultsService._build_bundle(
        user, city, ano, edicao, [selected], cut
    )
    by_student: Dict[str, Any] = {}
    for row in bundle.get("rows") or []:
        student = row.get("student")
        if student is None:
            continue
        by_student[str(student.id)] = row.get("score")
    meta = {
        "id": selected.id,
        "titulo": selected.title,
        "ano": ano,
        "edicao": edicao,
        "edicaoLabel": EVALUATION_KIND_LABELS.get(edicao, edicao),
    }
    return bundle.get("aggregate"), by_student, meta


def build_unified_report(
    user: dict,
    *,
    estado: str,
    municipio_id: str,
    report_entity_type: str,
    avaliacao_id: str,
    avaliacao_leitura_id: str,
    escola_ids: Optional[List[str]] = None,
    serie_ids: Optional[List[str]] = None,
    turma_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    permissao = get_user_permission_scope(user)
    if not permissao.get("permitted"):
        raise PermissionError(permissao.get("error") or "Sem permissão")

    city = _assert_municipio(user, municipio_id, permissao)
    _ensure_tenant_schema(municipio_id)

    is_cartao = str(report_entity_type or "").strip().lower() == "answer_sheet"
    if not avaliacao_id:
        raise ValueError("Informe a avaliação (avaliacao)")
    if not avaliacao_leitura_id:
        raise ValueError("Informe a avaliação de leitura (avaliacao_leitura)")
    if not escola_ids and not turma_ids:
        raise ValueError("Informe ao menos escola ou turma para delimitar o universo de alunos")
    # Cut do Alfabetômetro aceita um id por nível; multi-select quebraria a paridade do ICA.
    if escola_ids and len(escola_ids) > 1:
        raise ValueError("Selecione apenas uma escola (paridade com o Alfabetômetro)")
    if serie_ids and len(serie_ids) > 1:
        raise ValueError("Selecione apenas uma série (paridade com o Alfabetômetro)")
    if turma_ids and len(turma_ids) > 1:
        raise ValueError("Selecione apenas uma turma (paridade com o Alfabetômetro)")

    class_ids = _resolve_class_ids(
        user, permissao, municipio_id, escola_ids, serie_ids, turma_ids
    )
    students = (
        Student.query.filter(Student.class_id.in_(class_ids))
        .options(joinedload(Student.class_).joinedload(Class.grade))
        .order_by(Student.name.asc())
        .all()
        if class_ids
        else []
    )
    student_ids = [str(s.id) for s in students]

    grade_ids = {
        str(s.class_.grade_id)
        for s in students
        if s.class_ and s.class_.grade_id
    }
    grade_names = {
        str(g.id): (g.name or "")
        for g in (
            Grade.query.filter(Grade.id.in_(list(grade_ids))).all() if grade_ids else []
        )
    }

    # --- Avaliação (digital ou cartão) ---
    if is_cartao:
        gab = AnswerSheetGabarito.query.get(str(avaliacao_id))
        if not gab:
            raise LookupError("Gabarito não encontrado")
        eval_title = gab.title or "Cartão-resposta"
        disciplinas = _subject_list_answer_sheet(gab)
        results_map = _load_eval_results_answer_sheet(str(avaliacao_id), student_ids)
        entity_type = "answer_sheet"
    else:
        test = Test.query.get(str(avaliacao_id))
        if not test:
            raise LookupError("Avaliação não encontrada")
        eval_title = test.title or "Avaliação"
        disciplinas = _subject_list_digital(test)
        results_map = _load_eval_results_digital(str(avaliacao_id), student_ids)
        entity_type = "digital"

    subject_ids = [d["id"] for d in disciplinas]

    # Escopo de leitura alinhado ao Alfabetômetro (um id de escola/série/turma)
    escola_cut = escola_ids[0] if escola_ids and len(escola_ids) == 1 else None
    serie_cut = serie_ids[0] if serie_ids and len(serie_ids) == 1 else None
    turma_cut = turma_ids[0] if turma_ids and len(turma_ids) == 1 else None

    aggregate, reading_by_student, leitura_meta = _build_reading_by_student(
        user,
        city,
        str(avaliacao_leitura_id),
        escola_cut,
        serie_cut,
        turma_cut,
    )

    rotulo_leitura = _LEITURA_EDICAO_ROTULO.get(
        leitura_meta["edicao"],
        f"Leitura {leitura_meta.get('edicaoLabel') or leitura_meta['edicao']}",
    )
    rotulo_combinado = f"{eval_title} · {rotulo_leitura}"

    alunos_payload: List[Dict[str, Any]] = []
    alunos_com_leitura = 0
    alunos_lf = 0
    alunos_sem_leitura = 0

    for student in students:
        sid = str(student.id)
        klass = student.class_
        result = results_map.get(sid) or results_map.get(student.id)
        sem_prova = result is None

        if is_cartao:
            subject_map = getattr(result, "proficiency_by_subject", None) if result else None
            geral = (
                _geral_payload(result.proficiency, result.grade, result.classification)
                if result
                else _geral_payload(None, None, None)
            )
        else:
            subject_map = getattr(result, "subject_results", None) if result else None
            geral = (
                _geral_payload(result.proficiency, result.grade, result.classification)
                if result
                else _geral_payload(None, None, None)
            )

        por_disciplina = _subject_payload_from_map(subject_map, subject_ids)
        if sem_prova:
            for sid_disc in subject_ids:
                por_disciplina[sid_disc] = {
                    "proficiencia": None,
                    "nota": None,
                    "classificacao": None,
                }

        score = reading_by_student.get(sid)
        # Idêntico ao Alfabetômetro: avaliado = presente (status finalizada → presente).
        # ausente / em_andamento / pendente / sem sessão → sem leitura.
        tem_leitura = bool(score and getattr(score, "avaliado", False))
        if tem_leitura:
            alunos_com_leitura += 1
            nivel = score.nivel
            nivel_lbl = score.nivel_label or nivel_label(nivel)
            alfabetizado = nivel == LEVEL_LF
            if alfabetizado:
                alunos_lf += 1
            sem_leitura_flag = False
        else:
            nivel = None
            nivel_lbl = None
            alfabetizado = None
            sem_leitura_flag = True
            alunos_sem_leitura += 1

        alunos_payload.append(
            {
                "id": sid,
                "nome": student.name or "",
                "turmaId": str(student.class_id) if student.class_id else None,
                "turmaNome": _turma_label(student, klass, grade_names),
                "escolaId": str(student.school_id) if student.school_id else None,
                "porDisciplina": por_disciplina,
                "geral": geral,
                "nivelLeitura": nivel,
                "nivelLeituraLabel": nivel_lbl,
                "alfabetizado": alfabetizado,
                "semProva": sem_prova,
                "semLeitura": sem_leitura_flag,
            }
        )

    total_alunos = len(alunos_payload)
    ica_pct_lf = (
        round_to_two_decimals(100.0 * alunos_lf / alunos_com_leitura)
        if alunos_com_leitura
        else 0.0
    )

    # Comparação silenciosa com o Alfabetômetro (mesmo cut / _build_bundle).
    if aggregate is not None:
        alf_pct = float(getattr(aggregate, "leitores_fluentes_pct", 0.0) or 0.0)
        if float(ica_pct_lf) != float(alf_pct):
            logger.warning(
                "Relatório Unificado: icaPctLf diverge do Alfabetômetro. "
                "icaPctLf=%s leitoresFluentesPct=%s recorte={municipio=%s escola=%s serie=%s turma=%s "
                "avaliacao_leitura=%s report_entity_type=%s avaliacao=%s totalLista=%s "
                "comLeituraLista=%s lfLista=%s avaliadosAlf=%s}",
                ica_pct_lf,
                alf_pct,
                municipio_id,
                escola_cut,
                serie_cut,
                turma_cut,
                avaliacao_leitura_id,
                entity_type,
                avaliacao_id,
                total_alunos,
                alunos_com_leitura,
                alunos_lf,
                int(getattr(aggregate, "avaliados", 0) or 0),
            )

    return {
        "metadados": {
            "rotuloCombinado": rotulo_combinado,
            "estado": estado,
            "municipioId": str(city.id),
            "municipioNome": city.name,
            "avaliacao": {
                "id": str(avaliacao_id),
                "titulo": eval_title,
                "reportEntityType": entity_type,
            },
            "leitura": leitura_meta,
            "escopo": {
                "escolas": escola_ids or [],
                "series": serie_ids or [],
                "turmas": turma_ids or [],
            },
        },
        "disciplinas": disciplinas,
        "resumo": {
            "totalAlunos": total_alunos,
            "alunosComLeitura": alunos_com_leitura,
            "alunosLf": alunos_lf,
            "icaPctLf": ica_pct_lf,
            "alunosSemLeitura": alunos_sem_leitura,
        },
        "alunos": alunos_payload,
    }
