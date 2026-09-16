# -*- coding: utf-8 -*-
"""Gera o template DOCX para importação em lote de questões (múltipla escolha)."""

from __future__ import annotations

from io import BytesIO
from typing import Any, Dict, List, Optional, Sequence, Tuple

from docx import Document
from docx.enum.text import WD_COLOR_INDEX
from docx.shared import Pt, RGBColor

from app.question_import.constants import ALLOWED_DIFFICULTIES

MAX_TEMPLATE_QUESTIONS = 100


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


def parse_template_counts(raw: Optional[str]) -> List[Tuple[str, int]]:
    """
    Parseia counts=subjectId:qtd,subjectId:qtd.

    Retorna lista ordenada [(subject_id, count), ...].
    Levanta ValueError se o formato for inválido.
    """
    text = (raw or "").strip()
    if not text:
        raise ValueError(
            "Parâmetro obrigatório ausente: counts. "
            "Informe a quantidade por disciplina no formato subjectId:qtd,subjectId:qtd."
        )

    pairs: List[Tuple[str, int]] = []
    seen: set = set()
    for part in text.split(","):
        item = part.strip()
        if not item:
            continue
        if ":" not in item:
            raise ValueError(
                f"Formato inválido em counts: '{item}'. Use subjectId:qtd."
            )
        subject_id, qty_raw = item.rsplit(":", 1)
        subject_id = subject_id.strip()
        qty_raw = qty_raw.strip()
        if not subject_id:
            raise ValueError(f"SubjectId vazio em counts: '{item}'.")
        if subject_id in seen:
            raise ValueError(f"SubjectId duplicado em counts: {subject_id}")
        try:
            qty = int(qty_raw)
        except ValueError as exc:
            raise ValueError(
                f"Quantidade inválida para subjectId={subject_id}: '{qty_raw}'. "
                "Informe um inteiro ≥ 1."
            ) from exc
        if qty < 1:
            raise ValueError(
                f"Quantidade inválida para subjectId={subject_id}: {qty}. "
                "Informe um inteiro ≥ 1."
            )
        seen.add(subject_id)
        pairs.append((subject_id, qty))

    if not pairs:
        raise ValueError(
            "Parâmetro counts vazio. Informe subjectId:qtd para cada disciplina."
        )

    total = sum(q for _, q in pairs)
    if total > MAX_TEMPLATE_QUESTIONS:
        raise ValueError(
            f"Total de questões ({total}) excede o limite de {MAX_TEMPLATE_QUESTIONS}."
        )

    return pairs


def resolve_template_question_plan(
    subjects: Sequence[Dict[str, Any]],
    counts_raw: Optional[str],
) -> List[Tuple[Dict[str, Any], int]]:
    """
    Cruza subjects validados com counts.

    - Todo id em counts deve existir em subjects.
    - Toda disciplina em subjects deve ter quantidade em counts.
    - Retorna [(subject_dict, qty), ...] na ordem de counts.
    """
    counts = parse_template_counts(counts_raw)
    by_id = {str(s.get("id")): s for s in subjects if s.get("id")}
    subject_ids = set(by_id.keys())
    count_ids = {sid for sid, _ in counts}

    missing_in_subjects = sorted(count_ids - subject_ids)
    if missing_in_subjects:
        raise ValueError(
            "counts contém disciplina(s) não selecionada(s): "
            + ", ".join(missing_in_subjects)
        )

    missing_counts = sorted(subject_ids - count_ids)
    if missing_counts:
        raise ValueError(
            "Toda disciplina selecionada precisa de quantidade em counts. "
            "Faltando: " + ", ".join(missing_counts)
        )

    return [(by_id[sid], qty) for sid, qty in counts]


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
      subjects: [{id, name}, ...] — disciplinas permitidas
      questionPlan: [(subject, qty), ...] — opcional; se ausente, gera só o exemplo
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

    question_plan: List[Tuple[Dict[str, Any], int]] = list(
        context.get("questionPlan") or []
    )
    if not question_plan and context.get("counts") is not None:
        question_plan = resolve_template_question_plan(subjects, context.get("counts"))

    doc = Document()

    _add_heading(doc, "Template de importação de questões — Afirme Play")
    _add_muted(
        doc,
        "Este arquivo é só para questões de múltipla escolha. "
        "A série já foi definida no formulário (campos em verde — não altere). "
        "A disciplina de cada bloco já vem pré-preenchida. "
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
        "Em cada questão, Disciplina (nome) e SubjectId (UUID) já vêm preenchidos. "
        "O mais seguro é manter o SubjectId da lista. Cada questão pode ter uma disciplina diferente.",
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
        "SubjectId + Disciplina: já preenchidos (não altere)",
        "Dificuldade: obrigatória (copie e cole um dos quatro textos)",
        "Habilidade: código BNCC/código interno (ex.: EF05MA01) — opcional",
        "Título, Comando, Número, Valor — opcionais",
        "Marque a alternativa correta com [CORRETA] no final da linha",
        "No preview, desmarque o bloco de exemplo se ele aparecer",
    ]:
        doc.add_paragraph(line, style="List Bullet")

    example_subject = subjects[0] if subjects else {"id": "", "name": "Matemática"}

    doc.add_paragraph()
    _add_heading(doc, "Exemplo de preenchimento — não copie este bloco", size=13)
    _add_muted(
        doc,
        "Referência de como preencher. Não importe este bloco no preview "
        "(desmarque-o se aparecer na lista).",
    )
    _add_question_block(
        doc,
        subject=example_subject,
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

    if question_plan:
        doc.add_paragraph()
        _add_heading(doc, "Questões para preencher", size=13)
        _add_muted(
            doc,
            "Edite apenas o conteúdo de cada bloco abaixo. "
            "Mantenha os marcadores em amarelo e os campos em verde.",
        )

        question_number = 1
        for subject, qty in question_plan:
            subject_name = subject.get("name") or "—"
            for _ in range(qty):
                doc.add_paragraph()
                _add_heading(
                    doc,
                    f"Questão {question_number} – {subject_name}",
                    size=13,
                )
                _add_question_block(
                    doc,
                    subject=subject,
                    grade_name=grade_name,
                    grade_id=str(grade_id),
                    difficulty="",
                    title="",
                    enunciado="",
                    alternativas=["A) ", "B) ", "C) ", "D) "],
                    solucao="",
                )
                question_number += 1

    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer
