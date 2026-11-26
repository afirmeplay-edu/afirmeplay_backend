# -*- coding: utf-8 -*-
"""
Fachada única de leitura de resultados (ResultadoEscopo).

Coordena módulos canônicos existentes — não recalcula fórmulas próprias:
- universo/snapshot: evaluation_result_snapshot / answer_sheet_result_snapshot
- filtro ADAP: alunos_resultado_filtro + adap_resultado_pareado
- agregação: school_equal_weight_means (Regra B)
- participação: participation_census
- curso: contexto_avaliacao
- classificação/nota individual: EvaluationCalculator

Feature flags:
- RESULTADO_ESCOPO_USE=1 → consumidores devem preferir esta fachada
- RESULTADO_ESCOPO_SHADOW=1 → loga divergências sem trocar a resposta
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence

from app.services.contexto_avaliacao import resolve_contexto_avaliacao
from app.services.resultado_escopo_types import (
    ResultadoEscopoContexto,
    ResultadoEscopoIndicadores,
    ResultadoEscopoParticipacao,
    ResultadoEscopoPayload,
    ResultadoEscopoUniverso,
)
from app.utils.decimal_helpers import round_to_two_decimals
from app.utils.school_equal_weight_means import (
    granularidade_to_hierarchical_target,
    hierarchical_mean_grade_and_proficiency,
)

logger = logging.getLogger(__name__)

REGRA_CALCULO = "regra_b_v1"


def use_resultado_escopo() -> bool:
    return os.environ.get("RESULTADO_ESCOPO_USE", "").strip() in {"1", "true", "True", "yes"}


def shadow_resultado_escopo() -> bool:
    return os.environ.get("RESULTADO_ESCOPO_SHADOW", "").strip() in {
        "1",
        "true",
        "True",
        "yes",
    }


def _dedupe_by_student_instrument(
    rows: Sequence[Any],
    *,
    instrument_attr: str,
    ts_attr: str,
) -> List[Any]:
    best: Dict[tuple, Any] = {}
    for row in rows or []:
        sid = str(getattr(row, "student_id", "") or "")
        iid = str(getattr(row, instrument_attr, "") or "")
        if not sid:
            continue
        key = (sid, iid)
        prev = best.get(key)
        if prev is None:
            best[key] = row
            continue
        ts = getattr(row, ts_attr, None)
        pts = getattr(prev, ts_attr, None)
        if ts and (pts is None or ts >= pts):
            best[key] = row
        elif ts is None and pts is None:
            # Empate sem timestamp: mantém o de id maior se existir.
            rid = str(getattr(row, "id", "") or "")
            pid = str(getattr(prev, "id", "") or "")
            if rid > pid:
                best[key] = row
    return list(best.values())


def _class_ids_for_tests(test_ids: Sequence[str]) -> List[Any]:
    from app.models.classTest import ClassTest

    if not test_ids:
        return []
    rows = ClassTest.query.filter(ClassTest.test_id.in_(list(test_ids))).all()
    return [r.class_id for r in rows if getattr(r, "class_id", None)]


def _load_online_universe(
    test_ids: List[str],
    *,
    alunos_filtro: str,
    school_ids: Optional[Iterable[Any]] = None,
    class_ids: Optional[Iterable[Any]] = None,
    municipio_id: Any = None,
    parear: bool = True,
):
    from app.services.resultado_universo import carregar_universo_das_provas

    return carregar_universo_das_provas(
        test_ids,
        municipio_id=municipio_id,
        alunos_filtro=alunos_filtro,
        parear=parear,
        class_ids=class_ids,
        school_ids=school_ids,
    )


def carregar(
    test_ids: Sequence[Any],
    *,
    escopo: Optional[Dict[str, Any]] = None,
    alunos: str = "todos",
    modalidade: str = "online",
    target_level: Optional[str] = None,
) -> ResultadoEscopoPayload:
    """
    Carrega universo, resultados válidos, indicadores e participação do escopo.

    ``escopo`` aceita: school_id, class_id, serie_id, municipio_id, class_ids, school_ids.
    """
    escopo = dict(escopo or {})
    ids = [str(t) for t in (test_ids or []) if t]
    filtro = (alunos or "todos").strip().lower() or "todos"
    nivel = granularidade_to_hierarchical_target(
        target_level or escopo.get("nivel") or escopo.get("target_level") or "municipio"
    )

    school_id = escopo.get("school_id")
    class_id = escopo.get("class_id")
    serie_id = escopo.get("serie_id")
    municipio_id = escopo.get("municipio_id") or escopo.get("city_id")
    school_ids = escopo.get("school_ids")
    class_ids = escopo.get("class_ids")

    if class_id and not class_ids:
        class_ids = [class_id]
    if school_id and not school_ids:
        school_ids = [school_id]

    # Sem ClassTest → avaliação não aplicada.
    applied_class_ids = _class_ids_for_tests(ids)
    if class_ids is not None:
        allow = {str(c) for c in class_ids if c}
        applied_class_ids = [c for c in applied_class_ids if str(c) in allow]

    status_aplicacao = "aplicada" if applied_class_ids else "nao_aplicada"

    students: List[Any] = []
    results: List[Any] = []
    censo = None

    if modalidade == "online" and ids:
        students, results, censo = _load_online_universe(
            ids,
            alunos_filtro=filtro,
            school_ids=school_ids,
            class_ids=class_ids or applied_class_ids,
            municipio_id=municipio_id,
            parear=True,
        )
        results = _dedupe_by_student_instrument(
            results, instrument_attr="test_id", ts_attr="calculated_at"
        )
    elif modalidade == "cartao":
        # Cartão: consumidores passam results/students já filtrados via escopo["_preloaded"].
        pre = escopo.get("_preloaded") or {}
        students = list(pre.get("students") or [])
        results = _dedupe_by_student_instrument(
            list(pre.get("results") or []),
            instrument_attr="gabarito_id",
            ts_attr="corrected_at",
        )
        censo = pre.get("censo")

    # Filtrar alunos ativos no roster atual (histórico com resultado permanece via results).
    active_students = []
    for st in students:
        if st is None:
            continue
        if getattr(st, "is_active", True) is False and str(
            getattr(st, "id", "")
        ) not in {str(getattr(r, "student_id", "")) for r in results}:
            continue
        active_students.append(st)

    course_name, has_matematica = resolve_contexto_avaliacao(ids, results=results)

    contexto = ResultadoEscopoContexto(
        test_ids=ids,
        school_id=str(school_id) if school_id else None,
        class_id=str(class_id) if class_id else None,
        serie_id=str(serie_id) if serie_id else None,
        municipio_id=str(municipio_id) if municipio_id else None,
        course_name=course_name,
        has_matematica=has_matematica,
        modalidade=modalidade,
        filtro_alunos=filtro,
        target_level=nivel,
    )

    student_ids = [str(getattr(s, "id", "")) for s in active_students if getattr(s, "id", None)]
    avaliados_ids = list(
        {
            str(getattr(r, "student_id", ""))
            for r in results
            if getattr(r, "student_id", None) is not None
            and getattr(r, "proficiency", None) is not None
        }
    )

    matriculados = len(student_ids)
    avaliados = len(avaliados_ids)
    faltantes = max(0, matriculados - avaliados)

    if censo is not None:
        try:
            from app.services.participation_census import campos_participacao

            grupo = len(ids) > 1
            campos = campos_participacao(censo, grupo=grupo)
            matriculados = int(campos.get("total_alunos") or matriculados)
            avaliados = int(
                campos.get("alunos_participantes")
                or campos.get("alunos_completos")
                or avaliados
            )
            faltantes = int(campos.get("alunos_pendentes") or max(0, matriculados - avaliados))
            percentual = float(campos.get("percentual_comparecimento") or 0.0)
        except Exception as exc:
            logger.warning("ResultadoEscopo: falha ao ler censo: %s", exc)
            percentual = (
                round_to_two_decimals(100.0 * avaliados / matriculados)
                if matriculados
                else 0.0
            )
    else:
        percentual = (
            round_to_two_decimals(100.0 * avaliados / matriculados) if matriculados else 0.0
        )

    if status_aplicacao == "nao_aplicada":
        percentual = 0.0
        # Não confundir com 0% de aplicação real: status explícito.
        matriculados = 0
        avaliados = 0
        faltantes = 0

    universo = ResultadoEscopoUniverso(
        matriculados=matriculados,
        alunos_elegiveis=matriculados,
        alunos_historicos=0,
        avaliados=avaliados,
        faltantes=faltantes,
        ausentes=faltantes,
        pendentes=faltantes,
        inconsistentes=0,
        student_ids=student_ids,
        avaliados_ids=avaliados_ids,
        status_aplicacao=status_aplicacao,
    )

    # Indicadores: só resultados com proficiência válida.
    valid_results = [
        r for r in results if getattr(r, "proficiency", None) is not None
    ]
    if valid_results and status_aplicacao == "aplicada":
        nota, prof = hierarchical_mean_grade_and_proficiency(
            valid_results,
            nivel,
            course_name=course_name,
            subject_name="GERAL",
            has_matematica=has_matematica,
        )
        from app.services.evaluation_calculator import EvaluationCalculator

        classificacao = EvaluationCalculator.determine_classification(
            float(prof),
            course_name,
            "GERAL",
            has_matematica=has_matematica,
        )
    else:
        nota, prof, classificacao = 0.0, 0.0, None

    indicadores = ResultadoEscopoIndicadores(
        proficiencia_media=round_to_two_decimals(prof),
        nota=round_to_two_decimals(nota),
        classificacao=classificacao,
    )
    participacao = ResultadoEscopoParticipacao(
        matriculados=matriculados,
        avaliados=avaliados,
        percentual=percentual if status_aplicacao == "aplicada" else 0.0,
        status_aplicacao=status_aplicacao,
    )

    versao_roster = f"{len(student_ids)}:{len(avaliados_ids)}:{filtro}:{modalidade}"
    metadados = {
        "regra_calculo": REGRA_CALCULO,
        "versao_roster": versao_roster,
        "gerado_em": datetime.utcnow().isoformat() + "Z",
        "course_name": course_name,
        "has_matematica": has_matematica,
    }

    return ResultadoEscopoPayload(
        contexto=contexto,
        universo=universo,
        resultados=valid_results,
        indicadores=indicadores,
        participacao=participacao,
        hierarquia={},
        metadados=metadados,
    )


def indicadores_do_escopo(
    test_ids: Sequence[Any],
    *,
    escopo: Optional[Dict[str, Any]] = None,
    alunos: str = "todos",
    modalidade: str = "online",
    target_level: Optional[str] = None,
    label: str = "consumidor",
    legado: Optional[Dict[str, Any]] = None,
) -> Optional[ResultadoEscopoPayload]:
    """
    Helper para consumidores: carrega a fachada, loga sombra e devolve o payload.

    Com ``RESULTADO_ESCOPO_USE=1`` (ou sempre no piloto) o chamador deve
    preferir os números deste payload. Em falha devolve ``None``.
    """
    try:
        payload = carregar(
            test_ids,
            escopo=escopo,
            alunos=alunos,
            modalidade=modalidade,
            target_level=target_level,
        )
        if legado:
            log_shadow_divergencia(label, legado, payload)
        return payload
    except Exception as exc:
        logger.warning("ResultadoEscopo indicadores_do_escopo (%s): %s", label, exc)
        return None


def log_shadow_divergencia(
    label: str,
    antigo: Dict[str, Any],
    novo: ResultadoEscopoPayload,
) -> None:
    """Compara valores centrais no modo sombra (não altera resposta)."""
    if not shadow_resultado_escopo():
        return
    try:
        payload = novo.to_dict()
        diffs = []
        for key in ("nota", "proficiencia_media", "classificacao"):
            a = antigo.get(key)
            b = payload["indicadores"].get(
                "nota"
                if key == "nota"
                else ("proficiencia_media" if key == "proficiencia_media" else "classificacao")
            )
            if a is not None and b is not None and a != b:
                diffs.append(f"{key}: antigo={a} novo={b}")
        for key in ("matriculados", "avaliados", "percentual"):
            a = antigo.get(key)
            b = payload["participacao"].get(key)
            if a is not None and b is not None and a != b:
                diffs.append(f"part.{key}: antigo={a} novo={b}")
        if diffs:
            logger.warning("RESULTADO_ESCOPO_SHADOW %s | %s", label, "; ".join(diffs))
    except Exception as exc:
        logger.warning("RESULTADO_ESCOPO_SHADOW falhou (%s): %s", label, exc)
