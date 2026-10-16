# -*- coding: utf-8 -*-
"""
Relatório Comparativo (prova digital) — somente leitura.

Reutiliza o motor de Resultados apenas IMPORTANDO e CHAMANDO funções existentes,
sem alterar assinaturas nem comportamento. Estruturado para permitir cartão-resposta
no futuro (report_entity_type), sem implementar cartão nesta versão.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence, Set

from sqlalchemy import String, cast
from sqlalchemy.orm import joinedload

from app.models.city import City
from app.models.classTest import ClassTest
from app.models.grades import Grade
from app.models.school import School
from app.models.studentClass import Class
from app.models.test import Test
from app.services.alunos_resultado_filtro import (
    ALUNOS_FILTROS,
    AlunosFiltroInvalido,
    parse_alunos_filtro,
)
from app.utils.tenant_middleware import city_id_to_schema_name, set_search_path

logger = logging.getLogger(__name__)

INDICADORES_VALIDOS = (
    "participacao",
    "proficiencia_media",
    "distribuicao_niveis",
    "alunos_avaliados",
    "aplicacoes",
)

# Espaço reservado para extensão futura (cartão-resposta).
SUPPORTED_ENTITY_TYPES = ("evaluation",)


class ComparativeReportError(ValueError):
    """Erro de validação de negócio do relatório comparativo."""


def _norm_optional(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() == "all":
        return None
    return text


def _is_valid_filter(value: Optional[str]) -> bool:
    return bool(value) and str(value).lower() != "all"


def build_filter_options(
    user: dict,
    *,
    estado: Optional[str] = None,
    municipio: Optional[str] = None,
    avaliacao: Optional[str] = None,
    evaluation_ids: Optional[Sequence[str]] = None,
    escola: Optional[str] = None,
    serie: Optional[str] = None,
    nome: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Espelha GET /evaluation-results/opcoes-filtros (digital), com suporte a
    múltiplas avaliações (união de escolas/séries/turmas).
    """
    from app.routes.evaluation_results_routes import (
        _escola_param_eh_especifica,
        _obter_avaliacoes_por_municipio,
        _obter_escolas_por_avaliacao,
        _obter_estados_disponiveis,
        _obter_municipios_por_estado,
        _obter_series_por_avaliacao_municipio,
        _obter_series_por_escola,
        _obter_series_com_aplicacoes_municipio,
        _obter_turmas_por_serie,
        _obter_turmas_por_serie_municipio,
        _periodo_bounds_dados_digital,
        _serie_param_eh_especifica,
        verificar_permissao_filtros,
    )

    permissao = verificar_permissao_filtros(user)
    if not permissao.get("permitted"):
        raise PermissionError(permissao.get("error") or "Sem permissão para filtros")

    response: Dict[str, Any] = {
        "estados": _obter_estados_disponiveis(user, permissao),
        "report_entity_type": "evaluation",
    }

    estado_n = _norm_optional(estado)
    municipio_n = _norm_optional(municipio)
    if not estado_n:
        return response

    response["municipios"] = _obter_municipios_por_estado(estado_n, user, permissao)
    if not municipio_n:
        return response

    set_search_path(city_id_to_schema_name(str(municipio_n)))

    response["avaliacoes"] = _obter_avaliacoes_por_municipio(
        municipio_n,
        user,
        permissao,
        "all",
        None,
        serie_id=None,
        nome=nome,
    )
    response["series_disponiveis"] = _obter_series_com_aplicacoes_municipio(
        municipio_n,
        user,
        permissao,
        "all",
        None,
    )

    ids = [str(x).strip() for x in (evaluation_ids or []) if str(x).strip()]
    avaliacao_n = _norm_optional(avaliacao)
    if avaliacao_n and avaliacao_n not in ids:
        ids = [avaliacao_n] + ids

    if not ids:
        return response

    periodo_bounds_escopo = _periodo_bounds_dados_digital()
    escolas_by_id: Dict[str, Dict[str, Any]] = {}
    for eid in ids:
        for row in _obter_escolas_por_avaliacao(
            eid, municipio_n, user, permissao, periodo_bounds_escopo
        ):
            rid = str(row.get("id") or "")
            if rid and rid not in escolas_by_id:
                escolas_by_id[rid] = row
    response["escolas"] = sorted(
        escolas_by_id.values(),
        key=lambda r: (str(r.get("nome") or r.get("name") or "").lower(), str(r.get("id"))),
    )

    escola_n = _norm_optional(escola)
    serie_n = _norm_optional(serie)
    primary = ids[0]

    if _escola_param_eh_especifica(escola_n):
        series_by_id: Dict[str, Dict[str, Any]] = {}
        for eid in ids:
            for row in _obter_series_por_escola(
                eid, escola_n, municipio_n, user, permissao, periodo_bounds_escopo
            ):
                rid = str(row.get("id") or "")
                if rid and rid not in series_by_id:
                    series_by_id[rid] = row
        response["series"] = sorted(
            series_by_id.values(),
            key=lambda r: (str(r.get("nome") or r.get("name") or "").lower(), str(r.get("id"))),
        )
        if _serie_param_eh_especifica(serie_n):
            turmas_by_id: Dict[str, Dict[str, Any]] = {}
            for eid in ids:
                for row in _obter_turmas_por_serie(
                    eid,
                    escola_n,
                    serie_n,
                    municipio_n,
                    user,
                    permissao,
                    periodo_bounds_escopo,
                ):
                    rid = str(row.get("id") or "")
                    if rid and rid not in turmas_by_id:
                        turmas_by_id[rid] = row
            response["turmas"] = list(turmas_by_id.values())
    else:
        series_by_id = {}
        for eid in ids:
            for row in _obter_series_por_avaliacao_municipio(
                eid, municipio_n, user, permissao, periodo_bounds_escopo
            ):
                rid = str(row.get("id") or "")
                if rid and rid not in series_by_id:
                    series_by_id[rid] = row
        response["series"] = sorted(
            series_by_id.values(),
            key=lambda r: (str(r.get("nome") or r.get("name") or "").lower(), str(r.get("id"))),
        )
        if _serie_param_eh_especifica(serie_n):
            turmas_by_id = {}
            for eid in ids:
                for row in _obter_turmas_por_serie_municipio(
                    eid, serie_n, municipio_n, user, permissao, periodo_bounds_escopo
                ):
                    rid = str(row.get("id") or "")
                    if rid and rid not in turmas_by_id:
                        turmas_by_id[rid] = row
            response["turmas"] = list(turmas_by_id.values())

    # Mantém referência à avaliação usada no cascade (primeira)
    response["avaliacao_referencia"] = primary
    return response


