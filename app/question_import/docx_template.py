# -*- coding: utf-8 -*-
"""Gera o template DOCX para importação em lote de questões (múltipla escolha)."""

from __future__ import annotations

from io import BytesIO
from typing import Any, Dict, List, Optional

from docx import Document
from docx.enum.text import WD_COLOR_INDEX
from docx.shared import Pt, RGBColor

from app.question_import.constants import ALLOWED_DIFFICULTIES


def _add_heading(doc: Document, text: str, size: int = 16) -> None:
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(size)
    run.font.color.rgb = RGBColor(0x1A, 0x56, 0xDB)


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
    """Campo pré-preenchido pelo sistema — usuário não deve editar."""
    p = doc.add_paragraph()
    run = p.add_run(f"{label}: {value}")
    run.font.size = Pt(11)
    run.font.color.rgb = RGBColor(0x16, 0x65, 0x34)


def _add_user_meta(doc: Document, label: str, value: str) -> None:
    """Campo que o usuário preenche/escolhe por questão."""
    p = doc.add_paragraph()
    run = p.add_run(f"{label}: {value}")
    run.font.size = Pt(11)


def _add_question_block(
    doc: Document,
    *,
    subject: Dict[str, Any],
    grade_name: str,
    grade_id: str,
    difficulty: str,
    title: str,
    enunciado: str,
    alternativas: List[str],
    solucao: str,
    skill: Optional[str] = None,
) -> None:
    _add_marker(doc, "=== QUESTÃO ===")
    _add_locked_meta(doc, "Série", grade_name)
    if grade_id:
        _add_locked_meta(doc, "GradeId", str(grade_id))
    # Disciplina por questão — copiar SubjectId da lista
    _add_user_meta(doc, "Disciplina", subject.get("name") or "—")
    if subject.get("id"):
        _add_user_meta(doc, "SubjectId", str(subject["id"]))
    _add_user_meta(doc, "Dificuldade", difficulty)
    if skill:
        doc.add_paragraph(f"Habilidade: {skill}")
    doc.add_paragraph(f"Título: {title}")
    doc.add_paragraph()
    _add_marker(doc, "Enunciado:")
    doc.add_paragraph(enunciado)
    doc.add_paragraph()
    _add_marker(doc, "Alternativas:")
    for alt in alternativas:
        doc.add_paragraph(alt)
    doc.add_paragraph()
    _add_marker(doc, "Solução:")
    doc.add_paragraph(solucao)
    _add_marker(doc, "=== FIM ===")


