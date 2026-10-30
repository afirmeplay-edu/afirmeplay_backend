# -*- coding: utf-8 -*-
"""
Banco de questões do Afirme Ler (public.question, origin = 'afirme_ler').

Roda em SQLite em memória (schema "public" anexado); não conecta no Postgres.
Execução: python -m pytest tests/test_afirme_ler_question_bank.py -q
"""
import base64
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
from app.models.subject import Subject
from app.models.user import User
from app.afirme_ler.services import question_bank_service as bank
from app.afirme_ler.services.question_bank_service import QuestionBankService

SUBJECT_ID = "subj-portugues"
GRADE_ID = uuid.UUID("5600f4b8-af7e-429d-b03c-f7886c046b39")
STAGE_ID = uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
CITY_ID = "city-1"

ADMIN = {"id": "u-admin", "role": "admin", "city_id": None, "tenant_id": None}
TECADM = {"id": "u-tec", "role": "tecadm", "city_id": CITY_ID, "tenant_id": CITY_ID}
PROFESSOR = {"id": "u-prof", "role": "professor", "city_id": CITY_ID, "tenant_id": CITY_ID}
OTHER_PROFESSOR = {"id": "u-prof2", "role": "professor", "city_id": CITY_ID, "tenant_id": CITY_ID}
APLICADOR = {"id": "u-apl", "role": "aplicador", "city_id": CITY_ID, "tenant_id": CITY_ID}


def _options(correct_index=2, count=4):
    return [
        {"id": chr(65 + i), "text": f"Alternativa {i}", "isCorrect": i == correct_index}
        for i in range(count)
    ]


def _payload(**overrides):
    data = {
        "text": "Qual palavra começa com a mesma letra de BOLA?",
        "formattedText": "<p>Qual palavra começa com a mesma letra de BOLA?</p>",
        "type": "multipleChoice",
        "subjectId": SUBJECT_ID,
        "grade": str(GRADE_ID),
        "difficulty": "Básico",
        "options": _options(),
    }
    data.update(overrides)
    return data


@pytest.fixture()
def flask_app():
    application = Flask("afirme_ler_question_bank_tests")
    application.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
    application.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "poolclass": StaticPool,
        "connect_args": {"check_same_thread": False},
    }
    db.init_app(application)
    with application.app_context():
        engine = db.engine

        @event.listens_for(engine, "connect")
        def _attach_public(dbapi_conn, _record):
            dbapi_conn.execute("ATTACH DATABASE ':memory:' AS public")

        engine.dispose()
        tables = [m.__table__ for m in (EducationStage, Subject, Grade, User, Question)]
        db.metadata.create_all(engine, tables=tables)

        db.session.add_all([
            EducationStage(id=STAGE_ID, name="Anos Iniciais"),
            Subject(id=SUBJECT_ID, name="Língua Portuguesa"),
            Grade(id=GRADE_ID, name="1º ano", education_stage_id=STAGE_ID),
            Question(
                id="play-1", text="Questão do Play", question_type="multipleChoice",
                alternatives=_options(1), correct_answer="B", scope_type="GLOBAL",
                origin="afirme_play", subject_id=SUBJECT_ID, grade_level=GRADE_ID, version=1,
            ),
            Question(
                id="ler-1", text="Questão do Ler", question_type="multipleChoice",
                alternatives=_options(0), correct_answer="A", scope_type="GLOBAL",
                origin="afirme_ler", subject_id=SUBJECT_ID, grade_level=GRADE_ID, version=1,
            ),
        ])
        db.session.commit()

        with patch(
            "app.afirme_ler.services.scope_service.get_current_tenant_context",
            return_value=None,
        ):
            yield application

        db.session.remove()
        db.metadata.drop_all(engine, tables=tables)


# ---------------------------------------------------------------------------
# Questão do Ler não aparece no Play
# ---------------------------------------------------------------------------

def _call_play_view(module, view, user, *args, path="/", method="GET", json=None):
    """Chama a view do Play sem os decorators de JWT/role, com o usuário informado."""
    from flask import current_app

    raw = inspect.unwrap(getattr(module, view))
    with current_app.test_request_context(path, method=method, json=json):
        with patch.object(module, "get_current_user_from_token", return_value=user):
            if hasattr(module, "get_current_tenant_context"):
                with patch.object(module, "get_current_tenant_context", return_value=None):
                    return raw(*args)
            return raw(*args)


