# -*- coding: utf-8 -*-
"""Contrato das opções encadeadas da grade e do parâmetro de exportação."""
from app.logistics.grade import _want_export


def _filter_escolas(escolas, avaliacao_id):
    if not avaliacao_id:
        return escolas
    return [e for e in escolas if avaliacao_id in e["avaliacao_ids"]]


def _filter_series(series, avaliacao_id, escola_id):
    result = []
    for item in series:
        if avaliacao_id and avaliacao_id not in item["avaliacao_ids"]:
            continue
        if escola_id and escola_id not in item["escola_ids"]:
            continue
        result.append(item)
    return result


def _filter_turmas(turmas, avaliacao_id, escola_id, serie_id):
    result = []
    for item in turmas:
        if avaliacao_id and avaliacao_id not in item["avaliacao_ids"]:
            continue
        if escola_id and escola_id not in item["escola_ids"]:
            continue
        if serie_id and serie_id not in item["serie_ids"]:
            continue
        result.append(item)
    return result


def test_opcoes_encadeadas_avaliacao_escola_serie_turma():
    escolas = [
        {"id": "e1", "nome": "Escola A", "avaliacao_ids": ["av1"]},
        {"id": "e2", "nome": "Escola B", "avaliacao_ids": ["av2"]},
    ]
    series = [
        {"id": "s1", "nome": "1º ano", "avaliacao_ids": ["av1"], "escola_ids": ["e1"]},
        {"id": "s2", "nome": "2º ano", "avaliacao_ids": ["av1", "av2"], "escola_ids": ["e1", "e2"]},
    ]
    turmas = [
        {
            "id": "t1",
            "nome": "A",
            "avaliacao_ids": ["av1"],
            "escola_ids": ["e1"],
            "serie_ids": ["s1"],
        },
        {
            "id": "t2",
            "nome": "B",
            "avaliacao_ids": ["av1"],
            "escola_ids": ["e1"],
            "serie_ids": ["s2"],
        },
        {
            "id": "t3",
            "nome": "C",
            "avaliacao_ids": ["av2"],
            "escola_ids": ["e2"],
            "serie_ids": ["s2"],
        },
    ]

    assert [e["id"] for e in _filter_escolas(escolas, "")] == ["e1", "e2"]
    assert [e["id"] for e in _filter_escolas(escolas, "av1")] == ["e1"]

    assert [s["id"] for s in _filter_series(series, "av1", "")] == ["s1", "s2"]
    assert [s["id"] for s in _filter_series(series, "av1", "e1")] == ["s1", "s2"]
    assert [s["id"] for s in _filter_series(series, "av2", "e2")] == ["s2"]

    assert [t["id"] for t in _filter_turmas(turmas, "av1", "e1", "")] == ["t1", "t2"]
    assert [t["id"] for t in _filter_turmas(turmas, "av1", "e1", "s1")] == ["t1"]
    assert [t["id"] for t in _filter_turmas(turmas, "av2", "e2", "s2")] == ["t3"]


def test_export_flag_da_grade():
    assert _want_export({"export": "1"})
    assert _want_export({"export": "true"})
    assert _want_export({"export": "sim"})
    assert not _want_export({})
    assert not _want_export({"export": "0"})
    assert not _want_export({"export": ""})
