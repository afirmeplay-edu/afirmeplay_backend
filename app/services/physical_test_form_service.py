# -*- coding: utf-8 -*-
"""
Serviço principal para gerenciar formulários físicos de provas
Integra com o banco de dados e coordena a geração e correção
"""

import os
import logging
import qrcode
import base64
from io import BytesIO
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
from app.models.city import City
from app.models.grades import Grade
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

    def generate_physical_forms(self, test_id: str, output_dir: str = "physical_forms", test_data: Dict = None) -> Dict[str, Any]:
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
            # Buscar nome da série/grade
            grade_name = 'Não informado'
            if test.grade_id:
                grade_obj = Grade.query.get(test.grade_id)
                if grade_obj:
                    grade_name = grade_obj.name

            # Buscar município e estado através da escola do primeiro aluno
            municipality_name = None
            state_name = None
            if students:
                first_student = students[0]
                if first_student.class_id:
                    class_obj = Class.query.get(first_student.class_id)
                    if class_obj and class_obj.school_id:
                        school_obj = School.query.get(class_obj.school_id)
                        if school_obj and school_obj.city_id:
                            city_obj = City.query.get(school_obj.city_id)
                            if city_obj:
                                municipality_name = city_obj.name
                                state_name = city_obj.state

            # Criar test_data base, mesclando com test_data passado como parâmetro
            base_test_data = {
                'id': test.id,
                'title': test.title,
                'description': test.description,
                'type': test.type,
                'subjects_info': test.subjects_info,  # Incluir disciplinas da avaliação
                'grade_name': grade_name,  # Adicionar nome da série
                'municipality': municipality_name,  # Adicionar município
                'state': state_name  # Adicionar estado
            }
            
            # Mesclar com test_data passado (se houver), priorizando valores passados
            if test_data:
                base_test_data.update(test_data)
            
            test_data = base_test_data
            
            questions_data = [self._format_question_data(q) for q in questions]
            students_data = [self._format_student_data(s) for s in students]
            
            # Buscar ClassTest associado à prova
            class_tests = ClassTest.query.filter_by(test_id=test_id).all()
            class_test_id = class_tests[0].id if class_tests else "temp-class-test-id"
            
            # Gerar PDFs institucionais usando WeasyPrint (suporta HTML/CSS completo)
            # Este método gera a prova completa: capa, questões, imagens, alternativas e formulário
            from app.services.institutional_test_weasyprint_generator import InstitutionalTestWeasyPrintGenerator
            institutional_generator = InstitutionalTestWeasyPrintGenerator()

            # Gerar PDFs institucionais e salvar no banco
            generated_files = institutional_generator.generate_institutional_test_pdf(
                test_data, students_data, questions_data, class_test_id
            )
            
            # Salvar informações no banco de dados
            print(f"DEBUG: Total de arquivos gerados antes de salvar: {len(generated_files)}")
            saved_forms = self._save_physical_forms_to_db(
                test_id, generated_files, questions
            )
            print(f"DEBUG: Total de formulários salvos: {len(saved_forms)}")
            
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
        Processa correção de gabarito físico usando PhysicalTestPDFGenerator
        """
        try:
            from app.services.physical_test_pdf_generator import PhysicalTestPDFGenerator
            
            # Criar instância do gerador
            generator = PhysicalTestPDFGenerator()
            
            # Processar correção completa
            result = generator.processar_correcao_completa(test_id, image_data)
            
            return result
            
        except Exception as e:
            logging.error(f"Erro ao processar correção física: {str(e)}")
            return {
                'success': False,
                'error': f'Erro interno: {str(e)}'
            }

    def _get_test_questions(self, test_id: str) -> List[Dict]:
        """Busca questões da prova ordenadas com campo order"""
        from app.models.question import Question
        from app.models.testQuestion import TestQuestion
        
        # Buscar TestQuestions ordenadas
        test_questions = TestQuestion.query.filter_by(test_id=test_id).order_by(TestQuestion.order).all()
        
        # Buscar questões correspondentes
        question_ids = [tq.question_id for tq in test_questions]
        questions = Question.query.filter(Question.id.in_(question_ids)).all()
        
        # Criar dicionário para mapear questões
        questions_dict = {q.id: q for q in questions}
        
        # Retornar questões ordenadas com campo order
        ordered_questions = []
        for tq in test_questions:
            if tq.question_id in questions_dict:
                question = questions_dict[tq.question_id]
                # Adicionar campo order ao objeto questão
                question.order = tq.order
                ordered_questions.append(question)
        
        return ordered_questions

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
            'correct_answer': question.correct_answer,
            'subject_id': question.subject_id,  # Incluir ID da disciplina da questão
            'skill': question.skill,  # Incluir ID da habilidade da questão
            'order': getattr(question, 'order', None)  # Incluir ordem da questão (campo order da TestQuestion)
        }

    def _format_student_data(self, student: Student) -> Dict[str, Any]:
        """Formata dados do aluno para geração do PDF"""
        # Buscar dados completos da turma e escola
        class_obj = None
        school_name = 'Não informado'
        class_name = 'Não informado'

        if student.class_id:
            class_obj = Class.query.get(student.class_id)
            if class_obj:
                class_name = class_obj.name
                if class_obj.school_id:
                    school_obj = School.query.get(class_obj.school_id)
                    if school_obj:
                        school_name = school_obj.name

        # Gerar QR Code com metadados simplificados (apenas student_id)
        # NOTA: test_id será preenchido quando o QR code for gerado no contexto da prova (institutional_test_weasyprint_generator.py)
        # Removido: qr_code_id para tornar QR code menor e mais fácil de decodificar
        import json
        
        # Criar metadados simplificados do QR code (apenas student_id)
        qr_metadata = {
            "student_id": str(student.id)
        }
        
        # Converter para JSON
        qr_json = json.dumps(qr_metadata)
        
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=2,
        )
        qr.add_data(qr_json)
        qr.make(fit=True)

        # Criar imagem do QR Code
        img = qr.make_image(fill_color="black", back_color="white")

        # Converter para base64
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        qr_code_base64 = base64.b64encode(buffered.getvalue()).decode()

        return {
            'id': student.id,
            'name': student.name,
            'class_id': student.class_id,
            'class_name': class_name,
            'school_name': school_name,
            'qr_code': qr_code_base64
        }

    def _save_physical_forms_to_db(self, test_id: str, generated_files: List[Dict], questions: List[Question]) -> List[Dict]:
        """Salva formulários físicos no banco de dados"""
        saved_forms = []
        try:
            print(f"DEBUG: _save_physical_forms_to_db recebeu {len(generated_files)} arquivos")
            
            if not generated_files:
                print("DEBUG: Nenhum arquivo gerado para salvar!")
                return []
            
            # Buscar ClassTest associado à prova
            class_test = ClassTest.query.filter_by(test_id=test_id).first()
            
            if not class_test:
                # Se não existe ClassTest, criar um temporário ou usar um padrão
                print(f"⚠️ Nenhum ClassTest encontrado para a prova {test_id}")
                # Por enquanto, vamos usar um ID temporário
                class_test_id = "temp-class-test-id"
            else:
                class_test_id = class_test.id
            
            for file_info in generated_files:
                print(f"DEBUG: Salvando formulário para aluno {file_info.get('student_id')}")
                # Criar registro do formulário físico
                pdf_data = file_info.get('pdf_data')
                if not pdf_data:
                    print(f"DEBUG: Aluno {file_info.get('student_id')} não tem pdf_data!")
                    continue
                
                print(f"DEBUG: Criando PhysicalTestForm para aluno {file_info.get('student_id')}, tamanho PDF: {len(pdf_data) if pdf_data else 0} bytes")
                
                physical_form = PhysicalTestForm(
                    test_id=test_id,
                    student_id=file_info['student_id'],
                    class_test_id=class_test_id,
                    form_pdf_data=pdf_data,
                    form_pdf_url=file_info.get('pdf_path', None),
                    qr_code_data=file_info['student_id'],
                    status='gerado',
                    form_type='institutional'
                )
                db.session.add(physical_form)
                db.session.flush()  # Para obter o ID
                saved_forms.append({
                    'student_id': file_info['student_id'],
                    'student_name': file_info['student_name'],
                    'form_id': physical_form.id,
                    'pdf_path': file_info.get('pdf_path', None)
                })
                print(f"DEBUG: Formulário {physical_form.id} criado com sucesso para aluno {file_info.get('student_id')}")
            
            db.session.commit()
            print(f"DEBUG: Commit realizado, {len(saved_forms)} formulários salvos")
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
            
            # Gerar formulário individual usando InstitutionalTestPDFGenerator
            from app.services.institutional_test_pdf_generator import InstitutionalTestPDFGenerator
            institutional_generator = InstitutionalTestPDFGenerator()
            
            # Gerar formulário estilo formularios.py
            form_image, coordinates, qr_coordinates = institutional_generator._create_formulario_style_form(
                student_name=student.name,
                student_id=student.id,
                num_questoes=len(questions)
            )
            
            # Salvar imagem do formulário
            form_filename = f"formulario_{student.id}_{test.id}.png"
            form_path = os.path.join(output_dir, form_filename)
            form_image.save(form_path)
            
            # Converter imagem para PDF
            from io import BytesIO
            pdf_buffer = BytesIO()
            form_image.save(pdf_buffer, format='PDF')
            pdf_data = pdf_buffer.getvalue()
            
            generated_files = [{
                'student_id': student.id,
                'student_name': student.name,
                'pdf_path': form_path,
                'pdf_data': pdf_data,
                'answer_key_path': None,
                'qr_code_data': qr_coordinates,
                'coordinates': coordinates,
                'form_image': form_image
            }]
            
            # Salvar no banco
            saved_forms = self._save_physical_forms_to_db(
                test_id, generated_files, questions
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
