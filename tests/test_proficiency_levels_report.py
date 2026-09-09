# -*- coding: utf-8 -*-
"""Testes unitários do contrato de Níveis de Proficiência."""

from app.services.proficiency_levels_report_service import (
    build_report_payload,
    map_aluno_row,
    normalize_nivel,
)


def test_normalize_nivel_from_classification_text():
    assert normalize_nivel("Abaixo do Básico") == "Abaixo do Básico"
    assert normalize_nivel("basico") == "Básico"
    assert normalize_nivel("Adequado") == "Adequado"
    assert normalize_nivel("avançado") == "Avançado"
    assert normalize_nivel(None) is None


def test_map_aluno_uses_backend_classification_not_percent():
    # 90% de acertos, mas classificação Adequado (escala de proficiência).
    row = map_aluno_row(
        {
            "id": "1",
            "nome": "Ana",
            "escola": "EM Teste",
            "serie": "5º Ano",
            "turma": "A",
            "turno": "Manhã",
            "total_acertos_geral": 40,
            "total_questoes_geral": 44,
            "percentual_acertos_geral": 90.91,
            "nota_geral": 8.5,
            "proficiencia_geral": 230.0,
            "nivel_proficiencia_geral": "Adequado",
            "status_geral": "concluida",
        }
    )
    assert row is not None
    assert row["nivel"] == "Adequado"
    assert row["percentual_acertos"] == 90.91


def test_build_report_payload_filters_and_aggregates():
    alunos = [
        {
            "id": "1",
            "nome": "Ana",
            "escola": "EM",
            "serie": "5º Ano",
            "turma": "A",
            "turno": "Manhã",
            "total_acertos_geral": 30,
            "total_questoes_geral": 44,
            "percentual_acertos_geral": 68.18,
            "nota_geral": 7.0,
            "proficiencia_geral": 220.0,
            "nivel_proficiencia_geral": "Adequado",
            "status_geral": "concluida",
        },
        {
            "id": "2",
            "nome": "Bruno",
            "escola": "EM",
            "serie": "5º Ano",
            "turma": "A",
            "turno": "Tarde",
            "total_acertos_geral": 10,
            "total_questoes_geral": 44,
            "percentual_acertos_geral": 22.73,
            "nota_geral": 2.0,
            "proficiencia_geral": 120.0,
            "nivel_proficiencia_geral": "Abaixo do Básico",
            "status_geral": "concluida",
        },
        {
            "id": "3",
            "nome": "Pendente",
            "escola": "EM",
            "serie": "5º Ano",
            "turma": "B",
            "status_geral": "pendente",
        },
    ]
    payload = build_report_payload(
        fonte="avaliacao",
        meta={"titulo": "Prova"},
        filtros_aplicados={"turno": "Manhã"},
        alunos_raw=alunos,
        habilidades_raw=[
            {
                "codigo": "5N1.3",
                "descricao": "Teste",
                "disciplina_nome": "Matemática",
                "percentual_acertos": 28.1,
                "faixa": "abaixo_do_basico",
            }
        ],
        turno_filtro="Manhã",
        serie_label="5º Ano",
    )
    assert payload["fonte"] == "avaliacao"
    assert payload["indicadores"]["alunos_avaliados"] == 1
    assert payload["alunos"][0]["nome"] == "Ana"
    assert payload["distribuicao"]["Adequado"]["quantidade"] == 1
    assert payload["habilidades"][0]["nivel"] == "Abaixo do Básico"
    assert len(payload["por_turma"]) == 1
