# -*- coding: utf-8 -*-
"""Sombra do censo de participação.

Com ``PARTICIPATION_CENSUS_SHADOW=1``, os relatórios online calculam o censo
e gravam uma linha de log. A resposta HTTP não muda. Sem a variável, esta
função retorna antes de consultar prova pareada ou matrícula.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Iterable, List, Optional, Sequence

from app.services.participation_census import (
    AlunoEntradaCenso,
    ClassTestEntrada,
    DisciplinaCenso,
    ParticipationCensusRequest,
    ProvaCenso,
    ProvaPareadaCenso,
    ResultadoEntradaCenso,
    build_participation_census,
)
from app.services.special_education import (
    SpecialEducationStatus,
    _UNLOADED,
    _loaded,
    is_special_education_many,
)

logger = logging.getLogger(__name__)

_LIGADO = {"1", "true", "yes", "on"}


def census_shadow_enabled() -> bool:
    return str(os.environ.get("PARTICIPATION_CENSUS_SHADOW", "")).strip().lower() in _LIGADO


def log_participation_census_shadow(
    *,
    superficie: str,
    municipio_id: Any,
    universo: Optional[str],
    test_ids: Sequence[Any],
    alunos: Sequence[Any],
    class_tests: Sequence[Any],
    resultados: Sequence[Any],
    antigo_matriculados: int,
    antigo_participantes: int,
    class_ids_permitidos: Optional[Iterable[Any]] = None,
    testes: Optional[Sequence[Any]] = None,
) -> None:
    """Calcula o censo e registra o comparativo. Não devolve dado para a resposta."""
    if not census_shadow_enabled():
        return
    try:
        _registrar(
            superficie=superficie,
            municipio_id=municipio_id,
            universo=universo,
            test_ids=test_ids,
            alunos=alunos,
            class_tests=class_tests,
            resultados=resultados,
            antigo_matriculados=antigo_matriculados,
            antigo_participantes=antigo_participantes,
            class_ids_permitidos=class_ids_permitidos,
            testes=testes,
        )
    except Exception as exc:
        logger.warning(
            "PARTICIPATION_CENSUS_SHADOW falhou em %s: %s",
            superficie,
            exc,
        )


def montar_censo_carregado(
    *,
    municipio_id: Any,
    universo: Optional[str],
    test_ids: Sequence[Any],
    alunos: Sequence[Any],
    class_tests: Sequence[Any],
    resultados: Sequence[Any],
    class_ids_permitidos: Optional[Iterable[Any]] = None,
    testes: Optional[Sequence[Any]] = None,
):
    """Monta o censo com os dados que o relatório já carregou."""
    ids = _ids_ordenados(test_ids)
    provas = provas_da_aplicacao(_testes_da_aplicacao(ids, testes))
    if not provas:
        return None
    alunos_entrada = _alunos_entrada(alunos, resultados)
    linhas = _completar_resultados_adap(
        _resultados_entrada(resultados),
        provas,
        alunos_entrada,
    )
    return build_participation_census(
        ParticipationCensusRequest(
            municipio_id=str(municipio_id or ""),
            provas=provas,
            universo=universo or "todos",
            alunos=alunos_entrada,
            class_tests=_class_tests_entrada(class_tests),
            resultados=linhas,
            class_ids_permitidos=(
                None
                if class_ids_permitidos is None
                else [str(item) for item in class_ids_permitidos if item]
            ),
        )
    )


def log_censo_calculado(
    censo,
    *,
    superficie: str,
    municipio_id: Any,
    universo: Optional[str],
    test_ids: Sequence[Any],
    antigo_matriculados: int,
    antigo_participantes: int,
) -> None:
    """Registra a comparação só com a flag de sombra ligada."""
    if censo is None or not census_shadow_enabled():
        return
    try:
        _log_de_censo(
            censo,
            superficie=superficie,
            municipio_id=str(municipio_id or ""),
            universo=universo or "todos",
            test_ids=_ids_ordenados(test_ids),
            antigo_matriculados=antigo_matriculados,
            antigo_participantes=antigo_participantes,
        )
    except Exception as exc:
        logger.warning(
            "PARTICIPATION_CENSUS_SHADOW falhou em %s: %s",
            superficie,
            exc,
        )


def _registrar(
    *,
    superficie: str,
    municipio_id: Any,
    universo: Optional[str],
    test_ids: Sequence[Any],
    alunos: Sequence[Any],
    class_tests: Sequence[Any],
    resultados: Sequence[Any],
    antigo_matriculados: int,
    antigo_participantes: int,
    class_ids_permitidos: Optional[Iterable[Any]],
    testes: Optional[Sequence[Any]],
) -> None:
    censo = montar_censo_carregado(
        municipio_id=municipio_id,
        universo=universo,
        test_ids=test_ids,
        alunos=alunos,
        class_tests=class_tests,
        resultados=resultados,
        class_ids_permitidos=class_ids_permitidos,
        testes=testes,
    )
    if censo is None:
        return
    _log_de_censo(
        censo,
        superficie=superficie,
        municipio_id=str(municipio_id or ""),
        universo=universo or "todos",
        test_ids=_ids_ordenados(test_ids),
        antigo_matriculados=antigo_matriculados,
        antigo_participantes=antigo_participantes,
    )


def _log_de_censo(
    censo,
    *,
    superficie: str,
    municipio_id: str,
    universo: str,
    test_ids: Sequence[str],
    antigo_matriculados: int,
    antigo_participantes: int,
) -> None:
    geral = censo.geral
    payload = {
        "superficie": superficie,
        "municipio_id": municipio_id,
        "test_ids": list(test_ids),
        "universo": universo,
        "matriculados": geral.matriculados,
        "completos": geral.presentes_completos,
        "pelo_menos_uma": geral.presentes_pelo_menos_uma,
        "ausentes": geral.ausentes,
        "inconsistentes": geral.inconsistentes,
        "historico": censo.historico,
        "percentual_completa": geral.percentual_completa,
        "percentual_pelo_menos_uma": geral.percentual_pelo_menos_uma,
        "por_disciplina": [
            {
                "id": item.disciplina_id,
                "nome": item.nome,
                "elegiveis": item.elegiveis,
                "presentes": item.presentes,
                "ausentes": item.ausentes,
                "inconsistentes": item.inconsistentes,
                "origem_regular": item.presentes_origem_regular,
                "origem_adap": item.presentes_origem_adap,
            }
            for item in geral.por_disciplina
        ],
        "antigo_matriculados": int(antigo_matriculados or 0),
        "antigo_participantes": int(antigo_participantes or 0),
    }
    logger.info(
        "PARTICIPATION_CENSUS_SHADOW %s",
        json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str),
    )


def provas_da_aplicacao(testes: Sequence[Any]) -> List[ProvaCenso]:
    """Agrupa a prova regular com as ADAP que apontam para ela."""
    from app.services.adap_resultado_pareado import (
        find_paired_adap_tests,
        parse_adap_level_from_title,
    )

    slots: dict = {}
    ordem: List[str] = []

    def slot_de(regular_id: str) -> dict:
        if regular_id not in slots:
            slots[regular_id] = {"disciplinas": (), "adap": {}}
            ordem.append(regular_id)
        return slots[regular_id]

    for test in testes or []:
        test_id = str(getattr(test, "id", "") or "")
        if not test_id:
            continue
        pai = getattr(test, "paired_regular_test_id", None)
        if pai:
            atual = slot_de(str(pai))
            atual["adap"][test_id] = parse_adap_level_from_title(getattr(test, "title", None))
            if not atual["disciplinas"]:
                atual["disciplinas"] = disciplinas_de_prova(test)
            continue
        atual = slot_de(test_id)
        atual["disciplinas"] = disciplinas_de_prova(test)
        for paired in find_paired_adap_tests(test_id):
            paired_id = str(getattr(paired, "id", "") or "")
            if not paired_id:
                continue
            atual["adap"][paired_id] = parse_adap_level_from_title(getattr(paired, "title", None))

    provas: List[ProvaCenso] = []
    for regular_id in ordem:
        atual = slots[regular_id]
        provas.append(
            ProvaCenso(
                test_id=regular_id,
                disciplinas=tuple(atual["disciplinas"]),
                provas_adap=tuple(
                    ProvaPareadaCenso(adap_id, nivel)
                    for adap_id, nivel in atual["adap"].items()
                ),
            )
        )
    return provas


def disciplinas_de_prova(test: Any) -> tuple:
    encontradas: List[DisciplinaCenso] = []
    raw = getattr(test, "subjects_info", None)
    if isinstance(raw, dict):
        for nome, info in raw.items():
            disc_id = str(nome)
            if isinstance(info, dict):
                disc_id = str(info.get("id") or info.get("subject_id") or nome)
            encontradas.append(DisciplinaCenso(disc_id, str(nome)))
    elif isinstance(raw, list):
        for item in raw:
            if item is None:
                continue
            if isinstance(item, dict):
                disc_id = str(item.get("id") or item.get("subject_id") or "")
                nome = str(item.get("name") or item.get("nome") or disc_id)
            else:
                disc_id = nome = str(item)
            if disc_id:
                encontradas.append(DisciplinaCenso(disc_id, nome))
    rel = getattr(test, "subject_rel", None)
    nome_rel = getattr(rel, "name", None) if rel is not None else None
    if not encontradas:
        subject = getattr(test, "subject", None)
        if subject or nome_rel:
            encontradas.append(DisciplinaCenso(str(subject or nome_rel), str(nome_rel or subject)))
    if not encontradas:
        test_id = str(getattr(test, "id", "") or "prova")
        encontradas.append(DisciplinaCenso(test_id, str(getattr(test, "title", None) or test_id)))
    unicas: List[DisciplinaCenso] = []
    vistos = set()
    for disciplina in encontradas:
        if disciplina.id in vistos:
            continue
        vistos.add(disciplina.id)
        unicas.append(disciplina)
    if nome_rel and len(unicas) == 1:
        unicas = [DisciplinaCenso(unicas[0].id, str(nome_rel))]
    return tuple(unicas)


def _testes_da_aplicacao(test_ids: Sequence[str], testes: Optional[Sequence[Any]]) -> List[Any]:
    por_id = {}
    for test in testes or []:
        test_id = str(getattr(test, "id", "") or "")
        if test_id:
            por_id[test_id] = test
    faltantes = [test_id for test_id in test_ids if test_id not in por_id]
    if faltantes:
        from app.models.test import Test

        for test in Test.query.filter(Test.id.in_(faltantes)).all():
            por_id[str(test.id)] = test
    return [por_id[test_id] for test_id in test_ids if test_id in por_id]


def _completar_resultados_adap(
    linhas: Sequence[ResultadoEntradaCenso],
    provas: Sequence[ProvaCenso],
    alunos: Sequence[AlunoEntradaCenso],
) -> List[ResultadoEntradaCenso]:
    """Inclui a prova ADAP pareada quando o relatório só carregou a regular."""
    paired_ids = []
    for prova in provas or []:
        for par in prova.provas_adap or []:
            if par.test_id:
                paired_ids.append(str(par.test_id))
    student_ids = [aluno.student_id for aluno in alunos or [] if aluno.student_id]
    if not paired_ids or not student_ids:
        return list(linhas or [])
    ja_tem = {(row.student_id, row.test_id) for row in linhas or []}
    extras: List[ResultadoEntradaCenso] = []
    try:
        from app.models.evaluationResult import EvaluationResult

        rows = (
            EvaluationResult.query.filter(
                EvaluationResult.test_id.in_(paired_ids),
                EvaluationResult.student_id.in_(student_ids),
            ).all()
        )
        for row in rows:
            sid = str(getattr(row, "student_id", "") or "")
            tid = str(getattr(row, "test_id", "") or "")
            if not sid or not tid or (sid, tid) in ja_tem:
                continue
            ja_tem.add((sid, tid))
            extras.append(
                ResultadoEntradaCenso(
                    student_id=sid,
                    test_id=tid,
                    calculated_at=getattr(row, "calculated_at", None),
                    class_id_snapshot=(
                        str(row.class_id_snapshot)
                        if getattr(row, "class_id_snapshot", None)
                        else None
                    ),
                )
            )
    except Exception as exc:
        logger.warning("Censo: falha ao completar resultados ADAP: %s", exc)
    return list(linhas or []) + extras


def _alunos_entrada(alunos: Sequence[Any], resultados: Sequence[Any]) -> List[AlunoEntradaCenso]:
    statuses = is_special_education_many(alunos or [])
    entradas: List[AlunoEntradaCenso] = []
    vistos = set()
    for student in alunos or []:
        sid = str(getattr(student, "id", "") or "")
        if not sid or sid in vistos:
            continue
        vistos.add(sid)
        status = statuses.get(sid) or SpecialEducationStatus(False, None, None)
        escola_id, serie_id, turma_id = _colocacao(student)
        entradas.append(
            AlunoEntradaCenso(
                student_id=sid,
                escola_id=escola_id,
                serie_id=serie_id,
                turma_id=turma_id,
                is_special=bool(status.is_special),
                nivel_adap=status.level if status.is_special else None,
            )
        )
    for row in resultados or []:
        sid = str(getattr(row, "student_id", "") or "")
        if not sid or sid in vistos:
            continue
        vistos.add(sid)
        entradas.append(AlunoEntradaCenso(student_id=sid, turma_id=None))
    return entradas


def _colocacao(student: Any):
    classe = _loaded(student, "class_")
    if classe is _UNLOADED:
        classe = None
    escola_id = getattr(classe, "school_id", None) if classe is not None else None
    serie_id = getattr(classe, "grade_id", None) if classe is not None else None
    if serie_id is None:
        serie_id = getattr(student, "grade_id", None)
    turma_id = getattr(student, "class_id", None)
    return (
        str(escola_id) if escola_id else None,
        str(serie_id) if serie_id is not None else None,
        str(turma_id) if turma_id else None,
    )


def _class_tests_entrada(class_tests: Sequence[Any]) -> List[ClassTestEntrada]:
    entradas = []
    for link in class_tests or []:
        class_id = getattr(link, "class_id", None)
        test_id = getattr(link, "test_id", None)
        if class_id is None or not test_id:
            continue
        entradas.append(ClassTestEntrada(str(class_id), str(test_id)))
    return entradas


def _resultados_entrada(resultados: Sequence[Any]) -> List[ResultadoEntradaCenso]:
    entradas = []
    for row in resultados or []:
        sid = getattr(row, "student_id", None)
        test_id = getattr(row, "test_id", None)
        if not sid or not test_id:
            continue
        entradas.append(
            ResultadoEntradaCenso(
                student_id=str(sid),
                test_id=str(test_id),
                calculated_at=getattr(row, "calculated_at", None),
                class_id_snapshot=(
                    str(row.class_id_snapshot) if getattr(row, "class_id_snapshot", None) else None
                ),
            )
        )
    return entradas


def _ids_ordenados(test_ids: Sequence[Any]) -> List[str]:
    ids: List[str] = []
    vistos = set()
    for test_id in test_ids or []:
        texto = str(test_id or "")
        if not texto or texto in vistos:
            continue
        vistos.add(texto)
        ids.append(texto)
    return ids
