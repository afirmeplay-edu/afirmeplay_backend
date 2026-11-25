# -*- coding: utf-8 -*-
"""
Cálculo de proficiência por disciplina para cartões resposta.
Usa blocks_config (com subject_id por bloco) para agregar acertos por disciplina
e calcular proficiência e classificação por disciplina e média geral.

Disciplina AUSENTE: todas as questões do bloco estão null/em branco em
detected_answers. Não entra em média/proficiência/avaliados; no JSON fica com
absent=true (sem migration).
"""

import logging
from typing import Dict, List, Any, Tuple, Optional, Iterator, Iterable
from app.services.cartao_resposta.course_name_resolver import (
    infer_course_name_from_grade,
    resolve_grade_name_for_proficiency,
)

logger = logging.getLogger(__name__)

SUBJECT_ABSENT_CLASSIFICATION = "Ausente"
SUBJECT_ABSENT_STATUS = "ausente"


def _get_course_name_from_grade(grade_name: str) -> str:
    """
    Compatibilidade retroativa: mantém API antiga usada por rotas.
    """
    return infer_course_name_from_grade(grade_name)


def _resolve_subject_name(subject_id: str, subject_name: Optional[str]) -> str:
    """Retorna subject_name; se vazio, tenta buscar do modelo Subject."""
    if subject_name and str(subject_name).strip():
        return str(subject_name).strip()
    try:
        from app.models.subject import Subject
        obj = Subject.query.get(str(subject_id))
        if obj and getattr(obj, 'name', None):
            return obj.name
    except Exception as e:
        logger.debug(f"Erro ao buscar Subject por id {subject_id}: {e}")
    return 'Outras'


def _answer_value(answers: Optional[Dict], question_number: int) -> Optional[str]:
    """Lê resposta da questão aceitando chave int ou str."""
    if not isinstance(answers, dict):
        return None
    if question_number in answers:
        raw = answers.get(question_number)
    elif str(question_number) in answers:
        raw = answers.get(str(question_number))
    else:
        return None
    if raw is None:
        return None
    text = str(raw).strip()
    if not text or text.upper() in ("NONE", "NULL"):
        return None
    return text


def subject_questions_all_blank(
    question_numbers: Iterable[int],
    answers: Optional[Dict],
) -> bool:
    """True se o bloco tem questões e todas estão sem marcação."""
    nums = [int(q) for q in (question_numbers or [])]
    if not nums:
        return False
    return all(_answer_value(answers, q) is None for q in nums)


def make_absent_subject_entry(subject_name: str, total_questions: int) -> Dict[str, Any]:
    """Entrada JSON de disciplina ausente (sem nota/proficiência)."""
    return {
        "subject_name": subject_name or "Outras",
        "absent": True,
        "status": SUBJECT_ABSENT_STATUS,
        "proficiency": None,
        "grade": None,
        "classification": SUBJECT_ABSENT_CLASSIFICATION,
        "correct_answers": 0,
        "total_questions": int(total_questions or 0),
        "answered_questions": 0,
    }


def is_subject_entry_absent(entry: Any) -> bool:
    """True quando a disciplina foi marcada como ausente no proficiency_by_subject."""
    if not isinstance(entry, dict):
        return False
    if entry.get("absent") is True:
        return True
    status = str(entry.get("status") or "").strip().lower()
    if status == SUBJECT_ABSENT_STATUS:
        return True
    if entry.get("grade") is None and entry.get("proficiency") is None:
        cl = str(entry.get("classification") or "").strip().lower()
        if cl == SUBJECT_ABSENT_CLASSIFICATION.lower():
            return True
    return False


def subject_is_absent(
    entry: Any,
    question_numbers: Iterable[int],
    answers: Optional[Dict],
) -> bool:
    """Disciplina ausente: marcada como ausente no JSON ou bloco 100% em branco.

    Regra única do cartão-resposta: ausente marcado e bloco em branco são a mesma coisa.
    """
    return is_subject_entry_absent(entry) or subject_questions_all_blank(
        question_numbers, answers
    )


def _question_numbers_by_subject(blocks_config: Optional[Dict]) -> Dict[str, List[int]]:
    """Agrupa as questões por disciplina (vários blocos da mesma disciplina somam)."""
    by_subject: Dict[str, List[int]] = {}
    for block in _extract_blocks_with_questions(blocks_config):
        sid = block.get("subject_id") or f"block_{block.get('block_id', 0)}"
        by_subject.setdefault(str(sid), []).extend(
            int(q) for q in (block.get("question_numbers") or [])
        )
    return by_subject


