# -*- coding: utf-8 -*-
"""
Serviço para geração de PDFs de cartões resposta usando WeasyPrint + Jinja2
NOVO: Suporte a template base + overlay (Architecture 4)
"""

from weasyprint import HTML
from jinja2 import Environment, FileSystemLoader, select_autoescape
import os
import io
import base64
import logging
import json
import re
import unicodedata
import qrcode
import gc
from datetime import datetime
from typing import List, Dict, Any, Optional
from io import BytesIO
from pypdf import PdfReader, PdfWriter


def sanitize_filename(name: str, max_length: int = 80) -> str:
    """
    Normaliza string para uso seguro em nome de arquivo.
    Remove acentos, mantém apenas alfanuméricos e underscore, lowercase.
    """
    if not name or not isinstance(name, str):
        return "aluno"
    n = unicodedata.normalize('NFKD', name)
    n = n.encode('ascii', 'ignore').decode('ascii')
    n = re.sub(r'[^\w\s-]', '', n)
    n = re.sub(r'[-\s]+', '_', n).strip('_')
    n = n.lower() or "aluno"
    return n[:max_length] if max_length else n


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

    def generate_answer_sheets_arch4(self, class_id: str, test_data: Dict, 
                              num_questions: int, use_blocks: bool,
                              blocks_config: Dict, correct_answers: Dict,
                              gabarito_id: str = None, questions_options: Dict = None,
                              output_dir: str = None) -> Dict:
        """
        ⚠️ MÉTODO AUXILIAR - NÃO USAR DIRETAMENTE
        
        Este método é chamado internamente por generate_answer_sheets() (método descontinuado).
        
        Para gerar cartões resposta, use: generate_class_answer_sheets() que é usado
        pela rota POST /answer-sheets/generate e gera PDFs individuais por aluno.
        
        ---
        
        Gera UM PDF com MÚLTIPLAS PÁGINAS para uma turma usando Architecture 4 (Overlay).
        
        OTIMIZAÇÃO: WeasyPrint roda apenas 1× (template base), depois aplica overlay por aluno.
        Cada página = 1 cartão resposta de 1 aluno.
        
        Architecture 4 (Template Base + Overlay):
        1. Gera 1× PDF base com WeasyPrint (dados vazios/placeholder)
        2. Para cada aluno: gera overlay PDF (ReportLab: nome, escola, turma, QR)
        3. Merge: base + overlay = cartão final
        
        Args:
            class_id: ID da turma
            test_data: Dados da prova (title, municipality, state, etc.)
            num_questions: Quantidade de questões
            use_blocks: Se usa blocos ou não
            blocks_config: Configuração de blocos {num_blocks, questions_per_block, separate_by_subject}
            correct_answers: Dict com respostas corretas {1: "A", 2: "B", ...}
            gabarito_id: ID do gabarito salvo (obrigatório para QR code)
            questions_options: Dict com alternativas de cada questão {1: ['A', 'B', 'C'], 2: ['A', 'B', 'C', 'D'], ...}
            output_dir: Diretório para salvar PDF em disco (padrão: /tmp/celery_pdfs/answer_sheets)

        Returns:
            Dict com:
            {
                'class_id': uuid,
                'class_name': 'A',
                'pdf_path': '/tmp/.../cartoes_turma_A.pdf',
                'student_count': 25,
                'file_size': 1024000
            }
        """
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
            logging.info(f"[GENERATOR ARCH4] Turma: {class_obj.name} (ID: {class_id})")
            logging.info(f"[GENERATOR ARCH4] Estudantes encontrados: {len(students)}")
            
            # Retornar None para turmas sem alunos
            if not students:
                logging.warning(f"[GENERATOR ARCH4] ⚠️ Turma {class_obj.name} sem alunos cadastrados")
                return None

            # Criar diretório de saída
            os.makedirs(output_dir, exist_ok=True)

            # Processar questions_options: converter chaves string para int
            questions_map = {}
            if questions_options:
                for key, value in questions_options.items():
                    try:
                        q_num = int(key)
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

            # Organizar questões por blocos
            questions_by_block = self._organize_questions_by_blocks(
                num_questions, blocks_config, questions_map
            )

            # ========================================================================
            # ARCHITECTURE 4: GERAR TEMPLATE BASE (1× WeasyPrint)
            # ========================================================================
            logging.info(f"[GENERATOR ARCH4] Gerando template base com WeasyPrint...")
            
            # Aluno placeholder (dados vazios para template base)
            # IMPORTANTE: Usar espaço invisível (não vazio) para evitar fallbacks do Jinja2
            # String vazia '' → Jinja2 usa 'or' fallback → aparece "Não informado"
            # String com espaço ' ' → Jinja2 considera truthy → não usa fallback
            placeholder_student = {
                'id': ' ',
                'name': ' ',
                'nome': ' ',
                'school_name': ' ',  # Espaço para evitar "Não informado"
                'class_name': ' ',
                'grade_name': ' ',
                'qr_code': self._get_placeholder_qr_base64()  # QR placeholder
            }
            
            # Preparar dados para template base
            base_template_data = {
                'test_data': test_data,
                'student': placeholder_student,
                'questions_by_block': questions_by_block,
                'questions_map': questions_map,
                'blocks_config': blocks_config,
                'total_questions': num_questions,
                'datetime': datetime,
                'generated_date': datetime.now().strftime('%d/%m/%Y %H:%M')
            }

            # Renderizar template HTML base
            template = self.env.get_template('answer_sheet.html')
            base_html = template.render(**base_template_data)
            
            # Gerar PDF base com WeasyPrint (1× apenas)
            base_pdf_bytes = HTML(string=base_html).write_pdf()
            base_reader = PdfReader(io.BytesIO(base_pdf_bytes))
            
            logging.info(f"[GENERATOR ARCH4] ✅ Template base gerado ({len(base_pdf_bytes)} bytes)")

            # ========================================================================
            # ARCHITECTURE 4: GERAR OVERLAY POR ALUNO + MERGE
            # ========================================================================
            logging.info(f"[GENERATOR ARCH4] Gerando overlays para {len(students)} alunos...")
            
            writer = PdfWriter()
            successful_count = 0
            
            for idx, student in enumerate(students, 1):
                try:
                    # Buscar dados completos do aluno
                    student_data = self._get_complete_student_data(student)
                    
                    # Gerar overlay PDF (ReportLab: nome, escola, turma, QR)
                    overlay_bytes = self._generate_student_overlay_pdf(
                        student_data, 
                        test_data, 
                        gabarito_id=gabarito_id
                    )
                    
                    if not overlay_bytes:
                        logging.error(f"[GENERATOR ARCH4] Falha ao gerar overlay para aluno {student.id}")
                        continue
                    
                    # Clonar página do template base
                    base_page = base_reader.pages[0]
                    
                    # Aplicar overlay sobre a página base
                    overlay_reader = PdfReader(io.BytesIO(overlay_bytes))
                    base_page.merge_page(overlay_reader.pages[0])
                    
                    # Adicionar página mesclada ao writer
                    writer.add_page(base_page)
                    successful_count += 1
                    
                    if idx % 10 == 0:
                        logging.info(f"[GENERATOR ARCH4] Processados {idx}/{len(students)} alunos")

                except Exception as e:
                    logging.error(f"[GENERATOR ARCH4] Erro ao processar aluno {student.id}: {str(e)}", exc_info=True)
                    continue

            if successful_count == 0:
                raise ValueError("Nenhuma página foi gerada com sucesso")

            # ========================================================================
            # SALVAR PDF FINAL EM DISCO
            # ========================================================================
            
            pdf_buffer = io.BytesIO()
            writer.write(pdf_buffer)
            pdf_buffer.seek(0)
            pdf_bytes = pdf_buffer.read()

            class_name_safe = class_obj.name.replace(' ', '_').replace('/', '_')
            pdf_filename = f"cartoes_turma_{class_name_safe}_{class_id}.pdf"
            pdf_path = os.path.join(output_dir, pdf_filename)

            with open(pdf_path, 'wb') as f:
                f.write(pdf_bytes)

            file_size = os.path.getsize(pdf_path)
            logging.info(f"[GENERATOR ARCH4] ✅ PDF gerado: {pdf_filename} ({file_size} bytes, {successful_count} páginas)")

            # Buscar grade_name da turma
            grade_name = ''
            if class_obj.grade_id:
                from app.models.grades import Grade
                grade_obj = Grade.query.get(class_obj.grade_id)
                if grade_obj:
                    grade_name = grade_obj.name

            # Liberar memória
            del pdf_bytes, pdf_buffer, base_pdf_bytes, base_reader, writer
            gc.collect()

            return {
                'class_id': str(class_id),
                'class_name': class_obj.name,
                'grade_name': grade_name,
                'pdf_path': pdf_path,
                'filename': pdf_filename,
                'total_students': len(students),
                'total_pages': successful_count,
                'file_size': file_size
            }

        except Exception as e:
            logging.error(f"[GENERATOR ARCH4] ❌ Erro ao gerar cartões resposta: {str(e)}", exc_info=True)
            raise

    def _get_placeholder_qr_base64(self) -> str:
        """
        Gera QR code placeholder vazio para template base.
        Será substituído pelo overlay com dados reais do aluno.
        """
        try:
            qr_metadata = {"placeholder": "true"}
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=1,
            )
            qr.add_data(json.dumps(qr_metadata))
            qr.make(fit=True)
            qr_img = qr.make_image(fill_color="black", back_color="white")
            qr_buffer = BytesIO()
            qr_img.save(qr_buffer, format="PNG")
            qr_buffer.seek(0)
            return base64.b64encode(qr_buffer.read()).decode()
        except Exception:
            return ""

    def generate_answer_sheets(self, class_id: str, test_data: Dict, 
                              num_questions: int, use_blocks: bool,
                              blocks_config: Dict, correct_answers: Dict,
                              gabarito_id: str = None, questions_options: Dict = None,
                              output_dir: str = None, use_arch4: bool = True) -> Dict:
        """
        ⚠️ MÉTODO DESCONTINUADO - NÃO ESTÁ SENDO USADO
        
        Este método gera UM PDF ÚNICO com MÚLTIPLAS PÁGINAS (1 página por aluno).
        
        PROBLEMA: Demora muito para várias turmas (gera 1 arquivo grande por turma).
        
        SUBSTITUTO: Use generate_class_answer_sheets() que gera PDFs individuais
        por aluno e é usado pela rota POST /answer-sheets/generate.
        
        MOTIVO DA DESCONTINUAÇÃO:
        - Para múltiplas turmas, gerar 1 PDF grande por turma é ineficiente
        - PDFs individuais permitem melhor organização e distribuição
        - Sistema atual usa generate_class_answer_sheets() com arch4 (overlay)
        
        Este método foi mantido apenas para compatibilidade com código legado,
        mas NÃO é mais chamado pelas rotas principais do sistema.
        
        Args:
            class_id: ID da turma
            test_data: Dados da prova (title, municipality, state, etc.)
            num_questions: Quantidade de questões
            use_blocks: Se usa blocos ou não
            blocks_config: Configuração de blocos {num_blocks, questions_per_block, separate_by_subject}
            correct_answers: Dict com respostas corretas {1: "A", 2: "B", ...}
            gabarito_id: ID do gabarito salvo (obrigatório para QR code)
            questions_options: Dict com alternativas de cada questão {1: ['A', 'B', 'C'], 2: ['A', 'B', 'C', 'D'], ...}
            output_dir: Diretório para salvar PDF em disco (padrão: /tmp/celery_pdfs/answer_sheets)
            use_arch4: Se True, usa Architecture 4 (overlay); se False, usa método antigo (padrão: True)

        Returns:
            Dict com:
            {
                'class_id': uuid,
                'class_name': 'A',
                'pdf_path': '/tmp/.../cartoes_turma_A.pdf',
                'student_count': 25,
                'file_size': 1024000
            }
        """
        # ========================================================================
        # ARCHITECTURE 4: Template Base + Overlay (RECOMENDADO)
        # ========================================================================
        if use_arch4:
            logging.info(f"[GENERATOR] Usando Architecture 4 (Template Base + Overlay)")
            return self.generate_answer_sheets_arch4(
                class_id=class_id,
                test_data=test_data,
                num_questions=num_questions,
                use_blocks=use_blocks,
                blocks_config=blocks_config,
                correct_answers=correct_answers,
                gabarito_id=gabarito_id,
                questions_options=questions_options,
                output_dir=output_dir
            )
        
        # ========================================================================
        # MÉTODO ANTIGO: WeasyPrint por aluno (FALLBACK)
        # ========================================================================
        logging.warning(f"[GENERATOR] Usando método antigo (WeasyPrint por aluno) - considere usar arch4=True")
        
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
            logging.info(f"[GENERATOR] Turma: {class_obj.name} (ID: {class_id})")
            logging.info(f"[GENERATOR] Estudantes encontrados: {len(students)}")
            
            # Retornar None para turmas sem alunos
            if not students:
                logging.warning(f"[GENERATOR] ⚠️ Turma {class_obj.name} sem alunos cadastrados")
                return None

            # Criar diretório de saída
            os.makedirs(output_dir, exist_ok=True)

            # Processar questions_options: converter chaves string para int
            questions_map = {}
            if questions_options:
                for key, value in questions_options.items():
                    try:
                        q_num = int(key)
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

            # Organizar questões por blocos
            questions_by_block = self._organize_questions_by_blocks(
                num_questions, blocks_config, questions_map
            )
            
            # Gerar 1 PDF com múltiplas páginas (1 página por aluno)
            logging.info(f"[GENERATOR] Gerando PDF multi-página para {len(students)} alunos da turma {class_obj.name}")
            
            # Coletar HTMLs de todos os alunos
            html_pages = []
            for student in students:
                try:
                    student_data = self._get_complete_student_data(student)
                    
                    # Gerar QR code
                    qr_code_base64 = self._generate_qr_code(
                        student_id=student_data['id'],
                        test_id=test_data.get('id'),
                        gabarito_id=gabarito_id
                    )

                    student_with_qr = student_data.copy()
                    student_with_qr['qr_code'] = qr_code_base64

                    # Preparar dados para template
                    template_data = {
                        'test_data': test_data,
                        'student': student_with_qr,
                        'questions_by_block': questions_by_block,
                        'questions_map': questions_map,
                        'blocks_config': blocks_config,
                        'total_questions': num_questions,
                        'datetime': datetime,
                        'generated_date': datetime.now().strftime('%d/%m/%Y %H:%M')
                    }

                    # Renderizar template HTML
                    template = self.env.get_template('answer_sheet.html')
                    html_content = template.render(**template_data)
                    html_pages.append(html_content)

                except Exception as e:
                    logging.error(f"Erro ao gerar página para aluno {student.id}: {str(e)}", exc_info=True)
                    continue

            if not html_pages:
                raise ValueError("Nenhuma página foi gerada com sucesso")

            # Juntar todos os HTMLs em 1 documento
            combined_html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        @page { margin: 0; }
        body { margin: 0; padding: 0; }
        .page { page-break-after: always; }
    </style>
