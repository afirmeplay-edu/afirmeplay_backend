# -*- coding: utf-8 -*-
"""Média municipal do consolidado de cartões: rede = município para qualquer perfil."""
from __future__ import annotations

import sys
import types
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest

# Hosts sem libpango/weasyprint nativo quebram no import do app; stub mínimo.
if "weasyprint" not in sys.modules:
    _wp = types.ModuleType("weasyprint")
    _wp.HTML = object
    _wp.CSS = object
    sys.modules["weasyprint"] = _wp

from app.services import consolidated_report_service as crs
from app.services.consolidated_report_service import (
    GERAL_KEY,
    ScopeIndex,
    _build_numeric_matriz,
    _fetch_answer_sheet_scope,
    _matriz_kwargs,
    _scope_context_linhas_e_rede,
    build_answer_sheet_consolidated_report,
)


def _cls(cid: str, school_id: str, school_name: str = "Escola", grade_id: str = "serie-1", grade_name: str = "5º Ano"):
    grade = SimpleNamespace(id=grade_id, name=grade_name)
    school = SimpleNamespace(id=school_id, name=school_name)
    return SimpleNamespace(id=cid, school_id=school_id, school=school, grade=grade, grade_id=grade_id)


def _scope_from_classes(classes: List[Any], item_id: str = "gab-1") -> ScopeIndex:
    item_by = {str(c.id): item_id for c in classes}
    students = {str(c.id): [] for c in classes}
    return crs._build_scope_index(classes, students, item_by)


class _GabQuery:
    def __init__(self, gabs):
        self._gabs = gabs

    def filter(self, *args, **kwargs):
        return self

    def all(self):
        return list(self._gabs)


def _fake_gabarito_model(gabs):
    return SimpleNamespace(
        id=SimpleNamespace(in_=lambda *_a, **_k: True),
        query=_GabQuery(gabs),
    )


def test_fetch_for_rede_bypasses_acl_and_keeps_tipo_area(monkeypatch):
    gab = SimpleNamespace(id="gab-1")
    monkeypatch.setattr(crs, "AnswerSheetGabarito", _fake_gabarito_model([gab]))
    visible_calls = []
    city_calls = []

    monkeypatch.setattr(
        crs,
        "answer_sheet_target_classes_visible_for_user",
        lambda *a, **k: visible_calls.append(1) or [_cls("c-acl", "esc-acl")],
    )
    monkeypatch.setattr(
        crs,
        "get_answer_sheet_target_classes_for_report",
        lambda *a, **k: city_calls.append(1)
        or [
            _cls("c1", "esc-urbana"),
            _cls("c2", "esc-rural"),
        ],
    )
    monkeypatch.setattr(
        "app.utils.school_area_type.school_ids_for_area",
        lambda area: ["esc-urbana"],
    )

    _gabs, classes, by_gab = _fetch_answer_sheet_scope(
        ["gab-1"],
        "mun-1",
        None,
        {"id": "u1", "role": "diretor"},
        {"scope": "escola"},
        area_type="urbana",
        for_rede=True,
    )

    assert visible_calls == []
    assert city_calls == [1]
    assert [c.id for c in classes] == ["c1"]
    assert [c.id for c in by_gab["gab-1"]] == ["c1"]
    assert _gabs[0].id == "gab-1"


def test_fetch_linhas_still_uses_acl(monkeypatch):
    gab = SimpleNamespace(id="gab-1")
    monkeypatch.setattr(crs, "AnswerSheetGabarito", _fake_gabarito_model([gab]))
    monkeypatch.setattr(
        crs,
        "answer_sheet_target_classes_visible_for_user",
        lambda *a, **k: [_cls("c-acl", "esc-1")],
    )
    monkeypatch.setattr(
        crs,
        "get_answer_sheet_target_classes_for_report",
        lambda *a, **k: pytest.fail("rede city fetch não deve ser usado nas linhas"),
    )

    _g, classes, _ = _fetch_answer_sheet_scope(
        ["gab-1"],
        "mun-1",
        "esc-1",
        {"id": "u1", "role": "diretor"},
        {"scope": "escola"},
        for_rede=False,
    )
    assert [c.id for c in classes] == ["c-acl"]


