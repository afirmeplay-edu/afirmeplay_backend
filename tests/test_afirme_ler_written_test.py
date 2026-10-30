# -*- coding: utf-8 -*-
"""
Avaliação escrita do Afirme Ler (tenant.reading_written_test*).

Roda em SQLite em memória (schemas "public" e "tenant" anexados); não conecta no Postgres.
Execução: python -m pytest tests/test_afirme_ler_written_test.py -q
"""
import inspect
import json
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from flask import Flask
from sqlalchemy import event
from sqlalchemy.pool import StaticPool

from app import db
import app.models  # noqa: F401  registra todos os mappers
from app.models.city import City
from app.models.educationStage import EducationStage
from app.models.grades import Grade
from app.models.question import Question
from app.models.school import School
from app.models.student import Student
from app.models.studentClass import Class
from app.models.subject import Subject
from app.models.subturma import Subturma
from app.models.user import User
from app.afirme_ler.ddl import get_afirme_ler_written_test_tables_ddl
from app.afirme_ler.models.reading_written_test import (
    ReadingWrittenTest,
    ReadingWrittenTestClass,
    ReadingWrittenTestCorrection,
    ReadingWrittenTestPrintRun,
    ReadingWrittenTestQuestion,
)
from app.afirme_ler.services import written_test_service as svc
from app.afirme_ler.services.written_test_service import WrittenTestService

SUBJECT_ID = "subj-portugues"
# UUIDs com letras: no SQLite a coluna UUID tem afinidade NUMERIC e ids só com dígitos colidem.
STAGE_ID = uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
GRADE_1 = uuid.UUID("a1a1a1a1-0000-4000-8000-0000000000a1")
GRADE_2 = uuid.UUID("a2a2a2a2-0000-4000-8000-0000000000a2")
SCHOOL_A = "b1b1b1b1-0000-4000-8000-0000000000ba"
SCHOOL_B = "b2b2b2b2-0000-4000-8000-0000000000bb"
CLASS_A1 = uuid.UUID("c1c1c1c1-0000-4000-8000-0000000000a1")  # escola A, 1º ano
CLASS_A2 = uuid.UUID("c2c2c2c2-0000-4000-8000-0000000000a2")  # escola A, 2º ano
CLASS_B1 = uuid.UUID("c3c3c3c3-0000-4000-8000-0000000000b1")  # escola B, 1º ano
SUBTURMA_A1 = uuid.UUID("d1d1d1d1-0000-4000-8000-0000000000d1")  # ADAP 1 da turma 1º A
CITY_ID = "city-1"
# 12:00 UTC = 09:00 em America/Sao_Paulo (UTC-3).
NOW = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)

ADMIN = {"id": "u-admin", "role": "admin", "city_id": None, "tenant_id": None}
TECADM = {"id": "u-tec", "role": "tecadm", "city_id": CITY_ID, "tenant_id": CITY_ID}
PROFESSOR = {"id": "u-prof", "role": "professor", "city_id": CITY_ID, "tenant_id": CITY_ID}
OTHER_PROFESSOR = {"id": "u-prof2", "role": "professor", "city_id": CITY_ID, "tenant_id": CITY_ID}
APLICADOR = {"id": "u-apl", "role": "aplicador", "city_id": CITY_ID, "tenant_id": CITY_ID}

MC_IDS = [f"mc-{i:02d}" for i in range(1, 22)]  # 21 múltipla escolha GLOBAL, value 1
IMG_STATEMENT = "eeeeeeee-0000-4000-8000-0000000000e1"
IMG_ALTERNATIVE = "eeeeeeee-0000-4000-8000-0000000000e2"


def _options():
    return [
        {"id": "A", "text": "Sim", "isCorrect": True},
        {"id": "B", "text": "Não", "isCorrect": False},
    ]


def _question(question_id, **overrides):
    data = dict(
        id=question_id, text=f"Questão {question_id}", question_type="multipleChoice",
        alternatives=_options(), correct_answer="A", scope_type="GLOBAL", origin="afirme_ler",
        subject_id=SUBJECT_ID, grade_level=GRADE_1, version=1, value=1.0,
    )
    data.update(overrides)
    return Question(**data)


@pytest.fixture()
def flask_app():
    application = Flask("afirme_ler_written_test_tests")
    application.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
    application.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "poolclass": StaticPool,
        "connect_args": {"check_same_thread": False},
    }
    db.init_app(application)
    with application.app_context():
        engine = db.engine

        @event.listens_for(engine, "connect")
        def _attach_schemas(dbapi_conn, _record):
            dbapi_conn.execute("ATTACH DATABASE ':memory:' AS public")
            dbapi_conn.execute("ATTACH DATABASE ':memory:' AS tenant")

        engine.dispose()
        tables = [
            m.__table__ for m in (
                EducationStage, Subject, Grade, User, City, Question, School, Class, Subturma,
                Student, ReadingWrittenTest, ReadingWrittenTestQuestion, ReadingWrittenTestClass,
                ReadingWrittenTestPrintRun, ReadingWrittenTestCorrection,
            )
        ]
        db.metadata.create_all(engine, tables=tables)

        db.session.add_all([
            EducationStage(id=STAGE_ID, name="Anos Iniciais"),
            Subject(id=SUBJECT_ID, name="Língua Portuguesa"),
            Grade(id=GRADE_1, name="1º ano", education_stage_id=STAGE_ID),
            Grade(id=GRADE_2, name="2º ano", education_stage_id=STAGE_ID),
            School(id=SCHOOL_A, name="Escola A"),
            School(id=SCHOOL_B, name="Escola B"),
            Class(id=CLASS_A1, name="1º A", school_id=SCHOOL_A, grade_id=GRADE_1),
            Class(id=CLASS_A2, name="2º A", school_id=SCHOOL_A, grade_id=GRADE_2),
            Class(id=CLASS_B1, name="1º B", school_id=SCHOOL_B, grade_id=GRADE_1),
            *[_question(qid) for qid in MC_IDS],
            _question("play-mc", origin="afirme_play", question_type="multiple_choice"),
            _question("dict-1", question_type="dictation", alternatives=[],
                      correct_answer="sapato", value=2.0),
            _question("dict-2", question_type="dictation", alternatives=[],
                      correct_answer="borboleta", value=2.0),
            _question("prod-1", question_type="text_production", alternatives=[],
                      correct_answer=None, value=None),
            _question("play-ligar", origin="afirme_play", question_type="ligar_colunas"),
            _question("private-other", scope_type="PRIVATE", owner_user_id="u-prof2"),
            _question(
                "mc-img",
                formatted_text=f'<p>Observe a figura.</p><img src="/questions/mc-img/images/{IMG_STATEMENT}" />',
                secondstatement="<p>Qual é o animal?</p>",
                images=[{"id": IMG_STATEMENT, "type": "image/png", "minio_bucket": "question-images",
                         "minio_object_name": f"mc-img/{IMG_STATEMENT}.png"}],
                alternatives=[
                    {"id": "A", "text": "Gato", "isCorrect": True},
                    {"id": "B", "text": "", "image": {"id": IMG_ALTERNATIVE, "type": "image/png"},
                     "isCorrect": False},
                    {"id": "C", "text": "Pato", "isCorrect": False},
                ],
                formatted_solution="<p>SOLUCAO-SECRETA</p>",
            ),
            Subturma(id=SUBTURMA_A1, class_id=CLASS_A1, support_level=1),
            Student(id="st-ana", name="Ana", registration="M001", class_id=CLASS_A1,
                    school_id=SCHOOL_A, grade_id=GRADE_1),
            Student(id="st-caio", name="Caio", registration="M002", class_id=CLASS_A1,
                    school_id=SCHOOL_A, grade_id=GRADE_1, subturma_id=SUBTURMA_A1),
            Student(id="st-bia", name="Bia", registration=None, class_id=CLASS_A1,
                    school_id=SCHOOL_A, grade_id=GRADE_1),
            Student(id="st-davi", name="Davi", registration="M004", class_id=CLASS_B1,
                    school_id=SCHOOL_B, grade_id=GRADE_1),
            Student(id="st-eva", name="Eva", registration="M005", class_id=CLASS_A2,
                    school_id=SCHOOL_A, grade_id=GRADE_2),
        ])
        db.session.commit()

        with patch(
            "app.afirme_ler.services.scope_service.get_current_tenant_context",
            return_value=None,
        ):
            yield application

        db.session.remove()
        db.metadata.drop_all(engine, tables=tables)


def _scope(**overrides):
    data = {
        "title": "Avaliação escrita — 1º bimestre",
        "description": "Prova impressa",
        "gradeIds": [str(GRADE_1)],
        "schoolIds": [SCHOOL_A, SCHOOL_B],
        "classIds": [str(CLASS_A1), str(CLASS_B1)],
    }
    data.update(overrides)
    return data


def _pattern_ids():
    """16 múltipla escolha, ditado nas posições 17 e 18, bilhete na 19."""
    return MC_IDS[:16] + ["dict-1", "dict-2", "prod-1"]


def _items(ids):
    return [{"id": qid, "order": index} for index, qid in enumerate(ids, start=1)]


def _create(user=PROFESSOR, **overrides):
    return WrittenTestService.create(user, _scope(**overrides))


# ---------------------------------------------------------------------------
# Criação e escopo
# ---------------------------------------------------------------------------

def test_create_with_valid_scope(flask_app):
    written_test = _create(questions=[{"id": "dict-1"}, {"id": "mc-01"}])

    stored = db.session.get(ReadingWrittenTest, written_test.id)
    assert stored.status == "rascunho"
    assert stored.created_by == "u-prof"
    assert stored.grade_ids == [str(GRADE_1)]
    assert stored.school_ids == [SCHOOL_A, SCHOOL_B]
    assert stored.class_ids == [str(CLASS_A1), str(CLASS_B1)]
    assert stored.published_at is None

    detail = svc.to_detail(written_test)
    assert detail["grades"] == [{"id": str(GRADE_1), "name": "1º ano"}]
    assert [s["name"] for s in detail["schools"]] == ["Escola A", "Escola B"]
    assert detail["classes"][0] == {
        "id": str(CLASS_A1), "name": "1º A", "schoolId": SCHOOL_A, "gradeId": str(GRADE_1),
    }
    assert [(q["id"], q["order"]) for q in detail["questions"]] == [("dict-1", 1), ("mc-01", 2)]
    assert detail["questions"][0]["dictatedWord"] == "sapato"
    assert detail["totalQuestions"] == 2


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"title": "  "}, "title é obrigatório"),
        ({"gradeIds": []}, "ao menos uma série"),
        ({"schoolIds": []}, "ao menos uma escola"),
        ({"classIds": []}, "ao menos uma turma"),
        ({"gradeIds": "x"}, "gradeIds deve ser uma lista"),
        ({"classIds": ["nao-e-uuid"]}, "classIds contém ID inválido"),
        ({"gradeIds": [str(uuid.uuid4())]}, "Série não encontrada"),
        ({"schoolIds": [str(uuid.uuid4())]}, "Escola não encontrada"),
        ({"classIds": [str(uuid.uuid4())]}, "Turma não encontrada"),
        ({"schoolIds": [SCHOOL_A]}, "A turma 1º B não pertence às escolas escolhidas"),
        ({"classIds": [str(CLASS_A2)]}, "A turma 2º A não pertence às séries escolhidas"),
    ],
)
def test_create_rejects_invalid_scope(flask_app, overrides, message):
    with pytest.raises(ValueError, match=message):
        _create(**overrides)
    db.session.rollback()
    assert ReadingWrittenTest.query.count() == 0


def test_create_with_multiple_grades(flask_app):
    written_test = _create(
        gradeIds=[str(GRADE_1), str(GRADE_2)], schoolIds=[SCHOOL_A],
        classIds=[str(CLASS_A1), str(CLASS_A2)],
    )
    assert written_test.grade_ids == [str(GRADE_1), str(GRADE_2)]


# ---------------------------------------------------------------------------
# Questões da avaliação
# ---------------------------------------------------------------------------