def _fetch_class_tests_for_evaluation(
    evaluation_id: str,
    municipio_id: str,
    *,
    escola: Optional[str] = None,
    serie: Optional[str] = None,
    turma: Optional[str] = None,
) -> List[ClassTest]:
    """ClassTests da avaliação no município, com recorte opcional (igual Resultados)."""
    from app.utils.uuid_helpers import ensure_uuid, uuid_to_str

    query = (
        ClassTest.query.join(Test, ClassTest.test_id == Test.id)
        .join(Class, ClassTest.class_id == Class.id)
        .join(Grade, Class.grade_id == Grade.id)
        .join(School, School.id == cast(Class.school_id, String))
        .join(City, School.city_id == City.id)
        .options(
            joinedload(ClassTest.test).joinedload(Test.subject_rel),
            joinedload(ClassTest.class_).joinedload(Class.grade),
        )
        .filter(Test.id == str(evaluation_id))
        .filter(City.id == str(municipio_id))
    )

    if _is_valid_filter(escola):
        escola_str = uuid_to_str(escola)
        school_filter = (
            School.query.filter(School.id == escola_str).first() if escola_str else None
        )
        if school_filter:
            query = query.filter(School.id == escola)
        else:
            query = query.filter(School.name.ilike(f"%{escola}%"))

    if _is_valid_filter(serie):
        serie_uuid = ensure_uuid(serie)
        if serie_uuid:
            grade_filter = Grade.query.get(serie_uuid)
            if grade_filter:
                query = query.filter(Grade.id == serie_uuid)
            else:
                query = query.filter(Grade.name.ilike(f"%{serie}%"))
        else:
            query = query.filter(Grade.name.ilike(f"%{serie}%"))

    if _is_valid_filter(turma):
        turma_uuid = ensure_uuid(turma)
        if turma_uuid:
            class_filter = Class.query.get(turma_uuid)
            if class_filter:
                query = query.filter(Class.id == turma_uuid)
            else:
                query = query.filter(Class.name.ilike(f"%{turma}%"))
        else:
            query = query.filter(Class.name.ilike(f"%{turma}%"))

    return query.all()


