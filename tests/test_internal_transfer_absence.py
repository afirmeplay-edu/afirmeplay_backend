import unittest

from app.services.evaluation_result_snapshot import (
    internal_transfer_ids_outside_class_group,
)


PEDRO = "pedro-ribeiro"
BENEDITO = "benedito-galdino"
LINO = "pedro-antonio-lino"
CLASS_A = "turma-a"
CLASS_B = "turma-b"
CLASS_C = "turma-c"
CLASS_A_LINO = "turma-a-lino"
CLASS_A_BENEDITO = "turma-a-benedito"

JOAO = "joao"
ANA = "ana"
ALBERTO = "alberto"
RAISSA = "raissa"
WILLYANNE = "willyanne"
KIARA = "kiara"
MESMA_TURMA = "mesma-turma"


class TestInternalTransferAbsence(unittest.TestCase):
    def test_mesma_turma_nao_remove(self):
        removed = internal_transfer_ids_outside_class_group(
            {MESMA_TURMA},
            {CLASS_A},
            {PEDRO},
            [(MESMA_TURMA, PEDRO, CLASS_A)],
        )
        self.assertEqual(removed, set())

    def test_transferencia_interna_joao_sai_do_universo_da_turma_atual(self):
        removed = internal_transfer_ids_outside_class_group(
            {JOAO, ALBERTO},
            {CLASS_A},
            {PEDRO},
            [(JOAO, PEDRO, CLASS_B)],
        )
        self.assertEqual(removed, {JOAO})

    def test_joao_permanece_no_universo_da_turma_do_snapshot(self):
        removed = internal_transfer_ids_outside_class_group(
            set(),
            {CLASS_B},
            {PEDRO},
            [(JOAO, PEDRO, CLASS_B)],
        )
        self.assertEqual(removed, set())

    def test_ana_sai_do_universo_da_turma_atual_e_nao_da_turma_do_snapshot(self):
        fora_da_b = internal_transfer_ids_outside_class_group(
            {ANA},
            {CLASS_B},
            {PEDRO},
            [(ANA, PEDRO, CLASS_C)],
        )
        fora_da_c = internal_transfer_ids_outside_class_group(
            set(),
            {CLASS_C},
            {PEDRO},
            [(ANA, PEDRO, CLASS_C)],
        )
        self.assertEqual(fora_da_b, {ANA})
        self.assertEqual(fora_da_c, set())

    def test_sem_resultado_alberto_e_raissa_continuam_no_universo(self):
        removed_a = internal_transfer_ids_outside_class_group(
            {ALBERTO, JOAO},
            {CLASS_A},
            {PEDRO},
            [(JOAO, PEDRO, CLASS_B)],
        )
        removed_c = internal_transfer_ids_outside_class_group(
            {RAISSA},
            {CLASS_C},
            {PEDRO},
            [],
        )
        self.assertNotIn(ALBERTO, removed_a)
        self.assertEqual(removed_c, set())

    def test_willyanne_sem_matricula_nao_entra_na_exclusao(self):
        removed = internal_transfer_ids_outside_class_group(
            set(),
            {CLASS_A},
            {PEDRO},
            [(WILLYANNE, PEDRO, CLASS_A)],
        )
        self.assertEqual(removed, set())

    def test_kiara_transferida_de_escola_nao_sai_do_universo_da_escola_nova(self):
        removed = internal_transfer_ids_outside_class_group(
            {KIARA},
            {CLASS_A_LINO},
            {LINO},
            [(KIARA, BENEDITO, CLASS_A_BENEDITO)],
        )
        self.assertEqual(removed, set())

    def test_kiara_permanece_na_escola_onde_fez_a_prova(self):
        removed = internal_transfer_ids_outside_class_group(
            set(),
            {CLASS_A_BENEDITO},
            {BENEDITO},
            [(KIARA, BENEDITO, CLASS_A_BENEDITO)],
        )
        self.assertEqual(removed, set())

    def test_grupo_com_as_turmas_da_escola_nao_remove_transferido_interno(self):
        removed = internal_transfer_ids_outside_class_group(
            {JOAO, ANA, ALBERTO, RAISSA},
            {CLASS_A, CLASS_B, CLASS_C},
            {PEDRO},
            [(JOAO, PEDRO, CLASS_B), (ANA, PEDRO, CLASS_C)],
        )
        self.assertEqual(removed, set())

    def test_resultado_na_turma_do_grupo_impede_exclusao(self):
        removed = internal_transfer_ids_outside_class_group(
            {JOAO},
            {CLASS_A},
            {PEDRO},
            [(JOAO, PEDRO, CLASS_B), (JOAO, PEDRO, CLASS_A)],
        )
        self.assertEqual(removed, set())
