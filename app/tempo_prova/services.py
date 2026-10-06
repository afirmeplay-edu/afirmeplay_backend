# -*- coding: utf-8 -*-
"""Montagem do Relatório de Tempo de Prova."""
from __future__ import annotations

from collections import defaultdict
from statistics import median
from typing import Any, Dict, List, Optional

from sqlalchemy import String, and_, cast, func, or_
from sqlalchemy.orm import joinedload

from app import db
from app.models.city import City
from app.models.classTest import ClassTest
from app.models.evaluationResult import EvaluationResult
from app.models.grades import Grade
from app.models.school import School
from app.models.student import Student
from app.models.studentClass import Class
from app.models.test import Test
from app.models.testQuestion import TestQuestion
from app.models.testSession import TestSession
from app.participation_report.filters import _filtros_avaliacao_permitida
from app.participation_report.services import (
    _fetch_class_tests,
    _placement_for_student,
)
from app.permissions import get_user_permission_scope
from app.report_analysis.evaluation_time import (
    ORIGEM_ESTIMADA_FALLBACK,
    ORIGEM_ESTIMADA_MOBILE,
    ORIGEM_MEDIDA,
    compute_session_time_metrics,
)
from app.utils.uuid_helpers import ensure_uuid_list

_MAX_ALUNOS_DETALHE = 400


def _mean(values: List[float]) -> Optional[float]:
    if not values:
        return None
    return round(sum(values) / len(values), 2)


def _median(values: List[float]) -> Optional[float]:
    if not values:
        return None
    return round(float(median(values)), 2)


def _question_counts_by_test(test_ids: List[str]) -> Dict[str, int]:
    if not test_ids:
        return {}
    rows = (
        db.session.query(TestQuestion.test_id, func.count(TestQuestion.id))
        .filter(TestQuestion.test_id.in_(test_ids))
        .group_by(TestQuestion.test_id)
        .all()
    )
    return {str(tid): int(n) for tid, n in rows}


def _names_maps(escola_ids, turma_ids, serie_ids, test_ids):
    escolas = {}
    if escola_ids:
        for row in School.query.with_entities(School.id, School.name).filter(
            School.id.in_(list(escola_ids))
        ).all():
            escolas[str(row[0])] = row[1] or ""

    turmas = {}
    if turma_ids:
        for row in Class.query.with_entities(Class.id, Class.name).filter(
            Class.id.in_(list(turma_ids))
        ).all():
            turmas[str(row[0])] = (row[1] or "").strip()

    series = {}
    if serie_ids:
        uuids = ensure_uuid_list([str(s) for s in serie_ids if s is not None])
        if uuids:
            for row in Grade.query.with_entities(Grade.id, Grade.name).filter(
                Grade.id.in_(uuids)
            ).all():
                series[str(row[0])] = row[1] or ""

    provas = {}
    if test_ids:
        for row in Test.query.with_entities(Test.id, Test.title).filter(
            Test.id.in_(list(test_ids))
        ).all():
            provas[str(row[0])] = row[1] or ""

    return escolas, turmas, series, provas


def _agg_bucket() -> Dict[str, Any]:
    return {
        "sessoes": 0,
        "tempos_total": [],
        "tempos_questao": [],
        "online": 0,
        "mobile": 0,
    }


def _finalize_bucket(bucket: Dict[str, Any], extra: Dict[str, Any]) -> Dict[str, Any]:
    tempos_q = bucket["tempos_questao"]
    tempos_t = bucket["tempos_total"]
    out = {
        **extra,
        "sessoes": bucket["sessoes"],
        "sessoes_online": bucket["online"],
        "sessoes_mobile": bucket["mobile"],
        "tempo_medio_segundos": _mean(tempos_t),
        "tempo_medio_por_questao_segundos": _mean(tempos_q),
        "tempo_mediano_por_questao_segundos": _median(tempos_q),
    }
    return out


