# -*- coding: utf-8 -*-
"""Público do cartão-resposta: turma inteira ou subturma ADAP 1 / ADAP 2."""
from types import SimpleNamespace

import pytest

from app.services.cartao_resposta import answer_sheet_audience as audience_mod
from app.services.cartao_resposta.answer_sheet_audience import (
    GenerationAudienceError,
    audience_from_snapshots,
    cartao_adap_label,
    check_generation_compatible,
    check_generation_subturmas,
    resolve_generation_subturmas,
)

TURMA = "11111111-1111-1111-1111-111111111111"
OUTRA_TURMA = "22222222-2222-2222-2222-222222222222"
ADAP1 = "aaaaaaaa-0000-0000-0000-000000000001"
ADAP2 = "aaaaaaaa-0000-0000-0000-000000000002"
ADAP3 = "aaaaaaaa-0000-0000-0000-000000000003"
CIDADE = "cidade-1"


def _aluno(student_id, class_id=TURMA, subturma_id=None):
    return SimpleNamespace(id=student_id, class_id=class_id, subturma_id=subturma_id)


def _linha(**extra):
    base = {
        "subturma_id": ADAP1,
        "level": 1,
        "school_city_id": CIDADE,
        "parent_is_special": False,
        "students_count": 2,
        "label": "5º Ano A – ADAP 1",
    }
    base.update(extra)
    return base


def _snapshot_adap(*entries, level=1):
    return {
        "scope": "city",
        "publico": "adap",
        "support_level": level,
        "subturma_ids": [sub for _, sub in entries],
        "class_ids": [
            {"class_id": cid, "subturma_id": sub, "support_level": level, "label": "x"}
            for cid, sub in entries
        ],
    }


def _snapshot_regular(*class_ids):
    return {"scope": "city", "class_ids": [{"class_id": cid, "label": "x"} for cid in class_ids]}


# --- rótulo -----------------------------------------------------------------

def test_rotulo_serie_turma_e_nivel():
    assert cartao_adap_label("5º Ano", "A", 1) == "5º Ano A – ADAP 1"
    assert cartao_adap_label("", "", 2) == "ADAP 2"


# --- validação da geração ---------------------------------------------------

def test_geracao_valida_devolve_o_nivel():
    assert check_generation_subturmas([_linha(), _linha(subturma_id="b")], city_id=CIDADE) == 1


def test_adap_3_e_rejeitado():
    with pytest.raises(GenerationAudienceError) as err:
        check_generation_subturmas([_linha(level=3, subturma_id=ADAP3)], city_id=CIDADE)
    assert err.value.code == "subturma_level_not_allowed"


def test_niveis_misturados_sao_rejeitados():
    with pytest.raises(GenerationAudienceError) as err:
        check_generation_subturmas([_linha(), _linha(level=2, subturma_id=ADAP2)], city_id=CIDADE)
    assert err.value.code == "subturma_mixed_levels"


def test_subturma_vazia_e_rejeitada():
    with pytest.raises(GenerationAudienceError) as err:
        check_generation_subturmas([_linha(students_count=0)], city_id=CIDADE)
    assert err.value.code == "subturma_empty"
    assert err.value.details == ["5º Ano A – ADAP 1"]


def test_subturma_de_outro_municipio_e_rejeitada():
    with pytest.raises(GenerationAudienceError) as err:
        check_generation_subturmas([_linha(school_city_id="outra")], city_id=CIDADE)
    assert err.value.code == "subturma_out_of_city"


def test_turma_mae_de_serie_suporte_e_rejeitada():
    with pytest.raises(GenerationAudienceError) as err:
        check_generation_subturmas([_linha(parent_is_special=True)], city_id=CIDADE)
    assert err.value.code == "subturma_parent_special"


def test_mistura_com_turmas_regulares_e_rejeitada_antes_do_banco():
    with pytest.raises(GenerationAudienceError) as err:
        resolve_generation_subturmas([ADAP1], city_id=CIDADE, class_ids=[TURMA])
    assert err.value.code == "subturma_mixed_with_classes"


def test_id_invalido_ou_repetido_e_rejeitado_antes_do_banco():
    for ids in (["nao-e-uuid"], [ADAP1, ADAP1]):
        with pytest.raises(GenerationAudienceError) as err:
            resolve_generation_subturmas(ids, city_id=CIDADE)
        assert err.value.code == "subturma_not_found"


# --- público do gabarito ----------------------------------------------------

def test_sem_subturma_ids_vale_a_turma_inteira():
    audience = audience_from_snapshots([_snapshot_regular(TURMA)])
    assert audience.publico == "regular"
    assert audience.student_criterion() is None
    alunos = [_aluno("regular"), _aluno("adap", subturma_id=ADAP1)]
    assert audience.filter_students(alunos) == alunos


def test_gabarito_sem_geracao_nao_recorta():
    audience = audience_from_snapshots([])
    assert audience.publico == "regular"
    assert audience.allows(TURMA, None) is True


def test_gabarito_adap_so_inclui_alunos_da_subturma():
    audience = audience_from_snapshots([_snapshot_adap((TURMA, ADAP1))])
    alunos = [
        _aluno("regular"),
        _aluno("adap1-a", subturma_id=ADAP1),
        _aluno("adap1-b", subturma_id=ADAP1),
        _aluno("adap2", subturma_id=ADAP2),
        _aluno("adap3", subturma_id=ADAP3),
        _aluno("outra-turma", class_id=OUTRA_TURMA),
    ]
    assert audience.publico == "adap"
    assert audience.levels == {1}
    assert [a.id for a in audience.filter_students(alunos)] == ["adap1-a", "adap1-b"]
    assert audience.student_criterion() is not None


