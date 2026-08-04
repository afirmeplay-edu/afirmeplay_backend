import unittest
from unittest.mock import patch

from app.services.ranking_report_service import RankingReportService
from app.routes.ranking_routes import parse_ranking_request_args, validate_ranking_filters


class FakeArgs(dict):
    def get(self, key, default=None):
        return super().get(key, default)


class TestRankingReportService(unittest.TestCase):
    def test_build_request_rejects_invalid_ranking_type(self):
        with self.assertRaisesRegex(ValueError, "ranking_type inválido"):
            RankingReportService.build_request("foo")

    def test_build_request_accepts_valid_types(self):
        for rt in ("general", "specific_evaluation", "specific_answer_sheet", "teachers"):
            req = RankingReportService.build_request(rt, page=1, per_page=10, filters={})
            self.assertEqual(req.ranking_type, rt)

    def test_specific_evaluation_requires_evaluation_id(self):
        req = RankingReportService.build_request("specific_evaluation", filters={})
        with patch.object(RankingReportService, "_resolve_scope", return_value={"scope": "municipio"}):
            with self.assertRaisesRegex(ValueError, "evaluation_id"):
                RankingReportService.get_report({"role": "admin"}, req)

    def test_specific_answer_sheet_requires_answer_sheet_id(self):
        req = RankingReportService.build_request("specific_answer_sheet", filters={})
        with patch.object(RankingReportService, "_resolve_scope", return_value={"scope": "municipio"}):
            with self.assertRaisesRegex(ValueError, "answer_sheet_id"):
                RankingReportService.get_report({"role": "admin"}, req)

    def test_dispatches_general(self):
        req = RankingReportService.build_request("general", filters={})
        fake_payload = {"ranking_type": "general", "items": []}
        with patch.object(RankingReportService, "_resolve_scope", return_value={"scope": "municipio"}):
            with patch.object(RankingReportService, "_general_ranking", return_value=fake_payload) as general_mock:
                payload = RankingReportService.get_report({"role": "admin"}, req)
        general_mock.assert_called_once()
        self.assertEqual(payload, fake_payload)

    def test_dispatches_teachers(self):
        req = RankingReportService.build_request("teachers", filters={})
        fake_payload = {"ranking_type": "teachers", "items": []}
        with patch.object(RankingReportService, "_resolve_scope", return_value={"scope": "escola"}):
            with patch.object(RankingReportService, "_teacher_ranking", return_value=fake_payload) as teacher_mock:
                payload = RankingReportService.get_report({"role": "diretor"}, req)
        teacher_mock.assert_called_once()
        self.assertEqual(payload, fake_payload)

    def test_general_ranking_uses_page_offset(self):
        req = RankingReportService.build_request("general", page=2, per_page=10, filters={})
        with patch.object(RankingReportService, "_resolve_scope", return_value={"scope": "municipio"}):
            with patch.object(
                RankingReportService,
                "_build_school_general_rows",
                return_value=[
                    {
                        "school_id": "s1",
                        "school_name": "Escola 1",
                        "average_score": 7.1,
                        "average_proficiency": 260.4,
                        "classification": "Básico",
                        "students_count": 20,
                        "total_students": 25,
                        "participating_students": 15,
                        "participation_rate": 60.0,
                        "series": [
                            {
                                "grade_id": "g1",
                                "grade_name": "1º Ano",
                                "average_score": 7.1,
                                "average_proficiency": 260.4,
                                "classification": "Básico",
                                "students_count": 20,
                                "total_students": 25,
                                "participating_students": 15,
                            }
                        ],
                    }
                ],
            ):
                with patch("app.services.ranking_report_service.DashboardService.get_school_ranking_card") as school_card_mock:
                    with patch("app.services.ranking_report_service.DashboardService.get_class_ranking_card") as class_mock:
                        with patch("app.services.ranking_report_service.DashboardService.get_ranking_alunos") as ranking_mock:
                            school_card_mock.return_value = {"ranking": [], "total": 0}
                            class_mock.return_value = {"ranking": [], "total": 0}
                            ranking_mock.return_value = {"ranking": [], "total": 123}
                            payload = RankingReportService.get_report({"role": "admin"}, req)
        ranking_mock.assert_called_once_with({"scope": "municipio"}, limit=500, offset=0, filters={})
        self.assertEqual(payload["totals"]["count"], 1)
        self.assertIn("general_rankings", payload)
        self.assertIn("visibility", payload["general_rankings"])
        self.assertEqual(payload["general_rankings"]["visibility"]["schools_by_course"], True)
        self.assertEqual(payload["general_rankings"]["visibility"]["students_by_course"], True)
        self.assertEqual(payload["students_totals"]["count"], 123)
        self.assertIn("overview", payload)
        self.assertIn("municipal_ranking", payload)
        self.assertIn("school_class_ranking", payload)
        self.assertIn("teachers_top", payload)

    def test_general_ranking_with_escola_and_serie_filters(self):
        req = RankingReportService.build_request(
            "general",
            page=1,
            per_page=10,
            filters={
                "escola": "school-1",
                "serie": "grade-1",
                "evaluation_id": "eval-1",
            },
        )
        school_row = {
            "school_id": "school-1",
            "school_name": "Escola 1",
            "average_score": 7.1,
            "average_proficiency": 260.4,
            "classification": "Básico",
            "students_count": 20,
            "total_students": 25,
            "participating_students": 15,
            "participation_rate": 60.0,
            "series": [
                {
                    "grade_id": "grade-1",
                    "grade_name": "4º Ano",
                    "average_score": 7.1,
                    "average_proficiency": 260.4,
                    "classification": "Básico",
                    "students_count": 20,
                    "total_students": 25,
                    "participating_students": 15,
                }
            ],
        }
        with patch.object(RankingReportService, "_resolve_scope", return_value={"scope": "escola", "school_ids": ["school-1"]}):
            with patch.object(RankingReportService, "_build_school_general_rows", return_value=[school_row]):
                with patch("app.services.ranking_report_service.DashboardService.get_school_ranking_card") as school_card_mock:
                    with patch.object(RankingReportService, "_build_evaluation_class_rows", return_value=[]):
                        with patch("app.services.ranking_report_service.DashboardService.get_ranking_alunos") as ranking_mock:
                            with patch("app.services.ranking_report_service.db.session.query") as grade_query_mock:
                                school_card_mock.return_value = {"ranking": [], "total": 0}
                                ranking_mock.return_value = {"ranking": [], "total": 0}
                                grade_query_mock.return_value.filter.return_value.first.return_value = type(
                                    "GradeRow", (), {"name": "4º Ano"}
                                )()
                                payload = RankingReportService.get_report({"role": "admin"}, req)
        self.assertEqual(payload["general_rankings"]["visibility"]["schools_by_course"], False)
        self.assertEqual(payload["grade_options"], [{"id": "grade-1", "name": "4º Ano"}])
        self.assertIn("classes_ranking", payload)


