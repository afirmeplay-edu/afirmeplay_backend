# -*- coding: utf-8 -*-
"""Script de ausentes: backup/desfazer em disco antes dos UPDATE."""

import importlib.util
import json
from pathlib import Path


def _load_script_module():
    root = Path(__file__).resolve().parents[1]
    path = root / "scripts" / "recalculate_absent_subjects_answer_sheet.py"
    spec = importlib.util.spec_from_file_location("recalc_absent_script", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_write_backup_and_undo_creates_nonempty_files(tmp_path):
    mod = _load_script_module()
    rows = [
        {
            "schema": "city_abc",
            "id": "11111111-1111-1111-1111-111111111111",
            "grade": 3.5,
            "proficiency": 121.88,
            "classification": "Abaixo do Básico",
            "proficiency_by_subject": {
                "p": {"subject_name": "Português", "grade": 0.0, "proficiency": 0.0}
            },
        }
    ]
    backup_path, undo_path = mod._write_backup_and_undo(
        tmp_path,
        "147.79.87.213",
        15432,
        "afirmeplay_dev",
        rows,
    )
    assert backup_path.exists()
    assert undo_path.exists()
    assert backup_path.stat().st_size > 0
    assert undo_path.stat().st_size > 0
    payload = json.loads(backup_path.read_text(encoding="utf-8"))
    assert payload["database"].endswith("/afirmeplay_dev")
    assert len(payload["rows"]) == 1
    undo_txt = undo_path.read_text(encoding="utf-8")
    assert "UPDATE answer_sheet_results" in undo_txt
    assert rows[0]["id"] in undo_txt


def test_apply_updates_requires_prior_backup_contract():
    """Contrato documentado: apply_updates soh atualiza; backup e funcao separada."""
    mod = _load_script_module()
    assert callable(mod._write_backup_and_undo)
    assert callable(mod.apply_updates)
    assert callable(mod.collect_affected)
    # Ordem no main: collect -> (esperado) -> write backup -> apply -> commit
    src = (Path(__file__).resolve().parents[1] / "scripts" / "recalculate_absent_subjects_answer_sheet.py").read_text(
        encoding="utf-8"
    )
    i_main = src.index("def main() -> int:")
    main_src = src[i_main:]
    i_collect = main_src.index("affected, backup_rows, per_school = collect_affected(")
    i_backup = main_src.index("backup_path, undo_path = _write_backup_and_undo(")
    i_apply = main_src.index("updated = apply_updates(")
    assert i_collect < i_backup < i_apply


def test_cli_exige_city_slug_ou_todas_cidades():
    mod = _load_script_module()
    # argparse: city-slug e todas-cidades mutuamente exclusivos no main
    src = (Path(__file__).resolve().parents[1] / "scripts" / "recalculate_absent_subjects_answer_sheet.py").read_text(
        encoding="utf-8"
    )
    assert "--todas-cidades" in src
    assert "--esperado" in src
    assert "informe exatamente um de --city-slug" in src
