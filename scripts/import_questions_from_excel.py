# -*- coding: utf-8 -*-
"""
Script para importar questões em massa a partir de um arquivo Excel.
Utiliza o endpoint POST /questions da API. Imagens são embutidas em base64
no formattedText; o backend extrai, envia ao MinIO e substitui pela URL da API.

Uso:
    python scripts/import_questions_from_excel.py
    python scripts/import_questions_from_excel.py --create-template  # gera example_questions.xlsx

Estrutura do Excel (mapeamento para o payload da API):
    title          -> title
    text           -> text (texto plano da questão)
    image          -> nome do arquivo em import_data/images/ (ex: q1.png); embutido em formattedText como base64
    educationStageId -> educationStageId (UUID)
    subjectId      -> subjectId (ID da disciplina)
    grade          -> grade (UUID da série)
    difficulty     -> difficulty
    value          -> value (valor da questão)
    skills         -> skills: primeiro ID da lista (backend aceita apenas 1); coluna com IDs separados por vírgula (ex: 123,456,789)
    questionType   -> type (ex: multipleChoice, essay)
    secondStatement -> secondStatement
    A, B, C, D     -> options[].text; options[].id = "A","B","C","D"
    correct        -> letra da alternativa correta (ex: A); define options[].isCorrect e solution
    solution       -> solution (texto da resolução); também usado em formattedSolution
"""

import argparse
import base64
import logging
import os
import sys
from pathlib import Path

import pandas as pd
import requests

# =============================================================================
# CONFIGURAÇÃO (altere conforme o ambiente)
# =============================================================================
API_URL = os.getenv("IMPORT_API_URL", "http://localhost:5000")
API_TOKEN = os.getenv("IMPORT_API_TOKEN", "")
EXCEL_FILE = os.getenv("IMPORT_EXCEL_FILE", "example_questions.xlsx")
IMAGE_FOLDER = os.getenv("IMPORT_IMAGE_FOLDER", "import_data/images")
# createdBy é obrigatório no POST /questions (UUID do usuário que cria a questão)
CREATED_BY = os.getenv("IMPORT_CREATED_BY", "")

# =============================================================================
# LOGGING
# =============================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def _mime_from_ext(ext: str) -> str:
    """Retorna MIME type a partir da extensão do arquivo."""
    ext = (ext or "").lower().lstrip(".")
    mime = {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "gif": "image/gif",
        "webp": "image/webp",
    }
    return mime.get(ext, "image/png")


def load_image_as_base64(image_path: Path) -> str | None:
    """
    Carrega arquivo de imagem e retorna string data URL (data:image/xxx;base64,...).
    Retorna None se o arquivo não existir ou não puder ser lido.
    """
    if not image_path or not image_path.exists():
        return None
    try:
        with open(image_path, "rb") as f:
            raw = f.read()
        b64 = base64.b64encode(raw).decode("ascii")
        ext = image_path.suffix or ".png"
        mime = _mime_from_ext(ext)
        return f"data:{mime};base64,{b64}"
    except Exception as e:
        logger.warning("Falha ao carregar imagem %s: %s", image_path, e)
        return None


def safe_str(val) -> str:
    """Converte valor da célula para string, tratando NaN e None."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    return str(val).strip()


def _parse_value(val):
    """Converte valor da célula para float (value da questão); retorna None se vazio ou inválido."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    s = str(val).strip()
    if not s:
        return None
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def build_formatted_text(text: str, image_data_url: str | None) -> str:
    """
    Monta HTML do enunciado compatível com TipTap.
    formattedText: <p>{texto}</p> e, se houver imagem, <p style="text-align:center"><img src="data:..."></p>
    """
    parts = []
    if text:
        parts.append(f"<p>{text}</p>")
    if image_data_url:
        parts.append('<p style="text-align:center">\n<img src="' + image_data_url + '">\n</p>')
    return "\n".join(parts) if parts else ""


def build_formatted_solution(solution: str) -> str:
    """Monta HTML da solução: <p>{solution}</p>."""
    if not solution:
        return ""
    return f"<p>{solution}</p>"


def build_options(row: pd.Series) -> list[dict]:
    """
    Constrói array options a partir das colunas A, B, C, D e correct.
    correct contém a letra da alternativa correta (ex: A). solution é o texto da resolução.
    Payload: [ {"id": "A", "text": "...", "isCorrect": true/false}, ... ]
    """
    letters = ["A", "B", "C", "D"]
    correct_raw = safe_str(row.get("correct", "")).upper()
    correct_letter = correct_raw[0] if correct_raw else ""
    options = []
    for letter in letters:
        text = safe_str(row.get(letter, ""))
        options.append({
            "id": letter,
            "text": text,
            "isCorrect": letter == correct_letter,
        })
    return options


def row_to_payload(row: pd.Series, image_folder: Path) -> dict | None:
    """
    Converte uma linha do Excel no payload esperado por POST /questions.
    Retorna None se campos obrigatórios estiverem faltando.
    """
    text = safe_str(row.get("text", ""))
    subject_id = safe_str(row.get("subjectId", ""))
    grade = safe_str(row.get("grade", ""))
    question_type = safe_str(row.get("questionType", "multipleChoice")) or "multipleChoice"

    if not text:
        logger.warning("Linha sem 'text'; ignorando.")
        return None
    if not subject_id:
        logger.warning("Linha sem 'subjectId'; ignorando.")
        return None
    if not grade:
        logger.warning("Linha sem 'grade'; ignorando.")
        return None
    if not CREATED_BY:
        logger.error("CREATED_BY não configurado. Defina IMPORT_CREATED_BY ou altere CREATED_BY no script.")
        return None

    # Imagem: coluna "image" = nome do arquivo (ex: q1.png)
    image_filename = safe_str(row.get("image", ""))
    image_data_url = None
    if image_filename:
        image_path = image_folder / image_filename
        image_data_url = load_image_as_base64(image_path)
        if not image_data_url:
            logger.warning("Imagem não encontrada ou inválida: %s (linha com text=%s...)", image_path, text[:50])

    formatted_text = build_formatted_text(text, image_data_url)
    if not formatted_text:
        formatted_text = f"<p>{text}</p>"

    solution = safe_str(row.get("solution", ""))
    formatted_solution = build_formatted_solution(solution) if solution else ""

    # skills: múltiplos IDs separados por vírgula; backend aceita apenas 1, enviamos o primeiro
    skills_raw = safe_str(row.get("skills", ""))
    skill_value = None
    if skills_raw:
        parts = [p.strip() for p in skills_raw.split(",") if p.strip()]
        skill_value = parts[0] if parts else None

    payload = {
        "text": text,
        "type": question_type,
        "subjectId": subject_id,
        "grade": grade,
        "createdBy": CREATED_BY,
        "formattedText": formatted_text,
        "formattedSolution": formatted_solution or None,
        "title": safe_str(row.get("title", "")) or None,
        "secondStatement": safe_str(row.get("secondStatement", "")) or None,
        "educationStageId": safe_str(row.get("educationStageId", "")) or None,
        "difficulty": safe_str(row.get("difficulty", "")) or None,
        "value": _parse_value(row.get("value")),
        "skills": skill_value,
    }

    # Remover chaves com valor None para não sobrescrever defaults
    payload = {k: v for k, v in payload.items() if v is not None}

    if question_type == "multipleChoice":
        options = build_options(row)
        correct_letter = safe_str(row.get("correct", "")).upper()
        if correct_letter and not any(o["isCorrect"] for o in options):
            for o in options:
                if o["id"] == correct_letter:
                    o["isCorrect"] = True
                    break
        payload["options"] = options
        # Backend: "solution" no payload -> correct_answer (letra A/B/C/D)
        payload["solution"] = correct_letter
    # formattedSolution já preenchido acima com o texto da coluna "solution"

    return payload


