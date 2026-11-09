# -*- coding: utf-8 -*-
"""Contrato e orquestração do relatório Acertos e Níveis (Afirme Ler)."""
from unittest.mock import patch

import pytest

from app.afirme_ler.services.acertos_niveis_contract import (
    build_report_payload,
    map_aluno_row,
    map_habilidades,
    normalize_nivel,
)
from app.afirme_ler.services.acertos_niveis_ica_adapter import (
    people_to_alunos_raw,
    skills_to_habilidades_raw,
)
from app.afirme_ler.services import acertos_niveis_service


def test_normalize_nivel_aliases():
    assert normalize_nivel("Abaixo do Básico") == "Abaixo do Básico"
    assert normalize_nivel("basico") == "Básico"
    assert normalize_nivel("Adequado") == "Adequado"
    assert normalize_nivel("avançado") == "Avançado"
    assert normalize_nivel("Sem proficiência") is None
    assert normalize_nivel(None) is None


def test_map_aluno_uses_ica_fields():
    row = map_aluno_row(
        {
            "id": "st-1",
            "nome": "Ana",
            "escola": "Escola A",
            "serie": "1º ano",
            "turma": "1º A",
            "turno": "Matutino",
            "total_acertos_geral": 34,
            "total_questoes_geral": 34,
            "percentual_acertos_geral": 100.0,
            "nota_geral": 10.0,
            "proficiencia_geral": 1000.0,
            "nivel_proficiencia_geral": "Avançado",
            "status_geral": "concluida",
        }
    )
    assert row is not None
    assert row["nivel"] == "Avançado"
    assert row["acertos"] == 34
    assert row["total_itens"] == 34
    assert row["percentual_acertos"] == 100.0
    assert row["proficiencia"] == 1000.0


def test_map_aluno_discards_sem_proficiencia():
    assert map_aluno_row(
        {
            "id": "st-2",
            "nome": "Bia",
            "nivel_proficiencia_geral": "Sem proficiência",
            "status_geral": "pendente",
        }
    ) is None


def test_build_report_payload_aggregates():
    payload = build_report_payload(
        fonte="escrita",
        meta={"titulo": "ICA Demo"},
        filtros_aplicados={"fonte": "escrita"},
        alunos_raw=[
            {
                "id": "1",
                "nome": "Ana",
                "escola": "EM",
                "serie": "1º ano",
                "turma": "A",
                "turno": "Matutino",
                "total_acertos_geral": 34,
                "total_questoes_geral": 34,
                "percentual_acertos_geral": 100.0,
                "nota_geral": 10.0,
                "proficiencia_geral": 1000.0,
                "nivel_proficiencia_geral": "Avançado",
                "status_geral": "concluida",
            },
            {
                "id": "2",
                "nome": "Caio",
                "escola": "EM",
                "serie": "1º ano",
                "turma": "A",
                "turno": "Matutino",
                "total_acertos_geral": 10,
                "total_questoes_geral": 34,
                "percentual_acertos_geral": 29.4,
                "nota_geral": 0.0,
                "proficiencia_geral": 294.1,
                "nivel_proficiencia_geral": "Abaixo do Básico",
                "status_geral": "concluida",
            },
            {
                "id": "3",
                "nome": "Bia",
                "escola": "EM",
                "serie": "1º ano",
                "turma": "A",
                "nivel_proficiencia_geral": "Sem proficiência",
                "status_geral": "pendente",
            },
        ],
        habilidades_raw=[
            {
                "codigo": "LEIT01",
                "descricao": "Leitura",
                "percentual_acertos": 66.7,
            }
        ],
        nivel_granularidade="municipio",
    )
    assert payload["fonte"] == "escrita"
    assert payload["indicadores"]["alunos_avaliados"] == 2
    assert payload["indicadores"]["adequado_avancado"]["quantidade"] == 1
    assert payload["indicadores"]["abaixo_do_basico"]["quantidade"] == 1
    assert payload["distribuicao"]["Avançado"]["quantidade"] == 1
    assert len(payload["alunos"]) == 2
    assert len(payload["por_turma"]) == 1
    assert payload["habilidades"][0]["nivel"] == "Adequado"
    assert payload["habilidades"][0]["faixa"] == "adequado"