def test_set_questions_replaces_list_and_orders(flask_app):
    written_test = _create(questions=_items(MC_IDS[:3]))

    updated = WrittenTestService.set_questions(PROFESSOR, written_test.id, {"questions": [
        {"id": "prod-1", "order": 2}, {"id": "mc-05", "order": 1}, {"id": "play-mc", "order": 3},
    ]})
    assert [(q.question_id, q.order) for q in updated.questions] == [
        ("mc-05", 1), ("prod-1", 2), ("play-mc", 3),
    ]
    assert ReadingWrittenTestQuestion.query.count() == 3

    cleared = WrittenTestService.set_questions(PROFESSOR, written_test.id, {"questions": []})
    assert cleared.questions == []


def test_set_questions_without_order_uses_position(flask_app):
    written_test = _create()
    updated = WrittenTestService.set_questions(
        PROFESSOR, written_test.id, {"questions": [{"id": "mc-02"}, {"id": "mc-01"}]}
    )
    assert [(q.question_id, q.order) for q in updated.questions] == [("mc-02", 1), ("mc-01", 2)]


def test_set_questions_accepts_at_most_19(flask_app):
    written_test = _create()
    with pytest.raises(ValueError, match="A avaliação aceita no máximo 19 questões."):
        WrittenTestService.set_questions(PROFESSOR, written_test.id, {"questions": _items(MC_IDS)})
    db.session.rollback()
    with pytest.raises(ValueError, match="no máximo 19"):
        _create(questions=_items(MC_IDS))


@pytest.mark.parametrize(
    "questions, message",
    [
        ([{"id": "mc-01"}, {"id": "mc-01"}], "Questão repetida na avaliação."),
        ([{"id": "private-other"}], "Questão não encontrada ou sem acesso: private-other"),
        ([{"id": "nao-existe"}], "Questão não encontrada ou sem acesso: nao-existe"),
        ([{"id": "play-ligar"}], "tipo ligar_colunas, que não é aceito"),
        ([{"id": "mc-01", "order": 1}, {"id": "mc-02", "order": 1}], "únicos e de 1 a 2"),
        ([{"id": "mc-01", "order": 2}], "únicos e de 1 a 1"),
        ([{"id": "mc-01", "order": "1"}], "order deve ser um número inteiro"),
        ([{"order": 1}], "Cada questão precisa de id"),
        ("mc-01", "questions deve ser uma lista"),
    ],
)
def test_set_questions_rejects_invalid(flask_app, questions, message):
    written_test = _create(questions=[{"id": "mc-10"}])
    with pytest.raises(ValueError, match=message):
        WrittenTestService.set_questions(PROFESSOR, written_test.id, {"questions": questions})
    db.session.rollback()
    assert [q.question_id for q in WrittenTestService.get(written_test.id).questions] == ["mc-10"]


def test_private_question_of_owner_is_accepted(flask_app):
    written_test = _create(user=OTHER_PROFESSOR, questions=[{"id": "private-other"}])
    assert [q.question_id for q in written_test.questions] == ["private-other"]


def test_question_grade_does_not_need_to_match(flask_app):
    db.session.add(_question("mc-grade2", grade_level=GRADE_2))
    db.session.commit()
    written_test = _create(questions=[{"id": "mc-grade2"}])
    assert len(written_test.questions) == 1


def test_total_score_and_counts_by_type(flask_app):
    written_test = _create(questions=_items(["mc-01", "play-mc", "dict-1", "prod-1"]))
    detail = svc.to_detail(written_test)
    assert detail["totalQuestions"] == 4
    assert detail["totalScore"] == 5.0  # 1 + 1 + 2 + (nulo = 1)
    assert detail["questionsByType"] == {
        "multipleChoice": 2, "dictation": 1, "text_production": 1,
    }


# ---------------------------------------------------------------------------
# Publicação
# ---------------------------------------------------------------------------

def test_publish_requires_image_description(flask_app):
    written_test = _create(questions=_items(PDF_ORDER))
    question = db.session.get(Question, "dict-1")
    question.writing_stimulus = "image"
    question.correct_answer = None
    question.writing_reference = None
    db.session.commit()

    with pytest.raises(ValueError, match="sem descrição"):
        WrittenTestService.publish(PROFESSOR, written_test.id)
    db.session.rollback()

    question = db.session.get(Question, "dict-1")
    question.writing_reference = "cinto de roupa"
    db.session.commit()
    published = WrittenTestService.publish(PROFESSOR, written_test.id)
    assert published.status == "publicada"


def test_publish_requires_the_written_pattern(flask_app):
    written_test = _create(questions=_items(MC_IDS[:18]))
    with pytest.raises(
        ValueError, match="precisa ter exatamente 19 questões para ser publicada \\(hoje tem 18\\)"
    ):
        WrittenTestService.publish(PROFESSOR, written_test.id)
    db.session.rollback()

    WrittenTestService.set_questions(PROFESSOR, written_test.id, {"questions": _items(MC_IDS[:19])})
    with pytest.raises(ValueError, match="A posição 17 precisa ser ditado"):
        WrittenTestService.publish(PROFESSOR, written_test.id)
    db.session.rollback()

    WrittenTestService.set_questions(PROFESSOR, written_test.id, {"questions": _items(_pattern_ids())})
    published = WrittenTestService.publish(PROFESSOR, written_test.id)
    assert published.status == "publicada"
    assert published.published_at is not None
    assert svc.to_detail(published)["totalScore"] == 21.0
    assert svc.to_detail(published)["questionsByType"] == {
        "multipleChoice": 16, "dictation": 2, "text_production": 1,
    }


def test_publish_with_21_is_rejected(flask_app):
    written_test = _create(questions=_items(MC_IDS[:16]))
    with patch("app.afirme_ler.services.written_test_service.REQUIRED_QUESTIONS", 25):
        WrittenTestService.set_questions(PROFESSOR, written_test.id, {"questions": _items(MC_IDS)})
    with pytest.raises(ValueError, match="exatamente 19 questões .*hoje tem 21"):
        WrittenTestService.publish(PROFESSOR, written_test.id)
    db.session.rollback()
    assert WrittenTestService.get(written_test.id).status == "rascunho"


def test_publish_rejects_deleted_question(flask_app):
    written_test = _create(questions=_items(_pattern_ids()))
    table = Question.__table__
    db.session.execute(table.delete().where(table.c.id == "dict-2"))
    db.session.commit()
    with pytest.raises(ValueError, match="dict-2 não existe mais"):
        WrittenTestService.publish(PROFESSOR, written_test.id)
    db.session.rollback()


def test_published_test_is_locked(flask_app):
    written_test = _create(questions=_items(_pattern_ids()))
    WrittenTestService.publish(PROFESSOR, written_test.id)

    with pytest.raises(ValueError, match="Avaliação publicada não pode ser alterada."):
        WrittenTestService.update(PROFESSOR, written_test.id, {"title": "Outro"})
    db.session.rollback()
    with pytest.raises(ValueError, match="Avaliação publicada não pode ser alterada."):
        WrittenTestService.set_questions(PROFESSOR, written_test.id, {"questions": []})
    db.session.rollback()
    with pytest.raises(ValueError, match="Avaliação publicada não pode ser excluída."):
        WrittenTestService.delete(PROFESSOR, written_test.id)
    db.session.rollback()
    with pytest.raises(ValueError, match="já está publicada"):
        WrittenTestService.publish(PROFESSOR, written_test.id)
    db.session.rollback()

    stored = WrittenTestService.get(written_test.id)
    assert stored.title == "Avaliação escrita — 1º bimestre"
    assert len(stored.questions) == 19


# ---------------------------------------------------------------------------
# Edição, exclusão e permissões
# ---------------------------------------------------------------------------

def test_update_revalidates_scope(flask_app):
    written_test = _create()
    with pytest.raises(ValueError, match="A turma 1º B não pertence às escolas escolhidas"):
        WrittenTestService.update(PROFESSOR, written_test.id, {"schoolIds": [SCHOOL_A]})
    db.session.rollback()

    updated = WrittenTestService.update(PROFESSOR, written_test.id, {
        "title": "Novo título", "schoolIds": [SCHOOL_A], "classIds": [str(CLASS_A1)],
    })
    assert updated.title == "Novo título"
    assert updated.school_ids == [SCHOOL_A]
    assert updated.class_ids == [str(CLASS_A1)]
    assert updated.grade_ids == [str(GRADE_1)]


def test_delete_draft_removes_questions(flask_app):
    written_test = _create(questions=_items(MC_IDS[:3]))
    WrittenTestService.delete(PROFESSOR, written_test.id)
    assert ReadingWrittenTest.query.count() == 0
    assert ReadingWrittenTestQuestion.query.count() == 0
    with pytest.raises(LookupError):
        WrittenTestService.get(written_test.id)


def test_aplicador_is_blocked_on_write(flask_app):
    with pytest.raises(PermissionError, match="não pode criar ou alterar avaliações escritas"):
        _create(user=APLICADOR)
    written_test = _create()
    for call in (
        lambda: WrittenTestService.update(APLICADOR, written_test.id, {"title": "x"}),
        lambda: WrittenTestService.set_questions(APLICADOR, written_test.id, {"questions": []}),
        lambda: WrittenTestService.publish(APLICADOR, written_test.id),
        lambda: WrittenTestService.delete(APLICADOR, written_test.id),
    ):
        with pytest.raises(PermissionError):
            call()
        db.session.rollback()


def test_only_creator_admin_and_tecadm_manage(flask_app):
    written_test = _create()
    with pytest.raises(PermissionError, match="não tem permissão para alterar esta avaliação"):
        WrittenTestService.update(OTHER_PROFESSOR, written_test.id, {"title": "x"})
    db.session.rollback()

    assert WrittenTestService.update(TECADM, written_test.id, {"title": "Pelo tecadm"}).title == "Pelo tecadm"
    assert WrittenTestService.update(ADMIN, written_test.id, {"title": "Pelo admin"}).title == "Pelo admin"


# ---------------------------------------------------------------------------
# Listagem
# ---------------------------------------------------------------------------

def test_list_paginates_filters_and_counts(flask_app):
    first = _create(title="Prova Alfa", questions=_items(["mc-01", "dict-1"]))
    _create(
        title="Prova Beta", gradeIds=[str(GRADE_2)], schoolIds=[SCHOOL_A],
        classIds=[str(CLASS_A2)],
    )
    published = _create(title="Prova Gama", questions=_items(_pattern_ids()))
    WrittenTestService.publish(PROFESSOR, published.id)

    result = WrittenTestService.list_tests({})
    assert result["pagination"]["total"] == 3
    assert result["pagination"]["per_page"] == 10
    assert "questions" not in result["data"][0]

    by_title = {item["title"]: item for item in result["data"]}
    assert by_title["Prova Alfa"]["totalQuestions"] == 2
    assert by_title["Prova Alfa"]["totalScore"] == 3.0
    assert by_title["Prova Alfa"]["questionsByType"]["dictation"] == 1
    assert by_title["Prova Gama"]["status"] == "publicada"

    def titles(filters):
        return sorted(item["title"] for item in WrittenTestService.list_tests(filters)["data"])

    assert titles({"status": "publicada"}) == ["Prova Gama"]
    assert titles({"grade_id": str(GRADE_2)}) == ["Prova Beta"]
    assert titles({"school_id": SCHOOL_B}) == ["Prova Alfa", "Prova Gama"]
    assert titles({"q": "alf"}) == ["Prova Alfa"]
    assert WrittenTestService.list_tests({"per_page": "1", "page": "2"})["pagination"]["has_next"]
    assert WrittenTestService.list_tests({"per_page": "500"})["pagination"]["per_page"] == 100
    assert first.id in {item["id"] for item in result["data"]}

    with pytest.raises(ValueError, match="status inválido"):
        WrittenTestService.list_tests({"status": "aplicada"})
    with pytest.raises(ValueError, match="grade_id deve ser um UUID"):
        WrittenTestService.list_tests({"grade_id": "x"})


# ---------------------------------------------------------------------------
# Rotas (sem os decorators de JWT/feature/role/município)
# ---------------------------------------------------------------------------

def _call_view(view, user, *args, path="/", method="GET", json=None):
    from flask import current_app
    from app.afirme_ler.routes import written_tests_routes as module

    raw = inspect.unwrap(getattr(module, view))
    with current_app.test_request_context(path, method=method, json=json):
        with patch.object(module, "get_current_user_from_token", return_value=user):
            return raw(*args)