def test_play_list_questions_hides_afirme_ler(flask_app):
    from app.routes import question_routes

    response, status = _call_play_view(question_routes, "list_questions", ADMIN, path="/questions/")
    assert status == 200
    assert [q["id"] for q in response.get_json()] == ["play-1"]


def test_play_batch_and_detail_hide_afirme_ler(flask_app):
    from app.routes import question_routes

    response, status = _call_play_view(
        question_routes, "get_questions_batch", ADMIN, path="/questions/batch?ids=play-1,ler-1"
    )
    assert status == 200
    assert [q["id"] for q in response.get_json()] == ["play-1"]

    _, status = _call_play_view(question_routes, "get_question", ADMIN, "ler-1", path="/questions/ler-1")
    assert status == 404


def test_play_update_question_ignores_afirme_ler(flask_app):
    from app.routes import question_routes

    _, status = _call_play_view(
        question_routes, "update_question", ADMIN, "ler-1",
        path="/questions/ler-1", method="PUT", json={"text": "alterado pelo Play"},
    )
    assert status == 404
    assert db.session.get(Question, "ler-1").text == "Questão do Ler"


def test_play_create_test_rejects_afirme_ler_question(flask_app):
    from app.routes import test_routes

    payload = {
        "title": "Prova", "type": "AVALIACAO", "model": "SAEB", "course": "x",
        "created_by": "u-admin", "subject": SUBJECT_ID,
        "questions": [{"id": "play-1"}, {"id": "ler-1"}],
    }
    response, status = _call_play_view(
        test_routes, "criar_avaliacao", ADMIN, path="/test", method="POST", json=payload,
    )
    assert status == 400
    body = response.get_json()
    assert body["error"] == "Questões do Afirme Ler não podem ser usadas no Afirme Play."
    assert body["question_ids"] == ["ler-1"]


def test_competition_selection_hides_afirme_ler(flask_app):
    from app.competitions.services.question_selection_service import QuestionSelectionService

    ids = [q.id for q in QuestionSelectionService.build_query(SUBJECT_ID, None, {}).all()]
    assert ids == ["play-1"]


# ---------------------------------------------------------------------------
# Afirme Ler: listagem, criação e gabarito em letra
# ---------------------------------------------------------------------------

def test_ler_list_sees_play_and_ler_with_origin_filter(flask_app):
    result = QuestionBankService.list_questions(ADMIN, {})
    assert sorted(q["id"] for q in result["data"]) == ["ler-1", "play-1"]
    assert result["pagination"]["total"] == 2
    assert result["pagination"]["per_page"] == 10

    only_ler = QuestionBankService.list_questions(ADMIN, {"origin": "afirme_ler"})
    assert [q["id"] for q in only_ler["data"]] == ["ler-1"]
    assert only_ler["data"][0]["origin"] == "afirme_ler"
    assert only_ler["data"][0]["scopeType"] == "GLOBAL"


def test_ler_list_per_page_is_capped(flask_app):
    result = QuestionBankService.list_questions(ADMIN, {"per_page": "500"})
    assert result["pagination"]["per_page"] == 100


def test_ler_create_stores_correct_answer_as_letter(flask_app):
    question = QuestionBankService.create(PROFESSOR, _payload(options=_options(correct_index=2)))

    stored = db.session.get(Question, question.id)
    assert stored.correct_answer == "C"
    assert stored.origin == "afirme_ler"
    assert stored.question_type == "multipleChoice"
    assert stored.value == 1.0
    assert stored.scope_type == "PRIVATE"
    assert stored.owner_user_id == "u-prof"
    assert stored.created_by == "u-prof"


def test_ler_create_scope_by_role(flask_app):
    admin_q = QuestionBankService.create(ADMIN, _payload())
    tecadm_q = QuestionBankService.create(TECADM, _payload())
    assert (admin_q.scope_type, admin_q.owner_city_id) == ("GLOBAL", None)
    assert (tecadm_q.scope_type, tecadm_q.owner_city_id) == ("CITY", CITY_ID)


