# -*- coding: utf-8 -*-
"""Recorte de alunos da prova subjetiva entre turma regular e subturma ADAP."""
from types import SimpleNamespace

from app.services.subjective_evaluation_service import SubjectiveEvaluationService


def _aluno(student_id, class_id, subturma_id=None, name="Aluno"):
    return SimpleNamespace(id=student_id, class_id=class_id, subturma_id=subturma_id, name=name)


def test_turma_inteira_deixa_de_fora_a_subturma_escolhida():
    turma = {"id": "turma-a", "name": "A", "school_id": "escola"}
    subturma = {
        "id": "adap-3",
        "class_id": "turma-a",
        "class_name": "A",
        "grade_name": "5º Ano",
        "school_id": "escola",
        "support_level": 3,
    }
    alunos = [
        _aluno("regular", "turma-a", name="Bruno"),
        _aluno("adap", "turma-a", "adap-3", name="Ana"),
        _aluno("outro-adap", "turma-a", "adap-1", name="Caio"),
    ]

    recortes = SubjectiveEvaluationService.partition_subjective_audience(alunos, [turma], [subturma])

    inteira = next(item for item in recortes if item["subturma_id"] is None)
    adap = next(item for item in recortes if item["subturma_id"] == "adap-3")
    assert [aluno.id for aluno in inteira["students"]] == ["regular", "outro-adap"]
    assert [aluno.id for aluno in adap["students"]] == ["adap"]
    assert adap["name"] == "5º Ano A ADAP 3"


def test_so_a_subturma_nao_traz_o_resto_da_turma():
    subturma = {
        "id": "adap-3",
        "class_id": "turma-a",
        "class_name": "A",
        "school_id": "escola",
        "support_level": 3,
    }
    alunos = [
        _aluno("regular", "turma-a", name="Bruno"),
        _aluno("adap", "turma-a", "adap-3", name="Ana"),
    ]

    recortes = SubjectiveEvaluationService.partition_subjective_audience(alunos, [], [subturma])

    assert len(recortes) == 1
    assert [aluno.id for aluno in recortes[0]["students"]] == ["adap"]


def test_abre_o_unico_recorte_sem_subturma_id():
    recortes = [{
        "class_id": "turma-a",
        "subturma_id": "adap-3",
        "name": "A — ADAP 3",
        "students": [],
    }]
    escolhido, erro = SubjectiveEvaluationService.select_audience_slice(recortes, "turma-a")
    assert erro is None
    assert escolhido["subturma_id"] == "adap-3"


def test_rotulo_junta_serie_turma_e_nivel():
    assert SubjectiveEvaluationService.adap_option_name("5º Ano", "A", 3) == "5º Ano A ADAP 3"


def test_dois_adap_na_mesma_turma_pedem_subturma_id():
    recortes = [
        {"class_id": "turma-a", "subturma_id": "adap-1", "name": "A — ADAP 1", "students": []},
        {"class_id": "turma-a", "subturma_id": "adap-3", "name": "A — ADAP 3", "students": []},
    ]
    escolhido, erro = SubjectiveEvaluationService.select_audience_slice(recortes, "turma-a")
    assert escolhido is None
    assert erro == "subturma_required"
