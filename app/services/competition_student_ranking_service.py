# -*- coding: utf-8 -*-
"""
Serviço de classificação de ranking do aluno baseada em competições.

Critério acordado:
- Usa ACÚMULO de pódios (lifetime) em todas as competições.
- Classificação em faixas, por total de 1º, 2º e 3º lugares.

Faixas (exemplo inicial, fácil de ajustar):
- Aprendiz       → até 0 pódios
- Iniciante      → 1–2 pódios
- Dedicado       → 3–4 pódios
- Destaque       → 5–7 pódios
- Honra          → 8–11 pódios
- Excelência     → 12–15 pódios
- Mestre do Saber→ 16+ pódios
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from sqlalchemy import func

from app import db
from app.competitions.models import CompetitionResult
from app.models.student import Student
from app.certification.services.certificate_service import CertificateService


@dataclass(frozen=True)
class RankBand:
    name: str
    min_podiums: int
    max_podiums: Optional[int]  # None = infinito


RANK_BANDS = [
    RankBand("Aprendiz", min_podiums=0, max_podiums=0),
    RankBand("Iniciante", min_podiums=1, max_podiums=2),
    RankBand("Dedicado", min_podiums=3, max_podiums=4),
    RankBand("Destaque", min_podiums=5, max_podiums=7),
    RankBand("Honra", min_podiums=8, max_podiums=11),
    RankBand("Excelência", min_podiums=12, max_podiums=15),
    RankBand("Mestre do Saber", min_podiums=16, max_podiums=None),
]


class CompetitionStudentRankingService:
    """Serviço para classificação global do aluno em competições."""

    @staticmethod
    def _count_podiums(student_id: str) -> Dict[str, int]:
        """
        Conta quantos 1º, 2º e 3º lugares o aluno possui em CompetitionResult.
        """
        rows = (
            db.session.query(
                CompetitionResult.posicao,
                func.count(CompetitionResult.id),
            )
            .filter(
                CompetitionResult.student_id == student_id,
                CompetitionResult.posicao.in_([1, 2, 3]),
            )
            .group_by(CompetitionResult.posicao)
            .all()
        )
        counts = {1: 0, 2: 0, 3: 0}
        for pos, cnt in rows:
            if pos in counts:
                counts[pos] = int(cnt or 0)
        return {
            "first_places": counts[1],
            "second_places": counts[2],
            "third_places": counts[3],
            "total_podiums": counts[1] + counts[2] + counts[3],
        }

    @staticmethod
    def _band_for_total_podiums(total: int) -> RankBand:
        for band in RANK_BANDS:
            if total < band.min_podiums:
                continue
            if band.max_podiums is None or total <= band.max_podiums:
                return band
        # fallback
        return RANK_BANDS[-1]

    @staticmethod
    def get_student_competition_rank_classification(
        student_id: str,
    ) -> Optional[Dict]:
        """
        Retorna classificação global do aluno baseada apenas em competições.

        Retorno:
        {
          "band": "Destaque",
          "total_podiums": 7,
          "first_places": 3,
          "second_places": 2,
          "third_places": 2,
        }
        """
        student = Student.query.get(student_id)
        if not student:
            return None

        counts = CompetitionStudentRankingService._count_podiums(student_id)
        band = CompetitionStudentRankingService._band_for_total_podiums(
            counts["total_podiums"]
        )
        return {
            "band": band.name,
            **counts,
        }

    @staticmethod
    def handle_new_first_place(
        student_id: str,
        competition_id: str,
    ) -> None:
        """
        Deve ser chamado quando um novo 1º lugar é registrado.
        Responsável por emitir certificado para cada novo 1º lugar, com
        cores de acordo com a classificação atual do aluno.
        """
        # Recalcula classificação atual após contar todos os pódios
        classification = CompetitionStudentRankingService.get_student_competition_rank_classification(
            student_id
        )
        if not classification:
            return

        band_name = classification["band"]

        # Definir cores por faixa (exemplo; pode ser refinado no futuro)
        COLOR_MAP = {
            "Aprendiz": {
                "background_color": "#ECEFF1",
                "text_color": "#37474F",
                "accent_color": "#90A4AE",
            },
            "Iniciante": {
                "background_color": "#E3F2FD",
                "text_color": "#0D47A1",
                "accent_color": "#42A5F5",
            },
            "Dedicado": {
                "background_color": "#E8F5E9",
                "text_color": "#1B5E20",
                "accent_color": "#66BB6A",
            },
            "Destaque": {
                "background_color": "#FFF8E1",
                "text_color": "#FF6F00",
                "accent_color": "#FFB300",
            },
            "Honra": {
                "background_color": "#F3E5F5",
                "text_color": "#4A148C",
                "accent_color": "#AB47BC",
            },
            "Excelência": {
                "background_color": "#E0F7FA",
                "text_color": "#006064",
                "accent_color": "#00ACC1",
            },
            "Mestre do Saber": {
                "background_color": "#FFF3E0",
                "text_color": "#BF360C",
                "accent_color": "#FF7043",
            },
        }

        colors = COLOR_MAP.get(
            band_name,
            COLOR_MAP["Aprendiz"],
        )

        # Usa CertificateService para emitir/atualizar um certificado
        # genérico de "Mestre Afirmeplay" para essa conquista.
        # Aqui utilizamos um template especial por avaliação inexistente,
        # então apenas registramos a emissão usando o mecanismo existente,
        # sem vincular a um test_id específico.
        # Se no futuro houver templates próprios, podemos direcionar por evaluation_id.

        try:
            # Cria um template ad-hoc em memória e persiste via CertificateService
            template_data = {
                "evaluation_id": competition_id,
                "title": f"Conquista {band_name}",
                "text_content": f"Parabéns! Você alcançou a faixa {band_name} no ranking de competições da Afirmeplay.",
                "background_color": colors["background_color"],
                "text_color": colors["text_color"],
                "accent_color": colors["accent_color"],
            }
            template = CertificateService.save_template(template_data)

            # Emite certificado para o aluno (usa API de aprovação existente)
            CertificateService.approve_certificates(
                evaluation_id=competition_id,
                student_ids=[student_id],
            )
        except Exception:
            # Não deve quebrar o fluxo principal de ranking
            return


__all__ = [
    "CompetitionStudentRankingService",
]

