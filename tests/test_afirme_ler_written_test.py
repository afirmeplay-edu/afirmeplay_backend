# -*- coding: utf-8 -*-
"""
Avaliação escrita do Afirme Ler (tenant.reading_written_test*).

Roda em SQLite em memória (schemas "public" e "tenant" anexados); não conecta no Postgres.
Execução: python -m pytest tests/test_afirme_ler_written_test.py -q
"""
import inspect
import uuid
from unittest.mock import patch

import pytest
from flask import Flask
from sqlalchemy import event
from sqlalchemy.pool import StaticPool

from app import db
import app.models  # noqa: F401  registra todos os mappers
from app.models.educationStage import EducationStage
from app.models.grades import Grade
from app.models.question import Question
from app.models.school import School
from app.models.studentClass import Class
from app.models.subject import Subject
from app.models.user import User
from app.afirme_ler.ddl import get_afirme_ler_written_test_tables_ddl
from app.afirme_ler.models.reading_written_test import (
    ReadingWrittenTest,
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
CITY_ID = "city-1"

ADMIN = {"id": "u-admin", "role": "admin", "city_id": None, "tenant_id": None}
TECADM = {"id": "u-tec", "role": "tecadm", "city_id": CITY_ID, "tenant_id": CITY_ID}
PROFESSOR = {"id": "u-prof", "role": "professor", "city_id": CITY_ID, "tenant_id": CITY_ID}
OTHER_PROFESSOR = {"id": "u-prof2", "role": "professor", "city_id": CITY_ID, "tenant_id": CITY_ID}
APLICADOR = {"id": "u-apl", "role": "aplicador", "city_id": CITY_ID, "tenant_id": CITY_ID}

MC_IDS = [f"mc-{i:02d}" for i in range(1, 22)]  # 21 múltipla escolha GLOBAL, value 1


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
                EducationStage, Subject, Grade, User, Question, School, Class,
                ReadingWrittenTest, ReadingWrittenTestQuestion,
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
            _question("prod-1", question_type="text_production", alternatives=[],
                      correct_answer=None, value=None),
            _question("play-ligar", origin="afirme_play", question_type="ligar_colunas"),
            _question("private-other", scope_type="PRIVATE", owner_user_id="u-prof2"),
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


def test_set_questions_accepts_at_most_20(flask_app):
    written_test = _create()
    with pytest.raises(ValueError, match="A avaliação aceita no máximo 20 questões."):
        WrittenTestService.set_questions(PROFESSOR, written_test.id, {"questions": _items(MC_IDS)})
    db.session.rollback()
    with pytest.raises(ValueError, match="no máximo 20"):
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

def test_publish_requires_exactly_20(flask_app):
    written_test = _create(questions=_items(MC_IDS[:19]))
    with pytest.raises(
        ValueError, match="precisa ter exatamente 20 questões para ser publicada \\(hoje tem 19\\)"
    ):
        WrittenTestService.publish(PROFESSOR, written_test.id)
    db.session.rollback()

    WrittenTestService.set_questions(PROFESSOR, written_test.id, {
        "questions": _items(MC_IDS[:18] + ["dict-1", "prod-1"]),
    })
    published = WrittenTestService.publish(PROFESSOR, written_test.id)
    assert published.status == "publicada"
    assert published.published_at is not None
    assert svc.to_detail(published)["totalScore"] == 21.0


def test_publish_with_21_is_rejected(flask_app):
    written_test = _create(questions=_items(MC_IDS[:20]))
    with patch("app.afirme_ler.services.written_test_service.REQUIRED_QUESTIONS", 25):
        WrittenTestService.set_questions(PROFESSOR, written_test.id, {"questions": _items(MC_IDS)})
    with pytest.raises(ValueError, match="exatamente 20 questões .*hoje tem 21"):
        WrittenTestService.publish(PROFESSOR, written_test.id)
    db.session.rollback()
    assert WrittenTestService.get(written_test.id).status == "rascunho"


def test_publish_rejects_deleted_question(flask_app):
    written_test = _create(questions=_items(MC_IDS[:20]))
    table = Question.__table__
    db.session.execute(table.delete().where(table.c.id == "mc-20"))
    db.session.commit()
    with pytest.raises(ValueError, match="mc-20 não existe mais"):
        WrittenTestService.publish(PROFESSOR, written_test.id)
    db.session.rollback()


def test_published_test_is_locked(flask_app):
    written_test = _create(questions=_items(MC_IDS[:20]))
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
    assert len(stored.questions) == 20


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
    published = _create(title="Prova Gama", questions=_items(MC_IDS[:20]))
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
        "error": "A avaliação precisa ter exatamente 20 questões para ser publicada (hoje tem 1)."
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
    assert "reading_evaluation " not in ddl


def test_new_city_provisioning_includes_written_test_tables():
    from app.services.city_schema_service import _get_city_tables_ddl

    ddl = _get_city_tables_ddl("city_teste")
    assert 'CREATE TABLE IF NOT EXISTS "city_teste".reading_written_test (' in ddl
    assert 'CREATE TABLE IF NOT EXISTS "city_teste".reading_written_test_question (' in ddl