def build_questions_import_template(context: Optional[Dict[str, Any]] = None) -> BytesIO:
    """
    Monta um .docx só para questões de múltipla escolha.

    context:
      gradeId, gradeName (obrigatórios)
      subjects: [{id, name}, ...] — disciplinas permitidas / exemplos
      defaultSubjectId / defaultSubjectName — opcional (atalho 1 disciplina)
    """
    context = context or {}
    grade_name = context.get("gradeName") or "—"
    grade_id = context.get("gradeId") or ""
    subjects: List[Dict[str, Any]] = list(context.get("subjects") or [])
    if not subjects and context.get("subjectId"):
        subjects = [
            {
                "id": context.get("subjectId"),
                "name": context.get("subjectName") or "—",
            }
        ]

    doc = Document()

    _add_heading(doc, "Template de importação de questões — Afirme Play")
    _add_muted(
        doc,
        "Este arquivo é só para questões de múltipla escolha. "
        "A série já foi definida no formulário (campos em verde — não altere). "
        "A disciplina é por questão: em cada bloco, copie e cole o SubjectId "
        "da disciplina desejada (lista abaixo). "
        "Não altere os marcadores em amarelo. Você pode colar imagens no enunciado, "
        "nas alternativas ou na solução.",
    )
    doc.add_paragraph()

    _add_heading(doc, "Contexto deste arquivo (não editar)", size=13)
    _add_locked_meta(doc, "Série", grade_name)
    if grade_id:
        _add_locked_meta(doc, "GradeId", str(grade_id))
    doc.add_paragraph()

    _add_heading(doc, "Disciplinas deste arquivo (copie o SubjectId)", size=13)
    _add_muted(
        doc,
        "Em cada questão, preencha Disciplina (nome) e SubjectId (UUID). "
        "O mais seguro é copiar o SubjectId da lista. Cada questão pode ter uma disciplina diferente.",
    )
    if subjects:
        for subj in subjects:
            doc.add_paragraph(
                f"{subj.get('name') or '—'} → SubjectId: {subj.get('id')}",
                style="List Bullet",
            )
    else:
        _add_muted(
            doc,
            "Nenhuma disciplina foi enviada na geração do template. "
            "Informe SubjectId manualmente em cada questão (UUID cadastrado no sistema).",
        )

    doc.add_paragraph()
    _add_heading(doc, "Dificuldade (obrigatória em cada questão)", size=13)
    _add_muted(
        doc,
        "Copie e cole um dos textos abaixo exatamente no campo Dificuldade. "
        "Variações leves de acento/maiúscula são aceitas, mas o mais seguro é copiar e colar.",
    )
    for label in ALLOWED_DIFFICULTIES:
        doc.add_paragraph(label, style="List Bullet")

    doc.add_paragraph()
    _add_heading(doc, "O que você preenche em cada questão", size=13)
    for line in [
        "SubjectId + Disciplina: obrigatórios por questão (copie da lista acima)",
        "Dificuldade: obrigatória (copie e cole um dos quatro textos)",
        "Habilidade: código BNCC/código interno (ex.: EF05MA01) — opcional",
        "Título, Comando, Número, Valor — opcionais",
        "Marque a alternativa correta com [CORRETA] no final da linha",
    ]:
        doc.add_paragraph(line, style="List Bullet")

    # Exemplos: uma questão por disciplina (até 2), senão 2 da mesma
    example_subjects = subjects[:2] if subjects else [
        {"id": "", "name": "Matemática"},
        {"id": "", "name": "Língua Portuguesa"},
    ]
    if len(example_subjects) == 1:
        example_subjects = [example_subjects[0], example_subjects[0]]

    doc.add_paragraph()
    _add_heading(doc, "Exemplo 1", size=13)
    _add_question_block(
        doc,
        subject=example_subjects[0],
        grade_name=grade_name,
        grade_id=str(grade_id),
        difficulty="Adequado",
        title="Frações equivalentes",
        enunciado=(
            "Qual das frações abaixo é equivalente a 1/2? "
            "(Você pode colar uma imagem aqui, se quiser.)"
        ),
        alternativas=["A) 2/4 [CORRETA]", "B) 1/3", "C) 3/5", "D) 2/5"],
        solucao=(
            "Multiplicando numerador e denominador de 1/2 por 2 obtemos 2/4, "
            "que é uma fração equivalente."
        ),
        skill="EF05MA01",
    )

    doc.add_paragraph()
    _add_heading(doc, "Exemplo 2 (outra disciplina e/ou dificuldade)", size=13)
    _add_question_block(
        doc,
        subject=example_subjects[1],
        grade_name=grade_name,
        grade_id=str(grade_id),
        difficulty="Básico",
        title="Números pares" if example_subjects[0].get("id") == example_subjects[1].get("id") else "Interpretação de texto",
        enunciado=(
            "Qual dos números abaixo é par?"
            if example_subjects[0].get("id") == example_subjects[1].get("id")
            else "No texto, a palavra destacada indica qual ideia?"
        ),
        alternativas=(
            ["A) 3", "B) 7", "C) 8 [CORRETA]", "D) 9"]
            if example_subjects[0].get("id") == example_subjects[1].get("id")
            else ["A) causa [CORRETA]", "B) tempo", "C) lugar", "D) modo"]
        ),
        solucao=(
            "8 é divisível por 2, portanto é par."
            if example_subjects[0].get("id") == example_subjects[1].get("id")
            else "A palavra indica relação de causa."
        ),
    )

    doc.add_paragraph()
    _add_muted(
        doc,
        "Dica: copie o bloco inteiro (=== QUESTÃO === até === FIM ===) para adicionar mais questões. "
        "Mantenha Série/GradeId; altere SubjectId (disciplina), Dificuldade e o conteúdo.",
    )

    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer
