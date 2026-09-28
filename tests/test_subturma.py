# -*- coding: utf-8 -*-
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.services.special_education import ADAP_EDUCATION_STAGE_ID
from app.services.student_enrollment_service import transfer_student_to_class
from app.services.subturma_service import (
    SubturmaError,
    SubturmaPermissionError,
    authorize_subturma_access,
    clear_subturma_if_class_changes,
    link_student_to_subturma,
    remove_subturma,
    unlink_student_from_subturma,
    validate_support_level_available,
)


def _turma(name="5º Ano", stage="regular", grade_id=None):
    grade = SimpleNamespace(name=name, education_stage_id=stage)
    return SimpleNamespace(id="turma-a", school_id="escola-1", grade_id=grade_id, grade=grade)


class TestSubturmaRegras(unittest.TestCase):
    def test_turma_especial_nao_recebe_subturma(self):
        adap = _turma(name="Suporte 1", stage=ADAP_EDUCATION_STAGE_ID)
        with self.assertRaisesRegex(SubturmaError, "Educação Especial"):
            validate_support_level_available(adap, 1, [])

    def test_nivel_invalido_e_nivel_duplicado(self):
        regular = _turma()
        with self.assertRaisesRegex(SubturmaError, "Nível inválido"):
            validate_support_level_available(regular, 4, [])
        with self.assertRaisesRegex(SubturmaError, "Já existe ADAP 2"):
            validate_support_level_available(regular, 2, [2])
        self.assertEqual(validate_support_level_available(regular, 3, [1]), 3)

    def test_aluno_de_outra_turma_nao_entra(self):
        sub = SimpleNamespace(id="sub-1", class_id="turma-a", support_level=1)
        aluno = SimpleNamespace(id="a1", class_id="turma-b", subturma_id=None)
        with self.assertRaisesRegex(SubturmaError, "não pertence a esta turma"):
            link_student_to_subturma(aluno, sub)

    def test_trocar_de_adap_substitui_a_subturma(self):
        aluno = SimpleNamespace(id="a1", class_id="turma-a", subturma_id="sub-1")
        adap2 = SimpleNamespace(id="sub-2", class_id="turma-a", support_level=2)
        link_student_to_subturma(aluno, adap2)
        self.assertEqual(aluno.subturma_id, "sub-2")
        self.assertEqual(aluno.class_id, "turma-a")

    def test_excluir_subturma_nao_muda_a_turma_do_aluno(self):
        deleted = []

        class Session:
            def delete(self, row):
                deleted.append(row)

        aluno = SimpleNamespace(id="a1", class_id="turma-a", subturma_id="sub-1")
        sub = SimpleNamespace(id="sub-1", class_id="turma-a")
        remove_subturma(Session(), sub)
        self.assertEqual(deleted, [sub])
        self.assertEqual(aluno.class_id, "turma-a")
        unlink_student_from_subturma(aluno, sub)
        self.assertIsNone(aluno.subturma_id)
        self.assertEqual(aluno.class_id, "turma-a")

    def test_atualizar_aluno_mesmo_class_id_mantem_subturma(self):
        aluno = SimpleNamespace(id="a1", class_id="turma-a", subturma_id="sub-1", name="Ana")
        changed = clear_subturma_if_class_changes(aluno, "turma-a")
        self.assertFalse(changed)
        self.assertEqual(aluno.subturma_id, "sub-1")
        self.assertEqual(aluno.class_id, "turma-a")
        aluno.name = "Ana Souza"

    def test_atualizar_aluno_outra_turma_zera_subturma(self):
        aluno = SimpleNamespace(id="a1", class_id="turma-a", subturma_id="sub-1")
        changed = clear_subturma_if_class_changes(aluno, "turma-b")
        self.assertTrue(changed)
        self.assertIsNone(aluno.subturma_id)

    def test_transferencia_de_turma_zera_subturma(self):
        school = SimpleNamespace(id="escola-1", city_id="city-1")
        student = SimpleNamespace(
            id="student-1",
            school_id="escola-1",
            class_id="turma-a",
            subturma_id="sub-1",
            grade_id="g1",
            user=SimpleNamespace(city_id="city-1"),
        )
        new_class = SimpleNamespace(id="turma-b", school_id="escola-1", grade_id="g1")

        class FakeField:
            def __init__(self, name):
                self.name = name

            def __eq__(self, other):
                return lambda item: str(getattr(item, self.name, None)) == str(other)

        class FakeSchool:
            id = FakeField("id")
            city_id = FakeField("city_id")

        class FakeQuery:
            def __init__(self, items):
                self._items = list(items)

            def filter(self, *predicates):
                filtered = self._items
                for predicate in predicates:
                    if callable(predicate):
                        filtered = [item for item in filtered if predicate(item)]
                return FakeQuery(filtered)

            def first(self):
                return self._items[0] if self._items else None

        class FakeSession:
            def query(self, _model):
                return FakeQuery([school])

        with patch("app.models.school.School", FakeSchool):
            with patch("app.services.student_enrollment_service.close_active_enrollment"):
                with patch("app.services.student_enrollment_service.open_enrollment"):
                    with patch(
                        "app.services.student_password_log_service.sync_password_logs_with_student_placement"
                    ):
                        transfer_student_to_class(
                            FakeSession(), student, new_class, update_user_city=True
                        )

        self.assertEqual(student.class_id, "turma-b")
        self.assertIsNone(student.subturma_id)


class TestSubturmaPermissao(unittest.TestCase):
    def test_professor_sem_vinculo_nao_lista(self):
        turma = SimpleNamespace(id="turma-a", school_id="escola-1")
        user = {"id": "prof-1", "role": "professor"}
        with patch("app.services.subturma_service.get_teacher_classes", return_value=["turma-b"]):
            with self.assertRaisesRegex(SubturmaPermissionError, "vínculo"):
                authorize_subturma_access(user, turma, write=False)

    def test_professor_com_vinculo_pode_listar_e_nao_gravar(self):
        turma = SimpleNamespace(id="turma-a", school_id="escola-1")
        user = {"id": "prof-1", "role": "professor"}
        with patch("app.services.subturma_service.get_teacher_classes", return_value=["turma-a"]):
            authorize_subturma_access(user, turma, write=False)
            with self.assertRaisesRegex(SubturmaPermissionError, "visualiza"):
                authorize_subturma_access(user, turma, write=True)

    def test_diretor_de_outra_escola_nao_grava(self):
        turma = SimpleNamespace(id="turma-a", school_id="escola-1")
        user = {"id": "dir-1", "role": "diretor"}
        with patch("app.services.subturma_service.get_manager_school", return_value="escola-2"):
            with self.assertRaises(SubturmaPermissionError):
                authorize_subturma_access(user, turma, write=True)


if __name__ == "__main__":
    unittest.main()
