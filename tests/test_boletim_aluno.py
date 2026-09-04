"""Testes puros do boletim do aluno."""

from app.boletim_aluno.services.helpers import (
    build_cards,
    build_questao_boletim,
    parse_aluno_param,
    parse_pagination,
    pagination_meta,
)


def test_parse_pagination_defaults_and_caps():
    assert parse_pagination(None, None) == (1, 20)
    assert parse_pagination("2", "50") == (2, 50)
    assert parse_pagination("0", "999") == (1, 100)
    assert parse_pagination("abc", "x") == (1, 20)


def test_pagination_meta():
    assert pagination_meta(0, 1, 20)["total_pages"] == 0
    assert pagination_meta(20, 1, 20)["total_pages"] == 1
    assert pagination_meta(21, 1, 20)["total_pages"] == 2
    assert pagination_meta(150, 3, 20) == {
        "page": 3,
        "per_page": 20,
        "total": 150,
        "total_pages": 8,
    }


def test_parse_aluno_param():
    assert parse_aluno_param([]) is None
    assert parse_aluno_param(["all"]) is None
    assert parse_aluno_param(["todos"]) is None
    assert parse_aluno_param(["uuid-1"]) == "uuid-1"
    try:
        parse_aluno_param(["a", "b"])
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_questao_e_cards():
    q = build_questao_boletim(
        numero=1,
        habilidade="EF05LP03",
        resposta="A",
        gabarito="B",
        acertou=False,
        respondeu=True,
    )
    assert q["acertou"] is False
    assert q["gabarito"] == "B"
    blank = build_questao_boletim(
        numero=2,
        habilidade="N/A",
        resposta=None,
        gabarito="C",
        acertou=False,
        respondeu=False,
    )
    assert blank["respondeu"] is False
    cards = build_cards(12, 22, 6.4, 198.5, "Básico")
    assert cards["acertos_totais"]["percentual"] == 54.55
    assert cards["nota"] == 6.4
    assert cards["nivel"] == "Básico"