</head>
<body>
"""
            for html_page in html_pages:
                combined_html += f'<div class="page">{html_page}</div>\n'
            
            combined_html += """</body>
</html>"""

            # Gerar PDF único com todas as páginas
            pdf_buffer = io.BytesIO()
            HTML(string=combined_html).write_pdf(pdf_buffer)
            pdf_buffer.seek(0)
            pdf_bytes = pdf_buffer.read()

            # Salvar em disco
            class_name_safe = class_obj.name.replace(' ', '_').replace('/', '_')
            pdf_filename = f"cartoes_turma_{class_name_safe}_{class_id}.pdf"
            pdf_path = os.path.join(output_dir, pdf_filename)

            with open(pdf_path, 'wb') as f:
                f.write(pdf_bytes)

            file_size = os.path.getsize(pdf_path)
            logging.info(f"[GENERATOR] ✅ PDF gerado: {pdf_filename} ({file_size} bytes)")

            # Buscar grade_name da turma
            grade_name = ''
            if class_obj.grade_id:
                from app.models.grades import Grade
                grade_obj = Grade.query.get(class_obj.grade_id)
                if grade_obj:
                    grade_name = grade_obj.name

            # Liberar memória
            del pdf_bytes, pdf_buffer, combined_html, html_pages
            gc.collect()

            return {
                'class_id': str(class_id),
                'class_name': class_obj.name,
                'grade_name': grade_name,
                'pdf_path': pdf_path,
                'filename': pdf_filename,
                'total_students': len(students),
                'total_pages': len(students),
                'file_size': file_size
            }

        except Exception as e:
            logging.error(f"[GENERATOR] ❌ Erro ao gerar cartões resposta: {str(e)}", exc_info=True)
            raise

    def _build_questions_map(self, num_questions: int, questions_options: Dict = None) -> Dict[int, List[str]]:
        """Monta questions_map (igual ao fluxo de generate_answer_sheets). Não altera lógica existente."""
        questions_map = {}
        if questions_options:
            for key, value in questions_options.items():
                try:
                    q_num = int(key)
                    if isinstance(value, list) and len(value) >= 2:
                        questions_map[q_num] = value
                    else:
                        questions_map[q_num] = ['A', 'B', 'C', 'D']
                except (ValueError, TypeError):
                    continue
        if not questions_map:
            for q in range(1, num_questions + 1):
                questions_map[q] = ['A', 'B', 'C', 'D']
        else:
            for q in range(1, num_questions + 1):
                if q not in questions_map:
                    questions_map[q] = ['A', 'B', 'C', 'D']
        return questions_map

    def _build_class_folder_path(self, base_output_dir: str, class_obj) -> str:
        """
        Cria e retorna o path da turma usando NOMES (não IDs):
        base_output_dir/municipio_{nome}/escola_{nome}/serie_{nome}/turma_{nome}/
        Ex.: municipio_jaru/escola_em_joao_silva/serie_5_ano/turma_a/
        """
        from app.models.city import City
        city_name = 'municipio'
        if class_obj.school and getattr(class_obj.school, 'city_id', None):
            city_obj = City.query.get(class_obj.school.city_id)
            if city_obj and getattr(city_obj, 'name', None):
                city_name = city_obj.name
        school_name = (class_obj.school.name if class_obj.school else None) or 'escola'
        grade_name = (class_obj.grade.name if class_obj.grade else None) or 'serie'
        class_name = (class_obj.name or 'turma').strip() or 'turma'
        path = os.path.join(
            base_output_dir,
            f"municipio_{sanitize_filename(city_name, max_length=60)}",
            f"escola_{sanitize_filename(school_name, max_length=60)}",
            f"serie_{sanitize_filename(grade_name, max_length=40)}",
            f"turma_{sanitize_filename(class_name, max_length=40)}",
        )
        os.makedirs(path, exist_ok=True)
        return path

    def generate_class_answer_sheets(
        self,
        class_id: str,
        base_output_dir: str,
        test_data: Dict,
        num_questions: int,
        use_blocks: bool,
        blocks_config: Dict,
        correct_answers: Dict,
        gabarito_id: str = None,
        questions_options: Dict = None,
        use_arch4: bool = True,
    ) -> Optional[Dict]:
        """
        Gera 1 PDF por aluno da turma.
        
        NOVO (arch4=True): Usa Architecture 4 (Template Base + Overlay) - 10-50× mais rápido
        ANTIGO (arch4=False): Usa _generate_individual_answer_sheet (WeasyPrint por aluno)
        
        Salva em base_output_dir/municipio_/escola_/serie_/turma_/{nome}_{serie}_{turma}.pdf
        Retorna apenas metadados (class_id, total_students).
        """
        try:
            from app.models.student import Student
            from app.models.studentClass import Class

            class_obj = Class.query.get(class_id)
            if not class_obj:
                raise ValueError(f"Turma {class_id} não encontrada")
            students = Student.query.filter_by(class_id=class_id).all()
            if not students:
                logging.warning(f"[GENERATOR] ⚠️ Turma {class_obj.name} sem alunos cadastrados")
                return None

            questions_map = self._build_questions_map(num_questions, questions_options)
            questions_by_block = self._organize_questions_by_blocks(num_questions, blocks_config, questions_map)

            grade_name = (class_obj.grade.name if class_obj.grade else '').strip() or 'serie'
            grade_safe = sanitize_filename(grade_name, max_length=40)
            class_name_raw = (class_obj.name or 'turma').strip()
            class_safe = sanitize_filename(class_name_raw, max_length=40)

            folder = self._build_class_folder_path(base_output_dir, class_obj)
            
            # ========================================================================
            # ARCHITECTURE 4: Template Base + Overlay (RECOMENDADO)
            # ========================================================================
            if use_arch4:
                logging.info(f"[GENERATOR ARCH4] Gerando cartões para turma {class_obj.name} com overlay")
                
                # Gerar template base (1× WeasyPrint)
                # IMPORTANTE: Usar espaço invisível (não vazio) para evitar fallbacks do Jinja2
                # String vazia '' → Jinja2 usa 'or' fallback → aparece "Não informado"
                # String com espaço ' ' → Jinja2 considera truthy → não usa fallback
                placeholder_student = {
                    'id': ' ',
                    'name': ' ',
                    'nome': ' ',
                    'school_name': ' ',  # Espaço para evitar "Não informado"
                    'class_name': ' ',
                    'grade_name': ' ',
                    'qr_code': self._get_placeholder_qr_base64()
                }
                
                base_template_data = {
                    'test_data': test_data,
                    'student': placeholder_student,
                    'questions_by_block': questions_by_block,
                    'questions_map': questions_map,
                    'blocks_config': blocks_config,
                    'total_questions': num_questions,
                    'datetime': datetime,
                    'generated_date': datetime.now().strftime('%d/%m/%Y %H:%M')
                }
                
                template = self.env.get_template('answer_sheet.html')
                base_html = template.render(**base_template_data)
                base_pdf_bytes = HTML(string=base_html).write_pdf()
                base_reader = PdfReader(io.BytesIO(base_pdf_bytes))
                
                logging.info(f"[GENERATOR ARCH4] ✅ Template base gerado ({len(base_pdf_bytes)} bytes)")
                
                # Gerar overlay por aluno
                generated_count = 0
                for idx, student in enumerate(students, 1):
                    try:
                        student_data = self._get_complete_student_data(student)
                        
                        # Gerar overlay
                        overlay_bytes = self._generate_student_overlay_pdf(
                            student_data,
                            test_data,
                            gabarito_id=gabarito_id
                        )
                        
                        if not overlay_bytes:
                            logging.error(f"[GENERATOR ARCH4] Falha ao gerar overlay para aluno {student.id}")
                            continue
                        
                        # Clonar página base e aplicar overlay
                        base_page = base_reader.pages[0]
                        overlay_reader = PdfReader(io.BytesIO(overlay_bytes))
                        base_page.merge_page(overlay_reader.pages[0])
                        
                        # Salvar PDF individual
                        writer = PdfWriter()
                        writer.add_page(base_page)
                        
                        pdf_buffer = io.BytesIO()
                        writer.write(pdf_buffer)
                        pdf_buffer.seek(0)
                        pdf_bytes = pdf_buffer.read()
                        
                        student_name = student_data.get('name', 'aluno')
                        name_safe = sanitize_filename(student_name, max_length=60)
                        filename = f"{name_safe}_{grade_safe}_{class_safe}.pdf"
                        filepath = os.path.join(folder, filename)
                        
                        with open(filepath, 'wb') as f:
                            f.write(pdf_bytes)
                        
                        generated_count += 1
                        
                        if idx % 10 == 0:
                            logging.info(f"[GENERATOR ARCH4] Processados {idx}/{len(students)} alunos")
                        
                        gc.collect()
                        
                    except Exception as e:
                        logging.error(f"[GENERATOR ARCH4] Erro ao processar aluno {student.id}: {str(e)}", exc_info=True)
                        continue
                
                logging.info(f"[GENERATOR ARCH4] ✅ {generated_count} PDFs gerados para turma {class_obj.name}")
                
                return {
                    'class_id': str(class_id),
                    'total_students': generated_count,
                }
            
            # ========================================================================
            # MÉTODO ANTIGO: WeasyPrint por aluno (FALLBACK)
            # ========================================================================
            else:
                logging.warning(f"[GENERATOR] Usando método antigo (WeasyPrint por aluno) para turma {class_obj.name}")
                
                generated_count = 0
                for student in students:
                    pdf_bytes = self._generate_individual_answer_sheet(
                        student,
                        test_data,
                        num_questions,
                        use_blocks,
                        blocks_config,
                        questions_by_block,
                        gabarito_id=gabarito_id,
                        questions_map=questions_map,
                    )
                    if not pdf_bytes:
                        continue
                    student_name = self._get_complete_student_data(student).get('name', 'aluno')
                    name_safe = sanitize_filename(student_name, max_length=60)
                    filename = f"{name_safe}_{grade_safe}_{class_safe}.pdf"
                    filepath = os.path.join(folder, filename)
                    with open(filepath, 'wb') as f:
                        f.write(pdf_bytes)
                    generated_count += 1
                    gc.collect()

                return {
                    'class_id': str(class_id),
                    'total_students': generated_count,
                }
                
        except Exception as e:
            logging.error(f"[GENERATOR] ❌ Erro em generate_class_answer_sheets turma {class_id}: {str(e)}", exc_info=True)
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
            # ✅ Blocos personalizados com disciplinas (subject_id obrigatório)
            for block_def in custom_blocks:
                block_id = block_def.get('block_id')
                subject_id = block_def.get('subject_id')
                subject_name = block_def.get('subject_name')
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
                    'subject_id': str(subject_id) if subject_id else None,
                    'subject_name': subject_name,
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
            
            # Buscar dados da turma, série e escola
            class_name = ''
            school_name = ''
            grade_name = ''
            
            if student_obj.class_id:
                class_obj = Class.query.get(student_obj.class_id)
                if class_obj:
                    class_name = class_obj.name or ''
                    if class_obj.grade:
                        grade_name = class_obj.grade.name or ''
            
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
                'grade_name': grade_name,
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

    def _generate_student_overlay_pdf(self, student: Dict, test_data: Dict, gabarito_id: str = None) -> Optional[bytes]:
        """
        Gera overlay PDF com dados variáveis do aluno (nome, escola, turma, QR code).
        
        IMPORTANTE: Este overlay é aplicado sobre o template base gerado pelo WeasyPrint.
        As coordenadas são FIXAS e derivadas do layout do template answer_sheet.html.
        
        NÃO ALTERAR coordenadas sem validar visualmente o alinhamento!
        Ver documentação: app/services/cartao_resposta/COORDENADAS_OVERLAY.md
        
        Args:
            student: Dict com dados do aluno (id, name, school_name, class_name)
            test_data: Dict com dados da prova (id, title, grade_name, etc.)
            gabarito_id: ID do gabarito para incluir no QR code
            
        Returns:
            bytes: PDF overlay em formato bytes, ou None se erro
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

            # ========================================================================
            # COORDENADAS FIXAS - Derivadas do template answer_sheet.html
            # VALIDADAS: Mesmas coordenadas das provas físicas (institutional_test_weasyprint_generator.py)
            # ========================================================================
            # IMPORTANTE: NÃO ALTERAR sem validar alinhamento visual!
            # Template: padding 1.2cm top, 2cm sides; header 6.4cm height
            # Linhas: font-size 7pt, margin 0.5px, label min-width 100px
            # ========================================================================
            
            # COORDENADAS X: Cada campo tem X diferente baseado no tamanho do label
            # Template cartão resposta NÃO tem min-width no label (diferente das provas físicas)
            # Cálculo: padding(56.69) + border(0.75) + padding_header(3) = 60.44pt (base)
            # Labels têm tamanhos diferentes:
            #   - "NOME COMPLETO:" ≈ 85pt (label mais largo)
            #   - "ESCOLA:" ≈ 45pt (label médio)
            #   - "TURMA:" ≈ 40pt (label menor)
            X_BASE = 60.44
            X_NOME = X_BASE + 90     # 150.44pt - após "NOME COMPLETO:" (label mais largo)
            X_ESCOLA = X_BASE + 50   # 110.44pt - após "ESCOLA:"
            X_TURMA = X_BASE + 45    # 105.44pt - após "TURMA:"
            
            # COORDENADAS Y (validadas das provas físicas)
            Y_PDF_NAME = 780.16      # Baseline do NOME COMPLETO (linha 2)
            Y_PDF_SCHOOL = 744.31    # Baseline da ESCOLA (linha 5, após ESTADO e MUNICÍPIO)
            Y_PDF_TURMA = 732.36     # Baseline da TURMA (linha 6, 1 linha abaixo de ESCOLA)
            
            QR_X = 441.46            # Posição X do QR code (canto inferior esquerdo)
            QR_Y = 680.77            # Posição Y do QR code (canto inferior esquerdo)
            QR_SIZE = 90             # Tamanho do QR code (90pt = 120px do CSS)
            
            FONT_NAME = 'Helvetica'
            FONT_SIZE = 7            # 7pt (mesmo do CSS)
            FONT_COLOR = HexColor('#374151')
            MAX_TEXT_WIDTH_CHARS = 50  # ~268pt para não invadir QR

            def _truncate(s: str, max_chars: int = MAX_TEXT_WIDTH_CHARS) -> str:
                """Trunca texto com ellipsis se exceder limite"""
                s = (s or '').strip()
                if len(s) <= max_chars:
                    return s
                return s[:max_chars - 1] + '…'

            # ========================================================================
            # EXTRAIR E FORMATAR DADOS DO ALUNO
            # ========================================================================
            
            # Nome do aluno (NOME COMPLETO)
            student_name = _truncate(student.get('name') or student.get('nome') or '')
            
            # Escola (ESCOLA) - filtrar "Não informado"
            raw_school = (student.get('school_name') or '').strip()
            upper_school = raw_school.upper()
            if raw_school and 'NÃO INFORMADO' not in upper_school:
                school_name = _truncate(raw_school)
            else:
                school_name = ''
            
            # Turma (TURMA) - formato: "SÉRIE - TURMA"
            class_name = (student.get('class_name') or student.get('turma') or '').strip()
            grade_name = ((test_data or {}).get('grade_name') or '').strip()
            
            # Montar display de turma (igual ao template)
            if grade_name and class_name:
                turma_display = _truncate(f"{grade_name} - {class_name}")
            elif grade_name:
                turma_display = _truncate(grade_name)
            else:
                turma_display = _truncate(class_name)

            # ========================================================================
            # DESENHAR TEXTOS NO OVERLAY
            # ========================================================================
            
            c.setFont(FONT_NAME, FONT_SIZE)
            c.setFillColor(FONT_COLOR)
            
            # Usar coordenada X específica para cada campo (labels têm tamanhos diferentes)
            if student_name:
                c.drawString(X_NOME, Y_PDF_NAME, student_name.upper())
            
            if school_name:
                c.drawString(X_ESCOLA, Y_PDF_SCHOOL, school_name.upper())
            
            if turma_display:
                c.drawString(X_TURMA, Y_PDF_TURMA, turma_display.upper())

            # ========================================================================
            # GERAR E DESENHAR QR CODE
            # ========================================================================
            
            student_id = str(student.get('id', ''))
            test_id = str((test_data or {}).get('id', ''))
            
            # Metadados do QR code
            qr_metadata = {"student_id": student_id}
            if gabarito_id:
                qr_metadata["gabarito_id"] = str(gabarito_id)
            elif test_id:
                qr_metadata["test_id"] = test_id
            
            # Gerar QR code
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=1,
            )
            qr.add_data(json.dumps(qr_metadata))
            qr.make(fit=True)
            qr_img = qr.make_image(fill_color="black", back_color="white")
            
            # Converter para ImageReader
            qr_buffer = io.BytesIO()
            qr_img.save(qr_buffer, format="PNG")
            qr_buffer.seek(0)
            qr_image_reader = ImageReader(qr_buffer)
            
            # Desenhar QR code no overlay
            c.drawImage(qr_image_reader, QR_X, QR_Y, width=QR_SIZE, height=QR_SIZE)

            # ========================================================================
            # FINALIZAR OVERLAY
            # ========================================================================
            
            c.save()
            buffer.seek(0)
            return buffer.read()

        except Exception as e:
            logging.error(f"Erro ao gerar overlay PDF do aluno: {str(e)}", exc_info=True)
            return None
