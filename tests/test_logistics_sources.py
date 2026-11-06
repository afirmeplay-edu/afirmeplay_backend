# -*- coding: utf-8 -*-
"""Origens do cronograma: chave composta, rótulo, formato e sync só para avaliação."""
from types import SimpleNamespace

from app.logistics.sources import (
    instrument_key,
    parse_instrument_key,
    schedule_display_label,
    schedule_evaluation_mode,
    schedule_source,
    source_badge,
)
from app.logistics.sync import schedule_sync_decision
from app.models.logisticsSchedule import (
    LOGISTICS_SOURCE_AVALIACAO,
    LOGISTICS_SOURCE_CARTAO,
    LOGISTICS_SOURCE_PERSONALIZADA,
)


def _schedule(**overrides):
    data = dict(
        id="sch-1",
        source=LOGISTICS_SOURCE_AVALIACAO,
        test_id="test-1",
        gabarito_id=None,
        evaluation_mode=None,
        title="Cronograma",
    )
    data.update(overrides)
    return SimpleNamespace(**data)


def test_instrument_key_tres_origens():
    assert instrument_key(_schedule()) == "avaliacao:test-1"
    assert (
        instrument_key(
            _schedule(source=LOGISTICS_SOURCE_CARTAO, test_id=None, gabarito_id="gab-9")
        )
        == "cartao:gab-9"
    )
    assert (
        instrument_key(
            _schedule(source=LOGISTICS_SOURCE_CARTAO, test_id=None, gabarito_id=None, id="sch-x")
        )
        == "cartao-schedule:sch-x"
    )
    assert (
        instrument_key(
            _schedule(source=LOGISTICS_SOURCE_PERSONALIZADA, test_id=None, title="Extra")
        )
        == "personalizada:sch-1"
    )


def test_parse_instrument_key():
    assert parse_instrument_key("avaliacao:abc") == ("avaliacao", "abc")
    assert parse_instrument_key("cartao:gab") == ("cartao", "gab")
    assert parse_instrument_key("personalizada:uuid") == ("personalizada", "uuid")
    assert parse_instrument_key("uuid-puro") is None
    assert parse_instrument_key("") is None


def test_rotulo_e_formato_por_origem():
    test = SimpleNamespace(title="Prova SAEB", evaluation_mode="virtual")
    gab = SimpleNamespace(title="Cartão 5º")
    av = _schedule(title="Logística SAEB")
    assert schedule_display_label(av, test=test) == "Prova SAEB"
    assert schedule_evaluation_mode(av, test=test) == "virtual"
    assert source_badge(av) is None

    cartao = _schedule(
        source=LOGISTICS_SOURCE_CARTAO,
        test_id=None,
        gabarito_id="g1",
        title="Cartão 5º",
    )
    assert schedule_display_label(cartao, gabarito=gab) == "Cartão 5º"
    assert schedule_evaluation_mode(cartao) == "physical"
    assert source_badge(cartao) == "Cartão-resposta"

    # Gabarito excluído: mantém título gravado
    orphan = _schedule(
        source=LOGISTICS_SOURCE_CARTAO,
        test_id=None,
        gabarito_id=None,
        title="Cartão antigo",
    )
    assert schedule_display_label(orphan) == "Cartão antigo"

    pers = _schedule(
        source=LOGISTICS_SOURCE_PERSONALIZADA,
        test_id=None,
        title="Simulado interno",
        evaluation_mode="virtual",
    )
    assert schedule_display_label(pers) == "Simulado interno"
    assert schedule_evaluation_mode(pers) == "virtual"
    assert source_badge(pers) == "Personalizada"


def test_source_default_avaliacao_quando_ausente():
    legacy = SimpleNamespace(source=None, test_id="t1", title="X")
    assert schedule_source(legacy) == LOGISTICS_SOURCE_AVALIACAO


def test_sync_decision_inalterada():
    assert schedule_sync_decision([]) == "create"
    assert schedule_sync_decision(["rascunho"]) == "update"
    assert schedule_sync_decision(["publicado"]) == "skip"


def test_sync_codigo_exige_origem_avaliacao():
    """Cartão e personalizada não entram na sincronização automática."""
    import inspect

    from app.logistics import sync as sync_mod

    source = inspect.getsource(sync_mod._sync_schedule_from_class_tests)
    assert "LOGISTICS_SOURCE_AVALIACAO" in source
    assert "source=" in source or "LogisticsSchedule.source" in source