def test_routes_create_and_publish_errors(flask_app):
    response, status = _call_view(
        "create_written_test", PROFESSOR, path="/afirme-reading/written-tests",
        method="POST", json=_scope(questions=[{"id": "mc-01"}]),
    )
    assert status == 201
    body = response.get_json()
    assert body["status"] == "rascunho"
    assert body["questions"][0]["order"] == 1

    response, status = _call_view(
        "publish_written_test", PROFESSOR, body["id"],
        path=f"/afirme-reading/written-tests/{body['id']}/publish", method="POST",
    )
    assert status == 400
    assert response.get_json() == {
        "error": "A avaliação precisa ter exatamente 19 questões para ser publicada (hoje tem 1)."
    }

    response, status = _call_view(
        "get_written_test", APLICADOR, "nao-existe", path="/afirme-reading/written-tests/nao-existe",
    )
    assert status == 404
    assert response.get_json() == {"error": "Avaliação escrita não encontrada."}


def test_ddl_has_cascade_and_unique_constraints():
    ddl = get_afirme_ler_written_test_tables_ddl("city_teste")
    assert 'CREATE TABLE IF NOT EXISTS "city_teste".reading_written_test (' in ddl
    assert 'REFERENCES "city_teste".reading_written_test(id) ON DELETE CASCADE' in ddl
    assert "UNIQUE (written_test_id, question_id)" in ddl
    assert 'UNIQUE (written_test_id, "order")' in ddl
    assert "CHECK (status IN ('rascunho', 'publicada'))" in ddl
    assert 'CHECK ("order" BETWEEN 1 AND 19)' in ddl
    assert "reading_evaluation " not in ddl


def test_new_city_provisioning_includes_written_test_tables():
    from app.services.city_schema_service import _get_city_tables_ddl

    ddl = _get_city_tables_ddl("city_teste")
    assert 'CREATE TABLE IF NOT EXISTS "city_teste".reading_written_test (' in ddl
    assert 'CREATE TABLE IF NOT EXISTS "city_teste".reading_written_test_question (' in ddl
    assert 'CREATE TABLE IF NOT EXISTS "city_teste".reading_written_test_class (' in ddl


def test_ddl_application_table():
    ddl = get_afirme_ler_written_test_tables_ddl("city_teste")
    assert "UNIQUE (written_test_id, class_id)" in ddl
    assert 'class_id UUID NOT NULL REFERENCES "city_teste".class(id) ON DELETE CASCADE' in ddl
    assert "application_start TIMESTAMP NOT NULL" in ddl
    assert "CHECK (application_end IS NULL OR application_end > application_start)" in ddl


# ---------------------------------------------------------------------------
# Aplicação por turma
# ---------------------------------------------------------------------------

@pytest.fixture()
def clock(flask_app):
    holder = {"now": NOW}
    with patch.object(svc, "_utcnow", lambda: holder["now"]):
        yield holder


def _published(user=PROFESSOR):
    written_test = _create(user=user, questions=_items(_pattern_ids()))
    return WrittenTestService.publish(user, written_test.id).id


def _apply(test_id, class_ids, start="2026-11-12T08:00:00", user=PROFESSOR, **extra):
    data = {"classIds": [str(c) for c in class_ids], "applicationStart": start}
    data.update(extra)
    return WrittenTestService.apply(user, test_id, data)


def _by_class(result):
    return {item["classId"]: item for item in result["classes"]}


def test_apply_draft_is_rejected(clock):
    written_test = _create(questions=_items(_pattern_ids()))
    with pytest.raises(ValueError, match="Só avaliação publicada pode ser aplicada."):
        _apply(written_test.id, [CLASS_A1])


def test_apply_class_outside_test_is_rejected(clock):
    test_id = _published()
    with pytest.raises(ValueError, match="A turma 2º A não faz parte desta avaliação."):
        _apply(test_id, [CLASS_A1, CLASS_A2])
    db.session.rollback()
    assert ReadingWrittenTestClass.query.count() == 0


@pytest.mark.parametrize(
    "extra, message",
    [
        ({"applicationStart": None}, "applicationStart é obrigatório."),
        ({"applicationStart": "  "}, "applicationStart é obrigatório."),
        ({"applicationStart": "12/11/2026"}, "applicationStart deve ser uma data/hora ISO 8601"),
        ({"applicationEnd": "2026-11-12T07:00:00"}, "applicationEnd deve ser depois de applicationStart."),
        ({"applicationEnd": "2026-11-12T08:00:00"}, "applicationEnd deve ser depois de applicationStart."),
        ({"timezone": "Marte/Base"}, "timezone inválido: Marte/Base."),
        ({"classIds": []}, "Informe ao menos uma turma em classIds."),
    ],
)
def test_apply_rejects_invalid_payload(clock, extra, message):
    test_id = _published()
    data = {"classIds": [str(CLASS_A1)], "applicationStart": "2026-11-12T08:00:00"}
    data.update(extra)
    with pytest.raises(ValueError, match=message):
        WrittenTestService.apply(PROFESSOR, test_id, data)


def test_apply_and_upsert_before_start(clock):
    test_id = _published()
    first = _by_class(_apply(test_id, [CLASS_A1, CLASS_B1]))
    assert first[str(CLASS_A1)]["applied"] is True
    assert first[str(CLASS_A1)]["applicationStart"] == "2026-11-12T08:00:00"
    assert first[str(CLASS_A1)]["applicationEnd"] is None
    assert first[str(CLASS_A1)]["timezone"] == "America/Sao_Paulo"
    assert first[str(CLASS_A1)]["status"] == "agendada"

    second = _by_class(_apply(
        test_id, [CLASS_A1], start="2026-11-13T07:30:00", applicationEnd="2026-11-13T11:30:00",
    ))
    assert second[str(CLASS_A1)]["applicationStart"] == "2026-11-13T07:30:00"
    assert second[str(CLASS_A1)]["applicationEnd"] == "2026-11-13T11:30:00"
    assert ReadingWrittenTestClass.query.count() == 2
    stored = ReadingWrittenTestClass.query.filter_by(class_id=CLASS_A1).one()
    assert stored.created_by == "u-prof"


def test_apply_converts_offset_to_local_time(clock):
    test_id = _published()
    result = _by_class(_apply(test_id, [CLASS_A1], start="2026-11-12T11:00:00Z"))
    assert result[str(CLASS_A1)]["applicationStart"] == "2026-11-12T08:00:00"

    result = _by_class(_apply(
        test_id, [CLASS_B1], start="2026-11-12T08:00:00-03:00", timezone="America/Manaus",
    ))
    assert result[str(CLASS_B1)]["applicationStart"] == "2026-11-12T07:00:00"
    assert result[str(CLASS_B1)]["timezone"] == "America/Manaus"


def test_apply_after_start_cannot_change(clock):
    test_id = _published()
    _apply(test_id, [CLASS_A1], start="2026-11-10T08:00:00")  # 08:00 local; agora são 09:00
    with pytest.raises(ValueError, match="A aplicação da turma 1º A já começou e não pode ser alterada."):
        _apply(test_id, [CLASS_B1, CLASS_A1], start="2026-11-20T08:00:00")
    db.session.rollback()
    assert ReadingWrittenTestClass.query.count() == 1


def test_remove_class_before_and_after_start(clock):
    test_id = _published()
    _apply(test_id, [CLASS_A1, CLASS_B1], start="2026-11-12T08:00:00")
    WrittenTestService.remove_class(PROFESSOR, test_id, str(CLASS_B1))
    assert [str(a.class_id) for a in ReadingWrittenTestClass.query.all()] == [str(CLASS_A1)]

    with pytest.raises(LookupError, match="não está aplicada a esta turma"):
        WrittenTestService.remove_class(PROFESSOR, test_id, str(CLASS_B1))
    with pytest.raises(LookupError, match="Turma não encontrada nesta avaliação"):
        WrittenTestService.remove_class(PROFESSOR, test_id, str(CLASS_A2))

    clock["now"] = datetime(2026, 11, 12, 11, 0, tzinfo=timezone.utc)  # 08:00 local
    with pytest.raises(ValueError, match="A aplicação desta turma já começou e não pode ser retirada."):
        WrittenTestService.remove_class(PROFESSOR, test_id, str(CLASS_A1))
    db.session.rollback()
    assert ReadingWrittenTestClass.query.count() == 1


def test_status_is_calculated_on_read(clock):
    test_id = _published()
    _apply(test_id, [CLASS_A1], start="2026-11-12T08:00:00", applicationEnd="2026-11-12T12:00:00")
    _apply(test_id, [CLASS_B1], start="2026-11-12T08:00:00")

    def statuses():
        return {k: v["status"] for k, v in _by_class(WrittenTestService.list_classes(test_id)).items()}

    assert statuses() == {str(CLASS_A1): "agendada", str(CLASS_B1): "agendada"}
    clock["now"] = datetime(2026, 11, 12, 12, 0, tzinfo=timezone.utc)  # 09:00 local
    assert statuses() == {str(CLASS_A1): "em_andamento", str(CLASS_B1): "em_andamento"}
    clock["now"] = datetime(2026, 11, 12, 15, 0, tzinfo=timezone.utc)  # 12:00 local = fim
    assert statuses() == {str(CLASS_A1): "encerrada", str(CLASS_B1): "em_andamento"}


def test_classes_list_and_student_count(clock):
    test_id = _published()
    _apply(test_id, [CLASS_A1])

    classes = WrittenTestService.list_classes(test_id)["classes"]
    assert [c["classId"] for c in classes] == [str(CLASS_A1), str(CLASS_B1)]
    a1, b1 = classes
    assert a1["className"] == "1º A"
    assert a1["school"] == {"id": SCHOOL_A, "name": "Escola A"}
    assert a1["grade"] == {"id": str(GRADE_1), "name": "1º ano"}
    assert a1["applied"] is True and a1["studentCount"] == 3
    assert b1["applied"] is False and b1["status"] is None and b1["studentCount"] == 1


def test_students_of_applied_class(clock):
    test_id = _published()
    _apply(test_id, [CLASS_A1])

    result = WrittenTestService.list_students(test_id, str(CLASS_A1))
    assert result["studentCount"] == 3
    assert result["status"] == "agendada"
    assert [s["name"] for s in result["students"]] == ["Ana", "Bia", "Caio"]
    caio = result["students"][2]
    assert caio == {
        "id": "st-caio", "name": "Caio", "registration": "M002",
        "subturma": {"id": str(SUBTURMA_A1), "name": "ADAP 1"},
    }
    assert result["students"][1]["registration"] is None
    assert result["students"][0]["subturma"] is None

    with pytest.raises(ValueError, match="ainda não foi aplicada a esta turma"):
        WrittenTestService.list_students(test_id, str(CLASS_B1))
    with pytest.raises(LookupError, match="Turma não encontrada nesta avaliação"):
        WrittenTestService.list_students(test_id, str(CLASS_A2))


def test_students_follow_current_class(clock):
    test_id = _published()
    _apply(test_id, [CLASS_B1])
    db.session.get(Student, "st-ana").class_id = CLASS_B1
    db.session.commit()
    names = [s["name"] for s in WrittenTestService.list_students(test_id, str(CLASS_B1))["students"]]
    assert names == ["Ana", "Davi"]


def test_apply_permissions(clock):
    test_id = _published()
    with pytest.raises(PermissionError, match="não pode criar ou alterar avaliações escritas"):
        _apply(test_id, [CLASS_A1], user=APLICADOR)
    with pytest.raises(PermissionError, match="não tem permissão para alterar esta avaliação"):
        _apply(test_id, [CLASS_A1], user=OTHER_PROFESSOR)
    assert _apply(test_id, [CLASS_A1], user=TECADM)["classes"][0]["applied"] is True
    with pytest.raises(PermissionError):
        WrittenTestService.remove_class(APLICADOR, test_id, str(CLASS_A1))
    WrittenTestService.remove_class(ADMIN, test_id, str(CLASS_A1))
    assert ReadingWrittenTestClass.query.count() == 0