def test_ler_update_recalculates_letter_and_version(flask_app):
    question = QuestionBankService.create(PROFESSOR, _payload(options=_options(correct_index=0)))
    updated = QuestionBankService.update(
        PROFESSOR, question.id, {"options": _options(correct_index=3), "value": 2}
    )
    assert updated.correct_answer == "D"
    assert updated.version == 2
    assert updated.value == 2.0


@pytest.mark.parametrize(
    "options, message",
    [
        (_options(correct_index=99), "exatamente uma alternativa correta"),
        ([{"text": "A", "isCorrect": True}, {"text": "B", "isCorrect": True}],
         "exatamente uma alternativa correta"),
        ([{"text": "A", "isCorrect": True}], "pelo menos 2"),
        ([{"text": "A", "isCorrect": True}, {"text": " ", "isCorrect": False}],
         "precisa de texto ou imagem"),
    ],
)
def test_ler_rejects_invalid_gabarito(options, message):
    with pytest.raises(ValueError, match=message):
        bank.parse_create_payload(_payload(options=options))


@pytest.mark.parametrize("question_type", ["essay", "ligar_colunas", "trueFalse"])
def test_ler_rejects_other_types(question_type):
    with pytest.raises(
        ValueError,
        match="Tipos permitidos: multipleChoice .*, dictation .* e text_production",
    ):
        bank.parse_create_payload(_payload(type=question_type))


def test_ler_multiple_choice_ignores_dictated_word():
    fields = bank.parse_create_payload(_payload(dictatedWord="casa"))
    assert fields["question_type"] == "multipleChoice"
    assert fields["correct_answer"] == "C"
    assert len(fields["alternatives"]) == 4


# ---------------------------------------------------------------------------
# Ditado (dictation) e produção escrita (text_production)
# ---------------------------------------------------------------------------

def _dictation_payload(**overrides):
    data = {
        "text": "Escreva a palavra que o aplicador vai ditar.",
        "type": "dictation",
        "subjectId": SUBJECT_ID,
        "grade": str(GRADE_ID),
        "dictatedWord": "  borboleta  ",
    }
    data.update(overrides)
    return data


def _text_production_payload(**overrides):
    data = {
        "text": "Escreva um bilhete para a sua professora convidando-a para a festa da turma.",
        "type": "text_production",
        "subjectId": SUBJECT_ID,
        "grade": str(GRADE_ID),
        "formattedSolution": "<p>Tem destinatário, mensagem, despedida e assinatura.</p>",
    }
    data.update(overrides)
    return data


@pytest.mark.parametrize(
    "raw, canonical",
    [
        ("dictation", "dictation"),
        ("ditado", "dictation"),
        ("Ditado", "dictation"),
        ("text_production", "text_production"),
        ("producao_textual", "text_production"),
        ("Produção textual", "text_production"),
        ("bilhete", "text_production"),
        ("multiple_choice", "multipleChoice"),
    ],
)
def test_ler_type_aliases_store_canonical_name(raw, canonical):
    assert bank.normalize_ler_question_type(raw) == canonical


def test_ler_create_dictation_stores_word_as_answer(flask_app):
    question = QuestionBankService.create(PROFESSOR, _dictation_payload(type="ditado", value=2))

    stored = db.session.get(Question, question.id)
    assert stored.question_type == "dictation"
    assert stored.correct_answer == "borboleta"
    assert stored.alternatives == []
    assert stored.value == 2.0
    assert stored.origin == "afirme_ler"

    body = bank.to_response(question)
    assert body["type"] == "dictation"
    assert body["dictatedWord"] == "borboleta"
    assert body["correct_answer"] == "borboleta"
    assert body["options"] == []


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"dictatedWord": None}, "dictatedWord é obrigatório"),
        ({"dictatedWord": "   "}, "dictatedWord é obrigatório"),
        ({"dictatedWord": 123}, "dictatedWord deve ser um texto"),
        ({"dictatedWord": "bola azul"}, "uma única palavra"),
        ({"dictatedWord": "a" * 41}, "no máximo 40 caracteres"),
        ({"options": _options()}, "ditado \\(dictation\\) não tem alternativas"),
    ],
)
def test_ler_rejects_invalid_dictation(overrides, message):
    with pytest.raises(ValueError, match=message):
        bank.parse_create_payload(_dictation_payload(**overrides))


