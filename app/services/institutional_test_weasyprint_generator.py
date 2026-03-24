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
from pypdf import PdfReader, PdfWriter


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
        self._minio_service = None
        self._image_data_uri_cache: Dict[str, str] = {}

    def _get_minio_service(self):
        if self._minio_service is None:
            from app.services.storage.minio_service import MinIOService
            self._minio_service = MinIOService()
        return self._minio_service

    def _weasyprint_base_url(self) -> Optional[str]:
        public_api_base_url = os.getenv("PUBLIC_API_BASE_URL")
        if not public_api_base_url:
            app_env = (os.getenv("APP_ENV") or "").lower()
            if app_env in ("development", "dev", "local"):
                public_api_base_url = "http://localhost:5000"
        return public_api_base_url

    def _render_template(self, template_name: str, template_data: Dict[str, Any]) -> str:
        template = self.env.get_template(template_name)
        return template.render(**template_data)

    def _html_to_pdf_bytes(self, html_content: str) -> bytes:
        pdf_buffer = io.BytesIO()
        base_url = self._weasyprint_base_url()
        if base_url:
            html_obj = HTML(string=html_content, base_url=base_url)
        else:
            html_obj = HTML(string=html_content)
        html_obj.write_pdf(pdf_buffer)
        pdf_buffer.seek(0)
        return pdf_buffer.read()

    def _inline_question_images_html(self, html: str, images_meta: Any) -> str:
        """
        Substitui <img src="/questions/<question_id>/images/<image_id>"> por data:...;base64,...
        Usa question.images (minio_bucket/minio_object_name) quando existir; senão fallback
        via MinIO com bucket question-images e object_name {question_id}/{image_id}.png
        """
        if not html or not isinstance(html, str):
            return html or ""

        import re
        def _sanitize_img_tag(img_tag_html: str) -> str:
            """
            Normaliza <img> vindo do editor para o PDF:
            - Remove width/height (podem forçar largura excessiva no WeasyPrint)
            - Remove declarações width/height do style inline (mantém o restante)
            Mantém o layout/CSS do template como fonte de verdade.
            """
            if not img_tag_html:
                return img_tag_html

            # Remove width/height como atributos (com ou sem aspas)
            img_tag_html = re.sub(r"""\s+\b(width|height)\b\s*=\s*(".*?"|'.*?'|[^\s>]+)""", "", img_tag_html, flags=re.IGNORECASE)

            # Remove width/height dentro do style inline, preservando outras regras
            def _strip_style(m: re.Match) -> str:
                quote = m.group(1)
                style = m.group(2) or ""
                # remove width/height: ...; (aceita com/sem ';' final)
                style = re.sub(r"""(^|;)\s*(width|height)\s*:\s*[^;]+""", "", style, flags=re.IGNORECASE)
                # normaliza separators e espaços
                style = re.sub(r"""\s*;\s*""", "; ", style).strip()
                style = style.strip("; ").strip()
                if not style:
                    return ""
                return f' style={quote}{style}{quote}'

            img_tag_html = re.sub(r"""\s+style\s*=\s*(")(.*?)\1""", _strip_style, img_tag_html, flags=re.IGNORECASE | re.DOTALL)
            img_tag_html = re.sub(r"""\s+style\s*=\s*(')(.*?)\1""", _strip_style, img_tag_html, flags=re.IGNORECASE | re.DOTALL)

            # Limpa espaços duplicados antes do fechamento
            img_tag_html = re.sub(r"""\s+>""", ">", img_tag_html)
            return img_tag_html

        # Captura tags <img ... src="/questions/<question_id>/images/<image_id>" ...>
        img_tag_pattern = re.compile(
            r"""<img\b[^>]*\bsrc\s*=\s*["']/questions/([^/"']+)/images/([a-fA-F0-9-]{36})["'][^>]*>""",
            flags=re.IGNORECASE
        )

        by_id: Dict[str, Dict[str, Any]] = {}
        if isinstance(images_meta, list):
            for img in images_meta:
                if isinstance(img, dict) and img.get("id"):
                    by_id[str(img["id"])] = img

        def _replace(match: "re.Match"):
            img_tag = match.group(0)
            question_id = match.group(1)
            image_id = match.group(2)
            meta = by_id.get(image_id)
            bucket = None
            object_name = None
            mime = "image/png"
            if meta:
                bucket = meta.get("minio_bucket")
                object_name = meta.get("minio_object_name")
                mime = meta.get("type") or mime
            if not bucket or not object_name:
                # Fallback: path padrão MinIO question-images/{question_id}/{image_id}.png
                bucket = "question-images"
                object_name = f"{question_id}/{image_id}.png"

            cache_key = f"{bucket}:{object_name}"
            cached = self._image_data_uri_cache.get(cache_key)
            if cached:
                replaced = re.sub(
                    r"""\bsrc\s*=\s*["'][^"']*["']""",
                    f'src="{cached}"',
                    img_tag,
                    count=1,
                    flags=re.IGNORECASE
                )
                return _sanitize_img_tag(replaced)

            try:
                data = self._get_minio_service().download_file(bucket, object_name)
                if not data:
                    return _sanitize_img_tag(img_tag)
                b64 = base64.b64encode(data).decode("utf-8")
                data_uri = f"data:{mime};base64,{b64}"
                self._image_data_uri_cache[cache_key] = data_uri
                replaced = re.sub(
                    r"""\bsrc\s*=\s*["'][^"']*["']""",
                    f'src="{data_uri}"',
                    img_tag,
                    count=1,
                    flags=re.IGNORECASE
                )
                return _sanitize_img_tag(replaced)
            except Exception:
                return _sanitize_img_tag(img_tag)

        return img_tag_pattern.sub(_replace, html)

    def generate_institutional_test_pdf_arch4(
        self,
        test_data: Dict,
        students_data: List[Dict],
        questions_data: List[Dict],
        class_test_id: str = None,
        output_dir: str = None
    ) -> List[Dict]:
        """
        Architecture 4 (otimizada) com PDF Overlay para OMR:
        - Gera 1 PDF base (capa institucional genérica + blocos + questões), uma vez.
        - Gera 1 PDF template do cartão OMR (WeasyPrint, dados neutros), uma vez.
        - Por aluno: gera apenas overlay PDF (ReportLab: nome, escola, turma, QR) e aplica
          sobre o template OMR; depois mescla base + cartão OMR preenchido.
        - WeasyPrint roda apenas 2 vezes (prova + template OMR), não N vezes por aluno.
        """
        if output_dir is None:
            output_dir = '/tmp/celery_pdfs/physical_tests'
        os.makedirs(output_dir, exist_ok=True)

        # Preparar estrutura comum de questões (uma vez)
        questions_by_subject = self._organize_questions_by_subject(questions_data, test_data)
        blocks_config = test_data.get('blocks_config', {})
        use_blocks = blocks_config.get('use_blocks', False)
        if use_blocks:
            questions_by_block = self._organize_questions_by_blocks(questions_data, test_data)
            question_counter = 1
            for block in questions_by_block:
                if block and 'questions' in block:
                    for question in block['questions']:
                        if question:
                            question['question_number'] = question_counter
                            question_counter += 1
        else:
            questions_by_block = None
            question_counter = 1
            for subject_name, subject_questions in questions_by_subject.items():
                for question in subject_questions:
                    question['question_number'] = question_counter
                    question_counter += 1

        total_questions = len(questions_data)
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
                except Exception:
                    alternatives = []
            options_list = []
            if isinstance(alternatives, list) and len(alternatives) > 0:
                for idx, _alt in enumerate(alternatives):
                    if idx < len(letters):
                        options_list.append(letters[idx])
            else:
                options_list = ['A', 'B', 'C', 'D']
            if len(options_list) < 2:
                options_list = ['A', 'B', 'C', 'D']
            questions_map[question_num] = options_list

        # Inline base64 nas questões (uma vez)
        if questions_by_block:
            for block in questions_by_block:
                for q in block.get('questions', []) or []:
                    if not isinstance(q, dict):
                        continue
                    q['content'] = Markup(self._inline_question_images_html(str(q.get('content') or ''), q.get('images') or []))
                    if q.get('prompt'):
                        q['prompt'] = Markup(self._inline_question_images_html(str(q.get('prompt') or ''), q.get('images') or []))
                    alts = q.get('alternatives') or []
                    if isinstance(alts, list):
                        for alt in alts:
                            if isinstance(alt, dict) and alt.get('content'):
                                alt['content'] = Markup(self._inline_question_images_html(str(alt['content']), q.get('images') or []))
        else:
            for subject_questions in questions_by_subject.values():
                for q in subject_questions:
                    if not isinstance(q, dict):
                        continue
                    q['content'] = Markup(self._inline_question_images_html(str(q.get('content') or ''), q.get('images') or []))
                    if q.get('prompt'):
                        q['prompt'] = Markup(self._inline_question_images_html(str(q.get('prompt') or ''), q.get('images') or []))
                    alts = q.get('alternatives') or []
                    if isinstance(alts, list):
                        for alt in alts:
                            if isinstance(alt, dict) and alt.get('content'):
                                alt['content'] = Markup(self._inline_question_images_html(str(alt['content']), q.get('images') or []))

        default_logo_base64 = self._load_default_logo()
        # Aluno genérico para a capa do base (rodapé usa fallbacks do template)
        base_student = {'school_name': '', 'class_name': '', 'name': ''}
        base_template_data = {
            'test_data': test_data,
            'student': base_student,
            'questions_by_subject': questions_by_subject,
            'questions_by_block': questions_by_block,
            'blocks_config': blocks_config,
            'questions_map': questions_map,
            'answer_sheet_image': '',
            'total_questions': total_questions,
            'datetime': datetime,
            'generated_date': datetime.now().strftime('%d/%m/%Y %H:%M'),
            'default_logo': default_logo_base64,
            'include_cover': True,
            'include_questions': True,
            'include_answer_sheet': False,
        }
        base_html = self._render_template('institutional_test_hybrid.html', base_template_data)
        base_pdf_bytes = self._html_to_pdf_bytes(base_html)
        base_reader = PdfReader(io.BytesIO(base_pdf_bytes))

        # Template OMR único (WeasyPrint com dados vazios/placeholder) — uma vez
        omr_placeholder_student = {
            'name': '',
            'school_name': '',
            'class_name': '',
            'qr_code': self._get_omr_placeholder_qr_base64(),
        }
        omr_template_data = {
            'test_data': test_data,
            'student': omr_placeholder_student,
            'questions_by_subject': questions_by_subject,
            'questions_by_block': questions_by_block,
            'blocks_config': blocks_config,
            'questions_map': questions_map,
            'answer_sheet_image': '',
            'total_questions': total_questions,
            'datetime': datetime,
            'generated_date': datetime.now().strftime('%d/%m/%Y %H:%M'),
            'default_logo': default_logo_base64,
            'include_cover': False,
            'include_questions': False,
            'include_answer_sheet': True,
        }
        omr_template_html = self._render_template('institutional_test_hybrid.html', omr_template_data)
        omr_template_pdf_bytes = self._html_to_pdf_bytes(omr_template_html)
        omr_template_reader = PdfReader(io.BytesIO(omr_template_pdf_bytes))
        if len(omr_template_reader.pages) < 1:
            raise RuntimeError("Template OMR sem páginas")
        # Manter bytes para clonar a página por aluno (merge overlay em cima)
        del omr_template_reader

        # Coordenadas (uma vez)
        coordinates = self._map_existing_form_coordinates(questions_data)

        generated_files: List[Dict[str, Any]] = []
        total_students = len(students_data)
        job_id = (test_data or {}).get('job_id')
        previous_class_name = None
        for idx, student in enumerate(students_data, 1):
            index_0 = idx - 1
            current_class_name = student.get('class_name') or ''
            if job_id:
                try:
                    if current_class_name != previous_class_name:
                        from app.services.progress_store import update_job
                        update_job(job_id, {"stage_message": f"Gerando turma {current_class_name or '...'}..."})
                        previous_class_name = current_class_name
                except Exception:
                    pass
                try:
                    from app.services.progress_store import update_item_processing
                    update_item_processing(job_id, index_0, extra={
                        'student_id': str(student.get('id', '')),
                        'student_name': student.get('name', student.get('nome', '')),
                        'class_id': str(student.get('class_id', '')) if student.get('class_id') else None,
                        'class_name': student.get('class_name'),
                        'school_name': student.get('school_name'),
                    })
                except Exception:
                    pass
            try:
                student_id = str(student.get('id', ''))
                # Overlay ReportLab (nome, escola, turma, QR) nas posições do template
                overlay_bytes = self._generate_student_overlay_pdf(student, test_data)
                if not overlay_bytes:
                    raise RuntimeError("Falha ao gerar overlay do aluno")
                overlay_reader = PdfReader(io.BytesIO(overlay_bytes))
                # Clonar página do template OMR e aplicar overlay por cima
                omr_fresh = PdfReader(io.BytesIO(omr_template_pdf_bytes))
                omr_page = omr_fresh.pages[0]
                omr_page.merge_page(overlay_reader.pages[0])

                # Merge: prova base + cartão OMR (template + overlay)
                writer = PdfWriter()
                for p in base_reader.pages:
                    writer.add_page(p)
                writer.add_page(omr_page)
                out = io.BytesIO()
                writer.write(out)
                final_pdf_bytes = out.getvalue()

                # Persistir em disco para o pipeline existente
                student_name_safe = student.get('name', student.get('nome', 'aluno')).replace(' ', '_').replace('/', '_')
                pdf_path = os.path.join(output_dir, f"prova_{student_name_safe}_{student.get('id')}.pdf")
                with open(pdf_path, 'wb') as f:
                    f.write(final_pdf_bytes)

                qr_data_job = self._generate_qr_code_with_metadata(student.get('id'), test_data.get('id'))
                file_info = {
                    'student_id': student.get('id'),
                    'student_name': student.get('name', student.get('nome', 'Nome não informado')),
                    'qr_code_data': json.dumps(qr_data_job),
                    'coordinates': coordinates,
                    'has_pdf_data': True,
                    'has_answer_sheet_data': False,
                    'pdf_path': pdf_path,
                }
                generated_files.append(file_info)

                if job_id:
                    try:
                        from app.services.progress_store import update_item_done
                        update_item_done(job_id, index_0, {
                            'student_id': student_id,
                            'student_name': student.get('name', student.get('nome', '')),
                            'class_id': str(student.get('class_id', '')) if student.get('class_id') else None,
                            'class_name': student.get('class_name'),
                            'school_name': student.get('school_name'),
                        })
                    except Exception:
                        pass

                gc.collect()
                if idx % 10 == 0 or idx == total_students:
                    logging.debug(f"Gerados {idx}/{total_students} PDFs institucionais (arch4)")
            except Exception as e:
                logging.error(f"Erro ao gerar PDF institucional WeasyPrint (arch4) para aluno {student.get('id', 'N/A')}: {str(e)}", exc_info=True)
                if job_id:
                    try:
                        from app.services.progress_store import update_item_error
                        update_item_error(job_id, index_0, str(e), extra={
                            'student_id': str(student.get('id', '')),
                            'student_name': student.get('name', student.get('nome', '')),
                            'class_id': str(student.get('class_id', '')) if student.get('class_id') else None,
                            'class_name': student.get('class_name'),
                            'school_name': student.get('school_name'),
                        })
                    except Exception:
                        pass
                continue

        return generated_files

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
            gabarito_id = str(test_data.get('gabarito_id', ''))
            
            # Criar metadados do QR code no formato JSON
            # ✅ NOVO: Incluir gabarito_id para correção usar gabarito central
            qr_metadata = {
                "student_id": student_id,
                "test_id": test_id
            }
            
            if gabarito_id:
                qr_metadata["gabarito_id"] = gabarito_id
            
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

        images_meta = processed.get('images') or []

        processed['instruction'] = instruction
        processed['title'] = title
        main_content_inlined = self._inline_question_images_html(main_content, images_meta)
        processed['content'] = self._process_html_content(main_content_inlined)

        # Processar secondstatement como pergunta/objetivo (aparece APÓS content e ANTES de alternatives)
        prompt = processed.get('secondstatement', '')
        if prompt:
            prompt_inlined = self._inline_question_images_html(prompt, images_meta)
            processed['prompt'] = self._process_html_content(prompt_inlined)
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

                alt_content_inlined = self._inline_question_images_html(alt_content, images_meta)
                processed_alt = {
                    'letter': chr(65 + i),  # A, B, C, D...
                    'content': self._process_html_content(alt_content_inlined),
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
        Processa conteúdo HTML para renderização pelo WeasyPrint.

        Princípio: o WeasyPrint renderiza HTML/CSS nativamente — passamos o HTML
        do editor o mais íntegro possível e usamos CSS como grade de proteção.

        O que é feito aqui:
          1. Remove APENAS os wrappers de imagem do editor (node-imageComponent,
             image-component) como pares completos — preserva todos os outros <span>
             e seus fechamentos (bold, italic, cores etc. do editor).
          2. Mantém todos os <p> com seus atributos de style (text-align, etc.),
             preservando quebras de parágrafo e alinhamento definidos pelo editor.
          3. Sanitiza dimensões de <img> para que o CSS do template controle o tamanho.
        """
        if not content:
            return Markup('')

        import re

        # Remove os wrappers de imagem do editor como PARES COMPLETOS (abertura + conteúdo + fechamento).
        # Isso preserva o conteúdo interno e não deixa </span> órfãos que causariam
        # vazamento de formatação (bold/italic leaking) para o texto seguinte.
        processed = re.sub(
            r'<span\s+class="node-imageComponent">(.*?)</span>',
            r'\1',
            content,
            flags=re.DOTALL | re.IGNORECASE,
        )
        processed = re.sub(
            r'<span\s+class="image-component">(.*?)</span>',
            r'\1',
            processed,
            flags=re.DOTALL | re.IGNORECASE,
        )

        # Sanitizar TODAS as <img> — remove width/height para que o CSS do template
        # (max-width: 100%) controle o tamanho.
        processed = self._sanitize_all_img_dimensions(processed)

        # Retornar como Markup para Jinja2 não escapar HTML.
        # Os <p> do editor (com style="text-align: center/justify/left" etc.) chegam
        # intactos ao WeasyPrint, que os renderiza respeitando os inline styles.
        return Markup(processed)

    def _sanitize_all_img_dimensions(self, html: str) -> str:
        """
        Remove atributos width/height e propriedades width/height do style inline
        de TODAS as tags <img> no HTML, independente do padrão de URL da imagem.
        Garante que o CSS do template (max-width: 100%) seja a única fonte de verdade
        para o tamanho das imagens no PDF.
        """
        import re

        def _strip_img_tag(m: re.Match) -> str:
            tag = m.group(0)
            # Remove atributos width="..." e height="..."
            tag = re.sub(
                r"""\s+\b(width|height)\b\s*=\s*(?:"[^"]*"|'[^']*'|\S+)""",
                '',
                tag,
                flags=re.IGNORECASE,
            )
            # Remove width:/height: dentro do style inline, mantendo outras regras
            def _strip_style(sm: re.Match) -> str:
                quote = sm.group(1)
                style = sm.group(2) or ''
                style = re.sub(
                    r'(?:^|(?<=;))\s*(?:width|height)\s*:[^;]+',
                    '',
                    style,
                    flags=re.IGNORECASE,
                )
                style = re.sub(r';\s*;', ';', style).strip().strip(';').strip()
                if not style:
                    return ''
                return f' style={quote}{style}{quote}'

            tag = re.sub(
                r"""\s+style\s*=\s*(")(.*?)\1""",
                _strip_style,
                tag,
                flags=re.IGNORECASE | re.DOTALL,
            )
            tag = re.sub(
                r"""\s+style\s*=\s*(')(.*?)\1""",
                _strip_style,
                tag,
                flags=re.IGNORECASE | re.DOTALL,
            )
            return tag

        return re.sub(r'<img\b[^>]*>', _strip_img_tag, html, flags=re.IGNORECASE)

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

    def _get_omr_placeholder_qr_base64(self) -> str:
        """
        Retorna uma imagem PNG 1x1 branca em base64 para usar no template OMR
        quando não há dados de aluno (template base sem QR/nome).
        Evita quebrar o <img src="data:..."> do template.
        """
        buf = io.BytesIO()
        img = PILImage.new('RGB', (1, 1), (255, 255, 255))
        img.save(buf, format='PNG')
        buf.seek(0)
        return base64.b64encode(buf.read()).decode('utf-8')

    def _generate_student_overlay_pdf(
        self, student: Dict, test_data: Dict
    ) -> Optional[bytes]:
        """
        Gera um PDF A4 contendo apenas os dados variáveis do cartão OMR
        (nome, escola, turma, QR code) nas posições exatas do layout.
        Coordenadas fixas derivadas do template (COORDENADAS_OMR_OVERLAY.md);
        sem arquivo de configuração externo.
        """
        try:
            from reportlab.pdfgen.canvas import Canvas
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.utils import ImageReader
            from reportlab.lib.colors import HexColor

            # A4 em pontos (595.28 x 841.89); ReportLab: origem inferior esquerda
            buffer = io.BytesIO()
            c = Canvas(buffer, pagesize=A4)
            c.setPageSize(A4)

            # Coordenadas em pt derivadas do CSS do template (institutional_test_hybrid.html)
            # Origem ReportLab: canto inferior esquerdo da página A4 (595.28 x 841.89 pt)
            #
            # Cálculo base:
            #   @page answer-sheet-omr { margin: 0 }
            #   .answer-sheet { padding: 1.2cm 2cm ... }  → conteúdo começa em x=56.69pt, y_top=34.02pt
            #   .answer-sheet-header { border:1px; padding:4px } → conteúdo em x=60.44pt, y_top=37.77pt
            #   .header-info-line { font-size:7pt; line-height:1.6 } → linha=11.2pt, margem=0.375pt
            #   .header-info-line .label { min-width:120px=90pt; display:inline-block }
            #     → valor começa sempre em x = 60.44 + 90 = 150.44pt ≈ X_TEXT
            #
            # Linha 1 (NOME DA PROVA)  : baseline ≈ 48.7pt do topo  → ~793pt do rodapé
            # Linha 2 (NOME COMPLETO)  : baseline ≈ 61.7pt do topo  → Y_PDF_NAME
            # Linha 3 (ESTADO)         : baseline ≈ 73.7pt do topo  → estático, não sobreposto
            # Linha 4 (MUNICÍPIO)      : baseline ≈ 85.6pt do topo  → estático, não sobreposto
            # Linha 5 (ESCOLA)         : baseline ≈ 97.6pt do topo  → Y_PDF_SCHOOL
            # Linha 6 (TURMA)          : baseline ≈ 109.5pt do topo → Y_PDF_TURMA
            #
            # QR: .header-right (width=140px=105pt, padding-left=10px, border-left=1px)
            #     .qr-code-box (120px=90pt, box-sizing:border-box, border:1px) centralizado
            # X_TEXT: conteúdo começa em 60.44pt (left padding+border+padding do header)
            #         + min-width do label: 100px = 75pt → X_TEXT = 60.44 + 75 = 135.44pt
            X_TEXT = 135.44
            Y_PDF_NAME   = 780.16  # baseline NOME COMPLETO  (linha 2)
            Y_PDF_SCHOOL = 744.31  # baseline ESCOLA          (linha 5, após ESTADO e MUNICÍPIO)
            Y_PDF_TURMA  = 732.36  # baseline TURMA           (linha 6, 1 linha abaixo de ESCOLA)
            QR_X = 441.46          # borda esquerda do qr-code-box
            QR_Y = 680.77          # borda inferior do qr-code-box
            QR_SIZE = 90

            FONT_NAME = 'Helvetica'
            FONT_SIZE = 7
            FONT_COLOR = HexColor('#374151')
            MAX_TEXT_WIDTH_CHARS = 50

            def _truncate(s: str, max_chars: int = MAX_TEXT_WIDTH_CHARS) -> str:
                s = (s or '').strip()
                if len(s) <= max_chars:
                    return s
                return s[: max_chars - 1] + '…'

            student_name = _truncate(student.get('name') or student.get('nome') or '')
            raw_school = (student.get('school_name') or '').strip()
            upper_school = raw_school.upper()
            if raw_school and 'NÃO INFORMADO' not in upper_school:
                school_name = _truncate(raw_school)
            else:
                school_name = ''
            class_name = (student.get('class_name') or student.get('turma') or '').strip()
            grade_name = ((test_data or {}).get('grade_name') or '').strip()
            # Monta o valor completo de TURMA idêntico ao template:
            # "grade_name - class_name" → espelha {{ test_data.grade_name }} - {{ student.class_name }}
            if grade_name and class_name:
                turma_display = _truncate(f"{grade_name} - {class_name}")
            elif grade_name:
                turma_display = _truncate(grade_name)
            else:
                turma_display = _truncate(class_name)

            c.setFont(FONT_NAME, FONT_SIZE)
            c.setFillColor(FONT_COLOR)
            if student_name:
                c.drawString(X_TEXT, Y_PDF_NAME, student_name.upper())
            if school_name:
                c.drawString(X_TEXT, Y_PDF_SCHOOL, school_name.upper())
            if turma_display:
                c.drawString(X_TEXT, Y_PDF_TURMA, turma_display.upper())

            # QR code: incluir gabarito_id para correção usar gabarito central
            student_id = str(student.get('id', ''))
            test_id = str((test_data or {}).get('id', ''))
            gabarito_id = str((test_data or {}).get('gabarito_id', ''))
            
            # ✅ NOVO: Incluir gabarito_id no QR Code para provas físicas
            qr_metadata = {"student_id": student_id, "test_id": test_id}
            if gabarito_id:
                qr_metadata["gabarito_id"] = gabarito_id
            import qrcode as _qrcode
            qr = _qrcode.QRCode(
                version=1,
                error_correction=_qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=2,
            )
            qr.add_data(json.dumps(qr_metadata))
            qr.make(fit=True)
            qr_img = qr.make_image(fill_color="black", back_color="white")
            qr_buffer = io.BytesIO()
            qr_img.save(qr_buffer, format="PNG")
            qr_buffer.seek(0)
            c.drawImage(
                ImageReader(qr_buffer),
                QR_X, QR_Y,
                width=QR_SIZE,
                height=QR_SIZE,
            )

            c.save()
            buffer.seek(0)
            return buffer.read()
        except Exception as e:
            logging.error(f"Erro ao gerar overlay PDF do aluno {student.get('id', 'N/A')}: {str(e)}", exc_info=True)
            return None

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

    def _generate_qr_code_with_metadata(self, student_id: str, test_id: str, gabarito_id: str = None) -> dict:
        """
        Gera QR code com metadados simplificados (student_id, test_id e opcionalmente gabarito_id)
        
        Args:
            student_id: ID do aluno
            test_id: ID da prova
            gabarito_id: ID do gabarito central (opcional, usado para provas físicas)
        """
        try:
            qr_data = {
                'student_id': student_id,
                'test_id': test_id
            }
            
            # ✅ NOVO: Incluir gabarito_id se fornecido
            if gabarito_id:
                qr_data['gabarito_id'] = gabarito_id
            
            return qr_data

        except Exception as e:
            logging.error(f"Erro ao gerar QR code: {str(e)}")
            return {}
