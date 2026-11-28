# -*- coding: utf-8 -*-
"""
Identidade best-effort na Correção por foto (QR + ID-Grid) + filtro opcional.

O detector de bolhas não lê identidade. Esta camada tenta QR/ID-Grid na imagem
(quando o cabeçalho está no enquadramento) e cruza com student_id opcional
vindo dos filtros da UI.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)


def _empty_detected() -> Dict[str, Any]:
    return {
        "student_id": None,
        "gabarito_id": None,
        "test_id": None,
        "identity_source": None,
        "identity_confidence": None,
        "idgrid_checksum_ok": None,
        "identity_mismatch": False,
        "detected": False,
    }


def detect_sheet_identity(image_data: bytes) -> Dict[str, Any]:
    """
    Tenta ler QR e/ou ID-Grid na foto. Nunca levanta por ausência de identidade.
    """
    if not image_data:
        return _empty_detected()

    try:
        img = cv2.imdecode(np.frombuffer(image_data, dtype=np.uint8), cv2.IMREAD_COLOR)
        if img is None or img.size == 0:
            return _empty_detected()

        from app.services.cartao_resposta.correction_new_grid import (
            AnswerSheetCorrectionNewGrid,
        )

        omr = AnswerSheetCorrectionNewGrid(debug=False)

        qr_data = None
        try:
            qr_data = omr._detectar_qr_code(img)
        except Exception as exc:
            logger.info("photo_identity: QR não lido (%s)", exc)
            qr_data = None

        idgrid_result = None
        try:
            anchors = omr._detect_a4_anchors(img)
            if anchors:
                img_a4 = omr._normalize_to_a4(img, anchors)
            else:
                img_a4 = cv2.resize(img, (2480, 3508), interpolation=cv2.INTER_AREA)
            idgrid_result = omr._read_identity_grid(img_a4)
        except Exception as exc:
            logger.info("photo_identity: ID-Grid não lido (%s)", exc)
            idgrid_result = None

        if not qr_data and not (idgrid_result and idgrid_result.get("present")):
            return _empty_detected()

        identity = omr._merge_qr_and_idgrid(qr_data, idgrid_result)
        student_id = identity.get("student_id")
        gabarito_id = identity.get("gabarito_id")
        test_id = identity.get("test_id")
        detected = bool(student_id or gabarito_id or test_id)
        return {
            "student_id": student_id,
            "gabarito_id": gabarito_id,
            "test_id": test_id,
            "identity_source": identity.get("identity_source"),
            "identity_confidence": identity.get("identity_confidence"),
            "idgrid_checksum_ok": identity.get("idgrid_checksum_ok"),
            "identity_mismatch": bool(identity.get("identity_mismatch")),
            "detected": detected,
        }
    except Exception as exc:
        logger.warning("photo_identity: falha inesperada (%s)", exc, exc_info=True)
        return _empty_detected()


def _gabarito_test_id(gabarito_id: Optional[str]) -> Optional[str]:
    """Resolve test_id vinculado ao gabarito (cartão da prova)."""
    gid = (gabarito_id or "").strip() or None
    if not gid:
        return None
    try:
        from app.models.answerSheetGabarito import AnswerSheetGabarito

        row = AnswerSheetGabarito.query.get(gid)
        tid = getattr(row, "test_id", None) if row else None
        return str(tid).strip() if tid else None
    except Exception:
        return None


def _documents_compatible(
    *,
    expected_test_id: Optional[str],
    expected_gabarito_id: Optional[str],
    det_test_id: Optional[str],
    det_gabarito_id: Optional[str],
) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
    """
    Cartão OMR costuma trazer só gabarito_id no QR; a UI seleciona a prova (test_id).

    Compatível quando:
    - IDs iguais no mesmo tipo, ou
    - expected_test_id == gabarito.test_id do gabarito detectado, ou
    - expected_gabarito_id é o gabarito detectado / o da prova esperada.

    Retorna (ok, resolved_test_id, resolved_gabarito_id, reason|None).
    """
    exp_t = (expected_test_id or "").strip() or None
    exp_g = (expected_gabarito_id or "").strip() or None
    det_t = (det_test_id or "").strip() or None
    det_g = (det_gabarito_id or "").strip() or None

    # Sem expectativa de documento na rota → não há mismatch de doc
    if not exp_t and not exp_g:
        return True, det_t, det_g, None

    # Sem documento na foto → não marca mismatch (filtro/rota prevalece)
    if not det_t and not det_g:
        return True, exp_t, exp_g, None

    gabarito_linked_test = _gabarito_test_id(det_g) if det_g else None
    resolved_t = det_t or gabarito_linked_test
    resolved_g = det_g

    if exp_g:
        if det_g and det_g != exp_g:
            return False, resolved_t, resolved_g, "gabarito_mismatch"
        if det_t and not det_g:
            # Foto trouxe prova física; rota é cartão avulso
            return False, resolved_t, resolved_g, "test_vs_gabarito"
        return True, resolved_t or exp_t, resolved_g or exp_g, None

    # Rota de prova (expected_test_id)
    if exp_t:
        if det_t and det_t == exp_t:
            return True, exp_t, resolved_g, None
        if det_g and gabarito_linked_test and gabarito_linked_test == exp_t:
            # QR/ID-Grid do cartão da mesma prova — OK (não é "outra prova")
            return True, exp_t, resolved_g, None
        if det_g and not gabarito_linked_test and not det_t:
            # Gabarito avulso sem test_id: incompatível com rota de prova
            return False, resolved_t, resolved_g, "gabarito_without_test"
        if det_t and det_t != exp_t:
            return False, resolved_t, resolved_g, "test_mismatch"
        if det_g and gabarito_linked_test and gabarito_linked_test != exp_t:
            return False, resolved_t, resolved_g, "gabarito_other_test"
        # det_g sem link resolvido já tratado; fallback OK se só preenchemos expectativa
        return True, exp_t, resolved_g, None

    return True, resolved_t, resolved_g, None


def resolve_identity_with_filter(
    *,
    filter_student_id: Optional[str] = None,
    expected_test_id: Optional[str] = None,
    expected_gabarito_id: Optional[str] = None,
    detected: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Cruza filtro opcional da UI com identidade lida da imagem.

    Prioridade do aluno resolvido:
    1. Detecção (QR/ID-Grid), se houver student_id
    2. Filtro student_id, se a detecção não trouxe aluno
    3. None

    Se ambos existirem e divergirem → identity_mismatch=True e
    student_id resolvido = filtro (escolha explícita do operador).

    Documento: cartão com gabarito_id é compatível com a prova (test_id) à qual
    o gabarito está vinculado — não trate gabarito_id ≠ test_id como mismatch.
    """
    det = detected or _empty_detected()
    filt = (filter_student_id or "").strip() or None
    det_student = (det.get("student_id") or None) if det else None
    det_student = str(det_student).strip() if det_student else None

    student_mismatch = False
    if filt and det_student and filt != det_student:
        student_mismatch = True

    if student_mismatch:
        resolved_student = filt
        source = "filter+conflict"
        confidence = "low"
    elif det_student:
        resolved_student = det_student
        source = det.get("identity_source") or "detected"
        confidence = det.get("identity_confidence")
    elif filt:
        resolved_student = filt
        source = "filter"
        confidence = None
    else:
        resolved_student = None
        source = None
        confidence = None

    det_gabarito_id = (det.get("gabarito_id") or None) if det else None
    det_test_id = (det.get("test_id") or None) if det else None
    doc_ok, test_id, gabarito_id, doc_reason = _documents_compatible(
        expected_test_id=expected_test_id,
        expected_gabarito_id=expected_gabarito_id,
        det_test_id=det_test_id,
        det_gabarito_id=det_gabarito_id,
    )
    if expected_gabarito_id and not gabarito_id:
        gabarito_id = expected_gabarito_id
    if expected_test_id and not test_id:
        test_id = expected_test_id

    return {
        "student_id": resolved_student,
        "gabarito_id": gabarito_id,
        "test_id": test_id,
        "identity_source": source,
        "identity_confidence": confidence,
        "idgrid_checksum_ok": det.get("idgrid_checksum_ok") if det else None,
        "identity_mismatch": bool(
            student_mismatch or (not doc_ok) or det.get("identity_mismatch")
        ),
        "student_mismatch": student_mismatch,
        "document_mismatch": not doc_ok,
        "document_mismatch_reason": doc_reason,
        "matches_selected_document": bool(doc_ok),
        "detected_gabarito_id": det_gabarito_id,
        "detected_test_id": det_test_id,
        "filter_student_id": filt,
        "detected_student_id": det_student,
        "detected": bool(det.get("detected")),
        "filter_applied": bool(filt),
    }
