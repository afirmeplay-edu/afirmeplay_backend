# -*- coding: utf-8 -*-
"""Testes do PDF BASE do questionário socioeconômico (sem aluno/overlay)."""
# Exec: python -m unittest tests.test_socioeconomic_questionnaire_pdf
import importlib.util
import io
import re
import unittest
from pathlib import Path
from types import SimpleNamespace

from pypdf import PdfReader

_SERVICE = (
    Path(__file__).resolve().parents[1]
    / "app" / "socioeconomic_forms" / "services" / "questionnaire_pdf_service.py"
)


def _load_service_module():
    spec = importlib.util.spec_from_file_location("socio_questionnaire_pdf_service", _SERVICE)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


SocioeconomicQuestionnairePdfService = _load_service_module().SocioeconomicQuestionnairePdfService


def _question(question_id, order, text, qtype, options=None, sub_questions=None,
              min_value=None, max_value=None, depends_on=None):
    return SimpleNamespace(
        question_id=question_id, question_order=order, text=text, type=qtype,
        options=options, sub_questions=sub_questions, min_value=min_value,
        max_value=max_value, depends_on=depends_on,
    )


def _sample_form(extra_questions=()):
    questions = [
        _question("q2", 2, "Qual é a sua idade?", "selecao_unica",
                  options=[f"{n} anos" for n in range(8, 23)]),
        _question("q1", 1, "Qual é o seu gênero?", "selecao_unica",
                  options=["Feminino", "Masculino", "Outro", "Não quero declarar"]),
        _question("q3", 3, "Informe se você tem alguma(s) das características a seguir.",
                  "matriz_selecao", options=["Não", "Sim", "Não sei"],
                  sub_questions=[{"id": "q3a", "text": "Deficiência"},
                                 {"id": "q3b", "text": "Transtorno do espectro autista"}]),
        _question("q4", 4, "Você possui alguma das seguintes condições?", "multipla_escolha",
                  options=["Não", "Sim"], sub_questions=[{"id": "q4a", "text": "Baixa visão"}]),
        _question("q5", 5, "Indique a adequação dos recursos.", "matriz_selecao_complexa",
                  options=["Não tem", "Não uso", "Inadequado", "Adequado"],
                  sub_questions=[{"id": "Q5_1", "text": "Livro didático."}]),
        _question("q6", 6, "Há quantos anos você estuda nesta escola?", "slider",
                  min_value=0, max_value=30, depends_on={"id": "q3a", "value": "Sim"}),
        _question("q7", 7, "Sugestões de melhoria", "textarea"),
        *extra_questions,
    ]
    return SimpleNamespace(
        id="form-1", title="1° Questionário Socioeconômico - Anos Finais - Escola X",
        custom_title=None, description="Descrição do formulário",
        instructions="Leia com atenção.", questions=questions,
    )


class TestBuildQuestions(unittest.TestCase):
    def setUp(self):
        self.questions = SocioeconomicQuestionnairePdfService.build_questions(
            _sample_form().questions
        )

    def test_order_follows_question_order(self):
        self.assertEqual([q["id"] for q in self.questions], ["q1", "q2", "q3", "q4", "q5", "q6", "q7"])
        self.assertEqual([q["number"] for q in self.questions], [1, 2, 3, 4, 5, 6, 7])

    def test_option_letters_follow_option_count(self):
        age = self.questions[1]
        self.assertEqual(len(age["options"]), 15)
        self.assertEqual(age["options"][0], {"letter": "A", "text": "8 anos"})
        self.assertEqual(age["options"][-1]["letter"], "O")
        self.assertTrue(age["options_two_columns"])
        self.assertFalse(self.questions[0]["options_two_columns"])

    def test_layout_by_data_shape(self):
        layouts = {q["type"]: q["layout"] for q in self.questions}
        self.assertEqual(layouts["selecao_unica"], "options")
        self.assertEqual(layouts["matriz_selecao"], "matrix")
        self.assertEqual(layouts["multipla_escolha"], "matrix")
        self.assertEqual(layouts["matriz_selecao_complexa"], "matrix")
        self.assertEqual(layouts["slider"], "number")
        self.assertEqual(layouts["textarea"], "text")

    def test_sub_questions_keep_ids_and_letters(self):
        matrix = self.questions[2]
        self.assertEqual(
            [(s["id"], s["letter"], s["text"]) for s in matrix["sub_questions"]],
            [("q3a", "a", "Deficiência"), ("q3b", "b", "Transtorno do espectro autista")],
        )

    def test_dependency_references_sub_question(self):
        self.assertEqual(
            self.questions[5]["dependency"],
            {"reference": "Questão 3, item a)", "values": ["Sim"]},
        )

    def test_large_matrix_is_allowed_to_break(self):
        rows = [{"id": f"q8{i}", "text": f"Item {i}"} for i in range(16)]
        big = _question("q8", 8, "Matriz grande", "matriz_selecao", options=["Não", "Sim"], sub_questions=rows)
        questions = SocioeconomicQuestionnairePdfService.build_questions([big])
        self.assertFalse(questions[0]["keep_together"])
        self.assertTrue(self.questions[2]["keep_together"])