def create_question(base_url: str, token: str, payload: dict) -> tuple[bool, str | None]:
    """
    Envia POST /questions. Retorna (sucesso, id ou mensagem de erro).
    """
    url = f"{base_url.rstrip('/')}/questions"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=30)
        if r.status_code in (200, 201):
            data = r.json()
            return True, data.get("id") or str(data)
        return False, f"HTTP {r.status_code}: {r.text[:500]}"
    except requests.RequestException as e:
        return False, str(e)


def run_import(excel_path: Path, image_folder: Path, base_url: str, token: str) -> None:
    """Lê o Excel, itera as linhas, envia cada questão e reporta progresso e erros."""
    if not excel_path.exists():
        logger.error("Arquivo não encontrado: %s", excel_path)
        sys.exit(1)

    df = pd.read_excel(excel_path)
    total = len(df)
    success = 0
    failed = []

    for i, row in df.iterrows():
        row_num = i + 2  # 1-based + header
        payload = row_to_payload(row, image_folder)
        if payload is None:
            failed.append((row_num, "Campos obrigatórios faltando ou CREATED_BY não configurado"))
            continue
        ok, result = create_question(base_url, token, payload)
        if ok:
            success += 1
            logger.info("[%d/%d] OK (linha %d) -> id=%s", success, total, row_num, result)
        else:
            failed.append((row_num, result))
            logger.warning("[linha %d] FALHA: %s", row_num, result)

    logger.info("--- Resumo: %d sucesso, %d falhas (de %d linhas) ---", success, len(failed), total)
    if failed:
        for row_num, msg in failed:
            logger.error("Linha %d: %s", row_num, msg)


def create_template_excel(output_path: Path) -> None:
    """Gera example_questions.xlsx com a estrutura de colunas esperada."""
    columns = [
        "title",
        "text",
        "image",
        "educationStageId",
        "subjectId",
        "grade",
        "difficulty",
        "value",
        "skills",
        "questionType",
        "secondStatement",
        "A",
        "B",
        "C",
        "D",
        "correct",
        "solution",
    ]
    # Uma linha de exemplo (valores placeholder)
    example = [
        "Questão exemplo",
        "Qual o resultado de 2 + 2?",
        "q1.png",
        "",
        "",
        "",
        "Médio",
        1.0,
        "123,456,789",
        "multipleChoice",
        "",
        "3",
        "4",
        "5",
        "6",
        "B",
        "2 + 2 = 4, portanto alternativa B.",
    ]
    df = pd.DataFrame([example], columns=columns)
    df.to_excel(output_path, index=False)
    logger.info("Template criado: %s", output_path)


def main():
    parser = argparse.ArgumentParser(description="Importar questões em massa a partir de Excel")
    parser.add_argument(
        "--create-template",
        action="store_true",
        help="Cria example_questions.xlsx com a estrutura de colunas e uma linha de exemplo",
    )
    parser.add_argument("--excel", default=EXCEL_FILE, help="Caminho do arquivo Excel")
    parser.add_argument("--images", default=IMAGE_FOLDER, help="Pasta das imagens (import_data/images)")
    parser.add_argument("--api-url", default=API_URL, help="URL base da API")
    parser.add_argument("--token", default=API_TOKEN, help="Bearer token para autenticação")
    args = parser.parse_args()

    if args.create_template:
        out = Path(args.excel)
        create_template_excel(out)
        return

    image_folder = Path(args.images)
    excel_path = Path(args.excel)
    if not API_TOKEN and not args.token:
        logger.warning("API_TOKEN / --token não definido; a API pode rejeitar a requisição.")
    run_import(excel_path, image_folder, args.api_url, args.token or API_TOKEN)


if __name__ == "__main__":
    main()