def result_absent_in_all_subjects(
    proficiency_by_subject: Any,
    detected_answers: Any,
    blocks_config: Optional[Dict],
    fallback_question_numbers: Optional[Iterable[int]] = None,
) -> bool:
    """True se o resultado do cartão é de aluno ausente em todas as disciplinas.

    Um resultado assim não conta como participação. ``fallback_question_numbers``
    (ex.: questões do gabarito) vale para gabarito sem blocos por disciplina.
    """
    pbs = proficiency_by_subject or {}
    if isinstance(pbs, str):
        import json

        try:
            pbs = json.loads(pbs) or {}
        except Exception:
            pbs = {}
    if not isinstance(pbs, dict):
        pbs = {}
    answers = parse_detected_answers_map(detected_answers)

    subjects = _question_numbers_by_subject(blocks_config)
    if not subjects:
        qnums = list(fallback_question_numbers or answers.keys())
        if not qnums:
            return False
        subjects = {"geral": qnums}

    if detected_answers is None:
        # Sem respostas gravadas não dá para afirmar "em branco": só vale o que está
        # marcado como ausente no JSON (não tira da participação por falta de dado).
        return all(is_subject_entry_absent(pbs.get(sid)) for sid in subjects)

    return all(
        subject_is_absent(pbs.get(sid), qnums, answers)
        for sid, qnums in subjects.items()
    )


def iter_scored_subject_entries(
    proficiency_by_subject: Optional[Dict],
) -> Iterator[Tuple[str, Dict[str, Any]]]:
    """Yield (subject_id, data) só das disciplinas com nota/proficiência válidas."""
    if not isinstance(proficiency_by_subject, dict):
        return
    for sid, data in proficiency_by_subject.items():
        if not isinstance(data, dict):
            continue
        if is_subject_entry_absent(data):
            continue
        if data.get("proficiency") is None and data.get("grade") is None:
            continue
        yield str(sid), data


def parse_detected_answers_map(raw: Any) -> Dict[int, Optional[str]]:
    """Normaliza detected_answers para {int: str|None}."""
    payload = raw or {}
    if isinstance(payload, str):
        import json
        try:
            payload = json.loads(payload) or {}
        except Exception:
            return {}
    if not isinstance(payload, dict):
        return {}
    out: Dict[int, Optional[str]] = {}
    for k, v in payload.items():
        try:
            q = int(k)
        except (TypeError, ValueError):
            continue
        out[q] = _answer_value({q: v}, q)
    return out


def legacy_subject_blank_from_answers(
    entry: Optional[Dict[str, Any]],
    *,
    subject_id: str,
    blocks_config: Optional[Dict] = None,
    detected_answers: Any = None,
) -> bool:
    """
    Fallback de leitura para cartões antigos (ainda com nota 0 gravada):
    se o bloco da disciplina está 100% em branco em detected_answers, trata como ausente.
    """
    if is_subject_entry_absent(entry):
        return True
    answers = parse_detected_answers_map(detected_answers)
    if not answers and detected_answers is None:
        return False
    blocks = _extract_blocks_with_questions(blocks_config)
    qnums: List[int] = []
    sid = str(subject_id)
    for block in blocks:
        bid = block.get("subject_id")
        if not bid:
            bid = f"block_{block.get('block_id', 0)}"
        if str(bid) != sid:
            continue
        qnums.extend(int(q) for q in (block.get("question_numbers") or []))
    if not qnums:
        return False
    return subject_questions_all_blank(qnums, answers)


def sql_jsonb_subject_scored(pbs_column, storage_key):
    """
    Cláusula SQLAlchemy: disciplina presente no JSON e não ausente.
    Uso em Ranking/Dashboard ao filtrar por disciplina do cartão.
    """
    from sqlalchemy import and_, or_, cast, Float

    entry = pbs_column[storage_key]
    absent_txt = entry["absent"].astext
    not_absent = or_(absent_txt.is_(None), absent_txt != "true")
    has_prof = cast(entry["proficiency"].astext, Float).isnot(None)
    return and_(not_absent, has_prof)


def infer_has_matematica_from_blocks_config(blocks_config: Optional[Dict]) -> bool:
    """
    Determina se a prova/gabarito possui Matemática olhando para blocks_config/topology.

    Regras:
    - Se qualquer bloco (ou disciplina resolvida) contiver "matem" no nome -> True
    - Caso contrário -> False
    """
    blocks = _extract_blocks_with_questions(blocks_config)
    if not blocks:
        return False
    for block in blocks:
        subject_id = block.get('subject_id')
        subject_name = _resolve_subject_name(str(subject_id) if subject_id else "", block.get('subject_name'))
        if subject_name and "matem" in subject_name.lower():
            return True
    return False


