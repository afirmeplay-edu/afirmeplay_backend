# -*- coding: utf-8 -*-
"""
Relatório de Níveis de Proficiência.

Monta o contrato JSON consumido pelo frontend. A classificação do aluno
sempre vem da fonte da verdade do backend (`classification` /
`nivel_proficiencia_geral` já calculados por EvaluationCalculator).

Habilidades usam faixas por % de acertos (mapa de habilidades existente).
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from app.utils.class_label_helpers import normalize_shift
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


def normalize_nivel(value: Any) -> Optional[str]:
    """Normaliza texto de classificação para um dos 4 níveis oficiais."""
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

    # Mesma heurística das agregações existentes (substring).
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


def enrich_turnos_por_aluno(
    alunos_raw: Sequence[Dict[str, Any]],
    turno_por_aluno_id: Optional[Dict[str, Optional[str]]] = None,
) -> List[Dict[str, Any]]:
    """Anexa `turno`/`shift` quando o payload de origem não trouxe o campo."""
    turno_map = turno_por_aluno_id or {}
    out: List[Dict[str, Any]] = []
    for row in alunos_raw:
        item = dict(row)
        aluno_id = str(item.get("id") or "")
        turno = normalize_shift(item.get("turno") or item.get("shift"))
        if not turno and aluno_id:
            turno = normalize_shift(turno_map.get(aluno_id))
        item["turno"] = turno or ""
        item["shift"] = item["turno"]
        out.append(item)
    return out


def map_aluno_row(raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Converte aluno de tabela_detalhada.geral para o contrato do relatório.
    Descarta pendentes / sem classificação (não entram na escala).
    """
    status = str(raw.get("status_geral") or raw.get("status") or "").strip().lower()
    nivel = normalize_nivel(
        raw.get("nivel_proficiencia_geral")
        or raw.get("nivel")
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
        or 0
    )
    percentual = raw.get("percentual_acertos_geral")
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
        "turno": normalize_shift(raw.get("turno") or raw.get("shift")) or "",
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
    turno_norm = normalize_shift(turno)
    nivel_norm = normalize_nivel(nivel) if nivel and str(nivel).strip().lower() not in {"", "all", "todos"} else None

    out: List[Dict[str, Any]] = []
    for a in alunos:
        if turno_norm:
            aluno_turno = normalize_shift(a.get("turno") or a.get("shift")) or ""
            if aluno_turno.casefold() != turno_norm.casefold():
                continue
        if nivel_norm and a.get("nivel") != nivel_norm:
            continue
        out.append(a)
    return out