class TestRankingRoutesParse(unittest.TestCase):
    def test_parse_defaults(self):
        ranking_type, page, per_page, filters = parse_ranking_request_args(FakeArgs())
        self.assertEqual(ranking_type, "general")
        self.assertEqual(page, 1)
        self.assertEqual(per_page, 20)
        self.assertIsNone(filters["evaluation_id"])
        self.assertIsNone(filters["avaliacao"])

    def test_parse_explicit_values(self):
        args = FakeArgs(
            ranking_type="specific_evaluation",
            page="2",
            per_page="30",
            municipio="city-1",
            avaliacao="eval-1",
        )
        ranking_type, page, per_page, filters = parse_ranking_request_args(args)
        self.assertEqual(ranking_type, "specific_evaluation")
        self.assertEqual(page, 2)
        self.assertEqual(per_page, 30)
        self.assertEqual(filters["municipio"], "city-1")
        self.assertEqual(filters["evaluation_id"], "eval-1")

    def test_parse_preserves_legacy_evaluation_id(self):
        args = FakeArgs(ranking_type="specific_evaluation", evaluation_id="eval-legacy")
        _, _, _, filters = parse_ranking_request_args(args)
        self.assertEqual(filters["evaluation_id"], "eval-legacy")

    def test_parse_answer_sheet_uses_avaliacao_or_gabarito(self):
        args = FakeArgs(ranking_type="specific_answer_sheet", avaliacao="gab-1")
        _, _, _, filters = parse_ranking_request_args(args)
        self.assertEqual(filters["answer_sheet_id"], "gab-1")

        args = FakeArgs(ranking_type="specific_answer_sheet", gabarito_id="gab-2")
        _, _, _, filters = parse_ranking_request_args(args)
        self.assertEqual(filters["answer_sheet_id"], "gab-2")

    def test_parse_ignores_all_values(self):
        args = FakeArgs(estado="all", municipio="all", escola="all", avaliacao="all")
        _, _, _, filters = parse_ranking_request_args(args)
        self.assertIsNone(filters["estado"])
        self.assertIsNone(filters["municipio"])
        self.assertIsNone(filters["escola"])
        self.assertIsNone(filters["avaliacao"])