def test_scope_context_linhas_e_rede_comparativo_somente_com_escola():
    linhas = _scope_from_classes([_cls("c1", "esc-1", "A")])
    rede = _scope_from_classes(
        [_cls("c1", "esc-1", "A"), _cls("c2", "esc-2", "B", grade_id="serie-1")]
    )
    ctx_all = _scope_context_linhas_e_rede(linhas, rede, None)
    assert ctx_all.comparativo_municipio is False
    assert ctx_all.scope_rede is rede
    assert ctx_all.series_colunas == rede.series_colunas

    ctx_esc = _scope_context_linhas_e_rede(linhas, rede, "esc-1")
    assert ctx_esc.comparativo_municipio is True
    assert ctx_esc.escola_id == "esc-1"


def test_matriz_kwargs_sempre_expõe_scope_rede():
    linhas = _scope_from_classes([_cls("c1", "esc-1")])
    rede = _scope_from_classes([_cls("c1", "esc-1"), _cls("c2", "esc-2")])
    ctx = _scope_context_linhas_e_rede(linhas, rede, None)
    kw = _matriz_kwargs(ctx)
    assert kw["scope_rede"] is rede
    assert kw["series_colunas"] == rede.series_colunas


def test_medias_da_rede_usa_municipio_mesmo_sem_comparativo():
    """Diretor sem escola selecionada: linhas=escola, rede=município."""
    linhas = _scope_from_classes([_cls("c1", "esc-1", "José Marcos")])
    rede = _scope_from_classes(
        [
            _cls("c1", "esc-1", "José Marcos"),
            _cls("c2", "esc-2", "Esther"),
        ]
    )
    ctx = _scope_context_linhas_e_rede(linhas, rede, None)
    assert ctx.comparativo_municipio is False

    cell_vals = {
        ("esc-1", "serie-1"): 9.41,
        ("esc-2", "serie-1"): 9.56,
    }

    matriz = _build_numeric_matriz(
        ctx.scope_linhas,
        lambda e, s: cell_vals.get((e, s)),
        scope_rede=ctx.scope_rede,
        cell_fn_rede=lambda e, s: cell_vals.get((e, s)),
        series_colunas=ctx.series_colunas,
    )

    assert len(matriz["linhas"]) == 1
    assert matriz["linhas"][0]["valores_por_serie"] == [9.41]
    assert matriz["medias_da_rede"]["por_serie"] == [pytest.approx(9.485, abs=0.01)]
    assert matriz["medias_da_rede"]["por_serie"] != matriz["linhas"][0]["valores_por_serie"]


def test_duas_escolas_medias_rede_diferente_da_linha():
    linhas = _scope_from_classes([_cls("c1", "esc-a", "A")])
    rede = _scope_from_classes(
        [_cls("c1", "esc-a", "A"), _cls("c2", "esc-b", "B")]
    )
    vals = {("esc-a", "serie-1"): 5.0, ("esc-b", "serie-1"): 9.0}
    matriz = _build_numeric_matriz(
        linhas,
        lambda e, s: vals.get((e, s)),
        scope_rede=rede,
        cell_fn_rede=lambda e, s: vals.get((e, s)),
        series_colunas=rede.series_colunas,
    )
    assert matriz["linhas"][0]["valores_por_serie"] == [5.0]
    assert matriz["medias_da_rede"]["por_serie"] == [7.0]


def _stub_city(monkeypatch, city_id="mun-1", name="São Miguel"):
    city = SimpleNamespace(id=city_id, name=name)
    monkeypatch.setattr(
        crs,
        "City",
        SimpleNamespace(query=SimpleNamespace(get=lambda _id: city)),
    )


