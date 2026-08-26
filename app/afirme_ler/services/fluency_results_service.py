# -*- coding: utf-8 -*-
"""Relatórios de fluência leitora (catálogo, recorte, perfil). Usa FluencyScoring."""
from __future__ import annotations

import unicodedata
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple
from uuid import UUID

from sqlalchemy.orm import joinedload

from app.models.city import City
from app.models.grades import Grade
from app.models.school import School
from app.models.student import Student
from app.models.studentClass import Class
from app.permissions.roles import Roles
from app.permissions.utils import get_manager_school, get_teacher_classes
from app.utils.tenant_middleware import get_current_tenant_context
from app.afirme_ler.models import (
    ReadingEvaluation,
    ReadingEvaluationSession,
    ReadingFluencySession,
    ReadingWordList,
)
from app.afirme_ler.scoring import FluencyScoring, StudentReadingScore
from app.afirme_ler.scoring.from_session import input_from_session
from app.afirme_ler.scoring.levels import SEM_PERFIL_LABEL, nivel_label
from app.afirme_ler.services.parsing import (
    EVALUATION_KIND_LABELS,
    validate_evaluation_kind,
)
from app.afirme_ler.services.results_copy import (
    alertas_from_indicadores,
    criterios_payload,
    frase_analitica,
    leitura_analitica,
)

EDITION_ORDER = ("entrada", "formativa", "saida")
PREVIOUS_EDITION = {"formativa": "entrada", "saida": "formativa"}
HIDDEN_EVAL_STATUSES = frozenset({"cancelada"})
REDE_NOME = "Rede Municipal"
POR_VALUES = frozenset({"escola", "turma", "estudante"})
TURNO_CANON = ("Matutino", "Vespertino", "Noturno", "Integral")

_TURNO_ALIASES = {
    "matutino": "Matutino",
    "morning": "Matutino",
    "manha": "Matutino",
    "vespertino": "Vespertino",
    "afternoon": "Vespertino",
    "tarde": "Vespertino",
    "noturno": "Noturno",
    "night": "Noturno",
    "noite": "Noturno",
    "integral": "Integral",
    "full-time": "Integral",
    "full_time": "Integral",
    "fulltime": "Integral",
}


def _strip_accents(value: str) -> str:
    nfkd = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))


def normalize_turno(value: Any) -> Optional[str]:
    if value is None or str(value).strip() == "":
        return None
    raw = str(value).strip()
    if raw in TURNO_CANON:
        return raw
    key = _strip_accents(raw).lower().replace(" ", "-")
    return _TURNO_ALIASES.get(key)


def evaluation_year(evaluation: ReadingEvaluation) -> Optional[int]:
    dt = evaluation.application_start or evaluation.created_at
    return int(dt.year) if dt else None


def previous_edition(edicao: str) -> Optional[str]:
    return PREVIOUS_EDITION.get(edicao)


def evaluations_same_cycle(left: ReadingEvaluation, right: ReadingEvaluation) -> bool:
    """Mesmo ciclo: interseção de turmas ou, se vazio, de escolas."""
    left_classes = _as_str_set(_eval_ids(left, "class_ids"))
    right_classes = _as_str_set(_eval_ids(right, "class_ids"))
    if left_classes and right_classes:
        return bool(left_classes & right_classes)
    left_schools = _as_str_set(_eval_ids(left, "school_ids"))
    right_schools = _as_str_set(_eval_ids(right, "school_ids"))
    if left_schools and right_schools:
        return bool(left_schools & right_schools)
    return False


def _user_id(user: Dict[str, Any]) -> Optional[str]:
    return user.get("id") or user.get("user_id")


def _role(user: Dict[str, Any]) -> str:
    return Roles.normalize(user.get("role", ""))


def _as_str_set(values: Optional[Iterable[Any]]) -> Set[str]:
    return {str(item) for item in (values or []) if item}


def _class_uuids(class_ids: Iterable[str]) -> List[UUID]:
    parsed: List[UUID] = []
    for class_id in class_ids:
        try:
            parsed.append(UUID(str(class_id)))
        except (TypeError, ValueError):
            continue
    return parsed


def _eval_ids(evaluation: ReadingEvaluation, attr: str) -> List[str]:
    raw = getattr(evaluation, attr, None)
    if not isinstance(raw, list):
        return []
    return [str(item) for item in raw if item]


def _session_sort_key(session: Any) -> datetime:
    return (
        getattr(session, "updated_at", None)
        or getattr(session, "submitted_at", None)
        or getattr(session, "created_at", None)
        or datetime.min
    )


