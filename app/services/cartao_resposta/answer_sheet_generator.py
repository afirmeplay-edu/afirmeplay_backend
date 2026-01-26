# -*- coding: utf-8 -*-
"""
Serviço para geração de PDFs de cartões resposta usando WeasyPrint + Jinja2
"""

from weasyprint import HTML
from jinja2 import Environment, FileSystemLoader, select_autoescape
import os
import io
import base64
import logging
import json
import qrcode
import gc
from datetime import datetime
from typing import List, Dict, Any, Optional
from io import BytesIO


class AnswerSheetGenerator:
    """
    Gerador de PDFs para cartões resposta usando WeasyPrint + Jinja2
    """

    def __init__(self):
        # Configurar Jinja2 para carregar templates
        template_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'templates')
        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(['html', 'xml'])
        )

        # Adicionar filtros personalizados
        self.env.filters['safe'] = lambda x: x

    def generate_answer_sheets(self, class_id: str, test_data: Dict, 
                              num_questions: int, use_blocks: bool,
                              blocks_config: Dict, correct_answers: Dict,
                              gabarito_id: str = None, questions_options: Dict = None,
                              output_dir: str = None) -> List[Dict]:
        """
        Gera PDFs de cartões resposta para todos os alunos de uma turma
        PROCESSAMENTO INCREMENTAL: gera → salva em disco → libera memória

        Args:
            class_id: ID da turma
            test_data: Dados da prova (title, municipality, state, etc.)
            num_questions: Quantidade de questões
            use_blocks: Se usa blocos ou não
            blocks_config: Configuração de blocos {num_blocks, questions_per_block, separate_by_subject}
            correct_answers: Dict com respostas corretas {1: "A", 2: "B", ...}
            gabarito_id: ID do gabarito salvo (opcional)
            questions_options: Dict com alternativas de cada questão {1: ['A', 'B', 'C'], 2: ['A', 'B', 'C', 'D'], ...}
                              Se não fornecido, usa padrão A, B, C, D para todas
            output_dir: Diretório para salvar PDFs em disco (padrão: /tmp/celery_pdfs/answer_sheets)

        Returns:
            Lista com informações dos PDFs gerados (com pdf_path se output_dir fornecido)
        """
        # Definir output_dir padrão para containers Linux
        if output_dir is None:
            output_dir = '/tmp/celery_pdfs/answer_sheets'
        
        try:
            from app.models.student import Student
            from app.models.studentClass import Class

            # Buscar turma
            class_obj = Class.query.get(class_id)
            if not class_obj:
                raise ValueError(f"Turma {class_id} não encontrada")

            # Buscar alunos da turma
            students = Student.query.filter_by(class_id=class_id).all()
            if not students:
                raise ValueError(f"Nenhum aluno encontrado na turma {class_id}")

            # Criar diretório de saída (sempre criar, mesmo com padrão)
            os.makedirs(output_dir, exist_ok=True)

            generated_files = []

            # Processar questions_options: converter chaves string para int
            questions_map = {}
            if questions_options:
                for key, value in questions_options.items():
                    try:
                        q_num = int(key)  # Converter "1" -> 1
                        if isinstance(value, list) and len(value) >= 2:
                            questions_map[q_num] = value
                        else:
                            questions_map[q_num] = ['A', 'B', 'C', 'D']
                    except (ValueError, TypeError):
                        continue
            
            # Se questions_map vazio, preencher com padrão
            if not questions_map:
                for q in range(1, num_questions + 1):
                    questions_map[q] = ['A', 'B', 'C', 'D']
            else:
                # Garantir que todas questões existam
                for q in range(1, num_questions + 1):
                    if q not in questions_map:
                        questions_map[q] = ['A', 'B', 'C', 'D']

            # Organizar questões por blocos se necessário
            questions_by_block = None
            if use_blocks:
                questions_by_block = self._organize_questions_by_blocks(
                    num_questions, blocks_config, questions_map
                )

            # Processamento incremental: gerar → salvar → liberar
            total_students = len(students)
            for idx, student in enumerate(students, 1):
                try:
                    # Gerar PDF individual para cada aluno
                    pdf_data = self._generate_individual_answer_sheet(
                        student, test_data, num_questions, use_blocks,
                        blocks_config, questions_by_block, gabarito_id, questions_map
                    )

                    if pdf_data:
                        file_info = {
                            'student_id': student.id,
                            'student_name': student.name,
                            'has_pdf_data': True
                        }
                        
                        if output_dir:
                            # Salvar em disco e liberar memória imediatamente
                            student_name_safe = student.name.replace(' ', '_').replace('/', '_')
                            pdf_path = os.path.join(output_dir, f"cartao_{student_name_safe}_{student.id}.pdf")
                            
                            with open(pdf_path, 'wb') as f:
                                f.write(pdf_data)
                            
                            file_info['pdf_path'] = pdf_path
                            # NÃO incluir pdf_data quando salvo em disco
                            del pdf_data
                        else:
                            # Modo compatibilidade: retornar bytes em memória
                            file_info['pdf_data'] = pdf_data
                        
                        generated_files.append(file_info)
                        
                        # Liberar memória explicitamente após cada PDF
                        gc.collect()
                    
                    # Log de progresso apenas a cada 10 alunos ou no final
                    if idx % 10 == 0 or idx == total_students:
                        logging.debug(f"Gerados {idx}/{total_students} cartões resposta")

                except Exception as e:
                    # Log apenas em caso de erro (não dentro do loop normal)
                    logging.error(f"Erro ao gerar cartão resposta para aluno {student.id}: {str(e)}", exc_info=True)
                    continue

            return generated_files

        except Exception as e:
            logging.error(f"Erro ao gerar cartões resposta: {str(e)}", exc_info=True)
            raise

    def _generate_individual_answer_sheet(self, student: Dict, test_data: Dict,
                                         num_questions: int, use_blocks: bool,
                                         blocks_config: Dict, questions_by_block: List[Dict],
                                         gabarito_id: str = None, questions_map: Dict = None) -> Optional[bytes]:
        """
        Gera PDF individual de cartão resposta para um aluno
        
        Args:
            questions_map: Dict {question_num: [options]} para passar ao template
        """
        try:
            # Buscar dados completos do aluno
            student_data = self._get_complete_student_data(student)

            # Gerar QR code com metadados
            qr_code_base64 = self._generate_qr_code(
                student_id=student_data['id'],
                test_id=test_data.get('id'),
                gabarito_id=gabarito_id
            )

            # Adicionar QR code ao student dict
            student_with_qr = student_data.copy()
            student_with_qr['qr_code'] = qr_code_base64

            # Preparar dados para o template
            template_data = {
                'test_data': test_data,
                'student': student_with_qr,
                'questions_by_block': questions_by_block,
                'questions_map': questions_map or {},  # Mapa de alternativas por questão
                'blocks_config': blocks_config if use_blocks else None,
                'total_questions': num_questions,
                'datetime': datetime,
                'generated_date': datetime.now().strftime('%d/%m/%Y %H:%M')
            }

            # Renderizar template HTML
            template = self.env.get_template('answer_sheet.html')
            html_content = template.render(**template_data)

            # Gerar PDF com WeasyPrint
            pdf_buffer = io.BytesIO()
            HTML(string=html_content).write_pdf(pdf_buffer)
            pdf_buffer.seek(0)

            return pdf_buffer.read()

        except Exception as e:
            logging.error(f"Erro ao gerar PDF individual: {str(e)}")
            import traceback
            logging.error(traceback.format_exc())
            return None

    def _organize_questions_by_blocks(self, num_questions: int, blocks_config: Dict, 
                                      questions_map: Dict = None) -> List[Dict]:
        """
        Organiza questões por blocos conforme configuração
        
        Args:
            num_questions: Total de questões
            blocks_config: Configuração de blocos
            questions_map: Dict {question_num: [options]} com alternativas de cada questão
            
        Returns:
            Lista de blocos, cada um contendo:
            - block_number: número do bloco
            - subject_name: nome da disciplina (se fornecido)
            - questions: lista de questões com {question_number, options}
            - start_question_num: número da primeira questão
            - end_question_num: número da última questão
        """
        blocks = []
        
        # Garantir questions_map
        if questions_map is None:
            questions_map = {}
        
        # ✅ NOVO: Verificar se há blocos personalizados
        custom_blocks = blocks_config.get('blocks', [])
        
        if custom_blocks:
            # ✅ Blocos personalizados com disciplinas
            for block_def in custom_blocks:
                block_id = block_def.get('block_id')
                subject_name = block_def.get('subject_name')  # ✅ NOVO
                start_q = block_def.get('start_question')
                end_q = block_def.get('end_question')
                
                questions = []
                for q_num in range(start_q, end_q + 1):
                    options = questions_map.get(q_num, ['A', 'B', 'C', 'D'])
                    questions.append({
                        'question_number': q_num,
                        'options': options
                    })
                
                blocks.append({
                    'block_number': block_id,
                    'subject_name': subject_name,  # ✅ NOVO
                    'questions': questions,
                    'start_question_num': start_q,
                    'end_question_num': end_q
                })
        else:
            # ✅ Fallback: distribuir automaticamente (comportamento original)
            num_blocks = blocks_config.get('num_blocks', 1)
            questions_per_block = blocks_config.get('questions_per_block', 12)
            separate_by_subject = blocks_config.get('separate_by_subject', False)
            
            if separate_by_subject:
                # Se separar por disciplina, precisaríamos de dados de disciplinas
                # Por enquanto, vamos distribuir sequencialmente
                # TODO: Implementar separação por disciplina automática se necessário
                pass
            
            # Distribuir questões sequencialmente pelos blocos
            for block_num in range(1, num_blocks + 1):
                start_question = (block_num - 1) * questions_per_block + 1
                end_question = min(block_num * questions_per_block, num_questions)
                
                # Criar lista de questões com alternativas
                questions = []
                for q_num in range(start_question, end_question + 1):
                    # Buscar alternativas da questão ou usar padrão
                    options = questions_map.get(q_num, ['A', 'B', 'C', 'D'])
                    questions.append({
                        'question_number': q_num,
                        'options': options
                    })
                
                if questions:
                    blocks.append({
                        'block_number': block_num,
                        'subject_name': None,
                        'questions': questions,
                        'start_question_num': start_question,
                        'end_question_num': end_question
                    })
        
        # Validar que temos pelo menos um bloco
        if not blocks:
            questions = []
            for q_num in range(1, num_questions + 1):
                options = questions_map.get(q_num, ['A', 'B', 'C', 'D'])
                questions.append({
                    'question_number': q_num,
                    'options': options
                })
            
            if questions:
                blocks.append({
                    'block_number': 1,
                    'subject_name': None,
                    'questions': questions,
                    'start_question_num': 1,
                    'end_question_num': num_questions
                })
        
        return blocks

    def _get_complete_student_data(self, student) -> Dict:
        """
        Obtém dados completos do aluno
        """
        try:
            from app.models.student import Student
            from app.models.studentClass import Class
            from app.models.school import School
            
            # Se já for um objeto Student, usar diretamente
            if isinstance(student, Student):
                student_obj = student
            else:
                # Se for dict, buscar do banco
                student_id = student.get('id') if isinstance(student, dict) else str(student)
                student_obj = Student.query.get(student_id)
            
            if not student_obj:
                return {
                    'id': str(student.id) if hasattr(student, 'id') else str(student),
                    'name': getattr(student, 'name', 'Nome não informado'),
                    'nome': getattr(student, 'name', 'Nome não informado')
                }
            
            # Buscar dados da turma e escola
            class_name = ''
            school_name = ''
            
            if student_obj.class_id:
                class_obj = Class.query.get(student_obj.class_id)
                if class_obj:
                    class_name = class_obj.name or ''
            
            if student_obj.school_id:
                school_obj = School.query.get(student_obj.school_id)
                if school_obj:
                    school_name = school_obj.name or ''
            
            return {
                'id': str(student_obj.id),
                'name': student_obj.name or 'Nome não informado',
                'nome': student_obj.name or 'Nome não informado',
                'registration': getattr(student_obj, 'registration', ''),
                'class_name': class_name,
                'school_name': school_name,
                'class_id': str(student_obj.class_id) if student_obj.class_id else ''
            }

        except Exception as e:
            logging.error(f"Erro ao buscar dados do aluno: {str(e)}")
            import traceback
            logging.error(traceback.format_exc())
            return {
                'id': str(student.id) if hasattr(student, 'id') else '',
                'name': 'Nome não informado',
                'nome': 'Nome não informado'
            }

    def _generate_qr_code(self, student_id: str, test_id: str = None, 
                         gabarito_id: str = None) -> str:
        """
        Gera QR code com metadados simplificados
        Prioriza gabarito_id se fornecido, senão usa test_id
        """
        try:
            # Criar metadados do QR code
            qr_metadata = {
                "student_id": str(student_id)
            }
            
            # Adicionar test_id ou gabarito_id
            if gabarito_id:
                qr_metadata["gabarito_id"] = str(gabarito_id)
            elif test_id:
                qr_metadata["test_id"] = str(test_id)
            
            # Gerar QR code com JSON
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=2,
            )
            qr.add_data(json.dumps(qr_metadata))
            qr.make(fit=True)
            
            # Criar imagem do QR Code
            qr_img = qr.make_image(fill_color="black", back_color="white")
            
            # Converter para base64
            qr_buffer = BytesIO()
            qr_img.save(qr_buffer, format="PNG")
            qr_buffer.seek(0)
            qr_code_base64 = base64.b64encode(qr_buffer.read()).decode()
            
            return qr_code_base64

        except Exception as e:
            logging.error(f"Erro ao gerar QR code: {str(e)}")
            import traceback
            logging.error(traceback.format_exc())
            return ""