def _distribuicao_com_percentuais(dist: Dict[str, Any], total: int) -> Dict[str, Any]:
    keys = ("abaixo_do_basico", "basico", "adequado", "avancado")
    out: Dict[str, Any] = {"quantidades": {}, "percentuais": {}}
    for key in keys:
        qtd = int((dist or {}).get(key) or 0)
        out["quantidades"][key] = qtd
        out["percentuais"][key] = (
            round(100.0 * qtd / total, 2) if total > 0 else 0.0
        )
    return out


def _slice_indicators(
    stats: Dict[str, Any],
    por_disciplina: List[Dict[str, Any]],
    aplicacoes: int,
    indicadores: Sequence[str],
) -> Dict[str, Any]:
    wanted = set(indicadores)
    block: Dict[str, Any] = {}

    esperados = int(stats.get("total_alunos") or 0)
    avaliados = int(stats.get("alunos_participantes") or 0)
    pct = stats.get("percentual_comparecimento")
    if pct is None:
        pct = round(100.0 * avaliados / esperados, 2) if esperados else 0.0

    if "participacao" in wanted:
        block["participacao"] = {
            "esperados": esperados,
            "avaliados": avaliados,
            "percentual_comparecimento": pct,
        }

    if "proficiencia_media" in wanted:
        block["proficiencia_media"] = {
            "geral": stats.get("media_proficiencia_geral"),
            "media_nota_geral": stats.get("media_nota_geral"),
            "nivel_classificacao": stats.get("nivel_classificacao"),
            "por_disciplina": [
                {
                    "disciplina": row.get("disciplina"),
                    "media_proficiencia": row.get("media_proficiencia"),
                    "media_nota": row.get("media_nota"),
                    "alunos_participantes": row.get("alunos_participantes"),
                }
                for row in (por_disciplina or [])
            ],
        }

    if "distribuicao_niveis" in wanted:
        dist = stats.get("distribuicao_classificacao_geral") or {}
        block["distribuicao_niveis"] = _distribuicao_com_percentuais(dist, avaliados)

    if "alunos_avaliados" in wanted:
        block["alunos_avaliados"] = {"quantidade": avaliados}

    if "aplicacoes" in wanted:
        block["aplicacoes"] = {"quantidade": int(aplicacoes)}

    return block


def _compute_one_evaluation(
    evaluation_id: str,
    *,
    user: dict,
    estado: str,
    municipio: str,
    escola: Optional[str],
    serie: Optional[str],
    turma: Optional[str],
    alunos_filtro: str,
    indicadores: Sequence[str],
) -> Dict[str, Any]:
    from app.routes.evaluation_results_routes import (
        _calcular_estatisticas_consolidadas_por_escopo,
        _calcular_estatisticas_gerais_por_disciplina_escopo,
        _determinar_escopo_busca,
        _determinar_nivel_granularidade,
    )

    test = Test.query.get(str(evaluation_id))
    if not test:
        raise ComparativeReportError(f"Avaliação não encontrada: {evaluation_id}")

    escola_arg = escola or "all"
    serie_arg = serie or "all"
    turma_arg = turma or "all"

    scope_info = _determinar_escopo_busca(
        estado, municipio, escola_arg, serie_arg, turma_arg, str(evaluation_id), user
    )
    if not scope_info:
        raise ComparativeReportError(
            "Não foi possível determinar o escopo para a avaliação selecionada."
        )

    # Mesma regra de Resultados quando o parâmetro alunos está presente.
    scope_info["alunos"] = alunos_filtro
    scope_info["adap_pareamento"] = True

    class_tests = _fetch_class_tests_for_evaluation(
        str(evaluation_id),
        str(municipio),
        escola=escola,
        serie=serie,
        turma=turma,
    )
    aplicacoes = len(class_tests)

    nivel = _determinar_nivel_granularidade(
        estado, municipio, escola_arg, serie_arg, turma_arg, str(evaluation_id), user
    )

    stats = _calcular_estatisticas_consolidadas_por_escopo(
        class_tests, scope_info, nivel, user
    )
    if not isinstance(stats, dict):
        stats = {}

    por_disciplina: List[Dict[str, Any]] = []
    if "proficiencia_media" in indicadores:
        por_disciplina = _calcular_estatisticas_gerais_por_disciplina_escopo(
            class_tests, scope_info, nivel
        ) or []

    subject_name = None
    if getattr(test, "subject_rel", None) is not None:
        subject_name = getattr(test.subject_rel, "name", None)

    return {
        "evaluation_id": str(evaluation_id),
        "titulo": test.title,
        "disciplina": subject_name,
        "aplicacoes_no_recorte": aplicacoes,
        "indicadores": _slice_indicators(stats, por_disciplina, aplicacoes, indicadores),
    }


