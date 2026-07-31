# -*- coding: utf-8 -*-
import unittest
from unittest.mock import patch

from app.services.class_peer_ranking_service import ClassPeerRankingService


class FakeArgs(dict):
    def get(self, key, default=None):
        return super().get(key, default)


class TestClassPeerRankingService(unittest.TestCase):
    def test_build_request_requires_scope_and_evaluation(self):
        with self.assertRaisesRegex(ValueError, "scope"):
            ClassPeerRankingService.build_request(FakeArgs({"evaluation_id": "e1"}))
        with self.assertRaisesRegex(ValueError, "evaluation_id"):
            ClassPeerRankingService.build_request(FakeArgs({"scope": "municipio", "municipio": "c1"}))

    def test_build_request_requires_municipio_or_escola(self):
        with self.assertRaisesRegex(ValueError, "municipio"):
            ClassPeerRankingService.build_request(
                FakeArgs({"scope": "municipio", "evaluation_id": "e1"})
            )
        with self.assertRaisesRegex(ValueError, "escola"):
            ClassPeerRankingService.build_request(
                FakeArgs({"scope": "escola", "evaluation_id": "e1"})
            )

    def test_build_request_ok(self):
        req = ClassPeerRankingService.build_request(
            FakeArgs(
                {
                    "scope": "municipio",
                    "evaluation_id": "e1",
                    "municipio": "city-1",
                    "serie": "g1",
                    "turma_nome": "A",
                    "turno": "Manhã",
                    "page": "2",
                    "per_page": "10",
                }
            )
        )
        self.assertEqual(req.scope, "municipio")
        self.assertEqual(req.evaluation_id, "e1")
        self.assertEqual(req.evaluation_ids, ["e1"])
        self.assertEqual(req.municipio, "city-1")
        self.assertEqual(req.serie, "g1")
        self.assertEqual(req.turma_nome, "A")
        self.assertEqual(req.turno, "Manhã")
        self.assertEqual(req.page, 2)
        self.assertEqual(req.per_page, 10)

    def test_build_request_evaluation_ids_csv(self):
        req = ClassPeerRankingService.build_request(
            FakeArgs(
                {
                    "scope": "municipio",
                    "evaluation_ids": "e1, e2, e1",
                    "municipio": "city-1",
                }
            )
        )
        self.assertEqual(req.evaluation_ids, ["e1", "e2"])
        self.assertEqual(req.evaluation_id, "e1")

    def test_peer_key_normalizes_name_and_shift(self):
        self.assertEqual(
            ClassPeerRankingService._peer_key("A", "Manhã"),
            ClassPeerRankingService._peer_key(" a ", "manha"),
        )
        self.assertNotEqual(
            ClassPeerRankingService._peer_key("A", "Manhã"),
            ClassPeerRankingService._peer_key("A", "Tarde"),
        )

    def test_class_and_student_ranking_order_and_pagination(self):
        rows = [
            {
                "student_id": "s1",
                "name": "Ana",
                "school_id": "sch1",
                "school_name": "Escola X",
                "class_id": "c1",
                "class_name": "A",
                "shift": "Manhã",
                "serie_id": "g1",
                "serie_name": "5º Ano",
                "grade": 7.0,
                "proficiency": 300.0,
                "classification": "Básico",
                "correct_answers": 10,
                "total_questions": 20,
                "score_percentage": 50.0,
                "subject_results": {
                    "math": {
                        "subject_name": "Matemática",
                        "grade": 7.0,
                        "proficiency": 300.0,
                        "classification": "Básico",
                        "correct_answers": 5,
                        "total_questions": 10,
                    }
                },
            },
            {
                "student_id": "s2",
                "name": "Bruno",
                "school_id": "sch2",
                "school_name": "Escola Y",
                "class_id": "c2",
                "class_name": "A",
                "shift": "Manhã",
                "serie_id": "g1",
                "serie_name": "5º Ano",
                "grade": 8.5,
                "proficiency": 350.0,
                "classification": "Adequado",
                "correct_answers": 15,
                "total_questions": 20,
                "score_percentage": 75.0,
                "subject_results": {
                    "math": {
                        "subject_name": "Matemática",
                        "grade": 8.5,
                        "proficiency": 350.0,
                        "classification": "Adequado",
                        "correct_answers": 8,
                        "total_questions": 10,
                    }
                },
            },
            {
                "student_id": "s3",
                "name": "Carla",
                "school_id": "sch2",
                "school_name": "Escola Y",
                "class_id": "c2",
                "class_name": "A",
                "shift": "Manhã",
                "serie_id": "g1",
                "serie_name": "5º Ano",
                "grade": 9.0,
                "proficiency": 380.0,
                "classification": "Avançado",
                "correct_answers": 18,
                "total_questions": 20,
                "score_percentage": 90.0,
                "subject_results": {},
            },
        ]
        req = ClassPeerRankingService.build_request(
            FakeArgs(
                {
                    "scope": "municipio",
                    "evaluation_id": "e1",
                    "municipio": "city-1",
                    "page": "1",
                    "per_page": "2",
                }
            )
        )
        with patch.object(
            ClassPeerRankingService,
            "_classification",
            return_value="Básico",
        ), patch(
            "app.services.class_peer_ranking_service.aggregated_grade_from_proficiency",
            side_effect=lambda prof, *_a, **_k: float(prof or 0) / 50.0,
        ), patch(
            "app.services.class_peer_ranking_service.hierarchical_mean_grade_and_proficiency",
            side_effect=lambda results, *_a, **_k: (
                sum(float(r.grade) for r in results) / len(results),
                sum(float(r.proficiency) for r in results) / len(results),
            ),
        ):
            sections = ClassPeerRankingService._build_sections(rows, req)

        self.assertEqual(len(sections), 1)
        peers = sections[0]["peer_groups"]
        self.assertEqual(len(peers), 1)
        peer = peers[0]
        self.assertEqual(peer["peer_key"], "a|manha")
        self.assertEqual(peer["class_ranking"][0]["school_name"], "Escola Y")
        self.assertEqual(peer["class_ranking"][0]["position"], 1)
        self.assertEqual(peer["student_ranking"][0]["name"], "Carla")
        self.assertEqual(len(peer["student_ranking"]), 2)
        self.assertEqual(peer["students_pagination"]["total"], 3)
        self.assertEqual(peer["students_pagination"]["total_pages"], 2)

    def test_portuguese_correct_answers_detects_subject(self):
        subjects = [
            {"subject_name": "Matemática", "correct_answers": 9},
            {"subject_name": "Língua Portuguesa", "correct_answers": 7},
        ]
        self.assertEqual(ClassPeerRankingService._portuguese_correct_answers(subjects), 7)
        self.assertEqual(ClassPeerRankingService._portuguese_correct_answers([]), 0)
        self.assertEqual(
            ClassPeerRankingService._portuguese_correct_answers(
                [{"subject_name": "Português", "correct_answers": 4}]
            ),
            4,
        )

    def test_raw_correct_sum_from_subjects_and_fallback(self):
        subjects = [
            {"subject_name": "Português", "correct_answers": 8},
            {"subject_name": "Matemática", "correct_answers": 6},
            {"subject_name": "Ciências", "correct_answers": 6},
            {"subject_name": "História", "correct_answers": 5},
        ]
        self.assertEqual(ClassPeerRankingService._raw_correct_sum(subjects, 99), 25)
        self.assertEqual(ClassPeerRankingService._raw_correct_sum([], 17), 17)
        self.assertEqual(ClassPeerRankingService._raw_correct_sum(None, 11), 11)

    def test_school_display_name_ensino_medio_only(self):
        self.assertEqual(
            ClassPeerRankingService._school_display_name("LUZIÁPOLIS", "Ensino Médio"),
            "LUZIÁPOLIS – ENSINO MÉDIO",
        )
        self.assertEqual(
            ClassPeerRankingService._school_display_name("Escola X", "Anos Iniciais"),
            "Escola X",
        )
        self.assertEqual(
            ClassPeerRankingService._school_display_name("Campus Y", "Ensino Superior"),
            "Campus Y – SUPERIOR",
        )

    def test_student_ranking_raw_sum_portuguese_and_name(self):
        """Evidências: soma 3+ disciplinas, empate PT, empate nome, fallback subjects vazio, EM."""
        rows = [
            {
                "student_id": "s-sum",
                "name": "Zuleica",
                "school_id": "sch1",
                "school_name": "Escola Alpha",
                "class_id": "c1",
                "class_name": "A",
                "shift": "Manhã",
                "serie_id": "g1",
                "serie_name": "5º Ano",
                "grade": 1.0,
                "proficiency": 50.0,
                "classification": "Básico",
                "correct_answers": 99,
                "total_questions": 40,
                "score_percentage": 10.0,
                "course_name": "Anos Iniciais",
                "subject_results": {
                    "pt": {"subject_name": "Português", "correct_answers": 8, "total_questions": 10},
                    "m": {"subject_name": "Matemática", "correct_answers": 6, "total_questions": 10},
                    "c": {"subject_name": "Ciências", "correct_answers": 6, "total_questions": 10},
                    "h": {"subject_name": "História", "correct_answers": 5, "total_questions": 10},
                },
            },
            {
                "student_id": "s-pt-low",
                "name": "Bruno",
                "school_id": "sch1",
                "school_name": "Escola Alpha",
                "class_id": "c1",
                "class_name": "A",
                "shift": "Manhã",
                "serie_id": "g1",
                "serie_name": "5º Ano",
                "grade": 9.0,
                "proficiency": 900.0,
                "classification": "Avançado",
                "correct_answers": 20,
                "total_questions": 20,
                "score_percentage": 100.0,
                "course_name": "Anos Iniciais",
                "subject_results": {
                    "pt": {"subject_name": "Língua Portuguesa", "correct_answers": 5, "total_questions": 10},
                    "m": {"subject_name": "Matemática", "correct_answers": 15, "total_questions": 10},
                },
            },
            {
                "student_id": "s-pt-high",
                "name": "Ana",
                "school_id": "sch1",
                "school_name": "Escola Alpha",
                "class_id": "c1",
                "class_name": "A",
                "shift": "Manhã",
                "serie_id": "g1",
                "serie_name": "5º Ano",
                "grade": 2.0,
                "proficiency": 100.0,
                "classification": "Básico",
                "correct_answers": 20,
                "total_questions": 20,
                "score_percentage": 100.0,
                "course_name": "Anos Iniciais",
                "subject_results": {
                    "pt": {"subject_name": "Português", "correct_answers": 12, "total_questions": 10},
                    "m": {"subject_name": "Matemática", "correct_answers": 8, "total_questions": 10},
                },
            },
            {
                "student_id": "s-name-a",
                "name": "Carla",
                "school_id": "sch2",
                "school_name": "LUZIÁPOLIS",
                "class_id": "c2",
                "class_name": "A",
                "shift": "Manhã",
                "serie_id": "g1",
                "serie_name": "1ª Série EM",
                "grade": 5.0,
                "proficiency": 200.0,
                "classification": "Básico",
                "correct_answers": 15,
                "total_questions": 20,
                "score_percentage": 75.0,
                "course_name": "Ensino Médio",
                "subject_results": {
                    "pt": {"subject_name": "Português", "correct_answers": 7, "total_questions": 10},
                    "m": {"subject_name": "Matemática", "correct_answers": 8, "total_questions": 10},
                },
            },
            {
                "student_id": "s-name-b",
                "name": "Beatriz",
                "school_id": "sch2",
                "school_name": "LUZIÁPOLIS",
                "class_id": "c2",
                "class_name": "A",
                "shift": "Manhã",
                "serie_id": "g1",
                "serie_name": "1ª Série EM",
                "grade": 5.0,
                "proficiency": 200.0,
                "classification": "Básico",
                "correct_answers": 15,
                "total_questions": 20,
                "score_percentage": 75.0,
                "course_name": "Ensino Médio",
                "subject_results": {
                    "pt": {"subject_name": "Português", "correct_answers": 7, "total_questions": 10},
                    "m": {"subject_name": "Matemática", "correct_answers": 8, "total_questions": 10},
                },
            },
            {
                "student_id": "s-fallback",
                "name": "Diego",
                "school_id": "sch3",
                "school_name": "Escola Beta",
                "class_id": "c3",
                "class_name": "A",
                "shift": "Manhã",
                "serie_id": "g1",
                "serie_name": "5º Ano",
                "grade": 9.5,
                "proficiency": 380.0,
                "classification": "Avançado",
                "correct_answers": 18,
                "total_questions": 20,
                "score_percentage": 90.0,
                "course_name": "Anos Iniciais",
                "subject_results": {},
            },
        ]
        ranking = ClassPeerRankingService._build_student_ranking(rows)
        by_id = {row["student_id"]: row for row in ranking}

        # 1) Soma 8+6+6+5 = 25 a partir de subjects[] (ignora correct_answers=99)
        self.assertEqual(by_id["s-sum"]["raw_correct_answers"], 25)
        self.assertEqual(len(by_id["s-sum"]["subjects"]), 4)

        # 2) Empate soma 20: Ana (PT 12) acima de Bruno (PT 5)
        # 3) Empate soma 15 e PT 7: Beatriz antes de Carla (alfabético)
        # 4) subjects vazio: Diego usa fallback 18
        # Ordem: Zuleica(25), Ana(20), Bruno(20), Diego(18), Beatriz(15), Carla(15)
        self.assertEqual(
            [row["name"] for row in ranking],
            ["Zuleica", "Ana", "Bruno", "Diego", "Beatriz", "Carla"],
        )
        self.assertEqual(by_id["s-fallback"]["raw_correct_answers"], 18)
        self.assertEqual(by_id["s-fallback"]["subjects"], [])

        # 5) Ensino Médio → sufixo na escola
        self.assertEqual(by_id["s-name-a"]["school_display_name"], "LUZIÁPOLIS – ENSINO MÉDIO")
        self.assertEqual(by_id["s-name-b"]["school_display_name"], "LUZIÁPOLIS – ENSINO MÉDIO")
        self.assertEqual(by_id["s-sum"]["school_display_name"], "Escola Alpha")

        # proficiency/grade preservados (não usados no sort, mas presentes)
        self.assertEqual(by_id["s-pt-low"]["proficiency"], 900.0)
        self.assertEqual(by_id["s-pt-low"]["grade"], 9.0)


if __name__ == "__main__":
    unittest.main()