class TestTeachersTopSection(unittest.TestCase):
    def test_teachers_top_lists_all_participating_teachers_not_only_top_10(self):
        teacher_rows = [
            {
                "teacher_id": f"teacher-{idx}",
                "teacher_name": f"Professor {idx}",
                "teacher_email": f"prof{idx}@example.com",
                "average_proficiency": float(800 - idx * 10),
                "average_score": float(9 - idx * 0.1),
                "classification": "Avançado",
                "grade_names": ["5º Ano"],
            }
            for idx in range(15)
        ]
        with patch.object(RankingReportService, "_build_school_grade_teacher_map", return_value={}):
            with patch.object(RankingReportService, "_build_teacher_school_map", return_value={}):
                sections = RankingReportService._build_model_sections(
                    school_rows=[],
                    schools_by_course_sections=[],
                    series_by_school_sections=[],
                    classes_by_series_sections=[],
                    class_rows=[],
                    teacher_rows=teacher_rows,
                    filters={"evaluation_id": "eval-1"},
                )
        items = sections["teachers_top"]["items"]
        self.assertEqual(len(items), 15)
        self.assertEqual(sections["teachers_top"]["totals"]["count"], 15)
        self.assertEqual(items[0]["position"], 1)
        self.assertEqual(items[-1]["position"], 15)

    def test_teachers_top_uses_real_adequado_avancado_student_counts(self):
        teacher_rows = [
            {
                "teacher_id": "teacher-1",
                "teacher_name": "Professor 1",
                "teacher_email": "prof1@example.com",
                "average_proficiency": 520.0,
                "average_score": 7.5,
                "classification": "Adequado",
                "grade_names": ["5º Ano"],
            }
        ]
        teacher_student_metrics = {
            "teacher-1": {
                "participating_students": 20,
                "adequado_avancado_count": 8,
            }
        }
        with patch.object(RankingReportService, "_build_school_grade_teacher_map", return_value={}):
            with patch.object(RankingReportService, "_build_teacher_school_map", return_value={}):
                sections = RankingReportService._build_model_sections(
                    school_rows=[],
                    schools_by_course_sections=[],
                    series_by_school_sections=[],
                    classes_by_series_sections=[],
                    class_rows=[],
                    teacher_rows=teacher_rows,
                    filters={"evaluation_id": "eval-1"},
                    teacher_student_metrics=teacher_student_metrics,
                )
        item = sections["teachers_top"]["items"][0]
        self.assertEqual(item["adequado_avancado_count"], 8)
        self.assertEqual(item["participating_students"], 20)
        self.assertEqual(item["adequado_avancado_pct"], 40.0)

    def test_classification_for_teacher_uses_course_and_subject_not_legacy_thresholds(self):
        with patch.object(
            RankingReportService,
            "_resolve_subject_name_for_filters",
            return_value="Língua Portuguesa",
        ):
            classification = RankingReportService._classification_for_teacher(
                average_proficiency=300.0,
                grade_names=["6º Ano"],
                filters={"evaluation_id": "eval-1"},
            )
        self.assertEqual(classification, "Adequado")

    def test_teachers_top_recomputes_level_tag_from_proficiency(self):
        teacher_rows = [
            {
                "teacher_id": "teacher-1",
                "teacher_name": "Professor 1",
                "teacher_email": "prof1@example.com",
                "average_proficiency": 300.0,
                "average_score": 7.0,
                "classification": "Básico",
                "grade_names": ["6º Ano"],
            }
        ]
        with patch.object(RankingReportService, "_build_school_grade_teacher_map", return_value={}):
            with patch.object(RankingReportService, "_build_teacher_school_map", return_value={}):
                with patch.object(
                    RankingReportService,
                    "_resolve_subject_name_for_filters",
                    return_value="Língua Portuguesa",
                ):
                    sections = RankingReportService._build_model_sections(
                        school_rows=[],
                        schools_by_course_sections=[],
                        series_by_school_sections=[],
                        classes_by_series_sections=[],
                        class_rows=[],
                        teacher_rows=teacher_rows,
                        filters={"evaluation_id": "eval-1"},
                    )
        item = sections["teachers_top"]["items"][0]
        self.assertEqual(item["classification"], "Adequado")
        self.assertEqual(item["level_tag"], "Adequado")

    def test_teachers_top_derives_score_from_proficiency_not_avg_grades(self):
        # AVG das notas dos alunos seria ~8.5 (com teto em 10); canônico = calculate_grade(287.4) = 8.7
        teacher_rows = [
            {
                "teacher_id": "teacher-1",
                "teacher_name": "IZA KEYLLA",
                "teacher_email": "iza@example.com",
                "average_proficiency": 287.4,
                "average_score": 8.5,
                "classification": "Avançado",
                "grade_names": ["1º Ano"],
            }
        ]
        with patch.object(RankingReportService, "_build_school_grade_teacher_map", return_value={}):
            with patch.object(RankingReportService, "_build_teacher_school_map", return_value={}):
                with patch.object(
                    RankingReportService,
                    "_resolve_subject_name_for_filters",
                    return_value="Português",
                ):
                    sections = RankingReportService._build_model_sections(
                        school_rows=[],
                        schools_by_course_sections=[],
                        series_by_school_sections=[],
                        classes_by_series_sections=[],
                        class_rows=[],
                        teacher_rows=teacher_rows,
                        filters={
                            "evaluation_id": "eval-1",
                            "disciplina": "subj-lp",
                        },
                    )
        item = sections["teachers_top"]["items"][0]
        self.assertEqual(item["average_proficiency"], 287.4)
        self.assertEqual(item["average_score"], 8.7)
        self.assertNotEqual(item["average_score"], 8.5)

    def test_teachers_top_series_class_name_includes_grade_and_class(self):
        teacher_rows = [
            {
                "teacher_id": "teacher-1",
                "teacher_name": "Professor 1",
                "teacher_email": "prof1@example.com",
                "average_proficiency": 300.0,
                "average_score": 7.0,
                "classification": "Básico",
                "grade_names": ["4º Ano"],
            }
        ]
        with patch.object(RankingReportService, "_build_school_grade_teacher_map", return_value={}):
            with patch.object(RankingReportService, "_build_teacher_school_map", return_value={}):
                with patch.object(
                    RankingReportService,
                    "_build_teacher_series_class_labels_map",
                    return_value={"teacher-1": ["4º Ano - Turma A", "4º Ano - Turma B"]},
                ):
                    sections = RankingReportService._build_model_sections(
                        school_rows=[],
                        schools_by_course_sections=[],
                        series_by_school_sections=[],
                        classes_by_series_sections=[],
                        class_rows=[],
                        teacher_rows=teacher_rows,
                        filters={"evaluation_id": "eval-1"},
                    )
        self.assertEqual(
            sections["teachers_top"]["items"][0]["series_class_name"],
            "4º Ano - Turma A, 4º Ano - Turma B",
        )


class TestClassRankingAdequadoAvancado(unittest.TestCase):
    def test_class_ranking_payload_propagates_adequado_avancado_counts(self):
        class_rows = [
            {
                "class_id": "class-1",
                "turma": "Turma A",
                "serie": "4º Ano",
                "media": 7.5,
                "average_score": 7.5,
                "average_proficiency": 520.0,
                "participating_students": 20,
                "total_students": 22,
                "participation_rate": 90.9,
                "adequado_avancado_count": 8,
                "adequado_avancado_pct": 40.0,
                "classification": "Adequado",
                "acerto_percent": 75.0,
                "conclusao": 90.9,
                "avaliacoes": 1,
            }
        ]
        payload = RankingReportService._build_class_ranking_payload(class_rows, filters={"serie": ""})
        self.assertEqual(len(payload["items"]), 1)
        item = payload["items"][0]
        self.assertEqual(item["adequado_avancado_count"], 8)
        self.assertEqual(item["adequado_avancado_pct"], 40.0)


class TestDisciplineOptions(unittest.TestCase):
    def test_looks_like_course_label(self):
        self.assertTrue(RankingReportService._looks_like_course_label("Anos Iniciais"))
        self.assertTrue(RankingReportService._looks_like_course_label("Curso: 5º Ano"))
        self.assertFalse(RankingReportService._looks_like_course_label("Língua Portuguesa"))

    def test_resolve_discipline_options_empty_without_instrument(self):
        options = RankingReportService._resolve_discipline_options({})
        self.assertEqual(options, [])


