#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Diagnóstico: média de proficiência geral (resultados-agregados / estatísticas consolidadas)
usa apenas alunos cujas turmas estão em _class_ids_alunos_previstos_cartao, que para o
nível município (sem ?escola=) corresponde a _resolve_target_class_ids(gab, "city", city_id).

Se existirem answer_sheet_results de alunos cuja turma não entra nesse conjunto (ex.: turma
nova/escola criada depois e snapshots de geração desatualizados antes da correção), esses
alunos **não entram** na média geral — o script lista o desvio e compara médias.

Não altera dados.

Uso (venv ativo, raiz do projeto, DATABASE_URL em app/.env):

  python scripts/diagnose_cartao_proficiency_vs_scope.py \\
    --city-id 0f93f076-c274-4515-98df-302bbf7e9b15

  # Só um gabarito:
  python scripts/diagnose_cartao_proficiency_vs_scope.py \\
    --city-id 0f93f076-c274-4515-98df-302bbf7e9b15 \\
    --gabarito-id f634d960-7dff-4387-b17c-db3bea2aa6fa

  # Omitir tabela por escola (só resumo município):
  python scripts/diagnose_cartao_proficiency_vs_scope.py --city-id ... --no-por-escola

Nota: a média do município coincide com a **média ponderada** pelos alunos de cada escola
(Σ (média_escola_i × n_i) / Σ n_i). A **média simples** entre escolas só coincide se o peso
(nº de alunos) for igual em todas.
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app import create_app, db  # noqa: E402
from app.models.answerSheetGabarito import AnswerSheetGabarito  # noqa: E402
from app.models.answerSheetResult import AnswerSheetResult  # noqa: E402
from app.models.city import City  # noqa: E402
from app.models.school import School  # noqa: E402
from app.models.student import Student  # noqa: E402
from app.models.studentClass import Class  # noqa: E402
from app.report_analysis.answer_sheet_report_builder import (  # noqa: E402
    _resolve_target_class_ids,
    union_target_class_ids_for_gabarito,
)
from app.utils.tenant_middleware import city_id_to_schema_name  # noqa: E402


def _set_search_path(schema: str) -> None:
    db.session.execute(text(f'SET search_path TO "{schema}", public'))


def _mean_prof(rows: List[AnswerSheetResult]) -> Optional[float]:
    if not rows:
        return None
    vals = [float(r.proficiency or 0) for r in rows]
    return sum(vals) / len(vals)