def _capture_build_wiring(monkeypatch) -> Dict[str, Any]:
    """Instrumenta build_answer_sheet_consolidated_report e captura escopos usados."""
    captured: Dict[str, Any] = {
        "fetch_calls": [],
        "rede_builds": 0,
        "results_rede_ids": None,
        "ctx": None,
        "nota_rede": None,
    }

    gab = SimpleNamespace(
        id="gab-1",
        title="Cartão",
        blocks_config={},
        correct_answers={},
        created_by=None,
    )
    cls_esc = _cls("c-esc", "esc-1", "José Marcos")
    cls_outra = _cls("c-out", "esc-2", "Esther")

    def fake_fetch(
        gabarito_ids,
        municipio_id,
        escola_id,
        user,
        permissao,
        area_type=None,
        *,
        for_rede=False,
    ):
        captured["fetch_calls"].append(
            {"escola_id": escola_id, "for_rede": for_rede, "area_type": area_type}
        )
        if for_rede:
            classes = [cls_esc, cls_outra]
            if area_type == "urbana":
                classes = [cls_esc]
        else:
            classes = [cls_esc]
            if escola_id and escola_id != "esc-1":
                classes = []
        return [gab], classes, {"gab-1": list(classes)}

    def fake_rede_scope(gabarito_ids, municipio_id, user, permissao, area_type):
        captured["rede_builds"] += 1
        classes = [cls_esc, cls_outra]
        if area_type == "urbana":
            classes = [cls_esc]
        scope = _scope_from_classes(classes)
        return scope, [c.id for c in classes], [SimpleNamespace(id="r-rede")]

    def fake_results(gabarito_ids, class_ids):
        return [SimpleNamespace(id=f"res-{cid}") for cid in class_ids]

    def fake_students(class_ids, item_by):
        return {str(cid): [] for cid in class_ids}

    def fake_medias(ctx, results_linhas, results_rede, all_disciplines, field, **kwargs):
        captured["ctx"] = ctx
        captured["results_rede_ids"] = [getattr(r, "id", None) for r in results_rede]
        rede_por = [8.0, 7.0] if len(ctx.scope_rede.escolas) > 1 else [9.41]
        rede_taxa = 7.1 if len(ctx.scope_rede.escolas) > 1 else 7.3
        section = {
            GERAL_KEY: {
                "linhas": [
                    {
                        "escola_id": "esc-1",
                        "escola_nome": "José Marcos",
                        "valores_por_serie": [9.41],
                        "taxa_geral_escola": 7.24,
                    }
                ],
                "medias_da_rede": {"por_serie": list(rede_por), "taxa_geral": rede_taxa},
            },
            "por_disciplina": {},
        }
        if field == "grade":
            captured["nota_rede"] = section[GERAL_KEY]["medias_da_rede"]
        return section

    def fake_freq(ctx, results_linhas, results_rede, all_disciplines):
        return {
            GERAL_KEY: {
                "linhas": [{"escola_id": "esc-1", "valores_por_serie": [90.0], "taxa_geral_escola": 90.0}],
                "medias_da_rede": {
                    "por_serie": [80.0] if len(ctx.scope_rede.escolas) > 1 else [90.0],
                    "taxa_geral": 80.0 if len(ctx.scope_rede.escolas) > 1 else 90.0,
                },
            },
            "por_disciplina": {},
        }

    def fake_acertos(ctx, gabs_by_id, gabarito_ids, results_linhas, results_rede, all_disciplines):
        return {
            GERAL_KEY: {
                "matriz": {
                    "linhas": [],
                    "medias_da_rede": {
                        "por_serie": [70.0] if len(ctx.scope_rede.escolas) > 1 else [99.0],
                        "taxa_geral": 70.0 if len(ctx.scope_rede.escolas) > 1 else 99.0,
                    },
                },
                "por_serie": [],
            },
            "por_disciplina": {},
        }

    def fake_dist(ctx, results_linhas, results_rede, all_disciplines, has_matematica, course_override=None):
        return {
            GERAL_KEY: {
                "linhas": [],
                "medias_da_rede": {
                    "por_serie": [],
                    "taxa_geral": {"percentuais": {}, "contagens": {}, "total_registros": 0},
                    "media_da_rede_nivel": None,
                },
            },
            "por_disciplina": {},
        }

    monkeypatch.setattr(crs, "_fetch_answer_sheet_scope", fake_fetch)
    monkeypatch.setattr(crs, "_answer_sheet_build_rede_scope", fake_rede_scope)
    monkeypatch.setattr(crs, "_answer_sheet_results_for_classes", fake_results)
    monkeypatch.setattr(crs, "_answer_sheet_students_by_class", fake_students)
    monkeypatch.setattr(crs, "_disciplinas_from_gabarito", lambda g: {"Matemática"})
    monkeypatch.setattr(
        crs,
        "_answer_sheet_item_selecionado",
        lambda g: {"id": str(g.id), "titulo": "Cartão"},
    )
    monkeypatch.setattr(crs, "_build_medias_section_answer_sheet", fake_medias)
    monkeypatch.setattr(crs, "_build_frequencia_section_answer_sheet", fake_freq)
    monkeypatch.setattr(crs, "_answer_sheet_acertos_data", fake_acertos)
    monkeypatch.setattr(crs, "_build_distribuicao_section_answer_sheet", fake_dist)
    monkeypatch.setattr(crs, "_override_geral_taxa_municipal_from_results", lambda *a, **k: None)
    monkeypatch.setattr(
        "app.services.cartao_resposta.proficiency_by_subject.course_name_and_has_matematica_for_gabarito",
        lambda _gid: ("Anos Iniciais", True),
    )
    monkeypatch.setattr(
        "app.services.cartao_resposta.answer_sheet_audience.gabarito_adap_level",
        lambda _g: None,
    )
    _stub_city(monkeypatch)
    return captured


def test_tecadm_e_diretor_mesma_escola_medias_da_rede_identicos(monkeypatch):
    captured = _capture_build_wiring(monkeypatch)

    payload_tec = build_answer_sheet_consolidated_report(
        "mun-1",
        "esc-1",
        ["gab-1"],
        {"id": "tec", "role": "tecadm", "city_id": "mun-1"},
        {"scope": "municipio", "permitted": True, "city_id": "mun-1"},
    )
    rede_tec = payload_tec["consideracoes_gerais"]["consolidado_medias_nota"][GERAL_KEY]["medias_da_rede"]
    freq_tec = payload_tec["consolidado_frequencia"][GERAL_KEY]["medias_da_rede"]
    acertos_tec = payload_tec["consideracoes_gerais"]["acertos_por_habilidade"][GERAL_KEY]["matriz"][
        "medias_da_rede"
    ]

    captured["rede_builds"] = 0
    payload_dir = build_answer_sheet_consolidated_report(
        "mun-1",
        "esc-1",
        ["gab-1"],
        {"id": "dir", "role": "diretor", "city_id": "mun-1"},
        {"scope": "escola", "permitted": True, "city_id": "mun-1"},
    )
    rede_dir = payload_dir["consideracoes_gerais"]["consolidado_medias_nota"][GERAL_KEY]["medias_da_rede"]
    freq_dir = payload_dir["consolidado_frequencia"][GERAL_KEY]["medias_da_rede"]
    acertos_dir = payload_dir["consideracoes_gerais"]["acertos_por_habilidade"][GERAL_KEY]["matriz"][
        "medias_da_rede"
    ]

    assert rede_tec == rede_dir
    assert freq_tec == freq_dir
    assert acertos_tec == acertos_dir
    assert rede_dir["taxa_geral"] == 7.1
    assert payload_dir["comparativo"]["ativo"] is True


def test_diretor_sem_escola_linhas_restritas_rede_municipal(monkeypatch):
    captured = _capture_build_wiring(monkeypatch)
    payload = build_answer_sheet_consolidated_report(
        "mun-1",
        "all",
        ["gab-1"],
        {"id": "dir", "role": "diretor", "city_id": "mun-1"},
        {"scope": "escola", "permitted": True, "city_id": "mun-1"},
    )
    assert captured["rede_builds"] == 1
    assert "comparativo" not in payload
    nota = payload["consideracoes_gerais"]["consolidado_medias_nota"][GERAL_KEY]
    assert len(nota["linhas"]) == 1
    assert nota["linhas"][0]["escola_id"] == "esc-1"
    assert nota["medias_da_rede"]["taxa_geral"] == 7.1
    assert len(captured["ctx"].scope_rede.escolas) == 2


