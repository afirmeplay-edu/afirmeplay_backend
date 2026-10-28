# -*- coding: utf-8 -*-
"""Recorte Regular / Educação Especial do relatório de participação.

A série antiga "Suporte N" entra no ADAP daquele nível, como em
``special_education``. Educação especial sem nível fica só no total.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, Optional, Set

from app.services.alunos_resultado_filtro import aluno_entra_no_filtro, filtro_restringe
from app.services.special_education import SpecialEducationStatus

_NIVEIS = (1, 2, 3)
_CHAVES = ("regular", "adap_1", "adap_2", "adap_3")


def percentual(avaliados: int, matriculados: int) -> float:
    if matriculados <= 0:
        return 0.0
    return round(100.0 * avaliados / matriculados, 2)


def recorte(matriculados: int = 0, avaliados: int = 0) -> Dict[str, Any]:
    return {
        "matriculados": int(matriculados),
        "avaliados": int(avaliados),
        "percentual_participacao": percentual(avaliados, matriculados),
    }


def grupos_vazios() -> Dict[str, Dict[str, Any]]:
    base = {chave: recorte() for chave in _CHAVES}
    base["educacao_especial"] = recorte()
    return {
        "regular": base["regular"],
        "educacao_especial": base["educacao_especial"],
        "adap_1": base["adap_1"],
        "adap_2": base["adap_2"],
        "adap_3": base["adap_3"],
    }


def aplicar_filtro_ids(
    ids: Iterable[Any],
    statuses: Dict[str, SpecialEducationStatus],
    filtro: Optional[str],
) -> Set[Any]:
    """Mesma regra da prova online. ``todos`` devolve o conjunto como veio."""
    bruto = set(ids)
    if not filtro_restringe(filtro):
        return bruto
    return {
        item
        for item in bruto
        if aluno_entra_no_filtro(
            statuses.get(str(item), SpecialEducationStatus(False, None, None)),
            filtro or "todos",
        )
    }


class AcumuladorGrupos:
    def __init__(self) -> None:
        self._contas = {chave: [0, 0] for chave in _CHAVES}
        self.total_matriculados = 0
        self.total_avaliados = 0

    def add(self, status: SpecialEducationStatus, avaliado: bool) -> None:
        self.total_matriculados += 1
        if avaliado:
            self.total_avaliados += 1
        if status.is_special and status.level in _NIVEIS:
            chave = f"adap_{int(status.level)}"
        elif not status.is_special:
            chave = "regular"
        else:
            return
        self._contas[chave][0] += 1
        if avaliado:
            self._contas[chave][1] += 1

    def fechar(self) -> Dict[str, Dict[str, Any]]:
        partes = {chave: recorte(par[0], par[1]) for chave, par in self._contas.items()}
        ee_m = sum(self._contas[f"adap_{nivel}"][0] for nivel in _NIVEIS)
        ee_a = sum(self._contas[f"adap_{nivel}"][1] for nivel in _NIVEIS)
        return {
            "regular": partes["regular"],
            "educacao_especial": recorte(ee_m, ee_a),
            "adap_1": partes["adap_1"],
            "adap_2": partes["adap_2"],
            "adap_3": partes["adap_3"],
        }


def linhas_por_serie(
    acumulados: Dict[str, AcumuladorGrupos],
    nomes: Optional[Dict[str, str]] = None,
) -> list:
    serie_nomes = nomes or {}
    linhas = []
    for serie_id, acumulado in acumulados.items():
        linhas.append(
            {
                "serie_id": serie_id,
                "serie_nome": serie_nomes.get(serie_id) or serie_id,
                "matriculados": acumulado.total_matriculados,
                "avaliados": acumulado.total_avaliados,
                "percentual_participacao": percentual(
                    acumulado.total_avaliados, acumulado.total_matriculados
                ),
                "grupos": acumulado.fechar(),
            }
        )
    linhas.sort(key=lambda item: (item.get("serie_nome") or "").upper())
    return linhas


def recortar_roster(
    matriculados: Iterable[Any],
    avaliados: Iterable[Any],
    statuses: Dict[str, SpecialEducationStatus],
    filtro: Optional[str],
) -> tuple:
    """Aplica o filtro Alunos. ``todos`` devolve os mesmos conjuntos."""
    mantidos = aplicar_filtro_ids(matriculados, statuses, filtro)
    presentes = {item for item in avaliados if item in mantidos}
    return mantidos, presentes


def status_de_aluno_censo(aluno: Any) -> SpecialEducationStatus:
    perfil = getattr(aluno, "perfil", None)
    nivel = getattr(aluno, "nivel_adap", None)
    if perfil == "adap" and nivel in _NIVEIS:
        return SpecialEducationStatus(True, int(nivel), "censo")
    if perfil == "regular":
        return SpecialEducationStatus(False, None, None)
    return SpecialEducationStatus(True, None, "censo")


def anexar_grupos_do_censo(
    payload: Dict[str, Any],
    censo: Any,
    *,
    grupo: bool,
    serie_nomes: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Preenche ``grupos`` sem alterar matriculados/avaliados já calculados."""
    nomes = serie_nomes or {}
    geral = AcumuladorGrupos()
    por_escola: Dict[str, AcumuladorGrupos] = {}
    por_serie: Dict[str, AcumuladorGrupos] = {}
    por_turma: Dict[str, AcumuladorGrupos] = {}

    for aluno in getattr(censo, "alunos", ()) or ():
        if not getattr(aluno, "no_denominador", False):
            continue
        status = status_de_aluno_censo(aluno)
        presente = (
            bool(aluno.participacao_completa)
            if grupo
            else bool(aluno.participacao_pelo_menos_uma)
        )
        geral.add(status, presente)
        escola_id = str(aluno.escola_id) if getattr(aluno, "escola_id", None) else ""
        serie_id = str(aluno.serie_id) if getattr(aluno, "serie_id", None) else ""
        turma_id = str(aluno.turma_id) if getattr(aluno, "turma_id", None) else ""
        if escola_id:
            por_escola.setdefault(escola_id, AcumuladorGrupos()).add(status, presente)
        if serie_id:
            por_serie.setdefault(serie_id, AcumuladorGrupos()).add(status, presente)
        if turma_id:
            por_turma.setdefault(turma_id, AcumuladorGrupos()).add(status, presente)

    metricas = payload.setdefault("metricas", {})
    metricas["grupos"] = geral.fechar()
    for row in payload.get("por_escola") or []:
        chave = str(row.get("escola_id") or "")
        row["grupos"] = por_escola.get(chave, AcumuladorGrupos()).fechar()
    for row in payload.get("por_turma") or []:
        chave = str(row.get("turma_id") or "")
        row["grupos"] = por_turma.get(chave, AcumuladorGrupos()).fechar()

    payload["por_serie"] = linhas_por_serie(por_serie, nomes)
    return payload