def compute_indicadores(alunos: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(alunos)
    counts = empty_distribuicao_counts()
    sum_pct = 0.0
    sum_prof = 0.0
    turmas = set()

    for a in alunos:
        nivel = a.get("nivel")
        if nivel in counts:
            counts[nivel] += 1
        sum_pct += float(a.get("percentual_acertos") or 0)
        sum_prof += float(a.get("proficiencia") or 0)
        turmas.add(f"{a.get('serie')}|{a.get('turma')}")

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
    for a in alunos:
        chave = (str(a.get("serie") or "N/A"), str(a.get("turma") or "N/A"))
        grupos[chave].append(a)

    out: List[Dict[str, Any]] = []
    for (serie, turma) in sorted(grupos.keys(), key=lambda x: (x[0], x[1])):
        lista = sorted(
            grupos[(serie, turma)],
            key=lambda x: (-float(x.get("proficiencia") or 0), str(x.get("nome") or "")),
        )
        ind = compute_indicadores(lista)
        turnos = sorted(
            {
                normalize_shift(a.get("turno"))
                for a in lista
                if normalize_shift(a.get("turno"))
            }
        )
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
    for h in habilidades_raw or []:
        faixa = str(h.get("faixa") or "").strip().lower()
        nivel = FAIXA_TO_NIVEL.get(faixa) or normalize_nivel(h.get("nivel"))
        pct = float(h.get("percentual_acertos") or 0)
        if nivel is None:
            # Fallback alinhado ao mapa de habilidades (faixa_from_percent)
            if pct < 30:
                nivel = "Abaixo do Básico"
            elif pct < 60:
                nivel = "Básico"
            elif pct < 80:
                nivel = "Adequado"
            else:
                nivel = "Avançado"
            faixa = faixa or {
                "Abaixo do Básico": "abaixo_do_basico",
                "Básico": "basico",
                "Adequado": "adequado",
                "Avançado": "avancado",
            }[nivel]

        mapped.append(
            {
                "codigo": str(h.get("codigo") or ""),
                "descricao": str(h.get("descricao") or ""),
                "componente": str(
                    h.get("disciplina_nome")
                    or h.get("componente")
                    or h.get("disciplina")
                    or "N/A"
                ),
                "subject_id": str(h.get("subject_id") or "") or None,
                "percentual_acertos": round_to_two_decimals(pct),
                "faixa": faixa,
                "nivel": nivel,
                "serie": serie_label or h.get("serie") or None,
            }
        )

    mapped.sort(key=lambda x: (float(x["percentual_acertos"]), x["codigo"]))
    return mapped


def build_report_payload(
    *,
    fonte: str,
    meta: Dict[str, Any],
    filtros_aplicados: Dict[str, Any],
    alunos_raw: Sequence[Dict[str, Any]],
    habilidades_raw: Sequence[Dict[str, Any]] = (),
    turno_por_aluno_id: Optional[Dict[str, Optional[str]]] = None,
    turno_filtro: Optional[str] = None,
    nivel_filtro: Optional[str] = None,
    serie_label: Optional[str] = None,
    nivel_granularidade: Optional[str] = None,
) -> Dict[str, Any]:
    """Monta o contrato completo do relatório."""
    enriched = enrich_turnos_por_aluno(alunos_raw, turno_por_aluno_id)
    mapped: List[Dict[str, Any]] = []
    for raw in enriched:
        row = map_aluno_row(raw)
        if row:
            mapped.append(row)

    filtrados = filter_alunos(mapped, turno=turno_filtro, nivel=nivel_filtro)
    filtrados.sort(
        key=lambda x: (
            str(x.get("serie") or ""),
            str(x.get("turma") or ""),
            -float(x.get("proficiencia") or 0),
            str(x.get("nome") or ""),
        )
    )

    ind = compute_indicadores(filtrados)
    counts = ind.pop("distribuicao_counts")
    total = len(filtrados)

    return {
        "fonte": fonte,
        "nivel_granularidade": nivel_granularidade,
        "meta": meta,
        "filtros_aplicados": filtros_aplicados,
        "niveis": list(NIVEIS),
        "indicadores": ind,
        "distribuicao": build_distribuicao(counts, total),
        "alunos": filtrados,
        "por_turma": group_por_turma(filtrados),
        "habilidades": map_habilidades(habilidades_raw, serie_label=serie_label),
    }


def resolve_turno_map_from_students(
    student_ids: Iterable[str],
    class_id_by_student: Optional[Dict[str, Any]] = None,
) -> Dict[str, Optional[str]]:
    """
    Resolve turno (Class.shift) por aluno.
    `class_id_by_student` tem prioridade (ex.: class_id_snapshot do cartão).
    """
    from app.models.student import Student
    from app.models.studentClass import Class

    ids = [str(i) for i in student_ids if i]
    if not ids:
        return {}

    class_id_by_student = {str(k): v for k, v in (class_id_by_student or {}).items()}
    missing = [sid for sid in ids if sid not in class_id_by_student or not class_id_by_student.get(sid)]
    if missing:
        for row in Student.query.with_entities(Student.id, Student.class_id).filter(Student.id.in_(missing)).all():
            class_id_by_student[str(row[0])] = row[1]

    class_ids = {cid for cid in class_id_by_student.values() if cid}
    shift_by_class: Dict[Any, Optional[str]] = {}
    if class_ids:
        for c in Class.query.with_entities(Class.id, Class.shift).filter(Class.id.in_(list(class_ids))).all():
            shift_by_class[c[0]] = normalize_shift(c[1])

    out: Dict[str, Optional[str]] = {}
    for sid in ids:
        cid = class_id_by_student.get(sid)
        out[sid] = shift_by_class.get(cid) if cid else None
    return out
