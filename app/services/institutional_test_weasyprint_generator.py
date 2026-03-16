# -*- coding: utf-8 -*-
"""
Serviço para geração de PDFs de provas institucionais usando WeasyPrint + Jinja2
Permite uso completo de HTML e CSS sem as limitações do ReportLab
"""

from weasyprint import HTML, CSS
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup
import os
import io
import base64
import logging
import json
import gc
from datetime import datetime
from typing import List, Dict, Any, Optional
from PIL import Image as PILImage


class InstitutionalTestWeasyPrintGenerator:
    """
    Gerador de PDFs para provas institucionais usando WeasyPrint + Jinja2
    Suporta HTML e CSS completos, sem limitações de atributos
    """

    def __init__(self):
        # Configurar Jinja2 para carregar templates
        template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates')
        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(['html', 'xml'])
        )

        # Adicionar filtros personalizados
        self.env.filters['safe'] = lambda x: x

    def generate_institutional_test_pdf(self, test_data: Dict, students_data: List[Dict],
                                      questions_data: List[Dict], class_test_id: str = None,
                                      output_dir: str = None) -> List[Dict]:
        """
        Gera PDFs de provas institucionais para todos os alunos usando WeasyPrint
        PROCESSAMENTO INCREMENTAL: gera → salva em disco → libera memória

        Args:
            test_data: Dados da prova (test_id, title, description, etc.)
            students_data: Lista de alunos com dados (id, nome, email, etc.)
            questions_data: Lista de questões ordenadas
            class_test_id: ID da aplicação da prova (ClassTest)
            output_dir: Diretório para salvar PDFs em disco (padrão: /tmp/celery_pdfs/physical_tests)

        Returns:
            Lista com informações dos PDFs gerados (com pdf_path se output_dir fornecido)
        """
        # Definir output_dir padrão para containers Linux
        if output_dir is None:
            output_dir = '/tmp/celery_pdfs/physical_tests'
        
        # Criar diretório de saída
        os.makedirs(output_dir, exist_ok=True)
        
        # Mapear coordenadas uma única vez (reutilizar para todos)
        coordinates = self._map_existing_form_coordinates(questions_data)
        
        generated_files = []
        total_students = len(students_data)

        for idx, student in enumerate(students_data, 1):
            try:
                # Gerar PDF individual para cada aluno
                pdf_data = self._generate_individual_institutional_pdf_data(
                    test_data, student, questions_data, class_test_id
                )

                if pdf_data:
                    # Gerar QR code
                    qr_data = self._generate_qr_code_with_metadata(
                        student['id'], test_data['id']
                    )
                    
                    file_info = {
                        'student_id': student['id'],
                        'student_name': student.get('name', student.get('nome', 'Nome não informado')),
                        'qr_code_data': json.dumps(qr_data),
                        'coordinates': coordinates,
                        'has_pdf_data': True,
                        'has_answer_sheet_data': False
                    }
                    
                    if output_dir:
                        # Salvar em disco e liberar memória imediatamente
                        student_name_safe = student.get('name', student.get('nome', 'aluno')).replace(' ', '_').replace('/', '_')
                        pdf_path = os.path.join(output_dir, f"prova_{student_name_safe}_{student['id']}.pdf")
                        
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
                    logging.debug(f"Gerados {idx}/{total_students} PDFs institucionais")

            except Exception as e:
                # Log apenas em caso de erro (não dentro do loop normal)
                logging.error(f"Erro ao gerar PDF institucional WeasyPrint para aluno {student.get('id', 'N/A')}: {str(e)}", exc_info=True)
                continue

        return generated_files

    def _generate_individual_institutional_pdf_data(self, test_data: Dict, student: Dict,
                                                  questions_data: List[Dict], class_test_id: str = None) -> Optional[bytes]:
        """
        Gera PDF individual institucional para um aluno usando WeasyPrint
        """
        try:
            # Organizar questões por disciplina (mantido para compatibilidade)
            questions_by_subject = self._organize_questions_by_subject(questions_data, test_data)
            
            # Organizar questões por blocos conforme configuração
            blocks_config = test_data.get('blocks_config', {})
            use_blocks = blocks_config.get('use_blocks', False)
            
            if use_blocks:
                questions_by_block = self._organize_questions_by_blocks(questions_data, test_data)
                
                # Adicionar número sequencial às questões baseado nos blocos
                question_counter = 1
                for block in questions_by_block:
                    if block and 'questions' in block:
                        for question in block['questions']:
                            if question:
                                question['question_number'] = question_counter
                                question_counter += 1
            else:
                # Comportamento padrão: organizar por disciplina
                questions_by_block = None
                question_counter = 1
                for subject_name, subject_questions in questions_by_subject.items():
                    for question in subject_questions:
                        question['question_number'] = question_counter
                        question_counter += 1

            # Gerar formulário de resposta (imagem base64)
            answer_sheet_image = self._generate_answer_sheet_base64(
                student, questions_data, test_data
            )
            
            # Gerar QR code no formato JSON (igual ao answer_sheet.html)
            # Formato: {"student_id": "...", "test_id": "..."}
            # O correction_n.py buscará o gabarito pelo test_id
            import qrcode
            from io import BytesIO
            import base64
            import json
            
            total_questions = len(questions_data)
            
            # Obter IDs completos
            student_id = str(student.get('id', ''))
            test_id = str(test_data.get('id', ''))
            
            # Criar metadados do QR code no formato JSON
            qr_metadata = {
                "student_id": student_id,
                "test_id": test_id  # Usar test_id para buscar gabarito depois
            }
            
            # Converter para JSON
            qr_data = json.dumps(qr_metadata)
            
            # Gerar QR code
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,  # Tamanho padrão (pode ajustar se necessário)
                border=2,
            )
            qr.add_data(qr_data)
            qr.make(fit=True)
            
            # Criar imagem do QR Code
            qr_img = qr.make_image(fill_color="black", back_color="white")
            
            # Converter para base64
            qr_buffer = BytesIO()
            qr_img.save(qr_buffer, format="PNG")
            qr_buffer.seek(0)
            qr_code_base64 = base64.b64encode(qr_buffer.read()).decode()
            
            # Adicionar QR code ao student dict para o template
            student_with_qr = student.copy()
            student_with_qr['qr_code'] = qr_code_base64
            
            # Carregar logo padrão (afirme_logo.png) se não houver logo do município
            default_logo_base64 = self._load_default_logo()
            
            # Gerar questions_map: mapear número da questão para lista de letras das alternativas
            # Formato: {1: ["A", "B", "C"], 2: ["A", "B", "C", "D"], ...}
            questions_map = {}
            letters = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
            
            for question in questions_data:
                question_num = question.get('question_number')
                if not question_num:
                    continue
                
                alternatives = question.get('alternatives', [])
                if isinstance(alternatives, str):
                    try:
                        alternatives = json.loads(alternatives)
                    except:
                        alternatives = []
                
                # Extrair letras das alternativas
                options_list = []
                if isinstance(alternatives, list) and len(alternatives) > 0:
                    for idx, alt in enumerate(alternatives):
                        if idx < len(letters):
                            options_list.append(letters[idx])
                else:
                    # Se não tem alternativas definidas, usar padrão A, B, C, D
                    options_list = ['A', 'B', 'C', 'D']
                
                # Garantir pelo menos 2 alternativas
                if len(options_list) < 2:
                    options_list = ['A', 'B', 'C', 'D']
                
                questions_map[question_num] = options_list
            
            # Preparar dados para o template
            template_data = {
                'test_data': test_data,
                'student': student_with_qr,  # Usar student com QR code
                'questions_by_subject': questions_by_subject,  # Mantido para compatibilidade
                'questions_by_block': questions_by_block,  # Nova estrutura de blocos
                'blocks_config': blocks_config,  # Configuração de blocos
                'questions_map': questions_map,  # Mapa de alternativas por questão (igual ao answer_sheet.html)
                'answer_sheet_image': answer_sheet_image,
                'total_questions': total_questions,
                'datetime': datetime,
                'generated_date': datetime.now().strftime('%d/%m/%Y %H:%M'),
                'default_logo': default_logo_base64  # Logo padrão (afirme_logo.png)
            }
            

            # Renderizar template HTML
            #template = self.env.get_template('institutional_test.html')
            template = self.env.get_template('institutional_test_hybrid.html')
            html_content = template.render(**template_data)

            # Gerar PDF com WeasyPrint
            pdf_buffer = io.BytesIO()

            # Usar base_url público para resolver URLs relativas (ex: /questions/.../images/...)
            public_api_base_url = os.getenv("PUBLIC_API_BASE_URL")
            if not public_api_base_url:
                app_env = (os.getenv("APP_ENV") or "").lower()
                # Fallback sensato para desenvolvimento/local
                if app_env in ("development", "dev", "local"):
                    public_api_base_url = "http://localhost:5000"

            if public_api_base_url:
                html_obj = HTML(string=html_content, base_url=public_api_base_url)
            else:
                # Sem base_url: manter comportamento antigo (pode falhar para URLs relativas)
                html_obj = HTML(string=html_content)

            html_obj.write_pdf(pdf_buffer)
            pdf_buffer.seek(0)

            return pdf_buffer.read()

        except Exception as e:
            logging.error(f"Erro ao gerar PDF individual WeasyPrint: {str(e)}")
            import traceback
            logging.error(traceback.format_exc())
            return None

    def _organize_questions_by_subject(self, questions_data: List[Dict], test_data: Dict) -> Dict:
        """
        Organiza questões por disciplina
        """
        try:
            subjects = {}
            subjects_info = test_data.get('subjects_info', {})

            # Converter subjects_info para dict se for lista
            if isinstance(subjects_info, list):
                subjects_info_dict = {}
                for idx, item in enumerate(subjects_info):
                    if isinstance(item, dict) and 'id' in item:
                        # Item já é um dicionário com id e name
                        subjects_info_dict[str(item['id'])] = item
                    elif isinstance(item, str):
                        # Item é uma string (ID da disciplina) - buscar no banco
                        try:
                            from app.models.subject import Subject
                            from app import db
                            subject_obj = Subject.query.get(item)
                            if subject_obj:
                                subjects_info_dict[str(item)] = {
                                    'id': subject_obj.id,
                                    'name': subject_obj.name
                                }
                            else:
                                logging.warning(f"Subject não encontrado no banco: {item}")
                        except Exception as e:
                            logging.error(f"Erro ao buscar Subject {item}: {str(e)}")
                subjects_info = subjects_info_dict
            elif not isinstance(subjects_info, dict):
                logging.warning(f"subjects_info é de tipo inesperado: {type(subjects_info)}")
                subjects_info = {}
            
            for idx, question in enumerate(questions_data):
                subject_id = question.get('subject_id')

                if subject_id and str(subject_id) in subjects_info:
                    subject_name = subjects_info[str(subject_id)]['name']
                else:
                    # Fallback: tentar pegar do objeto subject
                    subject = question.get('subject', {})
                    if isinstance(subject, dict):
                        subject_name = subject.get('name', 'DISCIPLINA')
                    else:
                        subject_name = 'DISCIPLINA'

                if subject_name not in subjects:
                    subjects[subject_name] = []

                # Processar questão para o template
                processed_question = self._process_question_for_template(question)
                subjects[subject_name].append(processed_question)

            
            return subjects

        except Exception as e:
            logging.error(f"Erro ao organizar questões por disciplina: {str(e)}")
            import traceback
            logging.error(traceback.format_exc())
            return {}

    def _organize_questions_by_blocks(self, questions_data: List[Dict], test_data: Dict) -> List[Dict]:
        """
        Organiza questões por blocos conforme configuração
        
        Args:
            questions_data: Lista de questões ordenadas
            test_data: Dados da prova incluindo blocks_config
            
        Returns:
            Lista de blocos, cada um contendo:
            - block_number: número do bloco
            - subject_name: nome da disciplina (ou None se não separar por disciplina)
            - questions: lista de questões do bloco
            - start_question_num: número da primeira questão
            - end_question_num: número da última questão
        """
        blocks_config = test_data.get('blocks_config', {})
        use_blocks = blocks_config.get('use_blocks', False)
        separate_by_subject = blocks_config.get('separate_by_subject', False)
        
        blocks = []
        
        # Esta função só é chamada quando use_blocks = True
        # Se use_blocks = False, não deveria chegar aqui
        if separate_by_subject:
            # Separar por disciplina: 1 bloco = 1 disciplina
            questions_by_subject = self._organize_questions_by_subject(questions_data, test_data)
            
            block_num = 1
            question_counter = 1
            for subject_name, subject_questions in questions_by_subject.items():
                if subject_questions:
                    # As questões já foram processadas em _organize_questions_by_subject
                    blocks.append({
                        'block_number': block_num,
                        'subject_name': subject_name,
                        'questions': subject_questions,
                        'start_question_num': question_counter,
                        'end_question_num': question_counter + len(subject_questions) - 1
                    })
                    question_counter += len(subject_questions)
                    block_num += 1
        else:
            # Distribuir questões sequencialmente pelos blocos
            num_blocks = blocks_config.get('num_blocks', 1)
            questions_per_block = blocks_config.get('questions_per_block', 12)
            total_questions = len(questions_data)
            
            for block_num in range(1, num_blocks + 1):
                start_idx = (block_num - 1) * questions_per_block
                end_idx = min(block_num * questions_per_block, total_questions)
                block_questions_raw = questions_data[start_idx:end_idx]
                
                # Processar questões para o template
                block_questions = [self._process_question_for_template(q) for q in block_questions_raw]
                
                if block_questions:
                    blocks.append({
                        'block_number': block_num,
                        'subject_name': None,
                        'questions': block_questions,
                        'start_question_num': start_idx + 1,
                        'end_question_num': end_idx
                    })
        
        # Validar que temos pelo menos um bloco
        if not blocks:
            processed_questions = [self._process_question_for_template(q) for q in questions_data]
            if processed_questions:
                blocks.append({
                    'block_number': 1,
                    'subject_name': None,
                    'questions': processed_questions,
                    'start_question_num': 1,
                    'end_question_num': len(processed_questions)
                })
        
        return blocks

    def _process_question_for_template(self, question: Dict) -> Dict:
        """
        Processa questão para uso no template Jinja2
        Converte imagens e formata conteúdo HTML
        Separa instrução, título e conteúdo quando necessário
        """
        import json
        import re
        processed = question.copy()

        # Processar formatted_text como conteúdo principal
        content = processed.get('formatted_text') or processed.get('text', '')

        # Separar instrução inicial, título centralizado e conteúdo
        instruction = None
        title = None
        main_content = content

        if content:
            # Padrão: primeiro <p> com "Leia o texto" ou similar (instrução)
            instruction_match = re.match(r'<p[^>]*>(Leia o texto[^<]*)</p>', content, re.IGNORECASE)
            if instruction_match:
                instruction = instruction_match.group(1)
                # Remover a instrução do conteúdo
                main_content = content[instruction_match.end():]

                # Procurar título centralizado (segundo <p> com text-align: center e <strong>)
                title_match = re.match(r'<p[^>]*text-align:\s*center[^>]*><strong>([^<]+)</strong></p>', main_content, re.IGNORECASE)
                if title_match:
                    title = title_match.group(1)
                    # Remover o título do conteúdo
                    main_content = main_content[title_match.end():]

        processed['instruction'] = instruction
        processed['title'] = title
        processed['content'] = self._process_html_content(main_content)

        # Processar secondstatement como pergunta/objetivo (aparece APÓS content e ANTES de alternatives)
        prompt = processed.get('secondstatement', '')
        if prompt:
            processed['prompt'] = self._process_html_content(prompt)
        else:
            processed['prompt'] = None

        # Processar alternativas (podem vir como JSON string)
        alternatives_data = processed.get('alternatives', [])
        if isinstance(alternatives_data, str):
            try:
                alternatives_data = json.loads(alternatives_data)
            except:
                alternatives_data = []

        if alternatives_data and isinstance(alternatives_data, list):
            processed_alternatives = []
            for i, alt in enumerate(alternatives_data):
                # Alternativas podem ter diferentes formatos
                if isinstance(alt, dict):
                    alt_content = alt.get('text') or alt.get('content', '')
                    alt_id = alt.get('id', chr(65 + i))
                else:
                    alt_content = str(alt)
                    alt_id = chr(65 + i)

                processed_alt = {
                    'letter': chr(65 + i),  # A, B, C, D...
                    'content': self._process_html_content(alt_content),
                    'id': alt_id
                }
                processed_alternatives.append(processed_alt)
            processed['alternatives'] = processed_alternatives
        else:
            processed['alternatives'] = []

        # Processar código de habilidade
        if 'skill' in processed and processed['skill']:
            skill = processed['skill']
            if isinstance(skill, dict):
                processed['skill_code'] = skill.get('code', '')
            else:
                # Buscar código da skill no banco
                try:
                    from app.models.skill import Skill
                    skill_obj = Skill.query.get(skill)
                    if skill_obj:
                        processed['skill_code'] = skill_obj.code
                    else:
                        processed['skill_code'] = ''
                except:
                    processed['skill_code'] = str(skill)
        else:
            processed['skill_code'] = ''

        return processed

    def _process_html_content(self, content: str) -> Markup:
        """
        Processa conteúdo HTML - WeasyPrint suporta HTML/CSS completo,
        então não precisamos limpar atributos como no ReportLab!
        """
        if not content:
            return Markup('')

        # WeasyPrint aceita HTML completo!
        # Apenas remover algumas tags que podem causar problemas de layout
        import re

        # Remover node-imageComponent e image-component spans (são wrappers desnecessários)
        processed = re.sub(r'<span class="node-imageComponent">', '', content)
        processed = re.sub(r'<span class="image-component">', '', processed)
        processed = re.sub(r'</span>', '', processed)

        # Mesclar múltiplos <p> em um único parágrafo para evitar quebras indesejadas
        # Substituir </p><p> por espaço para manter texto contínuo
        processed = re.sub(r'</p>\s*<p[^>]*>', ' ', processed)

        # Remover <p> no início e </p> no final se houver
        processed = re.sub(r'^<p[^>]*>', '', processed)
        processed = re.sub(r'</p>$', '', processed)

        # Retornar como Markup para Jinja2 não escapar HTML
        return Markup(processed)

    def _generate_answer_sheet_base64(self, student: Dict, questions_data: List[Dict],
                                     test_data: Dict) -> str:
        """
        Gera imagem do formulário de resposta em base64
        """
        try:
            from app.formularios import gerar_formulario_com_qrcode
            import tempfile

            # Gerar formulário usando formularios.py
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                temp_path = tmp.name

            # Preparar dados do aluno
            student_data_complete = self._get_complete_student_data(student['id'])

            # Gerar formulário
            imagem, coordenadas_respostas, coordenadas_qr = gerar_formulario_com_qrcode(
                student['id'],
                student.get('name', student.get('nome', 'Nome não informado')),
                len(questions_data),
                temp_path,
                student_data=student_data_complete,
                test_data=test_data
            )

            if imagem:
                # Converter para base64
                img_buffer = io.BytesIO()
                imagem.save(img_buffer, format='PNG')
                img_buffer.seek(0)
                img_base64 = base64.b64encode(img_buffer.read()).decode('utf-8')

                # Limpar arquivo temporário
                try:
                    os.unlink(temp_path)
                except:
                    pass

                return img_base64

            return ''

        except Exception as e:
            logging.error(f"Erro ao gerar formulário de resposta: {str(e)}")
            return ''

    def _get_complete_student_data(self, student_id: str) -> Dict:
        """
        Obtém dados completos do aluno do banco de dados
        """
        try:
            from app.models.student import Student
            student = Student.query.get(student_id)

            if student:
                # Student pode não ter email, usar campos que existem
                return {
                    'id': str(student.id),
                    'name': student.name,
                    'registration': getattr(student, 'registration', ''),
                    'class_name': getattr(student, 'class_name', ''),
                    'class_id': str(student.class_id) if hasattr(student, 'class_id') else ''
                }

            return {}

        except Exception as e:
            logging.error(f"Erro ao buscar dados do aluno: {str(e)}")
            import traceback
            logging.error(traceback.format_exc())
            return {}

    def _map_existing_form_coordinates(self, questions_data: List[Dict]) -> Dict:
        """
        Mapeia coordenadas do formulário para compatibilidade
        """
        try:
            coordinates = {
                "subjects": {},
                "qr_code": {
                    "x": 10, "y": 100, "width": 100, "height": 100
                }
            }

            # Mapear questões por disciplina
            subjects = {}
            for question in questions_data:
                subject_id = question.get('subject_id')
                if subject_id:
                    from app.models.subject import Subject
                    subject_obj = Subject.query.get(subject_id)
                    if subject_obj:
                        subject_name = subject_obj.name
                        if subject_name not in subjects:
                            subjects[subject_name] = []
                        subjects[subject_name].append(question)

            for subject_name, subject_questions in subjects.items():
                subject_key = subject_name.lower().replace(' ', '_')
                coordinates["subjects"][subject_key] = {}

                for i, question in enumerate(subject_questions):
                    question_key = f"question_{i+1}"
                    coordinates["subjects"][subject_key][question_key] = {}

                    alternatives = question.get('alternatives', [])
                    for j, alt in enumerate(alternatives):
                        alt_id = alt.get('id', chr(65 + j))
                        coordinates["subjects"][subject_key][question_key][alt_id] = {
                            "x": 112 + (j * 50), "y": 950 + (i * 45), "radius": 10
                        }

            return coordinates

        except Exception as e:
            logging.error(f"Erro ao mapear coordenadas: {str(e)}")
            return {}

    def _load_default_logo(self) -> Optional[str]:
        """
        Carrega a logo padrão (afirme_logo.png) e converte para base64
        """
        try:
            # Caminho para a logo padrão
            assets_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets')
            logo_path = os.path.join(assets_dir, 'afirme_logo.png')
            
            if os.path.exists(logo_path):
                with open(logo_path, 'rb') as logo_file:
                    logo_data = logo_file.read()
                    logo_base64 = base64.b64encode(logo_data).decode('utf-8')
                    return logo_base64
            else:
                logging.warning(f"Logo padrão não encontrada em: {logo_path}")
                return None
                
        except Exception as e:
            logging.error(f"Erro ao carregar logo padrão: {str(e)}")
            return None

    def _generate_qr_code_with_metadata(self, student_id: str, test_id: str) -> dict:
        """
        Gera QR code com metadados simplificados (apenas student_id e test_id)
        """
        try:
            qr_data = {
                'student_id': student_id,
                'test_id': test_id
            }
            return qr_data

        except Exception as e:
            logging.error(f"Erro ao gerar QR code: {str(e)}")
            return {}
