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
# from app.services.physical_test_correction import PhysicalTestCorrection  # ARQUIVO DELETADO
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
        # self.correction_service = PhysicalTestCorrection()  # ARQUIVO DELETADO
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
        MÉTODO COMENTADO - USAR PhysicalTestPDFGenerator.processar_correcao_completa() DIRETAMENTE
        """
        return {
            'success': False,
            'error': 'Método comentado. Use PhysicalTestPDFGenerator.processar_correcao_completa() diretamente.'
        }

    def _get_test_questions(self, test_id: str) -> List[Question]:
        """Busca questões da prova ordenadas"""
        return Question.query.join(TestQuestion).filter(
            TestQuestion.test_id == test_id
        ).order_by(TestQuestion.order).all()

    def _get_students_from_applied_tests(self, applied_tests: List[ClassTest]) -> List[Student]:
        """Busca alunos das turmas onde a prova foi aplicada"""
        class_ids = [ct.class_id for ct in applied_tests]
        return Student.query.filter(Student.class_id.in_(class_ids)).all()

    def _format_question_data(self, question: Question) -> Dict[str, Any]:
        """Formata dados da questão para geração do PDF"""
        return {
            'id': question.id,
            'title': question.title,
            'text': question.text,
            'formatted_text': question.formatted_text,
            'secondstatement': question.secondstatement,
            'alternatives': question.alternatives or [],
            'correct_answer': question.correct_answer
        }

    def _format_student_data(self, student: Student) -> Dict[str, Any]:
        """Formata dados do aluno para geração do PDF"""
        return {
            'id': student.id,
            'name': student.name,
            'class_id': student.class_id
        }

    def _save_physical_forms_to_db(self, test_id: str, students: List[Student],
                                 generated_files: List[Dict], questions: List[Question]) -> List[Dict]:
        """Salva formulários físicos no banco de dados"""
        saved_forms = []
        try:
            for file_info in generated_files:
                for student in students:
                    # Criar registro do formulário físico
                    physical_form = PhysicalTestForm(
                        test_id=test_id,
                        student_id=student.id,
                        class_test_id=file_info.get('class_test_id'),
                        form_pdf_url=file_info['pdf_path'],
                        qr_code_data=student.id,
                        status='gerado',
                        form_type='institutional'
                    )
                    db.session.add(physical_form)
                    saved_forms.append({
                        'student_id': student.id,
                        'student_name': student.name,
                        'form_id': physical_form.id,
                        'pdf_path': file_info['pdf_path']
                    })
            
            db.session.commit()
            return saved_forms
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Erro ao salvar formulários no banco: {str(e)}")
            return []

    def get_physical_forms_by_test(self, test_id: str) -> List[Dict]:
        """Busca todos os formulários físicos de uma prova"""
        try:
            forms = PhysicalTestForm.query.filter_by(test_id=test_id).all()
            return [form.to_dict() for form in forms]
        except Exception as e:
            logging.error(f"Erro ao buscar formulários físicos: {str(e)}")
            return []

    def get_physical_form_by_student(self, test_id: str, student_id: str) -> Optional[Dict]:
        """Busca formulário físico de um aluno específico"""
        try:
            form = PhysicalTestForm.query.filter_by(
                test_id=test_id, 
                student_id=student_id
            ).first()
            return form.to_dict() if form else None
        except Exception as e:
            logging.error(f"Erro ao buscar formulário do aluno: {str(e)}")
            return None

    def delete_physical_form(self, form_id: str) -> Dict[str, Any]:
        """Exclui um formulário físico específico"""
        try:
            form = PhysicalTestForm.query.get(form_id)
            if not form:
                return {
                    'success': False,
                    'error': 'Formulário não encontrado'
                }
            
            # Excluir respostas associadas
            PhysicalTestAnswer.query.filter_by(physical_form_id=form_id).delete()
            
            # Excluir formulário
            db.session.delete(form)
            db.session.commit()
            
            return {
                'success': True,
                'message': 'Formulário excluído com sucesso',
                'deleted_form_id': form_id,
                'test_id': form.test_id,
                'student_id': form.student_id,
                'deleted_answers': True
            }
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Erro ao excluir formulário: {str(e)}")
            return {
                'success': False,
                'error': f'Erro interno: {str(e)}'
            }

    def delete_all_physical_forms_by_test(self, test_id: str) -> Dict[str, Any]:
        """Exclui todos os formulários físicos de uma prova"""
        try:
            forms = PhysicalTestForm.query.filter_by(test_id=test_id).all()
            if not forms:
                return {
                    'success': False,
                    'error': 'Nenhum formulário encontrado para esta prova'
                }
            
            form_ids = [form.id for form in forms]
            
            # Excluir respostas associadas
            PhysicalTestAnswer.query.filter(
                PhysicalTestAnswer.physical_form_id.in_(form_ids)
            ).delete()
            
            # Excluir formulários
            for form in forms:
                db.session.delete(form)
            
            # Excluir coordenadas do formulário (FormCoordinates)
            from app.models.formCoordinates import FormCoordinates
            form_coordinates = FormCoordinates.query.filter_by(
                test_id=test_id,
                form_type='physical_test'
            ).all()
            
            for coord in form_coordinates:
                db.session.delete(coord)
            
            db.session.commit()
            
            return {
                'success': True,
                'message': f'{len(forms)} formulários e {len(form_coordinates)} coordenadas excluídos com sucesso',
                'test_id': test_id,
                'deleted_forms': len(forms),
                'deleted_answers': True,
                'deleted_coordinates': len(form_coordinates)
            }
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Erro ao excluir formulários: {str(e)}")
            return {
                'success': False,
                'error': f'Erro interno: {str(e)}'
            }

    def generate_individual_physical_form(self, test_id: str, student_id: str, output_dir: str = "physical_forms") -> Dict[str, Any]:
        """Gera formulário físico individual para um aluno"""
        try:
            # Verificar se a prova existe
            test = Test.query.get(test_id)
            if not test:
                return {
                    'success': False,
                    'error': 'Prova não encontrada'
                }
            
            # Verificar se o aluno existe
            student = Student.query.get(student_id)
            if not student:
                return {
                    'success': False,
                    'error': 'Aluno não encontrado'
                }
            
            # Buscar questões da prova
            questions = self._get_test_questions(test_id)
            if not questions:
                return {
                    'success': False,
                    'error': 'Nenhuma questão encontrada para esta prova'
                }
            
            # Preparar dados
            test_data = {
                'id': test.id,
                'title': test.title,
                'description': test.description,
                'type': test.type
            }
            
            student_data = [self._format_student_data(student)]
            questions_data = [self._format_question_data(q) for q in questions]
            
            # Gerar formulário individual
            generated_files = self.pdf_generator.generate_individual_test_pdf(
                test_data, student_data, questions_data, output_dir
            )
            
            if not generated_files:
                return {
                    'success': False,
                    'error': 'Erro ao gerar formulário individual'
                }
            
            # Salvar no banco
            saved_forms = self._save_physical_forms_to_db(
                test_id, [student], generated_files, questions
            )
            
            return {
                'success': True,
                'message': 'Formulário individual gerado com sucesso',
                'generated_forms': generated_files,
                'test_title': test.title,
                'student_name': student.name,
                'total_questions': len(questions),
                'forms': saved_forms
            }
            
        except Exception as e:
            logging.error(f"Erro ao gerar formulário individual: {str(e)}")
            return {
                'success': False,
                'error': f'Erro interno: {str(e)}'
            }
