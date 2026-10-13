# -*- coding: utf-8 -*-
"""Escopo impresso, pastas do ZIP e decisão de publicar o pacote."""
# Exec: python -m unittest tests.test_socioeconomic_print_package
import importlib.util
import unittest
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace


_MODULE = (
    Path(__file__).resolve().parents[1]
    / "app" / "socioeconomic_forms" / "services" / "print_package.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("socio_print_package", _MODULE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


print_package = _load()


def _form(**kwargs):
    defaults = {
        "form_type": "aluno-velho",
        "selected_schools": ["escola-a", "escola-b"],
        "selected_grades": ["serie-1"],
        "selected_classes": ["turma-1", "turma-2"],
        "filters": {},
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


class TestResolvePrintScope(unittest.TestCase):
    def test_keeps_every_class_and_school(self):
        form = _form(
            selected_classes=["turma-1", "turma-2", "turma-3"],
            filters={"turma": "turma-9,turma-8", "escola": "escola-ignorada"},
        )
        scope = print_package.resolve_print_scope(form)
        self.assertTrue(scope["printable"])
        self.assertEqual(scope["classes"], ["turma-9", "turma-8"])
        self.assertEqual(scope["schools"], ["escola-a", "escola-b"])
        self.assertIsNone(scope["municipio"])
        self.assertIsNone(scope["estado"])

    def test_selected_classes_stay_when_filter_has_none(self):
        scope = print_package.resolve_print_scope(_form())
        self.assertEqual(scope["classes"], ["turma-1", "turma-2"])
        self.assertEqual(scope["grades"], ["serie-1"])

    def test_geo_only_without_explicit_school(self):
        form = _form(
            selected_schools=[],
            filters={"municipio": "cidade-1", "estado": "RN", "serie": "serie-9"},
            selected_grades=[],
            selected_classes=[],
        )
        scope = print_package.resolve_print_scope(form)
        self.assertTrue(scope["printable"])
        self.assertEqual(scope["schools"], [])
        self.assertEqual(scope["grades"], ["serie-9"])
        self.assertEqual(scope["municipio"], "cidade-1")
        self.assertEqual(scope["estado"], "RN")

    def test_professor_and_empty_scope_are_not_printable(self):
        professor = print_package.resolve_print_scope(_form(form_type="professor"))
        self.assertFalse(professor["printable"])
        self.assertIn("aluno", print_package.scope_rejection_message(professor))

        empty = print_package.resolve_print_scope(
            _form(selected_grades=[], selected_classes=[], filters={})
        )
        self.assertFalse(empty["printable"])
        self.assertIn("séries ou turmas", print_package.scope_rejection_message(empty))


class TestZipLayout(unittest.TestCase):
    def _student(self, student_id, name="Maria da Silva"):
        return {
            "student_id": student_id,
            "name": name,
            "school_name": "Escola João XXIII",
            "grade_name": "9º Ano",
            "class_name": "Turma B",
            "municipality": "São José",
            "state": "RN",
        }

    def test_folders_and_homonym_suffix(self):
        first = self._student("8f3c2a10-6b4e-4d77-9a21-0c5e7b91d4aa")
        second = self._student("11111111-2222-3333-4444-55555555aabb")
        left = print_package.pdf_arcname(first)
        right = print_package.pdf_arcname(second)
        self.assertTrue(left.startswith("municipio_sao_jose/escola_escola_joao_xxiii/serie_9o_ano/turma_turma_b/"))
        self.assertNotEqual(left, right)
        self.assertTrue(left.endswith("_7b91d4aa.pdf"))
        self.assertTrue(right.endswith("_5555aabb.pdf"))

    def test_one_failure_still_packs_the_other(self):
        students = [
            self._student("aaaaaaaa-bbbb-cccc-dddd-eeeeeeee0001"),
            self._student("aaaaaaaa-bbbb-cccc-dddd-eeeeeeee0002", name="João"),
        ]

        def personalize(base_pdf, **kwargs):
            if kwargs["student_id"].endswith("0002"):
                raise RuntimeError("overlay")
            return b"%PDF-1.4 " + kwargs["student_id"].encode()

        import tempfile
        import os
        handle = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
        handle.close()
        try:
            stats = print_package.write_print_zip(
                handle.name,
                b"%PDF-base",
                "form-1",
                students,
                personalize=personalize,
            )
            self.assertEqual(stats["generated"], 1)
            self.assertEqual(stats["failed"], 1)
            self.assertEqual(stats["total"], 2)
            with zipfile.ZipFile(handle.name) as archive:
                names = archive.namelist()
            self.assertEqual(len(names), 1)
            self.assertIn("maria_da_silva", names[0])
        finally:
            os.remove(handle.name)

    def test_zero_successes_do_not_complete_or_replace_zip(self):
        stats = {"generated": 0, "failed": 2, "total": 2, "errors": ["a: x", "b: y"]}
        outcome = print_package.decide_print_outcome(stats, {"object_name": "novo.zip", "url": "http://x"})
        self.assertEqual(outcome["status"], "failed")
        self.assertFalse(outcome["replace_zip"])

        uploaded_nothing = print_package.decide_print_outcome(
            {"generated": 3, "failed": 0, "total": 3, "errors": []},
            None,
        )
        self.assertEqual(uploaded_nothing["status"], "failed")
        self.assertFalse(uploaded_nothing["replace_zip"])
        self.assertIn("pacote anterior", uploaded_nothing["error"])

    def test_partial_success_completes_when_upload_returns_object(self):
        outcome = print_package.decide_print_outcome(
            {"generated": 2, "failed": 1, "total": 3, "errors": ["id: boom"]},
            {"bucket": "socioeconomic-forms", "object_name": "f/runs/1.zip", "url": "http://zip"},
        )
        self.assertEqual(outcome["status"], "completed")
        self.assertTrue(outcome["replace_zip"])
        self.assertEqual(outcome["object_name"], "f/runs/1.zip")
        self.assertIn("1 de 3", outcome["error"])


class TestCoverAndConcurrency(unittest.TestCase):
    def test_single_city_on_cover_and_blank_when_mixed(self):
        one = print_package.cover_place([
            {"state": "RN", "municipality": "Natal"},
            {"state": "RN", "municipality": "Natal"},
        ])
        self.assertEqual(one.state, "RN")
        self.assertEqual(one.name, "Natal")

        mixed = print_package.cover_place(
            [
                {"state": "RN", "municipality": "Natal"},
                {"state": "RN", "municipality": "Parnamirim"},
            ],
            {"estado": "RN"},
        )
        self.assertEqual(mixed.state, "RN")
        self.assertEqual(mixed.name, "")

    def test_never_started_is_distinct_from_a_failed_run(self):
        self.assertFalse(print_package.print_package_was_started(None, None, None))
        self.assertFalse(print_package.print_package_was_started("", None, None))
        started = datetime(2026, 10, 13, 15, 0, 0)
        self.assertTrue(print_package.print_package_was_started("failed", None, started))
        self.assertTrue(print_package.print_package_was_started("processing", "run-1", started))
        self.assertTrue(print_package.print_package_was_started("completed", "run-1", started))

    def test_recent_pending_blocks_and_stale_processing_does_not(self):
        now = datetime(2026, 10, 13, 15, 0, 0)
        recent = now - timedelta(minutes=5)
        stale = now - timedelta(minutes=31)
        self.assertTrue(print_package.print_generation_in_progress("processing", recent, "PENDING", now))
        self.assertTrue(print_package.print_generation_in_progress("processing", recent, "STARTED", now))
        self.assertFalse(print_package.print_generation_in_progress("processing", recent, "SUCCESS", now))
        self.assertFalse(print_package.print_generation_in_progress("processing", stale, "PENDING", now))
        self.assertFalse(print_package.print_generation_in_progress("completed", recent, "STARTED", now))


if __name__ == "__main__":
    unittest.main()