def test_detail_and_list_show_application_summary(clock):
    test_id = _published()
    detail = svc.to_detail(WrittenTestService.get(test_id))
    assert detail["appliedClassesCount"] == 0
    assert detail["nextApplicationStart"] is None

    _apply(test_id, [CLASS_A1], start="2026-11-12T08:00:00")
    _apply(test_id, [CLASS_B1], start="2026-11-11T08:00:00")
    detail = svc.to_detail(WrittenTestService.get(test_id))
    assert detail["appliedClassesCount"] == 2
    assert detail["nextApplicationStart"] == "2026-11-11T08:00:00"
    assert detail["totalQuestions"] == 19

    clock["now"] = datetime(2026, 11, 11, 12, 0, tzinfo=timezone.utc)  # B1 já começou
    item = WrittenTestService.list_tests({})["data"][0]
    assert item["appliedClassesCount"] == 2
    assert item["nextApplicationStart"] == "2026-11-12T08:00:00"
    assert item["totalQuestions"] == 19


def test_application_routes(clock):
    draft = _create(questions=_items(MC_IDS[:3]))
    response, status = _call_view(
        "apply_written_test", PROFESSOR, draft.id, method="POST",
        json={"classIds": [str(CLASS_A1)], "applicationStart": "2026-11-12T08:00:00"},
    )
    assert status == 400
    assert response.get_json() == {"error": "Só avaliação publicada pode ser aplicada."}

    test_id = _published()
    response, status = _call_view(
        "apply_written_test", PROFESSOR, test_id, method="POST",
        json={"classIds": [str(CLASS_A1)], "applicationStart": "2026-11-12T08:00:00"},
    )
    assert status == 200
    assert response.get_json()["classes"][0]["status"] == "agendada"

    response, status = _call_view("list_written_test_classes", APLICADOR, test_id)
    assert status == 200 and len(response.get_json()["classes"]) == 2

    response, status = _call_view(
        "list_written_test_class_students", APLICADOR, test_id, str(CLASS_A1)
    )
    assert status == 200 and response.get_json()["studentCount"] == 3

    response, status = _call_view(
        "remove_written_test_class", PROFESSOR, test_id, str(CLASS_A1), method="DELETE"
    )
    assert status == 200
    assert response.get_json() == {"message": "Aplicação da turma retirada com sucesso."}


# ---------------------------------------------------------------------------
# PDF da prova (caderno de questões) — sem gerar PDF de verdade
# ---------------------------------------------------------------------------

from types import SimpleNamespace  # noqa: E402

from app.afirme_ler.services import written_test_pdf_service as pdf_svc  # noqa: E402

PDF_ORDER = ["mc-img"] + MC_IDS[:15] + ["dict-1", "dict-2", "prod-1"]


def _published_for_pdf():
    written_test = _create(questions=_items(PDF_ORDER))
    return WrittenTestService.publish(PROFESSOR, written_test.id)


class _FakeMinio:
    def download_file(self, bucket, object_name):
        return b"\x89PNG-fake"


def _pdf_service():
    from app.services.institutional_test_weasyprint_generator import (
        InstitutionalTestWeasyPrintGenerator,
    )

    generator = InstitutionalTestWeasyPrintGenerator()
    generator._minio_service = _FakeMinio()
    generator._load_default_logo = lambda: None
    return pdf_svc.WrittenTestPdfService(generator=generator)


def test_pdf_data_order_numbers_and_letters(flask_app):
    data = pdf_svc.build_pdf_data(_published_for_pdf(), SimpleNamespace(name="Limoeiro", state="AL"))

    assert data["municipality"] == "Limoeiro" and data["state"] == "AL"
    assert data["grades"] == ["1º ano"]
    assert data["total_questions"] == 19
    assert [q["id"] for q in data["questions"]] == PDF_ORDER
    assert [q["number"] for q in data["questions"]] == list(range(1, 20))

    first = data["questions"][0]
    assert first["type"] == "multipleChoice"
    assert first["support_html"] == "<p>Qual é o animal?</p>"
    assert [a["letter"] for a in first["alternatives"]] == ["A", "B", "C"]
    assert first["alternatives"][1]["content_html"] == (
        f'<img src="/questions/mc-img/images/{IMG_ALTERNATIVE}" />'
    )
    assert data["questions"][1]["statement_html"] == "<p>Questão mc-01</p>"


def test_pdf_data_has_no_answer_key(flask_app):
    question = db.session.get(Question, "dict-2")
    question.writing_stimulus = "image"
    question.writing_reference = "cinto de roupa secreto"
    db.session.commit()
    data = pdf_svc.build_pdf_data(_published_for_pdf())
    dictations = data["questions"][16:18]
    production = data["questions"][18]

    assert [item["type"] for item in dictations] == ["dictation", "dictation"]
    assert production["type"] == "text_production"
    for item in (*dictations, production):
        assert item["alternatives"] == [] and item["support_html"] == ""
        assert item["answer_on_card"] is True
    expected_keys = {
        "number", "id", "type", "statement_html", "images", "support_html", "alternatives",
        "answer_on_card",
    }
    assert all(set(q) == expected_keys for q in data["questions"])

    dumped = json.dumps(data, ensure_ascii=False, default=str)
    for forbidden in ("sapato", "borboleta", "cinto de roupa secreto", "isCorrect", "correct", "solution", "SOLUCAO-SECRETA", "value"):
        assert forbidden not in dumped


def test_pdf_html_prints_questions_without_answer_key(flask_app):
    service = _pdf_service()
    data = pdf_svc.build_pdf_data(_published_for_pdf(), SimpleNamespace(name="Limoeiro", state="AL"))
    html = service.render_html(data)

    assert "Limoeiro" in html and "Avaliação escrita — 1º bimestre" in html
    assert "Nome do aluno:" in html and "Escola:" in html and "Turma:" in html and "Data:" in html
    assert html.count('class="question-number"') == 19
    assert html.count("Responda no cartão-resposta.") == 3
    assert "<span class=\"alternative-letter\">C)</span>" in html
    assert "Qual é o animal?" in html
    assert "data:image/png;base64," in html  # imagens do MinIO embutidas
    assert "/questions/mc-img/images/" not in html
    for forbidden in ("sapato", "borboleta", "isCorrect", "SOLUCAO-SECRETA", "Pontuação", "pontos"):
        assert forbidden not in html


def test_pdf_blocks_draft_and_missing_question(flask_app):
    draft = _create(questions=_items(PDF_ORDER))
    with pytest.raises(ValueError, match="Só avaliação publicada pode gerar a prova."):
        pdf_svc.build_pdf_data(draft)

    published = WrittenTestService.publish(PROFESSOR, draft.id)
    table = Question.__table__
    db.session.execute(table.delete().where(table.c.id == "dict-1"))
    db.session.commit()
    with pytest.raises(ValueError, match="dict-1 \\(posição 17\\) não existe mais"):
        pdf_svc.build_pdf_data(WrittenTestService.get(published.id))


def test_pdf_blocks_type_no_longer_allowed(flask_app):
    published = _published_for_pdf()
    db.session.get(Question, "mc-05").question_type = "ligar_colunas"
    db.session.commit()
    with pytest.raises(ValueError, match="tipo ligar_colunas, que não é aceito"):
        pdf_svc.build_pdf_data(WrittenTestService.get(published.id))


@pytest.mark.parametrize(
    "title, expected",
    [
        ("Avaliação escrita — 1º bimestre", "prova_avaliacao_escrita_1o_bimestre.pdf"),
        ("Prova/../../etc", "prova_provaetc.pdf"),
        ("!!!", "prova_avaliacao.pdf"),
        ("", "prova_avaliacao.pdf"),
    ],
)
def test_pdf_filename_is_safe(title, expected):
    assert pdf_svc.pdf_filename(title) == expected


def test_pdf_route(flask_app):
    from app.afirme_ler.routes import written_tests_routes as module
    from app.services.institutional_test_weasyprint_generator import (
        InstitutionalTestWeasyPrintGenerator,
    )

    published = _published_for_pdf()
    city = SimpleNamespace(name="Limoeiro", state="AL", logo_url=None)
    with patch.object(module, "resolve_context_city", return_value=city), \
            patch.object(InstitutionalTestWeasyPrintGenerator, "_html_to_pdf_bytes",
                         return_value=b"%PDF-1.4 fake") as render, \
            patch.object(InstitutionalTestWeasyPrintGenerator, "_load_default_logo",
                         return_value=None), \
            patch.object(InstitutionalTestWeasyPrintGenerator, "_get_minio_service",
                         return_value=_FakeMinio()):
        response = _call_view("download_written_test_pdf", APLICADOR, published.id)

        assert response.status_code == 200
        assert response.mimetype == "application/pdf"
        assert response.headers["Content-Disposition"] == (
            "attachment; filename=prova_avaliacao_escrita_1o_bimestre.pdf"
        )
        response.direct_passthrough = False
        assert response.get_data() == b"%PDF-1.4 fake"
        html = render.call_args.args[0]
        assert "sapato" not in html and "borboleta" not in html and html.count('class="question-number"') == 19

        draft = _create(questions=_items(MC_IDS[:2]))
        response, status = _call_view("download_written_test_pdf", PROFESSOR, draft.id)
        assert status == 400
        assert response.get_json() == {"error": "Só avaliação publicada pode gerar a prova."}

        response, status = _call_view("download_written_test_pdf", PROFESSOR, "nao-existe")
        assert status == 404


# ---------------------------------------------------------------------------
# Cartões-resposta — sem WeasyPrint, Celery nem MinIO de verdade
# ---------------------------------------------------------------------------

import io  # noqa: E402
import zipfile  # noqa: E402
from datetime import timedelta  # noqa: E402

from pypdf import PdfReader  # noqa: E402

from app.afirme_ler.services import written_test_answer_sheet_service as cards  # noqa: E402


def _fake_pdf(pages=2):
    from reportlab.pdfgen.canvas import Canvas

    buffer = io.BytesIO()
    canvas = Canvas(buffer)
    for page in range(pages):
        canvas.drawString(100, 100, f"base {page + 1}")
        canvas.showPage()
    canvas.save()
    return buffer.getvalue()


def _published_applied(class_ids=(CLASS_A1,)):
    written_test = _published_for_pdf()
    if class_ids:
        _apply(written_test.id, list(class_ids))
    return WrittenTestService.get(written_test.id)


def test_card_items_letters_lines_and_no_answer_key(flask_app):
    items = cards.build_card_items(_published_for_pdf())

    assert [i["number"] for i in items] == list(range(1, 20))
    assert [i["question_id"] for i in items] == PDF_ORDER
    assert items[0] == {"number": 1, "question_id": "mc-img", "type": "multipleChoice",
                        "letters": ["A", "B", "C"]}
    assert items[1]["letters"] == ["A", "B"]
    assert items[16] == {"number": 17, "question_id": "dict-1", "type": "dictation"}
    assert items[17] == {"number": 18, "question_id": "dict-2", "type": "dictation"}
    assert items[18] == {"number": 19, "question_id": "prod-1", "type": "text_production", "lines": 15}

    dumped = json.dumps(items, ensure_ascii=False)
    for forbidden in ("sapato", "borboleta", "isCorrect", "correct", "solution", "SOLUCAO", "value", "Gato"):
        assert forbidden not in dumped


def test_card_items_letters_stop_at_h(flask_app):
    db.session.get(Question, "mc-03").alternatives = [
        {"id": chr(65 + i), "text": f"op {i}", "isCorrect": i == 0} for i in range(10)
    ]
    db.session.commit()
    items = cards.build_card_items(_published_for_pdf())
    assert items[[i["question_id"] for i in items].index("mc-03")]["letters"] == list("ABCDEFGH")


def test_card_html_has_bubbles_lines_and_no_answer_key(flask_app):
    written_test = _published_for_pdf()
    items = cards.build_card_items(written_test)
    html = cards.render_card_html(written_test, items, generator=_pdf_service().generator)

    assert html.count('class="bubble"') == 3 + 15 * 2
    assert html.count('class="row-anchor"') == 19
    assert html.count('class="dictation-area"') == 2
    assert html.count('class="writing-line"') == 15
    assert html.count('class="num"') == 19
    assert html.count("@top-left-corner") == 1 and html.count("@bottom-right-corner") == 1
    assert "width: 340px" in html and "height: 482px" in html
    for forbidden in ("sapato", "borboleta", "isCorrect", "SOLUCAO-SECRETA", "Pontuação", "Gato", "Qual é o animal"):
        assert forbidden not in html