def test_turma_inteira_em_outra_geracao_prevalece():
    audience = audience_from_snapshots([
        _snapshot_adap((TURMA, ADAP1)),
        _snapshot_regular(TURMA),
    ])
    assert audience.publico == "regular"
    assert audience.allows(TURMA, None) is True


def test_gabarito_misto_recorta_so_a_turma_adap():
    audience = audience_from_snapshots([
        _snapshot_adap((TURMA, ADAP1)),
        _snapshot_regular(OUTRA_TURMA),
    ])
    assert audience.publico == "misto"
    assert audience.allows(OUTRA_TURMA, None) is True
    assert audience.allows(TURMA, None) is False
    assert audience.allows(TURMA, ADAP1) is True


def test_snapshot_antigo_com_lista_de_uuids_vale_turma_inteira():
    audience = audience_from_snapshots([{"class_ids": [TURMA, OUTRA_TURMA]}])
    assert audience.publico == "regular"
    assert audience.whole == {TURMA, OUTRA_TURMA}


def test_to_dict_expoe_publico_e_niveis():
    audience = audience_from_snapshots([_snapshot_adap((TURMA, ADAP2), level=2)])
    assert audience.to_dict() == {"publico": "adap", "adap_niveis": [2], "subturma_ids": [ADAP2]}


# --- compatibilidade entre gerações do mesmo gabarito -----------------------

def test_gabarito_novo_aceita_qualquer_publico():
    vazio = audience_from_snapshots([])
    check_generation_compatible(vazio, None)
    check_generation_compatible(vazio, 1)


def test_gabarito_regular_continua_aceitando_regular():
    check_generation_compatible(audience_from_snapshots([_snapshot_regular(TURMA)]), None)


def test_gabarito_regular_nao_recebe_adap():
    with pytest.raises(GenerationAudienceError) as err:
        check_generation_compatible(audience_from_snapshots([_snapshot_regular(TURMA)]), 1)
    assert err.value.code == "gabarito_publico_conflict"


def test_gabarito_adap_nao_recebe_regular_nem_outro_nivel():
    adap1 = audience_from_snapshots([_snapshot_adap((TURMA, ADAP1))])
    check_generation_compatible(adap1, 1)
    for level in (None, 2):
        with pytest.raises(GenerationAudienceError):
            check_generation_compatible(adap1, level)


# --- opções do seletor: cartão x subjetiva ----------------------------------

def test_opcoes_do_cartao_pedem_so_adap_1_e_2_com_aluno(monkeypatch):
    chamadas = {}

    def fake_rows(**kwargs):
        chamadas.update(kwargs)
        return []

    import app.services.subturma_options as subturma_options

    monkeypatch.setattr(subturma_options, "list_subturma_rows", fake_rows)
    audience_mod.list_cartao_adap_options(school_ids=["escola"], grade_ids=["serie"])
    assert tuple(chamadas["levels"]) == (1, 2)
    assert chamadas["only_with_students"] is True
    assert chamadas["exclude_special_parent"] is True


def test_subjetiva_continua_listando_todos_os_niveis_e_subturmas_vazias(monkeypatch):
    from app.services.special_education import ADAP_EDUCATION_STAGE_ID
    from app.services.subjective_evaluation_service import SubjectiveEvaluationService
    import app.services.subturma_options as subturma_options

    chamadas = {}
    linhas = [
        {
            "subturma": SimpleNamespace(id=ADAP3, support_level=3),
            "class": SimpleNamespace(id=TURMA, name="A"),
            "grade": SimpleNamespace(id="serie", name="5º Ano"),
            "school": None,
            "students_count": 0,
        }
    ]

    def fake_rows(**kwargs):
        chamadas.update(kwargs)
        return linhas

    monkeypatch.setattr(subturma_options, "list_subturma_rows", fake_rows)
    payload = SubjectiveEvaluationService.list_available_classes(
        education_stage_id=ADAP_EDUCATION_STAGE_ID,
        grade_id="serie",
        school_id="escola",
        user={"role": "admin"},
    )
    assert "levels" not in chamadas and "only_with_students" not in chamadas
    assert chamadas["grade_ids"] == ["serie"] and chamadas["school_ids"] == ["escola"]
    assert payload["classes"] == [{
        "id": ADAP3,
        "class_id": TURMA,
        "subturma_id": ADAP3,
        "support_level": 3,
        "name": "5º Ano A ADAP 3",
        "students_count": 0,
        "school": None,
        "grade": {"id": "serie", "name": "5º Ano"},
        "grade_id": "serie",
    }]


def test_payload_da_opcao_usa_id_da_subturma_e_rotulo_do_cartao():
    row = {
        "subturma": SimpleNamespace(id=ADAP1, support_level=1),
        "class": SimpleNamespace(id=TURMA, name="A", shift="Manhã", school_id="escola"),
        "grade": SimpleNamespace(id="serie", name="5º Ano"),
        "school": SimpleNamespace(name="Escola Teste"),
        "students_count": 2,
    }
    payload = audience_mod.adap_option_payload(row)
    assert payload["id"] == ADAP1
    assert payload["class_id"] == TURMA
    assert payload["name"] == "5º Ano A – ADAP 1"
    assert payload["support_level"] == 1
    assert payload["students_count"] == 2
    assert payload["escola_nome"] == "Escola Teste"
