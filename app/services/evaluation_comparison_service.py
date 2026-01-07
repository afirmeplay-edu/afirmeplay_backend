# -*- coding: utf-8 -*-
"""
Serviço para comparar duas avaliações e mostrar evolução
"""
from app import db
from app.models.test import Test
from app.models.question import Question
from app.models.testQuestion import TestQuestion
from app.models.evaluationResult import EvaluationResult
from app.models.studentAnswer import StudentAnswer
from app.models.subject import Subject
from app.models.skill import Skill
from app.services.evaluation_calculator import EvaluationCalculator
from datetime import datetime
import logging
from typing import Dict, Any, Optional, List
import json
import dateutil.parser

class EvaluationComparisonService:
    
    @staticmethod
    def compare_evaluations(test_ids: List[str]) -> Optional[Dict[str, Any]]:
        """
        Compara múltiplas avaliações e retorna a evolução sequencial entre elas
        
        Args:
            test_ids: Lista de IDs das avaliações (mínimo 2)
            
        Returns:
            Dicionário com comparação completa ou None se erro
        """
        import time
        service_start = time.time()
        
        try:
            
            if len(test_ids) < 2:
                logging.error(f"Mínimo de 2 avaliações necessário. Recebido: {len(test_ids)}")
                return None
            
            # Buscar todas as avaliações
            query_start = time.time()
            tests = Test.query.filter(Test.id.in_(test_ids)).all()
            query_time = time.time() - query_start
            
            if len(tests) != len(test_ids):
                missing_ids = set(test_ids) - {t.id for t in tests}
                logging.error(f"Avaliações não encontradas: {missing_ids}")
                return None
            
            # Buscar datas de aplicação e ordenar cronologicamente
            dates_start = time.time()
            from app.models.classTest import ClassTest
            tests_with_dates = []
            
            for test in tests:
                # Buscar data de aplicação mais antiga (primeira aplicação)
                class_tests = ClassTest.query.filter_by(test_id=test.id).all()
                application_date = None
                
                for ct in class_tests:
                    if ct.application:
                        try:
                            parsed_date = dateutil.parser.parse(ct.application)
                            if application_date is None or parsed_date < application_date:
                                application_date = parsed_date
                        except Exception as e:
                            logging.warning(f"Erro ao parsear data de aplicação para teste {test.id}: {e}")
                
                # Se não encontrar data de aplicação, usar created_at como fallback
                if application_date is None:
                    application_date = test.created_at or datetime.min
                
                tests_with_dates.append({
                    'test': test,
                    'application_date': application_date
                })
            
            dates_time = time.time() - dates_start
            
            # Ordenar por data de aplicação (primeira aplicada primeiro)
            tests_with_dates.sort(key=lambda x: x['application_date'])
            ordered_tests = [item['test'] for item in tests_with_dates]
            
            # Verificar se todas têm resultados
            results_start = time.time()
            all_results = {}
            for test in ordered_tests:
                results = EvaluationResult.query.filter_by(test_id=test.id).all()
                if not results:
                    logging.warning(f"Avaliação {test.id} não possui resultados calculados")
                    return None
                all_results[test.id] = results
            
            results_time = time.time() - results_start
            
            # Preparar dados básicos das avaliações ordenadas
            evaluations_data = []
            for i, item in enumerate(tests_with_dates):
                test = item['test']
                evaluations_data.append({
                    "order": i + 1,
                    "id": test.id,
                    "title": test.title,
                    "created_at": test.created_at.isoformat() if test.created_at else None,
                    "application_date": item['application_date'].isoformat() if item['application_date'] else None
                })
            
            # Fazer comparações sequenciais (1→2, 2→3, 3→4, etc.)
            comparisons_start = time.time()
            comparisons = []
            num_comparisons = len(ordered_tests) - 1
            
            for i in range(num_comparisons):
                comp_start = time.time()
                test_from = ordered_tests[i]
                test_to = ordered_tests[i + 1]
                results_from = all_results[test_from.id]
                results_to = all_results[test_to.id]
                
                
                # Comparação geral
                gen_start = time.time()
                general_comparison = EvaluationComparisonService._get_general_comparison(results_from, results_to)
                gen_time = time.time() - gen_start
                
                # Comparação por disciplina
                subj_start = time.time()
                subject_comparison = EvaluationComparisonService._get_subject_comparison(test_from, test_to, results_from, results_to)
                subj_time = time.time() - subj_start
                
                # Comparação por habilidade
                skills_start = time.time()
                skills_comparison = EvaluationComparisonService._get_skills_comparison(test_from, test_to, results_from, results_to)
                skills_time = time.time() - skills_start
                
                comparisons.append({
                    "from_evaluation": {
                        "id": test_from.id,
                        "title": test_from.title,
                        "order": i + 1
                    },
                    "to_evaluation": {
                        "id": test_to.id,
                        "title": test_to.title,
                        "order": i + 2
                    },
                    "general_comparison": general_comparison,
                    "subject_comparison": subject_comparison,
                    "skills_comparison": skills_comparison
                })
                
                comp_time = time.time() - comp_start
            
            comparisons_time = time.time() - comparisons_start
            
            # Calcular dados de participação para cada avaliação
            participation_start = time.time()
            participation_data = {
                "general": {},
                "by_school": {}
            }
            
            for i, test in enumerate(ordered_tests):
                eval_key = f"evaluation_{i+1}"
                
                # Participação geral
                general_participation = EvaluationComparisonService._get_general_participation(test.id)
                participation_data["general"][eval_key] = general_participation
                
                # Participação por escola
                school_participation = EvaluationComparisonService._get_participation_by_school(test.id)
                participation_data["by_school"][eval_key] = school_participation
                
            
            participation_time = time.time() - participation_start
            total_service_time = time.time() - service_start
            
            return {
                "evaluations": evaluations_data,
                "total_evaluations": len(ordered_tests),
                "comparisons": comparisons,
                "total_comparisons": len(comparisons),
                "participation": participation_data
            }
            
        except Exception as e:
            logging.error(f"Erro ao comparar avaliações {test_ids}: {str(e)}", exc_info=True)
            return None
    
    @staticmethod
    def _get_general_comparison(results_1: List[EvaluationResult], results_2: List[EvaluationResult]) -> Dict[str, Any]:
        """Calcula comparação geral entre as duas avaliações"""
        try:
            # Calcular médias da primeira avaliação
            avg_grade_1 = sum(r.grade for r in results_1) / len(results_1) if results_1 else 0
            avg_proficiency_1 = sum(r.proficiency for r in results_1) / len(results_1) if results_1 else 0
            
            # Calcular médias da segunda avaliação
            avg_grade_2 = sum(r.grade for r in results_2) / len(results_2) if results_2 else 0
            avg_proficiency_2 = sum(r.proficiency for r in results_2) / len(results_2) if results_2 else 0
            
            # Distribuição de classificação avaliação 1
            classification_dist_1 = {}
            for result in results_1:
                classification = result.classification or "Não definido"
                classification_dist_1[classification] = classification_dist_1.get(classification, 0) + 1
            
            # Distribuição de classificação avaliação 2
            classification_dist_2 = {}
            for result in results_2:
                classification = result.classification or "Não definido"
                classification_dist_2[classification] = classification_dist_2.get(classification, 0) + 1
            
            return {
                "average_grade": {
                    "evaluation_1": round(avg_grade_1, 2),
                    "evaluation_2": round(avg_grade_2, 2),
                    "evolution": EvaluationComparisonService._calculate_evolution_percentage(avg_grade_1, avg_grade_2)
                },
                "average_proficiency": {
                    "evaluation_1": round(avg_proficiency_1, 2),
                    "evaluation_2": round(avg_proficiency_2, 2),
                    "evolution": EvaluationComparisonService._calculate_evolution_percentage(avg_proficiency_1, avg_proficiency_2)
                },
                "total_students": {
                    "evaluation_1": len(results_1),
                    "evaluation_2": len(results_2)
                },
                "classification_distribution": {
                    "evaluation_1": classification_dist_1,
                    "evaluation_2": classification_dist_2
                }
            }
        except Exception as e:
            logging.error(f"Erro ao calcular comparação geral: {str(e)}")
            return {}
    
    @staticmethod
    def _get_subject_comparison(test_1: Test, test_2: Test, results_1: List[EvaluationResult], results_2: List[EvaluationResult]) -> Dict[str, Any]:
        """Calcula comparação por disciplina"""
        try:
            subject_comparison = {}
            
            # Extrair disciplinas de ambas avaliações
            subjects_1 = EvaluationComparisonService._extract_subjects_from_test(test_1)
            subjects_2 = EvaluationComparisonService._extract_subjects_from_test(test_2)
            
            logging.info(f"Disciplinas teste 1 ({test_1.id}): {subjects_1}")
            logging.info(f"Disciplinas teste 2 ({test_2.id}): {subjects_2}")
            
            # Criar set de IDs de disciplinas comuns
            subject_ids_1 = set(subjects_1.keys())
            subject_ids_2 = set(subjects_2.keys())
            common_subjects = subject_ids_1.intersection(subject_ids_2)
            
            logging.info(f"Disciplinas comuns: {common_subjects}")
            
            if not common_subjects:
                logging.warning(f"Nenhuma disciplina comum encontrada entre os testes. Disciplinas teste 1: {list(subject_ids_1)}, Disciplinas teste 2: {list(subject_ids_2)}")
                return {}
            
            for subject_id in common_subjects:
                subject_name_1 = subjects_1[subject_id]
                subject_name_2 = subjects_2[subject_id]
                
                # Usar o nome da primeira avaliação como referência
                subject_name = subject_name_1
                
                # Buscar questões de cada disciplina em cada teste
                questions_1 = EvaluationComparisonService._get_questions_by_subject(test_1.id, subject_id)
                questions_2 = EvaluationComparisonService._get_questions_by_subject(test_2.id, subject_id)
                
                if not questions_1 or not questions_2:
                    continue
                
                # Buscar resultados específicos desta disciplina para cada avaliação
                subject_results_1 = EvaluationComparisonService._get_subject_results_for_comparison(
                    test_1.id, subject_id, results_1
                )
                subject_results_2 = EvaluationComparisonService._get_subject_results_for_comparison(
                    test_2.id, subject_id, results_2
                )
                
                if not subject_results_1 or not subject_results_2:
                    continue
                
                # Calcular médias por disciplina
                avg_grade_1 = sum(r['grade'] for r in subject_results_1) / len(subject_results_1)
                avg_proficiency_1 = sum(r['proficiency'] for r in subject_results_1) / len(subject_results_1)
                
                avg_grade_2 = sum(r['grade'] for r in subject_results_2) / len(subject_results_2)
                avg_proficiency_2 = sum(r['proficiency'] for r in subject_results_2) / len(subject_results_2)
                
                # Distribuição de classificação por disciplina
                classification_dist_1 = {}
                for result in subject_results_1:
                    classification = result['classification'] or "Não definido"
                    classification_dist_1[classification] = classification_dist_1.get(classification, 0) + 1
                
                classification_dist_2 = {}
                for result in subject_results_2:
                    classification = result['classification'] or "Não definido"
                    classification_dist_2[classification] = classification_dist_2.get(classification, 0) + 1
                
                subject_comparison[subject_name] = {
                    "subject_id": subject_id,
                    "average_grade": {
                        "evaluation_1": round(avg_grade_1, 2),
                        "evaluation_2": round(avg_grade_2, 2),
                        "evolution": EvaluationComparisonService._calculate_evolution_percentage(avg_grade_1, avg_grade_2)
                    },
                    "average_proficiency": {
                        "evaluation_1": round(avg_proficiency_1, 2),
                        "evaluation_2": round(avg_proficiency_2, 2),
                        "evolution": EvaluationComparisonService._calculate_evolution_percentage(avg_proficiency_1, avg_proficiency_2)
                    },
                    "total_students": {
                        "evaluation_1": len(subject_results_1),
                        "evaluation_2": len(subject_results_2)
                    },
                    "classification_distribution": {
                        "evaluation_1": classification_dist_1,
                        "evaluation_2": classification_dist_2
                    }
                }
            
            return subject_comparison
            
        except Exception as e:
            logging.error(f"Erro ao calcular comparação por disciplina: {str(e)}")
            return {}
    
    @staticmethod
    def _get_skills_comparison(test_1: Test, test_2: Test, results_1: List[EvaluationResult], results_2: List[EvaluationResult]) -> Dict[str, Any]:
        """Calcula comparação por habilidade (skill) dentro de cada disciplina"""
        try:
            skills_comparison = {}
            
            # Extrair disciplinas de ambas avaliações
            subjects_1 = EvaluationComparisonService._extract_subjects_from_test(test_1)
            subjects_2 = EvaluationComparisonService._extract_subjects_from_test(test_2)
            
            logging.info(f"Buscando skills - Disciplinas teste 1: {subjects_1}")
            logging.info(f"Buscando skills - Disciplinas teste 2: {subjects_2}")
            
            # Criar set de IDs de disciplinas comuns
            subject_ids_1 = set(subjects_1.keys())
            subject_ids_2 = set(subjects_2.keys())
            common_subjects = subject_ids_1.intersection(subject_ids_2)
            
            logging.info(f"Disciplinas comuns para skills: {common_subjects}")
            
            if not common_subjects:
                logging.warning(f"Nenhuma disciplina comum encontrada para skills. Disciplinas teste 1: {list(subject_ids_1)}, Disciplinas teste 2: {list(subject_ids_2)}")
                return {}
            
            for subject_id in common_subjects:
                subject_name = subjects_1[subject_id]
                
                # Buscar habilidades de ambas avaliações para esta disciplina
                skills_1 = EvaluationComparisonService._get_skills_by_subject_and_test(test_1.id, subject_id)
                skills_2 = EvaluationComparisonService._get_skills_by_subject_and_test(test_2.id, subject_id)
                
                logging.info(f"Skills disciplina {subject_name} ({subject_id}) - Teste 1: {skills_1}")
                logging.info(f"Skills disciplina {subject_name} ({subject_id}) - Teste 2: {skills_2}")
                
                # Encontrar habilidades comuns
                skill_codes_1 = set(skills_1.keys())
                skill_codes_2 = set(skills_2.keys())
                common_skills = skill_codes_1.intersection(skill_codes_2)
                
                logging.info(f"Skills comuns para {subject_name}: {common_skills}")
                
                subject_skills_comparison = {}
                
                for skill_code in common_skills:
                    # Obter informações da skill dos dicionários já processados
                    skill_info_1 = skills_1.get(skill_code, {})
                    skill_info_2 = skills_2.get(skill_code, {})
                    
                    # Usar informações preferencialmente do primeiro teste, com fallback
                    if isinstance(skill_info_1, dict):
                        actual_code = skill_info_1.get('code', skill_code.strip('{}'))
                        skill_description = skill_info_1.get('description', f"Skill {actual_code}")
                    elif isinstance(skill_info_2, dict):
                        actual_code = skill_info_2.get('code', skill_code.strip('{}'))
                        skill_description = skill_info_2.get('description', f"Skill {actual_code}")
                    else:
                        actual_code = skill_code.strip('{}')
                        skill_description = f"Skill {actual_code}"
                    
                    # Calcular acertos por habilidade
                    skill_results_1 = EvaluationComparisonService._get_skill_results_for_comparison(
                        test_1.id, subject_id, skill_code
                    )
                    skill_results_2 = EvaluationComparisonService._get_skill_results_for_comparison(
                        test_2.id, subject_id, skill_code
                    )
                    
                    logging.info(f"Resultados skill {skill_code} - Teste 1: {skill_results_1}, Teste 2: {skill_results_2}")
                    
                    if not skill_results_1 or not skill_results_2:
                        logging.info(f"Pulando skill {skill_code} - faltam resultados: teste1={skill_results_1}, teste2={skill_results_2}")
                        continue
                    
                    # Calcular percentuais de acerto
                    percentage_1 = skill_results_1['percentage']
                    percentage_2 = skill_results_2['percentage']
                    
                    subject_skills_comparison[skill_code] = {
                        "code": actual_code,  # Retornar o código real da skill
                        "description": skill_description,
                        "evaluation_1": {
                            "correct_answers": skill_results_1['correct_answers'],
                            "total_questions": skill_results_1['total_questions'],
                            "percentage": round(percentage_1, 2)
                        },
                        "evaluation_2": {
                            "correct_answers": skill_results_2['correct_answers'],
                            "total_questions": skill_results_2['total_questions'],
                            "percentage": round(percentage_2, 2)
                        },
                        "evolution": EvaluationComparisonService._calculate_evolution_percentage(percentage_1, percentage_2)
                    }
                
                if subject_skills_comparison:
                    skills_comparison[subject_name] = subject_skills_comparison
            
            return skills_comparison
            
        except Exception as e:
            logging.error(f"Erro ao calcular comparação por habilidade: {str(e)}")
            return {}
    
    @staticmethod
    def _extract_subjects_from_test(test: Test) -> Dict[str, str]:
        """Extrai disciplinas de um teste"""
        subjects = {}
        
        logging.info(f"Extraindo disciplinas do teste {test.id}: subjects_info = {test.subjects_info}")
        
        # Primeiro, tentar extrair de subjects_info
        if test.subjects_info and isinstance(test.subjects_info, list):
            for subject_info in test.subjects_info:
                if isinstance(subject_info, dict) and 'id' in subject_info:
                    subject_id = subject_info['id']
                    subject_name = subject_info.get('name', f'Disciplina {subject_id}')
                    
                    # Buscar nome na tabela Subject se não tiver no subjects_info
                    if not subject_info.get('name'):
                        subject_obj = Subject.query.get(subject_id)
                        if subject_obj:
                            subject_name = subject_obj.name
                    
                    subjects[subject_id] = subject_name
                    logging.info(f"Disciplina encontrada em subjects_info: {subject_id} -> {subject_name}")
        
        # Se não encontrou disciplinas em subjects_info, tentar extrair das questões
        if not subjects:
            logging.info(f"Nenhuma disciplina encontrada em subjects_info, buscando nas questões do teste {test.id}")
            
            # Buscar questões do teste
            test_question_ids = [tq.question_id for tq in TestQuestion.query.filter_by(test_id=test.id).all()]
            if test_question_ids:
                questions = Question.query.filter(Question.id.in_(test_question_ids)).all()
                
                for question in questions:
                    if question.subject_id:
                        if question.subject_id not in subjects:
                            # Buscar nome da disciplina
                            subject_obj = Subject.query.get(question.subject_id)
                            subject_name = subject_obj.name if subject_obj else f"Disciplina {question.subject_id}"
                            subjects[question.subject_id] = subject_name
                            logging.info(f"Disciplina encontrada nas questões: {question.subject_id} -> {subject_name}")
        
        logging.info(f"Total de disciplinas extraídas do teste {test.id}: {len(subjects)} - {subjects}")
        return subjects
    
    @staticmethod
    def _get_questions_by_subject(test_id: str, subject_id: str) -> List[Question]:
        """Busca questões de um teste por disciplina"""
        test_question_ids = [tq.question_id for tq in TestQuestion.query.filter_by(test_id=test_id).order_by(TestQuestion.order).all()]
        
        if not test_question_ids:
            return []
        
        questions = Question.query.filter(
            Question.id.in_(test_question_ids),
            Question.subject_id == subject_id
        ).all()
        
        return questions
    
    @staticmethod
    def _get_subject_results_for_comparison(test_id: str, subject_id: str, results: List[EvaluationResult]) -> List[Dict[str, Any]]:
        """Busca resultados específicos de uma disciplina"""
        try:
            # Buscar questões da disciplina
            questions = EvaluationComparisonService._get_questions_by_subject(test_id, subject_id)
            question_ids = [q.id for q in questions]
            
            logging.info(f"_get_subject_results_for_comparison - test_id: {test_id}, subject_id: {subject_id}")
            logging.info(f"Questões encontradas: {len(questions)}, question_ids: {question_ids}")
            
            if not question_ids:
                logging.warning(f"Nenhuma questão encontrada para disciplina {subject_id} no teste {test_id}")
                return []
            
            # Buscar resultados dos alunos que responderam questões desta disciplina
            student_ids = [r.student_id for r in results]
            
            # Agregar resultados por aluno para esta disciplina
            subject_results = []
            
            for student_id in student_ids:
                # Buscar respostas do aluno para questões desta disciplina
                student_answers = StudentAnswer.query.filter(
                    StudentAnswer.test_id == test_id,
                    StudentAnswer.student_id == student_id,
                    StudentAnswer.question_id.in_(question_ids)
                ).all()
                
                if not student_answers:
                    continue
                
                # Calcular acertos para esta disciplina
                correct_answers = 0
                for answer in student_answers:
                    question = next((q for q in questions if q.id == answer.question_id), None)
                    if question:
                        # Verificar se é questão de múltipla escolha (com diferentes variações)
                        if question.question_type in ['multiple_choice', 'multipleChoice']:
                            from app.services.evaluation_result_service import EvaluationResultService
                            is_correct = EvaluationResultService.check_multiple_choice_answer(answer.answer, question.correct_answer)
                            if is_correct:
                                correct_answers += 1
                        elif question.correct_answer:
                            if str(answer.answer).strip().lower() == str(question.correct_answer).strip().lower():
                                correct_answers += 1
                
                # Usar o serviço de cálculo para manter consistência
                total_questions = len(student_answers)
                if total_questions > 0:
                    # Buscar curso do teste
                    test = Test.query.get(test_id)
                    course_name = "Anos Iniciais"  # Padrão
                    if test and test.course:
                        try:
                            from app.models.educationStage import EducationStage
                            course_uuid = test.course
                            course_obj = EducationStage.query.get(course_uuid)
                            if course_obj:
                                course_name = course_obj.name
                        except Exception:
                            pass
                    
                    # Buscar nome da disciplina
                    subject_obj = Subject.query.get(subject_id)
                    subject_name = subject_obj.name if subject_obj else "Outras"
                    
                    # Calcular usando EvaluationCalculator
                    result = EvaluationCalculator.calculate_complete_evaluation(
                        correct_answers=correct_answers,
                        total_questions=total_questions,
                        course_name=course_name,
                        subject_name=subject_name
                    )
                    
                    subject_results.append({
                        'student_id': student_id,
                        'grade': result['grade'],
                        'proficiency': result['proficiency'],
                        'classification': result['classification'],
                        'correct_answers': correct_answers,
                        'total_questions': total_questions
                    })
            
            return subject_results
            
        except Exception as e:
            logging.error(f"Erro ao buscar resultados da disciplina {subject_id}: {str(e)}")
            return []
    
    @staticmethod
    def _get_skills_by_subject_and_test(test_id: str, subject_id: str) -> Dict[str, Dict[str, str]]:
        """Busca habilidades de um teste por disciplina. Retorna dict com skill_code -> {code, description}"""
        skills = {}
        
        # Buscar questões da disciplina
        questions = EvaluationComparisonService._get_questions_by_subject(test_id, subject_id)
        
        for question in questions:
            if question.skill:
                # O campo skill pode conter múltiplas skills separadas por vírgula
                question_skills = [s.strip() for s in question.skill.split(',') if s.strip()]
                
                for skill_code in question_skills:
                    if skill_code not in skills:
                        # Limpar o código da skill (remover chaves se existirem)
                        skill_code_clean = skill_code.strip('{}')
                        
                        # Buscar skill por ID primeiro (UUID), depois por código
                        skill_obj = None
                        try:
                            import uuid
                            skill_uuid = uuid.UUID(skill_code_clean)
                            skill_obj = Skill.query.filter_by(id=str(skill_uuid)).first()
                        except (ValueError, AttributeError):
                            pass
                        
                        # Se não encontrou por ID, tentar por código
                        if not skill_obj:
                            skill_obj = Skill.query.filter_by(code=skill_code_clean).first()
                        
                        # Se ainda não encontrou, tentar com o código original
                        if not skill_obj:
                            skill_obj = Skill.query.filter_by(code=skill_code).first()
                        
                        # Determinar descrição e código real
                        if skill_obj:
                            skills[skill_code] = {
                                'code': skill_obj.code,
                                'description': skill_obj.description
                            }
                        else:
                            skills[skill_code] = {
                                'code': skill_code_clean,
                                'description': f"Skill {skill_code_clean}"
                            }
        
        return skills
    
    @staticmethod
    def _get_skill_results_for_comparison(test_id: str, subject_id: str, skill_code: str) -> Optional[Dict[str, Any]]:
        """Busca resultados de uma habilidade específica"""
        try:
            logging.info(f"_get_skill_results_for_comparison - test_id: {test_id}, subject_id: {subject_id}, skill_code: {skill_code}")
            
            # Buscar questões que têm esta habilidade
            questions = EvaluationComparisonService._get_questions_by_subject(test_id, subject_id)
            skill_questions = []
            
            logging.info(f"Total de questões da disciplina: {len(questions)}")
            
            for question in questions:
                if question.skill:
                    question_skills = [s.strip() for s in question.skill.split(',') if s.strip()]
                    logging.info(f"Questão {question.id} tem skills: {question_skills}")
                    if skill_code in question_skills:
                        skill_questions.append(question)
                        logging.info(f"Questão {question.id} adicionada para skill {skill_code}")
            
            logging.info(f"Questões encontradas para skill {skill_code}: {len(skill_questions)}")
            
            if not skill_questions:
                logging.warning(f"Nenhuma questão encontrada para skill {skill_code} na disciplina {subject_id}")
                return None
            
            question_ids = [q.id for q in skill_questions]
            
            # Buscar todas as respostas para essas questões
            all_answers = StudentAnswer.query.filter(
                StudentAnswer.test_id == test_id,
                StudentAnswer.question_id.in_(question_ids)
            ).all()
            
            logging.info(f"Respostas encontradas para skill {skill_code}: {len(all_answers)}")
            
            if not all_answers:
                logging.warning(f"Nenhuma resposta encontrada para skill {skill_code}")
                return None
            
            # Calcular acertos
            correct_answers = 0
            total_answers = len(all_answers)
            
            for answer in all_answers:
                question = next((q for q in skill_questions if q.id == answer.question_id), None)
                if question:
                    # Verificar se é questão de múltipla escolha (com diferentes variações)
                    if question.question_type in ['multiple_choice', 'multipleChoice']:
                        from app.services.evaluation_result_service import EvaluationResultService
                        is_correct = EvaluationResultService.check_multiple_choice_answer(answer.answer, question.correct_answer)
                        if is_correct:
                            correct_answers += 1
                    elif question.correct_answer:
                        if str(answer.answer).strip().lower() == str(question.correct_answer).strip().lower():
                            correct_answers += 1
            
            percentage = (correct_answers / total_answers * 100) if total_answers > 0 else 0
            
            result = {
                'correct_answers': correct_answers,
                'total_questions': total_answers,
                'percentage': percentage
            }
            
            logging.info(f"Resultado final para skill {skill_code}: {result}")
            return result
            
        except Exception as e:
            logging.error(f"Erro ao buscar resultados da habilidade {skill_code}: {str(e)}")
            return None
    
    @staticmethod
    def _calculate_evolution_percentage(old_value: float, new_value: float) -> Dict[str, Any]:
        """Calcula percentual de evolução entre dois valores"""
        try:
            if old_value == 0:
                return {
                    "value": new_value,
                    "percentage": 100.0 if new_value > 0 else 0.0,
                    "direction": "increase" if new_value > 0 else "stable"
                }
            
            difference = new_value - old_value
            percentage = (difference / abs(old_value)) * 100
            
            direction = "increase"
            if difference < 0:
                direction = "decrease"
            elif difference == 0:
                direction = "stable"
            
            return {
                "value": round(difference, 2),
                "percentage": round(percentage, 2),
                "direction": direction
            }
            
        except Exception as e:
            logging.error(f"Erro ao calcular evolução: {str(e)}")
            return {
                "value": 0.0,
                "percentage": 0.0,
                "direction": "stable"
            }
    
    @staticmethod
    def compare_student_evaluations_multiple(student_id: str, test_ids: List[str]) -> Optional[Dict[str, Any]]:
        """
        Compara múltiplas avaliações de um aluno específico, mostrando evolução sequencial
        
        Args:
            student_id: ID do aluno (pode ser user_id ou student_id)
            test_ids: Lista de IDs das avaliações (mínimo 2)
            
        Returns:
            Dicionário com comparação completa do aluno ou None se erro
        """
        try:
            from app.models.student import Student
            from app.models.classTest import ClassTest
            
            if len(test_ids) < 2:
                logging.error(f"Mínimo de 2 avaliações necessário. Recebido: {len(test_ids)}")
                return None
            
            # Resolver student_id - tentar como user_id primeiro, depois como student_id
            student_obj = Student.query.filter_by(user_id=student_id).first()
            if not student_obj:
                # Fallback: assumir que é um student_id direto
                student_obj = Student.query.get(student_id)
            
            if not student_obj:
                logging.error(f"Aluno não encontrado: {student_id}")
                return None
            
            actual_student_id = student_obj.id
            logging.info(f"Aluno encontrado - user_id: {student_id}, student_id: {actual_student_id}")
            
            # Buscar todas as avaliações
            tests = Test.query.filter(Test.id.in_(test_ids)).all()
            
            if len(tests) != len(test_ids):
                missing_ids = set(test_ids) - {t.id for t in tests}
                logging.error(f"Avaliações não encontradas: {missing_ids}")
                return None
            
            # Verificar se todas as avaliações foram aplicadas à classe do aluno
            class_tests = ClassTest.query.filter_by(class_id=student_obj.class_id).all()
            applied_test_ids = {ct.test_id for ct in class_tests}
            
            not_applied_tests = set(test_ids) - applied_test_ids
            if not_applied_tests:
                logging.error(f"Avaliações não aplicadas à classe do aluno: {not_applied_tests}")
                return None
            
            # Buscar datas de aplicação e ordenar cronologicamente
            tests_with_dates = []
            
            for test in tests:
                # Buscar data de aplicação mais antiga (primeira aplicação)
                test_class_tests = ClassTest.query.filter_by(test_id=test.id).all()
                application_date = None
                
                for ct in test_class_tests:
                    if ct.application:
                        try:
                            parsed_date = dateutil.parser.parse(ct.application)
                            if application_date is None or parsed_date < application_date:
                                application_date = parsed_date
                        except Exception as e:
                            logging.warning(f"Erro ao parsear data de aplicação para teste {test.id}: {e}")
                
                # Se não encontrar data de aplicação, usar created_at como fallback
                if application_date is None:
                    application_date = test.created_at or datetime.min
                
                tests_with_dates.append({
                    'test': test,
                    'application_date': application_date
                })
            
            # Ordenar por data de aplicação (primeira aplicada primeiro)
            tests_with_dates.sort(key=lambda x: x['application_date'])
            ordered_tests = [item['test'] for item in tests_with_dates]
            
            # Verificar se o aluno completou todas as avaliações
            all_results = {}
            for test in ordered_tests:
                result = EvaluationResult.query.filter_by(
                    test_id=test.id, 
                    student_id=actual_student_id
                ).first()
                
                if not result:
                    logging.warning(f"Aluno {actual_student_id} não completou avaliação {test.id}")
                    return None
                
                all_results[test.id] = result
            
            # Preparar dados básicos das avaliações ordenadas
            evaluations_data = []
            for i, item in enumerate(tests_with_dates):
                test = item['test']
                evaluations_data.append({
                    "order": i + 1,
                    "id": test.id,
                    "title": test.title,
                    "created_at": test.created_at.isoformat() if test.created_at else None,
                    "application_date": item['application_date'].isoformat() if item['application_date'] else None
                })
            
            # Fazer comparações sequenciais (1→2, 2→3, 3→4, etc.)
            comparisons = []
            for i in range(len(ordered_tests) - 1):
                test_from = ordered_tests[i]
                test_to = ordered_tests[i + 1]
                result_from = all_results[test_from.id]
                result_to = all_results[test_to.id]
                
                # Comparação geral
                general_comparison = EvaluationComparisonService._get_student_general_comparison(result_from, result_to)
                
                # Comparação por disciplina
                subject_comparison = EvaluationComparisonService._get_student_subject_comparison(actual_student_id, test_from, test_to)
                
                # Comparação por habilidade
                skills_comparison = EvaluationComparisonService._get_student_skills_comparison(actual_student_id, test_from, test_to)
                
                comparisons.append({
                    "from_evaluation": {
                        "id": test_from.id,
                        "title": test_from.title,
                        "order": i + 1
                    },
                    "to_evaluation": {
                        "id": test_to.id,
                        "title": test_to.title,
                        "order": i + 2
                    },
                    "general_comparison": general_comparison,
                    "subject_comparison": subject_comparison,
                    "skills_comparison": skills_comparison
                })
            
            return {
                "student": {
                    "id": actual_student_id,
                    "user_id": student_obj.user_id,
                    "name": student_obj.name
                },
                "evaluations": evaluations_data,
                "total_evaluations": len(ordered_tests),
                "comparisons": comparisons,
                "total_comparisons": len(comparisons)
            }
            
        except Exception as e:
            logging.error(f"Erro ao comparar avaliações do aluno {student_id}: {str(e)}", exc_info=True)
            return None
    
    @staticmethod
    def compare_student_evaluations(student_id: str, test_id_1: str, test_id_2: str) -> Optional[Dict[str, Any]]:
        """
        Compara as avaliações de um aluno específico entre duas avaliações
        
        Args:
            student_id: ID do aluno (pode ser user_id ou student_id)
            test_id_1: ID da primeira avaliação
            test_id_2: ID da segunda avaliação
            
        Returns:
            Dicionário com comparação completa do aluno ou None se erro
        """
        try:
            from app.models.student import Student
            
            # Resolver student_id - tentar como user_id primeiro, depois como student_id
            student_obj = Student.query.filter_by(user_id=student_id).first()
            if not student_obj:
                # Fallback: assumir que é um student_id direto
                student_obj = Student.query.get(student_id)
            
            if not student_obj:
                logging.error(f"Aluno não encontrado: {student_id}")
                return None
            
            actual_student_id = student_obj.id
            logging.info(f"Aluno encontrado - user_id: {student_id}, student_id: {actual_student_id}")
            
            # Buscar as duas avaliações
            test_1 = Test.query.get(test_id_1)
            test_2 = Test.query.get(test_id_2)
            
            if not test_1 or not test_2:
                logging.error(f"Avaliações não encontradas: {test_id_1}, {test_id_2}")
                return None
            
            # Verificar se o aluno completou ambas avaliações
            result_1 = EvaluationResult.query.filter_by(
                test_id=test_id_1, 
                student_id=actual_student_id
            ).first()
            
            result_2 = EvaluationResult.query.filter_by(
                test_id=test_id_2, 
                student_id=actual_student_id
            ).first()
            
            if not result_1:
                logging.warning(f"Aluno {actual_student_id} não completou avaliação {test_id_1}")
                return None
                
            if not result_2:
                logging.warning(f"Aluno {actual_student_id} não completou avaliação {test_id_2}")
                return None
            
            # Preparar dados básicos das avaliações
            evaluation_1_data = {
                "id": test_1.id,
                "title": test_1.title,
                "created_at": test_1.created_at.isoformat() if test_1.created_at else None,
                "completed_at": result_1.calculated_at.isoformat() if result_1.calculated_at else None
            }
            
            evaluation_2_data = {
                "id": test_2.id,
                "title": test_2.title,
                "created_at": test_2.created_at.isoformat() if test_2.created_at else None,
                "completed_at": result_2.calculated_at.isoformat() if result_2.calculated_at else None
            }
            
            # Comparação geral do aluno
            general_comparison = EvaluationComparisonService._get_student_general_comparison(result_1, result_2)
            
            # Comparação por disciplina do aluno
            subject_comparison = EvaluationComparisonService._get_student_subject_comparison(
                actual_student_id, test_1, test_2
            )
            
            # Comparação por habilidade do aluno
            skills_comparison = EvaluationComparisonService._get_student_skills_comparison(
                actual_student_id, test_1, test_2
            )
            
            return {
                "student_info": {
                    "id": actual_student_id,
                    "name": student_obj.name,
                    "user_id": student_obj.user_id
                },
                "evaluation_1": evaluation_1_data,
                "evaluation_2": evaluation_2_data,
                "general_comparison": general_comparison,
                "subject_comparison": subject_comparison,
                "skills_comparison": skills_comparison
            }
            
        except Exception as e:
            logging.error(f"Erro ao comparar avaliações do aluno {student_id} ({test_id_1} vs {test_id_2}): {str(e)}", exc_info=True)
            return None
    
    @staticmethod
    def _get_student_general_comparison(result_1: EvaluationResult, result_2: EvaluationResult) -> Dict[str, Any]:
        """Calcula comparação geral entre as duas avaliações para um aluno específico"""
        try:
            return {
                "student_grade": {
                    "evaluation_1": round(result_1.grade, 2),
                    "evaluation_2": round(result_2.grade, 2),
                    "evolution": EvaluationComparisonService._calculate_evolution_percentage(result_1.grade, result_2.grade)
                },
                "student_proficiency": {
                    "evaluation_1": round(result_1.proficiency, 2),
                    "evaluation_2": round(result_2.proficiency, 2),
                    "evolution": EvaluationComparisonService._calculate_evolution_percentage(result_1.proficiency, result_2.proficiency)
                },
                "student_classification": {
                    "evaluation_1": result_1.classification or "Não definido",
                    "evaluation_2": result_2.classification or "Não definido"
                },
                "correct_answers": {
                    "evaluation_1": result_1.correct_answers,
                    "evaluation_2": result_2.correct_answers,
                    "evolution": EvaluationComparisonService._calculate_evolution_percentage(float(result_1.correct_answers), float(result_2.correct_answers))
                },
                "total_questions": {
                    "evaluation_1": result_1.total_questions,
                    "evaluation_2": result_2.total_questions
                },
                "score_percentage": {
                    "evaluation_1": round(result_1.score_percentage, 2),
                    "evaluation_2": round(result_2.score_percentage, 2),
                    "evolution": EvaluationComparisonService._calculate_evolution_percentage(result_1.score_percentage, result_2.score_percentage)
                }
            }
        except Exception as e:
            logging.error(f"Erro ao calcular comparação geral do aluno: {str(e)}")
            return {}
    
    @staticmethod
    def _get_student_subject_comparison(student_id: str, test_1: Test, test_2: Test) -> Dict[str, Any]:
        """Calcula comparação por disciplina para um aluno específico"""
        try:
            subject_comparison = {}
            
            # Extrair disciplinas de ambas avaliações
            subjects_1 = EvaluationComparisonService._extract_subjects_from_test(test_1)
            subjects_2 = EvaluationComparisonService._extract_subjects_from_test(test_2)
            
            # Criar set de IDs de disciplinas comuns
            subject_ids_1 = set(subjects_1.keys())
            subject_ids_2 = set(subjects_2.keys())
            common_subjects = subject_ids_1.intersection(subject_ids_2)
            
            if not common_subjects:
                logging.warning(f"Nenhuma disciplina comum encontrada entre as avaliações")
                return {}
            
            for subject_id in common_subjects:
                subject_name = subjects_1[subject_id]
                
                # Buscar resultados específicos desta disciplina para o aluno
                subject_result_1 = EvaluationComparisonService._get_student_subject_results(student_id, test_1.id, subject_id)
                subject_result_2 = EvaluationComparisonService._get_student_subject_results(student_id, test_2.id, subject_id)
                
                if not subject_result_1 or not subject_result_2:
                    continue
                
                subject_comparison[subject_name] = {
                    "subject_id": subject_id,
                    "student_grade": {
                        "evaluation_1": round(subject_result_1['grade'], 2),
                        "evaluation_2": round(subject_result_2['grade'], 2),
                        "evolution": EvaluationComparisonService._calculate_evolution_percentage(subject_result_1['grade'], subject_result_2['grade'])
                    },
                    "student_proficiency": {
                        "evaluation_1": round(subject_result_1['proficiency'], 2),
                        "evaluation_2": round(subject_result_2['proficiency'], 2),
                        "evolution": EvaluationComparisonService._calculate_evolution_percentage(subject_result_1['proficiency'], subject_result_2['proficiency'])
                    },
                    "student_classification": {
                        "evaluation_1": subject_result_1['classification'] or "Não definido",
                        "evaluation_2": subject_result_2['classification'] or "Não definido"
                    },
                    "correct_answers": {
                        "evaluation_1": subject_result_1['correct_answers'],
                        "evaluation_2": subject_result_2['correct_answers'],
                        "evolution": EvaluationComparisonService._calculate_evolution_percentage(float(subject_result_1['correct_answers']), float(subject_result_2['correct_answers']))
                    },
                    "total_questions": {
                        "evaluation_1": subject_result_1['total_questions'],
                        "evaluation_2": subject_result_2['total_questions']
                    }
                }
            
            return subject_comparison
            
        except Exception as e:
            logging.error(f"Erro ao calcular comparação por disciplina do aluno: {str(e)}")
            return {}
    
    @staticmethod
    def _get_student_skills_comparison(student_id: str, test_1: Test, test_2: Test) -> Dict[str, Any]:
        """Calcula comparação por habilidade para um aluno específico"""
        try:
            skills_comparison = {}
            
            # Extrair disciplinas de ambas avaliações
            subjects_1 = EvaluationComparisonService._extract_subjects_from_test(test_1)
            subjects_2 = EvaluationComparisonService._extract_subjects_from_test(test_2)
            
            # Criar set de IDs de disciplinas comuns
            subject_ids_1 = set(subjects_1.keys())
            subject_ids_2 = set(subjects_2.keys())
            common_subjects = subject_ids_1.intersection(subject_ids_2)
            
            if not common_subjects:
                return {}
            
            for subject_id in common_subjects:
                subject_name = subjects_1[subject_id]
                
                # Buscar habilidades de ambas avaliações para esta disciplina
                skills_1 = EvaluationComparisonService._get_skills_by_subject_and_test(test_1.id, subject_id)
                skills_2 = EvaluationComparisonService._get_skills_by_subject_and_test(test_2.id, subject_id)
                
                # Encontrar habilidades comuns
                skill_codes_1 = set(skills_1.keys())
                skill_codes_2 = set(skills_2.keys())
                common_skills = skill_codes_1.intersection(skill_codes_2)
                
                subject_skills_comparison = {}
                
                for skill_code in common_skills:
                    # Obter informações da skill
                    skill_info_1 = skills_1.get(skill_code, {})
                    skill_info_2 = skills_2.get(skill_code, {})
                    
                    # Usar informações preferencialmente do primeiro teste
                    if isinstance(skill_info_1, dict):
                        actual_code = skill_info_1.get('code', skill_code.strip('{}'))
                        skill_description = skill_info_1.get('description', f"Skill {actual_code}")
                    elif isinstance(skill_info_2, dict):
                        actual_code = skill_info_2.get('code', skill_code.strip('{}'))
                        skill_description = skill_info_2.get('description', f"Skill {actual_code}")
                    else:
                        actual_code = skill_code.strip('{}')
                        skill_description = f"Skill {actual_code}"
                    
                    # Calcular acertos por habilidade para o aluno
                    skill_result_1 = EvaluationComparisonService._get_student_skill_results(student_id, test_1.id, subject_id, skill_code)
                    skill_result_2 = EvaluationComparisonService._get_student_skill_results(student_id, test_2.id, subject_id, skill_code)
                    
                    if not skill_result_1 or not skill_result_2:
                        continue
                    
                    # Calcular percentuais de acerto
                    percentage_1 = skill_result_1['percentage']
                    percentage_2 = skill_result_2['percentage']
                    
                    subject_skills_comparison[skill_code] = {
                        "code": actual_code,
                        "description": skill_description,
                        "correct_answers": {
                            "evaluation_1": skill_result_1['correct_answers'],
                            "evaluation_2": skill_result_2['correct_answers'],
                            "evolution": EvaluationComparisonService._calculate_evolution_percentage(float(skill_result_1['correct_answers']), float(skill_result_2['correct_answers']))
                        },
                        "total_questions": {
                            "evaluation_1": skill_result_1['total_questions'],
                            "evaluation_2": skill_result_2['total_questions']
                        },
                        "percentage": {
                            "evaluation_1": round(percentage_1, 2),
                            "evaluation_2": round(percentage_2, 2),
                            "evolution": EvaluationComparisonService._calculate_evolution_percentage(percentage_1, percentage_2)
                        }
                    }
                
                if subject_skills_comparison:
                    skills_comparison[subject_name] = subject_skills_comparison
            
            return skills_comparison
            
        except Exception as e:
            logging.error(f"Erro ao calcular comparação por habilidade do aluno: {str(e)}")
            return {}
    
    @staticmethod
    def _get_student_subject_results(student_id: str, test_id: str, subject_id: str) -> Optional[Dict[str, Any]]:
        """Busca resultados específicos de uma disciplina para um aluno específico"""
        try:
            # Buscar questões da disciplina
            questions = EvaluationComparisonService._get_questions_by_subject(test_id, subject_id)
            question_ids = [q.id for q in questions]
            
            if not question_ids:
                return None
            
            # Buscar respostas do aluno para questões desta disciplina
            student_answers = StudentAnswer.query.filter(
                StudentAnswer.test_id == test_id,
                StudentAnswer.student_id == student_id,
                StudentAnswer.question_id.in_(question_ids)
            ).all()
            
            if not student_answers:
                return None
            
            # Calcular acertos para esta disciplina
            correct_answers = 0
            for answer in student_answers:
                question = next((q for q in questions if q.id == answer.question_id), None)
                if question:
                    # Verificar se é questão de múltipla escolha
                    if question.question_type in ['multiple_choice', 'multipleChoice']:
                        from app.services.evaluation_result_service import EvaluationResultService
                        is_correct = EvaluationResultService.check_multiple_choice_answer(answer.answer, question.correct_answer)
                        if is_correct:
                            correct_answers += 1
                    elif question.correct_answer:
                        if str(answer.answer).strip().lower() == str(question.correct_answer).strip().lower():
                            correct_answers += 1
            
            total_questions = len(student_answers)
            if total_questions == 0:
                return None
            
            # Buscar curso do teste
            test = Test.query.get(test_id)
            course_name = "Anos Iniciais"  # Padrão
            if test and test.course:
                try:
                    from app.models.educationStage import EducationStage
                    course_obj = EducationStage.query.get(test.course)
                    if course_obj:
                        course_name = course_obj.name
                except Exception:
                    pass
            
            # Buscar nome da disciplina
            subject_obj = Subject.query.get(subject_id)
            subject_name = subject_obj.name if subject_obj else "Outras"
            
            # Calcular usando EvaluationCalculator
            result = EvaluationCalculator.calculate_complete_evaluation(
                correct_answers=correct_answers,
                total_questions=total_questions,
                course_name=course_name,
                subject_name=subject_name
            )
            
            return {
                'grade': result['grade'],
                'proficiency': result['proficiency'],
                'classification': result['classification'],
                'correct_answers': correct_answers,
                'total_questions': total_questions
            }
            
        except Exception as e:
            logging.error(f"Erro ao buscar resultados da disciplina {subject_id} para aluno {student_id}: {str(e)}")
            return None
    
    @staticmethod
    def _get_student_skill_results(student_id: str, test_id: str, subject_id: str, skill_code: str) -> Optional[Dict[str, Any]]:
        """Busca resultados de uma habilidade específica para um aluno específico"""
        try:
            # Buscar questões que têm esta habilidade
            questions = EvaluationComparisonService._get_questions_by_subject(test_id, subject_id)
            skill_questions = []
            
            for question in questions:
                if question.skill:
                    question_skills = [s.strip() for s in question.skill.split(',') if s.strip()]
                    if skill_code in question_skills:
                        skill_questions.append(question)
            
            if not skill_questions:
                return None
            
            question_ids = [q.id for q in skill_questions]
            
            # Buscar respostas do aluno para essas questões específicas
            student_answers = StudentAnswer.query.filter(
                StudentAnswer.test_id == test_id,
                StudentAnswer.student_id == student_id,
                StudentAnswer.question_id.in_(question_ids)
            ).all()
            
            if not student_answers:
                return None
            
            # Calcular acertos
            correct_answers = 0
            for answer in student_answers:
                question = next((q for q in skill_questions if q.id == answer.question_id), None)
                if question:
                    # Verificar se é questão de múltipla escolha
                    if question.question_type in ['multiple_choice', 'multipleChoice']:
                        from app.services.evaluation_result_service import EvaluationResultService
                        is_correct = EvaluationResultService.check_multiple_choice_answer(answer.answer, question.correct_answer)
                        if is_correct:
                            correct_answers += 1
                    elif question.correct_answer:
                        if str(answer.answer).strip().lower() == str(question.correct_answer).strip().lower():
                            correct_answers += 1
            
            total_questions = len(student_answers)
            percentage = (correct_answers / total_questions * 100) if total_questions > 0 else 0
            
            return {
                'correct_answers': correct_answers,
                'total_questions': total_questions,
                'percentage': percentage
            }
            
        except Exception as e:
            logging.error(f"Erro ao buscar resultados da habilidade {skill_code} para aluno {student_id}: {str(e)}")
            return None
    
    @staticmethod
    def _get_general_participation(test_id: str) -> Dict[str, Any]:
        """
        Calcula taxa de participação geral para uma avaliação
        
        Args:
            test_id: ID da avaliação
            
        Returns:
            {
                'total_students': int,  # Total de alunos matriculados
                'participating_students': int,  # Alunos com resultados
                'participation_rate': float  # Porcentagem
            }
        """
        try:
            from app.models.classTest import ClassTest
            from app.models.student import Student
            from app.models.evaluationResult import EvaluationResult
            
            # 1. Buscar ClassTest para esta avaliação
            class_tests = ClassTest.query.filter_by(test_id=test_id).all()
            class_ids = [ct.class_id for ct in class_tests if ct.class_id]
            
            if not class_ids:
                return {
                    'total_students': 0,
                    'participating_students': 0,
                    'participation_rate': 0.0
                }
            
            # 2. Buscar todos os alunos dessas turmas
            total_students = Student.query.filter(Student.class_id.in_(class_ids)).count()
            
            # 3. Buscar alunos com resultados
            participating_students = EvaluationResult.query.filter_by(test_id=test_id).count()
            
            # 4. Calcular taxa
            participation_rate = (participating_students / total_students * 100) if total_students > 0 else 0.0
            
            return {
                'total_students': total_students,
                'participating_students': participating_students,
                'participation_rate': round(participation_rate, 2)
            }
        except Exception as e:
            logging.error(f"Erro ao calcular participação geral para avaliação {test_id}: {str(e)}", exc_info=True)
            return {
                'total_students': 0,
                'participating_students': 0,
                'participation_rate': 0.0
            }
    
    @staticmethod
    def _get_participation_by_school(test_id: str) -> Dict[str, Dict[str, Any]]:
        """
        Calcula taxa de participação por escola para uma avaliação
        
        Args:
            test_id: ID da avaliação
            
        Returns:
            {
                'school_id_1': {
                    'school_name': 'Escola A',
                    'total_students': 100,
                    'participating_students': 95,
                    'participation_rate': 95.0
                },
                'school_id_2': {...}
            }
        """
        try:
            from app.models.classTest import ClassTest
            from app.models.studentClass import Class
            from app.models.school import School
            from app.models.student import Student
            from app.models.evaluationResult import EvaluationResult
            
            # 1. Buscar ClassTest para esta avaliação
            class_tests = ClassTest.query.filter_by(test_id=test_id).all()
            class_ids = [ct.class_id for ct in class_tests if ct.class_id]
            
            if not class_ids:
                return {}
            
            # 2. Buscar Classes e agrupar por escola
            classes = Class.query.filter(Class.id.in_(class_ids)).all()
            schools_data = {}
            
            for class_obj in classes:
                if not class_obj.school_id:
                    continue
                    
                school_id = class_obj.school_id
                
                if school_id not in schools_data:
                    school = School.query.get(school_id)
                    schools_data[school_id] = {
                        'school_id': school_id,
                        'school_name': school.name if school else f'Escola {school_id}',
                        'class_ids': []
                    }
                
                schools_data[school_id]['class_ids'].append(class_obj.id)
            
            # 3. Para cada escola, calcular participação
            participation_by_school = {}
            
            for school_id, school_info in schools_data.items():
                class_ids_school = school_info['class_ids']
                
                # Total de alunos da escola (nas turmas onde a avaliação foi aplicada)
                total_students = Student.query.filter(
                    Student.class_id.in_(class_ids_school)
                ).count()
                
                if total_students == 0:
                    continue
                
                # IDs dos alunos da escola
                student_ids = Student.query.filter(
                    Student.class_id.in_(class_ids_school)
                ).with_entities(Student.id).all()
                student_ids = [s[0] for s in student_ids]
                
                # Alunos participantes (com resultados)
                participating_students = EvaluationResult.query.filter(
                    EvaluationResult.test_id == test_id,
                    EvaluationResult.student_id.in_(student_ids)
                ).count()
                
                # Calcular taxa
                participation_rate = (participating_students / total_students * 100) if total_students > 0 else 0.0
                
                participation_by_school[school_id] = {
                    'school_name': school_info['school_name'],
                    'total_students': total_students,
                    'participating_students': participating_students,
                    'participation_rate': round(participation_rate, 2)
                }
            
            return participation_by_school
            
        except Exception as e:
            logging.error(f"Erro ao calcular participação por escola para avaliação {test_id}: {str(e)}", exc_info=True)
            return {}
