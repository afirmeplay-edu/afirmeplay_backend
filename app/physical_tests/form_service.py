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
from app.models.answerSheetGabarito import AnswerSheetGabarito
from app.physical_tests.pdf_generator import PhysicalTestPDFGenerator
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

    def generate_physical_forms(self, test_id: str, output_dir: str = None, test_data: Dict = None) -> Dict[str, Any]:
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
            
            # Verificar se já existem formulários gerados para esta prova
            existing_forms = PhysicalTestForm.query.filter_by(test_id=test_id, form_type='institutional').all()
            if existing_forms:
                # Buscar informações dos alunos que já têm formulários
                students_with_forms = []
                for form in existing_forms:
                    student = Student.query.get(form.student_id)
                    if student:
                        students_with_forms.append({
                            'student_id': form.student_id,
                            'student_name': student.name,
                            'form_id': form.id
                        })
                
                logging.info(f"Formulários já existem para a prova {test_id}. Total: {len(existing_forms)}")
                return {
                    'success': True,
                    'message': f'Formulários já foram gerados anteriormente para esta prova',
                    'already_generated': True,
                    'generated_forms': len(existing_forms),
                    'test_title': test.title,
                    'forms': students_with_forms
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

            # Aplicar filtro de escopo (escola / série / turma) em cascata, se informado
            scope_filter = (test_data or {}).get('scope_filter') or {}
            school_ids = scope_filter.get('school_ids')
            grade_ids = scope_filter.get('grade_ids')
            class_ids_filter = scope_filter.get('class_ids')
            if school_ids or grade_ids or class_ids_filter:
                class_ids_raw = [ct.class_id for ct in applied_tests]
                classes = Class.query.filter(Class.id.in_(class_ids_raw)).all()
                allowed_class_ids = set()
                for c in classes:
                    if school_ids and (c.school_id is None or str(c.school_id) not in [str(x) for x in school_ids]):
                        continue
                    if grade_ids and (c.grade_id is None or str(c.grade_id) not in [str(x) for x in grade_ids]):
                        continue
                    if class_ids_filter and str(c.id) not in [str(x) for x in class_ids_filter]:
                        continue
                    allowed_class_ids.add(c.id)
                applied_tests = [ct for ct in applied_tests if ct.class_id in allowed_class_ids]
                if not applied_tests:
                    return {
                        'success': False,
                        'error': 'Nenhuma turma encontrada para os filtros de escola/série/turma informados',
                        'generated_forms': 0
                    }
            
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
            city_obj = None
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

            
            # ✅ MODIFICADO: Extrair correction_data ANTES de mesclar test_data (para não perder)
            print(f"[SERVICE] ========== EXTRAINDO CORRECTION_DATA ==========")
            print(f"[SERVICE] test_data recebido: {test_data}")
            print(f"[SERVICE] 'correction_data' em test_data: {'correction_data' in test_data if test_data else False}")
            
            blocks_config = None
            correction_data = None
            
            # Primeiro, tentar pegar do test_data passado (vem do Celery task)
            if test_data and 'correction_data' in test_data:
                correction_data = test_data.pop('correction_data')  # Remover para não ser mesclado
                blocks_config = correction_data.get('blocks_config')
                print(f"[SERVICE] ✅ correction_data extraído: {correction_data}")
                print(f"[SERVICE] blocks_config extraído: {blocks_config}")
                print(f"[SERVICE] blocks_config tem topology: {'topology' in blocks_config if blocks_config else False}")
                logging.info(f"✅ Dados de correção obtidos do test_data (correction_data)")
            else:
                print(f"[SERVICE] ⚠️ correction_data NÃO encontrado em test_data, usando fallback")
                # Fallback: buscar do AnswerSheetGabarito (compatibilidade com código antigo)
                gabarito = AnswerSheetGabarito.query.filter_by(test_id=test_id).first()
                if gabarito:
                    if gabarito.blocks_config:
                        blocks_config = gabarito.blocks_config.copy()
                        # Garantir que use_blocks está presente
                        if gabarito.use_blocks:
                            blocks_config['use_blocks'] = True
                        else:
                            blocks_config['use_blocks'] = False
                    # Criar correction_data a partir do gabarito para compatibilidade
                    correction_data = {
                        'num_questions': gabarito.num_questions,
                        'use_blocks': gabarito.use_blocks,
                        'blocks_config': blocks_config,
                        'correct_answers': gabarito.correct_answers
                    }
                    logging.info(f"⚠️ Dados de correção obtidos do AnswerSheetGabarito (fallback)")
            
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
            
            # Incluir blocks_config do correction_data apenas se não foi passado no test_data
            if blocks_config and 'blocks_config' not in base_test_data:
                base_test_data['blocks_config'] = blocks_config
            elif blocks_config and 'blocks_config' in base_test_data:
                # Se ambos existem, mesclar: usar valores do test_data passado, mas preencher campos faltantes do correction_data
                merged_blocks_config = blocks_config.copy()
                merged_blocks_config.update(base_test_data['blocks_config'])
                base_test_data['blocks_config'] = merged_blocks_config
            
            test_data = base_test_data
            from app.services.city_branding_service import apply_city_branding_to_test_data
            test_data = apply_city_branding_to_test_data(test_data, city_obj)
            
            questions_data = [self._format_question_data(q) for q in questions]

            students_data = [self._format_student_data(s) for s in students]
            
            # Buscar ClassTest associado à prova
            class_tests = ClassTest.query.filter_by(test_id=test_id).all()
            class_test_id = class_tests[0].id if class_tests else "temp-class-test-id"
            
            # Gerar PDFs institucionais: fluxo atual = Arch4 + PDF Overlay (WeasyPrint 2×, overlay por aluno)
            # 1× PDF base (capa + questões) + 1× template OMR (dados neutros) + por aluno: overlay ReportLab + merge
            from app.services.institutional_test_weasyprint_generator import InstitutionalTestWeasyPrintGenerator
            institutional_generator = InstitutionalTestWeasyPrintGenerator()

            # Geração com processamento incremental (salva em disco); usa overlay para cartão OMR (sem WeasyPrint por aluno)
            generated_files = institutional_generator.generate_institutional_test_pdf_arch4(
                test_data, students_data, questions_data, class_test_id,
                output_dir=output_dir  # Se None, usa padrão /tmp/celery_pdfs/physical_tests
            )
            
            # Atualizar etapa para o usuário (polling de status)
            job_id = (test_data or {}).get('job_id')
            if job_id:
                try:
                    from app.services.progress_store import update_job
                    update_job(job_id, {"phase": "saving", "stage_message": "Salvando arquivos no banco de dados..."})
                except Exception:
                    pass
            
            # Salvar informações no banco de dados (processamento incremental)
            print(f"[SERVICE] ========== CHAMANDO _save_physical_forms_to_db ==========")
            print(f"[SERVICE] correction_data antes de passar: {correction_data}")
            print(f"[SERVICE] correction_data tem blocks_config: {'blocks_config' in correction_data if correction_data else False}")
            if correction_data and 'blocks_config' in correction_data:
                print(f"[SERVICE] blocks_config tem topology: {'topology' in correction_data['blocks_config']}")
            
            saved_forms = self._save_physical_forms_to_db(
                test_id, generated_files, questions, correction_data=correction_data
            )
            
            print(f"[SERVICE] _save_physical_forms_to_db retornou: {len(saved_forms)} formulários salvos")
            
            return {
                'success': True,
                'message': f'Formulários gerados com sucesso',
                'generated_forms': len(saved_forms),
                'test_title': test.title,
                'total_questions': len(questions),
                'total_students': len(students),
                'forms': saved_forms,
                'generated_files': generated_files  # Retornar arquivos gerados para criar ZIP
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
            from app.physical_tests.pdf_generator import PhysicalTestPDFGenerator
            
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
            'images': getattr(question, 'images', None) or [],  # ✅ Necessário para inline base64 no WeasyPrint
            'subject_id': question.subject_id,  # Incluir ID da disciplina da questão
            'skill': question.skill,  # Incluir ID da habilidade da questão
            'order': getattr(question, 'order', None)  # Incluir ordem da questão (campo order da TestQuestion)
        }

    def _format_student_data(self, student: Student) -> Dict[str, Any]:
        """Formata dados do aluno para geração do PDF"""
        # Buscar dados completos da turma e escola
        class_obj = None
        # Para o cartão-resposta OMR, é melhor deixar escola/turma vazios
        # quando não houver dados reais, em vez de exibir "Não informado".
        school_name = ''
        class_name = ''

        if student.class_id:
            class_obj = Class.query.get(student.class_id)
            if class_obj:
                class_name = class_obj.name
                if class_obj.school_id:
                    school_obj = School.query.get(class_obj.school_id)
                    if school_obj:
                        school_name = school_obj.name

        # Gerar QR Code com metadados simplificados (student_id + gabarito_id se disponível)
        # NOTA: test_id será preenchido quando o QR code for gerado no contexto da prova (institutional_test_weasyprint_generator.py)
        # ✅ NOVO: Incluir gabarito_id para correção usar gabarito central
        import json
        
        # Criar metadados simplificados do QR code
        qr_metadata = {
            "student_id": str(student.id)
        }
        
        # ✅ NOVO: Se gabarito_id foi passado no test_data, incluir no QR Code
        # Isso será preenchido pela task Celery após criar o AnswerSheetGabarito
        # (não está disponível aqui ainda, será adicionado no institutional_test_weasyprint_generator.py)
        
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

    def _save_physical_forms_to_db(self, test_id: str, generated_files: List[Dict], questions: List[Question], correction_data: Dict = None) -> List[Dict]:
        """
        Salva formulários físicos no banco de dados
        PROCESSAMENTO INCREMENTAL: salva aluno por aluno, libera memória após cada commit
        
        Args:
            test_id: ID da prova
            generated_files: Lista de arquivos gerados
            questions: Lista de questões
            correction_data: Dados de correção (num_questions, use_blocks, blocks_config, correct_answers)
        """
        print(f"[_save_physical_forms_to_db] ========== MÉTODO CHAMADO ==========")
        print(f"[_save_physical_forms_to_db] test_id: {test_id}")
        print(f"[_save_physical_forms_to_db] correction_data recebido: {correction_data}")
        print(f"[_save_physical_forms_to_db] correction_data é None: {correction_data is None}")
        if correction_data:
            print(f"[_save_physical_forms_to_db] correction_data tem blocks_config: {'blocks_config' in correction_data}")
            if 'blocks_config' in correction_data:
                print(f"[_save_physical_forms_to_db] blocks_config tem topology: {'topology' in correction_data['blocks_config']}")
        
        saved_forms = []
        try:
            if not generated_files:
                return []
            
            # Buscar ClassTest associado à prova
            class_test = ClassTest.query.filter_by(test_id=test_id).first()
            
            if not class_test:
                class_test_id = "temp-class-test-id"
            else:
                class_test_id = class_test.id
            
            # Processamento incremental: salvar aluno por aluno
            total_files = len(generated_files)
            for idx, file_info in enumerate(generated_files, 1):
                student_id = file_info['student_id']
                
                try:
                    # Verificar se já existe formulário para este aluno e esta prova
                    existing_form = PhysicalTestForm.query.filter_by(
                        test_id=test_id,
                        student_id=student_id,
                        form_type='institutional'
                    ).first()
                    
                    if existing_form:
                        logging.debug(f"Formulário já existe para aluno {student_id} e prova {test_id}. Pulando...")
                        saved_forms.append({
                            'student_id': student_id,
                            'student_name': file_info['student_name'],
                            'form_id': existing_form.id,
                            'pdf_path': file_info.get('pdf_path', None),
                            'already_exists': True
                        })
                        continue
                    
                    # ✅ MODIFICADO: Enviar PDF individual para MinIO e salvar apenas URL
                    pdf_path = file_info.get('pdf_path')
                    minio_url = None
                    
                    if pdf_path and os.path.exists(pdf_path):
                        try:
                            from app.services.storage.minio_service import MinIOService
                            
                            minio = MinIOService()
                            # Upload do PDF individual para MinIO
                            student_name_safe = file_info['student_name'].replace(' ', '_').replace('/', '_')
                            object_name = f"{test_id}/forms/{student_id}_{student_name_safe}.pdf"
                            
                            upload_result = minio.upload_from_path(
                                bucket_name=minio.BUCKETS['PHYSICAL_TESTS'],
                                object_name=object_name,
                                file_path=pdf_path
                            )
                            
                            if upload_result:
                                minio_url = upload_result['url']
                                logging.debug(f"✅ PDF enviado para MinIO: {minio_url}")
                            else:
                                logging.warning(f"⚠️ Falha ao enviar PDF para MinIO, usando caminho local: {pdf_path}")
                                minio_url = pdf_path  # Fallback para caminho local
                        except Exception as minio_error:
                            logging.warning(f"⚠️ Erro ao enviar PDF para MinIO (não crítico): {str(minio_error)}, usando caminho local")
                            minio_url = pdf_path  # Fallback para caminho local
                    elif file_info.get('pdf_data'):
                        # Modo compatibilidade: upload direto de bytes (não recomendado para produção)
                        try:
                            from app.services.storage.minio_service import MinIOService
                            
                            minio = MinIOService()
                            student_name_safe = file_info['student_name'].replace(' ', '_').replace('/', '_')
                            object_name = f"{test_id}/forms/{student_id}_{student_name_safe}.pdf"
                            
                            upload_result = minio.upload_file(
                                bucket_name=minio.BUCKETS['PHYSICAL_TESTS'],
                                object_name=object_name,
                                data=file_info['pdf_data'],
                                content_type='application/pdf'
                            )
                            
                            if upload_result:
                                minio_url = upload_result['url']
                                logging.debug(f"✅ PDF enviado para MinIO (bytes): {minio_url}")
                            else:
                                logging.warning(f"⚠️ Falha ao enviar PDF para MinIO")
                        except Exception as minio_error:
                            logging.warning(f"⚠️ Erro ao enviar PDF para MinIO: {str(minio_error)}")
                    
                    if not minio_url and not pdf_path:
                        logging.warning(f"PDF não encontrado para aluno {student_id}")
                        continue
                    
                    # Criar registro do formulário físico
                    # ✅ MODIFICADO: NÃO salvar form_pdf_data (apenas URL do MinIO)
                    physical_form = PhysicalTestForm(
                        test_id=test_id,
                        student_id=student_id,
                        class_test_id=class_test_id,
                        form_pdf_data=None,  # ✅ NÃO salvar bytes no banco
                        form_pdf_url=minio_url or pdf_path,  # ✅ Salvar apenas URL
                        qr_code_data=file_info.get('qr_code_data', file_info['student_id']),
                        status='gerado',
                        form_type='institutional'
                    )
                    
                    # ✅ NOVO: Salvar dados de correção no PhysicalTestForm
                    print(f"[SERVICE] ========== SALVANDO DADOS DE CORREÇÃO ==========")
                    print(f"[SERVICE] student_id: {student_id}")
                    print(f"[SERVICE] correction_data existe: {correction_data is not None}")
                    
                    if correction_data:
                        print(f"[SERVICE] correction_data: {correction_data}")
                        physical_form.num_questions = correction_data.get('num_questions')
                        physical_form.use_blocks = correction_data.get('use_blocks', False)
                        print(f"[SERVICE] num_questions: {physical_form.num_questions}")
                        print(f"[SERVICE] use_blocks: {physical_form.use_blocks}")
                        
                        # ✅ CRÍTICO: Garantir que blocks_config tenha a topology completa
                        blocks_config_to_save = correction_data.get('blocks_config')
                        print(f"[SERVICE] blocks_config_to_save: {blocks_config_to_save}")
                        
                        if blocks_config_to_save:
                            # Verificar se tem topology
                            has_topology = 'topology' in blocks_config_to_save and blocks_config_to_save.get('topology')
                            print(f"[SERVICE] blocks_config tem topology: {has_topology}")
                            
                            if not has_topology:
                                print(f"[SERVICE] ⚠️⚠️⚠️ ATENÇÃO: blocks_config SEM topology para aluno {student_id}")
                                logging.warning(f"⚠️ blocks_config sem topology para aluno {student_id}")
                            else:
                                num_blocks_in_topology = len(blocks_config_to_save['topology'].get('blocks', []))
                                print(f"[SERVICE] ✅ blocks_config com topology: {num_blocks_in_topology} blocos")
                                logging.info(f"✅ blocks_config com topology: {num_blocks_in_topology} blocos")
                            
                            physical_form.blocks_config = blocks_config_to_save
                            print(f"[SERVICE] blocks_config salvo no physical_form")
                        else:
                            print(f"[SERVICE] ⚠️⚠️⚠️ blocks_config NÃO encontrado em correction_data para aluno {student_id}")
                            logging.warning(f"⚠️ blocks_config não encontrado em correction_data para aluno {student_id}")
                        
                        physical_form.correct_answers = correction_data.get('correct_answers')
                        print(f"[SERVICE] correct_answers: {physical_form.correct_answers}")
                        print(f"[SERVICE] ✅ Dados de correção salvos: num_questions={physical_form.num_questions}, use_blocks={physical_form.use_blocks}")
                        logging.info(f"✅ Dados de correção salvos no PhysicalTestForm para aluno {student_id}: num_questions={physical_form.num_questions}, use_blocks={physical_form.use_blocks}")
                    else:
                        print(f"[SERVICE] ⚠️⚠️⚠️⚠️⚠️ correction_data NÃO fornecido para aluno {student_id} - dados NÃO serão salvos!")
                        logging.warning(f"⚠️ correction_data não fornecido para aluno {student_id} - dados de correção NÃO serão salvos!")
                    
                    print(f"[SERVICE] ========== COMMIT NO BANCO ==========")
                    
                    db.session.add(physical_form)
                    db.session.flush()  # Para obter o ID
                    
                    saved_forms.append({
                        'student_id': student_id,
                        'student_name': file_info['student_name'],
                        'form_id': physical_form.id,
                        'pdf_path': pdf_path,
                        'minio_url': minio_url,
                        'already_exists': False
                    })
                    
                    # Commit incremental: salvar aluno por aluno
                    db.session.commit()
                    
                    # Liberar memória após cada salvamento
                    import gc
                    gc.collect()
                    
                    # Log de progresso apenas a cada 10 alunos ou no final
                    if idx % 10 == 0 or idx == total_files:
                        logging.debug(f"Salvos {idx}/{total_files} formulários no banco")
                
                except Exception as e:
                    db.session.rollback()
                    logging.error(f"Erro ao salvar formulário para aluno {student_id}: {str(e)}", exc_info=True)
                    continue
            
            return saved_forms
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Erro ao salvar formulários no banco: {str(e)}", exc_info=True)
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
                test_id, generated_files, questions, correction_data=None
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
