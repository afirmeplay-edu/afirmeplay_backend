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
        {"id": "e1", "nome": "Escola A", "avaliacao_ids": ["avaliacao:av1"]},
        {"id": "e2", "nome": "Escola B", "avaliacao_ids": ["cartao:gab1"]},
        {"id": "e3", "nome": "Escola C", "avaliacao_ids": ["personalizada:sch1"]},
    ]
    series = [
        {
            "id": "s1",
            "nome": "1º ano",
            "avaliacao_ids": ["avaliacao:av1"],
            "escola_ids": ["e1"],
        },
        {
            "id": "s2",
            "nome": "2º ano",
            "avaliacao_ids": ["avaliacao:av1", "cartao:gab1"],
            "escola_ids": ["e1", "e2"],
        },
        {
            "id": "s3",
            "nome": "3º ano",
            "avaliacao_ids": ["personalizada:sch1"],
            "escola_ids": ["e3"],
        },
    ]
    turmas = [
        {
            "id": "t1",
            "nome": "A",
            "avaliacao_ids": ["avaliacao:av1"],
            "escola_ids": ["e1"],
            "serie_ids": ["s1"],
        },
        {
            "id": "t2",
            "nome": "B",
            "avaliacao_ids": ["avaliacao:av1"],
            "escola_ids": ["e1"],
            "serie_ids": ["s2"],
        },
        {
            "id": "t3",
            "nome": "C",
            "avaliacao_ids": ["cartao:gab1"],
            "escola_ids": ["e2"],
            "serie_ids": ["s2"],
        },
        {
            "id": "t4",
            "nome": "D",
            "avaliacao_ids": ["personalizada:sch1"],
            "escola_ids": ["e3"],
            "serie_ids": ["s3"],
        },
    ]

    assert [e["id"] for e in _filter_escolas(escolas, "")] == ["e1", "e2", "e3"]
    assert [e["id"] for e in _filter_escolas(escolas, "avaliacao:av1")] == ["e1"]
    assert [e["id"] for e in _filter_escolas(escolas, "cartao:gab1")] == ["e2"]
    assert [e["id"] for e in _filter_escolas(escolas, "personalizada:sch1")] == ["e3"]

    assert [s["id"] for s in _filter_series(series, "avaliacao:av1", "")] == ["s1", "s2"]
    assert [s["id"] for s in _filter_series(series, "avaliacao:av1", "e1")] == ["s1", "s2"]
    assert [s["id"] for s in _filter_series(series, "cartao:gab1", "e2")] == ["s2"]

    assert [t["id"] for t in _filter_turmas(turmas, "avaliacao:av1", "e1", "")] == ["t1", "t2"]
    assert [t["id"] for t in _filter_turmas(turmas, "avaliacao:av1", "e1", "s1")] == ["t1"]
    assert [t["id"] for t in _filter_turmas(turmas, "cartao:gab1", "e2", "s2")] == ["t3"]
    assert [t["id"] for t in _filter_turmas(turmas, "personalizada:sch1", "e3", "s3")] == ["t4"]


def test_export_flag_da_grade():
    assert _want_export({"export": "1"})
    assert _want_export({"export": "true"})
    assert _want_export({"export": "sim"})
    assert not _want_export({})
    assert not _want_export({"export": "0"})
    assert not _want_export({"export": ""})
