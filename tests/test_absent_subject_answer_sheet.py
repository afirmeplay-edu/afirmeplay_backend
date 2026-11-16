# -*- coding: utf-8 -*-
"""Disciplina ausente no cartão (bloco 100% em branco) ≠ nota 0."""

from app.services.cartao_resposta.proficiency_by_subject import (
    SUBJECT_ABSENT_CLASSIFICATION,
    calcular_proficiencia_por_disciplina,
    is_subject_entry_absent,
    iter_scored_subject_entries,
    make_absent_subject_entry,
    subject_questions_all_blank,
)


PORT_ID = "subj-port"
MAT_ID = "subj-mat"

BLOCKS = {
    "topology": {
        "blocks": [
            {
                "block_id": 1,
                "subject_id": PORT_ID,
                "subject_name": "Português",
                "questions": [{"q": i} for i in range(1, 21)],
            },
            {
                "block_id": 2,
                "subject_id": MAT_ID,
                "subject_name": "Matemática",
                "questions": [{"q": i} for i in range(21, 41)],
            },
        ]
    }
}

GABARITO = {i: "A" for i in range(1, 41)}


def _answers_only_math_all_correct():
    out = {i: None for i in range(1, 21)}
    out.update({i: "A" for i in range(21, 41)})
    return out


def _answers_only_port_all_wrong():
    out = {i: "B" for i in range(1, 21)}
    out.update({i: None for i in range(21, 41)})
    return out


def _answers_both_marked_all_wrong():
    return {i: "B" for i in range(1, 41)}


def _answers_both_half():
    out = {}
    for i in range(1, 41):
        out[i] = "A" if i % 2 == 0 else "B"
    return out


def _answers_all_blank():
    return {i: None for i in range(1, 41)}


def test_helpers_blank_and_absent_entry():
    assert subject_questions_all_blank(list(range(1, 21)), _answers_only_math_all_correct())
    assert not subject_questions_all_blank(list(range(21, 41)), _answers_only_math_all_correct())
    entry = make_absent_subject_entry("Português", 20)
    assert is_subject_entry_absent(entry)
    assert entry["classification"] == SUBJECT_ABSENT_CLASSIFICATION
    assert entry["grade"] is None
    assert entry["proficiency"] is None


def test_ausente_portugues_fez_matematica():
    pbs, prof_m, grade_m, classif, _ = calcular_proficiencia_por_disciplina(
        BLOCKS,
        _answers_only_math_all_correct(),
        GABARITO,
        grade_name="1º Ano",
    )
    assert is_subject_entry_absent(pbs[PORT_ID])
    assert not is_subject_entry_absent(pbs[MAT_ID])
    assert pbs[PORT_ID]["grade"] is None
    assert pbs[MAT_ID]["correct_answers"] == 20
    scored = list(iter_scored_subject_entries(pbs))
    assert len(scored) == 1
    assert scored[0][0] == MAT_ID
    # Geral = só Matemática
    assert prof_m == pbs[MAT_ID]["proficiency"]
    assert grade_m == pbs[MAT_ID]["grade"]
    assert classif != SUBJECT_ABSENT_CLASSIFICATION


def test_ausente_matematica_fez_portugues():
    pbs, prof_m, grade_m, classif, _ = calcular_proficiencia_por_disciplina(
        BLOCKS,
        _answers_only_port_all_wrong(),
        GABARITO,
        grade_name="1º Ano",
    )
    assert is_subject_entry_absent(pbs[MAT_ID])
    assert not is_subject_entry_absent(pbs[PORT_ID])
    assert pbs[PORT_ID]["correct_answers"] == 0
    assert pbs[PORT_ID]["grade"] == 0 or float(pbs[PORT_ID]["grade"]) == 0.0
    assert len(list(iter_scored_subject_entries(pbs))) == 1
    assert prof_m == pbs[PORT_ID]["proficiency"]


def test_marcou_e_errou_tudo_continua_zero():
    pbs, prof_m, grade_m, classif, _ = calcular_proficiencia_por_disciplina(
        BLOCKS,
        _answers_both_marked_all_wrong(),
        GABARITO,
        grade_name="1º Ano",
    )
    assert not is_subject_entry_absent(pbs[PORT_ID])
    assert not is_subject_entry_absent(pbs[MAT_ID])
    assert float(pbs[PORT_ID]["grade"]) == 0.0
    assert float(pbs[MAT_ID]["grade"]) == 0.0
    assert float(prof_m) == 0.0
    assert float(grade_m) == 0.0


def test_fez_as_duas_disciplinas():
    pbs, prof_m, grade_m, classif, _ = calcular_proficiencia_por_disciplina(
        BLOCKS,
        _answers_both_half(),
        GABARITO,
        grade_name="1º Ano",
    )
    assert not is_subject_entry_absent(pbs[PORT_ID])
    assert not is_subject_entry_absent(pbs[MAT_ID])
    assert len(list(iter_scored_subject_entries(pbs))) == 2
    assert float(prof_m) > 0
    assert float(grade_m) > 0


def test_cartao_sem_nenhuma_marcacao():
    pbs, prof_m, grade_m, classif, _ = calcular_proficiencia_por_disciplina(
        BLOCKS,
        _answers_all_blank(),
        GABARITO,
        grade_name="1º Ano",
    )
    assert is_subject_entry_absent(pbs[PORT_ID])
    assert is_subject_entry_absent(pbs[MAT_ID])
    assert list(iter_scored_subject_entries(pbs)) == []
    assert float(prof_m) == 0.0
    assert float(grade_m) == 0.0
    assert classif == SUBJECT_ABSENT_CLASSIFICATION


def test_agregacao_turma_escola_ignora_ausente():
    """Simula média de Português na turma: aluno ausente em LP não entra."""
    from collections import defaultdict

    # Aluno A: fez LP (prof 175)
    # Aluno B: ausente em LP (não entra)
    # Aluno C: fez LP (prof 225)
    rows_a = [
        {"student_id": "a", "class_id": "t1", "proficiency": 175.0, "grade": 4.58},
        {"student_id": "c", "class_id": "t1", "proficiency": 225.0, "grade": 6.4},
    ]
    # B ausente → não está em rows
    by_class = defaultdict(list)
    for r in rows_a:
        by_class[r["class_id"]].append((r["grade"], r["proficiency"]))
    turma_means = [
        (sum(g for g, _ in vals) / len(vals), sum(p for _, p in vals) / len(vals))
        for vals in by_class.values()
        if vals
    ]
    media_prof = sum(p for _, p in turma_means) / len(turma_means)
    assert abs(media_prof - 200.0) < 0.01
    # Se B entrasse com 0: (175+0+225)/3 = 133.33 — regressão que queremos evitar
    assert media_prof > 150
