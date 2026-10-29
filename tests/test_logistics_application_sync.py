# -*- coding: utf-8 -*-
"""Regras puras da sincronização de logística e o savepoint que protege a aplicação."""
import logging
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import text

from app.logistics.services import (
    ALUNO_APPLICATOR_ERROR,
    LogisticsError,
    applicator_rejection_message,
    mark_auto_item_edited,
    parse_applicator_field,
    user_may_be_applicator,
)
from app.logistics.sync import civil_application_date, schedule_sync_decision, sync_application_safe
from app.models.user import RoleEnum


def test_cronograma_publicado_ou_duplicado_nao_entra_na_sincronizacao():
    assert schedule_sync_decision([]) == "create"
    assert schedule_sync_decision(["rascunho"]) == "update"
    assert schedule_sync_decision(["publicado"]) == "skip"
    assert schedule_sync_decision(["rascunho", "publicado"]) == "skip"
    assert schedule_sync_decision(["rascunho", "rascunho"]) == "skip"


def test_dia_civil_respeita_o_fuso_da_aplicacao():
    assert civil_application_date("2026-03-15T23:30:00-03:00", None) == date(2026, 3, 15)
    assert civil_application_date("2026-03-16T02:30:00+00:00", "America/Sao_Paulo") == date(2026, 3, 15)
    assert civil_application_date("2026-03-16T02:30:00Z", "America/Sao_Paulo") == date(2026, 3, 15)
    assert civil_application_date("2026-03-16", None) == date(2026, 3, 16)
    assert civil_application_date(None, "America/Sao_Paulo") is None


def test_aplicador_ausente_no_payload_nao_zera():
    informed, value = parse_applicator_field({"class_id": "turma"})
    assert informed is False
    assert value is None
    informed, value = parse_applicator_field({"applicator_user_id": None})
    assert informed is True
    assert value is None
    informed, value = parse_applicator_field({"applicator_user_id": "  "})
    assert informed is True
    assert value is None
    informed, value = parse_applicator_field({"applicator_user_id": " user-1 "})
    assert informed is True
    assert value == "user-1"


def _item(**overrides):
    data = dict(
        origem="auto",
        editado_manualmente=False,
        class_id="turma-1",
        scheduled_date=date(2026, 4, 1),
        tablets_qty=10,
        booklets_qty=0,
        notes=None,
        applicator_user_id="user-1",
    )
    data.update(overrides)
    return SimpleNamespace(**data)


def _parsed(**overrides):
    data = dict(
        class_id="turma-1",
        scheduled_date=date(2026, 4, 1),
        tablets_qty=10,
        booklets_qty=0,
        notes=None,
        applicator_set=False,
        applicator_user_id=None,
    )
    data.update(overrides)
    return data


def test_item_automatico_so_fica_editado_quando_o_editor_muda_algum_campo():
    intact = _item()
    mark_auto_item_edited(intact, _parsed())
    assert intact.editado_manualmente is False

    applicator = _item()
    mark_auto_item_edited(applicator, _parsed(applicator_set=True, applicator_user_id="user-2"))
    assert applicator.editado_manualmente is True

    manual = _item(origem="manual")
    mark_auto_item_edited(manual, _parsed(scheduled_date=date(2026, 5, 1)))
    assert manual.editado_manualmente is False

    already = _item(editado_manualmente=True)
    mark_auto_item_edited(already, _parsed())
    assert already.editado_manualmente is True


def test_aplicador_vale_para_qualquer_perfil_do_municipio():
    city = "cidade-1"
    professor = SimpleNamespace(role=RoleEnum.PROFESSOR, city_id=city)
    outro = SimpleNamespace(role=RoleEnum.PROFESSOR, city_id="outra")
    admin = SimpleNamespace(role=RoleEnum.ADMIN, city_id=None)
    aluno = SimpleNamespace(role=RoleEnum.ALUNO, city_id=city)
    assert user_may_be_applicator(professor, city, False) is True
    assert user_may_be_applicator(aluno, city, False) is False
    assert user_may_be_applicator(aluno, city, True) is False
    assert user_may_be_applicator(admin, city, False) is True
    assert user_may_be_applicator(admin, city, True) is True
    assert user_may_be_applicator(outro, city, False) is False
    assert user_may_be_applicator(outro, city, True) is True


def test_aluno_como_aplicador_devolve_erro_400():
    city = "cidade-1"
    aluno = SimpleNamespace(role=RoleEnum.ALUNO, city_id=city)
    professor = SimpleNamespace(role=RoleEnum.PROFESSOR, city_id=city)
    admin = SimpleNamespace(role=RoleEnum.ADMIN, city_id=None)
    assert applicator_rejection_message(aluno, city, False) == ALUNO_APPLICATOR_ERROR
    assert applicator_rejection_message(aluno, city, True) == ALUNO_APPLICATOR_ERROR
    assert applicator_rejection_message(professor, city, False) is None
    assert applicator_rejection_message(admin, city, True) is None
    assert LogisticsError(ALUNO_APPLICATOR_ERROR).status_code == 400


def test_falha_na_sincronizacao_nao_invalida_a_sessao(caplog):
    """Exceção dentro do savepoint não pode impedir o restante da aplicação."""
    from app import create_app, db

    app = create_app()

    def _boom(_test_id, _actor_user_id):
        db.session.execute(text("SELECT 1/0"))

    with app.app_context():
        try:
            with caplog.at_level(logging.ERROR):
                with patch("app.logistics.sync._sync_schedule_from_class_tests", _boom):
                    sync_application_safe("avaliacao-teste", "usuario-teste")
            assert db.session.execute(text("SELECT 1")).scalar() == 1
        finally:
            db.session.rollback()

    assert "falha ao sincronizar" in caplog.text.lower()
