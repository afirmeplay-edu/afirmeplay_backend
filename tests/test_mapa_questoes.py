"""Testes puros do mapa de questões (sem banco)."""

from app.mapa_questoes.helpers import (
    answer_to_letter,
    build_marcacoes,
    build_question_row,
    gabarito_letter,
    is_discursive_question,
    is_objective_question,
    join_habilidade_campos,
    letters_for_alternatives,
    letters_for_answer_sheet,
    media_acertos_percentual,
    percentual,
)


def test_discursive_excluded():
    assert is_discursive_question("essay") is True
    assert is_discursive_question("discursive") is True
    assert is_objective_question("essay", [{"id": "a"}]) is False
    assert is_objective_question("multiple_choice") is True
    assert is_objective_question(None, [{"id": "option-0", "text": "X"}]) is True
    assert is_objective_question(None, None) is False


def test_answer_to_letter_from_letter_id_and_option():
    alts = [
        {"id": "opt-a", "text": "Casa"},
        {"id": "opt-b", "text": "Bola", "isCorrect": True},
        {"id": "opt-c", "text": "Pato"},
        {"id": "opt-d", "text": "Mesa"},
    ]
    assert answer_to_letter("B", alts) == "B"
    assert answer_to_letter("b", alts) == "B"
    assert answer_to_letter("opt-c", alts) == "C"
    assert answer_to_letter("bola", alts) == "B"
    assert answer_to_letter("option-0", alts) == "A"
    assert answer_to_letter("option-1", alts) == "B"
    assert answer_to_letter("", alts) is None
    assert answer_to_letter(None, alts) is None


def test_gabarito_letter_from_is_correct_flag():
    alts = [
        {"id": "a", "text": "A1"},
        {"id": "b", "text": "B1", "isCorrect": True},
    ]
    assert gabarito_letter(None, alts) == "B"
    assert gabarito_letter("A", alts) == "A"


def test_letters_for_alternatives_and_answer_sheet():
    assert letters_for_alternatives([{}, {}, {}, {}]) == ["A", "B", "C", "D"]
    assert letters_for_alternatives([{}, {}, {}, {}, {}]) == ["A", "B", "C", "D", "E"]
    assert letters_for_answer_sheet(["A", "C"], ["B"]) == ["A", "B", "C"]
    assert letters_for_answer_sheet([], []) == ["A", "B", "C", "D"]


def test_media_acertos_nao_ponderada():
    # 10 alunos, 4 questões, 24 acertos no total → 60%
    assert media_acertos_percentual(24, 10, 4) == 60.0
    # Escola grande não pesa mais: é só acertos / (alunos × questões)
    assert media_acertos_percentual(3, 2, 2) == 75.0
    assert media_acertos_percentual(0, 0, 10) == 0.0
    assert media_acertos_percentual(5, 10, 0) == 0.0


def test_marcacoes_incluem_sem_resposta_e_somam_cem():
    n = 20
    counts = {"A": 4, "B": 10, "C": 3, "D": 0, "sem_resposta": 3}
    rows = build_marcacoes(counts, ["A", "B", "C", "D"], n)
    by_alt = {r["alternativa"]: r for r in rows}
    assert by_alt["A"]["percentual"] == 20.0
    assert by_alt["B"]["alunos"] == 10
    assert by_alt["B"]["percentual"] == 50.0
    assert by_alt["sem_resposta"]["alunos"] == 3
    assert by_alt["sem_resposta"]["percentual"] == 15.0
    total = sum(r["percentual"] for r in rows)
    assert abs(total - 100.0) < 0.01


def test_percentual_zero_quando_sem_alunos():
    assert percentual(5, 0) == 0.0
    assert percentual(10, 20) == 50.0


def test_build_question_row_inclui_question_id_so_quando_informado():
    row = build_question_row(
        numero=1,
        disciplina="Matemática",
        disciplina_id="mat",
        habilidade="EF05MA01",
        gabarito="A",
        letters=["A", "B", "C", "D"],
        mark_counts={"A": 2, "B": 1, "C": 0, "D": 0, "sem_resposta": 0},
        acertaram=2,
        n_alunos=3,
        question_id="q-uuid-1",
    )
    assert row["question_id"] == "q-uuid-1"

    cartao = build_question_row(
        numero=1,
        disciplina="Matemática",
        disciplina_id="mat",
        habilidade="EF05MA01",
        gabarito="A",
        letters=["A", "B", "C", "D"],
        mark_counts={"A": 2, "B": 1, "C": 0, "D": 0, "sem_resposta": 0},
        acertaram=2,
        n_alunos=3,
    )
    assert "question_id" not in cartao


def test_join_habilidade_campos_uma_e_varias():
    assert join_habilidade_campos([]) == ("N/A", "")
    assert join_habilidade_campos([("EF15_D2", "Ler e interpretar textos.")]) == (
        "EF15_D2",
        "Ler e interpretar textos.",
    )
    codigo, desc = join_habilidade_campos(
        [("EF15_D2", "Ler."), ("EF15_D3", "Escrever.")]
    )
    assert codigo == "EF15_D2, EF15_D3"
    assert "EF15_D2 — Ler." in desc
    assert "EF15_D3 — Escrever." in desc


def test_build_question_row_inclui_habilidade_descricao():
    row = build_question_row(
        numero=1,
        disciplina="LP",
        disciplina_id="lp",
        habilidade="EF15_D2",
        habilidade_descricao="Ler e interpretar textos.",
        gabarito="A",
        letters=["A", "B", "C", "D"],
        mark_counts={"A": 1, "B": 0, "C": 0, "D": 0, "sem_resposta": 0},
        acertaram=1,
        n_alunos=1,
    )
    assert row["habilidade"] == "EF15_D2"
    assert row["habilidade_descricao"] == "Ler e interpretar textos."
