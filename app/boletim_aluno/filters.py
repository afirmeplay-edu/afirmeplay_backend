# -*- coding: utf-8 -*-
"""Opções de filtro do boletim: hierarquia padrão + alunos que fizeram a prova."""
from __future__ import annotations

from typing import Any, Dict

from app.boletim_aluno.helpers import parse_pagination
from app.participation_report.filters import (
    build_filter_options,
    is_answer_sheet_report,
    parse_id_list,
)


def _multi(args, *keys: str) -> List[str]:
    values = []
    for key in keys:
        values.append(args.get(key))
        getlist = getattr(args, "getlist", None)
        if callable(getlist):
            values.extend(getlist(key))
    return parse_id_list(*values)


def build_boletim_filter_options(user: dict, args) -> Dict[str, Any]:
    response = build_filter_options(user, args)

    municipio = (args.get("municipio") or "").strip() or None
    avaliacao_ids = _multi(args, "avaliacoes", "avaliacao", "gabaritos", "gabarito")
    if not municipio or len(avaliacao_ids) != 1:
        return response

    escola_ids = _multi(args, "escolas", "escola")
    serie_ids = _multi(args, "series", "serie")
    turma_ids = _multi(args, "turmas", "turma")
    nome = (args.get("nome") or args.get("q") or "").strip() or None
    page, per_page = parse_pagination(args.get("page"), args.get("per_page"))

    if is_answer_sheet_report(args):
        from app.boletim_aluno.answer_sheet import list_alunos_answer_sheet

        alunos_payload = list_alunos_answer_sheet(
            user=user,
            municipio_id=municipio,
            gabarito_id=avaliacao_ids[0],
            escola_ids=escola_ids or None,
            serie_ids=serie_ids or None,
            turma_ids=turma_ids or None,
            nome=nome,
            page=page,
            per_page=per_page,
        )
    else:
        from app.boletim_aluno.services import list_alunos_digital

        alunos_payload = list_alunos_digital(
            user=user,
            municipio_id=municipio,
            avaliacao_id=avaliacao_ids[0],
            escola_ids=escola_ids or None,
            serie_ids=serie_ids or None,
            turma_ids=turma_ids or None,
            nome=nome,
            page=page,
            per_page=per_page,
        )

    response["alunos"] = alunos_payload.get("alunos") or []
    response["alunos_paginacao"] = alunos_payload.get("paginacao")
    return response
