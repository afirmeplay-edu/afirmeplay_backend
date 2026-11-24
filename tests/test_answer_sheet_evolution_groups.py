# -*- coding: utf-8 -*-
"""Evolução por grupos do cartão-resposta (POST /answer-sheets/compare-groups), sem banco."""
from datetime import datetime
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from openpyxl import load_workbook

import app.models.answerSheetGabarito as gabarito_model
import app.routes.answer_sheet_routes as routes
import app.services.answer_sheet_evolution_groups_service as svc
import app.services.answer_sheet_result_snapshot as snapshot_mod
import app.services.cartao_resposta.answer_sheet_audience as audience_mod
from app.excel_export.groups_exporter import ExcelEvolutionGroupsExporter

ESCOLA = "escola-1"
OUTRA_ESCOLA = "escola-2"
TURMA = "turma-5a"
SERIE5 = "serie-5"

CONTRATO_GRUPO = {
    "id", "name", "school_id", "school_name", "grade_id", "grade_name",
    "class_id", "class_name", "current_level", "points", "transitions", "grade_by_recorte",
}
CONTRATO_PONTO = {
    "evaluation_id", "evaluation_title", "order", "average_grade",
    "average_proficiency", "level", "total_students",
}


def _gabarito(gid, grades, title="Diagnóstica"):
    return SimpleNamespace(
        id=gid,
        title=title,
        grades=grades,
        grade_id=None,
        grade_name=None,
        blocks_config={
            "blocks": [
                {"subject_id": "lp", "subject_name": "Língua Portuguesa", "start_question": 1, "end_question": 5},
                {"subject_id": "mat", "subject_name": "Matemática", "start_question": 6, "end_question": 10},
            ]
        },
        created_at=None,
    )


GAB_5 = _gabarito("gab-1", [{"id": SERIE5, "name": "5º Ano"}])
GAB_5_B = _gabarito("gab-2", [{"id": SERIE5, "name": "5º Ano"}], title="Final")
GAB_ADAP3 = _gabarito("gab-adap3", [{"id": "suporte-3", "name": "Suporte 3"}], title="ADAP 3")


def _turma(cid=TURMA, school=ESCOLA, grade=SERIE5, name="5º A"):
    return SimpleNamespace(id=cid, school_id=school, grade_id=grade, name=name)


def _sub(level):
    return SimpleNamespace(id=f"sub-{level}", class_id=TURMA, support_level=level)


def _aluno(aid, adap=None):
    sub = _sub(adap) if adap else None
    return SimpleNamespace(
        id=aid,
        class_id=TURMA,
        grade_id=None,
        grade=SimpleNamespace(name="5º Ano", education_stage_id=None),
        subturma_id=None if sub is None else sub.id,
        subturma=sub,
    )


def _resultado(aid, proficiency, pbs=None):
    return SimpleNamespace(
        id=f"r-{aid}",
        student_id=aid,
        grade=5.0,
        proficiency=proficiency,
        classification="Básico",
        proficiency_by_subject=pbs,
        corrected_at=datetime(2026, 5, 1),
        answered_questions=10,
        detected_answers={"1": "A"},
        school_id_snapshot=ESCOLA,
        class_id_snapshot=TURMA,
        grade_id_snapshot=SERIE5,
    )


@pytest.fixture
def banco(monkeypatch):
    """Loader real de Resultados (_load_cartao_roster_and_results) sobre dados em memória."""
    estado = {"alunos": [], "resultados": [], "gabaritos": {}}

    student = MagicMock()
    student.query.filter.return_value.all.side_effect = lambda: list(estado["alunos"])
    monkeypatch.setattr(routes, "Student", student)
    monkeypatch.setattr(audience_mod, "apply_gabarito_audience", lambda query, gab: query)
    monkeypatch.setattr(audience_mod, "filter_students_for_gabarito", lambda alunos, gab: list(alunos))
    monkeypatch.setattr(
        snapshot_mod, "student_ids_for_answer_sheet_class_group", lambda gid, cids, base: set(base)
    )
    monkeypatch.setattr(
        snapshot_mod,
        "query_answer_sheet_results_for_class_group",
        lambda gid, cids, base: SimpleNamespace(all=lambda: list(estado["resultados"])),
    )
    fake_model = SimpleNamespace(query=SimpleNamespace(get=lambda gid: estado["gabaritos"].get(str(gid))))
    monkeypatch.setattr(gabarito_model, "AnswerSheetGabarito", fake_model)

    monkeypatch.setattr(svc, "_turmas_alvo", lambda gid, scope, nivel, user: [TURMA])
    monkeypatch.setattr(svc, "_load_classes", lambda ids: {TURMA: _turma()})
    monkeypatch.setattr(svc, "_load_names", lambda classes: ({ESCOLA: "Escola A"}, {SERIE5: "5º Ano"}))
    monkeypatch.setattr(svc, "_data_aplicacao", lambda gab: datetime(2026, 5, 1))
    return estado


