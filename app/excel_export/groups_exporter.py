# -*- coding: utf-8 -*-
"""
Excel da evolução por grupos (turma / série / escola) a partir do payload de
POST /answer-sheets/compare-groups.
"""
from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import Any, Dict, List, Optional

from openpyxl import Workbook

from app.excel_export.formatters import ExcelFormatter

VIEW_LABELS = {"turma": "Turma", "serie": "Série", "escola": "Escola"}
ALUNOS_LABELS = {
    "todos": "Todos",
    "regular": "Regular",
    "regular_adap": "Regular + ADAP",
    "adap": "ADAP",
}
METRICAS = (
    ("average_grade", "Nota"),
    ("average_proficiency", "Proficiência"),
    ("level", "Nível"),
    ("alunos_participantes", "Participantes"),
    ("total_alunos", "Matriculados"),
    ("percentual_comparecimento", "Comparecimento (%)"),
)


class ExcelEvolutionGroupsExporter:
    def export(
        self,
        payload: Dict[str, Any],
        *,
        municipality: Optional[str] = None,
        state: Optional[str] = None,
        department: Optional[str] = None,
    ) -> BytesIO:
        wb = Workbook()
        cover = wb.active
        cover.title = "Capa"
        self._cover(cover, payload, municipality, state, department)

        evaluations = payload.get("evaluations") or []
        groups = payload.get("groups") or []
        view_by = payload.get("view_by") or "turma"

        sheet = wb.create_sheet("Evolução por grupos")
        rows = [(g, None) for g in groups]
        self._groups_table(sheet, rows, evaluations, view_by)

        serie_rows = [(g, s) for g in groups for s in (g.get("by_serie") or [])]
        if serie_rows:
            self._groups_table(wb.create_sheet("Escola por série"), serie_rows, evaluations, view_by)

        out = BytesIO()
        wb.save(out)
        out.seek(0)
        return out

    def _cover(self, ws, payload, municipality, state, department) -> None:
        filtros = payload.get("filtros_aplicados") or {}
        ws["A1"] = "RELATÓRIO DE EVOLUÇÃO POR GRUPOS — CARTÕES-RESPOSTA"
        ExcelFormatter.format_title_cell(ws["A1"])
        linhas = [
            ("Município", municipality or "-"),
            ("Estado", state or "-"),
            ("Secretaria", department or "-"),
            ("Visualizar por", VIEW_LABELS.get(payload.get("view_by"), payload.get("view_by"))),
            ("Alunos", ALUNOS_LABELS.get(filtros.get("alunos") or "todos", filtros.get("alunos"))),
            ("Grupos", payload.get("total_groups", 0)),
            ("Gerado em", datetime.now().strftime("%d/%m/%Y %H:%M")),
        ]
        row = 3
        for label, value in linhas:
            ws.cell(row=row, column=1, value=label).font = ExcelFormatter.BOLD_FONT
            ws.cell(row=row, column=2, value=value)
            row += 1

        row += 1
        ws.cell(row=row, column=1, value="Cartões-resposta (ordem da linha do tempo)")
        ExcelFormatter.format_subtitle_cell(ws.cell(row=row, column=1))
        for ev in payload.get("evaluations") or []:
            row += 1
            series = ", ".join(s.get("name") or "" for s in ev.get("series") or [])
            ws.cell(row=row, column=1, value=f"{ev.get('order')}. {ev.get('title')}")
            ws.cell(row=row, column=2, value=series or "-")

        row += 2
        ws.cell(row=row, column=1, value="Grupos por nível atual")
        ExcelFormatter.format_subtitle_cell(ws.cell(row=row, column=1))
        for nivel, total in (payload.get("summary_by_level") or {}).items():
            row += 1
            ws.cell(row=row, column=1, value=nivel)
            ws.cell(row=row, column=2, value=total)

        if payload.get("requer_filtro_serie"):
            row += 2
            ws.cell(
                row=row,
                column=1,
                value=(
                    "Escolas com mais de uma série não têm média única; "
                    "veja a aba 'Escola por série'."
                ),
            )
        ExcelFormatter.auto_adjust_column_width(ws)

    def _groups_table(
        self,
        ws,
        rows: List[tuple],
        evaluations: List[Dict[str, Any]],
        view_by: str,
    ) -> None:
        fixed = ["Escola", "Série", "Turma"]
        header = list(fixed)
        for ev in evaluations:
            for _key, label in METRICAS:
                header.append(f"{label} ({ev.get('order')})")
        header.append("Nível atual")
        for col, value in enumerate(header, start=1):
            ExcelFormatter.format_header_cell(ws.cell(row=1, column=col, value=value))

        for r, (group, serie) in enumerate(rows, start=2):
            source = serie or group
            serie_name = (serie or {}).get("serie_name") or group.get("grade_name")
            values: List[Any] = [
                group.get("school_name") or "-",
                serie_name or ("Todas" if view_by == "escola" else "-"),
                group.get("class_name") or ("Todas" if view_by != "turma" else "-"),
            ]
            points = {p.get("order"): p for p in source.get("points") or []}
            for ev in evaluations:
                point = points.get(ev.get("order")) or {}
                for key, _label in METRICAS:
                    values.append(point.get(key))
            values.append(source.get("current_level"))

            for col, value in enumerate(values, start=1):
                cell = ws.cell(row=r, column=col)
                if isinstance(value, float):
                    ExcelFormatter.format_number_cell(cell, value)
                else:
                    ExcelFormatter.format_data_cell(cell)
                    cell.value = "-" if value is None else value
        ExcelFormatter.auto_adjust_column_width(ws)