def test_people_to_alunos_raw_maps_ica_block():
    with patch(
        "app.afirme_ler.services.acertos_niveis_ica_adapter._turno_por_turma",
        return_value={"class-1": "Matutino"},
    ):
        rows = people_to_alunos_raw(
            [
                {
                    "student_id": "st-ana",
                    "student_name": "Ana",
                    "school_id": "sch-1",
                    "school_name": "Escola A",
                    "serie_name": "1º ano",
                    "class_id": "class-1",
                    "class_name": "1º A",
                    "ica": {
                        "avaliado": True,
                        "pontos_34": 34,
                        "nota_100": 100.0,
                        "nota_prof_0_10": 10.0,
                        "proficiencia": 1000.0,
                        "nivel_aprendizagem": "Avançado",
                    },
                }
            ]
        )
    assert rows[0]["id"] == "st-ana"
    assert rows[0]["turno"] == "Matutino"
    assert rows[0]["total_acertos_geral"] == 34
    assert rows[0]["nivel_proficiencia_geral"] == "Avançado"
    assert rows[0]["status_geral"] == "concluida"


def test_skills_to_habilidades_raw():
    rows = skills_to_habilidades_raw(
        {
            "skills": [
                {
                    "skill_code": "LEIT01",
                    "skill_label": "Leitura",
                    "performance_percentage": 66.7,
                }
            ]
        }
    )
    assert rows == [
        {
            "codigo": "LEIT01",
            "descricao": "Leitura",
            "componente": "Avaliação escrita",
            "percentual_acertos": 66.7,
            "serie": None,
        }
    ]


def test_report_rejects_fluencia():
    with pytest.raises(ValueError, match="fluencia ainda não implementada"):
        acertos_niveis_service.report({"fonte": "fluencia", "avaliacaoId": "x"})


def test_report_requires_avaliacao():
    with pytest.raises(ValueError, match="avaliacaoId é obrigatório"):
        acertos_niveis_service.report({"fonte": "escrita"})


def test_report_builds_payload_from_adapter():
    loaded = {
        "written_test": type("WT", (), {"id": "wt-1", "title": "ICA 2026"})(),
        "scope": {
            "level": "municipio",
            "escolaId": None,
            "escolaName": None,
            "serieId": None,
            "serieName": None,
            "turmaId": None,
            "turmaName": None,
            "estudanteId": None,
            "estudanteName": None,
        },
        "municipio": "Cidade X",
        "uf": "SP",
        "people": [],
    }
    alunos = [
        {
            "id": "1",
            "nome": "Ana",
            "escola": "EM",
            "serie": "1º ano",
            "turma": "A",
            "turno": "",
            "total_acertos_geral": 34,
            "total_questoes_geral": 34,
            "percentual_acertos_geral": 100.0,
            "nota_geral": 10.0,
            "proficiencia_geral": 1000.0,
            "nivel_proficiencia_geral": "Avançado",
            "status_geral": "concluida",
        }
    ]
    with patch(
        "app.afirme_ler.services.acertos_niveis_service.load_ica_bundle",
        return_value=(loaded, alunos, []),
    ):
        payload = acertos_niveis_service.report(
            {"fonte": "escrita", "avaliacaoId": "wt-1"}
        )
    assert payload["fonte"] == "escrita"
    assert payload["meta"]["titulo"] == "ICA 2026"
    assert payload["meta"]["avaliacao_id"] == "wt-1"
    assert payload["indicadores"]["alunos_avaliados"] == 1
    assert payload["alunos"][0]["nivel"] == "Avançado"


def test_map_habilidades_from_skill_map_shape():
    mapped = map_habilidades(
        [{"skill_code": "PRO01", "skill_label": "Produção", "performance_percentage": 20.0}]
    )
    assert mapped[0]["codigo"] == "PRO01"
    assert mapped[0]["nivel"] == "Abaixo do Básico"
    assert mapped[0]["componente"] == "Avaliação escrita"


def test_catalog_fluencia_unavailable():
    payload = acertos_niveis_service.catalog({"fonte": "fluencia"})
    assert payload["disponivel"] is False
    assert payload["avaliacoes"] == []