def _comparar(gabaritos, view_by="turma", alunos="todos", restricao=None):
    return svc.compare_gabaritos_by_groups(
        gabaritos,
        view_by=view_by,
        scope_info={"municipio_id": "city-1"},
        nivel_granularidade="municipio",
        alunos_filtro=alunos,
        restricao=restricao,
    )


def _ponto(payload, order=1):
    return payload["groups"][0]["points"][order - 1]


# --- contrato ---------------------------------------------------------------

def test_contrato_igual_ao_compare_groups_online(banco):
    banco["gabaritos"] = {"gab-1": GAB_5, "gab-2": GAB_5_B}
    banco["alunos"] = [_aluno("a1"), _aluno("a2")]
    banco["resultados"] = [_resultado("a1", 200.0), _resultado("a2", 250.0)]

    payload = _comparar([GAB_5, GAB_5_B])

    assert payload["view_by"] == "turma"
    assert payload["total_evaluations"] == 2
    assert [ev["id"] for ev in payload["evaluations"]] == ["gab-1", "gab-2"]
    assert payload["evaluations"][0]["origem"] == "cartao_resposta"
    assert set(payload["summary_by_level"]) == {"Abaixo do Básico", "Básico", "Adequado", "Avançado"}
    group = payload["groups"][0]
    assert CONTRATO_GRUPO <= set(group)
    assert group["class_id"] == TURMA and group["school_name"] == "Escola A"
    assert CONTRATO_PONTO <= set(group["points"][0])
    assert group["points"][0]["total_students"] == 2
    assert group["points"][0]["average_proficiency"] == 225.0
    assert group["grade_by_recorte"][0]["is_geral"] is True
    assert len(group["transitions"]) == 1
    assert group["transitions"][0]["proficiency_delta"] == 0.0


def test_ordem_da_linha_do_tempo_e_a_do_pedido(banco):
    banco["gabaritos"] = {"gab-1": GAB_5, "gab-2": GAB_5_B}
    banco["alunos"] = [_aluno("a1")]
    banco["resultados"] = [_resultado("a1", 200.0)]

    payload = _comparar([GAB_5_B, GAB_5])

    assert [(ev["order"], ev["id"]) for ev in payload["evaluations"]] == [(1, "gab-2"), (2, "gab-1")]


# --- ADAP 3 -----------------------------------------------------------------

def test_cartao_regular_deixa_aluno_adap3_de_fora(banco):
    banco["gabaritos"] = {"gab-1": GAB_5, "gab-2": GAB_5_B}
    banco["alunos"] = [_aluno("regular"), _aluno("adap3", adap=3)]
    banco["resultados"] = [_resultado("regular", 200.0), _resultado("adap3", 100.0)]

    ponto = _ponto(_comparar([GAB_5, GAB_5_B]))

    assert ponto["alunos_participantes"] == 1
    assert ponto["total_alunos"] == 1
    assert ponto["average_proficiency"] == 200.0


def test_gabarito_adap3_mantem_o_aluno_adap3(banco):
    banco["gabaritos"] = {"gab-adap3": GAB_ADAP3, "gab-1": GAB_5}
    banco["alunos"] = [_aluno("adap3", adap=3)]
    banco["resultados"] = [_resultado("adap3", 180.0)]

    ponto = _ponto(_comparar([GAB_ADAP3, GAB_5]))

    assert ponto["evaluation_id"] == "gab-adap3"
    assert ponto["alunos_participantes"] == 1
    assert ponto["average_proficiency"] == 180.0


