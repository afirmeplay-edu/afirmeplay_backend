"""Testes puros do boletim do aluno."""

from app.boletim_aluno.helpers import (
    attach_disciplina_cards,
    build_cards,
    build_disciplina_cards_parcial,
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


def test_disciplina_cards_from_subject_data_and_parcial():
    parcial = build_disciplina_cards_parcial(8, 10)
    assert parcial["acertos_totais"] == {"acertou": 8, "total": 10, "percentual": 80.0}
    assert parcial["nota"] is None
    assert parcial["proficiencia"] is None
    assert parcial["nivel"] is None

    bloco = {
        "questoes": [
            {"acertou": True},
            {"acertou": False},
        ]
    }
    attach_disciplina_cards(
        bloco,
        {
            "correct_answers": 8,
            "total_questions": 10,
            "grade": 7.5,
            "proficiency": 320.0,
            "classification": "Adequado",
        },
    )
    assert bloco["cards"]["acertos_totais"]["acertou"] == 8
    assert bloco["cards"]["nota"] == 7.5
    assert bloco["cards"]["proficiencia"] == 320.0
    assert bloco["cards"]["nivel"] == "Adequado"

    bloco_fallback = {"questoes": [{"acertou": True}, {"acertou": True}, {"acertou": False}]}
    attach_disciplina_cards(bloco_fallback, None)
    assert "cards" in bloco_fallback
    assert bloco_fallback["cards"]["acertos_totais"]["acertou"] == 2
    assert bloco_fallback["cards"]["acertos_totais"]["total"] == 3
    assert bloco_fallback["cards"]["nota"] is None
    assert bloco_fallback["cards"]["nivel"] is None