def _pick_report_session(sessions: Sequence[Any]) -> Optional[Any]:
    if not sessions:
        return None
    for status in ("finalizada", "ausente", "em_andamento", "pendente"):
        group = [item for item in sessions if getattr(item, "status", None) == status]
        if group:
            return max(group, key=_session_sort_key)
    return max(sessions, key=_session_sort_key)


def _turma_nome(grade_name: Optional[str], class_name: Optional[str]) -> str:
    grade = (grade_name or "").strip()
    name = (class_name or "").strip()
    if grade and name and grade.lower() not in name.lower():
        return f"{grade} {name}".strip()
    return name or grade or "—"


class FluencyResultsService:
    @staticmethod
    def _city() -> City:
        ctx = get_current_tenant_context()
        city_id = str(ctx.city_id) if ctx and getattr(ctx, "city_id", None) else None
        if not city_id:
            raise ValueError("Contexto de município obrigatório.")
        city = City.query.get(city_id)
        if not city:
            raise LookupError("Município não encontrado.")
        return city

    @staticmethod
    def _visible_evaluations(user: Dict[str, Any]) -> List[ReadingEvaluation]:
        rows = ReadingEvaluation.query.filter(
            ~ReadingEvaluation.status.in_(tuple(HIDDEN_EVAL_STATUSES))
        ).all()
        role = _role(user)
        if role in (Roles.ADMIN, Roles.TECADM):
            return rows
        uid = _user_id(user)
        school_id = get_manager_school(uid) if uid else None
        teacher_classes = {str(cid) for cid in (get_teacher_classes(uid) or [])} if uid else set()
        visible: List[ReadingEvaluation] = []
        for evaluation in rows:
            if uid and str(evaluation.created_by) == str(uid):
                visible.append(evaluation)
                continue
            school_ids = _as_str_set(_eval_ids(evaluation, "school_ids"))
            class_ids = _as_str_set(_eval_ids(evaluation, "class_ids"))
            if role in (Roles.DIRETOR, Roles.COORDENADOR) and school_id and school_id in school_ids:
                visible.append(evaluation)
                continue
            if teacher_classes and teacher_classes & class_ids:
                visible.append(evaluation)
        return visible

    @staticmethod
    def _apply_permission_roster(
        user: Dict[str, Any],
        students: List[Student],
        evaluations: List[ReadingEvaluation],
    ) -> List[Student]:
        role = _role(user)
        if role in (Roles.ADMIN, Roles.TECADM):
            return students
        uid = _user_id(user)
        created_ids = {
            ev.id for ev in evaluations if uid and str(ev.created_by) == str(uid)
        }
        school_id = get_manager_school(uid) if uid else None
        teacher_classes = (
            {str(cid) for cid in (get_teacher_classes(uid) or [])} if uid else set()
        )
        out: List[Student] = []
        for student in students:
            in_created = any(
                ev.id in created_ids
                and FluencyResultsService._student_in_evaluation(student, ev)
                for ev in evaluations
            )
            if in_created:
                out.append(student)
                continue
            if (
                role in (Roles.DIRETOR, Roles.COORDENADOR)
                and school_id
                and str(student.school_id) == str(school_id)
            ):
                out.append(student)
                continue
            if teacher_classes and str(student.class_id) in teacher_classes:
                out.append(student)
        return out

    @staticmethod
    def _student_in_evaluation(student: Student, evaluation: ReadingEvaluation) -> bool:
        class_ids = _as_str_set(_eval_ids(evaluation, "class_ids"))
        school_ids = _as_str_set(_eval_ids(evaluation, "school_ids"))
        grade_ids = _as_str_set(evaluation.grade_id_list())
        allow = [str(item) for item in (evaluation.student_ids or []) if item]
        if allow and str(student.id) not in allow:
            return False
        if class_ids and str(student.class_id or "") not in class_ids:
            return False
        if school_ids and str(student.school_id or "") not in school_ids:
            return False
        if grade_ids and str(student.grade_id or "") not in grade_ids:
            return False
        return True

    @staticmethod
    def catalog(user: Dict[str, Any]) -> dict:
        city = FluencyResultsService._city()
        evaluations = FluencyResultsService._visible_evaluations(user)
        years = sorted(
            {
                evaluation_year(item)
                for item in evaluations
                if evaluation_year(item)
            }
        )
        class_ids: Set[str] = set()
        school_ids: Set[str] = set()
        grade_ids: Set[str] = set()
        for evaluation in evaluations:
            class_ids.update(_eval_ids(evaluation, "class_ids"))
            school_ids.update(_eval_ids(evaluation, "school_ids"))
            grade_ids.update(evaluation.grade_id_list())

        klasses = []
        if class_ids:
            klasses = Class.query.filter(Class.id.in_(_class_uuids(class_ids))).all()
        for klass in klasses:
            if klass.school_id:
                school_ids.add(str(klass.school_id))
            if klass.grade_id:
                grade_ids.add(str(klass.grade_id))

        schools = School.query.filter(School.id.in_(list(school_ids))).all() if school_ids else []
        grades = Grade.query.filter(Grade.id.in_(list(grade_ids))).all() if grade_ids else []
        grade_name = {str(row.id): row.name for row in grades}

        rede_id = str(city.id)
        avaliacoes = [
            FluencyResultsService._catalog_evaluation(item)
            for item in sorted(
                evaluations,
                key=lambda row: (
                    -(evaluation_year(row) or 0),
                    EDITION_ORDER.index(row.evaluation_kind)
                    if row.evaluation_kind in EDITION_ORDER
                    else 99,
                    (row.title or "").lower(),
                ),
            )
        ]
        return {
            "anos": years,
            "edicoes": [
                {"id": kind, "label": EVALUATION_KIND_LABELS[kind]}
                for kind in EDITION_ORDER
            ],
            "avaliacoes": avaliacoes,
            "redes": [{"id": rede_id, "nome": REDE_NOME}],
            "municipios": [
                {"id": str(city.id), "redeId": rede_id, "nome": city.name}
            ],
            "escolas": [
                {
                    "id": str(school.id),
                    "municipioId": str(city.id),
                    "nome": school.name,
                }
                for school in sorted(schools, key=lambda row: (row.name or "").lower())
            ],
            "series": [
                {"id": str(grade.id), "nome": grade.name}
                for grade in sorted(grades, key=lambda row: (row.name or "").lower())
            ],
            "turmas": [
                {
                    "id": str(klass.id),
                    "escolaId": str(klass.school_id) if klass.school_id else None,
                    "serieId": str(klass.grade_id) if klass.grade_id else None,
                    "nome": _turma_nome(
                        grade_name.get(str(klass.grade_id)) if klass.grade_id else None,
                        klass.name,
                    ),
                    "turno": normalize_turno(klass.shift) or "",
                }
                for klass in sorted(klasses, key=lambda row: (row.name or "").lower())
            ],
        }

    @staticmethod
    def _catalog_evaluation(evaluation: ReadingEvaluation) -> dict:
        return {
            "id": evaluation.id,
            "titulo": evaluation.title,
            "ano": evaluation_year(evaluation),
            "edicao": evaluation.evaluation_kind,
            "edicaoLabel": EVALUATION_KIND_LABELS.get(evaluation.evaluation_kind),
            "status": evaluation.status,
            "escolaIds": _eval_ids(evaluation, "school_ids"),
            "serieIds": evaluation.grade_id_list(),
            "turmaIds": _eval_ids(evaluation, "class_ids"),
        }

    @staticmethod
    def _require_evaluation(
        user: Dict[str, Any],
        filters: dict,
    ) -> Tuple[ReadingEvaluation, List[ReadingEvaluation]]:
        avaliacao_id = (
            filters.get("avaliacaoId")
            or filters.get("avaliacao_id")
            or filters.get("evaluationId")
            or filters.get("evaluation_id")
        )
        if not avaliacao_id:
            raise ValueError("avaliacaoId é obrigatório.")
        visible = FluencyResultsService._visible_evaluations(user)
        selected = next(
            (item for item in visible if str(item.id) == str(avaliacao_id)),
            None,
        )
        if not selected:
            raise LookupError("Avaliação não encontrada.")
        if filters.get("ano"):
            requested_year = FluencyResultsService._parse_ano(filters.get("ano"))
            actual_year = evaluation_year(selected)
            if actual_year and actual_year != requested_year:
                raise ValueError("ano não corresponde à avaliação selecionada.")
        kind_raw = filters.get("edicao") or filters.get("evaluationKind")
        if kind_raw:
            requested_kind = validate_evaluation_kind(kind_raw)
            if requested_kind != selected.evaluation_kind:
                raise ValueError("edicao não corresponde à avaliação selecionada.")
        return selected, visible

    @staticmethod
    def _cycle_evaluations(
        visible: List[ReadingEvaluation],
        reference: ReadingEvaluation,
        kind: str,
        ano: int,
    ) -> List[ReadingEvaluation]:
        return [
            item
            for item in visible
            if item.evaluation_kind == kind
            and evaluation_year(item) == ano
            and evaluations_same_cycle(reference, item)
        ]

    @staticmethod
    def report(user: Dict[str, Any], filters: dict) -> dict:
        city = FluencyResultsService._city()
        selected, visible = FluencyResultsService._require_evaluation(user, filters)
        ano = evaluation_year(selected)
        if filters.get("ano"):
            ano = FluencyResultsService._parse_ano(filters.get("ano"))
        if not ano:
            raise ValueError("Não foi possível determinar o ano da avaliação.")
        edicao = selected.evaluation_kind
        cut = FluencyResultsService._parse_cut(filters, city)
        evaluations = [selected]
        bundle = FluencyResultsService._build_bundle(
            user, city, ano, edicao, evaluations, cut
        )
        previous_kind = previous_edition(edicao)
        previous_bundle = None
        if previous_kind:
            prev_evals = FluencyResultsService._cycle_evaluations(
                visible, selected, previous_kind, ano
            )
            if prev_evals:
                previous_bundle = FluencyResultsService._build_bundle(
                    user, city, ano, previous_kind, prev_evals, cut
                )

        indicadores = FluencyScoring.aplicar_delta(
            bundle["aggregate"],
            previous_bundle["aggregate"] if previous_bundle else None,
        )
        indicadores_dict = indicadores.to_dict()
        FluencyResultsService._attach_lista(indicadores_dict, bundle["rows"])

        anteriores_dict = None
        if previous_kind and previous_bundle and previous_bundle["aggregate"].previstos:
            anteriores_dict = previous_bundle["aggregate"].to_dict()
            for band in anteriores_dict["distribuicao"]:
                band["lista"] = []

        titulo = f"{EVALUATION_KIND_LABELS.get(edicao, edicao)} {ano}"
        return {
            "avaliacaoId": selected.id,
            "avaliacaoTitulo": selected.title,
            "avaliacaoStatus": selected.status,
            "ano": ano,
            "edicao": edicao,
            "tituloEdicao": titulo,
            "escopoLabel": FluencyResultsService._escopo_label(city, cut, bundle),
            "emitidoEm": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "criterios": criterios_payload(),
            "indicadores": indicadores_dict,
            "indicadoresAnteriores": anteriores_dict,
            "leituraAnalitica": leitura_analitica(
                titulo_edicao=titulo,
                previstos=indicadores.previstos,
                avaliados=indicadores.avaliados,
                participacao=indicadores.participacao,
                ifl=indicadores.ifl,
            ),
            "alertas": alertas_from_indicadores(indicadores_dict),
            "porEscola": FluencyResultsService._por_escola(bundle),
            "porTurma": FluencyResultsService._por_turma(bundle),
            "estudantes": [row["payload"] for row in bundle["rows"]],
        }

    @staticmethod
    def student_profile(user: Dict[str, Any], student_id: str, filters: dict) -> dict:
        city = FluencyResultsService._city()
        selected = None
        visible = FluencyResultsService._visible_evaluations(user)
        avaliacao_id = (
            filters.get("avaliacaoId")
            or filters.get("avaliacao_id")
            or filters.get("evaluationId")
        )
        if avaliacao_id:
            selected, visible = FluencyResultsService._require_evaluation(user, filters)
            ano = evaluation_year(selected)
            if filters.get("ano"):
                ano = FluencyResultsService._parse_ano(filters.get("ano"))
            if not ano:
                raise ValueError("Não foi possível determinar o ano da avaliação.")
            year_evals = [
                item
                for item in visible
                if evaluation_year(item) == ano
                and evaluations_same_cycle(selected, item)
            ]
            if selected not in year_evals:
                year_evals.append(selected)
            edicao_filtro = selected.evaluation_kind
        else:
            ano = FluencyResultsService._parse_ano(filters.get("ano"))
            edicao_filtro = filters.get("edicao") or filters.get("evaluationKind")
            if edicao_filtro:
                edicao_filtro = validate_evaluation_kind(edicao_filtro)
            year_evals = [item for item in visible if evaluation_year(item) == ano]

        student = Student.query.get(student_id)
        if not student:
            raise LookupError("Estudante não encontrado.")

        if not any(
            FluencyResultsService._student_in_evaluation(student, item)
            for item in year_evals
        ):
            if _role(user) not in (Roles.ADMIN, Roles.TECADM):
                raise LookupError("Estudante não encontrado neste recorte.")

        cut = {
            "rede_id": str(city.id),
            "municipio_id": str(city.id),
            "escola_id": None,
            "serie_id": None,
            "turma_id": None,
            "turno": None,
            "por": None,
            "item_id": None,
        }
        timeline = []
        scores_by_kind: Dict[str, Optional[StudentReadingScore]] = {}
        for kind in EDITION_ORDER:
            kind_evals = [item for item in year_evals if item.evaluation_kind == kind]
            bundle = FluencyResultsService._build_bundle(
                user, city, ano, kind, kind_evals, cut, student_ids={str(student.id)}
            )
            row = bundle["rows"][0] if bundle["rows"] else None
            if row:
                scores_by_kind[kind] = row["score"]
                nivel = row["score"].nivel
                timeline.append(
                    {
                        "edicao": kind,
                        "edicaoLabel": EVALUATION_KIND_LABELS[kind],
                        "nivel": nivel,
                        "nivelLabel": row["score"].nivel_label,
                        "resultado": row["payload"],
                    }
                )
            else:
                scores_by_kind[kind] = None
                timeline.append(
                    {
                        "edicao": kind,
                        "edicaoLabel": EVALUATION_KIND_LABELS[kind],
                        "nivel": None,
                        "nivelLabel": SEM_PERFIL_LABEL,
                        "resultado": None,
                    }
                )

        atual_kind = edicao_filtro
        if not atual_kind:
            for kind in reversed(EDITION_ORDER):
                score = scores_by_kind.get(kind)
                if score and score.nivel:
                    atual_kind = kind
                    break
            if not atual_kind:
                atual_kind = EDITION_ORDER[0]

        score_atual = scores_by_kind.get(atual_kind)
        prev_kind = previous_edition(atual_kind)
        score_prev = scores_by_kind.get(prev_kind) if prev_kind else None
        perfil_atual = score_atual.nivel if score_atual else None
        perfil_anterior = score_prev.nivel if score_prev else None

        identity = FluencyResultsService._student_identity(student, city, ano, atual_kind)
        turma_id = identity["turmaId"]
        participacao_turma = 0.0
        if turma_id:
            turma_evals = [
                item for item in year_evals if item.evaluation_kind == atual_kind
            ]
            turma_cut = dict(cut)
            turma_cut["turma_id"] = turma_id
            turma_bundle = FluencyResultsService._build_bundle(
                user, city, ano, atual_kind, turma_evals, turma_cut
            )
            participacao_turma = turma_bundle["aggregate"].participacao

        return {
            "id": str(student.id),
            "nome": student.name,
            "matricula": student.registration,
            "escolaNome": identity["escolaNome"],
            "turmaNome": identity["turmaNome"],
            "turno": identity["turno"],
            "serieNome": identity["serieNome"],
            "municipioNome": city.name,
            "redeNome": REDE_NOME,
            "ano": ano,
            "avaliacaoId": selected.id if selected else None,
            "avaliacaoTitulo": selected.title if selected else None,
            "edicao": atual_kind,
            "linhaDoTempo": timeline,
            "perfilAnterior": perfil_anterior,
            "perfilAtual": perfil_atual,
            "evolucao": FluencyScoring.evolucao(perfil_atual, perfil_anterior),
            "exportacao": {
                "iflDoNivel": FluencyScoring.ifl_do_nivel(perfil_atual),
                "participacaoTurmaPct": participacao_turma,
                "fraseAnalitica": frase_analitica(
                    nivel_label=nivel_label(perfil_atual),
                    ppm=score_atual.ppm if score_atual else 0.0,
                    precisao=score_atual.precisao if score_atual else 0.0,
                    avaliado=bool(score_atual and score_atual.avaliado),
                ),
            },
        }

    @staticmethod
    def _parse_ano(raw: Any) -> int:
        if raw is None or raw == "":
            raise ValueError("ano é obrigatório.")
        try:
            year = int(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError("ano deve ser um inteiro.") from exc
        if year < 2000 or year > 2100:
            raise ValueError("ano inválido.")
        return year

    @staticmethod
    def _parse_cut(filters: dict, city: City) -> dict:
        rede_id = filters.get("redeId") or filters.get("rede_id")
        municipio_id = filters.get("municipioId") or filters.get("municipio_id")
        if rede_id and str(rede_id) != str(city.id):
            raise ValueError("redeId não pertence ao município atual.")
        if municipio_id and str(municipio_id) != str(city.id):
            raise ValueError("municipioId não pertence ao município atual.")
        por = filters.get("por")
        if por:
            por = str(por).strip().lower()
            if por not in POR_VALUES:
                raise ValueError("por deve ser escola, turma ou estudante.")
        item_id = filters.get("itemId") or filters.get("item_id")
        if por and not item_id:
            raise ValueError("itemId é obrigatório quando por é informado.")
        turno = normalize_turno(filters.get("turno"))
        escola_id = filters.get("escolaId") or filters.get("escola_id")
        turma_id = filters.get("turmaId") or filters.get("turma_id")
        estudante_id = None
        if por == "escola":
            escola_id = str(item_id)
        elif por == "turma":
            turma_id = str(item_id)
        elif por == "estudante":
            estudante_id = str(item_id)
        serie_id = filters.get("serieId") or filters.get("serie_id")
        return {
            "rede_id": str(city.id),
            "municipio_id": str(city.id),
            "escola_id": str(escola_id) if escola_id else None,
            "serie_id": str(serie_id) if serie_id else None,
            "turma_id": str(turma_id) if turma_id else None,
            "estudante_id": estudante_id,
            "turno": turno,
            "por": por,
            "item_id": str(item_id) if item_id else None,
        }

    @staticmethod
    def _build_bundle(
        user: Dict[str, Any],
        city: City,
        ano: int,
        edicao: str,
        evaluations: List[ReadingEvaluation],
        cut: dict,
        student_ids: Optional[Set[str]] = None,
    ) -> dict:
        class_ids: Set[str] = set()
        for evaluation in evaluations:
            class_ids.update(_eval_ids(evaluation, "class_ids"))
        klasses = (
            Class.query.filter(Class.id.in_(_class_uuids(class_ids))).all()
            if class_ids
            else []
        )
        klass_by_id = {str(klass.id): klass for klass in klasses}
        school_ids = {str(klass.school_id) for klass in klasses if klass.school_id}
        for evaluation in evaluations:
            school_ids.update(_eval_ids(evaluation, "school_ids"))
        schools = (
            School.query.filter(School.id.in_(list(school_ids))).all() if school_ids else []
        )
        school_by_id = {str(row.id): row for row in schools}
        grade_ids = {str(klass.grade_id) for klass in klasses if klass.grade_id}
        for evaluation in evaluations:
            grade_ids.update(evaluation.grade_id_list())
        grades = Grade.query.filter(Grade.id.in_(list(grade_ids))).all() if grade_ids else []
        grade_by_id = {str(row.id): row for row in grades}

        students: List[Student] = []
        if class_ids:
            query = Student.query.filter(Student.class_id.in_(_class_uuids(class_ids)))
            students = query.order_by(Student.name.asc()).all()
        students = [
            student
            for student in students
            if any(
                FluencyResultsService._student_in_evaluation(student, evaluation)
                for evaluation in evaluations
            )
        ]
        students = FluencyResultsService._apply_permission_roster(
            user, students, evaluations
        )
        if student_ids is not None:
            students = [row for row in students if str(row.id) in student_ids]
        elif cut.get("estudante_id"):
            students = [
                row for row in students if str(row.id) == str(cut["estudante_id"])
            ]
        if cut.get("escola_id"):
            students = [
                row for row in students if str(row.school_id or "") == cut["escola_id"]
            ]
        if cut.get("serie_id"):
            students = [
                row for row in students if str(row.grade_id or "") == cut["serie_id"]
            ]
        if cut.get("turma_id"):
            students = [
                row for row in students if str(row.class_id or "") == cut["turma_id"]
            ]
        if cut.get("turno"):
            filtered = []
            for student in students:
                klass = klass_by_id.get(str(student.class_id) if student.class_id else "")
                if klass and normalize_turno(klass.shift) == cut["turno"]:
                    filtered.append(student)
            students = filtered

        eval_ids = [item.id for item in evaluations]
        fluency_by_student: Dict[str, List[Any]] = defaultdict(list)
        legacy_by_student: Dict[str, List[Any]] = defaultdict(list)
        ids = [student.id for student in students]
        if eval_ids and ids:
            fluency_rows = ReadingFluencySession.query.options(
                joinedload(ReadingFluencySession.evaluation)
            ).filter(
                ReadingFluencySession.reading_evaluation_id.in_(eval_ids),
                ReadingFluencySession.student_id.in_(ids),
            ).all()
            for session in fluency_rows:
                fluency_by_student[session.student_id].append(session)
            legacy_rows = ReadingEvaluationSession.query.filter(
                ReadingEvaluationSession.reading_evaluation_id.in_(eval_ids),
                ReadingEvaluationSession.student_id.in_(ids),
            ).all()
            for session in legacy_rows:
                legacy_by_student[session.student_id].append(session)

        list_sizes: Dict[str, Tuple[int, int]] = {}
        for evaluation in evaluations:
            list_sizes[evaluation.id] = (
                FluencyResultsService._word_list_len(evaluation.words_word_list_id),
                FluencyResultsService._word_list_len(evaluation.uncommon_word_list_id),
            )

        previous_kind = previous_edition(edicao)
        prev_by_student: Dict[str, StudentReadingScore] = {}
        if previous_kind and students and evaluations:
            visible = FluencyResultsService._visible_evaluations(user)
            prev_evals = [
                item
                for item in visible
                if item.evaluation_kind == previous_kind
                and evaluation_year(item) == ano
                and any(evaluations_same_cycle(ref, item) for ref in evaluations)
            ]
            prev_ids = [item.id for item in prev_evals]
            if prev_ids:
                prev_sessions = ReadingFluencySession.query.filter(
                    ReadingFluencySession.reading_evaluation_id.in_(prev_ids),
                    ReadingFluencySession.student_id.in_(ids),
                ).all()
                grouped: Dict[str, List[Any]] = defaultdict(list)
                for session in prev_sessions:
                    grouped[session.student_id].append(session)
                for sid, group in grouped.items():
                    picked = _pick_report_session(group)
                    if picked:
                        prev_by_student[sid] = FluencyScoring.from_session(picked)

        eval_by_id = {item.id: item for item in evaluations}
        rows = []
        scores: List[StudentReadingScore] = []
        for student in students:
            session = _pick_report_session(fluency_by_student.get(student.id) or [])
            if session is None:
                session = _pick_report_session(legacy_by_student.get(student.id) or [])
            if session is not None:
                score = FluencyScoring.from_session(session)
                evaluation = None
                eval_id = getattr(session, "reading_evaluation_id", None)
                if eval_id:
                    evaluation = eval_by_id.get(eval_id)
            else:
                score = FluencyScoring.score_student(
                    input_from_session({"status": "não avaliado"})
                )
                evaluation = next(
                    (
                        item
                        for item in evaluations
                        if FluencyResultsService._student_in_evaluation(student, item)
                    ),
                    evaluations[0] if evaluations else None,
                )
            prev_score = prev_by_student.get(student.id)
            totals = list_sizes.get(evaluation.id, (0, 0)) if evaluation else (0, 0)
            payload = FluencyResultsService._student_payload(
                student=student,
                city=city,
                ano=ano,
                edicao=edicao,
                score=score,
                previous=prev_score,
                klass=klass_by_id.get(str(student.class_id) if student.class_id else ""),
                school=school_by_id.get(str(student.school_id) if student.school_id else None),
                grade=grade_by_id.get(str(student.grade_id) if student.grade_id else None),
                total_palavras=totals[0],
                total_desconhecidas=totals[1],
            )
            rows.append(
                {
                    "student": student,
                    "score": score,
                    "payload": payload,
                    "escola_id": payload["escolaId"],
                    "escola_nome": payload["escolaNome"],
                    "turma_id": payload["turmaId"],
                    "turma_nome": payload["turmaNome"],
                }
            )
            scores.append(score)

        aggregate = FluencyScoring.agregar(scores, previstos=len(students))
        return {
            "rows": rows,
            "scores": scores,
            "aggregate": aggregate,
            "klass_by_id": klass_by_id,
            "school_by_id": school_by_id,
            "grade_by_id": grade_by_id,
            "cut": cut,
        }

    @staticmethod
    def _word_list_len(list_id: Optional[str]) -> int:
        if not list_id:
            return 0
        row = ReadingWordList.query.get(list_id)
        items = row.items if row and isinstance(row.items, list) else []
        return len(items)

    @staticmethod
    def _student_identity(student: Student, city: City, ano: int, edicao: str) -> dict:
        klass = Class.query.get(student.class_id) if student.class_id else None
        school = School.query.get(student.school_id) if student.school_id else None
        grade = student.grade
        grade_name = grade.name if grade else None
        return {
            "escolaId": str(student.school_id) if student.school_id else None,
            "escolaNome": school.name if school else None,
            "turmaId": str(student.class_id) if student.class_id else None,
            "turmaNome": _turma_nome(grade_name, klass.name if klass else None),
            "serieId": str(student.grade_id) if student.grade_id else None,
            "serieNome": grade_name,
            "turno": normalize_turno(klass.shift) if klass else None,
            "ano": ano,
            "edicao": edicao,
            "redeId": str(city.id),
            "redeNome": REDE_NOME,
            "municipioId": str(city.id),
            "municipioNome": city.name,
        }

    @staticmethod
    def _student_payload(
        *,
        student: Student,
        city: City,
        ano: int,
        edicao: str,
        score: StudentReadingScore,
        previous: Optional[StudentReadingScore],
        klass: Optional[Class],
        school: Optional[School],
        grade: Optional[Grade],
        total_palavras: int,
        total_desconhecidas: int,
    ) -> dict:
        grade_name = grade.name if grade else None
        metrics = score.to_dict()
        nivel_ant = previous.nivel if previous else None
        payload = {
            "id": str(student.id),
            "nome": student.name,
            "matricula": student.registration,
            "escolaId": str(student.school_id) if student.school_id else None,
            "escolaNome": school.name if school else None,
            "turmaId": str(student.class_id) if student.class_id else None,
            "turmaNome": _turma_nome(grade_name, klass.name if klass else None),
            "serieId": str(student.grade_id) if student.grade_id else None,
            "serieNome": grade_name,
            "turno": normalize_turno(klass.shift) if klass else None,
            "ano": ano,
            "edicao": edicao,
            "redeId": str(city.id),
            "redeNome": REDE_NOME,
            "municipioId": str(city.id),
            "municipioNome": city.name,
            **metrics,
            "nivelAnterior": nivel_ant,
            "nivelAnteriorLabel": (
                (nivel_label(nivel_ant) if nivel_ant else SEM_PERFIL_LABEL)
                if previous
                else None
            ),
            "evolucao": FluencyScoring.evolucao(score.nivel, nivel_ant),
            "totalPalavras": total_palavras,
            "totalDesconhecidas": total_desconhecidas,
        }
        if not score.avaliado:
            payload["prosodiaLabel"] = SEM_PERFIL_LABEL
        return payload

    @staticmethod
    def _attach_lista(indicadores: dict, rows: List[dict]) -> None:
        by_level: Dict[str, List[dict]] = defaultdict(list)
        for row in rows:
            nivel = row["score"].nivel
            if not nivel:
                continue
            payload = row["payload"]
            by_level[nivel].append(
                {
                    "id": payload["id"],
                    "nome": payload["nome"],
                    "turmaNome": payload["turmaNome"],
                }
            )
        for band in indicadores.get("distribuicao") or []:
            band["lista"] = by_level.get(band.get("code"), [])

    @staticmethod
    def _por_escola(bundle: dict) -> List[dict]:
        pares = []
        previstos: Dict[str, int] = defaultdict(int)
        meta: Dict[str, dict] = {}
        for row in bundle["rows"]:
            gid = row["escola_id"]
            if not gid:
                continue
            pares.append((gid, row["score"]))
            previstos[gid] += 1
            meta[gid] = row
        grouped = FluencyScoring.agregar_por(pares, previstos)
        out = []
        for gid, agg in grouped.items():
            item = agg.to_dict()
            for band in item["distribuicao"]:
                band["lista"] = []
            sample = meta[gid]
            item["escolaId"] = gid
            item["escolaNome"] = sample["escola_nome"]
            out.append(item)
        out.sort(key=lambda row: (row.get("escolaNome") or "").lower())
        return out

    @staticmethod
    def _por_turma(bundle: dict) -> List[dict]:
        pares = []
        previstos: Dict[str, int] = defaultdict(int)
        meta: Dict[str, dict] = {}
        for row in bundle["rows"]:
            gid = row["turma_id"]
            if not gid:
                continue
            pares.append((gid, row["score"]))
            previstos[gid] += 1
            meta[gid] = row
        grouped = FluencyScoring.agregar_por(pares, previstos)
        out = []
        for gid, agg in grouped.items():
            item = agg.to_dict()
            for band in item["distribuicao"]:
                band["lista"] = []
            sample = meta[gid]
            item["turmaId"] = gid
            item["turmaNome"] = sample["turma_nome"]
            item["escolaNome"] = sample["escola_nome"]
            out.append(item)
        out.sort(key=lambda row: (row.get("turmaNome") or "").lower())
        return out

    @staticmethod
    def _escopo_label(city: City, cut: dict, bundle: dict) -> str:
        parts = [REDE_NOME, city.name or "Município"]
        if cut.get("escola_id"):
            schools = {
                row["escola_nome"]
                for row in bundle["rows"]
                if row["escola_id"] == cut["escola_id"]
            }
            parts.append(next(iter(schools), "Escola"))
        else:
            parts.append("Todas as escolas")
        if cut.get("serie_id"):
            grade = bundle["grade_by_id"].get(cut["serie_id"])
            parts.append(grade.name if grade else "Série")
        else:
            parts.append("Todas as séries")
        if cut.get("turma_id"):
            names = {
                row["turma_nome"]
                for row in bundle["rows"]
                if row["turma_id"] == cut["turma_id"]
            }
            parts.append(next(iter(names), "Turma"))
        else:
            parts.append("Todas as turmas")
        if cut.get("turno"):
            parts.append(cut["turno"])
        return " · ".join(parts)
