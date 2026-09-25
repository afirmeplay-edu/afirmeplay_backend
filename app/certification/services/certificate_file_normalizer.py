from __future__ import annotations

import io
import os
from typing import Any, Dict

from PIL import Image, ImageOps
from pypdf import PdfReader
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas

A4_WIDTH_PT = 841.8897637795277
A4_HEIGHT_PT = 595.2755905511812
MAX_CERTIFICATE_FILE_BYTES = 20 * 1024 * 1024
TOLERANCE_PT = 2 * 72 / 25.4


def _validate_landscape(width: float, height: float, label: str) -> None:
    if abs(width - A4_WIDTH_PT) <= TOLERANCE_PT and abs(height - A4_HEIGHT_PT) <= TOLERANCE_PT:
        return
    raise ValueError(f'{label} precisa estar em A4 paisagem (297x210 mm).')


def normalize_upload(filename: str, data: bytes) -> Dict[str, Any]:
    if not data or len(data) > MAX_CERTIFICATE_FILE_BYTES:
        raise ValueError('Arquivo vazio ou maior que 20 MB.')
    lower = os.path.basename(filename or '').lower()
    if data.startswith(b'%PDF'):
        reader = PdfReader(io.BytesIO(data))
        if len(reader.pages) != 1:
            raise ValueError('O modelo deve ter exatamente uma página.')
        page = reader.pages[0]
        width, height = float(page.mediabox.width), float(page.mediabox.height)
        _validate_landscape(width, height, 'O PDF')
        return {
            'source_kind': 'pdf', 'mime_type': 'application/pdf', 'page_count': 1,
            'page_width_pt': width, 'page_height_pt': height, 'rotation': 0,
            'normalized_pdf': data,
        }
    if data.startswith(b'\x89PNG\r\n\x1a\n'):
        kind, mime = 'png', 'image/png'
    elif data.startswith(b'\xff\xd8\xff'):
        kind, mime = 'jpeg', 'image/jpeg'
    else:
        raise ValueError('Formato não suportado. Envie PDF, JPG/JPEG ou PNG.')

    try:
        image = ImageOps.exif_transpose(Image.open(io.BytesIO(data)))
        image.load()
    except Exception as exc:
        raise ValueError(f'Imagem inválida: {exc}') from exc
    ratio = image.width / float(image.height)
    target_ratio = A4_WIDTH_PT / A4_HEIGHT_PT
    if abs(ratio - target_ratio) / target_ratio > 0.02:
        raise ValueError('A imagem precisa ter proporção A4 paisagem (297x210 mm).')

    image = image.convert('RGB') if image.mode not in ('RGB', 'RGBA') else image
    buffer = io.BytesIO()
    canvas = Canvas(buffer, pagesize=(A4_WIDTH_PT, A4_HEIGHT_PT))
    canvas.drawImage(ImageReader(image), 0, 0, width=A4_WIDTH_PT, height=A4_HEIGHT_PT, preserveAspectRatio=False)
    canvas.showPage()
    canvas.save()
    return {
        'source_kind': kind, 'mime_type': mime, 'page_count': 1,
        'page_width_pt': A4_WIDTH_PT, 'page_height_pt': A4_HEIGHT_PT, 'rotation': 0,
        'normalized_pdf': buffer.getvalue(),
    }
