# -*- coding: utf-8 -*-
"""
=============================================================================
GERADOR OFICIAL EM PRODUÇÃO — PDF CARTÃO-RESPOSTA (AfirmePlay)
=============================================================================
Arquivo: app/services/cartao_resposta/answer_sheet_generator.py
Status: ATIVO

Template oficial: app/templates/answer_sheet.html
Correção pareada: app/services/cartao_resposta/correction_new_grid.py

NÃO confundir com app/services/answer_sheet_generator.py (cópia legada, sem imports).
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


def student_pdf_filename(student_name: str, grade_safe: str, class_safe: str, student_id: Any) -> str:
    """{nome}_{serie}_{turma}_{8 primeiros do student_id}.pdf: homônimos não dividem o mesmo arquivo."""
    name_safe = sanitize_filename(student_name, max_length=60)
    id_safe = sanitize_filename(str(student_id or "")[:8], max_length=8)
    return f"{name_safe}_{grade_safe}_{class_safe}_{id_safe}.pdf"


_ZIP_FORBIDDEN_CHARS = set('\\/:*?"<>|')


def zip_entry_name(name: str) -> str:
    """Nome legível de pasta/arquivo no ZIP: mantém acentos e espaços."""
    if not name or not isinstance(name, str):
        return ''
    cleaned = ''.join(ch for ch in name if ch not in _ZIP_FORBIDDEN_CHARS)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip().rstrip('.')
    return cleaned


def join_zip_path(*parts: str) -> str:
    cleaned = []
    for part in parts:
        if part is None:
            continue
        text = str(part).strip().strip('/')
        if text:
            cleaned.append(text)
    return '/'.join(cleaned)


def class_pdf_basename(grade_name: str, class_name: str) -> str:
    """Nome do PDF da turma, ex.: '9º ANO - A'."""
    grade = zip_entry_name(grade_name)
    turma = zip_entry_name(class_name)
    if grade and turma:
        return f"{grade} - {turma}"
    return grade or turma or 'turma'


def allocate_class_pdf_basename(base: str, class_id: Any, used: set) -> str:
    """Evita dois PDFs com o mesmo nome na mesma pasta do ZIP."""
    candidate = base or 'turma'
    if candidate.casefold() not in used:
        used.add(candidate.casefold())
        return candidate
    suffix = re.sub(r'[^0-9A-Za-z]', '', str(class_id or ''))[:8] or 'id'
    unique = f"{candidate} ({suffix})"
    n = 2
    while unique.casefold() in used:
        unique = f"{candidate} ({suffix}-{n})"
        n += 1
    used.add(unique.casefold())
    return unique


def class_pdf_zip_prefix(scope: str, school_name: str) -> str:
    """Pasta da escola só no escopo município. Escola, série e turma ficam na raiz."""
    if scope == 'city':
        return zip_entry_name(school_name) or 'Sem Escola'
    return ''


def _students_and_adap_label(class_obj, subturma_id: Any = None):
    """Alunos da turma, ou só da subturma ADAP (com o rótulo "5º Ano A – ADAP 1")."""
    from app.services.cartao_resposta.answer_sheet_audience import (
        cartao_adap_label,
        slice_students_query,
    )

    students = slice_students_query(class_obj.id, subturma_id).all()
    if not subturma_id:
        return students, None
    import uuid as _uuid

    from app.models.subturma import Subturma

    sub = Subturma.query.get(_uuid.UUID(str(subturma_id)))
    if sub is None or str(sub.class_id) != str(class_obj.id):
        return [], None
    grade_name = (class_obj.grade.name if class_obj.grade else '') or ''
    return students, cartao_adap_label(grade_name, class_obj.name, sub.support_level)


def legacy_student_zip_path(scope: str, school_name: str, grade_name: str, rel_zip_name: str) -> str:
    """Caminho interno do ZIP no modo um PDF por aluno (formato anterior)."""
    rel = (rel_zip_name or '').lstrip('/')
    if scope == 'city':
        school = school_name or 'Sem Escola'
        grade = grade_name or 'Sem Serie'
        return f"{school}/{grade}/{rel}"
    if scope == 'school':
        grade = grade_name or 'Sem Serie'
        return f"{grade}/{rel}"
    return rel


def school_name_is_missing(name: str) -> bool:
    raw = (name or '').strip()
    if not raw:
        return True
    folded = unicodedata.normalize('NFKD', raw).encode('ascii', 'ignore').decode('ascii').upper()
    return 'NAO INFORMADO' in folded


def reserve_pdf_path(path: str) -> str:
    """Caminho livre para gravar: se o arquivo já existir, registra aviso e usa sufixo em vez de sobrescrever."""
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    n = 2
    while os.path.exists(f"{base}-{n}{ext}"):
        n += 1
    free_path = f"{base}-{n}{ext}"
    logging.warning(
        "[ANSWER-SHEET] Arquivo de cartão já existe; gravando como %s para não sobrescrever %s",
        os.path.basename(free_path),
        path,
    )
    return free_path


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
                              output_dir: str = None, subturma_id: str = None) -> Dict:
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

            # Buscar alunos da turma (ou só da subturma ADAP)
            students, adap_label = _students_and_adap_label(class_obj, subturma_id)
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
                    if adap_label:
                        student_data['turma_label'] = adap_label
                    
                    # Gerar overlay PDF (ReportLab: nome, escola, turma, QR)
                    overlay_bytes = self._generate_student_overlay_pdf(
                        student_data, 
                        test_data, 
                        gabarito_id=gabarito_id
                    )
                    
                    if not overlay_bytes:
                        logging.error(f"[GENERATOR ARCH4] Falha ao gerar overlay para aluno {student.id}")
                        continue
                    
                    # Nova leitura do PDF base por aluno (merge_page muta a página; mesmo padrão que
                    # institutional_test_weasyprint_generator.generate_institutional_test_pdf_arch4)
                    base_fresh = PdfReader(io.BytesIO(base_pdf_bytes))
                    base_page = base_fresh.pages[0]
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
            del pdf_bytes, pdf_buffer, base_pdf_bytes, writer
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
                              output_dir: str = None, use_arch4: bool = True,
                              subturma_id: str = None) -> Dict:
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
                output_dir=output_dir,
                subturma_id=subturma_id,
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

            # Buscar alunos da turma (ou só da subturma ADAP)
            students, adap_label = _students_and_adap_label(class_obj, subturma_id)
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
                    if adap_label:
                        student_data['turma_label'] = adap_label
                    
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
        subturma_id: str = None,
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
            students, adap_label = _students_and_adap_label(class_obj, subturma_id)
            if not students:
                logging.warning(f"[GENERATOR] ⚠️ Turma {class_obj.name} sem alunos cadastrados")
                return None

            questions_map = self._build_questions_map(num_questions, questions_options)
            questions_by_block = self._organize_questions_by_blocks(num_questions, blocks_config, questions_map)

            grade_name = (class_obj.grade.name if class_obj.grade else '').strip() or 'serie'
            grade_safe = sanitize_filename(grade_name, max_length=40)
            class_name_raw = (class_obj.name or 'turma').strip()
            if adap_label:
                class_name_raw = adap_label
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
                
                logging.info(f"[GENERATOR ARCH4] ✅ Template base gerado ({len(base_pdf_bytes)} bytes)")
                
                # Gerar overlay por aluno
                generated_count = 0
                for idx, student in enumerate(students, 1):
                    try:
                        student_data = self._get_complete_student_data(student)
                        if adap_label:
                            student_data['turma_label'] = adap_label
                        
                        # Gerar overlay
                        overlay_bytes = self._generate_student_overlay_pdf(
                            student_data,
                            test_data,
                            gabarito_id=gabarito_id
                        )
                        
                        if not overlay_bytes:
                            logging.error(f"[GENERATOR ARCH4] Falha ao gerar overlay para aluno {student.id}")
                            continue
                        
                        # Nova leitura do PDF base por aluno (merge_page muta a página)
                        base_fresh = PdfReader(io.BytesIO(base_pdf_bytes))
                        base_page = base_fresh.pages[0]
                        overlay_reader = PdfReader(io.BytesIO(overlay_bytes))
                        base_page.merge_page(overlay_reader.pages[0])
                        
                        # Salvar PDF individual
                        writer = PdfWriter()
                        writer.add_page(base_page)
                        
                        pdf_buffer = io.BytesIO()
                        writer.write(pdf_buffer)
                        pdf_buffer.seek(0)
                        pdf_bytes = pdf_buffer.read()
                        
                        filename = student_pdf_filename(
                            student_data.get('name', 'aluno'), grade_safe, class_safe, student.id
                        )
                        filepath = reserve_pdf_path(os.path.join(folder, filename))
                        
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
                    filename = student_pdf_filename(
                        self._get_complete_student_data(student).get('name', 'aluno'),
                        grade_safe,
                        class_safe,
                        student.id,
                    )
                    filepath = reserve_pdf_path(os.path.join(folder, filename))
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
            # Fallback 1: topology OMR (fonte da verdade quando blocks[] está ausente)
            topology_blocks = (blocks_config.get('topology') or {}).get('blocks') or []
            if topology_blocks:
                for block_def in topology_blocks:
                    q_list = block_def.get('questions') or []
                    if not q_list:
                        continue
                    questions = []
                    for q_entry in q_list:
                        try:
                            q_num = int(q_entry.get('q'))
                        except (TypeError, ValueError, AttributeError):
                            continue
                        options = q_entry.get('alternatives') or questions_map.get(q_num, ['A', 'B', 'C', 'D'])
                        if not isinstance(options, list) or len(options) < 2:
                            options = questions_map.get(q_num, ['A', 'B', 'C', 'D'])
                        questions.append({
                            'question_number': q_num,
                            'options': options
                        })
                    if not questions:
                        continue
                    blocks.append({
                        'block_number': block_def.get('block_id'),
                        'subject_id': (
                            str(block_def['subject_id'])
                            if block_def.get('subject_id') is not None
                            else None
                        ),
                        'subject_name': block_def.get('subject_name'),
                        'questions': questions,
                        'start_question_num': questions[0]['question_number'],
                        'end_question_num': questions[-1]['question_number'],
                    })
            else:
                # Fallback 2: distribuir automaticamente (comportamento original)
                num_blocks = blocks_config.get('num_blocks', 1)
                questions_per_block = blocks_config.get('questions_per_block', 12)

                for block_num in range(1, num_blocks + 1):
                    start_question = (block_num - 1) * questions_per_block + 1
                    end_question = min(block_num * questions_per_block, num_questions)

                    questions = []
                    for q_num in range(start_question, end_question + 1):
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
            shift = ''
            class_obj = None
            
            if student_obj.class_id:
                class_obj = Class.query.get(student_obj.class_id)
                if class_obj:
                    class_name = class_obj.name or ''
                    shift = (class_obj.shift or '').strip()
                    if class_obj.grade:
                        grade_name = class_obj.grade.name or ''
            
            if student_obj.school_id:
                school_obj = School.query.get(student_obj.school_id)
                if school_obj:
                    school_name = (school_obj.name or '').strip()

            # Escola do aluno vazia ou "Não informado": usa a escola da turma.
            if school_name_is_missing(school_name) and class_obj is not None and class_obj.school:
                fallback_school = (class_obj.school.name or '').strip()
                if not school_name_is_missing(fallback_school):
                    school_name = fallback_school
            
            return {
                'id': str(student_obj.id),
                'name': student_obj.name or 'Nome não informado',
                'nome': student_obj.name or 'Nome não informado',
                'registration': getattr(student_obj, 'registration', ''),
                'class_name': class_name,
                'grade_name': grade_name,
                'shift': shift,
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
            # Cartão avulso: 12 primeiros caracteres. Gabarito identifica o cartão.
            qr_metadata = {
                "student_id": str(student_id)[:12]
            }
            
            if gabarito_id:
                qr_metadata["gabarito_id"] = str(gabarito_id)[:12]
            elif test_id:
                qr_metadata["test_id"] = str(test_id)[:12]
            
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
            # Linhas: font-size 7pt. O X do valor é a largura real do rótulo em negrito.
            # ========================================================================
            
            # X do valor = início do rótulo + largura real do rótulo em negrito + um espaço.
            # O rótulo no HTML é Helvetica 7pt bold. O valor fica colado, como ESTADO e MUNICÍPIO.
            # Base: padding(56.69) + border(0.75) + padding_header(3) = 60.44pt
            from reportlab.pdfbase.pdfmetrics import stringWidth

            X_BASE = 60.44
            FONT_NAME = 'Helvetica'
            LABEL_FONT = 'Helvetica-Bold'
            FONT_SIZE = 7            # 7pt (mesmo do CSS)
            SCHOOL_MIN_SIZE = 5.5
            FONT_COLOR = HexColor('#374151')

            def _x_after_label(label: str) -> float:
                gap = stringWidth(' ', FONT_NAME, FONT_SIZE)
                return X_BASE + stringWidth(label, LABEL_FONT, FONT_SIZE) + gap

            X_NOME = _x_after_label('NOME COMPLETO:')
            X_ESCOLA = _x_after_label('ESCOLA:')
            X_TURMA = _x_after_label('TURMA:')
            X_TURNO = _x_after_label('TURNO:')
            
            # COORDENADAS Y (validadas das provas físicas)
            Y_PDF_NAME = 780.16      # Baseline do NOME COMPLETO (linha 2)
            Y_PDF_SCHOOL = 744.31    # Baseline da ESCOLA (linha 5, após ESTADO e MUNICÍPIO)
            Y_PDF_TURMA = 732.36     # Baseline da TURMA (linha 6, 1 linha abaixo de ESCOLA)
            # TURNO é a linha seguinte: mesmo intervalo ESCOLA → TURMA
            Y_PDF_TURNO = Y_PDF_TURMA - (Y_PDF_SCHOOL - Y_PDF_TURMA)
            
            QR_X = 441.46            # Posição X do QR code (canto inferior esquerdo)
            QR_Y = 680.77            # Posição Y do QR code (canto inferior esquerdo)
            QR_SIZE = 90             # Tamanho do QR code (90pt = 120px do CSS)
            TEXT_RIGHT = QR_X - 6    # texto para antes do QR

            def _clip_to_width(text: str, font: str, size: float, max_width: float) -> str:
                text = (text or '').strip()
                if not text or max_width <= 0:
                    return ''
                if stringWidth(text, font, size) <= max_width:
                    return text
                ell = '...'
                if stringWidth(ell, font, size) > max_width:
                    return ''
                trimmed = text
                while trimmed and stringWidth(trimmed + ell, font, size) > max_width:
                    trimmed = trimmed[:-1]
                return (trimmed.rstrip() + ell) if trimmed else ell

            def _fit_school_line(text: str, max_width: float):
                """Uma linha só: reduz a fonte até 5,5 pt e só então corta."""
                text = (text or '').strip()
                if not text:
                    return '', FONT_SIZE
                size = float(FONT_SIZE)
                while True:
                    if max_width > 0 and stringWidth(text, FONT_NAME, size) <= max_width:
                        return text, size
                    if size <= SCHOOL_MIN_SIZE:
                        return _clip_to_width(text, FONT_NAME, SCHOOL_MIN_SIZE, max_width), SCHOOL_MIN_SIZE
                    size = round(size - 0.25, 2)
                    if size < SCHOOL_MIN_SIZE:
                        size = SCHOOL_MIN_SIZE

            # ========================================================================
            # EXTRAIR E FORMATAR DADOS DO ALUNO
            # ========================================================================
            
            # Nome do aluno (NOME COMPLETO) — 7 pt, corta só se for invadir o QR
            student_name = _clip_to_width(
                (student.get('name') or student.get('nome') or '').upper(),
                FONT_NAME,
                FONT_SIZE,
                TEXT_RIGHT - X_NOME,
            )
            
            # Escola: já vem com fallback da turma em _get_complete_student_data
            raw_school = (student.get('school_name') or '').strip()
            if school_name_is_missing(raw_school):
                school_text, school_size = '', FONT_SIZE
            else:
                school_text, school_size = _fit_school_line(
                    raw_school.upper(),
                    TEXT_RIGHT - X_ESCOLA,
                )
            
            # Turma (TURMA) - formato: "SÉRIE - TURMA". O PDF base só tem o rótulo.
            class_name = (student.get('class_name') or student.get('turma') or '').strip()
            grade_name = (student.get('grade_name') or (test_data or {}).get('grade_name') or '').strip()
            
            adap_turma = (student.get('turma_label') or '').strip()
            if adap_turma:
                turma_raw = adap_turma
            elif grade_name and class_name:
                turma_raw = f"{grade_name} - {class_name}"
            elif grade_name:
                turma_raw = grade_name
            else:
                turma_raw = class_name
            turma_display = _clip_to_width(
                turma_raw.upper(),
                FONT_NAME,
                FONT_SIZE,
                TEXT_RIGHT - X_TURMA,
            )
            # Texto do cadastro (Manhã, Tarde, Integral, Noturno). Vazio = não desenha.
            shift_display = (student.get('shift') or '').strip()

            # ========================================================================
            # DESENHAR TEXTOS NO OVERLAY
            # ========================================================================
            
            c.setFont(FONT_NAME, FONT_SIZE)
            c.setFillColor(FONT_COLOR)
            
            if student_name:
                c.setFont(FONT_NAME, FONT_SIZE)
                c.drawString(X_NOME, Y_PDF_NAME, student_name)
            
            if school_text:
                c.setFont(FONT_NAME, school_size)
                c.drawString(X_ESCOLA, Y_PDF_SCHOOL, school_text)
            
            if turma_display:
                c.setFont(FONT_NAME, FONT_SIZE)
                c.drawString(X_TURMA, Y_PDF_TURMA, turma_display)

            if shift_display:
                c.setFont(FONT_NAME, FONT_SIZE)
                c.drawString(X_TURNO, Y_PDF_TURNO, shift_display)

            # ========================================================================
            # GERAR E DESENHAR QR CODE
            # ========================================================================
            
            student_id = str(student.get('id', ''))[:12]
            test_id = str((test_data or {}).get('id', ''))[:12]
            
            # Cartão avulso: 12 primeiros caracteres. Gabarito identifica o cartão.
            qr_metadata = {"student_id": student_id}
            if gabarito_id:
                qr_metadata["gabarito_id"] = str(gabarito_id)[:12]
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