def _analyze_gabarito(gab: AnswerSheetGabarito, city_id: str) -> Dict[str, Any]:
    gid = str(gab.id)
    prev_classes = set(
        _resolve_target_class_ids(gab, "city", str(city_id))
    )
    union_classes = union_target_class_ids_for_gabarito(gab)

    # Resultados cujo aluno está no município (escola.city_id)
    results = AnswerSheetResult.query.filter_by(gabarito_id=gid).all()
    in_city: List[Tuple[AnswerSheetResult, Student, Optional[Class]]] = []
    no_class: List[AnswerSheetResult] = []
    turma_row_missing: List[AnswerSheetResult] = []
    wrong_city: List[AnswerSheetResult] = []

    for r in results:
        st = Student.query.get(r.student_id)
        if not st:
            continue
        if not st.class_id:
            no_class.append(r)
            continue
        co = Class.query.get(st.class_id)
        if not co:
            turma_row_missing.append(r)
            continue
        if not co.school_id:
            no_class.append(r)
            continue
        sch = co.school
        if not sch or str(sch.city_id) != str(city_id):
            wrong_city.append(r)
            continue
        in_city.append((r, st, co))

    excluded: List[Tuple[AnswerSheetResult, str, str, str]] = []
    included: List[AnswerSheetResult] = []
    for r, st, co in in_city:
        cid = str(co.id)
        if cid not in prev_classes:
            excluded.append(
                (
                    r,
                    str(st.id),
                    cid,
                    str(co.school_id) if co.school_id else "",
                )
            )
        else:
            included.append(r)

    mean_all_city = _mean_prof([t[0] for t in in_city])
    mean_in_scope = _mean_prof(included)

    by_school_excluded: Dict[str, int] = defaultdict(int)
    for _r, _sid, _cid, school_id in excluded:
        by_school_excluded[school_id or "_sem_escola"] += 1

    # Por escola: mesma base que a média municipal (turmas previstas + aluno no município)
    by_school_results: Dict[str, List[AnswerSheetResult]] = defaultdict(list)
    for r in included:
        st = Student.query.get(r.student_id)
        if not st or not st.class_id:
            continue
        co = Class.query.get(st.class_id)
        if not co or not co.school_id:
            continue
        by_school_results[str(co.school_id)].append(r)

    por_escola: List[Dict[str, Any]] = []
    soma_ponderada = 0.0
    n_total_incl = 0
    for sid, rows in sorted(by_school_results.items(), key=lambda x: x[0]):
        n = len(rows)
        m = _mean_prof(rows)
        nome = ""
        sch = School.query.get(sid)
        if sch and sch.name:
            nome = sch.name.strip()
        por_escola.append(
            {
                "school_id": sid,
                "nome": nome or "?",
                "n_resultados": n,
                "media_proficiencia": m,
                "soma_proficiencia": sum(float(x.proficiency or 0) for x in rows),
            }
        )
        if m is not None:
            soma_ponderada += m * n
            n_total_incl += n

    media_ponderada_escolas = (
        soma_ponderada / n_total_incl if n_total_incl else None
    )
    medias_esc = [p["media_proficiencia"] for p in por_escola if p["media_proficiencia"] is not None]
    media_simples_escolas = sum(medias_esc) / len(medias_esc) if medias_esc else None

    return {
        "gabarito_id": gid,
        "title": gab.title,
        "turmas_previstas_cidade": len(prev_classes),
        "turmas_uniao_bruta": len(union_classes),
        "resultados_no_municipio": len(in_city),
        "resultados_fora_escopo_medio": len(excluded),
        "resultados_sem_turma_ou_cidade": len(no_class),
        "resultados_class_id_sem_turma_na_base": len(turma_row_missing),
        "resultados_aluno_fora_municipio": len(wrong_city),
        "media_prof_todos_alunos_municipio": mean_all_city,
        "media_prof_so_turmas_previstas": mean_in_scope,
        "excluidos_por_escola_id": dict(by_school_excluded),
        "amostra_excluidos": [
            {
                "result_id": x[0].id,
                "student_id": x[1],
                "class_id": x[2],
                "school_id": x[3],
            }
            for x in excluded[:15]
        ],
        "por_escola": por_escola,
        "media_ponderada_por_escola": media_ponderada_escolas,
        "media_simples_entre_escolas": media_simples_escolas,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compara turmas previstas (escopo) vs resultados para média de proficiência."
    )
    parser.add_argument("--city-id", required=True, help="UUID do município (tenant).")
    parser.add_argument("--gabarito-id", default=None, help="Opcional: um gabarito.")
    parser.add_argument("--schema", default=None, help="Override do nome do schema city_*.")
    parser.add_argument(
        "--no-por-escola",
        action="store_true",
        help="Não imprimir tabela por escola nem reconciliação ponderada.",
    )
    args = parser.parse_args()

    city_id = args.city_id.strip()
    schema = args.schema or city_id_to_schema_name(city_id)

    app = create_app()
    with app.app_context():
        city = City.query.get(city_id)
        if not city:
            print(f"Cidade não encontrada em public.city: {city_id}")
            return 1

        _set_search_path(schema)

        if args.gabarito_id:
            gab = AnswerSheetGabarito.query.get(args.gabarito_id.strip())
            if not gab:
                print(f"Gabarito não encontrado no schema {schema}")
                return 1
            gabaritos = [gab]
        else:
            gids = {
                row[0]
                for row in db.session.query(AnswerSheetResult.gabarito_id)
                .distinct()
                .all()
            }
            gabaritos = []
            for gid in sorted(gids, key=str):
                g = AnswerSheetGabarito.query.get(gid)
                if g:
                    gabaritos.append(g)

        print("=" * 72)
        print(f"Município: {city.name} ({city_id})")
        print(f"Schema:    {schema}")
        print(
            "Critério de inclusão na média geral (município): turma em "
            '_resolve_target_class_ids(gab, "city", city_id)'
        )
        print("=" * 72)

        any_issue = False
        for gab in gabaritos:
            rep = _analyze_gabarito(gab, city_id)
            if rep["resultados_fora_escopo_medio"]:
                any_issue = True
            print(f"\n--- {rep['title'] or '(sem título)'} [{rep['gabarito_id']}] ---")
            print(f"  Turmas no escopo previsto (cidade):     {rep['turmas_previstas_cidade']}")
            print(f"  Turmas na união bruta (gen+batch+res):   {rep['turmas_uniao_bruta']}")
            print(f"  Resultados de alunos do município:       {rep['resultados_no_municipio']}")
            print(f"  Resultados **excluídos** da média escopo:  {rep['resultados_fora_escopo_medio']}")
            if rep["resultados_sem_turma_ou_cidade"]:
                print(f"  (Aviso) Resultados sem turma/escola OK:   {rep['resultados_sem_turma_ou_cidade']}")
            if rep.get("resultados_class_id_sem_turma_na_base"):
                print(
                    f"  (Aviso) class_id do aluno sem linha em `class`: {rep['resultados_class_id_sem_turma_na_base']}"
                )
            if rep["resultados_aluno_fora_municipio"]:
                print(f"  Resultados aluno fora deste município:   {rep['resultados_aluno_fora_municipio']}")
            mp_all = rep["media_prof_todos_alunos_municipio"]
            mp_sc = rep["media_prof_so_turmas_previstas"]
            print(f"  Média proficiência (todos alunos mun.):  {mp_all if mp_all is not None else '—'}")
            print(f"  Média proficiência (só turmas previstas): {mp_sc if mp_sc is not None else '—'}")
            if not args.no_por_escola and rep.get("por_escola") is not None:
                print("  --- Por escola (turmas previstas; mesmo critério da média municipal) ---")
                for pe in rep["por_escola"]:
                    mp_e = pe["media_proficiencia"]
                    mp_e_s = f"{mp_e:.6f}" if mp_e is not None else "—"
                    nome = (pe.get("nome") or "")[:56]
                    print(
                        f"      {nome:<56}  n={pe['n_resultados']:>4}  média={mp_e_s}  id={pe['school_id']}"
                    )
                mp_pond = rep.get("media_ponderada_por_escola")
                mp_simp = rep.get("media_simples_entre_escolas")
                print(
                    f"  Média ponderada Σ(média_escola×n)/Σn: {mp_pond if mp_pond is not None else '—'}"
                )
                print(
                    f"  (Referência) média municipal (turmas prev.): {mp_sc if mp_sc is not None else '—'}"
                )
                if mp_pond is not None and mp_sc is not None:
                    delta = abs(float(mp_pond) - float(mp_sc))
                    print(f"  |ponderado − municipal|: {delta:.2e} (deve ~0)")
                print(
                    f"  Média **simples** entre escolas (só referência): "
                    f"{mp_simp if mp_simp is not None else '—'}  ← em geral ≠ municipal"
                )
            if rep["excluidos_por_escola_id"]:
                print(f"  Excluídos por school_id: {rep['excluidos_por_escola_id']}")
            if rep["amostra_excluidos"]:
                print("  Amostra excluídos (result_id, student, class, school):")
                for row in rep["amostra_excluidos"]:
                    print(f"    {row}")

        print("\n" + "=" * 72)
        if any_issue:
            print(
                "Há resultados no município que **não** entram no conjunto de turmas previstas.\n"
                "Isso altera média/disciplinas agregadas que filtram por _class_ids_alunos_previstos_cartao.\n"
                "Causas típicas: dados antigos (snapshot só última geração), turma/escola criada depois,\n"
                "ou incoerência escola↔município no cadastro."
            )
        else:
            print(
                "Nenhum resultado no município ficou fora do escopo previsto para os gabaritos analisados."
            )
        if not args.no_por_escola:
            print(
                "Lembrete: a média municipal bate com a média ponderada por escola (peso = n de resultados).\n"
                "A média aritmética **entre** escolas (sem peso) só coincide se n for igual em todas."
            )
        print("=" * 72 + "\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