def test_card_qr_payload_format():
    payload = cards.build_qr_payload("st-caio-1234567890", "caead568-498e-47ec-9155-ad43a480a058", 1, 2)
    assert payload == {"v": 1, "student_id": "st-caio-1234", "written_test_id": "caead568-498", "p": "1/2"}
    assert cards.qr_text("st-caio-1234567890", "caead568-498e-47ec", 2, 2) == (
        '{"v":1,"student_id":"st-caio-1234","written_test_id":"caead568-498","p":"2/2"}'
    )
    with pytest.raises(ValueError):
        cards.build_qr_payload("st", "wt", 3, 2)
    with pytest.raises(ValueError):
        cards.build_qr_payload("", "wt", 1, 1)


def test_card_map_from_pdf_content():
    items = [
        {"number": 1, "question_id": "q1", "type": "multipleChoice", "letters": ["A", "B"]},
        {"number": 2, "question_id": "q2", "type": "dictation"},
        {"number": 3, "question_id": "q3", "type": "text_production", "lines": 15},
    ]

    def image(x, y, w, h):
        return f"q 1 0 0 1 {x} {y} cm 0 0 {w} {h} re W n /Im1 Do Q"

    page_1 = " ".join([
        "q 0.75 0 0 0.75 0 0 cm",
        image(5, 5, 32, 32),           # quadrado de canto: ignorado
        "0 0 500 20 re f",             # borda/linha sem imagem: ignorada
        image(100, 300, 340, 44),      # linha do ditado (fundo de bloco vem antes das bolhas)
        image(80, 600, 8, 8),          # quadrado da questão 1
        image(100, 600, 12, 12),       # bolha A
        image(130, 600, 12, 12),       # bolha B
        image(80, 300, 8, 8),          # quadrado da questão 2
        "Q",
    ])
    page_2 = " ".join([
        "q 0.75 0 0 0.75 0 0 cm",
        image(40, 100, 660, 482),
        image(50, 400, 8, 8),          # quadrado da questão 3
        "Q",
    ])

    result = cards.build_answer_sheet_map_from_pages([page_1, page_2], items, "wt-1")
    assert result["page_count"] == 2 and result["written_test_id"] == "wt-1"
    first, second = result["pages"]
    assert [(b["number"], b["letter"]) for b in first["bubbles"]] == [(1, "A"), (1, "B")]
    bubble_a = first["bubbles"][0]
    assert bubble_a["cx"] == pytest.approx(79.5) and bubble_a["cy"] == pytest.approx(454.5)
    assert bubble_a["r"] == pytest.approx(4.5)
    assert set(bubble_a["pixel"]) == {"x", "y", "r"}
    assert [(a["number"], a["type"]) for a in first["row_anchors"]] == [
        (1, "multipleChoice"), (2, "dictation"),
    ]
    assert second["row_anchors"][0]["number"] == 3
    assert set(first["row_anchors"][0]["pixel"]) == {"x", "y"}
    assert first["writing_areas"][0]["type"] == "dictation"
    assert first["writing_areas"][0]["right"] - first["writing_areas"][0]["left"] == pytest.approx(255.0)
    assert second["bubbles"] == []
    area = second["writing_areas"][0]
    assert (area["number"], area["type"]) == (3, "text_production")
    assert area["pixel"]["width"] > 0 and area["pixel"]["height"] > 0

    with pytest.raises(ValueError, match="1 bolhas e a avaliação tem 2"):
        cards.build_answer_sheet_map_from_pages([page_1.replace(image(130, 600, 12, 12), "")], items, "wt-1")
    with pytest.raises(ValueError, match="não corresponde ao tipo"):
        swapped = page_1.replace("340 44", "660 482")
        cards.build_answer_sheet_map_from_pages([swapped, page_2.replace("660 482", "340 44")], items, "wt-1")


def test_card_zip_names_do_not_collide_for_homonyms(flask_app, tmp_path):
    from app.socioeconomic_forms.services.print_package import write_print_zip

    db.session.add(Student(id="st-ana-2", name="Ana", class_id=CLASS_A1, school_id=SCHOOL_A, grade_id=GRADE_1))
    db.session.commit()
    students = cards.list_card_students([str(CLASS_A1)])
    assert [s["name"] for s in students] == ["Ana", "Ana", "Bia", "Caio"]
    assert students[0]["school_name"] == "Escola A" and students[0]["grade_name"] == "1º ano"

    zip_path = str(tmp_path / "cards.zip")
    stats = write_print_zip(zip_path, b"%PDF base", "wt-1", students, personalize=lambda base, **kw: b"%PDF aluno")
    assert stats["generated"] == 4
    names = zipfile.ZipFile(zip_path).namelist()
    assert len(set(names)) == 4
    anas = [n for n in names if "/ana_" in n]
    assert len(anas) == 2 and anas[0] != anas[1]
    assert all(n.startswith("municipio_municipio/escola_escola_a/serie_1o_ano/turma_1o_a/") for n in names)


def test_create_run_rules(flask_app, clock):
    draft = _create(questions=_items(PDF_ORDER))
    with pytest.raises(ValueError, match="Só avaliação publicada pode gerar os cartões-resposta."):
        cards.create_run(APLICADOR, draft.id, {})
    db.session.rollback()

    published = _published_applied(class_ids=())
    with pytest.raises(ValueError, match="ainda não foi aplicada a nenhuma turma"):
        cards.create_run(APLICADOR, published.id, {})
    _apply(published.id, [CLASS_A1])
    with pytest.raises(ValueError, match="A turma 1º B não está aplicada nesta avaliação."):
        cards.create_run(APLICADOR, published.id, {"classId": str(CLASS_B1)})
    with pytest.raises(ValueError, match="classId inválido"):
        cards.create_run(APLICADOR, published.id, {"classId": "x"})

    run = cards.create_run(APLICADOR, published.id, {})
    assert (run.status, run.total_students, run.class_id, run.created_by) == ("pendente", 3, None, "u-apl")

    with pytest.raises(cards.GenerationInProgress):
        cards.create_run(PROFESSOR, published.id, {"classId": str(CLASS_A1)})

    run.created_at = datetime.utcnow() - timedelta(minutes=31)
    db.session.commit()
    second = cards.create_run(PROFESSOR, published.id, {"classId": str(CLASS_A1)})
    assert str(second.class_id) == str(CLASS_A1)
    with pytest.raises(cards.GenerationInProgress):
        cards.create_run(PROFESSOR, published.id, {})
    second.status = "concluido"
    db.session.commit()
    assert cards.create_run(PROFESSOR, published.id, {}).status == "pendente"


def test_create_run_without_students(flask_app, clock):
    published = _published_applied(class_ids=(CLASS_B1,))
    db.session.get(Student, "st-davi").class_id = CLASS_A2
    db.session.commit()
    with pytest.raises(ValueError, match="Nenhum aluno nas turmas aplicadas."):
        cards.create_run(PROFESSOR, published.id, {})


def _run_generation(run_id, upload=None, map_side_effect=None):
    uploaded = {}

    def fake_upload(self, bucket, object_name, path):
        with zipfile.ZipFile(path) as archive:
            uploaded["files"] = {name: archive.read(name) for name in archive.namelist()}
        uploaded["bucket"], uploaded["object_name"] = bucket, object_name
        return {"bucket": bucket, "object_name": object_name} if upload is None else upload

    from app.services.storage.minio_service import MinIOService

    with patch.object(cards, "render_base_pdf", return_value=_fake_pdf(2)), \
            patch.object(cards, "extract_answer_sheet_map",
                         side_effect=map_side_effect, return_value={"version": 1, "pages": []}), \
            patch.object(MinIOService, "__init__", lambda self: None), \
            patch.object(MinIOService, "upload_from_path", fake_upload):
        result = cards.run_generation(run_id)
    return result, uploaded


def test_run_generation_builds_zip_with_overlay(flask_app, clock):
    published = _published_applied()
    run = cards.create_run(PROFESSOR, published.id, {})

    result, uploaded = _run_generation(run.id)
    assert result == {"success": True, "generated": 3, "failed": 0}

    stored = db.session.get(ReadingWrittenTestPrintRun, run.id)
    assert stored.status == "concluido" and stored.generated_count == 3 and stored.total_students == 3
    assert stored.minio_bucket == "afirme-reading-audio"
    assert stored.minio_object_name == f"afirme-ler/written-tests/{published.id}/runs/{run.id}.zip"
    assert stored.answer_sheet_map == {"version": 1, "pages": []}
    assert stored.started_at is not None and stored.finished_at is not None and stored.error_message is None

    assert uploaded["object_name"] == stored.minio_object_name
    pdfs = uploaded["files"]
    assert len(pdfs) == 3
    caio = next(content for name, content in pdfs.items() if "/caio_" in name)
    reader = PdfReader(io.BytesIO(caio))
    assert len(reader.pages) == 2
    page_1 = reader.pages[0].extract_text()
    assert "CAIO" in page_1 and "ESCOLA A" in page_1 and "1º ANO - 1º A" in page_1
    assert "FOLHA 1 DE 2" in page_1 and "FOLHA 2 DE 2" in reader.pages[1].extract_text()
    assert "Avaliação escrita — 1º bimestre" in page_1
    assert "sapato" not in page_1


def test_run_generation_keeps_zip_when_map_fails_and_fails_without_upload(flask_app, clock):
    published = _published_applied()
    run = cards.create_run(PROFESSOR, published.id, {})
    _run_generation(run.id, map_side_effect=ValueError("O cartão desenhou 0 bolhas e a avaliação tem 37."))
    stored = db.session.get(ReadingWrittenTestPrintRun, run.id)
    assert stored.status == "concluido"
    assert "Mapa do cartão não extraído" in stored.error_message
    assert stored.answer_sheet_map["error"].startswith("O cartão desenhou 0 bolhas")

    second = cards.create_run(PROFESSOR, published.id, {"classId": str(CLASS_A1)})
    result, _ = _run_generation(second.id, upload={})
    assert result["success"] is False
    stored = db.session.get(ReadingWrittenTestPrintRun, second.id)
    assert stored.status == "erro" and "Falha ao enviar o ZIP" in stored.error_message
    assert stored.minio_object_name is None


def test_answer_sheet_routes(flask_app, clock):
    from app.afirme_ler.routes import written_tests_routes as module
    from app.afirme_ler import tasks
    from app.services.storage.minio_service import MinIOService

    draft = _create(questions=_items(PDF_ORDER))
    with patch.object(module, "_context_city_id", return_value=CITY_ID):
        response, status = _call_view("create_written_test_answer_sheets", APLICADOR, draft.id, method="POST")
    assert status == 400
    assert response.get_json() == {"error": "Só avaliação publicada pode gerar os cartões-resposta."}

    published = _published_applied()
    with patch.object(module, "_context_city_id", return_value=CITY_ID), \
            patch.object(tasks.generate_written_test_answer_sheets, "delay",
                         return_value=SimpleNamespace(id="task-123")) as delay:
        response, status = _call_view(
            "create_written_test_answer_sheets", APLICADOR, published.id, method="POST", json={},
        )
        assert status == 202
        body = response.get_json()
        assert body["status"] == "pendente" and body["taskId"] == "task-123"
        assert body["totalStudents"] == 3 and body["allClasses"] is True and body["zipAvailable"] is False
        delay.assert_called_once_with(body["id"], CITY_ID)

        response, status = _call_view(
            "create_written_test_answer_sheets", APLICADOR, published.id, method="POST",
            json={"classId": str(CLASS_A1)},
        )
        assert status == 409
        assert response.get_json()["run"]["id"] == body["id"]

    response, status = _call_view("list_written_test_answer_sheets", APLICADOR, published.id)
    assert status == 200 and [r["id"] for r in response.get_json()["runs"]] == [body["id"]]

    response, status = _call_view(
        "download_written_test_answer_sheets", APLICADOR, published.id, body["id"],
    )
    assert status == 400
    assert "ainda não foi concluída" in response.get_json()["error"]

    run = db.session.get(ReadingWrittenTestPrintRun, body["id"])
    run.status, run.minio_bucket, run.minio_object_name = "concluido", "afirme-reading-audio", "x.zip"
    db.session.commit()
    with patch.object(MinIOService, "__init__", lambda self: None), \
            patch.object(MinIOService, "download_file", return_value=b"PK zip") as download:
        response = _call_view("download_written_test_answer_sheets", APLICADOR, published.id, body["id"])
        assert response.status_code == 200 and response.mimetype == "application/zip"
        assert response.headers["Content-Disposition"] == (
            "attachment; filename=cartoes_avaliacao_escrita_1o_bimestre.zip"
        )
        response.direct_passthrough = False
        assert response.get_data() == b"PK zip"
        download.assert_called_once_with("afirme-reading-audio", "x.zip")

    response, status = _call_view("download_written_test_answer_sheets", APLICADOR, published.id, "nao-existe")
    assert status == 404