class TestRenderHtml(unittest.TestCase):
    def test_template_renders_form_data_without_student_data(self):
        html = SocioeconomicQuestionnairePdfService().render_html(_sample_form())
        for expected in ("Qual é o seu gênero?", "Não quero declarar", "Transtorno do espectro autista",
                         "Livro didático.", "Questão 7", "de 0 a 30", "Prezado(a) estudante,",
                         "EXEMPLOS DE QUESTÕES", "Incentivar você a fazer a tarefa de casa.",
                         "Responda somente se, na Questão 3, item a)", "answer-sheet-header"):
            self.assertIn(expected, html)
        self.assertIn('<div class="qr-code-box"></div>', html)


class TestGenerateBasePdf(unittest.TestCase):
    def test_multipage_a4_pdf(self):
        try:
            from weasyprint import HTML  # noqa: F401
        except ImportError:
            self.skipTest("weasyprint não disponível")

        rows = [{"id": f"m{i}", "text": f"Item da matriz {i}"} for i in range(12)]
        extra = [
            _question(f"x{n}", 100 + n, f"Pergunta extra {n}", "matriz_selecao",
                      options=["Nunca", "Poucas vezes", "Algumas vezes", "Sempre"], sub_questions=rows)
            for n in range(6)
        ]
        pdf_bytes = SocioeconomicQuestionnairePdfService().generate_base_pdf(_sample_form(extra))
        reader = PdfReader(io.BytesIO(pdf_bytes))
        self.assertGreater(len(reader.pages), 1)

        for page in reader.pages:
            width = float(page.mediabox[2]) - float(page.mediabox[0])
            height = float(page.mediabox[3]) - float(page.mediabox[1])
            self.assertLess(abs(width - 595.28), 2.0)
            self.assertLess(abs(height - 841.89), 2.0)

        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        numbers = [int(n) for n in re.findall(r"Questão (\d+)", text)]
        self.assertEqual(sorted(set(numbers)), list(range(1, 14)))
        self.assertIn("Não quero declarar", text)
        self.assertIn("NOME COMPLETO", text)

        cover_text = reader.pages[0].extract_text() or ""
        self.assertIn("NOME COMPLETO", cover_text)
        self.assertNotIn("Questão 1.", cover_text)
        self.assertIn("Questão 1.", reader.pages[1].extract_text() or "")

    def test_corner_anchors_on_every_page(self):
        try:
            from pdf2image import convert_from_bytes
        except ImportError:
            self.skipTest("pdf2image não disponível")

        pdf_bytes = SocioeconomicQuestionnairePdfService().generate_base_pdf(_sample_form())
        pages = convert_from_bytes(pdf_bytes, dpi=72, grayscale=True)
        self.assertGreater(len(pages), 1)
        # Âncora de 32px a 0,2cm da borda: o centro fica a ~0,2cm + 16px de cada borda.
        offset = round(0.2 / 2.54 * 72 + 16 * 0.75)
        for page in pages:
            w, h = page.size
            for x, y in ((offset, offset), (w - offset, offset), (offset, h - offset), (w - offset, h - offset)):
                self.assertLess(page.getpixel((x, y)), 60)


if __name__ == "__main__":
    unittest.main()
