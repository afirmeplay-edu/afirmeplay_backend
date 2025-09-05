# -*- coding: utf-8 -*-
"""
Serviço principal para gerenciar formulários físicos de provas
Integra com o banco de dados e coordena a geração e correção
"""

import os
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from app import db
from app.models.test import Test
from app.models.question import Question
from app.models.testQuestion import TestQuestion
from app.models.student import Student
from app.models.classTest import ClassTest
from app.models.studentClass import Class
from app.models.school import School
from app.models.physicalTestForm import PhysicalTestForm
from app.models.physicalTestAnswer import PhysicalTestAnswer
from app.services.physical_test_pdf_generator import PhysicalTestPDFGenerator
from app.services.physical_test_correction import PhysicalTestCorrection
from app.services.evaluation_calculator import EvaluationCalculator
from app.services.evaluation_result_service import EvaluationResultService
from sqlalchemy.orm import joinedload
from sqlalchemy import and_

class PhysicalTestFormService:
    """
    Serviço principal para gerenciar formulários físicos
    """
    
    def __init__(self):
        self.pdf_generator = PhysicalTestPDFGenerator()
        self.correction_service = PhysicalTestCorrection()
        self.evaluation_calculator = EvaluationCalculator()
        self.evaluation_result_service = EvaluationResultService()

    def generate_physical_forms(self, test_id: str, output_dir: str = "physical_forms") -> Dict[str, Any]:
        """
        Gera formulários físicos para uma prova específica
        
        Args:
            test_id: ID da prova
            output_dir: Diretório para salvar os PDFs
            
        Returns:
            Dicionário com resultado da operação
        """
        try:
            # Verificar se a prova existe
            test = Test.query.get(test_id)
            if not test:
                return {
                    'success': False,
                    'error': 'Prova não encontrada',
                    'generated_forms': 0
                }
            
            # Verificar se a prova foi aplicada (class_test existe)
            class_tests = ClassTest.query.filter_by(test_id=test_id).all()
            if not class_tests:
                return {
                    'success': False,
                    'error': 'A prova precisa ser aplicada primeiro (class_test)',
                    'generated_forms': 0
                }
            
            # Para formulários físicos, consideramos aplicada se existe class_test
            # O status 'agendada' indica que a prova foi aplicada e está disponível
            applied_tests = class_tests
            
            # Buscar questões da prova ordenadas
            questions = self._get_test_questions(test_id)
            if not questions:
                return {
                    'success': False,
                    'error': 'Nenhuma questão encontrada para esta prova',
                    'generated_forms': 0
                }
            
            # Buscar alunos das turmas onde a prova foi aplicada
            students = self._get_students_from_applied_tests(applied_tests)
            if not students:
                return {
                    'success': False,
                    'error': 'Nenhum aluno encontrado nas turmas aplicadas',
                    'generated_forms': 0
                }
            
            # Preparar dados para geração
            test_data = {
                'id': test.id,
                'title': test.title,
                'description': test.description,
                'type': test.type
            }
            
            questions_data = [self._format_question_data(q) for q in questions]
            students_data = [self._format_student_data(s) for s in students]
            
            # Gerar apenas PDF combinado (1 arquivo com todas as provas e gabaritos)
            combined_pdf_path = self.pdf_generator.generate_combined_test_pdf(
                test_data, students_data, questions_data, output_dir
            )
            
            # Criar lista com apenas o PDF combinado
            generated_files = []
            if combined_pdf_path:
                generated_files.append({
                    'student_id': 'combined',
                    'student_name': test.title,  # Usar nome da prova
                    'pdf_path': combined_pdf_path,
                    'answer_key_path': None,
                    'qr_code_data': 'combined'
                })
            
            # Salvar informações no banco de dados
            saved_forms = self._save_physical_forms_to_db(
                test_id, students, generated_files, questions
            )
            
            return {
                'success': True,
                'message': f'Formulários gerados com sucesso',
                'generated_forms': len(saved_forms),
                'test_title': test.title,
                'total_questions': len(questions),
                'total_students': len(students),
                'forms': saved_forms
            }
            
        except Exception as e:
            logging.error(f"Erro ao gerar formulários físicos: {str(e)}")
            return {
                'success': False,
                'error': f'Erro interno: {str(e)}',
                'generated_forms': 0
            }

    def process_physical_correction(self, test_id: str, image_data: bytes, 
                                  correction_image_url: str = None) -> Dict[str, Any]:
        """
        Processa correção de gabarito físico
        
        Args:
            test_id: ID da prova
            image_data: Dados da imagem do gabarito preenchido
            correction_image_url: URL para salvar imagem corrigida
            
        Returns:
            Dicionário com resultado da correção
        """
        try:
            # Buscar questões da prova
            questions = self._get_test_questions(test_id)
            if not questions:
                return {
                    'success': False,
                    'error': 'Nenhuma questão encontrada para esta prova'
                }
            
            questions_data = [self._format_question_data(q) for q in questions]
            
            # Processar correção usando OpenCV
            correction_result = self.correction_service.process_correction(
                image_data, test_id, questions_data
            )
            
            if not correction_result['success']:
                return correction_result
            
            student_id = correction_result['student_id']
            
            # Buscar formulário físico do aluno
            physical_form = PhysicalTestForm.query.filter_by(
                test_id=test_id,
                student_id=student_id
            ).first()
            
            if not physical_form:
                return {
                    'success': False,
                    'error': f'Formulário físico não encontrado para o aluno {student_id}'
                }
            
            # Salvar respostas físicas no banco
            self._save_physical_answers(
                physical_form, correction_result['marked_answers'], questions
            )
            
            # Atualizar status do formulário
            physical_form.status = 'corrigido'
            physical_form.is_corrected = True
            physical_form.corrected_at = datetime.utcnow()
            
            # Salvar imagem corrigida no banco
            if correction_result.get('corrected_image'):
                physical_form.correction_image_data = correction_result['corrected_image']
                if correction_image_url:
                    physical_form.correction_image_url = correction_image_url
            
            db.session.commit()
            
            # Calcular resultados usando o sistema existente
            evaluation_results = self._calculate_evaluation_results(
                test_id, student_id, correction_result
            )
            
            return {
                'success': True,
                'message': 'Correção processada com sucesso',
                'student_id': student_id,
                'correction_results': correction_result['correction_results'],
                'evaluation_results': evaluation_results,
                'physical_form_id': physical_form.id
            }
            
        except Exception as e:
            logging.error(f"Erro ao processar correção física: {str(e)}")
            db.session.rollback()
            return {
                'success': False,
                'error': f'Erro interno: {str(e)}'
            }

    def _get_test_questions(self, test_id: str) -> List[Question]:
        """Busca questões da prova ordenadas"""
        return Question.query.join(TestQuestion).filter(
            TestQuestion.test_id == test_id
        ).order_by(TestQuestion.order).all()

    def _get_students_from_applied_tests(self, applied_tests: List[ClassTest]) -> List[Student]:
        """Busca alunos das turmas onde a prova foi aplicada"""
        class_ids = [ct.class_id for ct in applied_tests]
        
        return Student.query.options(
            joinedload(Student.class_),
            joinedload(Student.user)
        ).filter(Student.class_id.in_(class_ids)).all()

    def _format_question_data(self, question: Question) -> Dict[str, Any]:
        """Formata dados da questão para geração de PDF"""
        # Buscar códigos das habilidades
        skill_codes = []
        if question.skill:
            from app.models.skill import Skill
            # Verificar se skill é uma lista ou string única
            if isinstance(question.skill, list):
                skill_ids = question.skill
            else:
                skill_ids = [question.skill]
            
            skills = Skill.query.filter(Skill.id.in_(skill_ids)).all()
            skill_codes = [skill.code for skill in skills if skill.code]
        
        return {
            'id': question.id,
            'title': question.title,
            'text': question.text,
            'formatted_text': question.formatted_text,
            'secondstatement': question.secondstatement,
            'alternatives': question.alternatives or [],
            'correct_answer': question.correct_answer,
            'value': question.value or 1.0,
            'question_type': question.question_type,
            'difficulty_level': question.difficulty_level,
            'skills': skill_codes,  # Códigos das habilidades
            'images': question.images or []
        }

    def _format_student_data(self, student: Student) -> Dict[str, Any]:
        """Formata dados do aluno para geração de PDF"""
        return {
            'id': student.id,
            'nome': student.name,
            'email': student.user.email if student.user else None
        }

    def _save_physical_forms_to_db(self, test_id: str, students: List[Student], 
                                  generated_files: List[Dict], questions: List[Question]) -> List[Dict]:
        """Salva informações dos formulários físicos no banco de dados"""
        saved_forms = []
        
        # Verificar se é PDF combinado
        combined_file = next(
            (f for f in generated_files if f['student_id'] == 'combined'), 
            None
        )
        
        if combined_file:
            # PDF combinado - criar apenas 1 registro com nome da prova
            # Usar o primeiro aluno para class_test_id (todos têm o mesmo)
            first_student = students[0]
            class_test = ClassTest.query.filter_by(
                test_id=test_id,
                class_id=first_student.class_id
            ).first()
            
            if class_test:
                # Ler PDF combinado e salvar no banco
                pdf_data = None
                if combined_file.get('pdf_path') and os.path.exists(combined_file['pdf_path']):
                    with open(combined_file['pdf_path'], 'rb') as f:
                        pdf_data = f.read()
                
                # Criar registro único do formulário físico
                # Usar o primeiro aluno como student_id (campo obrigatório)
                physical_form = PhysicalTestForm(
                    test_id=test_id,
                    student_id=first_student.id,  # Usar primeiro aluno (campo obrigatório)
                    class_test_id=class_test.id,
                    form_pdf_data=pdf_data,
                    form_pdf_url=combined_file.get('pdf_path'),
                    qr_code_data='combined',  # QR Code especial para PDF combinado
                    status='gerado'
                )
                
                db.session.add(physical_form)
                db.session.flush()  # Para obter o ID
                
                # Adicionar à lista de retorno com nome da prova
                form_dict = physical_form.to_dict()
                form_dict['student_name'] = combined_file.get('student_name', 'Prova Completa')
                form_dict['student_id'] = 'combined'
                saved_forms.append(form_dict)
            
            # Commit das alterações
            db.session.commit()
            return saved_forms
        
        # Código original para PDFs individuais (mantido para compatibilidade)
        for student in students:
            # Encontrar arquivo gerado para este aluno
            student_file = next(
                (f for f in generated_files if f['student_id'] == student.id), 
                None
            )
            
            if student_file:
                # Buscar class_test para este aluno
                class_test = ClassTest.query.filter_by(
                    test_id=test_id,
                    class_id=student.class_id
                ).first()
                
                if class_test:
                    # Ler PDF do aluno e salvar no banco
                    pdf_data = None
                    if student_file.get('pdf_path') and os.path.exists(student_file['pdf_path']):
                        with open(student_file['pdf_path'], 'rb') as f:
                            pdf_data = f.read()
                    
                    # Ler gabarito e salvar no banco (apenas no primeiro aluno)
                    answer_key_data = None
                    if (student == students[0] and 
                        'answer_key_path' in student_file and 
                        student_file['answer_key_path'] and 
                        os.path.exists(student_file['answer_key_path'])):
                        with open(student_file['answer_key_path'], 'rb') as f:
                            answer_key_data = f.read()
                    
                    # Criar registro do formulário físico
                    physical_form = PhysicalTestForm(
                        test_id=test_id,
                        student_id=student.id,
                        class_test_id=class_test.id,
                        form_pdf_data=pdf_data,
                        answer_sheet_data=answer_key_data,  # Gabarito salvo apenas no primeiro registro
                        form_pdf_url=student_file.get('pdf_path'),  # Manter para compatibilidade
                        qr_code_data=student_file['qr_code_data'],
                        status='gerado'
                    )
                    
                    db.session.add(physical_form)
                    db.session.flush()  # Para obter o ID
                    
                    saved_forms.append({
                        'id': physical_form.id,
                        'student_id': student.id,
                        'student_name': student.name,
                        'pdf_url': student_file.get('pdf_path'),
                        'has_pdf_data': pdf_data is not None,
                        'qr_code_data': student_file.get('qr_code_data')
                    })
        
        db.session.commit()
        return saved_forms

    def _save_physical_answers(self, physical_form: PhysicalTestForm, 
                             marked_answers: List[Dict], questions: List[Question]):
        """Salva respostas físicas detectadas no banco de dados"""
        # Criar dicionário de respostas por questão
        answers_by_question = {}
        for answer in marked_answers:
            q_num = answer['question_number']
            if q_num not in answers_by_question:
                answers_by_question[q_num] = []
            answers_by_question[q_num].append(answer)
        
        # Salvar cada resposta
        for i, question in enumerate(questions, 1):
            correct_answer = question.correct_answer
            marked_for_question = answers_by_question.get(i, [])
            
            if marked_for_question:
                # Pegar a resposta com maior confiança
                best_answer = max(marked_for_question, key=lambda x: x['confidence'])
                marked_answer = best_answer['alternative']
                confidence = best_answer['confidence']
                coordinates = best_answer['coordinates']
                
                is_correct = marked_answer.upper() == correct_answer.upper()
            else:
                marked_answer = None
                confidence = 0.0
                coordinates = None
                is_correct = False
            
            # Criar registro da resposta física
            physical_answer = PhysicalTestAnswer(
                physical_form_id=physical_form.id,
                question_id=question.id,
                marked_answer=marked_answer,
                correct_answer=correct_answer,
                is_correct=is_correct,
                confidence_score=confidence,
                detection_coordinates=coordinates
            )
            
            db.session.add(physical_answer)

    def _calculate_evaluation_results(self, test_id: str, student_id: str, 
                                    correction_result: Dict) -> Optional[Dict]:
        """Calcula resultados da avaliação usando o sistema existente"""
        try:
            # Buscar dados da prova
            test = Test.query.get(test_id)
            if not test:
                return None
            
            # Buscar questões
            questions = self._get_test_questions(test_id)
            
            # Calcular proficiência, nota e classificação
            correction_data = correction_result['correction_results']
            correct_answers = correction_data['correct_answers']
            total_questions = correction_data['total_questions']
            
            # Determinar curso e disciplina
            course_name = test.course or "Anos Iniciais"
            subject_name = "Matemática"  # Pode ser extraído do test.subject
            
            # Calcular proficiência
            proficiency = self.evaluation_calculator.calculate_proficiency(
                correct_answers, total_questions, course_name, subject_name
            )
            
            # Calcular nota
            grade = self.evaluation_calculator.calculate_grade(
                proficiency, course_name, subject_name
            )
            
            # Determinar classificação
            classification = self.evaluation_calculator.determine_classification(
                proficiency, course_name, subject_name
            )
            
            # Calcular percentual
            score_percentage = (correct_answers / total_questions) * 100 if total_questions > 0 else 0
            
            return {
                'correct_answers': correct_answers,
                'total_questions': total_questions,
                'score_percentage': round(score_percentage, 2),
                'grade': grade,
                'proficiency': proficiency,
                'classification': classification
            }
            
        except Exception as e:
            logging.error(f"Erro ao calcular resultados da avaliação: {str(e)}")
            return None

    def get_physical_forms_by_test(self, test_id: str) -> List[Dict]:
        """Busca formulários físicos de uma prova"""
        forms = PhysicalTestForm.query.filter_by(test_id=test_id).all()
        return [form.to_dict() for form in forms]

    def get_physical_form_by_student(self, test_id: str, student_id: str) -> Optional[Dict]:
        """Busca formulário físico de um aluno específico"""
        form = PhysicalTestForm.query.filter_by(
            test_id=test_id,
            student_id=student_id
        ).first()
        
        return form.to_dict() if form else None

    def delete_physical_form(self, form_id: str) -> Dict[str, Any]:
        """
        Exclui um formulário físico específico
        
        Args:
            form_id: ID do formulário físico
            
        Returns:
            Dicionário com resultado da operação
        """
        try:
            # Buscar formulário físico
            physical_form = PhysicalTestForm.query.get(form_id)
            if not physical_form:
                return {
                    'success': False,
                    'error': 'Formulário físico não encontrado'
                }
            
            test_id = physical_form.test_id
            student_id = physical_form.student_id
            
            # Excluir respostas físicas relacionadas
            physical_answers = PhysicalTestAnswer.query.filter_by(
                physical_form_id=form_id
            ).all()
            
            for answer in physical_answers:
                db.session.delete(answer)
            
            logging.info(f"🗑️ Excluídas {len(physical_answers)} respostas físicas do formulário {form_id}")
            
            # Excluir formulário físico
            db.session.delete(physical_form)
            db.session.commit()
            
            logging.info(f"🗑️ Formulário físico {form_id} excluído com sucesso")
            
            return {
                'success': True,
                'message': 'Formulário físico excluído com sucesso',
                'deleted_form_id': form_id,
                'test_id': test_id,
                'student_id': student_id,
                'deleted_answers': len(physical_answers)
            }
            
        except Exception as e:
            logging.error(f"Erro ao excluir formulário físico {form_id}: {str(e)}")
            db.session.rollback()
            return {
                'success': False,
                'error': f'Erro interno: {str(e)}'
            }

    def delete_all_physical_forms_by_test(self, test_id: str) -> Dict[str, Any]:
        """
        Exclui todos os formulários físicos de uma prova
        
        Args:
            test_id: ID da prova
            
        Returns:
            Dicionário com resultado da operação
        """
        try:
            # Buscar todos os formulários físicos da prova
            physical_forms = PhysicalTestForm.query.filter_by(test_id=test_id).all()
            
            if not physical_forms:
                return {
                    'success': True,
                    'message': 'Nenhum formulário físico encontrado para esta prova',
                    'deleted_forms': 0,
                    'deleted_answers': 0
                }
            
            total_answers_deleted = 0
            
            # Excluir cada formulário e suas respostas
            for form in physical_forms:
                # Excluir respostas físicas relacionadas
                physical_answers = PhysicalTestAnswer.query.filter_by(
                    physical_form_id=form.id
                ).all()
                
                for answer in physical_answers:
                    db.session.delete(answer)
                
                total_answers_deleted += len(physical_answers)
                
                # Excluir formulário físico
                db.session.delete(form)
            
            db.session.commit()
            
            logging.info(f"🗑️ Excluídos {len(physical_forms)} formulários físicos e {total_answers_deleted} respostas da prova {test_id}")
            
            return {
                'success': True,
                'message': f'Todos os formulários físicos da prova foram excluídos com sucesso',
                'deleted_forms': len(physical_forms),
                'deleted_answers': total_answers_deleted,
                'test_id': test_id
            }
            
        except Exception as e:
            logging.error(f"Erro ao excluir formulários físicos da prova {test_id}: {str(e)}")
            db.session.rollback()
            return {
                'success': False,
                'error': f'Erro interno: {str(e)}'
            }

    def generate_individual_physical_form(self, test_id: str, student_id: str, output_dir: str = "physical_forms") -> Dict[str, Any]:
        """
        Gera formulário físico individual para um aluno específico
        
        Args:
            test_id: ID da prova
            student_id: ID do aluno
            output_dir: Diretório para salvar o PDF
            
        Returns:
            Dicionário com resultado da operação
        """
        try:
            # Verificar se a prova existe
            test = Test.query.get(test_id)
            if not test:
                return {
                    'success': False,
                    'error': 'Prova não encontrada',
                    'generated_forms': 0
                }
            
            # Verificar se o aluno existe
            student = Student.query.get(student_id)
            if not student:
                return {
                    'success': False,
                    'error': 'Aluno não encontrado',
                    'generated_forms': 0
                }
            
            # Verificar se a prova foi aplicada na turma do aluno
            class_test = ClassTest.query.filter_by(
                test_id=test_id,
                class_id=student.class_id
            ).first()
            
            if not class_test:
                return {
                    'success': False,
                    'error': 'A prova não foi aplicada na turma deste aluno',
                    'generated_forms': 0
                }
            
            # Verificar se já existe formulário para este aluno
            existing_form = PhysicalTestForm.query.filter_by(
                test_id=test_id,
                student_id=student_id
            ).first()
            
            if existing_form:
                return {
                    'success': False,
                    'error': 'Já existe um formulário físico para este aluno nesta prova',
                    'generated_forms': 0,
                    'existing_form_id': existing_form.id
                }
            
            # Buscar questões da prova ordenadas
            questions = self._get_test_questions(test_id)
            if not questions:
                return {
                    'success': False,
                    'error': 'Nenhuma questão encontrada para esta prova',
                    'generated_forms': 0
                }
            
            # Preparar dados para geração
            test_data = {
                'id': test.id,
                'title': test.title,
                'description': test.description,
                'type': test.type
            }
            
            questions_data = [self._format_question_data(q) for q in questions]
            student_data = [self._format_student_data(student)]
            
            # Gerar PDF individual para o aluno
            individual_pdf_path = self.pdf_generator.generate_individual_test_pdf(
                test_data, student_data[0], questions_data, output_dir
            )
            
            if not individual_pdf_path:
                return {
                    'success': False,
                    'error': 'Erro ao gerar PDF individual',
                    'generated_forms': 0
                }
            
            # Gerar gabarito individual
            answer_key_path = self.pdf_generator.generate_individual_answer_key(
                test_data, questions_data, output_dir
            )
            
            # Preparar dados do arquivo gerado
            generated_file = {
                'student_id': student.id,
                'student_name': student.name,
                'pdf_path': individual_pdf_path,
                'answer_key_path': answer_key_path,
                'qr_code_data': f"individual_{student.id}_{test_id}"
            }
            
            # Salvar informações no banco de dados
            saved_forms = self._save_individual_physical_form_to_db(
                test_id, student, class_test, generated_file, questions
            )
            
            return {
                'success': True,
                'message': f'Formulário individual gerado com sucesso para {student.name}',
                'generated_forms': len(saved_forms),
                'test_title': test.title,
                'student_name': student.name,
                'total_questions': len(questions),
                'forms': saved_forms
            }
            
        except Exception as e:
            logging.error(f"Erro ao gerar formulário individual: {str(e)}")
            return {
                'success': False,
                'error': f'Erro interno: {str(e)}',
                'generated_forms': 0
            }

    def _save_individual_physical_form_to_db(self, test_id: str, student: Student, 
                                           class_test: ClassTest, generated_file: Dict, 
                                           questions: List[Question]) -> List[Dict]:
        """Salva formulário físico individual no banco de dados"""
        try:
            # Ler PDF do aluno e salvar no banco
            pdf_data = None
            if generated_file.get('pdf_path') and os.path.exists(generated_file['pdf_path']):
                with open(generated_file['pdf_path'], 'rb') as f:
                    pdf_data = f.read()
            
            # Ler gabarito e salvar no banco
            answer_key_data = None
            if (generated_file.get('answer_key_path') and 
                os.path.exists(generated_file['answer_key_path'])):
                with open(generated_file['answer_key_path'], 'rb') as f:
                    answer_key_data = f.read()
            
            # Criar registro do formulário físico individual
            physical_form = PhysicalTestForm(
                test_id=test_id,
                student_id=student.id,
                class_test_id=class_test.id,
                form_pdf_data=pdf_data,
                answer_sheet_data=answer_key_data,
                form_pdf_url=generated_file.get('pdf_path'),
                qr_code_data=generated_file['qr_code_data'],
                status='gerado'
            )
            
            db.session.add(physical_form)
            db.session.flush()  # Para obter o ID
            
            # Commit das alterações
            db.session.commit()
            
            # Retornar dados do formulário salvo
            form_dict = physical_form.to_dict()
            form_dict['student_name'] = student.name
            form_dict['has_pdf_data'] = pdf_data is not None
            form_dict['has_answer_sheet_data'] = answer_key_data is not None
            
            return [form_dict]
            
        except Exception as e:
            logging.error(f"Erro ao salvar formulário individual no banco: {str(e)}")
            db.session.rollback()
            return []