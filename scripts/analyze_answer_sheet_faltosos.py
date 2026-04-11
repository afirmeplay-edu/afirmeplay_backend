#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Análise somente leitura: alunos faltosos (sem linha em answer_sheet_results)
para o mesmo escopo da rota GET /answer-sheets/resultados-agregados.

Não altera o banco.

Como rodar (na raiz do repositório, com o venv ativado e dependências instaladas):

  cd innovaplay_backend
  .\\.venv\\Scripts\\Activate.ps1
  python scripts/analyze_answer_sheet_faltosos.py \\
    --estado ALAGOAS \\
    --municipio 0f93f076-c274-4515-98df-302bbf7e9b15 \\
    --gabarito d0148d6c-13a7-4501-bfc9-ef6a68352f1f

Opcional (igual à API): --periodo 2026-04
Opcional: --escola, --serie, --turma (mesmos filtros da URL)

Requisitos: app/.env com DATABASE_URL (ou variáveis já exportadas no shell).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Optional, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))


def _load_env() -> None:
    p = ROOT_DIR / "app" / ".env"
    if p.is_file():
        with p.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                k, v = k.strip(), v.strip().strip('"').strip("'")
                if k and k not in os.environ:
                    os.environ[k] = v


_load_env()

from app import create_app  # noqa: E402
from app.utils.tenant_middleware import city_id_to_schema_name, set_search_path  # noqa: E402
from app.routes.answer_sheet_routes import (  # noqa: E402
    _apply_answer_sheet_result_period_filter,
    _class_ids_alunos_previstos_cartao,
    _dedupe_answer_sheet_results_latest_per_student,
    _determinar_escopo_busca_cartao,
    _determinar_nivel_granularidade_cartao,
    _parse_cartao_periodo_bounds,
)
from app.models.answerSheetResult import AnswerSheetResult  # noqa: E402
from app.models.grades import Grade  # noqa: E402
from app.models.school import School  # noqa: E402
from app.models.student import Student  # noqa: E402
from app.models.studentClass import Class  # noqa: E402


def _period_bounds(periodo: Optional[str]) -> Optional[Tuple]:
    if not periodo or not str(periodo).strip():
        return None
    return _parse_cartao_periodo_bounds(str(periodo).strip())


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Lista faltosos (sem AnswerSheetResult) no escopo do cartão-resposta."
    )
    ap.add_argument("--estado", required=True, help="Ex.: ALAGOAS")
    ap.add_argument("--municipio", required=True, help="UUID do município (city_id)")
    ap.add_argument("--gabarito", required=True, help="UUID do gabarito")
    ap.add_argument("--escola", default=None, help="UUID escola (opcional)")
    ap.add_argument("--serie", default=None, help="UUID série (opcional)")
    ap.add_argument("--turma", default=None, help="UUID turma (opcional)")
    ap.add_argument(
        "--periodo",
        default=None,
        help="YYYY-MM — filtra corrected_at em answer_sheet_results (opcional)",
    )
    args = ap.parse_args()

    estado = args.estado
    municipio = args.municipio
    gabarito = args.gabarito
    escola = args.escola
    serie = args.serie
    turma = args.turma
    periodo_bounds = _period_bounds(args.periodo)

    app = create_app()
    with app.app_context():
        schema = city_id_to_schema_name(municipio)
        set_search_path(schema)

        scope_info = _determinar_escopo_busca_cartao(
            estado, municipio, escola, serie, turma, gabarito, None, periodo_bounds
        )
        if not scope_info:
            print("ERRO: não foi possível determinar o escopo (scope_info None).")
            sys.exit(1)

        nivel = _determinar_nivel_granularidade_cartao(
            estado, municipio, escola, serie, turma, gabarito
        )
        class_ids = _class_ids_alunos_previstos_cartao(
            gabarito, scope_info, nivel, None
        )

        if not class_ids:
            print("schema:", schema)
            print("nivel_granularidade:", nivel)
            print("Nenhuma turma prevista no escopo (class_ids vazio).")
            sys.exit(0)

        students = Student.query.filter(Student.class_id.in_(class_ids)).all()
        sids = [s.id for s in students]

        if not sids:
            print("total_alunos_escopo: 0")
            sys.exit(0)

        rq = AnswerSheetResult.query.filter(
            AnswerSheetResult.gabarito_id == gabarito,
            AnswerSheetResult.student_id.in_(sids),
        )
        rq = _apply_answer_sheet_result_period_filter(rq, periodo_bounds)
        results = rq.all()
        dedup = _dedupe_answer_sheet_results_latest_per_student(results)
        with_res = {str(r.student_id) for r in dedup}
        all_ids = {str(s.id) for s in students}
        faltosos_ids = sorted(all_ids - with_res)

        classes_by = {c.id: c for c in Class.query.filter(Class.id.in_(class_ids)).all()}
        schools_cache: dict = {}
        grades_cache: dict = {}

        def escola_name(sid) -> str:
            if not sid:
                return "N/A"
            if sid not in schools_cache:
                schools_cache[sid] = School.query.get(sid)
            return schools_cache[sid].name if schools_cache[sid] else str(sid)

        def serie_name(gid) -> str:
            if not gid:
                return "N/A"
            if gid not in grades_cache:
                grades_cache[gid] = Grade.query.get(gid)
            return grades_cache[gid].name if grades_cache[gid] else str(gid)

        print("schema:", schema)
        print("nivel_granularidade:", nivel)
        print("periodo_bounds:", periodo_bounds)
        print("turmas_previstas (class_ids):", len(class_ids))
        print("total_alunos_escopo:", len(students))
        print("registros_answer_sheet_result (brutos):", len(results))
        print("alunos_com_resultado_dedup:", len(with_res))
        print("FALTOSOS (sem linha de resultado no critério acima):", len(faltosos_ids))
        print("--- Lista faltosos (nome | escola | serie | turma | student_id) ---")
        for fid in faltosos_ids:
            st = next((x for x in students if str(x.id) == fid), None)
            if not st:
                continue
            co = classes_by.get(st.class_id)
            en = escola_name(co.school_id) if co else "N/A"
            sn = serie_name(co.grade_id) if co else "N/A"
            tn = (co.name or "N/A") if co else "N/A"
            print(f"- {st.name or 'N/A'} | {en} | {sn} | {tn} | {fid}")


if __name__ == "__main__":
    main()