class TestGradeClassLabel(unittest.TestCase):
    def test_format_with_grade_and_class(self):
        label = RankingReportService._format_grade_class_label("5º Ano", "Turma A")
        self.assertEqual(label, "5º Ano - Turma A")

    def test_format_teacher_series_class_display_truncates_long_lists(self):
        label = RankingReportService._format_teacher_series_class_display(
            ["4º Ano - A", "4º Ano - B", "4º Ano - C", "4º Ano - D"]
        )
        self.assertEqual(label, "4º Ano - A, 4º Ano - B, 4º Ano - C (+1)")

    def test_format_without_class_returns_grade_only(self):
        label = RankingReportService._format_grade_class_label("5º Ano", "")
        self.assertEqual(label, "5º Ano")

    def test_build_best_class_by_school_picks_highest_score(self):
        class_rows = [
            {
                "school_id": "s1",
                "serie": "4º Ano",
                "turma": "Turma B",
                "media": 6.0,
                "average_proficiency": 200.0,
            },
            {
                "school_id": "s1",
                "serie": "5º Ano",
                "turma": "Turma A",
                "media": 8.5,
                "average_proficiency": 250.0,
            },
        ]
        best = RankingReportService._build_best_class_by_school(class_rows)
        self.assertEqual(best["s1"]["label"], "5º Ano - Turma A")
        self.assertEqual(best["s1"]["grade"], "5º Ano")
        self.assertEqual(best["s1"]["turma"], "Turma A")


class TestClassificationFromProficiency(unittest.TestCase):
    def test_anos_finais_adequado_not_basico_with_old_thresholds(self):
        result = RankingReportService._classification_from_proficiency(
            300.0,
            course_label="Anos Finais",
            subject_name="Língua Portuguesa",
        )
        self.assertEqual(result, "Adequado")

    def test_anos_iniciais_avancado(self):
        result = RankingReportService._classification_from_proficiency(
            280.0,
            course_label="Anos Iniciais",
            subject_name="GERAL",
        )
        self.assertEqual(result, "Avançado")


class TestInferSchoolStatus(unittest.TestCase):
    def test_basico_is_desenvolvimento(self):
        self.assertEqual(RankingReportService._infer_school_status("Básico"), "desenvolvimento")
        self.assertEqual(RankingReportService._infer_school_status("Basico"), "desenvolvimento")

    def test_adequado_and_avancado_are_destaque(self):
        self.assertEqual(RankingReportService._infer_school_status("Adequado"), "destaque")
        self.assertEqual(RankingReportService._infer_school_status("Avançado"), "destaque")

    def test_abaixo_is_atencao(self):
        self.assertEqual(RankingReportService._infer_school_status("Abaixo do Básico"), "atencao")


class TestDisciplineStorageKey(unittest.TestCase):
    def test_match_by_exact_key(self):
        key_names = {"sub-1": "Língua Portuguesa", "sub-2": "Matemática"}
        matched = RankingReportService._match_discipline_storage_key(
            "sub-1",
            key_names,
            subject_label="Língua Portuguesa",
        )
        self.assertEqual(matched, "sub-1")

    def test_match_by_subject_label_when_option_id_differs(self):
        key_names = {"block_0": "Matemática", "uuid-real": "Língua Portuguesa"}
        matched = RankingReportService._match_discipline_storage_key(
            "option-from-questions",
            key_names,
            subject_label="Matemática",
        )
        self.assertEqual(matched, "block_0")

    def test_register_discipline_option_skips_course_labels(self):
        bucket: dict[str, str] = {}
        with patch.object(
            RankingReportService,
            "_subject_display_name",
            side_effect=lambda sid, fb="": fb or "fallback",
        ):
            RankingReportService._register_discipline_option(bucket, "sub-1", "Anos Iniciais")
            RankingReportService._register_discipline_option(bucket, "sub-2", "Língua Portuguesa")
        self.assertNotIn("sub-1", bucket)
        self.assertEqual(bucket.get("sub-2"), "Língua Portuguesa")

    def test_extract_keys_skips_geral(self):
        payload = {
            "geral": {"subject_name": "Geral", "grade": 8.0},
            "sub-1": {"subject_name": "Ciências", "grade": 7.5},
        }
        keys = RankingReportService._extract_discipline_keys_from_payload(payload)
        self.assertEqual(keys, {"sub-1": "Ciências"})