# --- disciplina ausente -----------------------------------------------------

def test_disciplina_ausente_nao_vira_zero_na_media(banco):
    lp = lambda prof: {"subject_name": "Língua Portuguesa", "proficiency": prof, "grade": 5.0}
    mat = lambda prof: {"subject_name": "Matemática", "proficiency": prof, "grade": 5.0}
    ausente = {
        "subject_name": "Matemática",
        "absent": True,
        "proficiency": None,
        "grade": None,
        "classification": "Ausente",
    }
    banco["gabaritos"] = {"gab-1": GAB_5, "gab-2": GAB_5_B}
    banco["alunos"] = [_aluno("a1"), _aluno("a2")]
    banco["resultados"] = [
        _resultado("a1", 200.0, {"lp": lp(200.0), "mat": ausente}),
        _resultado("a2", 255.0, {"lp": lp(250.0), "mat": mat(260.0)}),
    ]

    ponto = _ponto(_comparar([GAB_5, GAB_5_B]))

    # LP = (200 + 250) / 2 = 225; MAT só de quem fez = 260; geral = (225 + 260) / 2
    assert ponto["average_proficiency"] == 242.5
    assert ponto["alunos_participantes"] == 2


# --- filtro de alunos -------------------------------------------------------

@pytest.mark.parametrize(
    "filtro,esperado",
    [("todos", 3), ("regular", 1), ("adap", 2), ("regular_adap", 3)],
)
def test_filtro_alunos_igual_ao_de_resultados(banco, filtro, esperado):
    banco["gabaritos"] = {"gab-1": GAB_5, "gab-2": GAB_5_B}
    banco["alunos"] = [_aluno("regular"), _aluno("adap1", adap=1), _aluno("adap2", adap=2)]
    banco["resultados"] = [
        _resultado("regular", 200.0),
        _resultado("adap1", 150.0),
        _resultado("adap2", 160.0),
    ]

    ponto = _ponto(_comparar([GAB_5, GAB_5_B], alunos=filtro))

    assert ponto["alunos_participantes"] == esperado
    assert ponto["total_alunos"] == esperado


# --- permissão --------------------------------------------------------------

def test_diretor_fica_preso_a_escola_do_manager(monkeypatch):
    monkeypatch.setattr(svc, "_manager_school_id", lambda user_id: ESCOLA)
    restricao = svc.restricao_por_perfil({"id": "u1", "role": "diretor"})
    assert restricao == {"tipo": "escola", "school_id": ESCOLA}

    svc.validar_filtros_do_perfil(restricao, {"escola": ESCOLA})
    with pytest.raises(svc.PermissaoGruposCartaoError) as err:
        svc.validar_filtros_do_perfil(restricao, {"escola": OUTRA_ESCOLA})
    assert err.value.status == 403

    assert svc.turma_permitida(_turma(school=ESCOLA), restricao)
    assert not svc.turma_permitida(_turma(school=OUTRA_ESCOLA), restricao)


def test_diretor_sem_escola_vinculada_e_barrado(monkeypatch):
    monkeypatch.setattr(svc, "_manager_school_id", lambda user_id: None)
    with pytest.raises(svc.PermissaoGruposCartaoError):
        svc.restricao_por_perfil({"id": "u1", "role": "coordenador"})


def test_professor_so_ve_as_proprias_turmas(monkeypatch):
    monkeypatch.setattr(svc, "_teacher_class_ids", lambda user_id: {TURMA})
    restricao = svc.restricao_por_perfil({"id": "u2", "role": "professor"})
    assert restricao == {"tipo": "turmas", "class_ids": {TURMA}}
    with pytest.raises(svc.PermissaoGruposCartaoError):
        svc.validar_filtros_do_perfil(restricao, {"turma": "turma-alheia"})

    turmas = {TURMA: _turma(), "turma-alheia": _turma(cid="turma-alheia", name="5º B")}
    monkeypatch.setattr(svc, "_turmas_alvo", lambda gid, scope, nivel, user: list(turmas))
    monkeypatch.setattr(svc, "_load_classes", lambda ids: dict(turmas))
    monkeypatch.setattr(svc, "_load_names", lambda classes: ({ESCOLA: "Escola A"}, {SERIE5: "5º Ano"}))
    monkeypatch.setattr(svc, "_data_aplicacao", lambda gab: None)
    chamadas = []

    def fake_stats(class_ids, gid, level, alunos, serie):
        chamadas.append(list(class_ids))
        return {"alunos_participantes": 1, "total_alunos": 1, "media_nota": 5.0, "media_proficiencia": 200.0}

    monkeypatch.setattr(svc, "_estatisticas_grupo", fake_stats)
    payload = _comparar([GAB_5, GAB_5_B], restricao=restricao)

    assert [g["class_id"] for g in payload["groups"]] == [TURMA]
    assert all(cids == [TURMA] for cids in chamadas)