def course_name_and_has_matematica_for_gabarito(
    gabarito_id: Optional[str],
    serie_id: Optional[str] = None,
) -> Tuple[str, bool]:
    """
    Curso (a partir da série do gabarito / filtro serie — NUNCA do title) e se inclui Matemática.
    Usado em agregações/API para alinhar regra do GERAL.

    Fallback de has_matematica: se blocks_config não indicar, usa "matem" no título só como
    heurística de disciplina (não de série).
    """
    if not gabarito_id:
        return "", False
    try:
        from app.models.answerSheetGabarito import AnswerSheetGabarito
        from app.services.cartao_resposta.gabarito_grades import course_meta_for_gabarito_serie

        gab = AnswerSheetGabarito.query.get(str(gabarito_id).strip())
        if not gab:
            return "", False
        course_name, grade_label, _ = course_meta_for_gabarito_serie(gab, serie_id)
        if not course_name:
            # Única série resolvível via resolver clássico (sem title)
            grade_name = resolve_grade_name_for_proficiency(gabarito_obj=gab)
            course_name = infer_course_name_from_grade(grade_name) if grade_name else ""
        bc = getattr(gab, "blocks_config", None) or {}
        if isinstance(bc, str):
            import json

            try:
                bc = json.loads(bc) or {}
            except Exception:
                bc = {}
        if not isinstance(bc, dict):
            bc = {}
        has_matematica = infer_has_matematica_from_blocks_config(bc)
        if not has_matematica:
            title = (gab.title or "").lower()
            if "matem" in title:
                has_matematica = True
        return course_name or "", has_matematica
    except Exception as e:
        logger.debug("course_name_and_has_matematica_for_gabarito: %s", e)
        return "", False


