"""A solução do DOCX só passa se for a letra da alternativa correta."""

from app.question_import.importer import solution_refusal_reason

OPTIONS = [
    {"id": "A", "text": "2/4", "isCorrect": True},
    {"id": "B", "text": "1/3", "isCorrect": False},
]


def test_aceita_somente_a_letra_correta():
    assert solution_refusal_reason("A", "<p>A</p>", OPTIONS) is None
    assert solution_refusal_reason("A", None, OPTIONS) is None


def test_recusa_qualquer_coisa_alem_da_letra():
    assert solution_refusal_reason("Gabarito: C.", None, OPTIONS)
    assert solution_refusal_reason("C.", None, OPTIONS)
    assert solution_refusal_reason("a", None, OPTIONS)
    assert solution_refusal_reason("A justificativa", None, OPTIONS)
    assert solution_refusal_reason("", None, OPTIONS)
    assert solution_refusal_reason(
        "A",
        "<p>A</p><p>porque 2/4 equivale a 1/2</p>",
        OPTIONS,
    )
    assert solution_refusal_reason("A", '<p>A</p><img src="x"/>', OPTIONS)


def test_recusa_letra_de_outra_alternativa():
    reason = solution_refusal_reason("B", None, OPTIONS)
    assert reason
    assert "B" in reason
