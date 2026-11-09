# -*- coding: utf-8 -*-
"""Contrato do relatório Acertos e Níveis do Afirme Ler.

Espelha o formato de `proficiency_levels_report_service` (KPIs, distribuição,
alunos, por turma, habilidades), sem depender do core de avaliação online.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.utils.decimal_helpers import round_to_two_decimals

NIVEIS: Tuple[str, ...] = (
    "Abaixo do Básico",
    "Básico",
    "Adequado",
    "Avançado",
)

FAIXA_TO_NIVEL = {
    "abaixo_do_basico": "Abaixo do Básico",
    "basico": "Básico",
    "adequado": "Adequado",
    "avancado": "Avançado",
}

_NIVEL_ALIASES = {
    "abaixo do basico": "Abaixo do Básico",
    "abaixo do básico": "Abaixo do Básico",
    "abaixo_do_basico": "Abaixo do Básico",
    "basico": "Básico",
    "básico": "Básico",
    "adequado": "Adequado",
    "avancado": "Avançado",
    "avançado": "Avançado",
}

FONTE_ESCRITA = "escrita"
FONTE_FLUENCIA = "fluencia"
FONTES = (FONTE_ESCRITA, FONTE_FLUENCIA)


def normalize_nivel(value: Any) -> Optional[str]:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    if raw in NIVEIS:
        return raw

    key = raw.lower()
    if key in _NIVEL_ALIASES:
        return _NIVEL_ALIASES[key]

    if "abaixo" in key:
        return "Abaixo do Básico"
    if "básico" in key or "basico" in key:
        return "Básico"
    if "adequado" in key:
        return "Adequado"
    if "avançado" in key or "avancado" in key:
        return "Avançado"
    return None


def empty_distribuicao_counts() -> Dict[str, int]:
    return {n: 0 for n in NIVEIS}


def _pct(part: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round_to_two_decimals((part / total) * 100.0)


def build_distribuicao(counts: Dict[str, int], total: int) -> Dict[str, Dict[str, float]]:
    out: Dict[str, Dict[str, float]] = {}
    for nivel in NIVEIS:
        qtd = int(counts.get(nivel, 0) or 0)
        out[nivel] = {
            "quantidade": qtd,
            "percentual": _pct(qtd, total),
        }
    return out


def faixa_from_percent(pct: float) -> str:
    if pct < 30:
        return "abaixo_do_basico"
    if pct < 60:
        return "basico"
    if pct < 80:
        return "adequado"
    return "avancado"


def map_aluno_row(raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Converte aluno bruto para o contrato. Descarta sem classificação válida."""
    status = str(raw.get("status_geral") or raw.get("status") or "").strip().lower()
    nivel = normalize_nivel(
        raw.get("nivel_proficiencia_geral")
        or raw.get("nivel")
        or raw.get("nivel_aprendizagem")
        or raw.get("classificacao")
        or raw.get("classification")
    )
    if status and status not in {"concluida", "concluído", "concluido"} and nivel is None:
        return None
    if nivel is None:
        return None

    total_itens = int(
        raw.get("total_questoes_geral")
        or raw.get("total_itens")
        or raw.get("total_questions")
        or 0
    )
    acertos = int(
        raw.get("total_acertos_geral")
        or raw.get("acertos")
        or raw.get("correct_answers")
        or raw.get("pontos_34")
        or 0
    )
    percentual = raw.get("percentual_acertos_geral")
    if percentual is None:
        percentual = raw.get("percentual_acertos")
    if percentual is None:
        percentual = (acertos / total_itens * 100.0) if total_itens > 0 else 0.0

    nota = raw.get("nota_geral", raw.get("nota", 0.0))
    proficiencia = raw.get("proficiencia_geral", raw.get("proficiencia", 0.0))

    return {
        "id": str(raw.get("id") or ""),
        "nome": str(raw.get("nome") or "N/A"),
        "escola_id": str(raw.get("escola_id") or "") or None,
        "escola": str(raw.get("escola") or "N/A"),
        "serie": str(raw.get("serie") or "N/A"),
        "turma": str(raw.get("turma") or "N/A"),
        "turno": str(raw.get("turno") or raw.get("shift") or "").strip(),
        "acertos": acertos,
        "total_itens": total_itens,
        "percentual_acertos": round_to_two_decimals(float(percentual or 0)),
        "nota": round_to_two_decimals(float(nota or 0)),
        "proficiencia": round_to_two_decimals(float(proficiencia or 0)),
        "nivel": nivel,
        "status": "concluida",
    }


def filter_alunos(
    alunos: Sequence[Dict[str, Any]],
    *,
    turno: Optional[str] = None,
    nivel: Optional[str] = None,
) -> List[Dict[str, Any]]:
    turno_norm = (str(turno).strip() if turno else "") or None
    if turno_norm and turno_norm.lower() in {"all", "todos"}:
        turno_norm = None
    nivel_norm = (
        normalize_nivel(nivel)
        if nivel and str(nivel).strip().lower() not in {"", "all", "todos"}
        else None
    )

    out: List[Dict[str, Any]] = []
    for aluno in alunos:
        if turno_norm:
            aluno_turno = str(aluno.get("turno") or aluno.get("shift") or "").strip()
            if aluno_turno.casefold() != turno_norm.casefold():
                continue
        if nivel_norm and aluno.get("nivel") != nivel_norm:
            continue
        out.append(aluno)
    return out


