# -*- coding: utf-8 -*-
"""Gera o modelo DOCX de importação de questões do Afirme Educacional."""

from __future__ import annotations

from io import BytesIO
from typing import Any, Dict, Optional

from docx import Document
from docx.enum.text import WD_COLOR_INDEX
from docx.shared import Pt, RGBColor

from app.models.grades import Grade
from app.models.subject import Subject
from app.question_import.constants import ALLOWED_DIFFICULTIES

MAX_TEMPLATE_QUESTIONS = 100
DEFAULT_TEMPLATE_COUNT = 10


def _add_heading(doc: Document, text: str, size: int = 16) -> None:
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(size)
    run.font.color.rgb = RGBColor(0x1A, 0x56, 0xDB)


def _add_warning(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(12)
    run.font.color.rgb = RGBColor(0xDC, 0x26, 0x26)


def _add_muted(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.font.size = Pt(10)
    run.font.color.rgb = RGBColor(0x4B, 0x55, 0x63)


def _add_marker(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(12)
    run.font.highlight_color = WD_COLOR_INDEX.YELLOW


def _add_locked_meta(doc: Document, label: str, value: str) -> None:
    p = doc.add_paragraph()
    run = p.add_run(f"{label}: {value}")
    run.font.size = Pt(11)
    run.font.color.rgb = RGBColor(0x16, 0x65, 0x34)


def _add_user_meta(doc: Document, label: str, value: str) -> None:
    p = doc.add_paragraph()
    run = p.add_run(f"{label}: {value}")
    run.font.size = Pt(11)


def resolve_template_context(grade_id: str, subject_id: str, count: int) -> Dict[str, Any]:
    grade_id = (grade_id or "").strip()
    subject_id = (subject_id or "").strip()
    if not grade_id:
        raise ValueError("Selecione a série antes de baixar o modelo.")
    if not subject_id:
        raise ValueError("Selecione a disciplina antes de baixar o modelo.")
    if count < 1 or count > MAX_TEMPLATE_QUESTIONS:
        raise ValueError(
            f"Informe uma quantidade entre 1 e {MAX_TEMPLATE_QUESTIONS}."
        )

    grade = Grade.query.get(grade_id)
    if not grade:
        raise ValueError("Série não encontrada.")
    subject = Subject.query.get(subject_id)
    if not subject:
        raise ValueError("Disciplina não encontrada.")

    return {
        "gradeId": str(grade.id),
        "gradeName": grade.name,
        "subjectId": str(subject.id),
        "subjectName": subject.name,
        "count": count,
    }


def _add_common_meta(
    doc: Document,
    *,
    grade_name: str,
    grade_id: str,
    subject_name: str,
    subject_id: str,
    question_type: str,
    title: str = "",
    difficulty: str = "",
    ditar: str = "",
) -> None:
    _add_locked_meta(doc, "Série", grade_name)
    _add_locked_meta(doc, "GradeId", grade_id)
    _add_user_meta(doc, "Disciplina", subject_name)
    _add_user_meta(doc, "SubjectId", subject_id)
    _add_user_meta(doc, "Tipo", question_type)
    if difficulty:
        _add_user_meta(doc, "Dificuldade", difficulty)
    else:
        _add_user_meta(doc, "Dificuldade", "")
    _add_user_meta(doc, "Título", title)
    if ditar:
        _add_user_meta(doc, "Ditar", ditar)


def _add_multiple_choice_block(
    doc: Document,
    *,
    grade_name: str,
    grade_id: str,
    subject_name: str,
    subject_id: str,
    title: str = "",
    enunciado: str = "",
    alternativas: Optional[list] = None,
    solucao: str = "",
    difficulty: str = "",
    ditar: str = "",
) -> None:
    _add_marker(doc, "=== QUESTÃO ===")
    _add_common_meta(
        doc,
        grade_name=grade_name,
        grade_id=grade_id,
        subject_name=subject_name,
        subject_id=subject_id,
        question_type="múltipla escolha",
        title=title,
        difficulty=difficulty,
        ditar=ditar,
    )
    doc.add_paragraph()
    _add_marker(doc, "Enunciado:")
    doc.add_paragraph(enunciado)
    doc.add_paragraph()
    _add_marker(doc, "Alternativas:")
    for alt in alternativas or ["A) ", "B) ", "C) ", "D) "]:
        doc.add_paragraph(alt)
    doc.add_paragraph()
    _add_marker(doc, "Solução:")
    _add_muted(
        doc,
        "Escreva só a letra correta (A, B, C…) ou marque [CORRETA] na alternativa.",
    )
    doc.add_paragraph(solucao)
    _add_marker(doc, "=== FIM ===")


def _add_dictation_block(
    doc: Document,
    *,
    grade_name: str,
    grade_id: str,
    subject_name: str,
    subject_id: str,
    title: str = "",
    enunciado: str = "",
    palavra: str = "",
    difficulty: str = "",
    ditar: str = "",
) -> None:
    _add_marker(doc, "=== QUESTÃO ===")
    _add_common_meta(
        doc,
        grade_name=grade_name,
        grade_id=grade_id,
        subject_name=subject_name,
        subject_id=subject_id,
        question_type="ditado",
        title=title,
        difficulty=difficulty,
        ditar=ditar,
    )
    doc.add_paragraph()
    _add_marker(doc, "Enunciado:")
    doc.add_paragraph(enunciado or "Escreva a palavra que o aplicador vai ditar.")
    doc.add_paragraph()
    _add_marker(doc, "Solução:")
    _add_muted(doc, "Coloque aqui a palavra ditada (uma única palavra, sem espaços).")
    doc.add_paragraph(palavra)
    _add_marker(doc, "=== FIM ===")


def _add_text_production_block(
    doc: Document,
    *,
    grade_name: str,
    grade_id: str,
    subject_name: str,
    subject_id: str,
    title: str = "",
    enunciado: str = "",
    criterios: str = "",
    difficulty: str = "",
    ditar: str = "",
) -> None:
    _add_marker(doc, "=== QUESTÃO ===")
    _add_common_meta(
        doc,
        grade_name=grade_name,
        grade_id=grade_id,
        subject_name=subject_name,
        subject_id=subject_id,
        question_type="produção escrita",
        title=title,
        difficulty=difficulty,
        ditar=ditar,
    )
    doc.add_paragraph()
    _add_marker(doc, "Enunciado:")
    doc.add_paragraph(enunciado)
    doc.add_paragraph()
    _add_marker(doc, "Solução:")
    _add_muted(doc, "Opcional: critérios de correção para o professor.")
    doc.add_paragraph(criterios)
    _add_marker(doc, "=== FIM ===")


def build_questions_import_template(context: Dict[str, Any]) -> BytesIO:
    grade_name = context["gradeName"]
    grade_id = context["gradeId"]
    subject_name = context["subjectName"]
    subject_id = context["subjectId"]
    count = int(context["count"])

    doc = Document()

    _add_heading(doc, "Modelo de importação — Afirme Educacional")
    _add_muted(
        doc,
        "Preencha só o conteúdo entre os marcadores amarelos. "
        "Não apague as linhas === QUESTÃO === e === FIM ===. "
        "A série e a disciplina já vêm preenchidas (campos em verde — não altere). "
        "Você pode colar imagens no enunciado ou nas alternativas.",
    )
    doc.add_paragraph()

    _add_heading(doc, "Como preencher", size=13)
    for line in [
        "Tipo: múltipla escolha, ditado ou produção escrita",
        "Dificuldade (opcional): copie um dos textos da lista abaixo",
        "Ditar (opcional): título, enunciado, apoio, alternativas A C",
        "Múltipla escolha: marque [CORRETA] na alternativa ou informe só a letra em Solução",
        "Ditado: em Solução, coloque a palavra ditada",
        "Produção escrita: o enunciado é o comando; não use alternativas",
    ]:
        doc.add_paragraph(line, style="List Bullet")

    doc.add_paragraph()
    _add_heading(doc, "Dificuldade (opcional)", size=13)
    for label in ALLOWED_DIFFICULTIES:
        doc.add_paragraph(label, style="List Bullet")

    doc.add_paragraph()
    _add_heading(doc, "Exemplos — não importe estes blocos", size=13)
    _add_warning(
        doc,
        "Os três blocos abaixo são só referência. Na pré-visualização, ignore-os se aparecerem.",
    )

    doc.add_paragraph()
    _add_heading(doc, "Exemplo 1 — múltipla escolha", size=12)
    _add_multiple_choice_block(
        doc,
        grade_name=grade_name,
        grade_id=grade_id,
        subject_name=subject_name,
        subject_id=subject_id,
        title="Palavras com a letra B",
        enunciado="Qual palavra começa com a mesma letra de BOLA?",
        alternativas=["A) Dado", "B) Casa", "C) Bota [CORRETA]", "D) Pato"],
        solucao="C",
        difficulty="Básico",
        ditar="enunciado",
    )

    doc.add_paragraph()
    _add_heading(doc, "Exemplo 2 — ditado", size=12)
    _add_dictation_block(
        doc,
        grade_name=grade_name,
        grade_id=grade_id,
        subject_name=subject_name,
        subject_id=subject_id,
        title="Ditado — borboleta",
        enunciado="Escreva a palavra que o aplicador vai ditar.",
        palavra="borboleta",
        difficulty="Básico",
        ditar="enunciado",
    )

    doc.add_paragraph()
    _add_heading(doc, "Exemplo 3 — produção escrita", size=12)
    _add_text_production_block(
        doc,
        grade_name=grade_name,
        grade_id=grade_id,
        subject_name=subject_name,
        subject_id=subject_id,
        title="Bilhete para a família",
        enunciado="Escreva um bilhete convidando a família para a reunião da escola.",
        criterios="Observe se o bilhete tem destinatário, mensagem clara e despedida.",
        difficulty="Adequado",
        ditar="título, enunciado",
    )

    doc.add_paragraph()
    _add_heading(doc, "Questões para preencher", size=13)
    _add_muted(
        doc,
        "Edite apenas o conteúdo de cada bloco. Mantenha os marcadores em amarelo e os campos em verde.",
    )

    for index in range(1, count + 1):
        doc.add_paragraph()
        _add_heading(doc, f"Questão {index}", size=13)
        _add_multiple_choice_block(
            doc,
            grade_name=grade_name,
            grade_id=grade_id,
            subject_name=subject_name,
            subject_id=subject_id,
        )

    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer
