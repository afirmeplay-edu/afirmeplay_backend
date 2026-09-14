# -*- coding: utf-8 -*-
"""Parser de DOCX estruturado para importação de questões."""

from __future__ import annotations

import base64
import html
import io
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from docx import Document
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph
from PIL import Image

logger = logging.getLogger(__name__)

SECTION_START_RE = re.compile(r"^===\s*QUEST[AÃ]O\s*===$", re.IGNORECASE)
SECTION_END_RE = re.compile(r"^===\s*FIM\s*===$", re.IGNORECASE)
ENUNCIADO_RE = re.compile(r"^Enunciado\s*:?\s*$", re.IGNORECASE)
ALTERNATIVAS_RE = re.compile(r"^Alternativas?\s*:?\s*$", re.IGNORECASE)
SOLUCAO_RE = re.compile(r"^Solu[cç][aã]o\s*:?\s*$", re.IGNORECASE)
META_RE = re.compile(r"^([^:]+)\s*:\s*(.*)$")
ALT_START_RE = re.compile(
    r"^([A-Ja-j])\)\s*(.*?)(?:\s*\[CORRET[AO]\])?\s*$",
    re.IGNORECASE,
)
CORRECT_MARK_RE = re.compile(r"\s*\[CORRET[AO]\]\s*$", re.IGNORECASE)

META_ALIASES = {
    "tipo": "type",
    "type": "type",
    "disciplina": "subject",
    "subject": "subject",
    "subjectid": "subjectId",
    "subject_id": "subjectId",
    "serie": "grade",
    "série": "grade",
    "grade": "grade",
    "gradeid": "gradeId",
    "grade_id": "gradeId",
    "dificuldade": "difficulty",
    "difficulty": "difficulty",
    "habilidade": "skill",
    "skill": "skill",
    "skills": "skill",
    "titulo": "title",
    "título": "title",
    "title": "title",
    "comando": "command",
    "command": "command",
    "descricao": "description",
    "descrição": "description",
    "description": "description",
    "subtitulo": "subtitle",
    "subtítulo": "subtitle",
    "subtitle": "subtitle",
    "numero": "number",
    "número": "number",
    "number": "number",
    "valor": "value",
    "value": "value",
}

TYPE_MAP = {
    "multiplechoice": "multipleChoice",
    "multiple_choice": "multipleChoice",
    "objetiva": "multipleChoice",
    "multipla_escolha": "multipleChoice",
    "múltipla_escolha": "multipleChoice",
    "multipla escolha": "multipleChoice",
    "múltipla escolha": "multipleChoice",
    "essay": "essay",
    "discursive": "essay",
    "dissertativa": "essay",
    "discursiva": "essay",
    "aberta": "essay",
    "open": "essay",
    "open_ended": "essay",
}


def _normalize_key(raw: str) -> str:
    key = (raw or "").strip().lower()
    key = key.replace(" ", "").replace("_", "").replace("-", "")
    # keep accents for série/tópicos lookup via META_ALIASES which has accented forms
    return key


def _canonical_meta_key(raw: str) -> Optional[str]:
    stripped = (raw or "").strip().lower()
    if stripped in META_ALIASES:
        return META_ALIASES[stripped]
    compact = _normalize_key(raw)
    # rebuild lookup without accents-insensitive for common keys
    for alias, canonical in META_ALIASES.items():
        if _normalize_key(alias) == compact:
            return canonical
    return None


def _normalize_type(raw: str) -> Optional[str]:
    if not raw:
        return None
    key = raw.strip().lower().replace("-", "_")
    if key in TYPE_MAP:
        return TYPE_MAP[key]
    key2 = key.replace(" ", "_")
    if key2 in TYPE_MAP:
        return TYPE_MAP[key2]
    # accept already-canonical
    if raw.strip() in ("multipleChoice", "essay"):
        return raw.strip()
    return raw.strip()


def _image_part_to_data_url(blob: bytes, content_type: Optional[str]) -> Tuple[str, str]:
    """Converte bytes da imagem em data-URL PNG/JPEG estável."""
    mime = (content_type or "image/png").split(";")[0].strip().lower()
    try:
        img = Image.open(io.BytesIO(blob))
        fmt = (img.format or "PNG").upper()
        out = io.BytesIO()
        if fmt in ("JPEG", "JPG"):
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            img.save(out, format="JPEG", quality=90)
            mime = "image/jpeg"
        else:
            if img.mode == "P":
                img = img.convert("RGBA")
            img.save(out, format="PNG")
            mime = "image/png"
        encoded = base64.b64encode(out.getvalue()).decode("ascii")
    except Exception:
        encoded = base64.b64encode(blob).decode("ascii")
        if "jpeg" in mime or "jpg" in mime:
            mime = "image/jpeg"
        elif "gif" in mime:
            mime = "image/gif"
        elif "webp" in mime:
            mime = "image/webp"
        else:
            mime = "image/png"
    return f"data:{mime};base64,{encoded}", mime


def _extract_images_from_element(element, document_part) -> List[str]:
    data_urls: List[str] = []
    for blip in element.findall(".//" + qn("a:blip")):
        embed = blip.get(qn("r:embed"))
        if not embed:
            continue
        try:
            part = document_part.related_parts[embed]
        except KeyError:
            continue
        data_url, _ = _image_part_to_data_url(part.blob, getattr(part, "content_type", None))
        data_urls.append(data_url)
    return data_urls


def _process_run_element(run_el, document_part) -> Tuple[str, str, List[str]]:
    """Retorna (html_fragment, plain_text, data_urls)."""
    html_parts: List[str] = []
    plain_parts: List[str] = []
    images: List[str] = []

    for node in run_el.iterchildren():
        tag = node.tag
        if tag == qn("w:t"):
            text = node.text or ""
            if text:
                html_parts.append(html.escape(text))
                plain_parts.append(text)
        elif tag == qn("w:tab"):
            html_parts.append("&nbsp;&nbsp;&nbsp;&nbsp;")
            plain_parts.append("\t")
        elif tag == qn("w:br"):
            html_parts.append("<br/>")
            plain_parts.append("\n")
        elif tag in (qn("w:drawing"), qn("w:pict")):
            for data_url in _extract_images_from_element(node, document_part):
                images.append(data_url)
                html_parts.append(f'<img src="{data_url}" alt=""/>')

    # fallback: blips nested deeper / not as direct children
    if not images:
        for data_url in _extract_images_from_element(run_el, document_part):
            images.append(data_url)
            html_parts.append(f'<img src="{data_url}" alt=""/>')

    return "".join(html_parts), "".join(plain_parts), images


def paragraph_content(paragraph: Paragraph) -> Dict[str, Any]:
    """Extrai HTML, texto plano e imagens de um parágrafo, na ordem do documento."""
    html_parts: List[str] = []
    plain_parts: List[str] = []
    images: List[str] = []
    part = paragraph.part

    for child in paragraph._p.iterchildren():
        if child.tag == qn("w:r"):
            h, t, imgs = _process_run_element(child, part)
            html_parts.append(h)
            plain_parts.append(t)
            images.extend(imgs)
        elif child.tag == qn("w:hyperlink"):
            for run in child.findall(qn("w:r")):
                h, t, imgs = _process_run_element(run, part)
                html_parts.append(h)
                plain_parts.append(t)
                images.extend(imgs)

    plain = "".join(plain_parts).strip()
    inner_html = "".join(html_parts).strip()
    return {
        "plain": plain,
        "html": f"<p>{inner_html}</p>" if inner_html else "",
        "images": images,
        "has_content": bool(plain or images),
    }


def _join_html(blocks: List[str]) -> str:
    return "".join(b for b in blocks if b)


def _join_plain(blocks: List[str]) -> str:
    return "\n".join(b for b in blocks if b).strip()


def _flush_alternative(buf: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not buf:
        return None
    text = _join_plain(buf.get("plain_parts") or [])
    html_body = _join_html(buf.get("html_parts") or [])
    images = buf.get("images") or []
    option: Dict[str, Any] = {
        "id": buf["letter"].upper(),
        "text": text,
        "isCorrect": bool(buf.get("is_correct")),
    }
    if html_body and (images or "<img" in html_body):
        option["formattedText"] = html_body
    if len(images) == 1 and not text:
        option["image"] = images[0]
    elif images and not option.get("image"):
        # múltiplas imagens: ficam no HTML; se não houver texto, ainda assim precisa de content
        if not text:
            option["text"] = ""
            option["formattedText"] = html_body or "".join(
                f'<img src="{u}" alt=""/>' for u in images
            )
    return option


def _parse_alternative_paragraph(content: Dict[str, Any], current: Optional[Dict[str, Any]], options: List[Dict[str, Any]]):
    plain = content["plain"]
    match = ALT_START_RE.match(plain) if plain else None

    if match:
        flushed = _flush_alternative(current) if current else None
        if flushed:
            options.append(flushed)

        letter = match.group(1).upper()
        rest = match.group(2) or ""
        is_correct = bool(CORRECT_MARK_RE.search(plain))
        rest_clean = CORRECT_MARK_RE.sub("", rest).strip()

        # Rebuild HTML for the remainder: if whole paragraph was "A) text [CORRETA]",
        # keep images from the paragraph and use cleaned text.
        html_parts = []
        if rest_clean:
            html_parts.append(f"<p>{html.escape(rest_clean)}</p>")
        for data_url in content["images"]:
            # if images already embedded in content html with surrounding text, still OK
            if data_url and f'src="{data_url}"' not in "".join(html_parts):
                html_parts.append(f'<p><img src="{data_url}" alt=""/></p>')

        # Prefer original html with marker stripped from plain representation
        original_html = content["html"]
        if original_html and CORRECT_MARK_RE.search(plain):
            # strip [CORRETA] from escaped html roughly
            original_html = re.sub(
                r"\s*\[CORRET[AO]\]",
                "",
                original_html,
                flags=re.IGNORECASE,
            )
            # remove leading "A) "
            original_html = re.sub(
                r"(<p>)?\s*[A-Ja-j]\)\s*",
                r"\1",
                original_html,
                count=1,
            )

        return {
            "letter": letter,
            "is_correct": is_correct,
            "plain_parts": [rest_clean] if rest_clean else [],
            "html_parts": [original_html] if original_html else html_parts,
            "images": list(content["images"]),
        }, options

    if current is None:
        # orphan content before first A) — ignore unless it has images with a warning later
        return current, options

    if content["plain"]:
        current["plain_parts"].append(content["plain"])
    if content["html"]:
        current["html_parts"].append(content["html"])
    current["images"].extend(content["images"])
    if CORRECT_MARK_RE.search(plain or ""):
        current["is_correct"] = True
    return current, options


def _empty_section() -> Dict[str, Any]:
    return {
        "meta": {},
        "enunciado_html": [],
        "enunciado_plain": [],
        "enunciado_images": [],
        "options": [],
        "alt_current": None,
        "solucao_html": [],
        "solucao_plain": [],
        "phase": "meta",
        "raw_errors": [],
    }


def parse_questions_docx(file_stream) -> List[Dict[str, Any]]:
    """
    Lê o DOCX e devolve lista de blocos brutos:
    {
      index, meta, enunciado: {text, html, images},
      options: [...], solution: {text, html}, errors: []
    }
    """
    document = Document(file_stream)
    sections: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None

    def close_current():
        nonlocal current
        if current is None:
            return
        if current.get("alt_current"):
            flushed = _flush_alternative(current["alt_current"])
            if flushed:
                current["options"].append(flushed)
            current["alt_current"] = None
        sections.append(current)
        current = None

    for paragraph in document.paragraphs:
        content = paragraph_content(paragraph)
        plain = content["plain"]

        if SECTION_START_RE.match(plain):
            close_current()
            current = _empty_section()
            continue

        if current is None:
            continue

        if SECTION_END_RE.match(plain):
            close_current()
            continue

        if ENUNCIADO_RE.match(plain):
            if current.get("alt_current"):
                flushed = _flush_alternative(current["alt_current"])
                if flushed:
                    current["options"].append(flushed)
                current["alt_current"] = None
            current["phase"] = "enunciado"
            continue

        if ALTERNATIVAS_RE.match(plain):
            if current.get("alt_current"):
                flushed = _flush_alternative(current["alt_current"])
                if flushed:
                    current["options"].append(flushed)
                current["alt_current"] = None
            current["phase"] = "alternativas"
            continue

        if SOLUCAO_RE.match(plain):
            if current.get("alt_current"):
                flushed = _flush_alternative(current["alt_current"])
                if flushed:
                    current["options"].append(flushed)
                current["alt_current"] = None
            current["phase"] = "solucao"
            continue

        phase = current["phase"]

        if phase == "meta":
            if not plain and not content["images"]:
                continue
            meta_match = META_RE.match(plain) if plain else None
            if meta_match:
                raw_key, raw_val = meta_match.group(1), meta_match.group(2)
                canonical = _canonical_meta_key(raw_key)
                if canonical:
                    current["meta"][canonical] = (raw_val or "").strip()
                else:
                    current["raw_errors"].append(f"Campo de metadado desconhecido: {raw_key}")
            elif content["has_content"]:
                # conteúdo sem chave antes do enunciado — trata como início do enunciado
                current["phase"] = "enunciado"
                if content["plain"]:
                    current["enunciado_plain"].append(content["plain"])
                if content["html"]:
                    current["enunciado_html"].append(content["html"])
                current["enunciado_images"].extend(content["images"])
            continue

        if phase == "enunciado":
            if not content["has_content"]:
                continue
            if content["plain"]:
                current["enunciado_plain"].append(content["plain"])
            if content["html"]:
                current["enunciado_html"].append(content["html"])
            current["enunciado_images"].extend(content["images"])
            continue

        if phase == "alternativas":
            if not content["has_content"]:
                continue
            current["alt_current"], current["options"] = _parse_alternative_paragraph(
                content, current.get("alt_current"), current["options"]
            )
            continue

        if phase == "solucao":
            if not content["has_content"]:
                continue
            if content["plain"]:
                current["solucao_plain"].append(content["plain"])
            if content["html"]:
                current["solucao_html"].append(content["html"])
            continue

    close_current()

    results: List[Dict[str, Any]] = []
    for idx, section in enumerate(sections, start=1):
        meta = dict(section.get("meta") or {})
        if "type" in meta:
            meta["type"] = _normalize_type(meta["type"]) or meta["type"]

        enunciado_text = _join_plain(section.get("enunciado_plain") or [])
        enunciado_html = _join_html(section.get("enunciado_html") or [])
        solucao_text = _join_plain(section.get("solucao_plain") or [])
        solucao_html = _join_html(section.get("solucao_html") or [])

        results.append(
            {
                "index": idx,
                "meta": meta,
                "enunciado": {
                    "text": enunciado_text,
                    "html": enunciado_html,
                    "imagesCount": len(section.get("enunciado_images") or []),
                },
                "options": section.get("options") or [],
                "solution": {
                    "text": solucao_text,
                    "html": solucao_html,
                },
                "parseErrors": list(section.get("raw_errors") or []),
            }
        )

    return results