def test_ddl_print_run_table():
    ddl = get_afirme_ler_written_test_tables_ddl("city_teste")
    assert 'CREATE TABLE IF NOT EXISTS "city_teste".reading_written_test_print_run (' in ddl
    assert "CHECK (status IN ('pendente', 'processando', 'concluido', 'erro'))" in ddl
    assert "answer_sheet_map JSON" in ddl
    assert 'CREATE TABLE IF NOT EXISTS "city_teste".reading_written_test_correction (' in ddl
    assert "UNIQUE (written_test_id, student_id)" in ddl
    assert "objective JSON NOT NULL DEFAULT '{}'::json" in ddl
    assert "writing JSON NOT NULL DEFAULT '{}'::json" in ddl
    assert "ADD COLUMN IF NOT EXISTS writing JSON" in ddl
    assert 'class_id UUID REFERENCES "city_teste".class(id) ON DELETE CASCADE' in ddl


# ---------------------------------------------------------------------------
# Correção do cartão
# ---------------------------------------------------------------------------

def _filled_page():
    """Folha já alinhada: o quadrado e a bolha A estão 20px à direita e abaixo do mapa."""
    import cv2
    import numpy as np

    image = np.full((420, 520, 3), 255, np.uint8)
    cv2.rectangle(image, (50, 90), (70, 110), (0, 0, 0), -1)
    cv2.circle(image, (160, 100), 12, (0, 0, 0), -1)
    cv2.line(image, (140, 230), (280, 230), (0, 0, 0), 3)
    page = {
        "page": 1,
        "bubbles": [
            {"number": 1, "question_id": "q1", "letter": "A", "option_index": 0,
             "pixel": {"x": 140, "y": 80, "r": 14}},
            {"number": 1, "question_id": "q1", "letter": "B", "option_index": 1,
             "pixel": {"x": 220, "y": 80, "r": 14}},
        ],
        "writing_areas": [{
            "number": 17, "question_id": "dict-1", "type": "dictation",
            "pixel": {"x": 120, "y": 200, "width": 180, "height": 50},
        }],
        "row_anchors": [
            {"number": 1, "question_id": "q1", "type": "multipleChoice", "pixel": {"x": 40, "y": 80}},
            {"number": 17, "question_id": "dict-1", "type": "dictation", "pixel": {"x": 40, "y": 250}},
        ],
    }
    return image, page


def test_black_square_shifts_the_bubble_and_the_crop_is_a_png(flask_app):
    from app.afirme_ler.services import written_test_answer_sheet_correction as reading

    image, page = _filled_page()
    answers, blank, invalid, crops = reading.interpret_aligned_page(image, page)

    assert answers["q1"] == {"number": 1, "letter": "A"}
    assert blank == [] and invalid == []
    assert crops["dict-1"]["png"].startswith(b"\x89PNG")
    assert len(crops["dict-1"]["png"]) > 50


def test_correction_saves_letters_and_three_images(flask_app):
    import cv2
    import numpy as np

    from app.afirme_ler.services import written_test_answer_sheet_correction as reading

    written_test = _published_for_pdf()
    image, page = _filled_page()
    answers, blank, invalid, crops = reading.interpret_aligned_page(image, page)

    bilhete = np.full((300, 400, 3), 255, np.uint8)
    cv2.rectangle(bilhete, (30, 40), (46, 56), (0, 0, 0), -1)
    cv2.line(bilhete, (80, 80), (200, 120), (0, 0, 0), 2)
    bilhete_page = {
        "page": 2,
        "bubbles": [],
        "writing_areas": [{
            "number": 19, "question_id": "prod-1", "type": "text_production",
            "pixel": {"x": 60, "y": 60, "width": 180, "height": 80},
        }],
        "row_anchors": [{
            "number": 19, "question_id": "prod-1", "type": "text_production",
            "pixel": {"x": 38, "y": 48},
        }],
    }
    _, _, _, bilhete_crops = reading.interpret_aligned_page(bilhete, bilhete_page)
    assert "prod-1" in bilhete_crops

    uploaded = {}

    class FakeMinio:
        BUCKETS = {"AFIRME_READING_AUDIO": "afirme-reading-audio"}

        def upload_file(self, bucket, name, data, content_type=None, metadata=None):
            uploaded[(bucket, name)] = bytes(data)
            return {"bucket": bucket, "object_name": name}

    prefix = "st-caio"
    first = {
        "qr": {"student_id": prefix, "written_test_id": written_test.id[:12], "page": 1, "page_count": 2},
        "answers": answers, "blank": blank, "invalid": invalid, "crops": crops,
    }
    second = {
        "qr": {"student_id": prefix, "written_test_id": written_test.id[:12], "page": 2, "page_count": 2},
        "answers": {}, "blank": [], "invalid": [], "crops": {
            "dict-2": {"number": 18, "type": "dictation", "png": crops["dict-1"]["png"]},
            **bilhete_crops,
        },
    }
    with patch("app.services.storage.minio_service.MinIOService", FakeMinio):
        saved = reading.save_student_pages(written_test.id, prefix, [first, second], 2)

    assert saved["saved"] is True
    assert saved["studentId"] == "st-caio"
    assert saved["answers"] == [{"number": 1, "questionId": "q1", "letter": "A"}]
    assert saved["missingPages"] == []
    assert [item["number"] for item in saved["crops"]] == [17, 18, 19]
    assert all(item["saved"] for item in saved["crops"])
    assert saved["crops"][0]["imageUrl"] == (
        f"/afirme-reading/written-tests/{written_test.id}"
        "/answer-sheet-corrections/st-caio/crops/17"
    )
    assert len(uploaded) == 3
    assert all(body.startswith(b"\x89PNG") for body in uploaded.values())

    class ReadingMinio(FakeMinio):
        def download_file(self, bucket, name):
            return uploaded[(bucket, name)]

    with patch("app.services.storage.minio_service.MinIOService", ReadingMinio):
        response = _call_view(
            "download_written_test_crop",
            PROFESSOR,
            written_test.id,
            "st-caio",
            17,
            method="GET",
        )
    assert response.status_code == 200
    assert response.mimetype == "image/png"
    response.direct_passthrough = False
    assert response.get_data().startswith(b"\x89PNG")

    stored = ReadingWrittenTestCorrection.query.filter_by(student_id="st-caio").one()
    assert stored.answers["q1"]["letter"] == "A"
    assert stored.pages == [1, 2]

    with patch("app.services.storage.minio_service.MinIOService", FakeMinio):
        again = reading.save_student_pages(written_test.id, prefix, [second], 2)
    assert again["answers"] == [{"number": 1, "questionId": "q1", "letter": "A"}]


def test_scan_with_corners_and_qr_reads_the_letter_and_the_crop(flask_app):
    """Imagem sintética com os quatro cantos, o QR, a bolha e o retângulo de escrita."""
    import cv2
    import numpy as np
    import qrcode

    from app.afirme_ler.services.written_test_answer_sheet_correction import read_card_image
    from app.afirme_ler.services.written_test_answer_sheet_service import qr_text

    written_test = _published_for_pdf()
    width, height, side = 1200, 1600, 48
    source = np.float32([[20, 20], [width - 20, 20], [width - 20, height - 20], [20, height - 20]])
    destination = np.float32([[0, 0], [2480, 0], [2480, 3508], [0, 3508]])
    inverse = cv2.getPerspectiveTransform(destination, source)

    def place(x, y):
        point = cv2.perspectiveTransform(np.float32([[[x, y]]]), inverse)[0, 0]
        return int(round(point[0])), int(round(point[1]))

    image = np.full((height, width, 3), 255, np.uint8)
    for x, y in (
        (20, 20),
        (width - 20 - side, 20),
        (20, height - 20 - side),
        (width - 20 - side, height - 20 - side),
    ):
        cv2.rectangle(image, (x, y), (x + side, y + side), (0, 0, 0), -1)

    code = qrcode.make(qr_text("st-caio", written_test.id, 1, 1)).convert("RGB").resize((180, 180))
    image[300:480, 400:580] = cv2.cvtColor(np.array(code), cv2.COLOR_RGB2BGR)

    anchor_x, anchor_y = place(400, 700)
    cv2.rectangle(image, (anchor_x - 8, anchor_y - 8), (anchor_x + 8, anchor_y + 8), (0, 0, 0), -1)
    bubble_x, bubble_y = place(560, 700)
    cv2.circle(image, (bubble_x, bubble_y), 14, (0, 0, 0), -1)
    line_start, line_end = place(420, 920), place(680, 960)
    cv2.line(image, line_start, line_end, (0, 0, 0), 4)

    sheet = {
        "written_test_id": written_test.id,
        "page_count": 1,
        "pages": [{
            "page": 1,
            "bubbles": [
                {"number": 1, "question_id": "q1", "letter": "A", "option_index": 0,
                 "pixel": {"x": 560, "y": 700, "r": 18}},
                {"number": 1, "question_id": "q1", "letter": "B", "option_index": 1,
                 "pixel": {"x": 720, "y": 700, "r": 18}},
            ],
            "writing_areas": [{
                "number": 17, "question_id": "dict-1", "type": "dictation",
                "pixel": {"x": 400, "y": 900, "width": 300, "height": 80},
            }],
            "row_anchors": [
                {"number": 1, "question_id": "q1", "type": "multipleChoice", "pixel": {"x": 400, "y": 700}},
                {"number": 17, "question_id": "dict-1", "type": "dictation", "pixel": {"x": 400, "y": 1100}},
            ],
        }],
    }
    read = read_card_image(image, sheet)
    assert read["status"] == "read"
    assert read["answers"]["q1"] == {"number": 1, "letter": "A"}
    assert read["blank"] == [] and read["invalid"] == []
    assert read["crops"]["dict-1"]["png"].startswith(b"\x89PNG")
    assert len(read["crops"]["dict-1"]["png"]) > 50


def test_page_without_corner_squares_is_skipped():
    import numpy as np

    from app.afirme_ler.services.written_test_answer_sheet_correction import read_card_image

    white = np.full((200, 160, 3), 255, np.uint8)
    read = read_card_image(white, {"written_test_id": "wt", "page_count": 1, "pages": []})
    assert read["status"] == "skipped"
    assert read["reason"] == "sem quadrados de canto"


def test_correction_route_skips_a_blank_image_and_requires_the_map(flask_app):
    import base64

    import cv2
    import numpy as np

    published = _published_for_pdf()
    ok, encoded = cv2.imencode(".png", np.full((60, 60, 3), 255, np.uint8))
    assert ok
    payload = {"images": [base64.b64encode(encoded.tobytes()).decode()]}

    response, status = _call_view(
        "correct_written_test_answer_sheets", APLICADOR, published.id, method="POST", json=payload,
    )
    assert status == 400
    assert "quadrado de cada questão" in response.get_json()["error"]

    db.session.add(ReadingWrittenTestPrintRun(
        written_test_id=published.id,
        created_by=PROFESSOR["id"],
        status="concluido",
        answer_sheet_map={
            "version": 2,
            "written_test_id": published.id,
            "page_count": 1,
            "pages": [{"page": 1, "bubbles": [], "writing_areas": [], "row_anchors": [
                {"number": 1, "question_id": "q1"},
            ]}],
        },
    ))
    db.session.commit()
    response, status = _call_view(
        "correct_written_test_answer_sheets", APLICADOR, published.id, method="POST", json=payload,
    )
    assert status == 200
    body = response.get_json()
    assert body["students"] == []
    assert body["skipped"][0]["reason"] == "sem quadrados de canto"


def _ai_payload():
    return {
        "palavras": [
            {"numero": 17, "pontos": 2, "transcricao_original": "sapato",
             "confianca_leitura": "ALTA", "status": "CORRIGIDA"},
            {"numero": 18, "pontos": 1, "transcricao_original": "borb",
             "confianca_leitura": "ALTA", "justificativa": "faltou o final"},
        ],
        "producao_textual": {
            "transcricao_original": "MAMAE AMANHA",
            "adequacao": 2, "tipologia": 2, "uso_pagina": 2, "ortografia": 1,
            "pontuacao": 0, "coesao": 2, "segmentacao": 2,
            "confianca_leitura": "ALTA",
        },
        "devolutiva": {
            "aprendizagens_demonstradas": ["escreve o destinatário"],
            "dificuldades_identificadas": ["ortografia"],
            "intervencoes_recomendadas": ["revisar o final das palavras"],
            "observacoes_para_professor": "conferir a questão 18",
        },
    }


class _FakeChoice:
    def __init__(self, content):
        self.message = type("Message", (), {"content": content})()


def _reading_payload(word_18):
    return {
        "questoes": [
            {"numero": 17, "transcricao_literal": "sapato", "situacao": "legivel",
             "trechos_duvidosos": []},
            {"numero": 18, "transcricao_literal": word_18, "situacao": "legivel",
             "trechos_duvidosos": []},
            {"numero": 19, "transcricao_literal": "MAMAE AMANHA", "situacao": "legivel",
             "trechos_duvidosos": []},
        ]
    }


class _FakeOpenAI:
    calls = []
    second_word = "borb"

    def __init__(self, api_key=None, timeout=None):
        self.api_key = api_key

    class chat:
        class completions:
            @staticmethod
            def create(**kwargs):
                _FakeOpenAI.calls.append(kwargs)
                system = kwargs["messages"][0]["content"]
                if "TRANSCRICAO_LITERAL" in system:
                    word = _FakeOpenAI.second_word if kwargs.get("model") != "gpt-4o" else "borb"
                    content = json.dumps(_reading_payload(word))
                else:
                    content = json.dumps(_ai_payload())
                return type("Response", (), {"choices": [_FakeChoice(content)]})()


def _message_text(call):
    parts = call["messages"][1]["content"]
    return "\n".join(part.get("text", "") for part in parts if part.get("type") == "text")


