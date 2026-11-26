# -*- coding: utf-8 -*-
"""Tipos do contrato ResultadoEscopo (fachada única de leitura)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence


@dataclass
class ResultadoEscopoContexto:
    test_ids: List[str]
    school_id: Optional[str] = None
    class_id: Optional[str] = None
    serie_id: Optional[str] = None
    municipio_id: Optional[str] = None
    course_name: str = "Anos Iniciais"
    has_matematica: Optional[bool] = None
    modalidade: str = "online"  # online | cartao
    filtro_alunos: str = "todos"
    target_level: str = "municipio"


@dataclass
class ResultadoEscopoUniverso:
    matriculados: int = 0
    alunos_elegiveis: int = 0
    alunos_historicos: int = 0
    avaliados: int = 0
    faltantes: int = 0
    ausentes: int = 0
    pendentes: int = 0
    inconsistentes: int = 0
    student_ids: List[str] = field(default_factory=list)
    avaliados_ids: List[str] = field(default_factory=list)
    status_aplicacao: str = "aplicada"  # aplicada | nao_aplicada


@dataclass
class ResultadoEscopoIndicadores:
    proficiencia_media: float = 0.0
    nota: float = 0.0
    classificacao: Optional[str] = None


@dataclass
class ResultadoEscopoParticipacao:
    matriculados: int = 0
    avaliados: int = 0
    percentual: float = 0.0
    status_aplicacao: str = "aplicada"


@dataclass
class ResultadoEscopoPayload:
    contexto: ResultadoEscopoContexto
    universo: ResultadoEscopoUniverso
    resultados: Sequence[Any] = field(default_factory=list)
    indicadores: ResultadoEscopoIndicadores = field(default_factory=ResultadoEscopoIndicadores)
    participacao: ResultadoEscopoParticipacao = field(
        default_factory=ResultadoEscopoParticipacao
    )
    hierarquia: Dict[str, Any] = field(default_factory=dict)
    metadados: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contexto": self.contexto.__dict__,
            "universo": {
                **{k: v for k, v in self.universo.__dict__.items() if k not in ("student_ids", "avaliados_ids")},
                "student_ids": list(self.universo.student_ids),
                "avaliados_ids": list(self.universo.avaliados_ids),
            },
            "indicadores": self.indicadores.__dict__,
            "participacao": self.participacao.__dict__,
            "hierarquia": self.hierarquia,
            "metadados": self.metadados,
            "resultados_count": len(list(self.resultados or [])),
        }