def test_admin_nao_tem_restricao():
    assert svc.restricao_por_perfil({"id": "u3", "role": "admin"}) == {"tipo": "livre"}


# --- multi-série na visão escola -------------------------------------------

def _cenario_escola(monkeypatch, gabarito, turmas, nomes_series):
    monkeypatch.setattr(svc, "_turmas_alvo", lambda gid, scope, nivel, user: [t.id for t in turmas])
    monkeypatch.setattr(svc, "_load_classes", lambda ids: {t.id: t for t in turmas})
    monkeypatch.setattr(svc, "_load_names", lambda classes: ({ESCOLA: "Escola A"}, nomes_series))
    monkeypatch.setattr(svc, "_data_aplicacao", lambda gab: None)
    chamadas = []
    prof_por_turma = {t.id: 150.0 + 50.0 * i for i, t in enumerate(turmas)}

    def fake_stats(class_ids, gid, level, alunos, serie):
        chamadas.append({"turmas": sorted(class_ids), "level": level, "serie": serie})
        prof = sum(prof_por_turma[c] for c in class_ids) / len(class_ids)
        return {
            "alunos_participantes": len(class_ids),
            "total_alunos": 2 * len(class_ids),
            "alunos_ausentes": len(class_ids),
            "percentual_comparecimento": 50.0,
            "media_nota": 5.0,
            "media_proficiencia": prof,
        }

    monkeypatch.setattr(svc, "_estatisticas_grupo", fake_stats)
    segundo = _gabarito(f"{gabarito.id}-b", gabarito.grades, title="Final")
    return _comparar([gabarito, segundo], view_by="escola"), chamadas


def test_escola_com_etapas_diferentes_separa_por_serie(monkeypatch):
    gab = _gabarito("gab-multi", [{"id": "s5", "name": "5º Ano"}, {"id": "s9", "name": "9º Ano"}])
    turmas = [_turma("t5", grade="s5", name="5º A"), _turma("t9", grade="s9", name="9º A")]

    payload, chamadas = _cenario_escola(monkeypatch, gab, turmas, {"s5": "5º Ano", "s9": "9º Ano"})

    group = payload["groups"][0]
    ponto = group["points"][0]
    assert payload["requer_filtro_serie"] is True
    assert group["requer_filtro_serie"] is True
    assert ponto["average_grade"] is None and ponto["level"] is None
    assert ponto["alunos_participantes"] == 2
    assert {"turmas": ["t5", "t9"], "level": "escola", "serie": None} in chamadas

    by_serie = {item["serie_id"]: item for item in group["by_serie"]}
    assert set(by_serie) == {"s5", "s9"}
    assert by_serie["s5"]["course_name"] == "Anos Iniciais"
    assert by_serie["s9"]["course_name"] == "Anos Finais"
    assert by_serie["s5"]["points"][0]["average_proficiency"] == 150.0
    assert by_serie["s9"]["points"][0]["average_proficiency"] == 200.0
    assert by_serie["s5"]["points"][0]["level"] is not None
    assert {"turmas": ["t5"], "level": "serie", "serie": "s5"} in chamadas
    assert {"turmas": ["t9"], "level": "serie", "serie": "s9"} in chamadas