def test_ler_image_dictation_waits_for_the_description(flask_app):
    payload = _dictation_payload(stimulus="imagem", text="Escreva o nome do objeto.")
    del payload["dictatedWord"]
    question = QuestionBankService.create(PROFESSOR, payload)

    stored = db.session.get(Question, question.id)
    assert stored.writing_stimulus == "image"
    assert stored.correct_answer is None
    assert stored.writing_reference is None
    body = bank.to_response(question)
    assert body["stimulus"] == "image"
    assert body["dictatedWord"] is None
    assert body["imageDescription"] is None
    assert body["correct_answer"] == ""

    with pytest.raises(ValueError, match="não recebe dictatedWord"):
        bank.parse_create_payload(_dictation_payload(stimulus="image", dictatedWord="cinto"))


def test_ler_describe_image_saves_the_reference(flask_app, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o")
    payload = _dictation_payload(stimulus="image")
    del payload["dictatedWord"]
    question = QuestionBankService.create(PROFESSOR, payload)
    question.images = [{
        "id": "img-cinto",
        "type": "image/png",
        "minio_bucket": "question-images",
        "minio_object_name": "q/cinto.png",
    }]
    db.session.commit()

    class _Choice:
        def __init__(self):
            self.message = type("Message", (), {"content": '{"descricao": "cinto de roupa"}'})()

    class _Client:
        def __init__(self, api_key=None, timeout=None):
            pass

        class chat:
            class completions:
                @staticmethod
                def create(**kwargs):
                    _Client.calls.append(kwargs)
                    return type("Response", (), {"choices": [_Choice()]})()

    _Client.calls = []
    with patch("app.services.storage.minio_service.MinIOService") as minio, patch("openai.OpenAI", _Client):
        minio.return_value.download_file.return_value = b"\x89PNG"
        described = QuestionBankService.describe_image(PROFESSOR, question.id)

    assert described.writing_reference == "cinto de roupa"
    body = bank.to_response(described)
    assert body["imageDescription"] == "cinto de roupa"
    assert body["dictatedWord"] is None
    sent = _Client.calls[0]
    assert "DESCRICAO_IMAGEM" in sent["messages"][0]["content"]
    user_text = sent["messages"][1]["content"][0]["text"]
    assert "cinto" not in user_text
    assert sent["messages"][1]["content"][1]["type"] == "image_url"

    updated = QuestionBankService.update(PROFESSOR, question.id, {"formattedText": "<p>Olhe de novo.</p>"})
    assert updated.writing_reference is None


def _png_html():
    encoded = base64.b64encode(b"\x89PNG").decode("ascii")
    return f'<p>Escreva o nome.</p><img src="data:image/png;base64,{encoded}" />'


class _DescriptionClient:
    calls = []

    def __init__(self, api_key=None, timeout=None):
        pass

    class chat:
        class completions:
            @staticmethod
            def create(**kwargs):
                _DescriptionClient.calls.append(kwargs)
                message = type("Message", (), {"content": '{"descricao": "cinto de roupa"}'})()
                choice = type("Choice", (), {"message": message})()
                return type("Response", (), {"choices": [choice]})()


def test_ler_preview_describes_without_creating_a_question(flask_app, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    before = Question.query.count()
    _DescriptionClient.calls = []
    with patch("openai.OpenAI", _DescriptionClient):
        description = QuestionBankService.preview_image_description(
            PROFESSOR, {"formattedText": _png_html()},
        )
    assert description == "cinto de roupa"
    assert Question.query.count() == before
    sent = _DescriptionClient.calls[0]["messages"][1]["content"]
    assert sent[1]["image_url"]["url"].startswith("data:image/png;base64,")

    with pytest.raises(ValueError, match="Anexe a imagem"):
        QuestionBankService.preview_image_description(PROFESSOR, {"formattedText": "<p>Sem foto.</p>"})


def test_ler_create_saves_the_accepted_image_description(flask_app):
    payload = _dictation_payload(
        stimulus="image",
        text="Escreva o nome do objeto.",
        formattedText=_png_html(),
        imageDescription="  cinto de roupa  ",
    )
    del payload["dictatedWord"]
    question = QuestionBankService.create(PROFESSOR, payload)
    assert question.writing_reference == "cinto de roupa"
    assert bank.to_response(question)["imageDescription"] == "cinto de roupa"

    with pytest.raises(ValueError, match="só vale para ditado com stimulus image"):
        bank.parse_create_payload(_dictation_payload(imageDescription="cinto de roupa"))


def test_ler_update_keeps_a_new_description_sent_with_the_photo(flask_app):
    payload = _dictation_payload(stimulus="image", imageDescription="cinto de roupa")
    del payload["dictatedWord"]
    question = QuestionBankService.create(PROFESSOR, payload)

    replaced = QuestionBankService.update(PROFESSOR, question.id, {
        "formattedText": _png_html(),
        "imageDescription": "cinto marrom",
    })
    assert replaced.writing_reference == "cinto marrom"

    cleared = QuestionBankService.update(PROFESSOR, question.id, {
        "formattedText": "<p><img src=\"/questions/x/images/1\" /></p>",
    })
    assert cleared.writing_reference is None


def test_ler_preview_route_returns_only_the_text(flask_app, monkeypatch):
    from app.afirme_ler.routes import questions_routes

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    before = Question.query.count()
    _DescriptionClient.calls = []
    with patch("openai.OpenAI", _DescriptionClient):
        response, status = _call_play_view(
            questions_routes, "preview_bank_question_image", PROFESSOR,
            path="/afirme-reading/questions/image-description", method="POST",
            json={"formattedText": _png_html()},
        )
    assert status == 200
    assert response.get_json() == {"imageDescription": "cinto de roupa"}
    assert Question.query.count() == before

    response, status = _call_play_view(
        questions_routes, "preview_bank_question_image", PROFESSOR,
        path="/afirme-reading/questions/image-description", method="POST",
        json={"formattedText": "<p>Sem foto.</p>"},
    )
    assert status == 400
    assert response.get_json()["error"] == "Anexe a imagem do objeto antes de gerar a descrição."


def test_ler_dictation_without_word_key_is_rejected():
    data = _dictation_payload()
    del data["dictatedWord"]
    with pytest.raises(ValueError, match="dictatedWord é obrigatório"):
        bank.parse_create_payload(data)


def test_ler_dictation_accepts_word_with_40_chars_and_empty_options():
    fields = bank.parse_create_payload(_dictation_payload(dictatedWord="b" * 40, options=[]))
    assert fields["correct_answer"] == "b" * 40
    assert fields["alternatives"] == []


def test_ler_create_text_production_without_answer(flask_app):
    question = QuestionBankService.create(PROFESSOR, _text_production_payload(type="bilhete"))

    stored = db.session.get(Question, question.id)
    assert stored.question_type == "text_production"
    assert stored.correct_answer is None
    assert stored.alternatives == []
    assert stored.value == 1.0
    assert stored.formatted_solution.startswith("<p>Tem destinatário")

    body = bank.to_response(question)
    assert body["type"] == "text_production"
    assert body["dictatedWord"] is None


def test_ler_rejects_text_production_with_options():
    with pytest.raises(ValueError, match="produção escrita \\(text_production\\) não tem alternativas"):
        bank.parse_create_payload(_text_production_payload(options=_options()))


def test_ler_create_route_returns_400_for_invalid_dictation(flask_app):
    from app.afirme_ler.routes import questions_routes

    response, status = _call_play_view(
        questions_routes, "create_bank_question", PROFESSOR,
        path="/afirme-reading/questions", method="POST",
        json=_dictation_payload(dictatedWord="bola azul"),
    )
    assert status == 400
    assert response.get_json() == {
        "error": "dictatedWord deve ser uma única palavra, sem espaços."
    }


def test_ler_update_multiple_choice_to_dictation(flask_app):
    question = QuestionBankService.create(PROFESSOR, _payload())

    with pytest.raises(ValueError, match="dictatedWord é obrigatório"):
        QuestionBankService.update(PROFESSOR, question.id, {"type": "dictation"})
    db.session.rollback()

    updated = QuestionBankService.update(
        PROFESSOR, question.id, {"type": "ditado", "dictatedWord": "sapato"}
    )
    assert updated.question_type == "dictation"
    assert updated.correct_answer == "sapato"
    assert updated.alternatives == []
    assert updated.version == 2


def test_ler_update_dictation_keeps_word_and_rejects_options(flask_app):
    question = QuestionBankService.create(PROFESSOR, _dictation_payload())

    updated = QuestionBankService.update(PROFESSOR, question.id, {"text": "Escreva a palavra ditada."})
    assert updated.correct_answer == "borboleta"

    updated = QuestionBankService.update(PROFESSOR, question.id, {"dictatedWord": "janela"})
    assert updated.correct_answer == "janela"

    with pytest.raises(ValueError, match="não tem alternativas"):
        QuestionBankService.update(PROFESSOR, question.id, {"options": _options()})
    db.session.rollback()


def test_ler_update_dictation_to_multiple_choice_requires_options(flask_app):
    question = QuestionBankService.create(PROFESSOR, _dictation_payload())

    with pytest.raises(ValueError, match="options é obrigatório"):
        QuestionBankService.update(PROFESSOR, question.id, {"type": "multipleChoice"})
    db.session.rollback()

    updated = QuestionBankService.update(
        PROFESSOR, question.id,
        {"type": "multipleChoice", "options": _options(correct_index=1)},
    )
    assert updated.question_type == "multipleChoice"
    assert updated.correct_answer == "B"
    assert len(updated.alternatives) == 4


def test_ler_update_dictation_to_text_production_clears_answer(flask_app):
    question = QuestionBankService.create(PROFESSOR, _dictation_payload())

    updated = QuestionBankService.update(PROFESSOR, question.id, {"type": "producao_textual"})
    assert updated.question_type == "text_production"
    assert updated.correct_answer is None
    assert updated.alternatives == []


def test_ler_list_filters_by_new_types(flask_app):
    dictation = QuestionBankService.create(ADMIN, _dictation_payload())
    production = QuestionBankService.create(ADMIN, _text_production_payload())

    def ids(type_filter):
        result = QuestionBankService.list_questions(ADMIN, {"type": type_filter})
        return sorted(q["id"] for q in result["data"])

    assert ids("dictation") == [dictation.id]
    assert ids("ditado") == [dictation.id]
    assert ids("text_production") == [production.id]
    assert ids("bilhete") == [production.id]
    assert ids("Produção textual") == [production.id]
    assert ids("multipleChoice") == ["ler-1", "play-1"]


def test_ler_rejects_aplicador_on_write():
    with pytest.raises(PermissionError):
        bank.assert_can_write(APLICADOR)


# ---------------------------------------------------------------------------
# Questão do Play não pode ser editada pelo Ler
# ---------------------------------------------------------------------------

def test_ler_cannot_edit_play_question(flask_app):
    with pytest.raises(PermissionError, match="somente leitura"):
        QuestionBankService.update(ADMIN, "play-1", {"text": "alterado pelo Ler"})
    db.session.rollback()
    assert db.session.get(Question, "play-1").text == "Questão do Play"


def test_ler_edit_respects_scope(flask_app):
    private_q = QuestionBankService.create(PROFESSOR, _payload())
    with pytest.raises(LookupError):
        QuestionBankService.update(OTHER_PROFESSOR, private_q.id, {"text": "x"})
    db.session.rollback()

    with pytest.raises(PermissionError, match="permissão"):
        QuestionBankService.update(TECADM, "ler-1", {"text": "x"})
    db.session.rollback()


def test_ler_detail_applies_scope(flask_app):
    private_q = QuestionBankService.create(PROFESSOR, _payload())
    assert QuestionBankService.get_question(PROFESSOR, private_q.id).id == private_q.id
    with pytest.raises(LookupError):
        QuestionBankService.get_question(OTHER_PROFESSOR, private_q.id)