class TestAdequadoAvancadoClassification(unittest.TestCase):
    def test_matches_adequado_and_avancado(self):
        self.assertTrue(RankingReportService._is_adequado_or_avancado_classification("Adequado"))
        self.assertTrue(RankingReportService._is_adequado_or_avancado_classification("Avançado"))
        self.assertTrue(RankingReportService._is_adequado_or_avancado_classification("avancado"))

    def test_rejects_other_levels(self):
        self.assertFalse(RankingReportService._is_adequado_or_avancado_classification("Básico"))
        self.assertFalse(RankingReportService._is_adequado_or_avancado_classification("Abaixo do Básico"))
        self.assertFalse(RankingReportService._is_adequado_or_avancado_classification(""))
        self.assertFalse(RankingReportService._is_adequado_or_avancado_classification(None))


class TestHierarchicalMeanCalculations(unittest.TestCase):
    def test_hierarchical_mean_equal_weight_per_turma_pedro_ribeiro(self):
        turma_means = [4.10, 6.01, 6.16]
        turma_profs = [161.7, 216.4, 220.2]
        self.assertAlmostEqual(
            RankingReportService._hierarchical_mean_values(turma_means),
            5.42,
            places=2,
        )
        self.assertAlmostEqual(
            RankingReportService._hierarchical_mean_values(turma_profs),
            199.43,
            places=1,
        )

    def test_hierarchical_mean_escola_equal_weight_per_serie(self):
        series_scores = [5.42, 6.80]
        self.assertAlmostEqual(
            RankingReportService._hierarchical_mean_values(series_scores),
            6.11,
            places=2,
        )

    def test_build_network_series_averages_uses_equal_weight_per_school(self):
        schools = [
            {
                "series": [
                    {"grade_name": "5º Ano", "average_score": 4.0, "average_proficiency": 150.0},
                ]
            },
            {
                "series": [
                    {"grade_name": "5º Ano", "average_score": 8.0, "average_proficiency": 250.0},
                ]
            },
        ]
        result = RankingReportService._build_network_series_averages(schools)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["grade_name"], "5º Ano")
        self.assertAlmostEqual(result[0]["average_score"], 6.0, places=1)
        self.assertAlmostEqual(result[0]["average_proficiency"], 200.0, places=1)

    def test_build_general_course_sections_uses_equal_weight_per_serie(self):
        school_rows = [
            {
                "school_id": "s1",
                "school_name": "Escola A",
                "series": [
                    {
                        "grade_name": "4º Ano",
                        "average_score": 4.0,
                        "average_proficiency": 150.0,
                        "students_count": 20,
                        "participating_students": 18,
                        "total_students": 22,
                    },
                    {
                        "grade_name": "5º Ano",
                        "average_score": 8.0,
                        "average_proficiency": 250.0,
                        "students_count": 5,
                        "participating_students": 5,
                        "total_students": 8,
                    },
                ],
            }
        ]
        sections = RankingReportService._build_general_course_sections(school_rows)
        self.assertEqual(len(sections), 1)
        school_entry = sections[0]["items"][0]
        self.assertAlmostEqual(school_entry["average_score"], 6.0, places=1)
        self.assertAlmostEqual(school_entry["average_proficiency"], 200.0, places=1)


class TestRankingRoutesValidation(unittest.TestCase):
    def test_requires_estado(self):
        with self.assertRaisesRegex(ValueError, "Estado é obrigatório"):
            validate_ranking_filters("general", {"municipio": "city-1"})

    def test_requires_municipio(self):
        with self.assertRaisesRegex(ValueError, "Município é obrigatório"):
            validate_ranking_filters("general", {"estado": "AL"})

    def test_specific_evaluation_requires_selected_avaliacao(self):
        with self.assertRaisesRegex(ValueError, "Selecione uma avaliação"):
            validate_ranking_filters(
                "specific_evaluation",
                {"estado": "AL", "municipio": "city-1", "evaluation_id": None},
            )

    def test_specific_answer_sheet_requires_selected_avaliacao(self):
        with self.assertRaisesRegex(ValueError, "Selecione um cartão resposta"):
            validate_ranking_filters(
                "specific_answer_sheet",
                {"estado": "AL", "municipio": "city-1", "answer_sheet_id": None},
            )


if __name__ == "__main__":
    unittest.main()