def build_comparative_report(
    user: dict,
    *,
    evaluation_ids: Sequence[str],
    estado: str,
    municipio: str,
    escola: Optional[str] = None,
    serie: Optional[str] = None,
    turma: Optional[str] = None,
    alunos: Any = "regular",
    indicadores: Sequence[str],
    report_entity_type: str = "evaluation",
) -> Dict[str, Any]:
    """
    Monta o comparativo descritivo (uma coluna por avaliação).
    report_entity_type=evaluation nesta versão; cartão fica para depois.
    """
    from app.routes.evaluation_results_routes import verificar_permissao_filtros

    entity = (report_entity_type or "evaluation").strip().lower()
    if entity in ("answer_sheet", "cartao", "cartao_resposta"):
        raise ComparativeReportError(
            "Cartão-resposta ainda não está disponível no Relatório Comparativo."
        )
    if entity not in SUPPORTED_ENTITY_TYPES:
        raise ComparativeReportError(
            f"Tipo de relatório inválido. Use: {', '.join(SUPPORTED_ENTITY_TYPES)}."
        )

    permissao = verificar_permissao_filtros(user)
    if not permissao.get("permitted"):
        raise PermissionError(permissao.get("error") or "Sem permissão")

    ids = []
    seen: Set[str] = set()
    for raw in evaluation_ids or []:
        eid = str(raw or "").strip()
        if not eid or eid in seen:
            continue
        seen.add(eid)
        ids.append(eid)

    if len(ids) < 2:
        raise ComparativeReportError(
            "Selecione pelo menos 2 avaliações para o relatório comparativo."
        )

    estado_n = (estado or "").strip()
    municipio_n = (municipio or "").strip()
    if not estado_n or not municipio_n:
        raise ComparativeReportError("Parâmetros obrigatórios: estado e municipio.")

    city = City.query.get(municipio_n)
    if not city:
        raise ComparativeReportError("Município não encontrado.")

    try:
        alunos_filtro = parse_alunos_filtro(alunos if alunos is not None else "regular")
    except AlunosFiltroInvalido as exc:
        raise ComparativeReportError(str(exc)) from exc

    if alunos_filtro not in ALUNOS_FILTROS:
        raise ComparativeReportError(
            "Parâmetro alunos inválido. Use regular, regular_adap, adap ou todos."
        )

    inds = []
    seen_ind: Set[str] = set()
    for raw in indicadores or []:
        key = str(raw or "").strip().lower()
        if not key or key in seen_ind:
            continue
        if key not in INDICADORES_VALIDOS:
            raise ComparativeReportError(
                f"Indicador inválido: {key}. Válidos: {', '.join(INDICADORES_VALIDOS)}."
            )
        seen_ind.add(key)
        inds.append(key)

    if not inds:
        raise ComparativeReportError("Selecione pelo menos um indicador.")

    set_search_path(city_id_to_schema_name(str(municipio_n)))

    escola_n = _norm_optional(escola)
    serie_n = _norm_optional(serie)
    turma_n = _norm_optional(turma)

    # Validar que todas as avaliações têm ClassTest no município
    for eid in ids:
        cts = _fetch_class_tests_for_evaluation(
            eid, str(municipio_n), escola=None, serie=None, turma=None
        )
        if not cts:
            raise ComparativeReportError(
                f"A avaliação {eid} não possui aplicações no município selecionado."
            )

    avaliacoes_out: List[Dict[str, Any]] = []
    for eid in ids:
        avaliacoes_out.append(
            _compute_one_evaluation(
                eid,
                user=user,
                estado=estado_n,
                municipio=str(municipio_n),
                escola=escola_n,
                serie=serie_n,
                turma=turma_n,
                alunos_filtro=alunos_filtro,
                indicadores=inds,
            )
        )

    return {
        "report_entity_type": "evaluation",
        "filtros_aplicados": {
            "estado": estado_n,
            "municipio": {
                "id": str(city.id),
                "nome": city.name,
            },
            "escola": escola_n,
            "serie": serie_n,
            "turma": turma_n,
            "alunos": alunos_filtro,
            "indicadores": inds,
            "evaluation_ids": ids,
        },
        "avaliacoes": avaliacoes_out,
    }