def compute_indicadores(alunos: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(alunos)
    counts = empty_distribuicao_counts()
    sum_pct = 0.0
    sum_prof = 0.0
    turmas = set()

    for aluno in alunos:
        nivel = aluno.get("nivel")
        if nivel in counts:
            counts[nivel] += 1
        sum_pct += float(aluno.get("percentual_acertos") or 0)
        sum_prof += float(aluno.get("proficiencia") or 0)
        turmas.add(f"{aluno.get('serie')}|{aluno.get('turma')}")

    adequado_avancado = counts["Adequado"] + counts["Avançado"]
    criticos = counts["Abaixo do Básico"]

    return {
        "alunos_avaliados": total,
        "turmas": len(turmas),
        "media_acertos_percentual": round_to_two_decimals(sum_pct / total) if total else 0.0,
        "media_proficiencia": round_to_two_decimals(sum_prof / total) if total else 0.0,
        "adequado_avancado": {
            "quantidade": adequado_avancado,
            "percentual": _pct(adequado_avancado, total),
        },
        "abaixo_do_basico": {
            "quantidade": criticos,
            "percentual": _pct(criticos, total),
        },
        "distribuicao_counts": counts,
    }


def group_por_turma(alunos: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    grupos: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for aluno in alunos:
        chave = (str(aluno.get("serie") or "N/A"), str(aluno.get("turma") or "N/A"))
        grupos[chave].append(aluno)

    out: List[Dict[str, Any]] = []
    for serie, turma in sorted(grupos.keys(), key=lambda item: (item[0], item[1])):
        lista = sorted(
            grupos[(serie, turma)],
            key=lambda item: (-float(item.get("proficiencia") or 0), str(item.get("nome") or "")),
        )
        ind = compute_indicadores(lista)
        turnos = sorted({str(a.get("turno") or "").strip() for a in lista if str(a.get("turno") or "").strip()})
        out.append(
            {
                "serie": serie,
                "turma": turma,
                "turno": turnos[0] if len(turnos) == 1 else (", ".join(turnos) if turnos else ""),
                "alunos_avaliados": ind["alunos_avaliados"],
                "media_acertos_percentual": ind["media_acertos_percentual"],
                "media_proficiencia": ind["media_proficiencia"],
                "distribuicao": build_distribuicao(ind["distribuicao_counts"], len(lista)),
                "alunos": lista,
            }
        )
    return out


def map_habilidades(
    habilidades_raw: Sequence[Dict[str, Any]],
    *,
    serie_label: Optional[str] = None,
) -> List[Dict[str, Any]]:
    mapped: List[Dict[str, Any]] = []
    for item in habilidades_raw or []:
        pct = float(
            item.get("percentual_acertos")
            if item.get("percentual_acertos") is not None
            else (item.get("performance_percentage") or 0)
        )
        faixa = str(item.get("faixa") or "").strip().lower()
        nivel = FAIXA_TO_NIVEL.get(faixa) or normalize_nivel(item.get("nivel"))
        if nivel is None:
            faixa = faixa_from_percent(pct)
            nivel = FAIXA_TO_NIVEL[faixa]
        elif not faixa:
            faixa = {
                "Abaixo do Básico": "abaixo_do_basico",
                "Básico": "basico",
                "Adequado": "adequado",
                "Avançado": "avancado",
            }[nivel]

        mapped.append(
            {
                "codigo": str(item.get("codigo") or item.get("skill_code") or ""),
                "descricao": str(item.get("descricao") or item.get("skill_label") or ""),
                "componente": str(
                    item.get("componente")
                    or item.get("disciplina_nome")
                    or item.get("disciplina")
                    or "Avaliação escrita"
                ),
                "subject_id": str(item.get("subject_id") or "") or None,
                "percentual_acertos": round_to_two_decimals(pct),
                "faixa": faixa,
                "nivel": nivel,
                "serie": serie_label or item.get("serie") or None,
            }
        )

    mapped.sort(key=lambda row: (float(row["percentual_acertos"]), row["codigo"]))
    return mapped


def build_report_payload(
    *,
    fonte: str,
    meta: Dict[str, Any],
    filtros_aplicados: Dict[str, Any],
    alunos_raw: Sequence[Dict[str, Any]],
    habilidades_raw: Sequence[Dict[str, Any]] = (),
    turno_filtro: Optional[str] = None,
    nivel_filtro: Optional[str] = None,
    serie_label: Optional[str] = None,
    nivel_granularidade: Optional[str] = None,
    niveis: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    mapped: List[Dict[str, Any]] = []
    for raw in alunos_raw:
        row = map_aluno_row(raw)
        if row:
            mapped.append(row)

    filtrados = filter_alunos(mapped, turno=turno_filtro, nivel=nivel_filtro)
    filtrados.sort(
        key=lambda item: (
            str(item.get("serie") or ""),
            str(item.get("turma") or ""),
            -float(item.get("proficiencia") or 0),
            str(item.get("nome") or ""),
        )
    )

    ind = compute_indicadores(filtrados)
    counts = ind.pop("distribuicao_counts")
    total = len(filtrados)
    escala = list(niveis) if niveis is not None else list(NIVEIS)

    return {
        "fonte": fonte,
        "nivel_granularidade": nivel_granularidade,
        "meta": meta,
        "filtros_aplicados": filtros_aplicados,
        "niveis": escala,
        "indicadores": ind,
        "distribuicao": build_distribuicao(counts, total),
        "alunos": filtrados,
        "por_turma": group_por_turma(filtrados),
        "habilidades": map_habilidades(habilidades_raw, serie_label=serie_label),
    }
