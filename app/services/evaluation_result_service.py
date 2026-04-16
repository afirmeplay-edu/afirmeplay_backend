# -*- coding: utf-8 -*-
"""
Serviço para gerenciar resultados de avaliação calculados
"""
from app import db
from app.models.evaluationResult import EvaluationResult
from app.models.test import Test
from app.models.question import Question
from app.models.student import Student
from app.models.school import School
from app.models.studentClass import Class
from app.models.studentAnswer import StudentAnswer
from app.services.evaluation_calculator import EvaluationCalculator
from app.report_analysis.services import ReportAggregateService
from app.utils.decimal_helpers import round_to_two_decimals
from app.utils.school_equal_weight_means import mean_grade_and_proficiency_equal_weight_by_school_from_subject_rows
from datetime import datetime
import logging
from typing import Dict, Any, Optional, List
import json

class EvaluationResultService:
    
    @staticmethod
    def check_multiple_choice_answer(student_answer, correct_answer):
        """
        Verifica se a resposta do aluno está correta para questão de múltipla escolha
        Compara a resposta do aluno com a alternativa correta
        """
        if not correct_answer or not student_answer:
            logging.warning(f"Alternativa correta ou resposta do aluno vazias: correct_answer={correct_answer}, student_answer={student_answer}")
            return False

        student_answer = str(student_answer).strip()
        correct_answer = str(correct_answer).strip()

        # Comparação direta (case-insensitive para maior flexibilidade)
        is_correct = student_answer.lower() == correct_answer.lower()
        logging.debug("Verificando resposta: '%s' vs '%s' => %s", student_answer, correct_answer, is_correct)
        return is_correct
    
    @staticmethod
    def _calculate_subject_specific_results(test_id: str, student_id: str, questions: List[Question], 
                                         answers: List[StudentAnswer], course_name: str) -> List[Dict[str, Any]]:
        """
        Calcula resultados específicos por disciplina quando há múltiplas disciplinas
        
        Args:
            test_id: ID do teste
            student_id: ID do aluno
            questions: Lista de questões do teste
            answers: Lista de respostas do aluno
            course_name: Nome do curso
            
        Returns:
            Lista de resultados por disciplina
        """
        from app.models.subject import Subject
        
        # Agrupar questões por disciplina
        questions_by_subject = {}
        for question in questions:
            if question.subject_id:
                if question.subject_id not in questions_by_subject:
                    questions_by_subject[question.subject_id] = []
                questions_by_subject[question.subject_id].append(question)
        
        subject_results = []
        
        for subject_id, subject_questions in questions_by_subject.items():
            # Buscar informações da disciplina
            subject_obj = Subject.query.get(subject_id)
            if not subject_obj:
                continue
                
            subject_name = subject_obj.name
            total_questions_subject = len(subject_questions)
            
            # Filtrar respostas para esta disciplina
            subject_question_ids = [q.id for q in subject_questions]
            subject_answers = [a for a in answers if a.question_id in subject_question_ids]
            answered_questions = len(subject_answers)
            
            # Calcular acertos para esta disciplina
            correct_answers_subject = 0
            for answer in subject_answers:
                question = next((q for q in subject_questions if q.id == answer.question_id), None)
                if question:
                    if question.question_type == 'multiple_choice':
                        is_correct = EvaluationResultService.check_multiple_choice_answer(answer.answer, question.correct_answer)
                        if is_correct:
                            correct_answers_subject += 1
                    elif question.correct_answer:
                        if str(answer.answer).strip().lower() == str(question.correct_answer).strip().lower():
                            correct_answers_subject += 1
            
            # Calcular resultado para esta disciplina usando questões respondidas
            result = EvaluationCalculator.calculate_complete_evaluation(
                correct_answers=correct_answers_subject,
                total_questions=answered_questions if answered_questions > 0 else total_questions_subject,
                course_name=course_name,
                subject_name=subject_name,
                use_simple_calculation=False
            )
            
            score_percentage = (correct_answers_subject / answered_questions * 100) if answered_questions > 0 else 0
            
            subject_results.append({
                'subject_id': subject_id,
                'subject_name': subject_name,
                'correct_answers': correct_answers_subject,
                'total_questions': total_questions_subject,
                'answered_questions': answered_questions,
                'score_percentage': round_to_two_decimals(score_percentage),
                'grade': result['grade'],
                'proficiency': result['proficiency'],
                'classification': result['classification']
            })
        
        return subject_results
    
    @staticmethod
    def calculate_and_save_result(test_id: str, student_id: str, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Calcula e salva o resultado completo de uma avaliação para um aluno
        
        Args:
            test_id: ID do teste
            student_id: ID do aluno
            session_id: ID da sessão
            
        Returns:
            Dicionário com os resultados calculados ou None se erro
        """
        try:
            # Buscar o teste e suas questões
            test = Test.query.get(test_id)
            if not test:
                logging.error(f"Teste {test_id} não encontrado")
                return None
            
            # Buscar todas as questões do teste
            # Buscar questões do teste através da tabela de associação
            from app.models.testQuestion import TestQuestion
            test_question_ids = [tq.question_id for tq in TestQuestion.query.filter_by(test_id=test_id).order_by(TestQuestion.order).all()]
            questions = Question.query.filter(Question.id.in_(test_question_ids)).all() if test_question_ids else []
            total_questions = len(questions)
            
            if total_questions == 0:
                logging.warning(f"Nenhuma questão encontrada para o teste {test_id}")
                return None
            
            # Buscar respostas do aluno
            answers = StudentAnswer.query.filter_by(
                test_id=test_id,
                student_id=student_id
            ).all()
            
            # Calcular acertos
            correct_answers = 0
            for answer in answers:
                question = next((q for q in questions if q.id == answer.question_id), None)
                if question:
                    if question.question_type == 'multiple_choice':
                        # Verificar usando correct_answer para questões de múltipla escolha
                        is_correct = EvaluationResultService.check_multiple_choice_answer(answer.answer, question.correct_answer)
                        if is_correct:
                            correct_answers += 1
                    elif question.correct_answer:
                        # Para outros tipos de questão que usam correct_answer
                        if str(answer.answer).strip().lower() == str(question.correct_answer).strip().lower():
                            correct_answers += 1
            
            # Buscar nome do curso baseado no ID
            course_name = "Anos Iniciais"  # Padrão
            if test.course:
                try:
                    from app.models.educationStage import EducationStage
                    import uuid
                    course_uuid = uuid.UUID(test.course)
                    course_obj = EducationStage.query.get(course_uuid)
                    if course_obj:
                        course_name = course_obj.name
                except (ValueError, TypeError, Exception):
                    pass
            
            # Determinar se deve usar subjects_info ou subject_rel
            use_subjects_info = False
            subject_name = "Outras"
            
            if test.subjects_info and isinstance(test.subjects_info, list) and len(test.subjects_info) > 0:
                # Verificar se há questões com subject_id (múltiplas disciplinas)
                questions_with_subject = [q for q in questions if q.subject_id]
                if questions_with_subject:
                    use_subjects_info = True
                    logging.info(f"Usando subjects_info para cálculo de proficiência por disciplina")
                else:
                    # Se não há subject_id nas questões, usar subject_rel
                    subject_name = test.subject_rel.name if test.subject_rel else "Outras"
            else:
                # Usar subject_rel como fallback
                subject_name = test.subject_rel.name if test.subject_rel else "Outras"
            
            # Determinar tipo de cálculo baseado na configuração do teste
            use_simple_calculation = test.grade_calculation_type == 'simple'
            
            if use_subjects_info:
                # Calcular resultados por disciplina
                subject_results = EvaluationResultService._calculate_subject_specific_results(
                    test_id, student_id, questions, answers, course_name
                )
                
                # CORREÇÃO: Calcular resultado geral como média aritmética das disciplinas
                if subject_results:
                    # Calcular proficiência geral como média das disciplinas
                    proficiencies = [sr['proficiency'] for sr in subject_results]
                    grades = [sr['grade'] for sr in subject_results]
                    
                    proficiency_geral = sum(proficiencies) / len(proficiencies) if proficiencies else 0.0
                    grade_geral = sum(grades) / len(grades) if grades else 0.0
                    
                    # Determinar se a avaliação tem Matemática (para regra do GERAL)
                    has_matematica = any(
                        (sr.get('subject_name') and 'matem' in str(sr.get('subject_name')).lower())
                        for sr in subject_results
                    )

                    # Classificação geral baseada na proficiência média, alinhada à disciplina efetiva do GERAL
                    classification_geral = EvaluationCalculator.determine_classification(
                        proficiency_geral,
                        course_name,
                        "GERAL",
                        has_matematica=has_matematica,
                    )
                    
                    result = {
                        'proficiency': round_to_two_decimals(proficiency_geral),
                        'grade': round_to_two_decimals(grade_geral),
                        'classification': classification_geral,
                        'correct_answers': correct_answers,
                        'total_questions': total_questions,
                        'accuracy_rate': round_to_two_decimals((correct_answers / total_questions) * 100) if total_questions > 0 else 0.0
                    }
                else:
                    # Fallback se não conseguir calcular por disciplina
                    result = EvaluationCalculator.calculate_complete_evaluation(
                        correct_answers=correct_answers,
                        total_questions=total_questions,
                        course_name=course_name,
                        subject_name=subject_name,
                        use_simple_calculation=use_simple_calculation
                    )
            else:
                # Calcular resultado geral (método original)
                result = EvaluationCalculator.calculate_complete_evaluation(
                    correct_answers=correct_answers,
                    total_questions=total_questions,
                    course_name=course_name,
                    subject_name=subject_name,
                    use_simple_calculation=use_simple_calculation
                )
            
            # Calcular percentual de acertos
            score_percentage = (correct_answers / total_questions * 100) if total_questions > 0 else 0
            
            # Preparar resultados por disciplina para salvar em JSON
            subject_results_json = None
            if use_subjects_info and subject_results:
                subject_results_json = {}
                for sr in subject_results:
                    subject_results_json[str(sr['subject_id'])] = {
                        'subject_name': sr['subject_name'],
                        'correct_answers': sr['correct_answers'],
                        'total_questions': sr['total_questions'],
                        'answered_questions': sr['answered_questions'],
                        'score_percentage': sr['score_percentage'],
                        'grade': sr['grade'],
                        'proficiency': sr['proficiency'],
                        'classification': sr['classification']
                    }
            
            # Verificar se já existe resultado para este aluno neste teste
            existing_result = EvaluationResult.query.filter_by(
                test_id=test_id,
                student_id=student_id
            ).first()
            
            if existing_result:
                # Atualizar resultado existente (não alterar session_id para evitar problemas de FK)
                existing_result.correct_answers = correct_answers
                existing_result.total_questions = total_questions
                existing_result.score_percentage = score_percentage
                existing_result.grade = result['grade']
                existing_result.proficiency = result['proficiency']
                existing_result.classification = result['classification']
                existing_result.subject_results = subject_results_json
                existing_result.calculated_at = datetime.utcnow()
                
                evaluation_result = existing_result
            else:
                # Criar novo resultado
                evaluation_result = EvaluationResult(
                    test_id=test_id,
                    student_id=student_id,
                    session_id=session_id,
                    correct_answers=correct_answers,
                    total_questions=total_questions,
                    score_percentage=score_percentage,
                    grade=result['grade'],
                    proficiency=result['proficiency'],
                    classification=result['classification']
                )
                evaluation_result.subject_results = subject_results_json
                db.session.add(evaluation_result)

            # Marcar agregados como desatualizados antes do commit
            scope_school_id = None
            scope_city_id = None
            student_obj = Student.query.get(student_id)
            if student_obj:
                scope_school_id = getattr(student_obj, 'school_id', None)
                class_identifier = getattr(student_obj, 'class_id', None)
                if not scope_school_id and class_identifier:
                    class_obj = Class.query.get(class_identifier)
                    if class_obj and getattr(class_obj, 'school_id', None):
                        scope_school_id = class_obj.school_id
                if scope_school_id:
                    school_obj = School.query.get(scope_school_id)
                    if school_obj and getattr(school_obj, 'city_id', None):
                        scope_city_id = school_obj.city_id
                    else:
                        scope_city_id = None

            # Marcar todos os escopos como dirty
            ReportAggregateService.mark_dirty(test_id, 'overall', None, commit=False)
            ReportAggregateService.mark_ai_dirty(test_id, 'overall', None, commit=False)
            
            if scope_school_id:
                ReportAggregateService.mark_dirty(test_id, 'school', scope_school_id, commit=False)
                ReportAggregateService.mark_ai_dirty(test_id, 'school', scope_school_id, commit=False)
            
            if scope_city_id:
                ReportAggregateService.mark_dirty(test_id, 'city', scope_city_id, commit=False)
                ReportAggregateService.mark_ai_dirty(test_id, 'city', scope_city_id, commit=False)
            
            # Marcar dirty para professores vinculados às turmas do aluno
            if class_identifier:
                from app.models.teacherClass import TeacherClass
                
                # Buscar professores vinculados à turma do aluno
                teacher_classes = TeacherClass.query.filter_by(class_id=class_identifier).all()
                teacher_ids = [tc.teacher_id for tc in teacher_classes]
                
                # Marcar dirty para cada professor
                for teacher_id in teacher_ids:
                    ReportAggregateService.mark_dirty(test_id, 'teacher', teacher_id, commit=False)
                    ReportAggregateService.mark_ai_dirty(test_id, 'teacher', teacher_id, commit=False)
            
            db.session.commit()
            
            # Disparar task Celery para rebuild (com debounce). Passar city_id para a task
            # setar o schema do tenant (multi-tenant: Celery não tem JWT/request).
            try:
                if scope_city_id:
                    from app.report_analysis.tasks import rebuild_reports_for_test
                    rebuild_reports_for_test.delay(test_id, str(scope_city_id))
                    logging.info(f"Task de rebuild agendada para test_id={test_id}, city_id={scope_city_id}")
                else:
                    logging.debug("Rebuild não agendado: scope_city_id ausente (sem tenant para report_aggregates)")
            except Exception as e:
                logging.warning(f"Erro ao agendar task de rebuild: {str(e)}. Continuando sem rebuild automático.")
                # Não falhar se Celery não estiver disponível
            
            # Preparar resposta com informações adicionais se houver múltiplas disciplinas
            response_data = {
                'id': evaluation_result.id,
                'test_id': test_id,
                'student_id': student_id,
                'session_id': session_id,
                'correct_answers': correct_answers,
                'total_questions': total_questions,
                'score_percentage': score_percentage,
                'grade': result['grade'],
                'proficiency': result['proficiency'],
                'classification': result['classification'],
                'calculated_at': evaluation_result.calculated_at.isoformat() if evaluation_result.calculated_at else None
            }
            
            # Adicionar resultados por disciplina se disponível
            if use_subjects_info and 'subject_results' in locals():
                response_data['subject_results'] = subject_results
                response_data['calculation_method'] = 'by_subject'
            else:
                response_data['calculation_method'] = 'general'
            
            return response_data
            
        except Exception as e:
            logging.error(f"Erro ao calcular resultado para aluno {student_id} no teste {test_id}: {str(e)}", exc_info=True)
            db.session.rollback()
            return None
    
    @staticmethod
    def get_evaluation_results(test_id: str) -> Dict[str, Any]:
        """
        Busca todos os resultados calculados de uma avaliação
        
        Args:
            test_id: ID do teste
            
        Returns:
            Dicionário com estatísticas agregadas
        """
        try:
            from app.models.classTest import ClassTest
            from app.models.student import Student
            
            # Buscar todas as turmas onde a avaliação foi aplicada
            class_tests = ClassTest.query.filter_by(test_id=test_id).all()
            class_ids = [ct.class_id for ct in class_tests]
            
            if not class_ids:
                return {
                    'total_alunos': 0,
                    'alunos_participantes': 0,
                    'alunos_pendentes': 0,
                    'alunos_ausentes': 0,
                    'media_nota': 0.0,
                    'media_proficiencia': 0.0,
                    'distribuicao_classificacao': {
                        'abaixo_do_basico': 0,
                        'basico': 0,
                        'adequado': 0,
                        'avancado': 0
                    }
                }
            
            # Buscar todos os alunos das turmas envolvidas
            todos_alunos = Student.query.filter(Student.class_id.in_(class_ids)).all()
            total_alunos = len(todos_alunos)
            
            # Buscar resultados dos alunos
            from app.models.evaluationResult import EvaluationResult
            results = EvaluationResult.query.filter_by(test_id=test_id).all()
            
            if not results:
                return {
                    'total_alunos': total_alunos,
                    'alunos_participantes': 0,
                    'alunos_pendentes': total_alunos,
                    'alunos_ausentes': 0,
                    'media_nota': 0.0,
                    'media_proficiencia': 0.0,
                    'distribuicao_classificacao': {
                        'abaixo_do_basico': 0,
                        'basico': 0,
                        'adequado': 0,
                        'avancado': 0
                    }
                }
            
            # Calcular estatísticas
            alunos_participantes = len(results)
            alunos_pendentes = total_alunos - alunos_participantes
            
            if alunos_participantes > 0:
                media_nota = sum(r.grade for r in results) / alunos_participantes
                media_proficiencia = sum(r.proficiency for r in results) / alunos_participantes
            else:
                media_nota = 0.0
                media_proficiencia = 0.0
            
            # Distribuição de classificação
            distribuicao = {
                'abaixo_do_basico': 0,
                'basico': 0,
                'adequado': 0,
                'avancado': 0
            }
            
            for result in results:
                if result.classification:
                    classification_lower = result.classification.lower().replace(' ', '_')
                    if classification_lower in distribuicao:
                        distribuicao[classification_lower] += 1
            
            return {
                'total_alunos': total_alunos,
                'alunos_participantes': alunos_participantes,
                'alunos_pendentes': alunos_pendentes,
                'alunos_ausentes': 0,
                'media_nota': round(media_nota, 2),
                'media_proficiencia': round(media_proficiencia, 2),
                'distribuicao_classificacao': distribuicao
            }
            
        except Exception as e:
            logging.error(f"Erro ao buscar resultados dos alunos do teste {test_id}: {str(e)}", exc_info=True)
            return []
    
    @staticmethod
    def get_subject_detailed_statistics(test_id: str, scope_info: dict = None, nivel_granularidade: str = None) -> Dict[str, Any]:
        """
        Obtém estatísticas detalhadas por disciplina de uma avaliação
        CORRIGIDO: Agora segue o fluxo correto: evaluation_results → test → subjects_info → education_stage
        
        Args:
            test_id: ID do teste
            
        Returns:
            Dicionário com estatísticas detalhadas por disciplina
        """
        try:
            from app.models.test import Test
            from app.models.question import Question
            from app.models.subject import Subject
            from app.models.testQuestion import TestQuestion
            from app.models.evaluationResult import EvaluationResult
            from app.models.educationStage import EducationStage
            from app.services.evaluation_calculator import EvaluationCalculator
            
            # 1. Buscar o teste
            test = Test.query.get(test_id)
            if not test:
                return {"error": "Teste não encontrado"}
            
            # 2. Verificar se há subjects_info (OBRIGATÓRIO - sem fallback)
            if not test.subjects_info:
                return {"error": "Campo subjects_info é obrigatório e não foi preenchido"}
            
            # 3. Buscar o nome do curso usando o course ID
            course_name = "Anos Iniciais"  # Padrão
            if test.course:
                education_stage = EducationStage.query.get(test.course)
                if education_stage:
                    course_name = education_stage.name
                else:
                    return {"error": f"Course ID {test.course} não encontrado na education_stage"}
            
            # 4. Processar subjects_info (pode ser lista de IDs ou lista de objetos)
            subject_ids = []
            if isinstance(test.subjects_info, list):
                for subject_info in test.subjects_info:
                    if isinstance(subject_info, dict):
                        # Se é objeto com 'id'
                        if 'id' in subject_info:
                            subject_ids.append(subject_info['id'])
                    elif isinstance(subject_info, str):
                        # Se é string (ID direto)
                        subject_ids.append(subject_info)
            else:
                return {"error": "subjects_info deve ser uma lista"}
            
            if not subject_ids:
                return {"error": "Nenhuma disciplina encontrada em subjects_info"}
            
            # 5. Buscar informações das disciplinas
            subjects = Subject.query.filter(Subject.id.in_(subject_ids)).all()
            if not subjects:
                return {"error": "Disciplinas não encontradas na tabela Subject"}
            
            # 6. Buscar questões do teste agrupadas por disciplina
            test_question_ids = [tq.question_id for tq in TestQuestion.query.filter_by(test_id=test_id).order_by(TestQuestion.order).all()]
            questions = Question.query.filter(Question.id.in_(test_question_ids)).all() if test_question_ids else []
            
            if not questions:
                return {"error": "Nenhuma questão encontrada para este teste"}
            
            # 7. Agrupar questões por disciplina usando subjects_info
            questions_by_subject = {}
            for question in questions:
                if question.subject_id and str(question.subject_id) in subject_ids:
                    if question.subject_id not in questions_by_subject:
                        questions_by_subject[question.subject_id] = []
                    questions_by_subject[question.subject_id].append(question)
            
            # 8. Buscar resultados dos alunos (com filtros de granularidade se especificados)
            if scope_info and nivel_granularidade:
                # Aplicar filtros de granularidade
                from app.routes.evaluation_results_routes import _determinar_escopo_calculo, _buscar_alunos_por_escopo

                escopo_calculo = _determinar_escopo_calculo(scope_info, nivel_granularidade)
                alunos_escopo = _buscar_alunos_por_escopo(escopo_calculo)

                if alunos_escopo:
                    student_ids = [aluno.id for aluno in alunos_escopo]
                    results = EvaluationResult.query.filter(
                        EvaluationResult.test_id == test_id,
                        EvaluationResult.student_id.in_(student_ids)
                    ).all()
                else:
                    results = []
            else:
                # Sem filtros de granularidade, buscar todos os resultados
                results = EvaluationResult.query.filter_by(test_id=test_id).all()

            subject_statistics = {}
            
            # 9. Para cada disciplina em subjects_info, calcular estatísticas
            for subject in subjects:
                subject_id = subject.id
                subject_name = subject.name
                
                if subject_id not in questions_by_subject:
                    continue
                
                subject_questions = questions_by_subject[subject_id]
                total_questions_subject = len(subject_questions)
                
                # Filtrar questões desta disciplina que têm correct_answer
                questions_with_answer = [q for q in subject_questions if q.correct_answer]
                
                if not questions_with_answer:
                    continue
                
                # Buscar estatísticas dos alunos para esta disciplina (USAR DADOS SALVOS DO JSON)
                subject_results = []
                for result in results:
                    # Buscar resultado pré-calculado por disciplina do campo JSON
                    if result.subject_results and str(subject_id) in result.subject_results:
                        # Usar dados pré-calculados do JSON (FONTE DA VERDADE)
                        subject_data = result.subject_results[str(subject_id)]
                        subject_results.append({
                            'student_id': result.student_id,
                            'correct_answers': subject_data.get('correct_answers', 0),
                            'total_questions': subject_data.get('answered_questions', 0),
                            'proficiency': subject_data.get('proficiency', 0.0),
                            'grade': subject_data.get('grade', 0.0),
                            'classification': subject_data.get('classification', 'Abaixo do Básico'),
                            'score_percentage': subject_data.get('score_percentage', 0.0)
                        })
                    else:
                        # Fallback: calcular se não houver dados salvos (não deveria acontecer)
                        logging.warning(f"Resultado por disciplina não encontrado no JSON para aluno {result.student_id}, disciplina {subject_id}. Recalculando...")
                        
                        from app.models.studentAnswer import StudentAnswer
                        subject_question_ids = [q.id for q in questions_with_answer]
                        student_answers = StudentAnswer.query.filter(
                            StudentAnswer.test_id == test_id,
                            StudentAnswer.student_id == result.student_id,
                            StudentAnswer.question_id.in_(subject_question_ids)
                        ).all()
                        
                        total_respondidas = len(student_answers)
                        
                        if total_respondidas == 0:
                            continue
                        
                        correct_answers_subject = 0
                        for answer in student_answers:
                            question = next((q for q in questions_with_answer if q.id == answer.question_id), None)
                            if question:
                                if question.question_type == 'multiple_choice':
                                    is_correct = EvaluationResultService.check_multiple_choice_answer(answer.answer, question.correct_answer)
                                    if is_correct:
                                        correct_answers_subject += 1
                                elif question.correct_answer:
                                    if str(answer.answer).strip().lower() == str(question.correct_answer).strip().lower():
                                        correct_answers_subject += 1
                        
                        evaluation_result = EvaluationCalculator.calculate_complete_evaluation(
                            correct_answers=correct_answers_subject,
                            total_questions=total_respondidas,
                            course_name=course_name,
                            subject_name=subject_name
                        )
                        
                        subject_results.append({
                            'student_id': result.student_id,
                            'correct_answers': correct_answers_subject,
                            'total_questions': total_respondidas,
                            'proficiency': evaluation_result['proficiency'],
                            'grade': evaluation_result['grade'],
                            'classification': evaluation_result['classification'],
                            'score_percentage': round_to_two_decimals((correct_answers_subject / total_respondidas) * 100) if total_respondidas > 0 else 0
                        })
                
                if subject_results:
                    # Médias por disciplina: mesmo peso por escola (média das médias escolares)
                    total_students = len(subject_results)
                    avg_grade, avg_proficiency, avg_score_percentage = (
                        mean_grade_and_proficiency_equal_weight_by_school_from_subject_rows(
                            subject_results, student_id_key="student_id"
                        )
                    )
                    avg_proficiency = round_to_two_decimals(avg_proficiency)
                    avg_grade = round_to_two_decimals(avg_grade)
                    avg_score_percentage = round_to_two_decimals(avg_score_percentage)
                    
                    # Distribuição de classificação
                    classification_distribution = {
                        'abaixo_do_basico': 0,
                        'basico': 0,
                        'adequado': 0,
                        'avancado': 0
                    }
                    
                    for sr in subject_results:
                        classification = sr['classification'].lower()
                        # CORREÇÃO: Verificar 'abaixo' primeiro para evitar classificar 'Básico' como 'Abaixo do Básico'
                        if 'abaixo' in classification:
                            classification_distribution['abaixo_do_basico'] += 1
                        elif 'básico' in classification or 'basico' in classification:
                            classification_distribution['basico'] += 1
                        elif 'adequado' in classification:
                            classification_distribution['adequado'] += 1
                        elif 'avançado' in classification or 'avancado' in classification:
                            classification_distribution['avancado'] += 1
                    
                    subject_statistics[subject_name] = {
                        'subject_id': str(subject_id),
                        'subject_name': subject_name,
                        'total_questions': total_questions_subject,
                        'questions_with_answer': len(questions_with_answer),
                        'total_students': total_students,
                        'average_proficiency': avg_proficiency,  # Já arredondado para 2 casas decimais
                        'average_grade': avg_grade,  # Já arredondado para 2 casas decimais
                        'average_score_percentage': avg_score_percentage,  # Já arredondado para 2 casas decimais
                        'classification_distribution': classification_distribution,
                        'student_results': subject_results
                    }
            
            return {
                'test_id': test_id,
                'test_title': test.title,
                'course_name': course_name,
                'subjects_count': len(subject_statistics),
                'subjects': subject_statistics
            }
            
        except Exception as e:
            logging.error(f"Erro ao obter estatísticas detalhadas por disciplina para teste {test_id}: {str(e)}", exc_info=True)
            return {"error": f"Erro ao calcular estatísticas: {str(e)}"}
    
    @staticmethod
    def get_student_result(test_id: str, student_id: str) -> Optional[Dict[str, Any]]:
        """
        Busca resultado de um aluno específico
        
        Args:
            test_id: ID do teste
            student_id: ID do aluno
            
        Returns:
            Dicionário com resultado do aluno ou None se não encontrado
        """
        try:
            result = EvaluationResult.query.filter_by(
                test_id=test_id,
                student_id=student_id
            ).first()
            
            if not result:
                return None
            
            return result.to_dict()
            
        except Exception as e:
            logging.error(f"Erro ao buscar resultado do aluno {student_id} no teste {test_id}: {str(e)}", exc_info=True)
            return None
    
    @staticmethod
    def get_all_student_results(test_id: str) -> list:
        """
        Busca resultados de todos os alunos de uma avaliação
        
        Args:
            test_id: ID do teste
            
        Returns:
            Lista com resultados de todos os alunos
        """
        try:
            results = EvaluationResult.query.filter_by(test_id=test_id).all()
            return [result.to_dict() for result in results]
            
        except Exception as e:
            logging.error(f"Erro ao buscar resultados dos alunos do teste {test_id}: {str(e)}", exc_info=True)
            return [] 