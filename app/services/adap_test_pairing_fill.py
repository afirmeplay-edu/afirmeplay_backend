# -*- coding: utf-8 -*-
"""Preenche ``test.paired_regular_test_id`` pela regra de título (simulação por padrão)."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.services.adap_resultado_pareado import (
    extract_pairing_key,
    fold_title,
    is_adap_test_title,
    parse_adap_level_from_title,
)

logger = logging.getLogger(__name__)


@dataclass
class PairProposal:
    adap_id: str
    adap_title: str
    adap_level: Optional[int]
    status: str  # par_unico | mais_de_um | nenhum
    candidate_ids: List[str] = field(default_factory=list)
    candidate_titles: List[str] = field(default_factory=list)
    already_paired: bool = False
    will_write: bool = False


def propose_pairs(
    adap_tests: Sequence[Any],
    regular_tests: Sequence[Any],
) -> List[PairProposal]:
    """Propõe pares ADAP → regular sem gravar."""
    regular_by_key: Dict[Tuple, List[Any]] = {}
    for test in regular_tests:
        title = getattr(test, "title", None)
        if is_adap_test_title(title):
            continue
        key = extract_pairing_key(title)
        if key is None:
            continue
        regular_by_key.setdefault(key, []).append(test)

    proposals: List[PairProposal] = []
    for adap in adap_tests:
        title = getattr(adap, "title", None) or ""
        if not is_adap_test_title(title):
            continue
        key = extract_pairing_key(title)
        already = bool(getattr(adap, "paired_regular_test_id", None))
        level = parse_adap_level_from_title(title)
        if key is None:
            proposals.append(
                PairProposal(
                    adap_id=str(adap.id),
                    adap_title=title,
                    adap_level=level,
                    status="nenhum",
                    already_paired=already,
                )
            )
            continue
        candidates = regular_by_key.get(key) or []
        # Fallback: mesmo ano+avaliação+disciplina pelo título normalizado parcial
        if not candidates and key[0] is not None:
            ano, disc, av, _norm = key
            for rkey, tests in regular_by_key.items():
                if rkey[0] == ano and rkey[1] == disc and rkey[2] == av:
                    candidates.extend(tests)
            # dedupe
            seen = set()
            uniq = []
            for t in candidates:
                tid = str(t.id)
                if tid not in seen:
                    seen.add(tid)
                    uniq.append(t)
            candidates = uniq

        if len(candidates) == 1:
            status = "par_unico"
        elif len(candidates) > 1:
            status = "mais_de_um"
        else:
            status = "nenhum"
        proposals.append(
            PairProposal(
                adap_id=str(adap.id),
                adap_title=title,
                adap_level=level,
                status=status,
                candidate_ids=[str(c.id) for c in candidates],
                candidate_titles=[getattr(c, "title", "") or "" for c in candidates],
                already_paired=already,
                will_write=False,
            )
        )
    return proposals


def apply_unique_pairs(
    proposals: Sequence[PairProposal],
    adap_by_id: Dict[str, Any],
    *,
    commit: bool,
) -> List[PairProposal]:
    """
    Grava só ``par_unico`` ainda sem vínculo. ``commit=False`` = simulação.
    """
    updated: List[PairProposal] = []
    for prop in proposals:
        item = PairProposal(
            adap_id=prop.adap_id,
            adap_title=prop.adap_title,
            adap_level=prop.adap_level,
            status=prop.status,
            candidate_ids=list(prop.candidate_ids),
            candidate_titles=list(prop.candidate_titles),
            already_paired=prop.already_paired,
            will_write=False,
        )
        if (
            commit
            and prop.status == "par_unico"
            and not prop.already_paired
            and prop.candidate_ids
        ):
            adap = adap_by_id.get(prop.adap_id)
            if adap is not None:
                adap.paired_regular_test_id = prop.candidate_ids[0]
                item.will_write = True
        elif (
            not commit
            and prop.status == "par_unico"
            and not prop.already_paired
            and prop.candidate_ids
        ):
            item.will_write = True  # seria gravado
        updated.append(item)
    return updated


def run_pairing_for_schema(
    *,
    schema: str,
    write: bool = False,
) -> Dict[str, Any]:
    """
    Executa no schema tenant atual (search_path / translate_map já configurados).

    Por padrão só simula. ``write=True`` grava pares únicos novos.
    """
    from app import db
    from app.models.test import Test

    if not schema or not str(schema).startswith("city_"):
        raise ValueError("Informe um schema city_… (um município por vez).")

    all_tests = Test.query.all()
    adap_tests = [t for t in all_tests if is_adap_test_title(getattr(t, "title", None))]
    regular_tests = [
        t for t in all_tests if not is_adap_test_title(getattr(t, "title", None))
    ]
    proposals = propose_pairs(adap_tests, regular_tests)
    adap_by_id = {str(t.id): t for t in adap_tests}
    applied = apply_unique_pairs(proposals, adap_by_id, commit=write)
    if write:
        db.session.commit()
        logger.info(
            "Pareamento ADAP gravado em %s: %s pares",
            schema,
            sum(1 for p in applied if p.will_write and p.status == "par_unico"),
        )
    else:
        db.session.rollback()

    summary = {
        "schema": schema,
        "write": write,
        "par_unico": sum(1 for p in applied if p.status == "par_unico"),
        "mais_de_um": sum(1 for p in applied if p.status == "mais_de_um"),
        "nenhum": sum(1 for p in applied if p.status == "nenhum"),
        "ja_vinculados": sum(1 for p in applied if p.already_paired),
        "gravados_ou_a_gravar": sum(1 for p in applied if p.will_write),
        "propostas": [
            {
                "adap_id": p.adap_id,
                "adap_title": p.adap_title,
                "adap_level": p.adap_level,
                "status": p.status,
                "candidates": list(zip(p.candidate_ids, p.candidate_titles)),
                "already_paired": p.already_paired,
                "will_write": p.will_write,
            }
            for p in applied
        ],
    }
    return summary