def test_escola_com_series_da_mesma_etapa_tambem_separa_por_serie(monkeypatch):
    gab = _gabarito("gab-af", [{"id": "s6", "name": "6º Ano"}, {"id": "s7", "name": "7º Ano"}])
    turmas = [_turma("t6", grade="s6", name="6º A"), _turma("t7", grade="s7", name="7º A")]

    payload, chamadas = _cenario_escola(monkeypatch, gab, turmas, {"s6": "6º Ano", "s7": "7º Ano"})

    group = payload["groups"][0]
    ponto = group["points"][0]
    assert payload["requer_filtro_serie"] is True
    assert group["requer_filtro_serie"] is True
    assert ponto["average_grade"] is None
    assert ponto["average_proficiency"] is None
    assert ponto["level"] is None
    assert ponto["alunos_participantes"] == 2
    assert ponto["total_alunos"] == 4
    assert {"turmas": ["t6", "t7"], "level": "escola", "serie": None} in chamadas

    by_serie = {item["serie_id"]: item for item in group["by_serie"]}
    assert set(by_serie) == {"s6", "s7"}
    assert by_serie["s6"]["course_name"] == "Anos Finais"
    assert by_serie["s7"]["course_name"] == "Anos Finais"
    assert by_serie["s6"]["points"][0]["average_proficiency"] == 150.0
    assert by_serie["s7"]["points"][0]["average_proficiency"] == 200.0
    assert by_serie["s6"]["points"][0]["level"] is not None
    assert by_serie["s7"]["points"][0]["level"] is not None
    assert {"turmas": ["t6"], "level": "serie", "serie": "s6"} in chamadas
    assert {"turmas": ["t7"], "level": "serie", "serie": "s7"} in chamadas


def test_escola_de_serie_unica_nao_gera_by_serie(monkeypatch):
    turmas = [_turma("t5a", name="5º A"), _turma("t5b", name="5º B")]

    payload, chamadas = _cenario_escola(monkeypatch, GAB_5, turmas, {SERIE5: "5º Ano"})

    group = payload["groups"][0]
    assert group["by_serie"] == []
    assert group["requer_filtro_serie"] is False
    assert chamadas[0] == {"turmas": ["t5a", "t5b"], "level": "escola", "serie": SERIE5}


def test_excel_por_grupos_tem_aba_por_serie(monkeypatch):
    gab = _gabarito("gab-multi", [{"id": "s5", "name": "5º Ano"}, {"id": "s9", "name": "9º Ano"}])
    turmas = [_turma("t5", grade="s5", name="5º A"), _turma("t9", grade="s9", name="9º A")]
    payload, _ = _cenario_escola(monkeypatch, gab, turmas, {"s5": "5º Ano", "s9": "9º Ano"})

    arquivo = ExcelEvolutionGroupsExporter().export(payload, municipality="Cidade", state="UF")
    wb = load_workbook(BytesIO(arquivo.getvalue()))

    assert wb.sheetnames == ["Capa", "Evolução por grupos", "Escola por série"]
    linhas = list(wb["Escola por série"].iter_rows(min_row=2, values_only=True))
    assert [linha[1] for linha in linhas] == ["5º Ano", "9º Ano"]


def test_excel_por_grupos_mesma_etapa_sem_media_unica_e_com_aba_por_serie(monkeypatch):
    gab = _gabarito("gab-af", [{"id": "s6", "name": "6º Ano"}, {"id": "s7", "name": "7º Ano"}])
    turmas = [_turma("t6", grade="s6", name="6º A"), _turma("t7", grade="s7", name="7º A")]
    payload, _ = _cenario_escola(monkeypatch, gab, turmas, {"s6": "6º Ano", "s7": "7º Ano"})

    arquivo = ExcelEvolutionGroupsExporter().export(payload, municipality="Cidade", state="UF")
    wb = load_workbook(BytesIO(arquivo.getvalue()))

    assert wb.sheetnames == ["Capa", "Evolução por grupos", "Escola por série"]
    linha_escola = list(wb["Evolução por grupos"].iter_rows(min_row=2, values_only=True))[0]
    # Colunas 4, 5, 6 = Nota (1), Proficiência (1), Nível (1); 7 = Participantes (1)
    assert linha_escola[3:6] == ("-", "-", "-")
    assert linha_escola[6] == 2
    linhas_serie = list(wb["Escola por série"].iter_rows(min_row=2, values_only=True))
    assert [linha[1] for linha in linhas_serie] == ["6º Ano", "7º Ano"]
