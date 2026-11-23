# -*- coding: utf-8 -*-
"""Correção por foto para cartões-resposta avulsos."""

from io import BytesIO
import os
import sys
from types import SimpleNamespace

import pytest
from flask import Flask

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.models.answerSheetGabarito import AnswerSheetGabarito
from app.physical_tests import routes as photo_routes
from app.services.cartao_resposta.photo_answers_service import PhotoAnswersService


def _gabarito(**kwargs):
    defaults = {
        "id": "gab-1",
        "test_id": None,
        "title": "Cartao",
        "num_questions": 0,
        "use_blocks": True,
        "blocks_config": {},
        "correct_answers": {},
    }
    defaults.update(kwargs)
    return AnswerSheetGabarito(**defaults)


def _legacy_block(end_question, correct_answers=None):
    return _gabarito(
        num_questions=end_question,
        blocks_config={
            "blocks": [
                {
                    "block_id": 1,
                    "subject_id": "subject-1",
                    "subject_name": "Portugues",
                    "start_question": 1,
                    "end_question": end_question,
                }
            ]
        },
        correct_answers=correct_answers or {str(i): "A" for i in range(1, end_question + 1)},
    )


def _undecorated(func):
    while hasattr(func, "__wrapped__"):
        func = func.__wrapped__
    return func


def test_resolve_gabarito_topology_legacy_11_questions_ad():
    topo = PhotoAnswersService.resolve_gabarito_topology(_legacy_block(11))

    assert topo["source"] == "gabarito_legacy_blocks"
    block = topo["topology"]["blocks"][0]
    assert block["subject_name"] == "Portugues"
    assert [q["q"] for q in block["questions"]] == list(range(1, 12))
    assert {tuple(q["alternatives"]) for q in block["questions"]} == {("A", "B", "C", "D")}


def test_resolve_gabarito_topology_legacy_22_questions_ad():
    topo = PhotoAnswersService.resolve_gabarito_topology(_legacy_block(22))

    block = topo["topology"]["blocks"][0]
    assert len(block["questions"]) == 22
    assert block["questions"][-1]["q"] == 22
    assert block["questions"][-1]["alternatives"] == ["A", "B", "C", "D"]


def test_resolve_gabarito_topology_legacy_uses_ae_when_correct_answer_has_e():
    topo = PhotoAnswersService.resolve_gabarito_topology(
        _legacy_block(3, correct_answers={"1": "A", "2": "E", "3": "C"})
    )

    assert {
        tuple(q["alternatives"])
        for q in topo["topology"]["blocks"][0]["questions"]
    } == {("A", "B", "C", "D", "E")}


def test_gabarito_without_topology_or_blocks_is_not_scan_compatible():
    gabarito = _gabarito(
        num_questions=3,
        blocks_config={},
        correct_answers={"1": "A", "2": "B", "3": "C"},
    )

    topo = PhotoAnswersService.resolve_gabarito_topology(gabarito)
    assert topo["source"] == "gabarito_num_questions"
    assert PhotoAnswersService.is_gabarito_scan_compatible(gabarito) is False


def test_gabarito_photo_subtitle_uses_grade_and_school():
    gabarito = _gabarito(
        grade_name="5o Ano",
        school_name="Escola Pedro Antonio Lino",
    )

    assert photo_routes._gabarito_photo_subtitle(gabarito) == "5o Ano - Escola Pedro Antonio Lino"


def test_gabarito_photo_subtitle_falls_back_to_grades():
    gabarito = _gabarito(
        grade_name=None,
        grades=[{"id": "grade-1", "name": "2o Ano"}],
        school_name=None,
    )

    assert photo_routes._gabarito_photo_subtitle(gabarito) == "2o Ano"


def test_load_gabarito_for_photo_rejects_test_linked_gabarito(monkeypatch):
    app = Flask(__name__)
    gabarito = _gabarito(test_id="test-1")
    monkeypatch.setattr(photo_routes, "_get_gabarito_for_photo", lambda _gid: gabarito)

    with app.test_request_context():
        loaded, err = photo_routes._load_gabarito_for_photo("gab-1")
        response, status = err

    assert loaded is None
    assert status == 422
    assert response.get_json()["code"] == "use_test_routes"
    assert response.get_json()["test_id"] == "test-1"


def test_detect_gabarito_answers_from_photo_with_mocked_detector(monkeypatch):
    app = Flask(__name__)
    gabarito = _legacy_block(1, correct_answers={"1": "A"})
    student = SimpleNamespace(id="student-1", name="Aluno")

    monkeypatch.setattr(photo_routes, "get_current_user_from_token", lambda: {"id": "u1", "role": "admin"})
    monkeypatch.setattr(photo_routes, "_load_gabarito_for_photo", lambda _gid: (gabarito, None))
    monkeypatch.setattr(photo_routes, "_get_student_for_photo", lambda _sid: student)
    monkeypatch.setattr(PhotoAnswersService, "validate_image_bytes", classmethod(lambda cls, data, ct=None: None))
    monkeypatch.setattr(PhotoAnswersService, "is_gabarito_scan_compatible", classmethod(lambda cls, g: True))
    monkeypatch.setattr(
        PhotoAnswersService,
        "resolve_gabarito_topology",
        classmethod(lambda cls, g: {"source": "gabarito_legacy_blocks", "topology": {"blocks": []}}),
    )
    monkeypatch.setattr(
        PhotoAnswersService,
        "get_gabarito_questions_meta",
        classmethod(lambda cls, g: [{"order": 1, "alternatives": ["A", "B", "C", "D"], "correct_answer": "A"}]),
    )
    monkeypatch.setattr(PhotoAnswersService, "get_gabarito_existing_answers", classmethod(lambda cls, gid, sid: {}))

    import app.services.cartao_resposta.manual_answer_sheet_service as manual_service
    import app.services.cartao_resposta.photo_answers_detector as detector_module

    monkeypatch.setattr(manual_service, "assert_user_can_manual_correct", lambda user, gab, stu: None)

    class FakeDetector:
        def __init__(self, debug=False):
            self.debug = debug

        def detect(self, image_data, topology):
            return {
                "answers": [{"question_number": 1, "answer": "A"}],
                "summary": {"total": 1},
                "blocks_detected": 1,
                "blocks_expected": 1,
                "method": "fake",
            }

    monkeypatch.setattr(detector_module, "PhotoAnswersDetector", FakeDetector)

    with app.test_request_context(
        "/physical-tests/gabarito/gab-1/student/student-1/detect-answers",
        method="POST",
        data={"image": (BytesIO(b"image"), "foto.jpg")},
        content_type="multipart/form-data",
    ):
        response, status = _undecorated(photo_routes.detect_gabarito_answers_from_photo)("gab-1", "student-1")

    data = response.get_json()
    assert status == 200
    assert data["success"] is True
    assert data["answers"][0]["answer"] == "A"
    assert data["topology_source"] == "gabarito_legacy_blocks"


@pytest.mark.parametrize("overwrite,existing,status", [(False, object(), 409), (True, object(), 200)])
def test_save_gabarito_answers_from_photo_overwrite_contract(monkeypatch, overwrite, existing, status):
    app = Flask(__name__)
    gabarito = _legacy_block(1, correct_answers={"1": "A"})

    monkeypatch.setattr(photo_routes, "get_current_user_from_token", lambda: {"id": "u1", "role": "admin"})
    monkeypatch.setattr(photo_routes, "_load_gabarito_for_photo", lambda _gid: (gabarito, None))

    import app.services.cartao_resposta.manual_answer_sheet_service as manual_service

    monkeypatch.setattr(photo_routes, "_get_existing_gabarito_answer_result", lambda _gid, _sid: existing)
    monkeypatch.setattr(
        manual_service,
        "submit_manual_correction",
        lambda **kwargs: {
            "student_name": "Aluno",
            "answer_sheet_result_id": "result-1",
            "percentage": 100,
            "saved": {"grade": 10},
        },
    )

    with app.test_request_context(
        "/physical-tests/gabarito/gab-1/student/student-1/save-answers",
        method="POST",
        json={"answers": {"1": "A"}, "overwrite": overwrite},
    ):
        response, got_status = _undecorated(photo_routes.save_gabarito_answers_from_photo)("gab-1", "student-1")

    data = response.get_json()
    assert got_status == status
    if status == 409:
        assert data["code"] == "answers_exist"
    else:
        assert data["success"] is True
        assert data["overwritten"] is True
