# -*- coding: utf-8 -*-
from app.afirme_ler.services.fluency_metrics_service import (
    build_fluency_record,
    refresh_ica_in_fluency_data,
)


def test_build_fluency_from_q1_q2_q3():
    record, flat = build_fluency_record(
        {
            "kind": "FLUENCY",
            "prosodyLevel": 3,
            "q1": {"wordsRead": 60, "errorsCount": 0, "readingTimeSeconds": 60},
            "q2": {"wordsRead": 40, "errorsCount": 0, "readingTimeSeconds": 60},
            "q3": {"wordsRead": 120, "errorsCount": 8, "readingTimeSeconds": 90},
            "extras": {"cadernoUi": "A"},
        },
        comprehension_score=100.0,
    )

    assert record["kind"] == "FLUENCY"
    assert record["q1"]["accuracy"] == 100.0
    assert record["q1"]["plcm"] == 60.0
    assert record["q3"]["accuracy"] == 93.33
    assert record["q3"]["plcm"] == 74.67
    assert record["metrics"]["icaScore"] is not None
    assert flat["ica_score"] == record["metrics"]["icaScore"]
    assert flat["prosody_level"] == 3


def test_flat_prototype_payload_maps_to_q3():
    record, flat = build_fluency_record(
        {
            "wordsRead": 120,
            "errorsCount": 8,
            "readingTimeSeconds": 90,
            "prosodyLevel": 2,
        }
    )
    assert record["q3"]["wordsRead"] == 120
    assert record["q1"] is None
    assert flat["calculated_plcm"] == 74.67
    assert flat["ica_score"] is None  # falta q1/q2/compreensão


def test_refresh_ica_after_comprehension():
    record, _ = build_fluency_record(
        {
            "q1": {"wordsRead": 60, "errorsCount": 0, "readingTimeSeconds": 60},
            "q2": {"wordsRead": 40, "errorsCount": 0, "readingTimeSeconds": 60},
            "q3": {"wordsRead": 60, "errorsCount": 0, "readingTimeSeconds": 60},
        },
        comprehension_score=None,
    )
    assert record["metrics"]["icaScore"] is None

    updated, flat = refresh_ica_in_fluency_data(record, comprehension_score=100.0)
    assert updated["metrics"]["icaScore"] == 100.0
    assert flat["ica_score"] == 100.0


def test_q3_persists_markings_and_derives_last_word_position():
    record, _ = build_fluency_record(
        {
            "q3": {
                "wordsRead": 115,
                "errorsCount": 1,
                "readingTimeSeconds": 52,
                "totalWords": 115,
                "unreadAfterEnd": 0,
                "markings": [
                    {
                        "index": 0,
                        "word": "O",
                        "status": "acertou",
                        "source": "manual",
                    },
                    {
                        "index": 42,
                        "word": "PROCURÁ-LA",
                        "status": "errou",
                        "source": "manual",
                    },
                ],
            }
        }
    )
    q3 = record["q3"]
    assert q3["lastWordPosition"] == 115
    assert q3["markings"][1]["status"] == "errou"
    assert q3["markings"][1]["word"] == "PROCURÁ-LA"


def test_q3_without_markings_derives_last_word_position_from_unread():
    record, _ = build_fluency_record(
        {
            "q3": {
                "wordsRead": 90,
                "errorsCount": 1,
                "readingTimeSeconds": 52,
                "totalWords": 115,
                "unreadAfterEnd": 25,
            }
        }
    )
    assert record["q3"].get("markings") is None
    assert record["q3"]["lastWordPosition"] == 90