def calcular_proficiencia_por_disciplina(
    blocks_config: Optional[Dict],
    validated_answers: Dict[int, Optional[str]],
    gabarito_dict: Dict[int, str],
    grade_name: str = '',
    gabarito_obj: Any = None,
    student: Any = None,
) -> Tuple[Dict[str, Any], float, float, str, bool]:
    """
    Calcula proficiência e classificação por disciplina e média geral.

    Args:
        blocks_config: Config do gabarito (topology.blocks ou blocks com subject_id).
        validated_answers: Respostas detectadas { num_questao: "A"|None, ... }.
        gabarito_dict: Respostas corretas { num_questao: "A", ... }.
        grade_name: Nome da série para inferir nível do curso (opcional se gabarito_obj/student).
        gabarito_obj: Gabarito (grade_name, grade_id, scope_snapshot, title).
        student: Aluno (fallback: série da turma).

    Returns:
        (proficiency_by_subject, proficiency_media, grade_media, classification_geral, has_matematica)
        - disciplina 100% em branco: absent=true (não entra na média geral)
        - média geral: só disciplinas feitas
    """
    from app.services.evaluation_calculator import EvaluationCalculator

    effective_grade_name = resolve_grade_name_for_proficiency(
        gabarito_obj=gabarito_obj,
        grade_name=grade_name,
        student=student,
    )
    course_name = infer_course_name_from_grade(effective_grade_name)
    proficiency_by_subject = {}
    blocks = _extract_blocks_with_questions(blocks_config)
    has_matematica_prova = infer_has_matematica_from_blocks_config(blocks_config)
    answers = parse_detected_answers_map(validated_answers)
    if not blocks:
        # Fallback: um único bloco com todas as questões (sem subject_id)
        all_q = list(gabarito_dict.keys())
        if all_q:
            if subject_questions_all_blank(all_q, answers):
                # Cartão sem marcação: o fluxo de correção não deve persistir;
                # devolve ausente explícito para quem chamar direto.
                proficiency_by_subject['geral'] = make_absent_subject_entry('Outras', len(all_q))
                return proficiency_by_subject, 0.0, 0.0, SUBJECT_ABSENT_CLASSIFICATION, False
            # Denominador = total de questões (em branco conta como erro)
            total = len(all_q)
            correct = sum(
                1
                for q in all_q
                if answers.get(q) is not None
                and answers.get(q) == (str(gabarito_dict.get(q)).strip().upper() if gabarito_dict.get(q) is not None else None)
            )
            subject_name = 'Outras'
            prof = EvaluationCalculator.calculate_proficiency(
                correct, total, course_name, subject_name
            )
            classification = EvaluationCalculator.determine_classification(
                prof, course_name, subject_name
            )
            grade = EvaluationCalculator.calculate_grade(
                prof, course_name, subject_name,
                use_simple_calculation=False
            )
            proficiency_by_subject['geral'] = {
                'subject_name': subject_name,
                'absent': False,
                'status': 'avaliado',
                'proficiency': prof,
                'classification': classification,
                'grade': grade,
                'correct_answers': correct,
                'total_questions': total,
                'answered_questions': sum(1 for q in all_q if answers.get(q) is not None),
            }
            return proficiency_by_subject, prof, grade, classification, False
        return {}, 0.0, 0.0, 'Não calculado', False

    # Agrupar por subject_id (questões podem estar em vários blocos da mesma disciplina)
    questions_by_subject: Dict[str, List[int]] = {}
    subject_names: Dict[str, str] = {}
    for block in blocks:
        subject_id = block.get('subject_id')
        if not subject_id:
            subject_id = f"block_{block.get('block_id', 0)}"
        subject_id = str(subject_id)
        subject_name = _resolve_subject_name(subject_id, block.get('subject_name'))
        subject_names[subject_id] = subject_name
        q_list = block.get('question_numbers', [])
        if subject_id not in questions_by_subject:
            questions_by_subject[subject_id] = []
        questions_by_subject[subject_id].extend(q_list)

    for subject_id, question_numbers in questions_by_subject.items():
        if not question_numbers:
            continue
        total = len(question_numbers)
        subject_name = subject_names.get(subject_id, 'Outras')
        if subject_questions_all_blank(question_numbers, answers):
            proficiency_by_subject[subject_id] = make_absent_subject_entry(subject_name, total)
            continue
        # Denominador = total de questões da disciplina (em branco conta como erro)
        correct = sum(
            1
            for q in question_numbers
            if answers.get(q) is not None
            and answers.get(q) == (
                str(gabarito_dict.get(q)).strip().upper()
                if gabarito_dict.get(q) is not None
                else None
            )
        )
        answered = sum(1 for q in question_numbers if answers.get(q) is not None)
        proficiency = EvaluationCalculator.calculate_proficiency(
            correct, total, course_name, subject_name
        )
        classification = EvaluationCalculator.determine_classification(
            proficiency, course_name, subject_name
        )
        grade = EvaluationCalculator.calculate_grade(
            proficiency, course_name, subject_name,
            use_simple_calculation=False
        )
        proficiency_by_subject[subject_id] = {
            'subject_name': subject_name,
            'absent': False,
            'status': 'avaliado',
            'proficiency': round(proficiency, 2),
            'classification': classification,
            'grade': grade,
            'correct_answers': correct,
            'total_questions': total,
            'answered_questions': answered,
        }

    scored = list(iter_scored_subject_entries(proficiency_by_subject))
    if not scored:
        # Só ausentes (ou vazio): sem média numérica
        return proficiency_by_subject, 0.0, 0.0, SUBJECT_ABSENT_CLASSIFICATION, has_matematica_prova

    proficiencies = [float(v['proficiency']) for _sid, v in scored]
    grades = [float(v['grade']) for _sid, v in scored]
    proficiency_media = round(sum(proficiencies) / len(proficiencies), 2)
    # Nota geral = média das notas por disciplina feitas
    grade_media = round(sum(grades) / len(grades), 2)
    has_matematica_scored = any(
        "matem" in str(v.get("subject_name") or "").lower() for _sid, v in scored
    )
    classification_geral = EvaluationCalculator.determine_classification(
        proficiency_media, course_name, 'GERAL', has_matematica=has_matematica_scored
    )
    return proficiency_by_subject, proficiency_media, grade_media, classification_geral, has_matematica_prova


def _extract_blocks_with_questions(blocks_config: Optional[Dict]) -> List[Dict]:
    """
    Extrai lista de blocos com subject_id/subject_name e lista de números de questão.
    Preferência: topology.blocks (com questions[].q), senão blocks (com start_question/end_question).
    """
    if not blocks_config:
        return []
    if isinstance(blocks_config, str):
        import json
        try:
            blocks_config = json.loads(blocks_config) or {}
        except Exception:
            return []
    if not isinstance(blocks_config, dict):
        return []
    blocks = blocks_config.get('topology', {}).get('blocks', [])
    if not blocks:
        blocks = blocks_config.get('blocks', [])
    if not blocks:
        return []

    result = []
    for block in blocks:
        subject_id = block.get('subject_id')
        subject_name = block.get('subject_name')
        block_id = block.get('block_id')
        question_numbers = []
        if 'questions' in block:
            for q_item in block.get('questions', []):
                q_num = q_item.get('q') if isinstance(q_item, dict) else q_item
                if q_num is not None:
                    question_numbers.append(int(q_num))
        else:
            start_q = block.get('start_question')
            end_q = block.get('end_question')
            if start_q is not None and end_q is not None:
                question_numbers = list(range(int(start_q), int(end_q) + 1))
        if question_numbers:
            result.append({
                'block_id': block_id,
                'subject_id': subject_id,
                'subject_name': subject_name,
                'question_numbers': question_numbers,
            })
    return result