def test_professor_linhas_restritas_rede_municipal(monkeypatch):
    captured = _capture_build_wiring(monkeypatch)
    payload = build_answer_sheet_consolidated_report(
        "mun-1",
        "esc-1",
        ["gab-1"],
        {"id": "prof", "role": "professor", "city_id": "mun-1"},
        {"scope": "escola", "permitted": True, "city_id": "mun-1"},
    )
    assert captured["rede_builds"] == 1
    assert len(captured["ctx"].scope_linhas.escolas) == 1
    assert len(captured["ctx"].scope_rede.escolas) == 2
    nota = payload["consideracoes_gerais"]["consolidado_medias_nota"][GERAL_KEY]
    assert nota["medias_da_rede"]["taxa_geral"] == 7.1


def test_tipo_area_restringe_rede(monkeypatch):
    captured = _capture_build_wiring(monkeypatch)
    payload = build_answer_sheet_consolidated_report(
        "mun-1",
        "esc-1",
        ["gab-1"],
        {"id": "dir", "role": "diretor", "city_id": "mun-1"},
        {"scope": "escola", "permitted": True, "city_id": "mun-1"},
        area_type="urbana",
    )
    assert captured["rede_builds"] == 1
    # fake_rede_scope com urbana → só 1 escola
    assert len(captured["ctx"].scope_rede.escolas) == 1
    nota = payload["consideracoes_gerais"]["consolidado_medias_nota"][GERAL_KEY]
    assert nota["medias_da_rede"]["taxa_geral"] == 7.3


def test_tecadm_sem_escola_reutiliza_linhas_sem_rede_extra(monkeypatch):
    captured = _capture_build_wiring(monkeypatch)
    # Ajuste: com scope municipio e escola=all, fake_fetch (for_rede=False) devolve só esc-1
    # no stub; para simular tecadm real, fazemos fetch de linhas retornar as duas escolas.
    cls_esc = _cls("c-esc", "esc-1", "José Marcos")
    cls_outra = _cls("c-out", "esc-2", "Esther")
    gab = SimpleNamespace(id="gab-1", title="Cartão", blocks_config={}, correct_answers={}, created_by=None)

    def fake_fetch_tecadm(
        gabarito_ids,
        municipio_id,
        escola_id,
        user,
        permissao,
        area_type=None,
        *,
        for_rede=False,
    ):
        captured["fetch_calls"].append(
            {"escola_id": escola_id, "for_rede": for_rede, "area_type": area_type}
        )
        classes = [cls_esc, cls_outra]
        return [gab], classes, {"gab-1": list(classes)}

    monkeypatch.setattr(crs, "_fetch_answer_sheet_scope", fake_fetch_tecadm)

    payload = build_answer_sheet_consolidated_report(
        "mun-1",
        "all",
        ["gab-1"],
        {"id": "tec", "role": "tecadm", "city_id": "mun-1"},
        {"scope": "municipio", "permitted": True, "city_id": "mun-1"},
    )
    assert captured["rede_builds"] == 0
    assert all(c["for_rede"] is False for c in captured["fetch_calls"])
    assert "comparativo" not in payload
    assert captured["ctx"].scope_rede is captured["ctx"].scope_linhas


def test_admin_com_escola_ainda_busca_rede_municipal(monkeypatch):
    captured = _capture_build_wiring(monkeypatch)
    payload = build_answer_sheet_consolidated_report(
        "mun-1",
        "esc-1",
        ["gab-1"],
        {"id": "adm", "role": "admin", "city_id": "mun-1"},
        {"scope": "all", "permitted": True},
    )
    assert captured["rede_builds"] == 1
    assert payload["comparativo"]["ativo"] is True
    assert payload["consideracoes_gerais"]["consolidado_medias_nota"][GERAL_KEY]["medias_da_rede"][
        "taxa_geral"
    ] == 7.1