# -*- coding: utf-8 -*-
"""Topologia/gabarito de cartão-resposta usados na correção por foto (sem banco)."""
from types import SimpleNamespace

from app.services.cartao_resposta.photo_answers_service import PhotoAnswersService


def _gab(**kw):
    base = dict(
        blocks_config=None,
        correct_answers={"1": "a", "2": "B", "3": "C"},
        num_questions=3,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def test_topologia_vem_do_blocks_config():
    g = _gab(
        blocks_config={
            "topology": {
                "blocks": [
                    {
                        "block_id": 1,
                        "subject_name": "Português",
                        "questions": [
                            {"q": 1, "alternatives": ["a", "b"]},
                            {"q": 2},
                        ],
                    },
                    {"block_id": 2, "questions": [{"q": 3, "alternatives": ["A", "B", "C", "D", "E"]}]},
                ]
            }
        }
    )
    topo = PhotoAnswersService.resolve_gabarito_topology(g)
    blocks = topo["topology"]["blocks"]
    assert [len(b["questions"]) for b in blocks] == [2, 1]
    assert blocks[0]["questions"][0]["alternatives"] == ["A", "B"]
    assert blocks[0]["questions"][1]["alternatives"] == ["A", "B", "C", "D"]
    assert blocks[0]["questions"][0]["subject_name"] == "Português"
    assert topo["source"] == "gabarito_blocks_config"


def test_fallback_por_num_questions_divide_em_blocos_de_22():
    g = _gab(num_questions=30, correct_answers={str(i): "A" for i in range(1, 31)})
    topo = PhotoAnswersService.resolve_gabarito_topology(g)
    blocks = topo["topology"]["blocks"]
    assert [len(b["questions"]) for b in blocks] == [22, 8]
    assert topo["source"] == "gabarito_num_questions"


def test_legado_sem_topology_usa_blocks_com_start_end_e_disciplina():
    g = _gab(
        num_questions=11,
        correct_answers={str(i): "A" for i in range(1, 12)},
        blocks_config={
            "use_blocks": True,
            "num_blocks": 1,
            "blocks": [
                {"block_id": 1, "start_question": 1, "end_question": 11,
                 "subject_name": "Matemática", "subject_id": "s1"}
            ],
        },
    )
    topo = PhotoAnswersService.resolve_gabarito_topology(g)
    blocks = topo["topology"]["blocks"]
    assert len(blocks) == 1 and len(blocks[0]["questions"]) == 11
    assert blocks[0]["subject_name"] == "Matemática"
    assert topo["source"] == "gabarito_legacy_blocks"


def test_compatibilidade_exige_gabarito_e_questoes():
    assert not PhotoAnswersService.is_gabarito_scan_compatible(_gab())
    assert not PhotoAnswersService.is_gabarito_scan_compatible(_gab(correct_answers={}))
    assert not PhotoAnswersService.is_gabarito_scan_compatible(_gab(num_questions=0))


def test_questions_meta_traz_resposta_correta_em_maiuscula():
    meta = PhotoAnswersService.get_gabarito_questions_meta(_gab())
    assert [m["order"] for m in meta] == [1, 2, 3]
    assert meta[0]["correct_answer"] == "A"
    assert meta[0]["question_id"] is None