def build_tempo_prova_report(
    user: dict,
    estado: str,
    municipio_id: str,
    avaliacao_ids: Optional[List[str]] = None,
    escola_ids: Optional[List[str]] = None,
    serie_ids: Optional[List[str]] = None,
    turma_ids: Optional[List[str]] = None,
    aluno_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    permissao = get_user_permission_scope(user)
    if not permissao.get("permitted"):
        raise PermissionError(permissao.get("error") or "Sem permissão")

    class_tests = _fetch_class_tests(
        municipio_id,
        user,
        permissao,
        avaliacao_ids=avaliacao_ids or None,
        escola_ids=escola_ids or None,
        serie_ids=serie_ids or None,
        turma_ids=turma_ids or None,
    )

    escopo = {
        "estado": estado,
        "municipio_id": str(municipio_id),
        "avaliacoes": list(avaliacao_ids or []),
        "escolas": list(escola_ids or []),
        "series": list(serie_ids or []),
        "turmas": [str(t) for t in (turma_ids or [])],
        "alunos": list(aluno_ids or []),
    }

    empty_metrics = {
        "sessoes": 0,
        "alunos": 0,
        "sessoes_online_medidas": 0,
        "sessoes_mobile_estimadas": 0,
        "sessoes_estimadas_fallback": 0,
        "tempo_medio_segundos": None,
        "tempo_medio_por_questao_segundos": None,
        "tempo_mediano_por_questao_segundos": None,
        "questoes_media": None,
    }

    if not class_tests:
        return {
            "escopo": escopo,
            "metricas": empty_metrics,
            "por_escola": [],
            "por_serie": [],
            "por_turma": [],
            "por_avaliacao": [],
            "por_origem": [],
            "alunos": [],
        }

    allowed_class_ids = {ct.class_id for ct in class_tests if ct.class_id is not None}
    test_ids = list({str(ct.test_id) for ct in class_tests if ct.test_id})
    question_by_test = _question_counts_by_test(test_ids)

    tests = (
        Test.query.filter(Test.id.in_(test_ids))
        .options(joinedload(Test.grade), joinedload(Test.test_questions))
        .all()
    )
    tests_by_id = {str(t.id): t for t in tests}

    query = (
        db.session.query(TestSession, Student, EvaluationResult)
        .join(Student, Student.id == TestSession.student_id)
        .outerjoin(
            EvaluationResult,
            and_(
                EvaluationResult.session_id == TestSession.id,
                EvaluationResult.test_id == TestSession.test_id,
            ),
        )
        .filter(TestSession.test_id.in_(test_ids))
        .filter(
            or_(
                TestSession.status.is_(None),
                func.lower(TestSession.status).notin_(("em_andamento", "expirada")),
            )
        )
        .options(joinedload(Student.class_).joinedload(Class.grade))
    )
    if aluno_ids:
        query = query.filter(Student.id.in_([str(a) for a in aluno_ids]))

    rows = query.all()

    grade_name_cache: Dict[str, str] = {}

    def _grade_name(grade_id) -> Optional[str]:
        if grade_id is None:
            return None
        key = str(grade_id)
        if key not in grade_name_cache:
            g = Grade.query.get(grade_id)
            grade_name_cache[key] = (g.name if g else "") or ""
        return grade_name_cache[key] or None

    por_escola = defaultdict(_agg_bucket)
    por_serie = defaultdict(_agg_bucket)
    por_turma = defaultdict(_agg_bucket)
    por_avaliacao = defaultdict(_agg_bucket)
    por_origem = defaultdict(_agg_bucket)

    detalhe: List[Dict[str, Any]] = []
    tempos_total: List[float] = []
    tempos_questao: List[float] = []
    questoes_vals: List[float] = []
    alunos_set = set()
    counts_origem = {
        ORIGEM_MEDIDA: 0,
        ORIGEM_ESTIMADA_MOBILE: 0,
        ORIGEM_ESTIMADA_FALLBACK: 0,
    }

    escola_ids_seen = set()
    turma_ids_seen = set()
    serie_ids_seen = set()

    for session, student, result in rows:
        test = tests_by_id.get(str(session.test_id))
        school_id, class_id, grade_id = _placement_for_student(student, result)

        if allowed_class_ids and class_id is not None and class_id not in allowed_class_ids:
            continue
        if escola_ids and school_id and str(school_id) not in {str(e) for e in escola_ids}:
            continue
        if serie_ids and grade_id is not None:
            serie_set = {str(s) for s in serie_ids}
            if str(grade_id) not in serie_set:
                continue
        if turma_ids and class_id is not None:
            turma_set = {str(t) for t in turma_ids}
            if str(class_id) not in turma_set:
                continue

        grade_name = None
        if test is not None and getattr(test, "grade", None) is not None:
            grade_name = test.grade.name
        if not grade_name:
            grade_name = _grade_name(grade_id)

        qcount = question_by_test.get(str(session.test_id), 0)
        metrics = compute_session_time_metrics(
            session,
            test=test,
            grade_name=grade_name,
            question_count=qcount or None,
        )
        if not metrics:
            continue

        origem = metrics["origem"]
        total_s = float(metrics["tempo_total_segundos"])
        per_q = metrics["tempo_por_questao_segundos"]
        nq = int(metrics["total_questions"] or 0)

        alunos_set.add(str(student.id))
        tempos_total.append(total_s)
        if per_q is not None:
            tempos_questao.append(float(per_q))
        if nq > 0:
            questoes_vals.append(float(nq))
        counts_origem[origem] = counts_origem.get(origem, 0) + 1

        escola_key = str(school_id) if school_id else ""
        serie_key = str(grade_id) if grade_id is not None else ""
        turma_key = str(class_id) if class_id is not None else ""
        prova_key = str(session.test_id)

        if school_id:
            escola_ids_seen.add(str(school_id))
        if class_id is not None:
            turma_ids_seen.add(class_id)
        if grade_id is not None:
            serie_ids_seen.add(grade_id)

        def _add(bucket_map, key):
            b = bucket_map[key]
            b["sessoes"] += 1
            b["tempos_total"].append(total_s)
            if per_q is not None:
                b["tempos_questao"].append(float(per_q))
            if origem == ORIGEM_MEDIDA:
                b["online"] += 1
            elif origem == ORIGEM_ESTIMADA_MOBILE:
                b["mobile"] += 1

        _add(por_escola, escola_key)
        _add(por_serie, serie_key)
        _add(por_turma, turma_key)
        _add(por_avaliacao, prova_key)
        _add(por_origem, origem)

        if len(detalhe) < _MAX_ALUNOS_DETALHE:
            detalhe.append(
                {
                    "aluno_id": str(student.id),
                    "aluno_nome": student.name or "",
                    "escola_id": escola_key,
                    "turma_id": turma_key,
                    "serie_id": serie_key,
                    "prova_id": prova_key,
                    "sessao_id": str(session.id),
                    "origem": origem,
                    "tempo_total_segundos": int(total_s),
                    "total_questions": nq,
                    "tempo_por_questao_segundos": per_q,
                    "estimated_time_minutos": metrics["estimated_time_minutos"],
                }
            )

    escolas_nomes, turmas_nomes, series_nomes, provas_nomes = _names_maps(
        escola_ids_seen, turma_ids_seen, serie_ids_seen, test_ids
    )

    origem_labels = {
        ORIGEM_MEDIDA: "Online (tempo real)",
        ORIGEM_ESTIMADA_MOBILE: "Mobile (estimado)",
        ORIGEM_ESTIMADA_FALLBACK: "Estimado (sem cronômetro)",
    }

    for row in detalhe:
        row["escola_nome"] = escolas_nomes.get(row["escola_id"], "")
        row["turma_nome"] = turmas_nomes.get(row["turma_id"], "")
        row["serie_nome"] = series_nomes.get(row["serie_id"], "")
        row["prova_titulo"] = provas_nomes.get(row["prova_id"], "")

    detalhe.sort(key=lambda r: ((r.get("tempo_por_questao_segundos") or 0), r.get("aluno_nome") or ""))

    return {
        "escopo": escopo,
        "metricas": {
            "sessoes": len(tempos_total),
            "alunos": len(alunos_set),
            "sessoes_online_medidas": counts_origem.get(ORIGEM_MEDIDA, 0),
            "sessoes_mobile_estimadas": counts_origem.get(ORIGEM_ESTIMADA_MOBILE, 0),
            "sessoes_estimadas_fallback": counts_origem.get(ORIGEM_ESTIMADA_FALLBACK, 0),
            "tempo_medio_segundos": _mean(tempos_total),
            "tempo_medio_por_questao_segundos": _mean(tempos_questao),
            "tempo_mediano_por_questao_segundos": _median(tempos_questao),
            "questoes_media": _mean(questoes_vals),
        },
        "por_escola": sorted(
            [
                _finalize_bucket(
                    b,
                    {
                        "escola_id": k,
                        "escola_nome": escolas_nomes.get(k, ""),
                    },
                )
                for k, b in por_escola.items()
                if k
            ],
            key=lambda x: x["escola_nome"] or "",
        ),
        "por_serie": sorted(
            [
                _finalize_bucket(
                    b,
                    {
                        "serie_id": k,
                        "serie_nome": series_nomes.get(k, ""),
                    },
                )
                for k, b in por_serie.items()
                if k
            ],
            key=lambda x: x["serie_nome"] or "",
        ),
        "por_turma": sorted(
            [
                _finalize_bucket(
                    b,
                    {
                        "turma_id": k,
                        "turma_nome": turmas_nomes.get(k, ""),
                        "escola_id": "",
                    },
                )
                for k, b in por_turma.items()
                if k
            ],
            key=lambda x: x["turma_nome"] or "",
        ),
        "por_avaliacao": sorted(
            [
                _finalize_bucket(
                    b,
                    {
                        "prova_id": k,
                        "prova_titulo": provas_nomes.get(k, ""),
                    },
                )
                for k, b in por_avaliacao.items()
                if k
            ],
            key=lambda x: x["prova_titulo"] or "",
        ),
        "por_origem": [
            _finalize_bucket(
                por_origem[key],
                {"origem": key, "origem_label": origem_labels[key]},
            )
            for key in (ORIGEM_MEDIDA, ORIGEM_ESTIMADA_MOBILE, ORIGEM_ESTIMADA_FALLBACK)
            if por_origem[key]["sessoes"] > 0
        ],
        "alunos": detalhe,
    }
