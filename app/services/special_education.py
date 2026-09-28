# -*- coding: utf-8 -*-
"""
Detecção de Educação Especial (ADAP / Suporte).

A subturma vigente tem prioridade. Sem subturma, vale a regra já usada no
sistema: série da etapa ADAP, ou nome de série "Suporte N". "ADAP N" entra
na mesma leitura, sem renomear as séries existentes.

Funções de texto abaixo preservam o que cada tela já fazia com o ano escolar
embutido no nome (ex.: "Suporte 1 9º Ano" continua Anos Finais no curso).
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional, Sequence

# Etapa pública "Educação Especial (ADAP)". Não mudar: formulários e séries
# existentes apontam para este UUID.
ADAP_EDUCATION_STAGE_ID = "247c4af5-2688-41b0-95fa-443f503a9d87"

_UNLOADED = object()
_EXACT_LEVEL_RE = re.compile(r"^(suporte|adap)\s*([123])$", re.IGNORECASE)
_YEAR_IN_LABEL_RE = re.compile(
    r"^(suporte|adap)\s*([123])\s+(\d+)\s*[ºo°]?\s*ano",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SpecialEducationStatus:
    """is_special no contexto booleano; level é 1, 2, 3 ou None."""

    is_special: bool
    level: Optional[int] = None
    source: Optional[str] = None

    def __bool__(self) -> bool:
        return self.is_special


def fold_text(value: Any) -> str:
    """Minúsculas, sem acento, pontas aparadas."""
    normalized = unicodedata.normalize("NFD", str(value or ""))
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn").strip().lower()


def is_adap_education_stage(education_stage_id: Any) -> bool:
    if not education_stage_id:
        return False
    return str(education_stage_id).lower() == ADAP_EDUCATION_STAGE_ID


def support_level_from_exact_grade_name(grade_name: Any) -> Optional[int]:
    """
    Nível quando o nome da série É só "Suporte N" ou "ADAP N".

    "Suporte 1 9º Ano" não entra: o ano escolar é outro dado, não o nível.
    """
    match = _EXACT_LEVEL_RE.match(str(grade_name or "").strip())
    if not match:
        return None
    return int(match.group(2))


def support_series_sort_key(serie_nome: str):
    """
    Mesma ordem do consolidado: Suporte/ADAP N + ano, depois só o nível, depois o resto.
    """
    text = (serie_nome or "").strip()
    year = _YEAR_IN_LABEL_RE.match(text)
    if year:
        return (0, int(year.group(2)), int(year.group(3)), text.upper())
    exact = _EXACT_LEVEL_RE.match(text)
    if exact:
        return (0, int(exact.group(2)), 0, text.upper())
    return (1, 0, 0, text.upper())


def serie_course_is_special_education(serie_name: Any, course_name: Any) -> bool:
    """
    Rótulo do ranking entre pares. Igual à regra anterior, e também série que
    começa com "adap".
    """
    course_n = fold_text(course_name)
    serie_n = fold_text(serie_name)
    if "educacao especial" in course_n:
        return True
    return serie_n.startswith("suporte") or serie_n.startswith("adap")


def course_name_is_special_education(course_name: Any) -> bool:
    """
    Ramo de educação especial do cálculo de proficiência.

    Continua verdadeiro quando o nome contém "especial" (ex.: "Educação Especial").
    "ADAP N" sozinho também. "Suporte 1 9º Ano" não entra: o ano escolar segue
    o caminho de Anos Iniciais/Finais, como hoje.
    """
    raw = str(course_name or "")
    if "especial" in raw.lower():
        return True
    return grade_label_is_exact_adap(raw)


def grade_label_is_exact_adap(text: Any) -> bool:
    """Verdadeiro só para o nome inteiro "ADAP N", sem ano escolar."""
    match = _EXACT_LEVEL_RE.match(str(text or "").strip())
    return bool(match and match.group(1).lower() == "adap")


def special_education_label_from_course_text(low: str) -> Optional[str]:
    """
    Bloco de etapa da análise de IA. `low` já vem sem acento e em minúsculas.

    Ano escolar explícito no texto é tratado pelo chamador, antes desta função.
    "Suporte N" mantém o rótulo antigo. "ADAP N" só quando não há "Suporte N".
    """
    suporte = re.search(r"suporte\s*([123])", low or "")
    if suporte or "aee" in (low or ""):
        if suporte:
            return f"Educação Especial (Suporte {suporte.group(1)})"
        return "Educação Especial"
    adap = re.search(r"adap\s*([123])", low or "")
    if adap:
        return f"Educação Especial (ADAP {adap.group(1)})"
    if "especial" in (low or "") and "ensino medio" not in (low or ""):
        return "Educação Especial"
    return None


def _level_from_subturma(subturma: Any) -> Optional[int]:
    level = getattr(subturma, "support_level", None)
    try:
        level_int = int(level)
    except (TypeError, ValueError):
        return None
    if level_int in (1, 2, 3):
        return level_int
    return None


def _same_class(student_class_id: Any, subturma: Any) -> bool:
    sub_class = getattr(subturma, "class_id", None)
    if student_class_id is None or sub_class is None:
        return False
    return str(student_class_id) == str(sub_class)


def class_is_special_education(class_obj: Any) -> bool:
    """
    Turma de Educação Especial: série da etapa ADAP ou nome Suporte N / ADAP N.
    """
    if class_obj is None:
        return False
    grade = getattr(class_obj, "grade", None)
    if grade is None and getattr(class_obj, "grade_id", None) is not None:
        from app.models.grades import Grade

        grade = Grade.query.get(class_obj.grade_id)
    status = status_from_grade_and_subturma(
        student_class_id=getattr(class_obj, "id", None),
        grade=grade,
        subturma=None,
    )
    return bool(status)


def status_from_grade_and_subturma(
    *,
    student_class_id: Any,
    grade: Any,
    subturma: Any,
) -> SpecialEducationStatus:
    """
    Compõe o resultado sem consultar o banco.

    Subturma só conta se o class_id dela for o da turma do aluno.
    """
    if subturma is not None and _same_class(student_class_id, subturma):
        level = _level_from_subturma(subturma)
        if level is not None:
            return SpecialEducationStatus(True, level, "subturma")

    if grade is None:
        return SpecialEducationStatus(False, None, None)

    level = support_level_from_exact_grade_name(getattr(grade, "name", None))
    stage_id = getattr(grade, "education_stage_id", None)
    if is_adap_education_stage(stage_id) or level is not None:
        return SpecialEducationStatus(True, level, "serie")
    return SpecialEducationStatus(False, None, None)


def _loaded(obj: Any, name: str) -> Any:
    """Valor já na memória. Não dispara lazy load do SQLAlchemy."""
    state = getattr(obj, "_sa_instance_state", None)
    if state is None:
        data = getattr(obj, "__dict__", None)
        if data is not None and name in data:
            return data[name]
        return _UNLOADED
    if name in state.unloaded:
        return _UNLOADED
    if name in state.dict:
        return state.dict.get(name)
    return _UNLOADED


def _student_key(student: Any) -> str:
    return str(getattr(student, "id", id(student)))


def _status_from_memory(student: Any) -> Optional[SpecialEducationStatus]:
    """Retorna status só se subturma e série já estiverem carregadas."""
    subturma_id = _loaded(student, "subturma_id")
    if subturma_id is _UNLOADED:
        return None
    subturma = None
    if subturma_id is not None:
        subturma = _loaded(student, "subturma")
        if subturma is _UNLOADED:
            return None

    grade = _loaded(student, "grade")
    if grade is _UNLOADED:
        classe = _loaded(student, "class_")
        if classe is _UNLOADED:
            if getattr(student, "grade_id", None) or getattr(student, "class_id", None):
                return None
            grade = None
        elif classe is None:
            grade = None
        else:
            grade = _loaded(classe, "grade")
            if grade is _UNLOADED:
                if getattr(classe, "grade_id", None):
                    return None
                grade = None
    return status_from_grade_and_subturma(
        student_class_id=getattr(student, "class_id", None),
        grade=grade,
        subturma=None if subturma_id is None else subturma,
    )


def is_special_education_many(students: Iterable[Any]) -> Dict[str, SpecialEducationStatus]:
    """
    Versão em lote. Uma consulta de turmas, uma de séries e uma de subturmas,
    só para os alunos cujo vínculo ainda não está na memória.
    """
    rows = [student for student in students if student is not None]
    result: Dict[str, SpecialEducationStatus] = {}
    pending = []
    for student in rows:
        status = _status_from_memory(student)
        if status is None:
            pending.append(student)
        else:
            result[_student_key(student)] = status
    if not pending:
        return result

    classes_by_id, grades_by_id, subturma_id_by_student, subturmas_by_id = _load_placement(pending)
    for student in pending:
        key = _student_key(student)
        classe = classes_by_id.get(str(getattr(student, "class_id", "") or ""))
        grade = None
        if classe is not None and getattr(classe, "grade_id", None) is not None:
            grade = grades_by_id.get(str(classe.grade_id))
        if grade is None and getattr(student, "grade_id", None) is not None:
            grade = grades_by_id.get(str(student.grade_id))
        sub_id = _loaded(student, "subturma_id")
        if sub_id is _UNLOADED:
            sub_id = subturma_id_by_student.get(key)
        subturma = subturmas_by_id.get(str(sub_id)) if sub_id else None
        result[key] = status_from_grade_and_subturma(
            student_class_id=getattr(student, "class_id", None),
            grade=grade,
            subturma=subturma,
        )
    return result


def is_special_education(student: Any) -> SpecialEducationStatus:
    """
    Verdadeiro se o aluno tem subturma ADAP da mesma turma, ou se a série atual
    é da etapa ADAP / chama-se Suporte N ou ADAP N. O nível vem junto, quando há.
    """
    if student is None:
        return SpecialEducationStatus(False, None, None)
    found = is_special_education_many([student])
    return found.get(_student_key(student), SpecialEducationStatus(False, None, None))


def _load_placement(students: Sequence[Any]):
    from app.models.grades import Grade
    from app.models.student import Student
    from app.models.studentClass import Class
    from app.models.subturma import Subturma

    class_ids = []
    grade_ids = []
    persistent_ids = []
    for student in students:
        if getattr(student, "class_id", None) is not None:
            class_ids.append(student.class_id)
        if getattr(student, "grade_id", None) is not None:
            grade_ids.append(student.grade_id)
        if isinstance(student, Student) and _loaded(student, "subturma_id") is _UNLOADED:
            persistent_ids.append(student.id)

    classes_by_id = {}
    if class_ids:
        for classe in Class.query.filter(Class.id.in_(class_ids)).all():
            classes_by_id[str(classe.id)] = classe
            if classe.grade_id is not None:
                grade_ids.append(classe.grade_id)

    grades_by_id = {}
    if grade_ids:
        for grade in Grade.query.filter(Grade.id.in_(grade_ids)).all():
            grades_by_id[str(grade.id)] = grade

    subturma_id_by_student = {}
    subturmas_by_id = {}
    if persistent_ids:
        id_rows = (
            Student.query.filter(Student.id.in_(persistent_ids))
            .with_entities(Student.id, Student.subturma_id)
            .all()
        )
        sub_ids = []
        for student_id, subturma_id in id_rows:
            subturma_id_by_student[str(student_id)] = subturma_id
            if subturma_id is not None:
                sub_ids.append(subturma_id)
        if sub_ids:
            for subturma in Subturma.query.filter(Subturma.id.in_(sub_ids)).all():
                subturmas_by_id[str(subturma.id)] = subturma
    return classes_by_id, grades_by_id, subturma_id_by_student, subturmas_by_id