def test_objective_score_uses_the_answer_key_and_ai_grades_only_the_writing(flask_app, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o")
    monkeypatch.setenv("OPENAI_MODEL_RELEITURA", "gpt-4o-mini")
    _FakeOpenAI.calls = []
    _FakeOpenAI.second_word = "borb"

    from app.afirme_ler.services import written_test_answer_sheet_correction as reading
    from app.afirme_ler.services.written_test_writing_grade import grade_scanned_writing

    written_test = _published_for_pdf()
    links = (
        ReadingWrittenTestQuestion.query
        .filter_by(written_test_id=written_test.id)
        .order_by(ReadingWrittenTestQuestion.order.asc())
        .all()
    )
    answers = {}
    blank = []
    for link in links:
        if link.order > 16:
            continue
        if link.order == 2:
            answers[link.question_id] = {"number": 2, "letter": "B"}
        elif link.order == 3:
            blank.append({"number": 3, "questionId": link.question_id})
        else:
            answers[link.question_id] = {"number": link.order, "letter": "A"}
    png = b"\x89PNG\r\n\x1a\nfake"
    crops = {}
    for link in links:
        if link.order < 17:
            continue
        crops[link.question_id] = {"number": link.order, "type": "writing", "png": png}
    page = {
        "qr": {"student_id": "st-caio", "written_test_id": written_test.id[:12], "page": 1, "page_count": 2},
        "answers": answers, "blank": blank, "invalid": [], "crops": crops,
    }
    with patch("app.services.storage.minio_service.MinIOService") as minio:
        minio.BUCKETS = {"AFIRME_READING_AUDIO": "afirme-reading-audio"}
        minio.return_value.upload_file.return_value = {"ok": True}
        saved = reading.save_student_pages(written_test.id, "st-caio", [page], 2)

    assert saved["objective"]["points"] == 14
    assert saved["objective"]["maxPoints"] == 16
    by_number = {item["number"]: item for item in saved["objective"]["items"]}
    assert by_number[1]["points"] == 1 and by_number[1]["status"] == "CORRETA"
    assert by_number[2]["points"] == 0 and by_number[2]["status"] == "INCORRETA"
    assert by_number[3]["points"] == 0 and by_number[3]["status"] == "EM_BRANCO"

    with patch("openai.OpenAI", _FakeOpenAI):
        writing = grade_scanned_writing(written_test.id, "st-caio", [page])

    assert len(_FakeOpenAI.calls) == 3
    assert [call["model"] for call in _FakeOpenAI.calls] == ["gpt-4o", "gpt-4o-mini", "gpt-4o"]
    for call in _FakeOpenAI.calls[:2]:
        assert "TRANSCRICAO_LITERAL" in call["messages"][0]["content"]
        assert len(call["messages"]) == 2
        user_text = _message_text(call)
        assert "sapato" not in user_text and "borboleta" not in user_text
        assert "st-caio" not in user_text
        assert sum(1 for part in call["messages"][1]["content"] if part["type"] == "image_url") == 3
    scoring = _FakeOpenAI.calls[2]
    assert "AVALIACAO_PEDAGOGICA" in scoring["messages"][0]["content"]
    assert "Questões 17 e 18" in scoring["messages"][0]["content"]
    score_text = _message_text(scoring)
    assert "sapato" in score_text and "borboleta" in score_text
    assert "st-caio" not in score_text
    assert sum(1 for part in scoring["messages"][1]["content"] if part["type"] == "image_url") == 1
    assert writing["source"] == "ia"
    assert writing["models"]["leitura"] == "gpt-4o"
    assert writing["models"]["releitura"] == "gpt-4o-mini"
    assert writing["words"][0]["transcription"] == "sapato"
    assert len(writing["words"][0]["readings"]) == 2
    assert _FakeOpenAI.calls[0]["messages"] == _FakeOpenAI.calls[1]["messages"]
    assert writing["status"] == "PENDENTE_REVISAO"
    assert writing["wordPoints"] == 3
    assert writing["textPoints"] == 11
    assert writing["words"][1]["needsReview"] is True
    assert writing["words"][1]["points"] == 1
    assert writing["production"]["criteria"]["pontuacao"] == 0
    assert writing["feedback"]["notes"] == "conferir a questão 18"

    stored = ReadingWrittenTestCorrection.query.filter_by(student_id="st-caio").one()
    assert stored.objective["points"] == 14
    assert stored.writing["source"] == "ia"


def test_readings_agree_on_case_and_diverge_on_spelling_or_lines(flask_app):
    from app.afirme_ler.services.written_test_writing_grade import readings_agree

    legible = {"situation": "legivel", "uncertain": []}
    assert readings_agree(
        {**legible, "transcription": "BOBOLETA"},
        {**legible, "transcription": "boboleta"},
        "word",
    )
    assert not readings_agree(
        {**legible, "transcription": "BOBOLETA"},
        {**legible, "transcription": "BORBOLETA"},
        "word",
    )
    assert not readings_agree(
        {**legible, "transcription": "MAMAE\nAMANHA"},
        {**legible, "transcription": "MAMAE AMANHA"},
        "text",
    )
    assert readings_agree(
        {"situation": "em_branco", "uncertain": [], "transcription": ""},
        {"situation": "em_branco", "uncertain": [], "transcription": ""},
        "word",
    )
    assert not readings_agree(
        {**legible, "transcription": "sapato", "uncertain": ["p"]},
        {**legible, "transcription": "sapato"},
        "word",
    )


def test_divergent_reading_stays_pending_and_skips_that_score(flask_app, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o")
    monkeypatch.setenv("OPENAI_MODEL_RELEITURA", "gpt-4o-mini")
    _FakeOpenAI.calls = []
    _FakeOpenAI.second_word = "casa"

    from app.afirme_ler.services.written_test_writing_grade import grade_scanned_writing

    written_test = _published_for_pdf()
    links = (
        ReadingWrittenTestQuestion.query
        .filter_by(written_test_id=written_test.id)
        .all()
    )
    png = b"\x89PNG\r\n\x1a\nfake"
    crops = {
        link.question_id: {"number": link.order, "type": "writing", "png": png}
        for link in links
        if link.order >= 17
    }
    with patch("openai.OpenAI", _FakeOpenAI):
        writing = grade_scanned_writing(written_test.id, "st-caio", [{"crops": crops}])

    assert len(_FakeOpenAI.calls) == 3
    score_text = _message_text(_FakeOpenAI.calls[2])
    assert "sapato" in score_text
    assert "Questão 18" not in score_text
    assert "borboleta" not in score_text
    pending = writing["words"][1]
    assert pending["points"] is None
    assert pending["needsReview"] is True
    assert pending["status"] == "PENDENTE"
    assert pending["transcription"] == "borb"
    assert pending["secondTranscription"] == "casa"
    assert writing["words"][0]["points"] == 2
    assert writing["wordPoints"] is None
    assert writing["textPoints"] == 11
    assert writing["status"] == "PENDENTE_REVISAO"
    assert writing["published"] is False


def _writing_crops(written_test):
    links = ReadingWrittenTestQuestion.query.filter_by(written_test_id=written_test.id).all()
    png = b"\x89PNG\r\n\x1a\nfake"
    return {
        link.question_id: {"number": link.order, "type": "writing", "png": png}
        for link in links
        if link.order >= 17
    }


def test_image_reference_is_used_only_when_scoring(flask_app, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o")
    monkeypatch.setenv("OPENAI_MODEL_RELEITURA", "gpt-4o-mini")
    _FakeOpenAI.calls = []
    _FakeOpenAI.second_word = "borb"
    question = db.session.get(Question, "dict-1")
    question.writing_stimulus = "image"
    question.writing_reference = "cinto de roupa"
    question.correct_answer = None
    db.session.commit()

    from app.afirme_ler.services.written_test_writing_grade import grade_scanned_writing

    written_test = _published_for_pdf()
    with patch("openai.OpenAI", _FakeOpenAI):
        writing = grade_scanned_writing(
            written_test.id, "st-caio", [{"crops": _writing_crops(written_test)}],
        )

    for call in _FakeOpenAI.calls[:2]:
        assert "cinto de roupa" not in _message_text(call)
    score_text = _message_text(_FakeOpenAI.calls[2])
    assert "descricao_da_imagem: cinto de roupa" in score_text
    assert "tipo_estimulo: IMAGEM" in score_text
    assert writing["words"][0]["stimulus"] == "IMAGEM"
    assert writing["words"][0]["expected"] == "cinto de roupa"
    assert writing["published"] is False
    assert writing["audit"][0]["action"] == "leitura"
    assert writing["promptVersions"]["leitura"] == "transcricao-escrita-1"


def test_teacher_confirms_transcription_before_release(flask_app, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o")
    monkeypatch.setenv("OPENAI_MODEL_RELEITURA", "gpt-4o-mini")
    _FakeOpenAI.calls = []
    _FakeOpenAI.second_word = "casa"

    from app.afirme_ler.services.written_test_writing_grade import grade_scanned_writing

    written_test = _published_for_pdf()
    with patch("openai.OpenAI", _FakeOpenAI):
        grade_scanned_writing(written_test.id, "st-caio", [{"crops": _writing_crops(written_test)}])

    blocked, status = _call_view(
        "release_written_test_writing",
        PROFESSOR,
        written_test.id,
        method="POST",
        json={"studentId": "st-caio"},
    )
    assert status == 400
    assert "pendente" in blocked.get_json()["error"]

    _FakeOpenAI.calls = []
    with patch("openai.OpenAI", _FakeOpenAI):
        response, status = _call_view(
            "review_written_test_writing",
            PROFESSOR,
            written_test.id,
            method="POST",
            json={
                "studentId": "st-caio",
                "words": [{"number": 18, "transcription": "borb"}],
            },
        )
    assert status == 200
    body = response.get_json()["writing"]
    assert body["published"] is False
    assert body["words"][1]["transcription"] == "borb"
    assert body["words"][1]["points"] == 1
    score_text = _message_text(_FakeOpenAI.calls[0])
    assert "transcricao_conferida: borb" in score_text
    assert "palavra_esperada: borboleta" in score_text
    assert "Questão 17" not in score_text
    assert "st-caio" not in score_text
    assert body["audit"][-1]["action"] == "revisao"
    assert body["audit"][-1]["actorId"] == PROFESSOR["id"]

    released, status = _call_view(
        "release_written_test_writing",
        PROFESSOR,
        written_test.id,
        method="POST",
        json={"studentId": "st-caio"},
    )
    assert status == 200
    writing = released.get_json()["writing"]
    assert writing["published"] is True
    assert writing["status"] == "CONCLUIDA"
    assert writing["review"]["decision"] == "liberada"
    assert writing["review"]["reviewerId"] == PROFESSOR["id"]


def test_writing_without_a_card_is_manual_and_skips_openai(flask_app, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    written_test = _published_for_pdf()

    def explode(*_args, **_kwargs):
        raise AssertionError("a IA não deve ser chamada sem cartão")

    with patch("openai.OpenAI", explode):
        response, status = _call_view(
            "save_written_test_writing_correction",
            PROFESSOR,
            written_test.id,
            method="POST",
            json={
                "studentId": "st-caio",
                "words": [
                    {"number": 17, "transcription": "sapato", "points": 2},
                    {"number": 18, "transcription": "borboleta", "points": 2},
                ],
                "production": {
                    "transcription": "MAMAE AMANHA VAI TE FESTA",
                    "adequacao": 2,
                    "tipologia": 2,
                    "usoPagina": 1,
                    "ortografia": 1,
                    "pontuacao": 0,
                    "coesao": 2,
                    "segmentacao": 2,
                },
            },
        )
    assert status == 200
    body = response.get_json()
    assert body["objective"] is None
    assert body["writing"]["source"] == "manual"
    assert body["writing"]["wordPoints"] == 4
    assert body["writing"]["textPoints"] == 10
    assert body["writing"]["model"] is None

    response, status = _call_view(
        "save_written_test_writing_correction",
        PROFESSOR,
        written_test.id,
        method="POST",
        json={"studentId": "st-caio", "words": [{"number": 17, "points": 3}], "production": {}},
    )
    assert status == 400

    response, status = _call_view(
        "list_written_test_answer_sheet_corrections", PROFESSOR, written_test.id,
    )
    assert status == 200
    listed = response.get_json()["students"]
    assert listed[0]["studentId"] == "st-caio"
    assert listed[0]["writing"]["source"] == "manual"
    assert listed[0]["answers"] == []


# ---------------------------------------------------------------------------
# Painel ICA
# ---------------------------------------------------------------------------

def _objective(points):
    items = []
    for number in range(1, 17):
        value = points.get(number, 0)
        items.append({"number": number, "points": value, "status": "CORRIGIDA"})
    return {"items": items, "points": sum(points.get(number, 0) for number in range(1, 17)), "maxPoints": 16}


def _writing(word_a, word_b, text, published=True):
    return {
        "published": published,
        "wordPoints": word_a + word_b,
        "textPoints": text,
        "words": [
            {"number": 17, "points": word_a, "status": "CORRIGIDA"},
            {"number": 18, "points": word_b, "status": "CORRIGIDA"},
        ],
        "production": {"number": 19, "points": text, "status": "CORRIGIDA"},
    }


def _ica_test():
    written_test = _create(questions=_items(_pattern_ids()))
    full = {number: 1 for number in range(1, 17)}
    caio = {number: 1 for number in range(2, 12)}
    db.session.add_all([
        ReadingWrittenTestCorrection(
            written_test_id=written_test.id, student_id="st-ana",
            objective=_objective(full), writing=_writing(2, 2, 14),
        ),
        ReadingWrittenTestCorrection(
            written_test_id=written_test.id, student_id="st-caio",
            objective=_objective(caio), writing=_writing(0, 0, 0),
        ),
        ReadingWrittenTestCorrection(
            written_test_id=written_test.id, student_id="st-bia",
            objective=_objective(full), writing=_writing(2, 2, 14, published=False),
        ),
        ReadingWrittenTestCorrection(
            written_test_id=written_test.id, student_id="st-davi",
            objective=_objective(full), writing=_writing(2, 2, 14),
        ),
    ])
    db.session.commit()
    return written_test


def test_ica_dashboard_scopes_and_one_decimal(flask_app):
    from app.afirme_ler.services.written_test_ica_service import ica_dashboard

    written_test = _ica_test()
    municipal = ica_dashboard(written_test.id, {})
    assert municipal["scope"]["level"] == "municipio"
    assert municipal["participation"] == {
        "expected": 4, "evaluated_diagnostic": 3, "percentage": 75.0,
    }
    assert municipal["diagnostic"] == {"valid": 3, "apt": 2, "iad_percentage": 66.7}
    assert municipal["proficiency_inep"] == {
        "imported_valid": 0, "ica_percentage": None, "status": "SEM_DADOS",
    }
    assert [row["name"] for row in municipal["rows"]] == ["Escola A", "Escola B"]
    school_a = municipal["rows"][0]
    assert school_a["rowLevel"] == "escola"
    assert school_a["expected"] == 3
    assert school_a["evaluated_diagnostic"] == 2
    assert school_a["percentage"] == 66.7
    assert school_a["apt"] == 1
    assert school_a["iad_percentage"] == 50.0
    assert school_a["score"] == 64.7

    school = ica_dashboard(written_test.id, {"escolaId": SCHOOL_A})
    assert school["scope"]["level"] == "escola"
    assert [row["rowLevel"] for row in school["rows"]] == ["serie"]
    assert school["rows"][0]["name"] == "1º ano"
    assert school["rows"][0]["serieId"] == str(GRADE_1)

    grade = ica_dashboard(written_test.id, {"serieId": str(GRADE_1)})
    assert grade["scope"]["level"] == "serie"
    assert [row["name"] for row in grade["rows"]] == ["1º A", "1º B"]
    assert grade["rows"][0]["rowLevel"] == "turma"

    classroom = ica_dashboard(written_test.id, {"turmaId": str(CLASS_A1)})
    assert classroom["scope"]["level"] == "turma"
    assert [row["student_name"] for row in classroom["rows"]] == ["Ana", "Caio"]
    ana = classroom["rows"][0]
    assert ana["reading"] == 16
    assert ana["words"] == 4
    assert ana["text"] == 14
    assert ana["score"] == 100.0
    assert ana["apt"] is True
    caio = classroom["rows"][1]
    assert caio["reading"] == 10
    assert caio["words"] == 0
    assert caio["text"] == 0
    assert caio["score"] == 29.4
    assert caio["apt"] is False

    pending = ica_dashboard(written_test.id, {"estudanteId": "st-bia"})
    assert pending["participation"]["expected"] == 1
    assert pending["participation"]["evaluated_diagnostic"] == 0
    assert pending["participation"]["percentage"] == 0.0
    assert pending["diagnostic"]["iad_percentage"] is None
    assert pending["student"]["finalized"] is False
    assert pending["student"]["reading"] is None
    assert pending["student"]["apt"] is False
    assert pending["rows"][0]["score"] is None

    detail = ica_dashboard(written_test.id, {"estudanteId": "st-ana"})
    assert detail["scope"]["level"] == "aluno"
    assert detail["student"]["finalized"] is True
    assert len(detail["student"]["items"]) == 19
    assert detail["student"]["items"][0]["code"] == "Q1"
    assert detail["student"]["items"][0]["points"] == 1
    assert detail["student"]["items"][18]["code"] == "Q19"
    assert detail["student"]["items"][18]["points"] == 14

    with pytest.raises(ValueError, match="não faz parte"):
        ica_dashboard(written_test.id, {"escolaId": "escola-fora"})


def test_ica_skill_map_and_csv_follow_the_scope(flask_app):
    from app.models.skill import Skill, skill_grade
    from app.afirme_ler.services.written_test_ica_service import ica_csv, skill_map

    db.metadata.create_all(db.engine, tables=[Skill.__table__, skill_grade])
    reading_skill = uuid.UUID("f1f1f1f1-0000-4000-8000-0000000000f1")
    production_skill = uuid.UUID("f2f2f2f2-0000-4000-8000-0000000000f2")
    db.session.add_all([
        Skill(id=reading_skill, code="LEIT01", description="Leitura de palavra", subject_id=SUBJECT_ID),
        Skill(id=production_skill, code="PRO01", description="Produção textual", subject_id=SUBJECT_ID),
    ])
    db.session.get(Question, "mc-01").skill = str(reading_skill)
    db.session.get(Question, "prod-1").skill = str(production_skill)
    db.session.commit()

    written_test = _ica_test()
    payload = skill_map(written_test.id, {})
    by_code = {item["skill_code"]: item for item in payload["skills"]}
    assert payload["max_points"] == 34
    assert payload["valid_attempts"] == 3
    assert by_code["LEIT01"]["items"] == ["Q1"]
    assert by_code["LEIT01"]["max_points_student"] == 1
    assert by_code["LEIT01"]["relative_weight_percentage"] == 2.9
    assert by_code["LEIT01"]["performance_percentage"] == 66.7
    assert by_code["PRO01"]["items"] == ["Q19"]
    assert by_code["PRO01"]["max_points_student"] == 14
    assert by_code["PRO01"]["relative_weight_percentage"] == 41.2
    assert by_code["PRO01"]["performance_percentage"] == 66.7
    assert "dict-1" not in str(payload["skills"])

    one = skill_map(written_test.id, {"estudanteId": "st-caio"})
    caio_skills = {item["skill_code"]: item for item in one["skills"]}
    assert one["valid_attempts"] == 1
    assert caio_skills["LEIT01"]["performance_percentage"] == 0.0
    assert caio_skills["PRO01"]["performance_percentage"] == 0.0

    empty = skill_map(written_test.id, {"estudanteId": "st-bia"})
    assert empty["valid_attempts"] == 0
    assert empty["skills"][0]["performance_percentage"] is None

    content, filename = ica_csv(written_test.id, {"escolaId": SCHOOL_B})
    assert filename == "resultados_ica.csv"
    lines = content.decode("utf-8").strip().split("\n")
    assert lines[0] == "aluno_id;aluno;turma;leitura;palavras;texto;total;nota_100;apto_diagnostico"
    assert lines[1] == "st-davi;Davi;1º B;16;4;14;34;100.0;SIM"
    assert len(lines) == 2


def test_ica_routes_return_dashboard_and_csv(flask_app):
    written_test = _ica_test()
    response, status = _call_view(
        "written_test_ica_dashboard", PROFESSOR, written_test.id,
        path=f"/afirme-reading/written-tests/{written_test.id}/ica-dashboard?turmaId={CLASS_A1}",
    )
    assert status == 200
    body = response.get_json()
    assert body["scope"]["level"] == "turma"
    assert body["participation"]["evaluated_diagnostic"] == 2

    response, status = _call_view(
        "written_test_ica_dashboard", PROFESSOR, written_test.id,
        path=f"/afirme-reading/written-tests/{written_test.id}/ica-dashboard?escolaId=fora",
    )
    assert status == 400
    assert response.get_json()["error"] == "A escola não faz parte desta avaliação."

    response = _call_view(
        "written_test_ica_csv", PROFESSOR, written_test.id,
        path=f"/afirme-reading/written-tests/{written_test.id}/results.csv",
    )
    assert response.status_code == 200
    assert response.mimetype == "text/csv"
    response.direct_passthrough = False
    text = response.get_data(as_text=True)
    assert text.split("\n")[0].startswith("aluno_id;aluno;turma;")
    assert "st-bia" not in text
    assert "st-ana" in text
    assert "29.4" in text
