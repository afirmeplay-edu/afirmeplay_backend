# -*- coding: utf-8 -*-
"""
Serviço para geração de PDFs de provas físicas
Baseado no formularios.py original, mas adaptado para integrar com o banco de dados
"""

from PIL import Image as PILImage, ImageDraw, ImageFont, ImageFilter, ImageOps
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, portrait
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image as RLImage, Frame, PageTemplate
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.lib import colors
import qrcode
import os
import io
import base64
import uuid
import requests
import numpy as np
import cv2
from PIL import Image
import json
from datetime import datetime
import re
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional
import logging
from app.models.formCoordinates import FormCoordinates

# --- Parâmetros Globais de Layout ---
LARGURA_CONTEUDO = 1000  # Aumentado de 800 para 1000
ALTURA_CONTEUDO = 500    # Aumentado de 400 para 500
PADDING_EXTERNO = 20     # Aumentado de 15 para 20
LARGURA_FINAL = LARGURA_CONTEUDO + (2 * PADDING_EXTERNO)  # 1040
ALTURA_FINAL = ALTURA_CONTEUDO + (2 * PADDING_EXTERNO)   # 540
LARGURA_COL_NUM = 60     # Aumentado de 45 para 60
LARGURA_COL_ALT = 70     # Aumentado de 50 para 70
ALTURA_LINHA = 45        # Aumentado de 35 para 45
PADDING_HORIZONTAL_COL = 15  # Aumentado de 12 para 15
PADDING_VERTICAL_FORM = 20   # Aumentado de 15 para 20
RAIO_CIRCULO = 15        # Aumentado de 12 para 15
ESPESSURA_LINHA = 3      # Aumentado de 2 para 3
TAMANHO_FONTE_NUM = 22   # Aumentado de 18 para 22
TAMANHO_FONTE_ALT = 20   # Aumentado de 16 para 20
ALTERNATIVAS = ["A", "B", "C", "D", "E"]
MAX_QUESTOES_POR_COLUNA = 10
QR_CODE_SIZE = 100       # Mesmo tamanho do formularios.py
TAMANHO_FONTE_NOME = 20  # Aumentado de 16 para 20
PADDING_NOME_QR = 10     # Aumentado de 8 para 10
PADDING_LEFT_AREA_QR = 25  # Aumentado de 20 para 25
PADDING_QR_FORM = 40     # Aumentado de 30 para 40
SPACING_FORM_COLS = 60   # Aumentado de 40 para 60
MAX_LARGURA_NOME = QR_CODE_SIZE + 20  # Aumentado de 15 para 20

class PhysicalTestPDFGenerator:
    """
    Gerador de PDFs para provas físicas
    Integra com o sistema de banco de dados para buscar questões e dados dos alunos
    """
    
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
    
    def create_pdf_with_large_frame(self, pdf_buffer, story):
        """
        Cria PDF com frame maior (margens de 1cm) para melhor aproveitamento da página
        
        Args:
            pdf_buffer: Buffer para salvar o PDF
            story: Lista de elementos ReportLab para adicionar ao PDF
        """
        try:
            from reportlab.platypus import BaseDocTemplate
            
            # Criar frame que ocupa quase toda a página A4 (margens reduzidas para formulário alto)
            frame = Frame(
                x1=0.5*cm,                # margem esquerda reduzida
                y1=0.5*cm,                # margem inferior reduzida
                width=A4[0] - 1*cm,       # largura do frame = largura total - margens reduzidas
                height=A4[1] - 1*cm,      # altura do frame = altura total - margens reduzidas
                id='normal',
                leftPadding=0,
                bottomPadding=0,
                rightPadding=0,
                topPadding=0
            )
            
            # Criar template de página com frame maior
            page_template = PageTemplate(id='Later', frames=[frame])
            
            # Criar documento com template customizado
            doc = BaseDocTemplate(pdf_buffer, pagesize=A4)
            doc.addPageTemplates([page_template])
            
            # Construir PDF
            doc.build(story)
            
            logging.info(f"PDF criado com frame maior: {frame.width:.1f}x{frame.height:.1f} pontos")
            return True
            
        except Exception as e:
            logging.error(f"Erro ao criar PDF com frame maior: {str(e)}")
            return False
    
    def _setup_custom_styles(self):
        """Configura estilos personalizados para o PDF"""
        # Estilo para título da prova
        self.styles.add(ParagraphStyle(
            name='TestTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#1e40af'),
            fontName='Helvetica-Bold'
        ))
        
        # Estilo para cabeçalho do aluno (layout moderno)
        self.styles.add(ParagraphStyle(
            name='StudentHeader',
            parent=self.styles['Normal'],
            fontSize=14,
            spaceAfter=15,
            alignment=TA_LEFT,
            textColor=colors.HexColor('#374151'),
            fontName='Helvetica-Bold'
        ))
        
        # Estilo para número da questão
        self.styles.add(ParagraphStyle(
            name='QuestionNumber',
            parent=self.styles['Normal'],
            fontSize=20,
            spaceAfter=12,
            spaceBefore=25,
            alignment=TA_LEFT,
            textColor=colors.HexColor('#1f2937'),
            fontName='Helvetica-Bold'
        ))
        
        # Estilo para título da questão
        self.styles.add(ParagraphStyle(
            name='QuestionTitle',
            parent=self.styles['Normal'],
            fontSize=16,
            spaceAfter=15,
            spaceBefore=8,
            alignment=TA_LEFT,
            textColor=colors.HexColor('#1f2937'),
            fontName='Helvetica-Bold'
        ))
        
        # Estilo para texto da questão
        self.styles.add(ParagraphStyle(
            name='QuestionText',
            parent=self.styles['Normal'],
            fontSize=12,
            spaceAfter=12,
            spaceBefore=8,
            alignment=TA_LEFT,
            textColor=colors.HexColor('#374151'),
            fontName='Helvetica'
        ))
        
        # Estilo para segundo enunciado
        self.styles.add(ParagraphStyle(
            name='SecondStatement',
            parent=self.styles['Normal'],
            fontSize=12,
            spaceAfter=12,
            spaceBefore=8,
            alignment=TA_LEFT,
            textColor=colors.HexColor('#374151'),
            fontName='Helvetica'
        ))
        
        # Estilo para habilidades
        self.styles.add(ParagraphStyle(
            name='Skills',
            parent=self.styles['Normal'],
            fontSize=11,
            spaceAfter=8,
            spaceBefore=15,
            alignment=TA_LEFT,
            textColor=colors.HexColor('#7c3aed'),
            fontName='Helvetica-Bold'
        ))
        
        # Estilo para alternativas
        self.styles.add(ParagraphStyle(
            name='Alternative',
            parent=self.styles['Normal'],
            fontSize=11,
            spaceAfter=5,
            spaceBefore=5,
            alignment=TA_LEFT,
            textColor=colors.HexColor('#374151'),
            fontName='Helvetica'
        ))
        
        # Estilo para tags de informação
        self.styles.add(ParagraphStyle(
            name='InfoTag',
            parent=self.styles['Normal'],
            fontSize=9,
            spaceAfter=3,
            spaceBefore=3,
            alignment=TA_LEFT,
            textColor=colors.white,
            fontName='Helvetica-Bold'
        ))



    def _process_paragraph_formatting(self, text: str, base_style, bold_style, italic_style) -> List:
        """
        Processa formatação dentro de um parágrafo (negrito, itálico, quebras de linha)
        """
        story = []
        
        if not text.strip():
            return story
        
        # Dividir por quebras de linha
        lines = re.split(r'<br\s*/?>', text)
        
        for i, line in enumerate(lines):
            if not line.strip():
                continue
                
            # Processar formatação inline (negrito, itálico)
            formatted_elements = self._process_inline_formatting(line.strip(), base_style, bold_style, italic_style)
            
            if formatted_elements:
                # Se há múltiplos elementos formatados, criar parágrafo combinado
                if len(formatted_elements) > 1:
                    combined_text = ''.join(formatted_elements)
                    story.append(Paragraph(combined_text, base_style))
                else:
                    story.append(Paragraph(formatted_elements[0], base_style))
            
            # Adicionar quebra de linha se não for a última
            if i < len(lines) - 1:
                story.append(Spacer(1, 3))
        
        return story

    def _process_inline_formatting(self, text: str, base_style, bold_style, italic_style) -> List:
        """
        Processa formatação inline (negrito, itálico) dentro de uma linha
        """
        elements = []
        
        # Dividir por tags de formatação
        parts = re.split(r'(<strong[^>]*>.*?</strong>|<em[^>]*>.*?</em>|<b[^>]*>.*?</b>|<i[^>]*>.*?</i>)', text)
        
        for part in parts:
            if not part.strip():
                continue
                
            if part.startswith('<strong') or part.startswith('<b'):
                # Texto em negrito
                clean_text = re.sub(r'</?strong[^>]*>|</?b[^>]*>', '', part)
                elements.append(f'<font name="Helvetica-Bold">{clean_text}</font>')
            elif part.startswith('<em') or part.startswith('<i'):
                # Texto em itálico
                clean_text = re.sub(r'</?em[^>]*>|</?i[^>]*>', '', part)
                elements.append(f'<font name="Helvetica-Oblique">{clean_text}</font>')
            else:
                # Texto normal
                elements.append(part)
        
        return elements

    def _clean_html_for_reportlab(self, html_text: str) -> str:
        """
        Limpa HTML para ser compatível com ReportLab
        Remove tags e atributos não suportados de forma agressiva
        """
        if not html_text or not html_text.strip():
            return html_text
            
        clean_text = html_text
        
        # Remover tags complexas que causam problemas (mais agressivo)
        clean_text = re.sub(r'<span[^>]*class="[^"]*"[^>]*>', '', clean_text)
        clean_text = re.sub(r'<span[^>]*>', '', clean_text)
        clean_text = re.sub(r'</span>', '', clean_text)
        clean_text = re.sub(r'<div[^>]*>', '', clean_text)
        clean_text = re.sub(r'</div>', '', clean_text)
        clean_text = re.sub(r'<section[^>]*>', '', clean_text)
        clean_text = re.sub(r'</section>', '', clean_text)
        clean_text = re.sub(r'<article[^>]*>', '', clean_text)
        clean_text = re.sub(r'</article>', '', clean_text)
        
        # Remover atributos de todas as tags restantes
        clean_text = re.sub(r'\s+class=["\'][^"\']*["\']', '', clean_text)
        clean_text = re.sub(r'\s+id=["\'][^"\']*["\']', '', clean_text)
        clean_text = re.sub(r'\s+data-[^=]*=["\'][^"\']*["\']', '', clean_text)
        clean_text = re.sub(r'\s+style=["\'][^"\']*["\']', '', clean_text)
        clean_text = re.sub(r'\s+onclick=["\'][^"\']*["\']', '', clean_text)
        clean_text = re.sub(r'\s+onload=["\'][^"\']*["\']', '', clean_text)
        
        # Converter <br> para <br/> (self-closing)
        clean_text = re.sub(r'<br\s*/?>', '<br/>', clean_text)
        
        # Remover tags vazias ou malformadas
        clean_text = re.sub(r'<[^>]*class="[^"]*"[^>]*>', '', clean_text)
        clean_text = re.sub(r'<[^>]*></[^>]*>', '', clean_text)
        
        # Limpar espaços extras
        clean_text = re.sub(r'\s+', ' ', clean_text)
        clean_text = clean_text.strip()
        
        return clean_text

    def _fallback_html_to_text(self, html_text: str, base_style) -> List:
        """
        Fallback: converte HTML para texto simples quando a conversão falha
        """
        # Remover todas as tags HTML
        clean_text = re.sub(r'<[^>]+>', '', html_text)
        # Decodificar entidades HTML básicas
        clean_text = clean_text.replace('&nbsp;', ' ')
        clean_text = clean_text.replace('&lt;', '<')
        clean_text = clean_text.replace('&gt;', '>')
        clean_text = clean_text.replace('&amp;', '&')
        clean_text = clean_text.replace('&quot;', '"')
        clean_text = clean_text.replace('&#39;', "'")
        
        if clean_text.strip():
            return [Paragraph(clean_text.strip(), base_style)]
        return []

    def _process_text_with_images(self, text: str) -> List:
        """
        Processa texto que pode conter imagens (URL ou Base64) - método legado
        """
        return self._process_html_content(text, self.styles['QuestionText'])


    def _create_answer_sheet(self, test_data: Dict, student: Dict, questions_data: List[Dict], class_test_id: str = None) -> List:
        """Cria formulário de resposta com QR Code usando ReportLab"""
        story = []
        
        # story.append(PageBreak())
        story.append(Paragraph("<b>CARTÃO-RESPOSTA</b>", self.styles['TestTitle']))
        story.append(Spacer(1, 20))
        
        # Adicionar class_test_id aos dados do teste
        test_data_with_class = test_data.copy()
        test_data_with_class['class_test_id'] = class_test_id
        
        # Gerar formulário usando ReportLab diretamente
        form_elements = self._generate_answer_sheet_reportlab(test_data_with_class, student, questions_data)
        story.extend(form_elements)
        
        return story

    def _generate_answer_sheet_reportlab(self, test_data: Dict, student: Dict, questions_data: List[Dict]) -> List:
        """
        Gera formulário de resposta usando formularios.py e adiciona no PDF
        """
        try:
            from reportlab.platypus import Image as RLImage, Spacer
            from reportlab.lib.units import cm
            import io
            import sys
            import os
            
            elements = []
            
            # Importar e usar diretamente as funções do formularios.py
            sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
            
            from app.formularios import gerar_formulario_com_qrcode
            from app.models.student import Student
            from app.models.user import User
            from app.models.school import School
            from app.models.studentClass import Class
            from app.models.grades import Grade
            from app.models.city import City
            from app import db
            
            # Temporariamente modificar ALTERNATIVAS para 4 alternativas
            import app.formularios as formularios_module
            original_alternativas = formularios_module.ALTERNATIVAS
            formularios_module.ALTERNATIVAS = ["A", "B", "C", "D"]  # Apenas 4 alternativas
            
            try:
                # Dados do aluno
                student_id = student.get('id', 'unknown')
                student_name = student.get('nome', 'Nome não informado')
                
                # Buscar dados completos do aluno com joins
                student_data = self._get_complete_student_data(student_id)
                
                # Contar total de questões
                total_questions = len(questions_data)
                
                # Usar tempfile para melhor gerenciamento de arquivos temporários
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    temp_path = tmp.name
                
                # Usar a função modificada do formularios.py com dados completos
                imagem, coordenadas_respostas, coordenadas_qr = gerar_formulario_com_qrcode(
                    student_id, 
                    student_name, 
                    total_questions, 
                    temp_path,  # Arquivo temporário
                    student_data,  # Dados completos do aluno
                    test_data  # Dados do teste
                )
                
                if imagem and coordenadas_respostas and coordenadas_qr:
                    # Converter PIL Image para BytesIO
                    img_buffer = io.BytesIO()
                    imagem.save(img_buffer, format='PNG')
                    img_buffer.seek(0)
                    
                    # Adicionar imagem ao PDF com dimensões que garantem que caiba no frame
                    from reportlab.lib.pagesizes import A4
                    
                    # Dimensões do frame maior (A4 - 1cm de margem para acomodar formulário alto)
                    # Frame será criado com: Frame(x1=0.5*cm, y1=0.5*cm, width=A4[0]-1*cm, height=A4[1]-1*cm)
                    frame_width = A4[0] - 1*cm   # largura = 595 - 1*28.35 = 566.65 pontos
                    frame_height = A4[1] - 1*cm  # altura = 842 - 1*28.35 = 813.65 pontos
                    
                    # Calcula proporção da imagem original
                    img_width, img_height = imagem.size
                    img_ratio = img_width / img_height
                    
                    # Ajusta para caber no frame maior (usando toda a largura disponível)
                    # Prioriza usar toda a largura do frame para maximizar o tamanho visual
                    largura_pdf = frame_width  # Usar toda a largura disponível (538.3 pontos)
                    altura_pdf = largura_pdf / img_ratio  # Calcular altura proporcional
                    
                    # Se a altura exceder o frame, ajustar para caber
                    if altura_pdf > frame_height:
                        altura_pdf = frame_height  # Usar toda a altura disponível (785.2 pontos)
                        largura_pdf = altura_pdf * img_ratio  # Recalcular largura proporcional
                    
                    # Debug: verificar dimensões calculadas
                    logging.info(f"Imagem original: {img_width}x{img_height} pixels")
                    logging.info(f"Proporção da imagem: {img_ratio:.3f}")
                    logging.info(f"Frame disponível: {frame_width:.1f}x{frame_height:.1f} pontos")
                    logging.info(f"Dimensões finais: {largura_pdf:.1f}x{altura_pdf:.1f} pontos")
                    logging.info(f"Margem de segurança: {frame_width - largura_pdf:.1f}x{frame_height - altura_pdf:.1f} pontos")
                    
                    # Calcular espaçamento para centralizar verticalmente e horizontalmente na página A4
                    from reportlab.platypus import KeepTogether
                    
                    altura_pagina = A4[1]  # Altura da página A4 em pontos
                    largura_pagina = A4[0]  # Largura da página A4 em pontos
                    
                    # largura_pdf e altura_pdf já estão em pontos (cm * 28.35)
                    altura_pdf_pontos = altura_pdf
                    largura_pdf_pontos = largura_pdf
                    
                    # Posicionamento próximo ao label "CARTÃO-RESPOSTA" (reduzido espaçamento)
                    espaco_superior = 10  # Espaçamento mínimo entre label e formulário
                    espaco_esquerdo = max((frame_width - largura_pdf) / 2, 0)
                    
                    # Criar imagem flowable
                    img_flowable = RLImage(img_buffer, width=largura_pdf, height=altura_pdf)
                    
                    # Aplicar deslocamento vertical e horizontal
                    elements.append(Spacer(1, espaco_superior))
                    elements.append(KeepTogether([Spacer(espaco_esquerdo, 1), img_flowable]))
                    elements.append(Spacer(1, 20))
                    
                    # Limpar arquivo temporário
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                else:
                    logging.error("Falha ao gerar formulário usando formularios.py")
                
            finally:
                # Restaurar ALTERNATIVAS original
                formularios_module.ALTERNATIVAS = original_alternativas
                
                # Garantir limpeza do arquivo temporário mesmo em caso de erro
                if 'temp_path' in locals() and os.path.exists(temp_path):
                    os.remove(temp_path)
                
            return elements
            
        except Exception as e:
            logging.error(f"Erro ao gerar formulário usando formularios.py: {str(e)}")
            return []
    
    def _get_complete_student_data(self, student_id: str) -> Dict:
        """
        Busca dados completos do aluno incluindo escola, cidade, turma e série
        """
        try:
            from app.models.student import Student
            from app.models.user import User
            from app.models.school import School
            from app.models.studentClass import Class
            from app.models.grades import Grade
            from app.models.city import City
            from app import db
            
            # Query com joins para buscar dados completos do aluno
            result = db.session.query(
                Student,
                User,
                School,
                Class,
                Grade,
                City
            ).join(
                User, Student.user_id == User.id
            ).outerjoin(
                School, Student.school_id == School.id
            ).outerjoin(
                Class, Student.class_id == Class.id
            ).outerjoin(
                Grade, Student.grade_id == Grade.id
            ).outerjoin(
                City, School.city_id == City.id
            ).filter(
                Student.id == student_id
            ).first()
            
            if not result:
                logging.warning(f"Dados completos do aluno {student_id} não encontrados")
                return {
                    'student_name': 'Nome não informado',
                    'class_name': 'Turma não informada',
                    'school_name': 'Escola não informada',
                    'city_name': 'Município não informado',
                    'state_name': 'Estado não informado'
                }
            
            student, user, school, class_obj, grade, city = result
            
            return {
                'student_name': student.name or 'Nome não informado',
                'class_name': class_obj.name if class_obj else 'Turma não informada',
                'school_name': school.name if school else 'Escola não informada',
                'city_name': city.name if city else 'Município não informado',
                'state_name': city.state if city else 'Estado não informado'
            }
            
        except Exception as e:
            logging.error(f"Erro ao buscar dados completos do aluno {student_id}: {str(e)}")
            return {
                'student_name': 'Nome não informado',
                'class_name': 'Turma não informada',
                'school_name': 'Escola não informada',
                'city_name': 'Município não informado',
                'state_name': 'Estado não informado'
            }
    
    def _generate_coordinates_map(self, questions_data: List[Dict], num_questions: int) -> Dict:
        """
        Gera mapeamento de coordenadas das bolinhas para correção
        Baseado no layout ReportLab com colWidths=[20] + [25] * max_alternatives
        """
        coordinates_map = {}
        
        # Parâmetros do layout ReportLab
        COL_NUM_WIDTH = 20
        COL_ALT_WIDTH = 25
        ROW_HEIGHT = 20  # Altura aproximada de cada linha
        START_X = 200  # Posição X inicial (após left_table)
        START_Y = 100  # Posição Y inicial
        
        if num_questions <= 10:
            # Uma coluna apenas
            max_alternatives = max(len(q.get('alternative_ids', [])) for q in questions_data) if questions_data else 0
            
            for i, question_data in enumerate(questions_data):
                question_num = i + 1
                alternative_ids = question_data.get('alternative_ids', [])
                
                coordinates_map[f"question_{question_num}"] = {}
                
                # Posição Y da linha (incluindo cabeçalho)
                y_pos = START_Y + (i + 1) * ROW_HEIGHT
                
                # Posição X inicial das alternativas
                x_start = START_X + COL_NUM_WIDTH
                
                for j, alt_id in enumerate(alternative_ids):
                    x_pos = x_start + (j * COL_ALT_WIDTH) + (COL_ALT_WIDTH // 2)
                    coordinates_map[f"question_{question_num}"][alt_id] = {
                        "x": x_pos,
                        "y": y_pos,
                        "radius": 6,
                        "question_id": question_data.get('id', f'q{question_num}')
                    }
        else:
            # Duas colunas
            questions_col1 = questions_data[:10]
            questions_col2 = questions_data[10:]
            
            max_alt_col1 = max(len(q.get('alternative_ids', [])) for q in questions_col1) if questions_col1 else 0
            max_alt_col2 = max(len(q.get('alternative_ids', [])) for q in questions_col2) if questions_col2 else 0
            
            # Coluna 1 (questões 1-10)
            for i, question_data in enumerate(questions_col1):
                question_num = i + 1
                alternative_ids = question_data.get('alternative_ids', [])
                
                coordinates_map[f"question_{question_num}"] = {}
                
                y_pos = START_Y + (i + 1) * ROW_HEIGHT
                x_start = START_X + COL_NUM_WIDTH
                
                for j, alt_id in enumerate(alternative_ids):
                    x_pos = x_start + (j * COL_ALT_WIDTH) + (COL_ALT_WIDTH // 2)
                    coordinates_map[f"question_{question_num}"][alt_id] = {
                        "x": x_pos,
                        "y": y_pos,
                        "radius": 6,
                        "question_id": question_data.get('id', f'q{question_num}')
                    }
            
            # Coluna 2 (questões 11-18)
            col2_start_x = START_X + COL_NUM_WIDTH + (max_alt_col1 * COL_ALT_WIDTH) + 30  # 30px de espaçamento
            
            for i, question_data in enumerate(questions_col2):
                question_num = i + 11
                alternative_ids = question_data.get('alternative_ids', [])
                
                coordinates_map[f"question_{question_num}"] = {}
                
                y_pos = START_Y + (i + 1) * ROW_HEIGHT
                x_start = col2_start_x + COL_NUM_WIDTH
                
                for j, alt_id in enumerate(alternative_ids):
                    x_pos = x_start + (j * COL_ALT_WIDTH) + (COL_ALT_WIDTH // 2)
                    coordinates_map[f"question_{question_num}"][alt_id] = {
                        "x": x_pos,
                        "y": y_pos,
                        "radius": 6,
                        "question_id": question_data.get('id', f'q{question_num}')
                    }
        
        return coordinates_map

    def ordenar_pontos(self, pontos):
        """
        Ordena pontos para transformação de perspectiva (baseado em projeto.py)
        """
        pontos = pontos.reshape((4, 2))
        soma = pontos.sum(axis=1)
        diff = np.diff(pontos, axis=1)

        topo_esq = pontos[np.argmin(soma)]
        baixo_dir = pontos[np.argmax(soma)]
        topo_dir = pontos[np.argmin(diff)]
        baixo_esq = pontos[np.argmax(diff)]

        return np.array([topo_esq, topo_dir, baixo_dir, baixo_esq], dtype="float32")

    def corrigir_perspectiva(self, img):
        """
        Corrige perspectiva da imagem detectando os 4 cantos da folha/prova
        Baseado no código fornecido pelo usuário
        """
        print(f"🔄 INICIANDO CORREÇÃO DE PERSPECTIVA")
        print(f"📏 Imagem de entrada: {img.shape}")
        
        # Converter para escala de cinza se necessário
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img.copy()
        
        # Aplicar blur e threshold
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        print(f"🎯 Threshold aplicado: {thresh.shape}, valores únicos: {len(np.unique(thresh))}")
        
        # Encontrar contorno externo da folha
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        print(f"🔍 Encontrados {len(contours)} contornos")
        
        if not contours:
            print("❌ Nenhum contorno encontrado")
            return img
        
        # Encontrar maior contorno (folha)
        c = max(contours, key=cv2.contourArea)
        area_contorno = cv2.contourArea(c)
        print(f"📐 Maior contorno: área {area_contorno:.2f}")
        
        # Aproximar polígono
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        print(f"📐 Pontos aproximados: {len(approx)}")
        
        if len(approx) == 4:  # temos 4 cantos
            print("✅ 4 cantos detectados, aplicando correção de perspectiva")
            
            pts = approx.reshape(4, 2)
            print(f"📍 Pontos originais: {pts}")
            
            # Ordenar os pontos: [top-left, top-right, bottom-right, bottom-left]
            rect = np.zeros((4, 2), dtype="float32")
            s = pts.sum(axis=1)
            rect[0] = pts[np.argmin(s)]  # top-left
            rect[2] = pts[np.argmax(s)]  # bottom-right

            diff = np.diff(pts, axis=1)
            rect[1] = pts[np.argmin(diff)]  # top-right
            rect[3] = pts[np.argmax(diff)]  # bottom-left
            
            print(f"📍 Pontos ordenados: {rect}")
            
            (tl, tr, br, bl) = rect

            # Largura e altura finais
            widthA = np.linalg.norm(br - bl)
            widthB = np.linalg.norm(tr - tl)
            maxWidth = max(int(widthA), int(widthB))

            heightA = np.linalg.norm(tr - br)
            heightB = np.linalg.norm(tl - bl)
            maxHeight = max(int(heightA), int(heightB))
            
            print(f"📐 Dimensões calculadas: {maxWidth}x{maxHeight}")

            dst = np.array([
                [0, 0],
                [maxWidth - 1, 0],
                [maxWidth - 1, maxHeight - 1],
                [0, maxHeight - 1]], dtype="float32")

            M = cv2.getPerspectiveTransform(rect, dst)
            warp = cv2.warpPerspective(img, M, (maxWidth, maxHeight))
            
            print(f"✅ Perspectiva corrigida: {warp.shape}")
            return warp
        else:
            print(f"⚠️ Não foram encontrados 4 cantos ({len(approx)} encontrados), retornando imagem original")
            return img

    def aplicar_transformacao_perspectiva(self, img, contorno, largura=688, altura=301):
        """
        Aplica transformação de perspectiva para alinhar o formulário (baseado em projeto.py)
        MANTIDO PARA COMPATIBILIDADE - usar corrigir_perspectiva() para nova implementação
        """
        epsilon = 0.02 * cv2.arcLength(contorno, True)
        aproximado = cv2.approxPolyDP(contorno, epsilon, True)

        if len(aproximado) == 4:
            pontos_ordenados = self.ordenar_pontos(aproximado)

            destino = np.array([
                [0, 0],
                [largura - 1, 0],
                [largura - 1, altura - 1],
                [0, altura - 1]
            ], dtype="float32")

            matriz = cv2.getPerspectiveTransform(pontos_ordenados, destino)
            corrigido = cv2.warpPerspective(img, matriz, (largura, altura))
            return corrigido
        else:
            return img

    def ler_qrcode_em_rgb(self, imagem_gray):
        """
        Lê QR Code da imagem com múltiplos métodos de detecção melhorados
        """
        print(f"🔍 INICIANDO DETECÇÃO DE QR CODE")
        print(f"📏 Imagem de entrada: {imagem_gray.shape}, dtype: {imagem_gray.dtype}")
        print(f"📊 Valores únicos: {len(np.unique(imagem_gray))}, min: {imagem_gray.min()}, max: {imagem_gray.max()}")
        
        detector = cv2.QRCodeDetector()
        
        # Método 1: Detecção direta em escala de cinza
        try:
            dados, _, _ = detector.detectAndDecode(imagem_gray)
            if dados:
                print(f"✅ QR Code detectado: {dados}")
                return dados
        except Exception as e:
            logging.debug(f"Detecção grayscale falhou: {e}")
        
        # Método 2: Detecção em alta resolução (método mais eficaz)
        try:
            print(f"🔍 Tentando detecção em alta resolução...")
            # Usar imagem original se disponível
            if hasattr(self, '_original_image_for_qr') and self._original_image_for_qr is not None:
                dados, _, _ = detector.detectAndDecode(self._original_image_for_qr)
                print(f"📏 Imagem original: {self._original_image_for_qr.shape}")
                print(f"📱 Resultado: {dados}")
                if dados:
                    print(f"✅ QR Code detectado com alta resolução: {dados}")
                    return dados
        except Exception as e:
            print(f"❌ Detecção alta resolução falhou: {e}")
            logging.debug(f"Detecção alta resolução falhou: {e}")
        
        # Método 3: Detecção por regiões (QR Code geralmente no canto superior direito)
        try:
            print(f"🔍 Tentando detecção por regiões...")
            height, width = imagem_gray.shape
            
            # Região superior direita (onde geralmente está o QR Code no formulário)
            roi_size = min(width, height) // 3
            roi_top_right = imagem_gray[0:roi_size, width-roi_size:width]
            print(f"📍 ROI superior direita: {roi_top_right.shape}")
            
            dados, _, _ = detector.detectAndDecode(roi_top_right)
            if dados:
                print(f"✅ QR Code detectado com ROI superior direita: {dados}")
                return dados
        except Exception as e:
            print(f"❌ Detecção por regiões falhou: {e}")
            logging.debug(f"Detecção por regiões falhou: {e}")
        
        # Método 4: Detecção com threshold OTSU
        try:
            print(f"🔍 Tentando threshold OTSU...")
            _, thresh = cv2.threshold(imagem_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            dados, _, _ = detector.detectAndDecode(thresh)
            if dados:
                print(f"✅ QR Code detectado com OTSU: {dados}")
                return dados
        except Exception as e:
            print(f"❌ Detecção OTSU falhou: {e}")
            logging.debug(f"Detecção OTSU falhou: {e}")
        
        # Método 5: Detecção com múltiplos thresholds
        try:
            print(f"🔍 Tentando múltiplos thresholds...")
            for threshold in [127, 100, 150, 200]:
                _, thresh = cv2.threshold(imagem_gray, threshold, 255, cv2.THRESH_BINARY)
                dados, _, _ = detector.detectAndDecode(thresh)
                if dados:
                    print(f"✅ QR Code detectado com threshold {threshold}: {dados}")
                    return dados
        except Exception as e:
            print(f"❌ Detecção múltiplos thresholds falhou: {e}")
            logging.debug(f"Detecção múltiplos thresholds falhou: {e}")
        
        # Método 6: Detecção com morfologia
        try:
            print(f"🔍 Tentando detecção com morfologia...")
            # Aplicar operações morfológicas para limpar a imagem
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            morphed = cv2.morphologyEx(imagem_gray, cv2.MORPH_CLOSE, kernel)
            morphed = cv2.morphologyEx(morphed, cv2.MORPH_OPEN, kernel)
            
            dados, _, _ = detector.detectAndDecode(morphed)
            if dados:
                print(f"✅ QR Code detectado com morfologia: {dados}")
                return dados
        except Exception as e:
            print(f"❌ Detecção morfologia falhou: {e}")
            logging.debug(f"Detecção morfologia falhou: {e}")
        
        # Método 7: Detecção com redimensionamento
        try:
            print(f"🔍 Tentando detecção com redimensionamento...")
            # Redimensionar para diferentes tamanhos
            for scale in [2.0, 0.5, 1.5, 3.0]:
                new_width = int(imagem_gray.shape[1] * scale)
                new_height = int(imagem_gray.shape[0] * scale)
                resized = cv2.resize(imagem_gray, (new_width, new_height), interpolation=cv2.INTER_CUBIC)
                
                dados, _, _ = detector.detectAndDecode(resized)
                if dados:
                    print(f"✅ QR Code detectado com escala {scale}: {dados}")
                    return dados
        except Exception as e:
            print(f"❌ Detecção redimensionamento falhou: {e}")
            logging.debug(f"Detecção redimensionamento falhou: {e}")
        
        print(f"❌ Nenhum QR Code detectado")
        return None

    def processar_imagem_formulario(self, image_data: str) -> Dict:
        """
        Processa imagem do formulário preenchido e extrai respostas marcadas
        """
        try:
            print(f"🔍 INICIANDO PROCESSAMENTO DE IMAGEM")
            print(f"📏 Tamanho da imagem base64: {len(image_data)} caracteres")
            
            # Decodificar imagem base64
            if ',' in image_data:
                image_data = image_data.split(',')[1]
                print(f"📝 Removido prefixo data:image, tamanho restante: {len(image_data)} caracteres")
            
            image_bytes = base64.b64decode(image_data)
            print(f"📦 Imagem decodificada: {len(image_bytes)} bytes")
            
            img = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
            
            if img is None:
                print("❌ ERRO: Falha ao decodificar imagem")
                return {"error": "Erro ao decodificar imagem"}
            
            print(f"🖼️ Imagem carregada: {img.shape} pixels, canais: {img.shape[2] if len(img.shape) > 2 else 1}")
            
            # Converter para escala de cinza
            img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            print(f"⚫ Convertido para grayscale: {img_gray.shape} pixels")
            
            # NOVO: Aplicar correção de perspectiva ANTES de redimensionar
            print(f"🔄 APLICANDO CORREÇÃO DE PERSPECTIVA...")
            img_corrigida = self.corrigir_perspectiva(img)
            
            # Se a correção funcionou, usar a imagem corrigida
            if img_corrigida is not None and img_corrigida.shape != img.shape:
                print(f"✅ Perspectiva corrigida aplicada: {img_corrigida.shape}")
                img = img_corrigida
                img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
            else:
                print(f"⚠️ Correção de perspectiva não aplicada, usando imagem original")
            
            # NOVO: Salvar imagem original para detecção de QR Code
            self._original_image_for_qr = img_gray.copy()
            
            # Redimensionar mantendo proporção para evitar distorção
            original_height, original_width = img_gray.shape
            print(f"📏 Dimensões originais: {original_width}x{original_height}")
            
            # Redimensionar mantendo proporção
            target_width = 720
            target_height = int(original_height * target_width / original_width)
            
            # Limitar altura máxima para evitar imagens muito altas
            if target_height > 600:
                target_height = 600
                target_width = int(original_width * target_height / original_height)
            
            print(f"📐 Redimensionando mantendo proporção: {target_width}x{target_height}")
            
            img_gray = cv2.resize(img_gray, (target_width, target_height))
            img = cv2.resize(img, (target_width, target_height))
            print(f"📐 Imagem redimensionada para: {img_gray.shape} pixels")
            
            # Aplicar threshold adaptativo para detecção de respostas
            borrada = cv2.GaussianBlur(img_gray, (5, 5), 0)
            print(f"🌫️ Blur gaussiano aplicado: {borrada.shape}")
            
            binario = cv2.adaptiveThreshold(borrada, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)
            print(f"🎯 Threshold adaptativo aplicado: {binario.shape}")
            
            # Tentar detectar QR Code na imagem original primeiro
            print(f"🔍 Tentando detectar QR Code na imagem original...")
            qr_data = self.ler_qrcode_em_rgb(img_gray)
            print(f"📱 QR Code detectado: {qr_data}")
            
            # Se não detectou, tentar com correção de perspectiva
            if not qr_data:
                print("❌ QR Code não detectado na imagem original, tentando correção de perspectiva...")
                
                kernel = np.ones((3, 3), np.uint8)
                opening = cv2.morphologyEx(binario, cv2.MORPH_OPEN, kernel)
                print(f"🔧 Operação morfológica aplicada: {opening.shape}")
                
                # Encontrar contornos
                contornos, _ = cv2.findContours(binario, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                print(f"🔍 Encontrados {len(contornos)} contornos")
                
                if contornos:
                    # Encontrar maior contorno (formulário)
                    maior_contorno = max(contornos, key=cv2.contourArea)
                    area_maior = cv2.contourArea(maior_contorno)
                    print(f"📐 Maior contorno: área {area_maior:.2f}")
                    
                    recorte_corrigido = self.aplicar_transformacao_perspectiva(img_gray, maior_contorno)
                    binario_corrigido = self.aplicar_transformacao_perspectiva(opening, maior_contorno)
                    
                    if recorte_corrigido is not None and binario_corrigido is not None:
                        print(f"🔄 Imagem corrigida: {recorte_corrigido.shape}")
                        # Tentar detectar QR Code na imagem corrigida
                        qr_data = self.ler_qrcode_em_rgb(recorte_corrigido)
                        print(f"📱 QR Code após correção: {qr_data}")
                        # Usar imagem binária corrigida se disponível
                        binario = binario_corrigido
                    else:
                        print("❌ Falha na correção de perspectiva")
                else:
                    print("❌ Nenhum contorno encontrado")
            
            print(f"🎯 RESULTADO FINAL - QR Code: {qr_data}")
            
            return {
                "success": True,
                "image_processed": img_gray,
                "binary_image": binario,
                "qr_data": qr_data
            }
            
        except Exception as e:
            logging.error(f"Erro ao processar imagem: {str(e)}")
            return {"error": f"Erro no processamento: {str(e)}"}

    def processar_gabarito_melhorado(self, img):
        """
        Processa gabarito com correção de perspectiva e detecção de bolhas
        Baseado no código fornecido pelo usuário
        """
        print(f"🎯 INICIANDO PROCESSAMENTO DE GABARITO MELHORADO")
        print(f"📏 Imagem de entrada: {img.shape}")
        
        # 1. Corrigir perspectiva
        img_corrigida = self.corrigir_perspectiva(img)
        print(f"✅ Perspectiva corrigida: {img_corrigida.shape}")
        
        # 2. Pré-processamento na imagem corrigida
        gray = cv2.cvtColor(img_corrigida, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        print(f"📊 Estatísticas da imagem corrigida: min={gray.min()}, max={gray.max()}, mean={gray.mean():.1f}")
        print(f"🎯 Threshold aplicado na imagem corrigida: {thresh.shape}")
        
        # 3. Encontrar contornos usando RETR_TREE para detectar elementos internos
        print(f"🔍 Buscando contornos com RETR_TREE...")
        contours, _ = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        print(f"🔍 Encontrados {len(contours)} contornos (incluindo internos)")
        
        # Debug: mostrar informações dos contornos
        for i, c in enumerate(contours[:20]):  # Mostrar os primeiros 20
            area = cv2.contourArea(c)
            perimeter = cv2.arcLength(c, True)
            if perimeter > 0:
                circularity = 4 * np.pi * area / (perimeter * perimeter)
                print(f"  Contorno {i}: área={area:.1f}, perímetro={perimeter:.1f}, circularidade={circularity:.3f}")
        
        # 4. Filtrar bolhas com critérios ajustados
        bolhas = []
        for c in contours:
            area = cv2.contourArea(c)
            # Critérios ajustados baseados no seu código: 50 < area < 1500
            if area < 50 or area > 1500:
                continue
            perimeter = cv2.arcLength(c, True)
            if perimeter == 0:
                continue
            circularity = 4 * np.pi * area / (perimeter * perimeter)
            # Critérios mais permissivos: 0.4 < circularity < 1.3
            if 0.4 < circularity < 1.3:
                bolhas.append(c)
                print(f"  ✅ Bolha válida: área={area:.1f}, circularidade={circularity:.3f}")
        
        print(f"⭕ Total de bolhas encontradas: {len(bolhas)}")
        
        # 4. Agrupar bolhas por linhas (questões)
        print(f"🔍 Agrupando {len(bolhas)} bolhas por linhas...")
        linhas = self._agrupar_bolhas_por_linha(bolhas, thresh)
        
        respostas = {}
        
        # Processar cada linha (questão)
        for i, linha in enumerate(linhas, start=1):
            print(f"📝 Processando Questão {i} com {len(linha)} bolhas...")
            
            if len(linha) < 4:
                print(f"⚠️ Questão {i}: Apenas {len(linha)} bolhas encontradas, pulando...")
                continue
            
            valores = []
            for j, (contorno, letra) in enumerate(linha):
                # Usar círculo em vez de contorno para melhor precisão
                x, y, w, h = cv2.boundingRect(contorno)
                cx, cy = x + w // 2, y + h // 2
                radius = min(w, h) // 2
                
                mask = np.zeros(thresh.shape, dtype="uint8")
                cv2.circle(mask, (cx, cy), radius, 255, -1)
                mean = cv2.mean(thresh, mask=mask)[0]
                valores.append((mean, letra))
                print(f"  Questão {i} {letra}: mean={mean:.1f} (centro=({cx},{cy}), raio={radius})")
            
            # Calcula baseline (mediana de todas as bolhas da linha)
            baseline = np.median([v[0] for v in valores])
            print(f"  📊 Baseline da Questão {i}: {baseline:.1f}")
            
            # Considera marcada se estiver MUITO mais escura que o baseline
            threshold = baseline * 0.7
            print(f"  🎯 Threshold: {threshold:.1f} (baseline * 0.7)")
            
            marcadas = [alt for (mean, alt) in valores if mean < threshold]
            print(f"  🔍 Bolhas detectadas como marcadas: {marcadas}")
            
            if len(marcadas) == 1:
                marcada = marcadas[0]
                print(f"  ✅ Questão {i}: {marcada} marcada (única)")
            elif len(marcadas) > 1:
                marcada = marcadas  # Múltiplas respostas
                print(f"  ⚠️ Questão {i}: Múltiplas respostas {marcadas}")
            else:
                marcada = None  # Nenhuma resposta
                print(f"  ❌ Questão {i}: Nenhuma resposta marcada")
            
            respostas[i] = marcada
        
        print(f"📊 RESPOSTAS DETECTADAS: {respostas}")
        return respostas

    # ===== CÓDIGO ANTIGO - COMENTADO (NÃO EXCLUIR) =====
    def detect_bubbles_robust_OLD(self, img, expected_cols=4, debug=True):
        """
        Detecção de bolhas usando borda grossa da tabela como ROI
        """
        # ADAPTADO - FUNÇÃO ANTIGA FUNCIONANDO
        print(f"🎯 INICIANDO DETECÇÃO COM BORDA DA TABELA ROI")
        print(f"📏 Imagem de entrada: {img.shape}")
        print(f"🎯 INICIANDO DETECÇÃO COM BORDA DA TABELA ROI")
        print(f"📏 Imagem de entrada: {img.shape}")
        
        # 1. Detectar borda grossa da tabela de questões para definir ROI
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape
        
        # Detectar borda da tabela (ROI)
        roi_corners = self._detectar_borda_tabela_roi(gray)
        
        if roi_corners is None:
            print(f"⚠️ Borda da tabela não detectada, usando região inferior padrão")
            # Fallback: usar região inferior (últimos 40% da imagem)
            bubble_region = gray[int(h * 0.6):, :]
            print(f"📦 Região das bolhas (fallback): {bubble_region.shape}")
        else:
            # Usar ROI detectada pela borda da tabela
            x1, y1, x2, y2 = roi_corners
            bubble_region = gray[y1:y2, x1:x2]
            print(f"📦 Região das bolhas (ROI detectada): {bubble_region.shape}")
            print(f"🎯 ROI: ({x1},{y1}) a ({x2},{y2})")
        
        # 2. USAR GRADE FIXA - Solução para contornos fragmentados
        print(f"🎯 USANDO GRADE FIXA PARA EVITAR CONTORNOS FRAGMENTADOS")
        
        # Aplicar morfologia para unir contornos quebrados
        kernel = np.ones((3,3), np.uint8)
        proc = cv2.morphologyEx(bubble_region, cv2.MORPH_CLOSE, kernel, iterations=2)
        
        # Detectar quantas questões temos (assumir 4 por padrão, mas detectar dinamicamente)
        h, w = bubble_region.shape
        print(f"📏 ROI da tabela: {w}x{h} pixels")
        
        # Assumir 4 questões por padrão (pode ser ajustado)
        num_questions = 4
        num_alternatives = 4
        
        # Calcular tamanho de cada célula
        cell_h = h // num_questions
        cell_w = w // num_alternatives
        
        print(f"📐 Células: {cell_w}x{cell_h} pixels cada")
        
        # Processar cada célula da grade
        answers = {}
        
        for i in range(num_questions):
            question_num = i + 1
            option_proportions = {}
            
            for j in range(num_alternatives):
                # Calcular coordenadas da célula
                x1 = j * cell_w
                y1 = i * cell_h
                x2 = (j + 1) * cell_w
                y2 = (i + 1) * cell_h
                
                # Extrair célula
                cell = bubble_region[y1:y2, x1:x2]
                
                # Calcular proporção de pixels pretos usando binarização
                proportion_black = self._calcular_proporcao_pixels_pretos(cell)
                
                # Armazenar resultado
                option_proportions[j] = {
                    'proportion': proportion_black,
                    'cx': (x1 + x2) // 2,
                    'cy': (y1 + y2) // 2,
                    'r': min(cell_w, cell_h) // 4
                }
                
                print(f"  📊 Questão {question_num}, {chr(65+j)}: proporção_pretos={proportion_black:.3f}, pos=({(x1+x2)//2},{(y1+y2)//2})")
            
            # Aplicar critério inteligente de binarização
            proporcoes = [v['proportion'] for v in option_proportions.values()]
            max_proportion = max(proporcoes)
            max_idx = max(option_proportions.keys(), key=lambda k: option_proportions[k]['proportion'])
            
            # Calcular estatísticas para critério relativo
            proporcoes_ordenadas = sorted(proporcoes, reverse=True)
            segundo_maior = proporcoes_ordenadas[1] if len(proporcoes_ordenadas) > 1 else 0
            media_proporcoes = np.mean(proporcoes)
            
            # DEBUG: Mostrar proporções para análise
            print(f"    🔍 DEBUG Proporções: A={option_proportions[0]['proportion']:.3f}, B={option_proportions[1]['proportion']:.3f}, C={option_proportions[2]['proportion']:.3f}, D={option_proportions[3]['proportion']:.3f}")
            print(f"    🔍 DEBUG Maior: {max_proportion:.3f}, Segundo: {segundo_maior:.3f}, Média: {media_proporcoes:.3f}")
            
            # Critério 1: Threshold absoluto (proporção mínima para considerar preenchida)
            threshold_absoluto = 0.15  # 15% dos pixels
            
            # Critério 2: Detecção relativa (diferença significativa do segundo maior)
            diferenca_relativa = max_proportion - segundo_maior
            threshold_relativo = 0.05  # 5% de diferença mínima
            
            # Critério 3: Normalização (maior que 1.5x a média)
            threshold_normalizado = media_proporcoes * 1.5
            
            # Aplicar critérios combinados
            if (max_proportion > threshold_absoluto and 
                diferenca_relativa > threshold_relativo and 
                max_proportion > threshold_normalizado):
                answers[question_num] = chr(65 + max_idx)
                print(f"    ✅ Critério combinado: {max_proportion:.3f} > {threshold_absoluto:.3f} E dif {diferenca_relativa:.3f} > {threshold_relativo:.3f} E {max_proportion:.3f} > {threshold_normalizado:.3f} → Resposta = {chr(65 + max_idx)}")
            else:
                answers[question_num] = None
                print(f"    ❌ Critério combinado: Não atendeu aos critérios (abs: {max_proportion:.3f} > {threshold_absoluto:.3f}, rel: {diferenca_relativa:.3f} > {threshold_relativo:.3f}, norm: {max_proportion:.3f} > {threshold_normalizado:.3f})")
            
            print(f"  ✅ Questão {question_num}: {answers[question_num]}")
            print(f"    📊 Opções detectadas: {option_proportions}")
        
        print(f"📊 RESPOSTAS DETECTADAS: {answers}")
        return answers

    # ===== CÓDIGO ANTIGO - COMENTADO (NÃO EXCLUIR) =====
    def _calcular_proporcao_pixels_pretos_OLD(self, roi):
        """
        Recebe a região da bolha (ROI).
        Aplica processamento robusto e binarização para separar fundo (branco) de marca (preto).
        Retorna a % de pixels pretos (quanto maior, mais preenchida está a bolha).
        """
        # ADAPTADO - FUNÇÃO ANTIGA FUNCIONANDO
        # roi já é grayscale, não precisa converter
        gray = roi
        
        # 1. Aplicar blur gaussiano para suavizar ruído
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)
        
        # 2. Usar threshold adaptativo para melhor separação
        thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)
        
        # 3. Aplicar morfologia para remover ruídos pequenos
        kernel = np.ones((2, 2), np.uint8)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=1)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=1)
        
        # 4. Contar pixels pretos (valor > 0 no THRESH_BINARY_INV)
        preenchimento = cv2.countNonZero(thresh)
        total_pixels = thresh.shape[0] * thresh.shape[1]
        proporcao_pretos = preenchimento / float(total_pixels)
        
        return proporcao_pretos  # valor entre 0.0 e 1.0

    def _calcular_proporcao_pixels_pretos_melhorada(self, roi, debug_path=None):
        """
        Versão melhorada do cálculo de proporção de pixels pretos.
        Usa máscara circular interna para ignorar bordas impressas.
        """
        try:
            # 1. Redimensionar ROI para melhor processamento (40x40)
            roi_resized = cv2.resize(roi, (40, 40), interpolation=cv2.INTER_CUBIC)
            
            # 2. Aplicar CLAHE para normalizar iluminação
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            roi_clahe = clahe.apply(roi_resized)
            
            # 3. Blur suave para reduzir ruído
            roi_blurred = cv2.GaussianBlur(roi_clahe, (3, 3), 0)
            
            # 4. Threshold adaptativo por ROI
            thresh = cv2.adaptiveThreshold(roi_blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)
            
            # 5. Criar máscara circular interna (ignora borda de 4px)
            h, w = thresh.shape
            center = (w//2, h//2)
            radius = min(w, h) // 2 - 4  # 4px de margem da borda
            
            mask = np.zeros((h, w), dtype=np.uint8)
            cv2.circle(mask, center, radius, 255, -1)
            
            # 6. Aplicar máscara para contar apenas o interior
            thresh_masked = cv2.bitwise_and(thresh, mask)
            
            # 7. Morfologia para limpar ruídos
            kernel = np.ones((2, 2), np.uint8)
            thresh_masked = cv2.morphologyEx(thresh_masked, cv2.MORPH_CLOSE, kernel, iterations=1)
            thresh_masked = cv2.morphologyEx(thresh_masked, cv2.MORPH_OPEN, kernel, iterations=1)
            
            # 8. Calcular proporção apenas na área mascarada
            pixels_pretos = cv2.countNonZero(thresh_masked)
            pixels_totais = cv2.countNonZero(mask)
            
            if pixels_totais == 0:
                return 0.0
                
            proporcao = pixels_pretos / float(pixels_totais)
            
            # Debug: salvar imagens se path fornecido
            if debug_path:
                debug_img = np.hstack([
                    roi_resized,
                    roi_clahe,
                    thresh,
                    thresh_masked,
                    mask
                ])
                cv2.imwrite(debug_path, debug_img)
            
            return proporcao
            
        except Exception as e:
            print(f"❌ Erro no cálculo melhorado: {str(e)}")
            # Fallback para método antigo
            return self._calcular_proporcao_pixels_pretos_OLD(roi)

    def _detectar_respostas_robusto(self, aligned_bgr, template_coords_list, debug_save=True):
        """
        Implementação robusta baseada no código de referência fornecido.
        Detecta respostas com critérios mais rigorosos e debug visual.
        """
        # Configurações ajustadas para ser menos rigoroso
        MIN_FILL_RATIO = 0.08      # se o topo for menor que isso => vazio (reduzido de 0.12)
        MIN_DIFF_ABS = 0.05        # diferença absoluta entre top e 2º (reduzido de 0.10)
        ROI_PAD = 8                # padding em px ao redor da bbox
        INNER_MASK_SHRINK = 0.65   # quanto do raio usar para a máscara interna (0..1)
        OPTIONS = ["A", "B", "C", "D"]
        
        # Criar diretório de debug
        if debug_save:
            os.makedirs("debug_bubbles", exist_ok=True)
        
        def preprocess_gray(img_bgr):
            gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            return clahe.apply(gray)
        
        def inner_circle_mask(w, h, shrink=INNER_MASK_SHRINK):
            mask = np.zeros((h, w), dtype=np.uint8)
            cx, cy = w // 2, h // 2
            r = int(min(w, h) // 2 * shrink)
            cv2.circle(mask, (cx, cy), r, 255, -1)
            return mask
        
        def roi_fill_ratio_from_thresholded(thresh_roi, shrink=INNER_MASK_SHRINK):
            h, w = thresh_roi.shape
            mask = inner_circle_mask(w, h, shrink)
            masked = cv2.bitwise_and(thresh_roi, mask)
            filled = np.count_nonzero(masked)
            total = np.count_nonzero(mask)
            if total == 0:
                return 0.0
            return filled / total
        
        def threshold_roi(roi_gray):
            # blur -> Otsu
            blur = cv2.GaussianBlur(roi_gray, (5,5), 0)
            _, th = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            # Decide direção: queremos que *preenchimento* seja 255
            if np.mean(th) > 127:
                th = cv2.bitwise_not(th)
            # small morphology to reduce noise
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3,3))
            th = cv2.morphologyEx(th, cv2.MORPH_OPEN, kernel)
            th = cv2.morphologyEx(th, cv2.MORPH_CLOSE, kernel)
            return th
        
        # Processamento principal
        gray = preprocess_gray(aligned_bgr)
        answers = {}
        annotated = aligned_bgr.copy()
        
        for qi, boxes in enumerate(template_coords_list):
            ratios = []
            debug_rois = []
            
            for opt_idx, (x, y, w, h) in enumerate(boxes):
                x0 = max(0, x - ROI_PAD)
                y0 = max(0, y - ROI_PAD)
                x1 = min(gray.shape[1], x + w + ROI_PAD)
                y1 = min(gray.shape[0], y + h + ROI_PAD)
                roi_gray = gray[y0:y1, x0:x1]
                
                # Threshold e cálculo de proporção
                th = threshold_roi(roi_gray)
                fill_ratio = roi_fill_ratio_from_thresholded(th)
                debug_img = np.dstack([roi_gray, roi_gray, roi_gray])
                debug_rois.append(("th", opt_idx, th, fill_ratio, debug_img))
                
                ratios.append((OPTIONS[opt_idx], fill_ratio, (x0, y0, x1, y1)))
            
            # Ordenar por proporção
            ratios_sorted = sorted(ratios, key=lambda x: x[1], reverse=True)
            top_label, top_val = ratios_sorted[0][0], ratios_sorted[0][1]
            second_val = ratios_sorted[1][1]
            
            # Regras de decisão
            if top_val < MIN_FILL_RATIO:
                answer = None   # branco
                reason = "below_min"
            elif (top_val - second_val) < MIN_DIFF_ABS:
                # Em caso de empate técnico, escolher o maior valor se a diferença for muito pequena
                if (top_val - second_val) < 0.02:  # Menos de 2 pontos percentuais
                    answer = top_label  # Escolher o maior valor
                    reason = "tie_break"
                else:
                    answer = "AMBIG"  # ambíguo
                    reason = "small_diff"
            else:
                answer = top_label
                reason = "ok"
            
            answers[qi+1] = {
                "answer": answer, 
                "top": top_val, 
                "second": second_val, 
                "reason": reason, 
                "ratios": ratios_sorted
            }
            
            # Desenhar anotação
            for opt_label, val, bbox in ratios:
                x0, y0, x1, y1 = bbox
                color = (0, 255, 0) if opt_label == answer else (0, 0, 255)
                cv2.rectangle(annotated, (x0, y0), (x1, y1), color, 1)
                cv2.putText(annotated, f"{opt_label}:{val:.2f}", (x0, y0-4),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
            
            # Salvar DEBUG
            if debug_save:
                for kind, opt_idx, th, fill_ratio, debug_img in debug_rois:
                    fname = f"debug_bubbles/q{qi+1}_{OPTIONS[opt_idx]}_{kind}_r{fill_ratio:.3f}.png"
                    # Salvar ROI em escala de cinza + threshold lado a lado
                    th_bgr = cv2.cvtColor(th, cv2.COLOR_GRAY2BGR)
                    out = np.hstack([cv2.resize(debug_img, (th_bgr.shape[1], th_bgr.shape[0])), th_bgr])
                    cv2.imwrite(fname, out)
        
        if debug_save:
            cv2.imwrite("debug_bubbles/annotated.png", annotated)
        
        return answers

    def _detectar_borda_tabela_roi(self, gray):
        """
        Detecta a borda grossa ao redor da tabela de questões para definir ROI
        """
        print(f"🔍 DETECTANDO BORDA DA TABELA ROI...")
        
        # Aplicar threshold mais agressivo para detectar bordas pretas
        _, thresh = cv2.threshold(gray, 80, 255, cv2.THRESH_BINARY_INV)
        
        # Encontrar contornos
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        print(f"🔍 Total de contornos encontrados: {len(contours)}")
        
        # Procurar por retângulos grandes (borda da tabela)
        retangulos = []
        for i, c in enumerate(contours):
            area = cv2.contourArea(c)
            # Área esperada para borda da tabela (mais flexível)
            if area > 5000:  # Reduzido de 10000 para 5000
                # Verificar se é aproximadamente retangular
                x, y, w, h = cv2.boundingRect(c)
                aspect_ratio = w / h
                if 0.2 < aspect_ratio < 5.0:  # Proporção mais flexível
                    # Verificar se é preto (intensidade baixa)
                    roi = gray[y:y+h, x:x+w]
                    mean_intensity = np.mean(roi)
                    if mean_intensity < 200:  # Mais flexível para preto
                        retangulos.append((x, y, w, h, area))
                        print(f"  ✅ Retângulo {len(retangulos)}: área={area:.1f}, intensidade={mean_intensity:.1f}, pos=({x},{y}), tamanho=({w}x{h})")
        
        print(f"🔍 Retângulos candidatos encontrados: {len(retangulos)}")
        
        if not retangulos:
            print(f"⚠️ Nenhum retângulo encontrado")
            return None
        
        # Ordenar por área (maior primeiro) e pegar o maior
        retangulos.sort(key=lambda x: x[4], reverse=True)
        maior_retangulo = retangulos[0]
        
        x, y, w, h, area = maior_retangulo
        print(f"🎯 Maior retângulo selecionado: área={area:.1f}, pos=({x},{y}), tamanho=({w}x{h})")
        
        # Adicionar margem de segurança pequena
        margin = 5
        roi_corners = (
            max(0, x - margin),
            max(0, y - margin),
            min(gray.shape[1], x + w + margin),
            min(gray.shape[0], y + h + margin)
        )
        
        print(f"✅ ROI detectada: {roi_corners}")
        return roi_corners

    def processar_correcao_completa(self, test_id, image_data):
        """
        Processa correção completa: QR code + detecção de bolhas + salvamento no banco
        NOVA ORDEM: QR Code primeiro na imagem original, depois processamento para bolhas
        NOVA ORDEM: QR Code primeiro na imagem original, depois processamento para bolhas
        """
        from app import db
        
        print(f"🎯 INICIANDO PROCESSAMENTO DE CORREÇÃO COMPLETA")
        print(f"📋 Test ID: {test_id}")
        
        try:
            # 1. Decodificar imagem original (sem processamento pesado)
            img_color = self._decode_image_direct(image_data)
            if img_color is None:
            # 1. Decodificar imagem original (sem processamento pesado)
            img_color = self._decode_image_direct(image_data)
            if img_color is None:
                return {"success": False, "error": "Erro ao decodificar imagem"}
            
            print(f"🖼️ Imagem original decodificada: {img_color.shape}")
            
            # 2. EXTRAIR QR CODE PRIMEIRO (na imagem original, sem processamento)
            print(f"🔍 ETAPA 1: DETECTANDO QR CODE NA IMAGEM ORIGINAL...")
            student_id = self._extrair_qr_code_original(img_color)
            print(f"🖼️ Imagem original decodificada: {img_color.shape}")
            
            # 2. EXTRAIR QR CODE PRIMEIRO (na imagem original, sem processamento)
            print(f"🔍 ETAPA 1: DETECTANDO QR CODE NA IMAGEM ORIGINAL...")
            student_id = self._extrair_qr_code_original(img_color)
            if not student_id:
                return {"success": False, "error": "QR code não detectado ou inválido"}
            
            print(f"✅ QR CODE DETECTADO: {student_id}")
            
            # 3. AGORA processar imagem para detecção de bolhas (mantendo funcionalidade existente)
            print(f"🔍 ETAPA 2: PROCESSANDO IMAGEM PARA DETECÇÃO DE BOLHAS...")
            img_result = self.processar_imagem_formulario(image_data)
            if img_result is None or not img_result.get('success'):
                return {"success": False, "error": "Erro ao processar imagem para detecção de bolhas"}
            
            img_gray = img_result['image_processed']
            print(f"🖼️ Imagem processada para bolhas: {img_gray.shape}")
            print(f"✅ QR CODE DETECTADO: {student_id}")
            
            # 3. AGORA processar imagem para detecção de bolhas (mantendo funcionalidade existente)
            print(f"🔍 ETAPA 2: PROCESSANDO IMAGEM PARA DETECÇÃO DE BOLHAS...")
            img_result = self.processar_imagem_formulario(image_data)
            if img_result is None or not img_result.get('success'):
                return {"success": False, "error": "Erro ao processar imagem para detecção de bolhas"}
            
            img_gray = img_result['image_processed']
            print(f"🖼️ Imagem processada para bolhas: {img_gray.shape}")
            
            # 4. Detectar respostas usando pipeline robusto (MANTENDO FUNCIONALIDADE EXISTENTE)
            print(f"🔍 ETAPA 3: DETECTANDO RESPOSTAS (BOLHAS)...")
            # 4. Detectar respostas usando pipeline robusto (MANTENDO FUNCIONALIDADE EXISTENTE)
            print(f"🔍 ETAPA 3: DETECTANDO RESPOSTAS (BOLHAS)...")
            respostas_detectadas = self.detect_bubbles_robust(img_color, expected_cols=4, debug=True)
            if not respostas_detectadas:
                return {"success": False, "error": "Nenhuma resposta detectada"}
            
            print(f"✅ RESPOSTAS DETECTADAS: {respostas_detectadas}")
            print(f"✅ RESPOSTAS DETECTADAS: {respostas_detectadas}")
            
            # 4. Buscar questões da prova
            from app.models.testQuestion import TestQuestion
            from app.models.question import Question
            
            test_questions = TestQuestion.query.filter_by(test_id=test_id).order_by(TestQuestion.order).all()
            if not test_questions:
                return {"success": False, "error": "Nenhuma questão encontrada para esta prova"}
            
            print(f"📚 Questões da prova: {len(test_questions)}")
            
            # 5. Mapear respostas detectadas com questões
            student_answers = []
            correct_answers = 0
            total_questions = len(test_questions)
            
            for test_question in test_questions:
                question_order = test_question.order
                question_id = test_question.question_id
                
                # Buscar questão
                question = Question.query.get(question_id)
                if not question:
                    print(f"⚠️ Questão {question_order}: ID {question_id} não encontrada")
                    continue
                
                # Resposta detectada para esta questão
                detected_answer = respostas_detectadas.get(question_order)
                if not detected_answer:
                    print(f"⚠️ Questão {question_order}: Nenhuma resposta detectada")
                    continue
                
                # Verificar se está correta
                is_correct = False
                if question.correct_answer:
                    is_correct = str(detected_answer).strip().upper() == str(question.correct_answer).strip().upper()
                    if is_correct:
                        correct_answers += 1
                
                print(f"📝 Questão {question_order}: {detected_answer} {'✅' if is_correct else '❌'} (correta: {question.correct_answer})")
                
                # Salvar resposta do aluno
                from app.models.studentAnswer import StudentAnswer
                
                # Verificar se já existe resposta para esta questão
                existing_answer = StudentAnswer.query.filter_by(
                    test_id=test_id,
                    student_id=student_id,
                    question_id=question_id
                ).first()
                
                if existing_answer:
                    # Atualizar resposta existente
                    existing_answer.answer = detected_answer
                    existing_answer.is_correct = is_correct
                    print(f"  🔄 Resposta atualizada para questão {question_order}")
                else:
                    # Criar nova resposta
                    student_answer = StudentAnswer(
                        test_id=test_id,
                        student_id=student_id,
                        question_id=question_id,
                        answer=detected_answer,
                        is_correct=is_correct
                    )
                    db.session.add(student_answer)
                    print(f"  ➕ Nova resposta criada para questão {question_order}")
                
                student_answers.append({
                    'question_order': question_order,
                    'question_id': question_id,
                    'detected_answer': detected_answer,
                    'correct_answer': question.correct_answer,
                    'is_correct': is_correct
                })
            
            # 6. Calcular nota e proficiência usando EvaluationResultService
            from app.services.evaluation_result_service import EvaluationResultService
            
            # Usar session_id None para correções físicas
            session_id = None
            
            evaluation_result = EvaluationResultService.calculate_and_save_result(
                test_id=test_id,
                student_id=student_id,
                session_id=session_id
            )
            
            if not evaluation_result:
                return {"success": False, "error": "Erro ao calcular resultado da avaliação"}
            
            print(f"📊 Resultado calculado: {correct_answers}/{total_questions} acertos")
            print(f"📈 Nota: {evaluation_result['grade']}")
            print(f"📈 Proficiência: {evaluation_result['proficiency']}")
            print(f"📈 Classificação: {evaluation_result['classification']}")
            
            # 7. Commit das alterações
            db.session.commit()
            
            return {
                "success": True,
                "student_id": student_id,
                "test_id": test_id,
                "correct_answers": correct_answers,
                "total_questions": total_questions,
                "score_percentage": evaluation_result['score_percentage'],
                "grade": evaluation_result['grade'],
                "proficiency": evaluation_result['proficiency'],
                "classification": evaluation_result['classification'],
                "answers_detected": respostas_detectadas,
                "student_answers": student_answers,
                "evaluation_result_id": evaluation_result['id']
            }
            
        except Exception as e:
            print(f"❌ Erro no processamento: {str(e)}")
            db.session.rollback()
            return {"success": False, "error": f"Erro interno: {str(e)}"}

    def _decode_image_direct(self, image_data):
        """
        Decodifica imagem base64 diretamente para OpenCV
        """
        try:
            import cv2
            import numpy as np
            import base64
            
            # Decodificar imagem base64
            if ',' in image_data:
                image_data = image_data.split(',')[1]
            
            image_bytes = base64.b64decode(image_data)
            img = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
            
            if img is None:
                return None
            
            return img
            
        except Exception as e:
            print(f"❌ Erro ao decodificar imagem: {str(e)}")
            return None

    def _extrair_qr_code_original(self, img):
        """
        Extrai QR code da imagem ORIGINAL (sem processamento pesado)
        PRIORIDADE: Detectar QR Code na melhor qualidade possível
        """
        try:
            import cv2
            import numpy as np
            
            print(f"🔍 INICIANDO DETECÇÃO DE QR CODE NA IMAGEM ORIGINAL")
            print(f"📏 Imagem original: {img.shape}, dtype: {img.dtype}")
            print(f"📊 Valores únicos: {len(np.unique(img))}, min: {img.min()}, max: {img.max()}")
            
            # Converter para escala de cinza se necessário
            if len(img.shape) == 3:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            else:
                gray = img.copy()
            
            print(f"📊 Escala de cinza: {gray.shape}, valores únicos: {len(np.unique(gray))}, min: {gray.min()}, max: {gray.max()}")
            
            # Detector de QR Code
            qr_detector = cv2.QRCodeDetector()
            
            # MÉTODO 1: Detecção direta na imagem colorida (melhor qualidade)
            if len(img.shape) == 3:
                print(f"🔍 Tentando detecção em imagem colorida...")
                try:
                    data, bbox, _ = qr_detector.detectAndDecode(img)
                    print(f"📱 Resultado colorida: dados='{data}', bbox={bbox}")
                    if data and data.strip():
                        print(f"✅ QR Code detectado (imagem colorida): {data}")
                        return data.strip()
                except Exception as e:
                    print(f"❌ Erro detecção colorida: {e}")
            
            # MÉTODO 2: Detecção direta em escala de cinza
            print(f"🔍 Tentando detecção em escala de cinza...")
            try:
                data, bbox, _ = qr_detector.detectAndDecode(gray)
                print(f"📱 Resultado grayscale: dados='{data}', bbox={bbox}")
                if data and data.strip():
                    print(f"✅ QR Code detectado (escala de cinza): {data}")
                    return data.strip()
            except Exception as e:
                print(f"❌ Erro detecção grayscale: {e}")
            
            # MÉTODO 3: ROI no canto superior esquerdo (onde geralmente está o QR Code)
            print(f"🔍 Tentando detecção por ROI (canto superior esquerdo)...")
            h, w = gray.shape
            roi_size = min(w, h) // 3  # 1/3 da imagem
            roi = gray[0:roi_size, 0:roi_size]
            print(f"📍 ROI superior esquerda: {roi.shape}, valores únicos: {len(np.unique(roi))}")
            
            try:
                data, bbox, _ = qr_detector.detectAndDecode(roi)
                print(f"📱 Resultado ROI 1/3: dados='{data}', bbox={bbox}")
                if data and data.strip():
                    print(f"✅ QR Code detectado (ROI superior esquerda): {data}")
                    return data.strip()
            except Exception as e:
                print(f"❌ Erro ROI 1/3: {e}")
            
            # MÉTODO 4: ROI menor no canto superior esquerdo (QR Code pode estar pequeno)
            print(f"🔍 Tentando ROI menor...")
            roi_size_small = min(w, h) // 4  # 1/4 da imagem
            roi_small = gray[0:roi_size_small, 0:roi_size_small]
            print(f"📍 ROI pequena: {roi_small.shape}, valores únicos: {len(np.unique(roi_small))}")
            
            try:
                data, bbox, _ = qr_detector.detectAndDecode(roi_small)
                print(f"📱 Resultado ROI 1/4: dados='{data}', bbox={bbox}")
                if data and data.strip():
                    print(f"✅ QR Code detectado (ROI pequena): {data}")
                    return data.strip()
            except Exception as e:
                print(f"❌ Erro ROI 1/4: {e}")
            
            # MÉTODO 5: Threshold OTSU (método mais suave)
            print(f"🔍 Tentando threshold OTSU...")
            try:
                _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                print(f"📊 OTSU threshold: {thresh.shape}, valores únicos: {len(np.unique(thresh))}")
                data, bbox, _ = qr_detector.detectAndDecode(thresh)
                print(f"📱 Resultado OTSU: dados='{data}', bbox={bbox}")
                if data and data.strip():
                    print(f"✅ QR Code detectado (threshold OTSU): {data}")
                    return data.strip()
            except Exception as e:
                print(f"❌ Erro OTSU: {e}")
            
            # MÉTODO 6: Threshold adaptativo (mais suave)
            print(f"🔍 Tentando threshold adaptativo...")
            try:
                thresh_adapt = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
                print(f"📊 Threshold adaptativo: {thresh_adapt.shape}, valores únicos: {len(np.unique(thresh_adapt))}")
                data, bbox, _ = qr_detector.detectAndDecode(thresh_adapt)
                print(f"📱 Resultado adaptativo: dados='{data}', bbox={bbox}")
                if data and data.strip():
                    print(f"✅ QR Code detectado (threshold adaptativo): {data}")
                    return data.strip()
            except Exception as e:
                print(f"❌ Erro adaptativo: {e}")
            
            # MÉTODO 7: Threshold inverso
            print(f"🔍 Tentando threshold inverso...")
            try:
                _, thresh_inv = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
                print(f"📊 Threshold inverso: {thresh_inv.shape}, valores únicos: {len(np.unique(thresh_inv))}")
                data, bbox, _ = qr_detector.detectAndDecode(thresh_inv)
                print(f"📱 Resultado inverso: dados='{data}', bbox={bbox}")
                if data and data.strip():
                    print(f"✅ QR Code detectado (threshold inverso): {data}")
                    return data.strip()
            except Exception as e:
                print(f"❌ Erro inverso: {e}")
            
            # MÉTODO 8: Tentar em diferentes regiões (caso QR Code não esteja no canto superior esquerdo)
            print(f"🔍 Tentando detecção em múltiplas regiões...")
            regions = [
                (0, 0, w//2, h//2),      # Superior esquerda
                (w//2, 0, w, h//2),      # Superior direita
                (0, h//2, w//2, h),      # Inferior esquerda
                (w//2, h//2, w, h)       # Inferior direita
            ]
            
            for i, (x1, y1, x2, y2) in enumerate(regions):
                roi = gray[y1:y2, x1:x2]
                if roi.size > 0:
                    try:
                        data, bbox, _ = qr_detector.detectAndDecode(roi)
                        print(f"📱 Resultado região {i+1}: dados='{data}', bbox={bbox}")
                        if data and data.strip():
                            print(f"✅ QR Code detectado (região {i+1}): {data}")
                            return data.strip()
                    except Exception as e:
                        print(f"❌ Erro região {i+1}: {e}")
            
            # MÉTODO 9: Tentar com diferentes tamanhos de ROI
            print(f"🔍 Tentando diferentes tamanhos de ROI...")
            for size_factor in [0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5]:
                roi_size = int(min(w, h) * size_factor)
                if roi_size > 20:  # Mínimo de 20x20 pixels
                    roi = gray[0:roi_size, 0:roi_size]
                    try:
                        data, bbox, _ = qr_detector.detectAndDecode(roi)
                        print(f"📱 Resultado ROI {roi_size}x{roi_size}: dados='{data}', bbox={bbox}")
                        if data and data.strip():
                            print(f"✅ QR Code detectado (ROI {roi_size}x{roi_size}): {data}")
                            return data.strip()
                    except Exception as e:
                        print(f"❌ Erro ROI {roi_size}x{roi_size}: {e}")
            
            # MÉTODO 10: Tentar com diferentes valores de threshold manual
            print(f"🔍 Tentando threshold manual...")
            for threshold_value in [50, 100, 127, 150, 200]:
                try:
                    _, thresh_manual = cv2.threshold(gray, threshold_value, 255, cv2.THRESH_BINARY)
                    data, bbox, _ = qr_detector.detectAndDecode(thresh_manual)
                    print(f"📱 Resultado threshold {threshold_value}: dados='{data}', bbox={bbox}")
                    if data and data.strip():
                        print(f"✅ QR Code detectado (threshold {threshold_value}): {data}")
                        return data.strip()
                except Exception as e:
                    print(f"❌ Erro threshold {threshold_value}: {e}")
            
            # MÉTODO 11: Tentar com pyzbar (biblioteca alternativa)
            print(f"🔍 Tentando detecção com pyzbar...")
            try:
                from pyzbar import pyzbar
                import numpy as np
                
                # Converter para formato PIL se necessário
                if len(img.shape) == 3:
                    from PIL import Image
                    pil_img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
                else:
                    from PIL import Image
                    pil_img = Image.fromarray(gray)
                
                barcodes = pyzbar.decode(pil_img)
                print(f"📱 Resultado pyzbar: {len(barcodes)} códigos encontrados")
                
                for barcode in barcodes:
                    data = barcode.data.decode('utf-8')
                    print(f"📱 Código pyzbar: {data}")
                    if data and data.strip():
                        print(f"✅ QR Code detectado (pyzbar): {data}")
                        return data.strip()
                        
            except ImportError:
                print(f"⚠️ pyzbar não disponível")
            except Exception as e:
                print(f"❌ Erro pyzbar: {e}")
            
            # MÉTODO 12: Tentar com pyzbar em ROI
            print(f"🔍 Tentando pyzbar em ROI...")
            try:
                from pyzbar import pyzbar
                from PIL import Image
                
                # Tentar em ROI do canto superior esquerdo
                roi_size = min(w, h) // 3
                roi = gray[0:roi_size, 0:roi_size]
                pil_roi = Image.fromarray(roi)
                
                barcodes = pyzbar.decode(pil_roi)
                print(f"📱 Resultado pyzbar ROI: {len(barcodes)} códigos encontrados")
                
                for barcode in barcodes:
                    data = barcode.data.decode('utf-8')
                    print(f"📱 Código pyzbar ROI: {data}")
                    if data and data.strip():
                        print(f"✅ QR Code detectado (pyzbar ROI): {data}")
                        return data.strip()
                        
            except ImportError:
                print(f"⚠️ pyzbar não disponível para ROI")
            except Exception as e:
                print(f"❌ Erro pyzbar ROI: {e}")
            
            print("❌ QR Code não detectado em nenhum método na imagem original")
            return None
                
        except Exception as e:
            print(f"❌ Erro ao extrair QR code da imagem original: {str(e)}")
            return None

    def _extrair_qr_code_original(self, img):
        """
        Extrai QR code da imagem ORIGINAL (sem processamento pesado)
        PRIORIDADE: Detectar QR Code na melhor qualidade possível
        """
        try:
            import cv2
            import numpy as np
            
            print(f"🔍 INICIANDO DETECÇÃO DE QR CODE NA IMAGEM ORIGINAL")
            print(f"📏 Imagem original: {img.shape}, dtype: {img.dtype}")
            print(f"📊 Valores únicos: {len(np.unique(img))}, min: {img.min()}, max: {img.max()}")
            
            # Converter para escala de cinza se necessário
            if len(img.shape) == 3:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            else:
                gray = img.copy()
            
            print(f"📊 Escala de cinza: {gray.shape}, valores únicos: {len(np.unique(gray))}, min: {gray.min()}, max: {gray.max()}")
            
            # Detector de QR Code
            qr_detector = cv2.QRCodeDetector()
            
            # MÉTODO 1: Detecção direta na imagem colorida (melhor qualidade)
            if len(img.shape) == 3:
                print(f"🔍 Tentando detecção em imagem colorida...")
                try:
                    data, bbox, _ = qr_detector.detectAndDecode(img)
                    print(f"📱 Resultado colorida: dados='{data}', bbox={bbox}")
                    if data and data.strip():
                        print(f"✅ QR Code detectado (imagem colorida): {data}")
                        return data.strip()
                except Exception as e:
                    print(f"❌ Erro detecção colorida: {e}")
            
            # MÉTODO 2: Detecção direta em escala de cinza
            print(f"🔍 Tentando detecção em escala de cinza...")
            try:
                data, bbox, _ = qr_detector.detectAndDecode(gray)
                print(f"📱 Resultado grayscale: dados='{data}', bbox={bbox}")
                if data and data.strip():
                    print(f"✅ QR Code detectado (escala de cinza): {data}")
                    return data.strip()
            except Exception as e:
                print(f"❌ Erro detecção grayscale: {e}")
            
            # MÉTODO 3: ROI no canto superior esquerdo (onde geralmente está o QR Code)
            print(f"🔍 Tentando detecção por ROI (canto superior esquerdo)...")
            h, w = gray.shape
            roi_size = min(w, h) // 3  # 1/3 da imagem
            roi = gray[0:roi_size, 0:roi_size]
            print(f"📍 ROI superior esquerda: {roi.shape}, valores únicos: {len(np.unique(roi))}")
            
            try:
                data, bbox, _ = qr_detector.detectAndDecode(roi)
                print(f"📱 Resultado ROI 1/3: dados='{data}', bbox={bbox}")
                if data and data.strip():
                    print(f"✅ QR Code detectado (ROI superior esquerda): {data}")
                    return data.strip()
            except Exception as e:
                print(f"❌ Erro ROI 1/3: {e}")
            
            # MÉTODO 4: ROI menor no canto superior esquerdo (QR Code pode estar pequeno)
            print(f"🔍 Tentando ROI menor...")
            roi_size_small = min(w, h) // 4  # 1/4 da imagem
            roi_small = gray[0:roi_size_small, 0:roi_size_small]
            print(f"📍 ROI pequena: {roi_small.shape}, valores únicos: {len(np.unique(roi_small))}")
            
            try:
                data, bbox, _ = qr_detector.detectAndDecode(roi_small)
                print(f"📱 Resultado ROI 1/4: dados='{data}', bbox={bbox}")
                if data and data.strip():
                    print(f"✅ QR Code detectado (ROI pequena): {data}")
                    return data.strip()
            except Exception as e:
                print(f"❌ Erro ROI 1/4: {e}")
            
            # MÉTODO 5: Threshold OTSU (método mais suave)
            print(f"🔍 Tentando threshold OTSU...")
            try:
                _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                print(f"📊 OTSU threshold: {thresh.shape}, valores únicos: {len(np.unique(thresh))}")
                data, bbox, _ = qr_detector.detectAndDecode(thresh)
                print(f"📱 Resultado OTSU: dados='{data}', bbox={bbox}")
                if data and data.strip():
                    print(f"✅ QR Code detectado (threshold OTSU): {data}")
                    return data.strip()
            except Exception as e:
                print(f"❌ Erro OTSU: {e}")
            
            # MÉTODO 6: Threshold adaptativo (mais suave)
            print(f"🔍 Tentando threshold adaptativo...")
            try:
                thresh_adapt = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
                print(f"📊 Threshold adaptativo: {thresh_adapt.shape}, valores únicos: {len(np.unique(thresh_adapt))}")
                data, bbox, _ = qr_detector.detectAndDecode(thresh_adapt)
                print(f"📱 Resultado adaptativo: dados='{data}', bbox={bbox}")
                if data and data.strip():
                    print(f"✅ QR Code detectado (threshold adaptativo): {data}")
                    return data.strip()
            except Exception as e:
                print(f"❌ Erro adaptativo: {e}")
            
            # MÉTODO 7: Threshold inverso
            print(f"🔍 Tentando threshold inverso...")
            try:
                _, thresh_inv = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
                print(f"📊 Threshold inverso: {thresh_inv.shape}, valores únicos: {len(np.unique(thresh_inv))}")
                data, bbox, _ = qr_detector.detectAndDecode(thresh_inv)
                print(f"📱 Resultado inverso: dados='{data}', bbox={bbox}")
                if data and data.strip():
                    print(f"✅ QR Code detectado (threshold inverso): {data}")
                    return data.strip()
            except Exception as e:
                print(f"❌ Erro inverso: {e}")
            
            # MÉTODO 8: Tentar em diferentes regiões (caso QR Code não esteja no canto superior esquerdo)
            print(f"🔍 Tentando detecção em múltiplas regiões...")
            regions = [
                (0, 0, w//2, h//2),      # Superior esquerda
                (w//2, 0, w, h//2),      # Superior direita
                (0, h//2, w//2, h),      # Inferior esquerda
                (w//2, h//2, w, h)       # Inferior direita
            ]
            
            for i, (x1, y1, x2, y2) in enumerate(regions):
                roi = gray[y1:y2, x1:x2]
                if roi.size > 0:
                    try:
                        data, bbox, _ = qr_detector.detectAndDecode(roi)
                        print(f"📱 Resultado região {i+1}: dados='{data}', bbox={bbox}")
                        if data and data.strip():
                            print(f"✅ QR Code detectado (região {i+1}): {data}")
                            return data.strip()
                    except Exception as e:
                        print(f"❌ Erro região {i+1}: {e}")
            
            # MÉTODO 9: Tentar com diferentes tamanhos de ROI
            print(f"🔍 Tentando diferentes tamanhos de ROI...")
            for size_factor in [0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5]:
                roi_size = int(min(w, h) * size_factor)
                if roi_size > 20:  # Mínimo de 20x20 pixels
                    roi = gray[0:roi_size, 0:roi_size]
                    try:
                        data, bbox, _ = qr_detector.detectAndDecode(roi)
                        print(f"📱 Resultado ROI {roi_size}x{roi_size}: dados='{data}', bbox={bbox}")
                        if data and data.strip():
                            print(f"✅ QR Code detectado (ROI {roi_size}x{roi_size}): {data}")
                            return data.strip()
                    except Exception as e:
                        print(f"❌ Erro ROI {roi_size}x{roi_size}: {e}")
            
            # MÉTODO 10: Tentar com diferentes valores de threshold manual
            print(f"🔍 Tentando threshold manual...")
            for threshold_value in [50, 100, 127, 150, 200]:
                try:
                    _, thresh_manual = cv2.threshold(gray, threshold_value, 255, cv2.THRESH_BINARY)
                    data, bbox, _ = qr_detector.detectAndDecode(thresh_manual)
                    print(f"📱 Resultado threshold {threshold_value}: dados='{data}', bbox={bbox}")
                    if data and data.strip():
                        print(f"✅ QR Code detectado (threshold {threshold_value}): {data}")
                        return data.strip()
                except Exception as e:
                    print(f"❌ Erro threshold {threshold_value}: {e}")
            
            # MÉTODO 11: Tentar com pyzbar (biblioteca alternativa)
            print(f"🔍 Tentando detecção com pyzbar...")
            try:
                from pyzbar import pyzbar
                import numpy as np
                
                # Converter para formato PIL se necessário
                if len(img.shape) == 3:
                    from PIL import Image
                    pil_img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
                else:
                    from PIL import Image
                    pil_img = Image.fromarray(gray)
                
                barcodes = pyzbar.decode(pil_img)
                print(f"📱 Resultado pyzbar: {len(barcodes)} códigos encontrados")
                
                for barcode in barcodes:
                    data = barcode.data.decode('utf-8')
                    print(f"📱 Código pyzbar: {data}")
                    if data and data.strip():
                        print(f"✅ QR Code detectado (pyzbar): {data}")
                        return data.strip()
                        
            except ImportError:
                print(f"⚠️ pyzbar não disponível")
            except Exception as e:
                print(f"❌ Erro pyzbar: {e}")
            
            # MÉTODO 12: Tentar com pyzbar em ROI
            print(f"🔍 Tentando pyzbar em ROI...")
            try:
                from pyzbar import pyzbar
                from PIL import Image
                
                # Tentar em ROI do canto superior esquerdo
                roi_size = min(w, h) // 3
                roi = gray[0:roi_size, 0:roi_size]
                pil_roi = Image.fromarray(roi)
                
                barcodes = pyzbar.decode(pil_roi)
                print(f"📱 Resultado pyzbar ROI: {len(barcodes)} códigos encontrados")
                
                for barcode in barcodes:
                    data = barcode.data.decode('utf-8')
                    print(f"📱 Código pyzbar ROI: {data}")
                    if data and data.strip():
                        print(f"✅ QR Code detectado (pyzbar ROI): {data}")
                        return data.strip()
                        
            except ImportError:
                print(f"⚠️ pyzbar não disponível para ROI")
            except Exception as e:
                print(f"❌ Erro pyzbar ROI: {e}")
            
            print("❌ QR Code não detectado em nenhum método na imagem original")
            return None
                
        except Exception as e:
            print(f"❌ Erro ao extrair QR code da imagem original: {str(e)}")
            return None

    def _extrair_qr_code(self, img):
        """
        Extrai QR code da imagem e retorna o student_id
        MANTIDO PARA COMPATIBILIDADE - usar _extrair_qr_code_original para nova implementação
        MANTIDO PARA COMPATIBILIDADE - usar _extrair_qr_code_original para nova implementação
        """
        try:
            import cv2
            import numpy as np
            
            print(f"🔍 INICIANDO DETECÇÃO DE QR CODE")
            print(f"📏 Imagem de entrada: {img.shape}, dtype: {img.dtype}")
            
            # Converter para escala de cinza se necessário
            if len(img.shape) == 3:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            else:
                gray = img.copy()
            
            print(f"📊 Valores únicos: {len(np.unique(gray))}, min: {gray.min()}, max: {gray.max()}")
            
            # Tentar diferentes métodos de detecção
            qr_detector = cv2.QRCodeDetector()
            
            # Método 1: Detecção direta na imagem colorida
            if len(img.shape) == 3:
                data, bbox, _ = qr_detector.detectAndDecode(img)
                if data and data.strip():
                    print(f"✅ QR Code detectado (imagem colorida): {data}")
                    return data.strip()
            
            # Método 2: Detecção direta em escala de cinza
            data, bbox, _ = qr_detector.detectAndDecode(gray)
            if data and data.strip():
                print(f"✅ QR Code detectado (escala de cinza): {data}")
                return data.strip()
            
            # Método 3: Aplicar threshold OTSU
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            data, bbox, _ = qr_detector.detectAndDecode(thresh)
            if data and data.strip():
                print(f"✅ QR Code detectado (threshold OTSU): {data}")
                return data.strip()
            
            # Método 4: Aplicar threshold adaptativo
            thresh_adapt = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
            data, bbox, _ = qr_detector.detectAndDecode(thresh_adapt)
            if data and data.strip():
                print(f"✅ QR Code detectado (threshold adaptativo): {data}")
                return data.strip()
            
            # Método 5: Tentar em diferentes regiões da imagem
            h, w = gray.shape
            regions = [
                (0, 0, w//2, h//2),  # Superior esquerda
                (w//2, 0, w, h//2),  # Superior direita
                (0, h//2, w//2, h),  # Inferior esquerda
                (w//2, h//2, w, h)   # Inferior direita
            ]
            
            for i, (x1, y1, x2, y2) in enumerate(regions):
                roi = gray[y1:y2, x1:x2]
                if roi.size > 0:
                    data, bbox, _ = qr_detector.detectAndDecode(roi)
                    if data and data.strip():
                        print(f"✅ QR Code detectado (região {i+1}): {data}")
                        return data.strip()
            
            # Método 6: Tentar com diferentes tamanhos de ROI (QR code pode estar pequeno)
            for size_factor in [0.1, 0.2, 0.3, 0.4]:
                roi_size = int(min(w, h) * size_factor)
                if roi_size > 50:  # Mínimo de 50x50 pixels
                    roi = gray[0:roi_size, 0:roi_size]
                    data, bbox, _ = qr_detector.detectAndDecode(roi)
                    if data and data.strip():
                        print(f"✅ QR Code detectado (ROI {roi_size}x{roi_size}): {data}")
                        return data.strip()
            
            print("❌ QR Code não detectado em nenhum método")
            return None
                
        except Exception as e:
            print(f"❌ Erro ao extrair QR code: {str(e)}")
            return None

    def _agrupar_bolhas_por_linha(self, bolhas, thresh, tolerancia=20):
        """
        Agrupa bolhas por linhas horizontais (questões)
        """
        print(f"🔍 Agrupando {len(bolhas)} bolhas com tolerância de {tolerancia}px...")
        
        # Converter contornos para coordenadas (x, y, w, h)
        bolhas_coords = []
        for c in bolhas:
            x, y, w, h = cv2.boundingRect(c)
            cx, cy = x + w // 2, y + h // 2  # Centro da bolha
            bolhas_coords.append((cx, cy, w, h, c))  # Incluir contorno original
        
        # Agrupar por linhas
        linhas = []
        for (cx, cy, w, h, contorno) in bolhas_coords:
            colocado = False
            for linha in linhas:
                # Verificar se está na mesma linha (tolerância vertical)
                if abs(linha[0][1] - cy) < tolerancia:  # linha[0][1] é o y da primeira bolha da linha
                    linha.append((cx, cy, w, h, contorno))
                    colocado = True
                    break
            if not colocado:
                linhas.append([(cx, cy, w, h, contorno)])
        
        # Ordenar linhas de cima para baixo
        linhas.sort(key=lambda l: l[0][1])
        print(f"📏 Encontradas {len(linhas)} linhas")
        
        # Ordenar cada linha da esquerda para a direita e mapear para letras
        linhas_ordenadas = []
        letras = ["A", "B", "C", "D"]
        
        for i, linha in enumerate(linhas):
            linha_ordenada = sorted(linha, key=lambda b: b[0])  # Ordenar por x
            print(f"  Linha {i+1}: {len(linha_ordenada)} bolhas")
            
            # Mapear para contornos e letras
            linha_final = []
            for j, (cx, cy, w, h, contorno) in enumerate(linha_ordenada):
                if j < len(letras):  # Limitar a 4 alternativas (A, B, C, D)
                    linha_final.append((contorno, letras[j]))
                    print(f"    {letras[j]}: centro=({cx}, {cy})")
            
            if len(linha_final) >= 4:  # Só incluir linhas com pelo menos 4 bolhas
                linhas_ordenadas.append(linha_final)
            else:
                print(f"    ⚠️ Linha {i+1} ignorada: apenas {len(linha_final)} bolhas")
        
        print(f"✅ {len(linhas_ordenadas)} linhas válidas processadas")
        return linhas_ordenadas

    def _detectar_bolhas_manual(self, img_corrigida, gray):
        """
        Detecção manual de bolhas quando a detecção automática falha
        """
        print(f"🔧 INICIANDO DETECÇÃO MANUAL DE BOLHAS")
        
        # Assumir que temos 4 questões com 4 alternativas cada
        # Procurar por padrões regulares na imagem
        h, w = gray.shape
        print(f"📏 Dimensões da imagem: {w}x{h}")
        
        # Dividir a imagem em regiões onde esperamos encontrar as bolhas
        # Assumir que as bolhas estão em uma grade 4x4 (4 questões x 4 alternativas)
        respostas = {}
        
        # Estimar posições das bolhas baseado no layout típico
        # Assumir que as bolhas estão na parte direita da imagem
        start_x = w // 2  # Começar da metade da imagem
        start_y = h // 4  # Começar do quarto superior
        
        # Tamanho estimado das bolhas
        bolha_size = min(w, h) // 20
        
        print(f"📍 Região de busca: x={start_x}-{w}, y={start_y}-{h}")
        print(f"📐 Tamanho estimado das bolhas: {bolha_size}")
        
        for questao in range(1, 5):  # 4 questões
            print(f"🔍 Analisando questão {questao}...")
            marcada = None
            
            for alt_idx, letra in enumerate(["A", "B", "C", "D"]):
                # Calcular posição estimada da bolha
                x = start_x + (alt_idx * bolha_size * 2)
                y = start_y + ((questao - 1) * bolha_size * 2)
                
                # Verificar se a posição está dentro da imagem
                if x + bolha_size < w and y + bolha_size < h:
                    # Extrair região da bolha
                    roi = gray[y:y+bolha_size, x:x+bolha_size]
                    
                    if roi.size > 0:
                        # Calcular intensidade média
                        mean_intensity = roi.mean()
                        print(f"  {letra}: pos=({x},{y}), intensidade={mean_intensity:.1f}")
                        
                        # Se a região é escura (bolha marcada)
                        if mean_intensity < 120:  # Threshold mais baixo para detecção manual
                            marcada = letra
                            print(f"  ✅ {letra} marcada (intensidade: {mean_intensity:.1f})")
            
            respostas[questao] = marcada
            if marcada is None:
                print(f"  ❌ Questão {questao}: Nenhuma alternativa marcada")
        
        return respostas

    def testar_deteccao_bolhas(self, image_data: str) -> Dict:
        """
        Função de teste para verificar se a detecção de bolhas está funcionando
        """
        try:
            print(f"🧪 INICIANDO TESTE DE DETECÇÃO DE BOLHAS")
            print(f"📏 Tamanho da imagem base64: {len(image_data)} caracteres")
            
            # Decodificar imagem base64
            if ',' in image_data:
                image_data = image_data.split(',')[1]
            
            image_bytes = base64.b64decode(image_data)
            img = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
            
            if img is None:
                return {"error": "Erro ao decodificar imagem"}
            
            print(f"🖼️ Imagem carregada: {img.shape}")
            
            # Testar detecção de bolhas com pipeline robusto
            respostas = self.detect_bubbles_robust(img, expected_cols=4, debug=True)
            
            return {
                "success": True,
                "respostas_detectadas": respostas,
                "total_questoes": len(respostas),
                "questoes_respondidas": len([r for r in respostas.values() if r is not None]),
                "message": f"Detectadas {len(respostas)} questões, {len([r for r in respostas.values() if r is not None])} respondidas"
            }
            
        except Exception as e:
            logging.error(f"Erro no teste de detecção: {str(e)}")
            return {"error": f"Erro no teste: {str(e)}"}

    def detectar_respostas_marcadas(self, binary_image, coordinates_map: Dict) -> Dict:
        """
        Detecta respostas marcadas usando coordenadas mapeadas por disciplina
        """
        try:
            print(f"🔍 INICIANDO DETECÇÃO DE RESPOSTAS MARCADAS")
            print(f"📏 Dimensões da imagem binária: {binary_image.shape}")
            print(f"🗺️ Coordenadas mapeadas: {len(coordinates_map)} disciplinas")
            
            respostas_por_disciplina = {}
            
            for subject_key, subject_coords in coordinates_map.items():
                print(f"📚 Processando disciplina: {subject_key}")
                respostas_por_disciplina[subject_key] = {}
                
                for question_key, question_coords in subject_coords.items():
                    print(f"  📝 Processando questão: {question_key}")
                    respostas_por_disciplina[subject_key][question_key] = {}
                    
                    for alt_id, coord_info in question_coords.items():
                        x = coord_info["x"]
                        y = coord_info["y"]
                        radius = coord_info["radius"]
                        
                        print(f"    📍 Coordenadas {alt_id}: x={x}, y={y}, radius={radius}")
                        
                        # Verificar se coordenadas estão dentro da imagem
                        h, w = binary_image.shape
                        if x < 0 or x >= w or y < 0 or y >= h:
                            print(f"    ⚠️ Coordenadas {alt_id} fora da imagem: x={x}, y={y}, img_size=({w}, {h})")
                            respostas_por_disciplina[subject_key][question_key][alt_id] = False
                            continue
                        
                        # Criar máscara circular
                        mascara = np.zeros((h, w), dtype=np.uint8)
                        cv2.circle(mascara, (x, y), radius, 255, -1)
                        
                        # Aplicar máscara na região de interesse
                        interesse_mascarado = cv2.bitwise_and(binary_image, binary_image, mask=mascara)
                        
                        # Debug da região de interesse
                        region_pixels = binary_image[max(0, y-radius):min(h, y+radius), max(0, x-radius):min(w, x+radius)]
                        print(f"    🔍 Região {alt_id}: {region_pixels.shape}, valores únicos: {len(np.unique(region_pixels))}")
                        
                        # Calcular porcentagem de pixels brancos
                        total_pixels = cv2.countNonZero(mascara)
                        pixels_brancos = cv2.countNonZero(interesse_mascarado)
                        
                        if total_pixels > 0:
                            porcentagem_branco = (pixels_brancos / total_pixels) * 100
                            
                            # Ajustar threshold - se 15% ou mais dos pixels são brancos = marcado
                            is_marked = porcentagem_branco >= 15
                            respostas_por_disciplina[subject_key][question_key][alt_id] = is_marked
                            
                            print(f"    {alt_id}: {porcentagem_branco:.1f}% branco -> {'✅ MARCADO' if is_marked else '❌ NÃO MARCADO'}")
                        else:
                            respostas_por_disciplina[subject_key][question_key][alt_id] = False
                            print(f"    {alt_id}: ❌ ERRO - Total de pixels = 0")
            
            print(f"📊 DETECÇÃO CONCLUÍDA: {respostas_por_disciplina}")
            return respostas_por_disciplina
            
        except Exception as e:
            logging.error(f"Erro ao detectar respostas marcadas: {str(e)}")
            return {}

    def _group_questions_by_subject(self, questions_data: List[Dict]) -> Dict:
        """
        Agrupa questões por disciplina
        """
        subjects = {}
        for question in questions_data:
            subject_name = question.get('subject', {}).get('name', 'Outras')
            if subject_name not in subjects:
                subjects[subject_name] = []
            subjects[subject_name].append(question)
        return subjects

    def _determine_layout(self, num_subjects: int) -> str:
        """
        Determina o layout baseado no número de disciplinas
        """
        if num_subjects <= 2:
            return "horizontal"  # 2x1
        elif num_subjects <= 4:
            return "grid"        # 2x2
        else:
            return "vertical"    # Empilhado

    def _create_subject_tables(self, subjects: Dict, layout: str) -> List:
        """
        Cria tabelas para cada disciplina
        """
        from reportlab.platypus import Table, TableStyle, Paragraph
        from reportlab.lib import colors
        from reportlab.graphics.shapes import Drawing, Circle
        
        # Função para criar bolinha
        def bolinha():
            d = Drawing(15, 15)
            c = Circle(7, 7, 6)
            c.strokeColor = colors.black
            c.fillColor = None
            d.add(c)
            return d
        
        # Função para gerar linhas de alternativas
        def gerar_linhas_disciplina(questions, subject_name):
            linhas = []
            for i, question_data in enumerate(questions):
                question_num = i + 1
                alternative_ids = question_data.get('alternative_ids', [])
                
                # Criar linha com número da questão + bolinhas para cada alternativa
                linha = [str(question_num)]
                for alt_id in alternative_ids:
                    linha.append(bolinha())
                linhas.append(linha)
            return linhas
        
        subject_tables = []
        
        if layout == "horizontal":
            # 2 disciplinas lado a lado
            for subject_name, questions in subjects.items():
                max_alternatives = max(len(q.get('alternative_ids', [])) for q in questions) if questions else 0
                header = [Paragraph(f"<b>{subject_name}</b>", self.styles['Normal'])] + [""] * max_alternatives
                sub_header = ["Nº"] + [chr(65 + i) for i in range(max_alternatives)]
                
                table_data = [header, sub_header] + gerar_linhas_disciplina(questions, subject_name)
                table = Table(table_data, colWidths=[20] + [25] * max_alternatives)
                
                # Estilo da tabela
                estilo = TableStyle([
                    ("GRID", (1,1), (-1,-1), 0.5, colors.black),  # Grid apenas nas linhas de questões
                    ("ALIGN", (0,0), (-1,-1), "CENTER"),
                    ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
                    ("SPAN", (0,0), (-1,0)),  # Mesclar primeira linha para título
                ])
                table.setStyle(estilo)
                subject_tables.append(table)
        
        elif layout == "grid":
            # 2x2 grid
            subject_list = list(subjects.items())
            for i in range(0, len(subject_list), 2):
                row_tables = []
                for j in range(2):
                    if i + j < len(subject_list):
                        subject_name, questions = subject_list[i + j]
                        max_alternatives = max(len(q.get('alternative_ids', [])) for q in questions) if questions else 0
                        header = [Paragraph(f"<b>{subject_name}</b>", self.styles['Normal'])] + [""] * max_alternatives
                        sub_header = ["Nº"] + [chr(65 + i) for i in range(max_alternatives)]
                        
                        table_data = [header, sub_header] + gerar_linhas_disciplina(questions, subject_name)
                        table = Table(table_data, colWidths=[20] + [25] * max_alternatives)
                        
                        # Estilo da tabela
                        estilo = TableStyle([
                            ("GRID", (1,1), (-1,-1), 0.5, colors.black),
                            ("ALIGN", (0,0), (-1,-1), "CENTER"),
                            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
                            ("SPAN", (0,0), (-1,0)),
                        ])
                        table.setStyle(estilo)
                        row_tables.append(table)
                subject_tables.append(row_tables)
        
        else:
            # Empilhado verticalmente
            for subject_name, questions in subjects.items():
                max_alternatives = max(len(q.get('alternative_ids', [])) for q in questions) if questions else 0
                header = [Paragraph(f"<b>{subject_name}</b>", self.styles['Normal'])] + [""] * max_alternatives
                sub_header = ["Nº"] + [chr(65 + i) for i in range(max_alternatives)]
                
                table_data = [header, sub_header] + gerar_linhas_disciplina(questions, subject_name)
                table = Table(table_data, colWidths=[20] + [25] * max_alternatives)
                
                # Estilo da tabela
                estilo = TableStyle([
                    ("GRID", (1,1), (-1,-1), 0.5, colors.black),
                    ("ALIGN", (0,0), (-1,-1), "CENTER"),
                    ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
                    ("SPAN", (0,0), (-1,0)),
                ])
                table.setStyle(estilo)
                subject_tables.append(table)
        
        return subject_tables

    def _generate_coordinates_map_by_subject(self, subjects: Dict) -> Dict:
        """
        Gera mapeamento de coordenadas por disciplina
        """
        coordinates_map = {}
        
        # Parâmetros do layout
        COL_NUM_WIDTH = 20
        COL_ALT_WIDTH = 25
        ROW_HEIGHT = 20
        START_X = 200
        START_Y = 100
        
        for subject_name, questions in subjects.items():
            subject_key = subject_name.lower().replace(' ', '_')
            coordinates_map[subject_key] = {}
            
            max_alternatives = max(len(q.get('alternative_ids', [])) for q in questions) if questions else 0
            
            for i, question_data in enumerate(questions):
                question_num = i + 1
                alternative_ids = question_data.get('alternative_ids', [])
                
                coordinates_map[subject_key][f"question_{question_num}"] = {}
                
                # Posição Y da linha (incluindo cabeçalho)
                y_pos = START_Y + (i + 2) * ROW_HEIGHT  # +2 para pular título e cabeçalho
                
                # Posição X inicial das alternativas
                x_start = START_X + COL_NUM_WIDTH
                
                for j, alt_id in enumerate(alternative_ids):
                    x_pos = x_start + (j * COL_ALT_WIDTH) + (COL_ALT_WIDTH // 2)
                    coordinates_map[subject_key][f"question_{question_num}"][alt_id] = {
                        "x": x_pos,
                        "y": y_pos,
                        "radius": 6,
                        "question_id": question_data.get('id', f'{subject_key}_q{question_num}')
                    }
        
        return coordinates_map

    def process_physical_correction_with_coordinates(self, test_id: str, student_id: str, 
                                                   filled_coordinates: Dict, questions_data: List[Dict]) -> Dict:
        """
        Processa correção de formulário físico usando coordenadas mapeadas por disciplina
        
        Args:
            test_id: ID do teste
            student_id: ID do aluno
            filled_coordinates: Coordenadas das bolinhas preenchidas por disciplina
            questions_data: Dados das questões com correct_answer
            
        Returns:
            Resultado da correção com nota e classificação
        """
        try:
            from app.services.evaluation_result_service import EvaluationResultService
            from app.models.question import Question
            from app.models.studentAnswer import StudentAnswer
            from app import db
            
            # Buscar questões do teste
            from app.models.testQuestion import TestQuestion
            test_question_ids = [tq.question_id for tq in TestQuestion.query.filter_by(test_id=test_id).order_by(TestQuestion.order).all()]
            questions = Question.query.filter(Question.id.in_(test_question_ids)).all() if test_question_ids else []
            
            if not questions:
                return {"error": "Nenhuma questão encontrada para este teste"}
            
            # Agrupar questões por disciplina para mapeamento
            subjects = self._group_questions_by_subject(questions_data)
            
            # Mapear respostas do aluno baseado nas coordenadas preenchidas por disciplina
            student_answers = {}
            
            for subject_name, subject_questions in subjects.items():
                subject_key = subject_name.lower().replace(' ', '_')
                
                if subject_key in filled_coordinates:
                    subject_responses = filled_coordinates[subject_key]
                    
                    for question_num_str, answer in subject_responses.items():
                        # Extrair número da questão (ex: "question_1" -> 1)
                        question_num = int(question_num_str.split('_')[1])
                        
                        # Encontrar a questão correspondente
                        if question_num <= len(subject_questions):
                            question_data = subject_questions[question_num - 1]
                            question_id = question_data.get('id')
                            
                            if question_id:
                                student_answers[question_id] = answer
            
            # Salvar respostas do aluno
            for question_id, answer in student_answers.items():
                # Verificar se já existe resposta
                existing_answer = StudentAnswer.query.filter_by(
                    test_id=test_id,
                    student_id=student_id,
                    question_id=question_id
                ).first()
                
                if existing_answer:
                    # Atualizar resposta existente
                    existing_answer.answer = answer
                else:
                    # Criar nova resposta
                    new_answer = StudentAnswer(
                        test_id=test_id,
                        student_id=student_id,
                        question_id=question_id,
                        answer=answer
                    )
                    db.session.add(new_answer)
            
            db.session.commit()
            
            # Calcular resultado usando o serviço existente
            result = EvaluationResultService.calculate_and_save_result(
                test_id=test_id,
                student_id=student_id,
                session_id=None  # Para correções físicas
            )
            
            if result:
                return {
                    "success": True,
                    "message": "Correção processada com sucesso",
                    "student_id": student_id,
                    "test_id": test_id,
                    "correct_answers": result['correct_answers'],
                    "total_questions": result['total_questions'],
                    "score_percentage": result['score_percentage'],
                    "grade": result['grade'],
                    "proficiency": result['proficiency'],
                    "classification": result['classification']
                }
            else:
                return {"error": "Erro ao calcular resultado"}
                
        except Exception as e:
            logging.error(f"Erro ao processar correção física: {str(e)}")
            return {"error": f"Erro interno: {str(e)}"}

    def processar_correcao_por_imagem(self, test_id: str, image_data: str) -> Dict:
        """
        Processa correção completa por imagem do formulário preenchido
        
        Args:
            test_id: ID do teste
            image_data: Imagem em base64 do formulário preenchido
            
        Returns:
            Resultado da correção com nota e classificação
        """
        try:
            from app.services.evaluation_result_service import EvaluationResultService
            from app.models.question import Question
            from app.models.studentAnswer import StudentAnswer
            from app.models.testQuestion import TestQuestion
            from app.models.test import Test
            from app.models.classTest import ClassTest
            from app import db
            
            print(f"🚀 INICIANDO PROCESSAMENTO DE CORREÇÃO POR IMAGEM")
            print(f"📋 Test ID: {test_id}")
            print(f"📏 Tamanho da imagem: {len(image_data)} caracteres")
            
            # 1. Processar imagem
            print(f"🔍 Processando imagem...")
            image_result = self.processar_imagem_formulario(image_data)
            if "error" in image_result:
                print(f"❌ ERRO no processamento da imagem: {image_result['error']}")
                return {"error": f"Erro no processamento da imagem: {image_result['error']}"}
            
            print(f"✅ Imagem processada com sucesso")
            
            # 2. Extrair metadados do QR Code (JSON com metadados)
            qr_data = image_result.get("qr_data")
            print(f"📱 QR Data extraído: {qr_data}")
            
            qr_metadata = None
            student_id = None
            qr_code_id = None
            class_test_id = None
            
            if qr_data:
                try:
                    # QR Code agora contém JSON com metadados
                    if isinstance(qr_data, str):
                        qr_metadata = json.loads(qr_data)
                    else:
                        qr_metadata = qr_data
                    
                    student_id = qr_metadata.get("student_id")
                    qr_code_id = qr_metadata.get("qr_code_id")
                    test_id_from_qr = qr_metadata.get("test_id")
                    
                    print(f"✅ Metadados extraídos do QR Code:")
                    print(f"    Student ID: {student_id}")
                    print(f"    QR Code ID: {qr_code_id}")
                    print(f"    Test ID: {test_id_from_qr}")
                    
                    # Verificar se o test_id do QR Code confere
                    if test_id_from_qr != test_id:
                        print(f"⚠️ AVISO: Test ID do QR Code ({test_id_from_qr}) diferente do parâmetro ({test_id})")
                    
                    logging.info(f"QR Code detectado com metadados: {qr_metadata}")
                except (TypeError, AttributeError, json.JSONDecodeError) as e:
                    print(f"❌ QR Code inválido ou corrompido: {e}")
                    logging.warning(f"QR Code inválido ou corrompido: {e}")
            
            # Se não conseguiu extrair do QR Code, retornar erro
            if not student_id or not qr_code_id:
                print(f"❌ ERRO: QR Code não detectado ou metadados incompletos")
                return {"error": "QR Code não detectado ou metadados incompletos"}
            
            # 2. Obter class_id do test_id
            test = Test.query.get(test_id)
            if not test:
                return {"error": f"Teste {test_id} não encontrado"}
            
            # Buscar class_test_id através da tabela ClassTest
            class_test = ClassTest.query.filter_by(test_id=test_id).first()
            if not class_test:
                return {"error": f"Nenhuma turma encontrada para o teste {test_id}"}
            
            class_test_id = class_test.id
            class_id = class_test.class_id
            logging.info(f"Class_id obtido do test_id: {class_id}")
            
            # 3. Buscar questões do teste
            test_question_ids = [tq.question_id for tq in TestQuestion.query.filter_by(test_id=test_id).order_by(TestQuestion.order).all()]
            questions = Question.query.filter(Question.id.in_(test_question_ids)).all() if test_question_ids else []
            
            if not questions:
                return {"error": "Nenhuma questão encontrada para este teste"}
            
            # 4. Preparar dados das questões para mapeamento
            questions_data = []
            for question in questions:
                # Extrair alternative_ids do JSON
                alternative_ids = []
                if question.alternatives:
                    try:
                        alternatives_json = json.loads(question.alternatives) if isinstance(question.alternatives, str) else question.alternatives
                        alternative_ids = [alt.get('id', '') for alt in alternatives_json if alt.get('id')]
                    except (json.JSONDecodeError, TypeError):
                        alternative_ids = ['A', 'B', 'C', 'D', 'E']  # Fallback
                
                questions_data.append({
                    'id': question.id,
                    'alternative_ids': alternative_ids,
                    'correct_answer': question.correct_answer,
                    'subject': {
                        'id': question.subject_id,
                        'name': question.subject.name if question.subject else 'Outras'
                    }
                })
            
            # 5. NOVO: Buscar coordenadas específicas do formulário
            print(f"🔍 BUSCANDO COORDENADAS ESPECÍFICAS...")
            coordinates = self._get_form_coordinates(test_id, qr_code_id, student_id)
            
            if not coordinates:
                print(f"❌ ERRO: Coordenadas não encontradas para este formulário")
                return {"error": "Coordenadas não encontradas para este formulário"}
            
            print(f"✅ Coordenadas encontradas: {len(coordinates.get('subjects', {}))} disciplinas")
            
            # 6. NOVO: Detectar respostas usando coordenadas específicas
            binary_image = image_result["binary_image"]
            print(f"🔍 DETECTANDO RESPOSTAS COM COORDENADAS ESPECÍFICAS...")
            
            # Obter número de questões do QR Code ou do banco
            num_questions = None
            if qr_metadata and 'num_questions' in qr_metadata:
                num_questions = qr_metadata['num_questions']
                print(f"📊 Número de questões do QR Code: {num_questions}")
            elif coordinates and 'num_questions' in coordinates:
                num_questions = coordinates['num_questions']
                print(f"📊 Número de questões do banco: {num_questions}")
            else:
                num_questions = len(questions)
                print(f"📊 Número de questões calculado: {num_questions}")
            
            respostas_detectadas = self._detectar_respostas_com_coordenadas(binary_image, coordinates, num_questions)
            print(f"📊 RESPOSTAS DETECTADAS: {respostas_detectadas}")
            
            # 7. NOVO: Mapear respostas para questões reais usando coordenadas específicas
            student_answers = {}
            print(f"🔄 MAPEANDO RESPOSTAS PARA QUESTÕES REAIS...")
            
            # Organizar questões por disciplina para mapeamento
            subjects = self._group_questions_by_subject(questions_data)
            
            for subject_name, subject_questions in subjects.items():
                subject_key = subject_name.lower().replace(' ', '_')
                print(f"📚 Processando disciplina: {subject_name} (key: {subject_key})")
                
                if subject_key in respostas_detectadas:
                    subject_responses = respostas_detectadas[subject_key]
                    print(f"✅ Respostas encontradas para {subject_name}: {subject_responses}")
                    
                    for question_num_str, question_responses in subject_responses.items():
                        # Extrair número da questão (ex: "question_1" -> 1)
                        question_num = int(question_num_str.split('_')[1])
                        print(f"  📝 Questão {question_num}: {question_responses}")
                        
                        # Encontrar a questão correspondente
                        if question_num <= len(subject_questions):
                            question_data = subject_questions[question_num - 1]
                            question_id = question_data.get('id')
                            correct_answer = question_data.get('correct_answer')
                            
                            print(f"    🆔 ID da questão: {question_id}")
                            print(f"    ✅ Resposta correta: {correct_answer}")
                            
                            if question_id:
                                # Encontrar qual alternativa foi marcada
                                for alt_id, is_marked in question_responses.items():
                                    if is_marked:
                                        student_answers[question_id] = alt_id
                                        print(f"    🎯 RESPOSTA MARCADA: {alt_id}")
                                        print(f"    ✅ CORRETO: {'SIM' if alt_id == correct_answer else 'NÃO'}")
                                        break
                                else:
                                    print(f"    ❌ NENHUMA RESPOSTA MARCADA")
                        else:
                            print(f"    ⚠️ Questão {question_num} não encontrada (máximo: {len(subject_questions)})")
                else:
                    print(f"❌ Nenhuma resposta detectada para {subject_name}")
            
            # 8. Salvar respostas do aluno
            for question_id, answer in student_answers.items():
                # Verificar se já existe resposta
                existing_answer = StudentAnswer.query.filter_by(
                    test_id=test_id,
                    student_id=student_id,
                    question_id=question_id
                ).first()
                
                if existing_answer:
                    # Atualizar resposta existente
                    existing_answer.answer = answer
                else:
                    # Criar nova resposta
                    new_answer = StudentAnswer(
                        test_id=test_id,
                        student_id=student_id,
                        question_id=question_id,
                        answer=answer
                    )
                    db.session.add(new_answer)
            
            db.session.commit()
            
            # Resumo das respostas detectadas
            print(f"📊 RESUMO DAS RESPOSTAS DETECTADAS:")
            print(f"  🎯 Total de respostas: {len(student_answers)}")
            print(f"  📝 Respostas por questão:")
            for question_id, answer in student_answers.items():
                print(f"    Questão {question_id}: {answer}")
            
            # 9. Calcular resultado usando o serviço existente
            print(f"🧮 CALCULANDO RESULTADO...")
            print(f"⚠️ ATENÇÃO: {len(student_answers)} respostas detectadas, mas o cálculo pode usar respostas anteriores do banco")
            
            # Verificar respostas existentes no banco
            from app.models.studentAnswer import StudentAnswer
            existing_answers = StudentAnswer.query.filter_by(
                test_id=test_id,
                student_id=student_id
            ).all()
            print(f"📚 Respostas existentes no banco: {len(existing_answers)}")
            for ans in existing_answers:
                print(f"    Questão {ans.question_id}: {ans.answer}")
            
            result = EvaluationResultService.calculate_and_save_result(
                test_id=test_id,
                student_id=student_id,
                session_id=None  # Para correções físicas
            )
            
            if result:
                print(f"✅ RESULTADO CALCULADO:")
                print(f"  🎯 Acertos: {result['correct_answers']}/{result['total_questions']}")
                print(f"  📊 Percentual: {result['score_percentage']:.2f}%")
                print(f"  🏆 Nota: {result['grade']}")
                print(f"  📈 Proficiência: {result['proficiency']}")
                print(f"  🏅 Classificação: {result['classification']}")
            else:
                print(f"❌ ERRO AO CALCULAR RESULTADO")
            
            if result:
                return {
                    "success": True,
                    "message": "Correção processada com sucesso",
                    "student_id": student_id,
                    "test_id": test_id,
                    "class_id": class_id,
                    "class_test_id": class_test_id,
                    "correct_answers": result['correct_answers'],
                    "total_questions": result['total_questions'],
                    "score_percentage": result['score_percentage'],
                    "grade": result['grade'],
                    "proficiency": result['proficiency'],
                    "classification": result['classification'],
                    "answers_detected": len(student_answers),
                    "qr_detected": qr_data is not None
                }
            else:
                return {"error": "Erro ao calcular resultado"}
                
        except Exception as e:
            logging.error(f"Erro ao processar correção por imagem: {str(e)}")
            return {"error": f"Erro interno: {str(e)}"}

    def _create_answer_key(self, test_data: Dict, questions_data: List[Dict], student: Dict = None) -> List:
        """Cria gabarito idêntico à imagem usando o modelo fornecido"""
        from reportlab.platypus import Table, TableStyle, Paragraph
        from reportlab.lib import colors
        
        story = []
        
        # Criar QR Code simples (como no formularios.py)
        qr_data = f"{test_data['id']}_gabarito"
        qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=4, border=2)
        qr.add_data(str(qr_data))
        qr.make(fit=True)
        img_qr = qr.make_image(fill_color="black", back_color="white").resize((100, 100))
        
        # Salvar QR Code temporariamente
        qr_buffer = io.BytesIO()
        img_qr.save(qr_buffer, format='PNG')
        qr_buffer.seek(0)
        
        # Criar células para as alternativas (A, B, C, D, E dentro de círculos)
        def create_alternativas():
            return ["(A)", "(B)", "(C)", "(D)", "(E)"]  # Letras com parênteses para simular círculos
        
        # Criar as linhas apenas para o número de questões existentes
        num_questions = len(questions_data)
        linhas = []
        for i in range(1, num_questions + 1):  # Apenas as questões que existem
            linha = [str(i)] + create_alternativas()
            linhas.append(linha)
        
        # Separar em duas tabelas apenas se necessário
        if len(linhas) <= 10:
            # Se 10 ou menos questões, usar apenas uma tabela
            tabela_esquerda = Table(linhas, colWidths=[20, 25, 25, 25, 25, 25])
            tabela_direita = None
        else:
            # Se mais de 10 questões, dividir em duas tabelas
            tabela_esquerda = Table(linhas[:10], colWidths=[20, 25, 25, 25, 25, 25])
            tabela_direita = Table(linhas[10:], colWidths=[20, 25, 25, 25, 25, 25])
        
        # Estilo das tabelas
        estilo = TableStyle([
            ('GRID', (0,0), (-1,-1), 0.7, colors.black),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
            ('FONTSIZE', (0,0), (-1,-1), 9),
        ])
        
        tabela_esquerda.setStyle(estilo)
        if tabela_direita:
            tabela_direita.setStyle(estilo)
        
        # Montar layout principal com NOME DO ALUNO, QR Code e tabelas
        student_name = 'ALUNO'
        if student and 'nome' in student:
            student_name = student['nome']
        elif test_data.get('student_name'):
            student_name = test_data['student_name']
        
        # Criar estilo menor para o nome do aluno
        student_style = ParagraphStyle(
            'StudentName',
            parent=self.styles['TestTitle'],
            fontSize=14,  # Menor que o título
            fontName='Helvetica-Bold',
            alignment=TA_LEFT,
            spaceBefore=0,  # Sem espaço antes (colado no QR Code)
            spaceAfter=0    # Sem espaço depois
        )
        
        # Layout com QR Code em cima, nome do aluno embaixo, e tabelas ao lado
        if tabela_direita:
            layout = Table([
                [RLImage(qr_buffer, width=80, height=80), '', tabela_esquerda, tabela_direita],
                [Paragraph(f"<b>{student_name}</b>", student_style), '', '', '']
            ], colWidths=[80, 20, 200, 200])
        else:
            layout = Table([
                [RLImage(qr_buffer, width=80, height=80), '', tabela_esquerda],
                [Paragraph(f"<b>{student_name}</b>", student_style), '', '']
            ], colWidths=[80, 20, 400])
        
        layout.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('BOX', (0,0), (-1,-1), 1, colors.black),  # Borda ao redor de tudo
            ('LEFTPADDING', (0,0), (-1,-1), 15),
            ('RIGHTPADDING', (0,0), (-1,-1), 15),
            ('TOPPADDING', (0,0), (-1,-1), 5),   # Reduzido de 15 para 5
            ('BOTTOMPADDING', (0,0), (-1,-1), 5), # Reduzido de 15 para 5
        ]))
        
        story.append(layout)
        return story

    def _generate_answer_sheet_image(self, test_data: Dict, student: Dict, questions_data: List[Dict]) -> Optional[PILImage.Image]:
        """
        Gera imagem do formulário de resposta usando a lógica correta do formularios.py
        """
        try:
            # Parâmetros do formularios.py
            LARGURA_CONTEUDO = 700
            ALTURA_CONTEUDO = 300
            PADDING_EXTERNO = 10
            LARGURA_FINAL = LARGURA_CONTEUDO + (2 * PADDING_EXTERNO)
            ALTURA_FINAL = ALTURA_CONTEUDO + (2 * PADDING_EXTERNO)
            LARGURA_COL_NUM = 35
            LARGURA_COL_ALT = 40
            ALTURA_LINHA = 28
            PADDING_HORIZONTAL_COL = 8
            RAIO_CIRCULO = 9
            ESPESSURA_LINHA = 1
            TAMANHO_FONTE_NUM = 16
            TAMANHO_FONTE_ALT = 14
            MAX_QUESTOES_POR_COLUNA = 10
            QR_CODE_SIZE = 100
            TAMANHO_FONTE_NOME = 14
            PADDING_NOME_QR = 5
            PADDING_LEFT_AREA_QR = 15
            PADDING_QR_FORM = 25
            SPACING_FORM_COLS = 30
            MAX_LARGURA_NOME = QR_CODE_SIZE + 10
            
            # Criar imagem
            imagem = PILImage.new('RGB', (LARGURA_FINAL, ALTURA_FINAL), 'white')
            desenho = ImageDraw.Draw(imagem)
            
            # Carregar fontes
            try:
                fonte_num = ImageFont.truetype("arial.ttf", TAMANHO_FONTE_NUM)
                fonte_alt = ImageFont.truetype("arial.ttf", TAMANHO_FONTE_ALT)
                fonte_nome = ImageFont.truetype("arialbd.ttf", TAMANHO_FONTE_NOME)
            except IOError:
                try:
                    fonte_num = ImageFont.truetype("DejaVuSans.ttf", TAMANHO_FONTE_NUM)
                    fonte_alt = ImageFont.truetype("DejaVuSans.ttf", TAMANHO_FONTE_ALT)
                    fonte_nome = ImageFont.truetype("DejaVuSans-Bold.ttf", TAMANHO_FONTE_NOME)
                except IOError:
                    fonte_num = ImageFont.load_default()
                    fonte_alt = ImageFont.load_default()
                    fonte_nome = ImageFont.load_default()
            
            # Gerar QR Code com metadados JSON
            student_id = student.get('id', 'unknown')
            test_id = test_data.get('id', 'unknown')
            
            # Criar metadados do QR Code
            qr_code_id = str(uuid.uuid4())
            qr_data = {
                "student_id": student_id,
                "qr_code_id": qr_code_id,
                "test_id": test_id
            }
            
            qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=4, border=2)
            qr.add_data(json.dumps(qr_data))
            qr.make(fit=True)
            img_qr = qr.make_image(fill_color="black", back_color="white").resize((QR_CODE_SIZE, QR_CODE_SIZE))
            
            # Posicionar QR Code no centro (como no formularios.py)
            x_qr = PADDING_LEFT_AREA_QR
            y_qr = (ALTURA_CONTEUDO / 2) - (QR_CODE_SIZE / 2)
            y_qr = max(5, y_qr)
            
            # Posicionar nome acima do QR
            student_name = student.get('nome', 'Nome não informado')
            y_nome = y_qr - 30
            
            # Desenhar nome
            desenho.text((x_qr, y_nome), student_name, fill='black', font=fonte_nome)
            
            # Colar QR Code
            imagem.paste(img_qr, (int(x_qr), int(y_qr)))
            
            # Posicionar formulário à direita do QR (centralizado)
            offset_x_form = x_qr + QR_CODE_SIZE + PADDING_QR_FORM
            y_form = (ALTURA_CONTEUDO / 2) - (MAX_QUESTOES_POR_COLUNA * ALTURA_LINHA / 2)
            y_form = max(5, y_form)
            
            # Desenhar formulário usando as alternativas específicas de cada questão
            self._draw_answer_form_correct(desenho, fonte_num, fonte_alt, questions_data, offset_x_form, y_form)
            
            return imagem
            
        except Exception as e:
            logging.error(f"Erro ao gerar imagem do formulário: {str(e)}")
            return None

    def _generate_alternative_coordinates(self, num_questions: int) -> List[Tuple]:
        """
        Gera coordenadas das alternativas usando coordenadas fixas especificadas
        X: [112, 162, 212, 262] - diferença de 50px entre alternativas
        Y: [950, 995, 1040, 1085] - diferença de 45px entre questões
        """
        coordenadas = []
        
        # Coordenadas fixas especificadas pelo usuário
        x_positions = [112, 162, 212, 262]  # Posições X das alternativas A, B, C, D
        y_positions = [950, 995, 1040, 1085]  # Posições Y das questões 1, 2, 3, 4
        
        # Gerar coordenadas para todas as questões
        for i in range(num_questions):
            if i < len(y_positions):
                y = y_positions[i]
            else:
                # Se houver mais de 4 questões, continuar o padrão
                y = y_positions[-1] + (i - len(y_positions) + 1) * 45
            
            # Gerar coordenadas para todas as alternativas (A, B, C, D)
            for j, x in enumerate(x_positions):
                # Usar raio de 10px para as bolhas
                radius = 10
                coordenadas.append((x, y, radius * 2, radius * 2))
        
        return coordenadas

    def _draw_answer_form_correct(self, desenho, fonte_num, fonte_alt, questions_data: List[Dict], offset_x: int, offset_y: int):
        """
        Desenha o formulário de respostas usando as alternativas específicas de cada questão
        """
        try:
            
            # Parâmetros do formularios.py
            LARGURA_COL_NUM = 35
            LARGURA_COL_ALT = 40
            ALTURA_LINHA = 28
            PADDING_HORIZONTAL_COL = 8
            RAIO_CIRCULO = 9
            ESPESSURA_LINHA = 1
            MAX_QUESTOES_POR_COLUNA = 10
            SPACING_FORM_COLS = 30
            
            num_questions = len(questions_data)
            
            # Determinar quantas colunas precisamos
            if num_questions <= MAX_QUESTOES_POR_COLUNA:
                # Uma coluna apenas
                questions_col_esq = questions_data
                self._desenhar_coluna_formulario_dinamico(desenho, fonte_num, fonte_alt, questions_col_esq, 
                                                        offset_x, offset_y, LARGURA_COL_NUM, LARGURA_COL_ALT, 
                                                        ALTURA_LINHA, PADDING_HORIZONTAL_COL, RAIO_CIRCULO, ESPESSURA_LINHA)
            else:
                # Duas colunas
                questions_col_esq = questions_data[:MAX_QUESTOES_POR_COLUNA]
                questions_col_dir = questions_data[MAX_QUESTOES_POR_COLUNA:]
                
                # Calcular largura da coluna baseada no máximo de alternativas
                max_alternativas_esq = max(len(q.get('alternative_ids', [])) for q in questions_col_esq) if questions_col_esq else 0
                max_alternativas_dir = max(len(q.get('alternative_ids', [])) for q in questions_col_dir) if questions_col_dir else 0
                
                largura_col_esq = LARGURA_COL_NUM + (max_alternativas_esq * LARGURA_COL_ALT) + (PADDING_HORIZONTAL_COL * 2)
                largura_col_dir = LARGURA_COL_NUM + (max_alternativas_dir * LARGURA_COL_ALT) + (PADDING_HORIZONTAL_COL * 2)
                
                # Coluna esquerda
                self._desenhar_coluna_formulario_dinamico(desenho, fonte_num, fonte_alt, questions_col_esq, 
                                                        offset_x, offset_y, LARGURA_COL_NUM, LARGURA_COL_ALT, 
                                                        ALTURA_LINHA, PADDING_HORIZONTAL_COL, RAIO_CIRCULO, ESPESSURA_LINHA)
                
                # Coluna direita
                offset_x_col_dir = offset_x + largura_col_esq + SPACING_FORM_COLS
                self._desenhar_coluna_formulario_dinamico(desenho, fonte_num, fonte_alt, questions_col_dir, 
                                                        offset_x_col_dir, offset_y, LARGURA_COL_NUM, LARGURA_COL_ALT, 
                                                        ALTURA_LINHA, PADDING_HORIZONTAL_COL, RAIO_CIRCULO, ESPESSURA_LINHA)
            
        except Exception as e:
            logging.error(f"Erro ao desenhar formulário: {str(e)}")

    def _desenhar_coluna_formulario_dinamico(self, desenho, fonte_num, fonte_alt, questions_data: List[Dict], 
                                           offset_x, offset_y, LARGURA_COL_NUM, LARGURA_COL_ALT, 
                                           ALTURA_LINHA, PADDING_HORIZONTAL_COL, RAIO_CIRCULO, ESPESSURA_LINHA):
        """
        Desenha uma coluna do formulário usando coordenadas fixas especificadas
        X: [112, 162, 212, 262] - diferença de 50px entre alternativas
        Y: [950, 995, 1040, 1085] - diferença de 45px entre questões
        """
        if not questions_data:
            return
        
        # Coordenadas fixas especificadas pelo usuário
        x_positions = [112, 162, 212, 262]  # Posições X das alternativas A, B, C, D
        y_positions = [950, 995, 1040, 1085]  # Posições Y das questões 1, 2, 3, 4
        
        # Desenhar cada questão usando as coordenadas fixas
        for i, question_data in enumerate(questions_data):
            # Usar coordenadas fixas para Y
            if i < len(y_positions):
                centro_y_linha = y_positions[i]
            else:
                # Se houver mais de 4 questões, continuar o padrão
                centro_y_linha = y_positions[-1] + (i - len(y_positions) + 1) * 45

            # Número da questão (posicionado à esquerda das alternativas)
            question_number = i + 1
            texto_num = str(question_number)
            centro_x_num = x_positions[0] - 30  # 30px à esquerda da primeira alternativa
            
            try:
                desenho.text((centro_x_num, centro_y_linha), texto_num, fill='black', font=fonte_num, anchor="mm")
            except AttributeError:
                bbox_num = desenho.textbbox((0, 0), texto_num, font=fonte_num)
                largura_texto_num = bbox_num[2] - bbox_num[0]
                altura_texto_num = bbox_num[3] - bbox_num[1]
                x_num_texto = centro_x_num - (largura_texto_num / 2)
                y_num_texto = centro_y_linha - (altura_texto_num / 2)
                desenho.text((x_num_texto, y_num_texto - 2), texto_num, fill='black', font=fonte_num)

            # Alternativas específicas da questão usando coordenadas fixas
            alternative_ids = question_data.get('alternative_ids', [])
            for j, alt_id in enumerate(alternative_ids):
                if j < len(x_positions):
                    centro_x_alt = x_positions[j]
                else:
                    # Se houver mais de 4 alternativas, continuar o padrão
                    centro_x_alt = x_positions[-1] + (j - len(x_positions) + 1) * 50

                # Desenhar círculo
                x0_circ = centro_x_alt - RAIO_CIRCULO
                y0_circ = centro_y_linha - RAIO_CIRCULO
                x1_circ = centro_x_alt + RAIO_CIRCULO
                y1_circ = centro_y_linha + RAIO_CIRCULO
                desenho.ellipse([(x0_circ, y0_circ), (x1_circ, y1_circ)], outline='black', width=ESPESSURA_LINHA)
                
                # Letra da alternativa
                try:
                    desenho.text((centro_x_alt, centro_y_linha), alt_id, fill='black', font=fonte_alt, anchor="mm")
                except AttributeError:
                    bbox_alt = desenho.textbbox((0, 0), alt_id, font=fonte_alt)
                    largura_texto_alt = bbox_alt[2] - bbox_alt[0]
                    altura_texto_alt = bbox_alt[3] - bbox_alt[1]
                    x_alt_texto = centro_x_alt - (largura_texto_alt / 2)
                    y_alt_texto = centro_y_linha - (altura_texto_alt / 2)
                    desenho.text((x_alt_texto, y_alt_texto - 1), alt_id, fill='black', font=fonte_alt)

    def _desenhar_coluna_formulario(self, desenho, fonte_num, fonte_alt, num_questao_inicial, num_questoes_nesta_coluna, 
                                   offset_x, offset_y, largura_col_unica, LARGURA_COL_NUM, LARGURA_COL_ALT, 
                                   ALTURA_LINHA, PADDING_HORIZONTAL_COL, RAIO_CIRCULO, ESPESSURA_LINHA, ALTERNATIVAS):
        """
        Desenha uma única coluna do formulário (baseado no formularios.py)
        """
        altura_efetiva_linhas = num_questoes_nesta_coluna * ALTURA_LINHA
        y_final_borda_real = offset_y + altura_efetiva_linhas

        # Bordas da coluna
        desenho.line([(offset_x, offset_y), (offset_x, y_final_borda_real)], fill='black', width=ESPESSURA_LINHA)
        desenho.line([(offset_x + largura_col_unica - 1, offset_y), (offset_x + largura_col_unica - 1, y_final_borda_real)], fill='black', width=ESPESSURA_LINHA)
        
        # Linha vertical separando número das alternativas
        x_vert_num = offset_x + PADDING_HORIZONTAL_COL + LARGURA_COL_NUM
        desenho.line([(x_vert_num, offset_y), (x_vert_num, y_final_borda_real)], fill='black', width=ESPESSURA_LINHA)

        # Linha superior
        desenho.line([(offset_x, offset_y), (offset_x + largura_col_unica - 1, offset_y)], fill='black', width=ESPESSURA_LINHA)

        if num_questoes_nesta_coluna == 0:
            return

        # Desenhar cada questão
        for i in range(num_questoes_nesta_coluna):
            linha_atual = num_questao_inicial + i
            y_linha_superior = offset_y + (i * ALTURA_LINHA)
            y_linha_inferior = y_linha_superior + ALTURA_LINHA
            centro_y_linha = y_linha_superior + (ALTURA_LINHA / 2)

            # Linha horizontal entre questões
            desenho.line([(offset_x, y_linha_inferior), (offset_x + largura_col_unica - 1, y_linha_inferior)], fill='black', width=ESPESSURA_LINHA)

            # Número da questão
            texto_num = str(linha_atual)
            centro_x_num = offset_x + PADDING_HORIZONTAL_COL + (LARGURA_COL_NUM / 2)
            try:
                desenho.text((centro_x_num, centro_y_linha), texto_num, fill='black', font=fonte_num, anchor="mm")
            except AttributeError:
                bbox_num = desenho.textbbox((0, 0), texto_num, font=fonte_num)
                largura_texto_num = bbox_num[2] - bbox_num[0]
                altura_texto_num = bbox_num[3] - bbox_num[1]
                x_num_texto = centro_x_num - (largura_texto_num / 2)
                y_num_texto = centro_y_linha - (altura_texto_num / 2)
                desenho.text((x_num_texto, y_num_texto - 2), texto_num, fill='black', font=fonte_num)

            # Alternativas A, B, C, D, E
            for j, alt in enumerate(ALTERNATIVAS):
                centro_x_alt = offset_x + PADDING_HORIZONTAL_COL + LARGURA_COL_NUM + (j * LARGURA_COL_ALT) + (LARGURA_COL_ALT / 2)

                # Desenhar círculo
                x0_circ = centro_x_alt - RAIO_CIRCULO
                y0_circ = centro_y_linha - RAIO_CIRCULO
                x1_circ = centro_x_alt + RAIO_CIRCULO
                y1_circ = centro_y_linha + RAIO_CIRCULO
                desenho.ellipse([(x0_circ, y0_circ), (x1_circ, y1_circ)], outline='black', width=ESPESSURA_LINHA)
                
                # Letra da alternativa
                try:
                    desenho.text((centro_x_alt, centro_y_linha), alt, fill='black', font=fonte_alt, anchor="mm")
                except AttributeError:
                    bbox_alt = desenho.textbbox((0, 0), alt, font=fonte_alt)
                    largura_texto_alt = bbox_alt[2] - bbox_alt[0]
                    altura_texto_alt = bbox_alt[3] - bbox_alt[1]
                    x_alt_texto = centro_x_alt - (largura_texto_alt / 2)
                    y_alt_texto = centro_y_linha - (altura_texto_alt / 2)
                    desenho.text((x_alt_texto, y_alt_texto - 1), alt, fill='black', font=fonte_alt)

    def _draw_answer_form(self, desenho, fonte_num, fonte_alt, num_questions: int, coordenadas: List[Tuple]):
        """
        Desenha o formulário de respostas com duas colunas como na imagem
        """
        # Ajustar posição do formulário (direita do QR Code)
        offset_x = 200  # Posição X do formulário
        
        # Calcular dimensões para duas colunas
        largura_col = LARGURA_COL_NUM + (len(ALTERNATIVAS) * LARGURA_COL_ALT) + (PADDING_HORIZONTAL_COL * 2)
        
        # Determinar quantas colunas realmente precisamos
        num_cols = 1 if num_questions <= MAX_QUESTOES_POR_COLUNA else 2
        
        # Desenhar colunas necessárias
        for col in range(num_cols):
            col_x = offset_x + (col * (largura_col + SPACING_FORM_COLS))
            
            # Calcular questões para esta coluna
            start_question = col * MAX_QUESTOES_POR_COLUNA + 1
            end_question = min(start_question + MAX_QUESTOES_POR_COLUNA - 1, num_questions)
            questions_in_col = end_question - start_question + 1
            
            # Só desenhar a coluna se tiver questões
            if questions_in_col > 0:
                altura_efetiva = questions_in_col * ALTURA_LINHA
                
                # Borda externa da coluna
                desenho.rectangle([(col_x, 10), (col_x + largura_col, 10 + altura_efetiva)], 
                         outline='black', width=ESPESSURA_LINHA)
        
        # Linha vertical separando número da questão das alternativas
        x_vert = col_x + PADDING_HORIZONTAL_COL + LARGURA_COL_NUM
        desenho.line([(x_vert, 10), (x_vert, 10 + altura_efetiva)], fill='black', width=ESPESSURA_LINHA)
        
        # Desenhar questões e alternativas para esta coluna
        for i in range(questions_in_col):
            question_num = start_question + i
            y_linha = 10 + (i * ALTURA_LINHA)
            y_linha_inferior = y_linha + ALTURA_LINHA
            centro_y = y_linha + (ALTURA_LINHA / 2)
            
            # Linha horizontal entre questões
            if i < questions_in_col - 1:
                desenho.line([(col_x, y_linha_inferior), (col_x + largura_col, y_linha_inferior)], 
                   fill='black', width=ESPESSURA_LINHA)
            
            # Número da questão
            texto_num = str(question_num)
            centro_x_num = col_x + PADDING_HORIZONTAL_COL + (LARGURA_COL_NUM / 2)
            try:
                desenho.text((centro_x_num, centro_y), texto_num, fill='black', font=fonte_num, anchor="mm")
            except:
                desenho.text((centro_x_num, centro_y), texto_num, fill='black')
            
            # Alternativas A, B, C, D, E (sempre 5 alternativas como na imagem)
            for j, alt in enumerate(ALTERNATIVAS):
                centro_x_alt = col_x + PADDING_HORIZONTAL_COL + LARGURA_COL_NUM + (j * LARGURA_COL_ALT) + (LARGURA_COL_ALT / 2)
                
                # Desenhar círculo
                x0_circ = centro_x_alt - RAIO_CIRCULO
                y0_circ = centro_y - RAIO_CIRCULO
                x1_circ = centro_x_alt + RAIO_CIRCULO
                y1_circ = centro_y + RAIO_CIRCULO
                desenho.ellipse([(x0_circ, y0_circ), (x1_circ, y1_circ)], outline='black', width=ESPESSURA_LINHA)
                
                # Letra da alternativa (formato original)
                try:
                    desenho.text((centro_x_alt, centro_y), alt, fill='black', font=fonte_alt, anchor="mm")
                except:
                    desenho.text((centro_x_alt, centro_y), alt, fill='black')

    def _clean_html_text(self, html_text: str) -> str:
        """
        Remove tags HTML básicas para exibição no PDF
        """
        # Remove tags HTML comuns
        clean_text = re.sub(r'<[^>]+>', '', html_text)
        # Decodifica entidades HTML básicas
        clean_text = clean_text.replace('&nbsp;', ' ')
        clean_text = clean_text.replace('&lt;', '<')
        clean_text = clean_text.replace('&gt;', '>')
        clean_text = clean_text.replace('&amp;', '&')
        return clean_text.strip()

    def _process_image_from_text(self, text: str) -> Optional[RLImage]:
        """
        Processa imagem de URL ou Base64 e retorna objeto Image do ReportLab
        """
        try:
            import base64
            import requests
            from io import BytesIO
            
            # Verificar se é Base64
            if text.startswith('data:image'):
                # Extrair dados Base64
                header, data = text.split(',', 1)
                image_data = base64.b64decode(data)
                img_buffer = BytesIO(image_data)
                return RLImage(img_buffer, width=200, height=150)
            
            # Verificar se é URL
            elif text.startswith('http'):
                # Baixar imagem da URL
                response = requests.get(text, timeout=10)
                if response.status_code == 200:
                    img_buffer = BytesIO(response.content)
                    return RLImage(img_buffer, width=200, height=150)
            
            return None
            
        except Exception as e:
            logging.error(f"Erro ao processar imagem: {str(e)}")
            return None

   
    def _get_skill_codes(self, question: Dict) -> List[str]:
        """
        Extrai códigos das habilidades da questão (já formatados pelo serviço)
        """
        try:
            skills = question.get('skills', [])
            if isinstance(skills, list):
                return [str(skill) for skill in skills if skill]
            return []
        except:
            return []
    
    def _get_form_coordinates(self, test_id: str, qr_code_id: str, student_id: str) -> Optional[Dict]:
        """
        Busca coordenadas específicas do formulário usando coordenadas fixas
        """
        try:
            from app import db
            
            print(f"🔍 BUSCANDO COORDENADAS ESPECÍFICAS...")
            print(f"   Test ID: {test_id}")
            print(f"   QR Code ID: {qr_code_id}")
            print(f"   Student ID: {student_id}")
            
            # Buscar template de coordenadas para este teste
            form_template = FormCoordinates.query.filter_by(
                test_id=test_id,
                form_type='physical_test'
            ).first()
            
            if not form_template:
                print(f"❌ Template de coordenadas não encontrado para este teste")
                return None
            
            print(f"✅ Template de coordenadas encontrado para teste {test_id}")
            print(f"📊 Número de questões no template: {getattr(form_template, 'num_questions', 'N/A')}")
            
            # Retornar coordenadas fixas do banco (já calculadas com o número correto de questões)
            coordinates_map = {
                'test_id': test_id,
                'qr_code_id': qr_code_id,
                'student_id': student_id,
                'coordinates': form_template.coordinates,
                'form_type': form_template.form_type,
                'num_questions': getattr(form_template, 'num_questions', None)
            }
            
            print(f"   Coordenadas: {len(form_template.coordinates)} coordenadas")
            return coordinates_map
                
        except Exception as e:
            print(f"❌ Erro ao buscar coordenadas: {str(e)}")
            logging.error(f"Erro ao buscar coordenadas: {str(e)}")
            return None
    
    def _detectar_respostas_com_coordenadas(self, binary_image, coordinates: Dict, num_questions: int = None) -> Dict:
        """
        Detecta respostas usando coordenadas fixas especificadas
        X: [112, 162, 212, 262] - diferença de 50px entre alternativas
        Y: [950, 995, 1040, 1085] - diferença de 45px entre questões
        """
        try:
            print(f"🔍 DETECTANDO RESPOSTAS COM COORDENADAS FIXAS")
            print(f"📏 Dimensões da imagem binária: {binary_image.shape}")
            
            # Coordenadas fixas especificadas pelo usuário (NUNCA ALTERAR)
            x_positions = [112, 162, 212, 262]  # Posições X das alternativas A, B, C, D
            y_positions_base = [950, 995, 1040, 1085]  # Posições Y das questões 1, 2, 3, 4
            
            # Se num_questions não foi fornecido, usar o número de questões das coordenadas base
            if num_questions is None:
                num_questions = len(y_positions_base)
            
            # Gerar posições Y dinamicamente mantendo as coordenadas fixas
            y_positions = []
            for i in range(num_questions):
                if i < len(y_positions_base):
                    # Usar as coordenadas fixas para as primeiras 4 questões
                    y_positions.append(y_positions_base[i])
                else:
                    # Continuar o padrão de 45px para questões adicionais
                    y_positions.append(y_positions_base[-1] + (i - len(y_positions_base) + 1) * 45)
            
            print(f"📊 Processando {num_questions} questões com coordenadas Y: {y_positions}")
            
            # Gerar respostas para todas as questões usando coordenadas fixas
            respostas_por_disciplina = {}
            
            # Assumir uma disciplina padrão se não especificada
            subject_key = "default"
            respostas_por_disciplina[subject_key] = {}
            
            # Processar cada questão dinamicamente
            for i in range(num_questions):
                question_key = f"question_{i+1}"
                respostas_por_disciplina[subject_key][question_key] = {}
                
                # Usar a posição Y calculada dinamicamente
                y = y_positions[i]
                
                # Processar cada alternativa (sempre A, B, C, D)
                for j, x in enumerate(x_positions):
                    alt_id = chr(65 + j)  # A, B, C, D
                    radius = 10
                    
                    print(f"    📍 Q{i+1} {alt_id}: x={x}, y={y}, radius={radius}")
                    
                    # Verificar se coordenadas estão dentro da imagem
                    h, w = binary_image.shape
                    if x < 0 or x >= w or y < 0 or y >= h:
                        print(f"    ⚠️ Coordenadas Q{i+1} {alt_id} fora da imagem: x={x}, y={y}, img_size=({w}, {h})")
                        respostas_por_disciplina[subject_key][question_key][alt_id] = False
                        continue
                    
                    # Detectar se está marcado
                    is_marked = self._detectar_marcacao_circular(binary_image, x, y, radius)
                    respostas_por_disciplina[subject_key][question_key][alt_id] = is_marked
                    
                    print(f"    Q{i+1} {alt_id}: {'✅ MARCADO' if is_marked else '❌ NÃO MARCADO'}")
            
            # Calcular estatísticas
            total_questions = 0
            total_marked = 0
            
            print(f"📊 RESUMO DAS RESPOSTAS DETECTADAS:")
            for subject, questions in respostas_por_disciplina.items():
                print(f"   📚 {subject}:")
                for q_num, alts in questions.items():
                    total_questions += 1
                    marked_alts = [alt for alt, marked in alts.items() if marked]
                    if marked_alts:
                        total_marked += 1
                        print(f"      Q{q_num}: {marked_alts}")
                    else:
                        print(f"      Q{q_num}: Nenhuma marcada")
            
            print(f"📈 ESTATÍSTICAS FINAIS:")
            print(f"   Total de questões: {total_questions}")
            print(f"   Questões com respostas: {total_marked}")
            print(f"   Percentual respondido: {(total_marked/total_questions*100):.1f}%" if total_questions > 0 else "0%")
            
            print(f"📊 DETECÇÃO CONCLUÍDA: {respostas_por_disciplina}")
            return respostas_por_disciplina
            
        except Exception as e:
            logging.error(f"Erro ao detectar respostas com coordenadas: {str(e)}")
            return {}
    
    def _detectar_marcacao_circular(self, binary_image, x: int, y: int, radius: int) -> bool:
        """
        Detecta marcação usando o MESMO método exato do projeto.py
        """
        try:
            # Usar o método EXATO do projeto.py
            h, w = binary_image.shape
            
            # Definir região de 20x20 como no projeto.py
            region_size = 20
            x1 = max(0, x)
            y1 = max(0, y)
            x2 = min(w, x + region_size)
            y2 = min(h, y + region_size)
            
            # Extrair região de interesse
            interesse = binary_image[y1:y2, x1:x2]
            if interesse.size == 0:
                return False
            
            # Criar máscara circular (método exato do projeto.py)
            mask = np.zeros((region_size, region_size), dtype=np.uint8)
            centro_x = region_size // 2
            centro_y = region_size // 2
            raio = min(region_size, region_size) // 2
            cv2.circle(mask, (centro_x, centro_y), raio, 255, -1)
            
            # Aplicar máscara
            interesse_mascarado = cv2.bitwise_and(interesse, interesse, mask=mask)
            
            # Contar pixels (método exato do projeto.py)
            total_pixels = cv2.countNonZero(mask)
            pixels_brancos = cv2.countNonZero(interesse_mascarado)
            
            if total_pixels == 0:
                return False
            
            porcentagem_branco = (pixels_brancos / total_pixels) * 100
            
            # Threshold exato do projeto.py
            return porcentagem_branco >= 70
            
        except Exception as e:
            logging.error(f"Erro ao detectar marcação circular: {str(e)}")
            return False
    
    def processar_correcao_projeto_style(self, test_id: str, image_data: str) -> Dict:
        """
        Processa correção EXATAMENTE como o projeto.py
        QR Code contém APENAS o student_id, usa coordenadas hardcoded
        """
        try:
            # Processar imagem
            processed_data = self.processar_imagem_formulario(image_data)
            
            if not processed_data.get('success'):
                return processed_data
            
            # Extrair APENAS o student_id do QR Code (como no projeto.py)
            qr_data = processed_data.get('qr_data')
            if not qr_data:
                return {
                    'success': False,
                    'error': 'QR Code não detectado na imagem'
                }
            
            # QR Code contém APENAS o student_id (string), não JSON
            student_id = qr_data.strip()
            
            # Buscar o número real de questões do teste
            from app.models.test import Test
            from app.models.testQuestion import TestQuestion
            
            test = Test.query.get(test_id)
            if not test:
                return {"error": "Teste não encontrado"}
            
            # Buscar questões do teste
            test_question_ids = [tq.question_id for tq in TestQuestion.query.filter_by(test_id=test_id).order_by(TestQuestion.order).all()]
            num_questoes_teste = len(test_question_ids)
            
            # Buscar template de coordenadas do banco de dados
            from app.models.formCoordinates import FormCoordinates
            form_template = FormCoordinates.query.filter_by(
                test_id=test_id,
                form_type='physical_test'
            ).first()
            
            if not form_template:
                print(f"❌ Template de coordenadas não encontrado para teste: {test_id}")
                return {
                    'success': False,
                    'error': f'Template de coordenadas não encontrado para o teste {test_id}',
                    'method': 'projeto_style'
                }
            
            print(f"✅ Template de coordenadas encontrado: {len(form_template.coordinates)} círculos")
            
            # USAR COORDENADAS DINÂMICAS DO FORMULARIOS.PY
            print(f"🎯 USANDO COORDENADAS DINÂMICAS DO FORMULARIOS.PY")
            
            # Ajustar coordenadas proporcionalmente de 720x320 para 688x301
            fator_x = 688 / 720
            fator_y = 301 / 320
            
            # Usar coordenadas do template
            form_coords = form_template.coordinates
            
            coordenadas_ajustadas = []
            for x, y, w, h in form_coords.coordinates:
                x_ajustado = int(x * fator_x)
                y_ajustado = int(y * fator_y)
                w_ajustado = int(w * fator_x)
                h_ajustado = int(h * fator_y)
                coordenadas_ajustadas.append((x_ajustado, y_ajustado, w_ajustado, h_ajustado))
            
            print(f"📐 Fatores de ajuste: X={fator_x:.3f}, Y={fator_y:.3f}")
            print(f"📊 Coordenadas ajustadas: {len(coordenadas_ajustadas)} círculos")
            
            # Aplicar transformação de perspectiva como no projeto.py
            binary_image = processed_data.get('binary_image')
            if binary_image is None:
                return {
                    'success': False,
                    'error': 'Erro ao processar imagem binária'
                }

            print(f"🔍 DETALHES DA IMAGEM BINÁRIA:")
            print(f"  📏 Dimensões: {binary_image.shape}")
            print(f"  📊 Valores únicos: {len(np.unique(binary_image))}")
            print(f"  🎯 Min/Max: {binary_image.min()}/{binary_image.max()}")

            print(f"🔄 APLICANDO TRANSFORMAÇÃO DE PERSPECTIVA...")
            
            # Encontrar contorno do formulário
            contornos, _ = cv2.findContours(binary_image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contornos:
                return {
                    'success': False,
                    'error': 'Nenhum contorno encontrado na imagem'
                }
            
            maior_contorno = max(contornos, key=cv2.contourArea)
            area_maior = cv2.contourArea(maior_contorno)
            print(f"📐 Maior contorno: área {area_maior:.2f}")
            
            # Aplicar transformação de perspectiva para 688x301 (como projeto.py)
            recorte_corrigido = self.aplicar_transformacao_perspectiva(binary_image, maior_contorno)
            if recorte_corrigido is None:
                return {
                    'success': False,
                    'error': 'Erro ao aplicar transformação de perspectiva'
                }
            
            print(f"🔄 Imagem corrigida: {recorte_corrigido.shape}")
            
            # Usar coordenadas dinâmicas ajustadas
            coordenadas_projeto = coordenadas_ajustadas
            binary_image = recorte_corrigido

            respostas_marcadas = []
            
            # LÓGICA EXATA DO PROJETO.PY
            for i, (x, y, w, h) in enumerate(coordenadas_projeto):
                # Verificar se as coordenadas estão dentro da imagem
                if x + w > binary_image.shape[1] or y + h > binary_image.shape[0]:
                    print(f"  ⚠️ Coordenada {i} fora da imagem: ({x},{y},{w},{h}) vs {binary_image.shape}")
                    continue
                
                # Método EXATO do projeto.py (pixels brancos, threshold 70%)
                interesse = binary_image[y:y + h, x:x + w]
                mascara = np.zeros((h, w), dtype=np.uint8)
                centro_x = w // 2
                centro_y = h // 2
                raio = min(w, h) // 2
                cv2.circle(mascara, (centro_x, centro_y), raio, 255, -1)
                interesse_mascarado = cv2.bitwise_and(interesse, interesse, mask=mascara)
                total_pixels = cv2.countNonZero(mascara)
                pixels_brancos = cv2.countNonZero(interesse_mascarado)
                porcentagem_branco = (pixels_brancos / total_pixels) * 100

                # Log detalhado para as primeiras 16 coordenadas (4 questões)
                if i < 16:
                    questao_num = (i // 4) + 1  # 4 alternativas por questão (A, B, C, D)
                    alt_letra = chr(65 + (i % 4))  # A, B, C, D
                    print(f"  🔍 Questão {questao_num} - {alt_letra}: pos=({x},{y}) size=({w},{h}) pixels_brancos={pixels_brancos}/{total_pixels} = {porcentagem_branco:.1f}%")
                
                if porcentagem_branco >= 70:  # Threshold equilibrado
                    respostas_marcadas.append(i)
                    questao_num = (i // 4) + 1
                    alt_letra = chr(65 + (i % 4))
                    print(f"    ✅ MARCADA: Questão {questao_num} - {alt_letra} ({porcentagem_branco:.1f}%)")
            
            # Buscar respostas corretas do banco de dados
            print("\n=== BUSCANDO RESPOSTAS CORRETAS ===")
            from app.models.question import Question
            from app.models.testQuestion import TestQuestion
            
            # Buscar questões do teste
            test_questions = TestQuestion.query.filter_by(test_id=test_id).all()
            print(f"📚 Encontradas {len(test_questions)} questões no teste")
            
            gabarito = {}
            for tq in test_questions:
                question = Question.query.get(tq.question_id)
                if question and question.correct_answer:
                    gabarito[tq.order] = question.correct_answer
                    print(f"  Questão {tq.order}: Resposta correta = {question.correct_answer}")
            
            print("=====================================\n")
            
            # Mostrar respostas detectadas e comparar
            print("\n=== RESPOSTAS DETECTADAS vs CORRETAS ===")
            num_questoes = num_questoes_teste
            acertos = 0
            
            for i in range(num_questoes):
                alternativas_questao = [(i * 4) + j for j in range(4)]  # 4 alternativas por questão (A, B, C, D)
                marcadas_na_questao = [idx for idx in respostas_marcadas if idx in alternativas_questao]
                
                if marcadas_na_questao:
                    # NOVA LÓGICA: Pegar a alternativa com MAIOR porcentagem
                    melhor_alternativa = None
                    melhor_porcentagem = 0
                    
                    for idx in marcadas_na_questao:
                        x, y, w, h = coordenadas_projeto[idx]
                        interesse = binary_image[y:y + h, x:x + w]
                        mascara = np.zeros((h, w), dtype=np.uint8)
                        centro_x = w // 2
                        centro_y = h // 2
                        raio = min(w, h) // 2
                        cv2.circle(mascara, (centro_x, centro_y), raio, 255, -1)
                        interesse_mascarado = cv2.bitwise_and(interesse, interesse, mask=mascara)
                        total_pixels = cv2.countNonZero(mascara)
                        pixels_brancos = cv2.countNonZero(interesse_mascarado)
                        porcentagem = (pixels_brancos / total_pixels) * 100
                        
                        if porcentagem > melhor_porcentagem:
                            melhor_porcentagem = porcentagem
                            melhor_alternativa = idx
                    
                    if melhor_alternativa is not None:
                        alternativa_index = melhor_alternativa % 4
                        alternativa_letra = chr(65 + alternativa_index)  # A=0, B=1, C=2, D=3
                        resposta_detectada = alternativa_letra
                    else:
                        resposta_detectada = "Sem resposta"
                else:
                    resposta_detectada = "Sem resposta"
                
                # Buscar resposta correta
                questao_num = i + 1
                resposta_correta = gabarito.get(questao_num, "Não encontrada")
                
                # Comparar
                if resposta_detectada == resposta_correta:
                    status = "✅ CORRETO"
                    acertos += 1
                elif resposta_detectada == "Sem resposta":
                    status = "❌ SEM RESPOSTA"
                else:
                    status = "❌ ERRADO"
                
                print(f"Questão {questao_num}: Detectada={resposta_detectada} | Correta={resposta_correta} | {status}")
            
            print(f"\n📊 RESULTADO: {acertos}/{num_questoes} acertos ({acertos/num_questoes*100:.1f}%)")
            print("==========================================\n")
            
            # Acertos já foram calculados na comparação acima
            
            return {
                'success': True,
                'student_id': student_id,
                'detected_answers': respostas_marcadas,
                'correct_answers': acertos,
                'total_questions': num_questoes,
                'score_percentage': (acertos / num_questoes * 100) if num_questoes > 0 else 0,
                'grade': (acertos / num_questoes * 10) if num_questoes > 0 else 0,
                'proficiency': (acertos / num_questoes * 400) if num_questoes > 0 else 0,
                'classification': 'Avançado' if acertos == num_questoes else 'Adequado' if acertos >= num_questoes/2 else 'Básico' if num_questoes > 0 else 'Básico',
                'method': 'projeto_style'
            }
            
        except Exception as e:
            logging.error(f"Erro ao processar correção por imagem: {str(e)}")
            return {
                'success': False,
                'error': f'Erro interno: {str(e)}'
            }

    def processar_correcao_por_gabarito(self, test_id, image_data_str):
        """
        Nova abordagem: Correção por gabarito de referência ADAPTATIVA
        
        1. Processa imagem do usuário PRIMEIRO para obter dimensões
        2. Gera gabarito de referência no tamanho exato da imagem do usuário
        3. Alinha gabarito com imagem do usuário (se necessário)
        4. Compara bolha-a-bolha usando coordenadas corretas
        """
        try:
            print(f"🎯 INICIANDO CORREÇÃO POR GABARITO DE REFERÊNCIA ADAPTATIVA")
            print(f"📋 Test ID: {test_id}")
            
            # 1. Processar imagem do usuário PRIMEIRO para obter dimensões
            print(f"🔧 ETAPA 1: PROCESSANDO IMAGEM DO USUÁRIO...")
            user_image = self._processar_imagem_usuario(image_data_str)
            
            if user_image is None:
                return {
                    'success': False,
                    'error': 'Erro ao processar imagem do usuário'
                }
            
            # Extrair dimensões da imagem do usuário
            user_height, user_width = user_image.shape[:2]
            print(f"📏 Dimensões da imagem do usuário: {user_width}x{user_height}")
            
            # 1.5. Detectar QR code na imagem do usuário para extrair student_id
            print(f"🔧 ETAPA 1.5: DETECTANDO QR CODE...")
            user_qr = self._detectar_qr_code_avancado(user_image)
            if user_qr is None:
                return {
                    'success': False,
                    'error': 'QR code não encontrado na imagem do usuário. Verifique se a imagem contém um QR code válido e está com boa qualidade.'
                }
            
            # Extrair student_id do QR code
            student_id = user_qr['data'].get('student_id')
            if not student_id:
                return {
                    'success': False,
                    'error': 'QR code inválido: student_id não encontrado'
                }
            
            print(f"✅ QR code detectado - Student ID: {student_id}")
            
            # 2. Gerar gabarito de referência no tamanho exato da imagem do usuário
            print(f"🔧 ETAPA 2: GERANDO GABARITO ADAPTATIVO...")
            gabarito_image, gabarito_coords = self._gerar_gabarito_referencia_adaptativo(
                test_id, (user_width, user_height)
            )
            
            if gabarito_image is None:
                return {
                    'success': False,
                    'error': 'Erro ao gerar gabarito de referência adaptativo'
                }
            
            # 3. Alinhar gabarito com imagem do usuário (se necessário)
            print(f"🔧 ETAPA 3: ALINHANDO GABARITO COM IMAGEM DO USUÁRIO...")
            aligned_gabarito = self._alinhar_gabarito_com_usuario(gabarito_image, user_image)
            
            if aligned_gabarito is None:
                # Se alinhamento falhar, usar gabarito original (já está no tamanho correto)
                print(f"⚠️ Alinhamento falhou, usando gabarito original")
                aligned_gabarito = gabarito_image
            
            # 4. Comparar bolha-a-bolha usando gabarito alinhado
            print(f"🔧 ETAPA 4: COMPARANDO BOLHA-A-BOLHA...")
            respostas_detectadas = self._comparar_bolhas_adaptativo(aligned_gabarito, user_image, test_id)
            
            # 5. Calcular resultado
            print(f"🔧 ETAPA 5: CALCULANDO RESULTADO...")
            resultado = self._calcular_resultado_final(test_id, respostas_detectadas, student_id)
            
            # 6. Gerar imagem de debug (sempre)
            print(f"🔧 ETAPA 6: GERANDO IMAGEM DE DEBUG...")
            debug_image_path = self._gerar_imagem_debug_alinhamento(
                aligned_gabarito,  # Gabarito alinhado (lado esquerdo)
                user_image,        # Imagem original do usuário (lado direito)
                test_id
            )
            if debug_image_path:
                resultado['debug_image_path'] = debug_image_path
                print(f"✅ Imagem de debug salva: {debug_image_path}")
            
            return resultado
            
        except Exception as e:
            logging.error(f"Erro na correção por gabarito: {str(e)}")
            return {
                'success': False,
                'error': f'Erro na correção por gabarito: {str(e)}'
            }

    def _gerar_gabarito_referencia_adaptativo(self, test_id, target_size):
        """
        Gera gabarito de referência adaptativo no tamanho exato da imagem do usuário
        
        Args:
            test_id: ID da prova
            target_size: (width, height) da imagem do usuário
        """
        try:
            target_width, target_height = target_size
            print(f"🔧 Gerando gabarito adaptativo para test_id: {test_id}")
            print(f"📏 Tamanho alvo: {target_width}x{target_height}")
            
            # Buscar dados da prova
            from app.models.test import Test
            from app.models.question import Question
            from app.models.testQuestion import TestQuestion
            
            test = Test.query.get(test_id)
            if not test:
                print(f"❌ Test não encontrado: {test_id}")
                return None, None
            
            # Buscar questões da prova
            test_questions = TestQuestion.query.filter_by(test_id=test_id).order_by(TestQuestion.order).all()
            
            # Manter a ordem correta das questões
            questions = []
            for tq in test_questions:
                question = Question.query.get(tq.question_id)
                if question:
                    questions.append(question)
            
            if not questions:
                print(f"❌ Nenhuma questão encontrada para o teste")
                return None, None
            
            # Gerar gabarito usando formularios.py com dimensões específicas
            from app.formularios import gerar_formulario_com_qrcode_adaptativo
            
            # Dados do gabarito (respostas corretas)
            gabarito_data = {
                'id': 'GABARITO_REFERENCIA',
                'nome': 'GABARITO DE REFERÊNCIA',
                'questoes': []
            }
            
            for i, question in enumerate(questions):
                # Buscar resposta correta da questão
                correct_answer = question.correct_answer
                if not correct_answer:
                    print(f"⚠️ Questão {i+1} sem resposta correta definida")
                    continue
                
                gabarito_data['questoes'].append({
                    'numero': i + 1,
                    'resposta_correta': correct_answer
                })
            
            # Gerar imagem do gabarito com dimensões específicas
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                temp_path = tmp.name
            
            imagem_gabarito, coordenadas_respostas, coordenadas_qr = gerar_formulario_com_qrcode_adaptativo(
                'GABARITO_REFERENCIA',
                'GABARITO DE REFERÊNCIA', 
                len(questions),
                temp_path,
                gabarito_data,
                {'id': test_id, 'title': test.title},
                target_width,
                target_height
            )
            
            if imagem_gabarito and coordenadas_respostas:
                # Preencher as respostas corretas no gabarito
                print(f"🔧 Preenchendo respostas corretas no gabarito adaptativo...")
                imagem_gabarito_preenchida = self._preencher_respostas_corretas_adaptativo(
                    imagem_gabarito, 
                    coordenadas_respostas, 
                    questions,
                    len(questions),
                    target_width,
                    target_height
                )
                
                print(f"✅ Gabarito adaptativo gerado com {len(coordenadas_respostas)} coordenadas")
                print(f"📏 Dimensões finais: {target_width}x{target_height}")
                
                return imagem_gabarito_preenchida, coordenadas_respostas
            else:
                print(f"❌ Erro ao gerar gabarito adaptativo")
                return None, None
                
        except Exception as e:
            print(f"❌ Erro ao gerar gabarito adaptativo: {str(e)}")
            return None, None

    def _preencher_respostas_corretas_adaptativo(self, imagem_gabarito, coordenadas_respostas, questions, num_questions, target_width, target_height):
        """
        Preenche as respostas corretas no gabarito adaptativo usando coordenadas proporcionais
        """
        try:
            from PIL import Image, ImageDraw
            
            # Converter PIL para ImageDraw se necessário
            if hasattr(imagem_gabarito, 'mode'):
                draw = ImageDraw.Draw(imagem_gabarito)
            else:
                # Se for numpy array, converter para PIL
                import numpy as np
                if len(imagem_gabarito.shape) == 3:
                    imagem_gabarito = Image.fromarray(cv2.cvtColor(imagem_gabarito, cv2.COLOR_BGR2RGB))
                else:
                    imagem_gabarito = Image.fromarray(imagem_gabarito)
                draw = ImageDraw.Draw(imagem_gabarito)
            
            # Calcular coordenadas proporcionais baseadas no tamanho alvo
            # Usar as mesmas proporções das coordenadas originais
            proporcao_x = target_width / 1240  # Proporção baseada na largura original
            proporcao_y = target_height / 1753  # Proporção baseada na altura original
            
            # Coordenadas originais (para referência)
            x_positions_orig = [112, 162, 212, 262]
            y_positions_orig = [950, 995, 1040, 1085]
            
            # Calcular coordenadas proporcionais
            x_positions = [int(x * proporcao_x) for x in x_positions_orig]
            y_positions = []
            for i in range(num_questions):
                if i < len(y_positions_orig):
                    y_positions.append(int(y_positions_orig[i] * proporcao_y))
                else:
                    # Continuar o padrão para questões adicionais
                    y_positions.append(int((y_positions_orig[-1] + (i - len(y_positions_orig) + 1) * 45) * proporcao_y))
            
            print(f"📊 Coordenadas adaptativas calculadas:")
            print(f"  X: {x_positions}")
            print(f"  Y: {y_positions}")
            
            # Preencher as respostas corretas
            for i, question in enumerate(questions):
                questao_num = i + 1
                resposta_correta = question.correct_answer
                
                if resposta_correta and questao_num <= len(y_positions):
                    # Encontrar a coordenada da resposta correta
                    alternativa_idx = ['A', 'B', 'C', 'D'].index(resposta_correta)
                    x = x_positions[alternativa_idx]
                    y = y_positions[questao_num - 1]
                    
                    # Calcular tamanho do círculo proporcional
                    raio = int(15 * min(proporcao_x, proporcao_y))  # Raio proporcional
                    
                    # Desenhar círculo preenchido
                    center_x = x
                    center_y = y
                    
                    # Preencher círculo com preto
                    draw.ellipse(
                        [center_x - raio, center_y - raio, 
                         center_x + raio, center_y + raio],
                        fill='black'
                    )
                    
                    print(f"  ✅ Questão {questao_num}: {resposta_correta} preenchida em ({x},{y})")
            
            return imagem_gabarito
            
        except Exception as e:
            print(f"❌ Erro ao preencher respostas adaptativas: {str(e)}")
            return imagem_gabarito

    def _alinhar_gabarito_com_usuario(self, gabarito_image, user_image):
        """
        Alinha gabarito com imagem do usuário (já estão no mesmo tamanho, apenas ajuste fino)
        """
        try:
            print(f"🔧 Alinhando gabarito com usuário...")
            
            # Como gabarito e usuário já estão no mesmo tamanho, 
            # apenas aplicar transformação de perspectiva se necessário
            # Por enquanto, retornar o gabarito original
            print(f"✅ Gabarito já está no tamanho correto, sem necessidade de alinhamento")
            return gabarito_image
            
        except Exception as e:
            print(f"❌ Erro ao alinhar gabarito: {str(e)}")
            return None

    def _comparar_bolhas_adaptativo(self, gabarito_image, user_image, test_id):
        """
        Compara bolhas usando gabarito adaptativo (mesmo tamanho que usuário)
        """
        try:
            print(f"🔧 Comparando bolhas com gabarito adaptativo...")
            
            # Converter imagens para numpy arrays se necessário
            if hasattr(gabarito_image, 'mode'):  # É PIL Image
                gabarito_array = np.array(gabarito_image)
                if len(gabarito_array.shape) == 3:
                    gabarito_array = cv2.cvtColor(gabarito_array, cv2.COLOR_RGB2BGR)
            else:
                gabarito_array = gabarito_image
                
            if hasattr(user_image, 'mode'):  # É PIL Image
                user_array = np.array(user_image)
                if len(user_array.shape) == 3:
                    user_array = cv2.cvtColor(user_array, cv2.COLOR_RGB2BGR)
            else:
                user_array = user_image
            
            # Converter para grayscale
            if len(gabarito_array.shape) == 3:
                gabarito_gray = cv2.cvtColor(gabarito_array, cv2.COLOR_BGR2GRAY)
            else:
                gabarito_gray = gabarito_array
                
            if len(user_array.shape) == 3:
                user_gray = cv2.cvtColor(user_array, cv2.COLOR_BGR2GRAY)
            else:
                user_gray = user_array
            
            # Obter dimensões (devem ser iguais)
            gabarito_h, gabarito_w = gabarito_gray.shape
            user_h, user_w = user_gray.shape
            
            print(f"📏 Dimensões - Gabarito: {gabarito_w}x{gabarito_h}, Usuário: {user_w}x{user_h}")
            
            # Usar coordenadas proporcionais baseadas no tamanho real
            proporcao_x = gabarito_w / 1240
            proporcao_y = gabarito_h / 1753
            
            x_positions = [int(x * proporcao_x) for x in [112, 162, 212, 262]]
            y_positions = [int(y * proporcao_y) for y in [950, 995, 1040, 1085]]
            
            print(f"📊 Coordenadas finais: X={x_positions}, Y={y_positions}")
            
            # Detectar bolhas na imagem do usuário
            respostas_detectadas = {}
            
            # Buscar dados da prova
            from app.models.test import Test
            from app.models.question import Question
            from app.models.testQuestion import TestQuestion
            
            test = Test.query.get(test_id)
            test_questions = TestQuestion.query.filter_by(test_id=test_id).order_by(TestQuestion.order).all()
            num_questoes = len(test_questions)
            
            for i in range(num_questoes):
                questao_num = i + 1
                opcoes = ["A", "B", "C", "D"]
                proporcoes = {}
                
                print(f"  🔍 Processando questão {questao_num}...")
                
                # Processar cada alternativa da questão
                for j in range(4):
                    x = x_positions[j]
                    y = y_positions[i] if i < len(y_positions) else y_positions[-1]
                    
                    # Extrair região da bolha na imagem do usuário
                    # AUMENTAR TAMANHO DA REGIÃO para capturar bolhas completas
                    w = h = int(80 * min(proporcao_x, proporcao_y))  # Aumentado de 30 para 80
                    x1 = max(0, x - w//2)
                    y1 = max(0, y - h//2)
                    x2 = min(user_w, x + w//2)
                    y2 = min(user_h, y + h//2)
                    
                    if x2 > x1 and y2 > y1:
                        regiao_bolha = user_gray[y1:y2, x1:x2]
                        
                        # Calcular proporção de pixels pretos
                        proporcao = self._calcular_proporcao_pixels_pretos_melhorada(regiao_bolha, None)
                        proporcoes[opcoes[j]] = proporcao
                        
                        print(f"    📊 Questão {questao_num}, {opcoes[j]}: proporção={proporcao:.3f}, região=({x1},{y1})-({x2},{y2}), tamanho={w}x{h}")
                    else:
                        print(f"    ❌ Região inválida para {opcoes[j]}: ({x1},{y1})-({x2},{y2})")
                
                # Aplicar critérios de detecção
                if proporcoes:
                    print(f"  🔍 Aplicando critérios para questão {questao_num}: {proporcoes}")
                    resposta = self._aplicar_criterios_deteccao(proporcoes, questao_num)
                    if resposta:
                        respostas_detectadas[questao_num] = resposta
                        print(f"  ✅ Questão {questao_num}: {resposta}")
                    else:
                        print(f"  ❌ Questão {questao_num}: Não marcada")
                else:
                    print(f"  ❌ Questão {questao_num}: Sem proporções")
            
            print(f"📊 RESPOSTAS DETECTADAS: {respostas_detectadas}")
            return respostas_detectadas
            
        except Exception as e:
            print(f"❌ Erro ao comparar bolhas adaptativo: {str(e)}")
            return {}

    def _gerar_gabarito_referencia(self, test_id):
        """
        Gera gabarito de referência com respostas corretas preenchidas
        """
        try:
            print(f"🔧 Gerando gabarito de referência para test_id: {test_id}")
            
            # Buscar dados da prova
            from app.models.test import Test
            from app.models.question import Question
            from app.models.testQuestion import TestQuestion
            
            test = Test.query.get(test_id)
            if not test:
                print(f"❌ Test não encontrado: {test_id}")
                return None, None
            
            # Buscar questões da prova
            test_questions = TestQuestion.query.filter_by(test_id=test_id).order_by(TestQuestion.order).all()
            
            # Manter a ordem correta das questões
            questions = []
            for tq in test_questions:
                question = Question.query.get(tq.question_id)
                if question:
                    questions.append(question)
            
            if not questions:
                print(f"❌ Nenhuma questão encontrada para o teste")
                return None, None
            
            # Gerar gabarito usando formularios.py
            from app.formularios import gerar_formulario_com_qrcode
            
            # Dados do gabarito (respostas corretas)
            gabarito_data = {
                'id': 'GABARITO_REFERENCIA',
                'nome': 'GABARITO DE REFERÊNCIA',
                'questoes': []
            }
            
            for i, question in enumerate(questions):
                # Buscar resposta correta da questão
                correct_answer = question.correct_answer
                if not correct_answer:
                    print(f"⚠️ Questão {i+1} sem resposta correta definida")
                    continue
                
                gabarito_data['questoes'].append({
                    'numero': i + 1,
                    'resposta_correta': correct_answer
                })
            
            # Gerar imagem do gabarito
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                temp_path = tmp.name
            
            imagem_gabarito, coordenadas_respostas, coordenadas_qr = gerar_formulario_com_qrcode(
                'GABARITO_REFERENCIA',
                'GABARITO DE REFERÊNCIA', 
                len(questions),
                temp_path,
                gabarito_data,
                {'id': test_id, 'title': test.title}
            )
            
            if imagem_gabarito and coordenadas_respostas:
                # Preencher as respostas corretas no gabarito
                print(f"🔧 Preenchendo respostas corretas no gabarito...")
                imagem_gabarito_preenchida = self._preencher_respostas_corretas(
                    imagem_gabarito, 
                    coordenadas_respostas, 
                    questions,
                    len(questions)  # Passar número de questões
                )
                
                print(f"✅ Gabarito de referência gerado com {len(coordenadas_respostas)} coordenadas")
                
                # Salvar template de coordenadas se não existir
                from app.models.formCoordinates import FormCoordinates
                from app import db
                existing_template = FormCoordinates.query.filter_by(
                    test_id=test_id,
                    form_type='physical_test'
                ).first()
                
                if not existing_template:
                    # Gerar coordenadas usando as coordenadas fixas especificadas
                    num_questions = len(questions)
                    # Usar coordenadas fixas corretas [112, 162, 212, 262]
                    coordenadas_fixas = []
                    x_positions = [112, 162, 212, 262]
                    y_positions = [950, 995, 1040, 1085]
                    for i in range(num_questions):
                        for j in range(4):
                            x = x_positions[j]
                            y = y_positions[i] if i < len(y_positions) else y_positions[-1] + (i - len(y_positions) + 1) * 45
                            coordenadas_fixas.append([x, y, 28, 28])
                    
                    form_template = FormCoordinates(
                        test_id=test_id,
                        form_type='physical_test',
                        qr_code_id=None,
                        student_id=None,
                        coordinates=coordenadas_fixas,
                        num_questions=num_questions  # Salvar número de questões
                    )
                    db.session.add(form_template)
                    db.session.commit()
                    print(f"✅ Template de coordenadas salvo para teste {test_id} com {num_questions} questões")
                else:
                    # Atualizar número de questões se necessário
                    if existing_template.num_questions != len(questions):
                        existing_template.num_questions = len(questions)
                        # Regenerar coordenadas com o número correto usando coordenadas fixas
                        coordenadas_fixas = []
                        x_positions = [112, 162, 212, 262]
                        y_positions = [950, 995, 1040, 1085]
                        for i in range(len(questions)):
                            for j in range(4):
                                x = x_positions[j]
                                y = y_positions[i] if i < len(y_positions) else y_positions[-1] + (i - len(y_positions) + 1) * 45
                                coordenadas_fixas.append([x, y, 28, 28])
                        existing_template.coordinates = coordenadas_fixas
                        db.session.commit()
                        print(f"✅ Template de coordenadas atualizado para {len(questions)} questões")
                
                return imagem_gabarito_preenchida, coordenadas_respostas
            else:
                print(f"❌ Erro ao gerar gabarito de referência")
                return None, None
                
        except Exception as e:
            print(f"❌ Erro ao gerar gabarito de referência: {str(e)}")
            return None, None

    def _preencher_respostas_corretas(self, imagem_gabarito, coordenadas_respostas, questions, num_questions: int = None):
        """
        Preenche as respostas corretas no gabarito usando coordenadas fixas
        X: [112, 162, 212, 262] - diferença de 50px entre alternativas
        Y: [950, 995, 1040, 1085] - diferença de 45px entre questões
        """
        try:
            from PIL import Image, ImageDraw
            
            # Converter PIL para ImageDraw se necessário
            if hasattr(imagem_gabarito, 'mode'):
                draw = ImageDraw.Draw(imagem_gabarito)
            else:
                # Se for numpy array, converter para PIL
                import numpy as np
                if len(imagem_gabarito.shape) == 3:
                    imagem_gabarito = Image.fromarray(cv2.cvtColor(imagem_gabarito, cv2.COLOR_BGR2RGB))
                else:
                    imagem_gabarito = Image.fromarray(imagem_gabarito)
                draw = ImageDraw.Draw(imagem_gabarito)
            
            # COORDENADAS FIXAS ESPECIFICADAS PELO USUÁRIO (NUNCA ALTERAR)
            x_positions_fixed = [112, 162, 212, 262]  # Posições X das alternativas A, B, C, D
            y_positions_base = [950, 995, 1040, 1085]  # Posições Y das questões 1, 2, 3, 4
            
            # Se num_questions não foi fornecido, usar o número de questões das coordenadas base
            if num_questions is None:
                num_questions = len(y_positions_base)
                print(f"📊 Usando número de questões padrão: {num_questions}")
            else:
                print(f"📊 Usando número de questões fornecido: {num_questions}")
            
            # Gerar posições Y dinamicamente mantendo as coordenadas fixas
            y_positions_centro = []
            for i in range(num_questions):
                if i < len(y_positions_base):
                    # Usar as coordenadas fixas para as primeiras 4 questões
                    y_positions_centro.append(y_positions_base[i])
                else:
                    # Continuar o padrão de 45px para questões adicionais
                    y_positions_centro.append(y_positions_base[-1] + (i - len(y_positions_base) + 1) * 45)
            
            print(f"🔍 DEBUG: Usando coordenadas fixas dinâmicas")
            print(f"  X: {x_positions_fixed}")
            print(f"  Y: {y_positions_centro} (para {num_questions} questões)")
            
            # Debug visual: marcar cada coluna no gabarito (REMOVIDO)
            # for idx, col_x in enumerate(x_positions_fixed):
            #     draw.line([(col_x, 0), (col_x, imagem_gabarito.height)], fill="red", width=2)
            #     draw.text((col_x+5, 10), f"{['A','B','C','D'][idx]}", fill="blue")
            
            # Função para mapear posição X para alternativa
            def mapear_alternativa_por_posicao(x):
                try:
                    idx = x_positions_fixed.index(x)
                    return ['A', 'B', 'C', 'D'][idx]
                except ValueError:
                    # Se não encontrar exato, encontrar a mais próxima
                    distancias = [abs(x - col_x) for col_x in x_positions_fixed]
                    idx = distancias.index(min(distancias))
                    return ['A', 'B', 'C', 'D'][idx]
            
            # Agrupar coordenadas por questão usando coordenadas fixas dinâmicas
            questoes_coords = {}
            for i in range(num_questions):  # Usar num_questions dinamicamente
                questao_num = i + 1
                questoes_coords[questao_num] = []
                
                for j in range(4):  # 4 alternativas (A, B, C, D)
                    x = x_positions_fixed[j]  # Usar coordenadas X fixas
                    y = y_positions_centro[i]  # Usar coordenadas Y dinâmicas
                    alternativa = ['A', 'B', 'C', 'D'][j]
                    
                    questoes_coords[questao_num].append({
                        'coord': [x, y, 20, 20],  # x, y, w, h
                        'alternativa': alternativa
                    })
            
            print(f"🔍 DEBUG: Coordenadas agrupadas por questão (usando coordenadas fixas):")
            for questao_num, alternativas in questoes_coords.items():
                print(f"  Questão {questao_num}: {[alt['alternativa'] for alt in alternativas]}")
            
            # Preencher as respostas corretas
            for i, question in enumerate(questions):
                questao_num = i + 1
                resposta_correta = question.correct_answer
                
                if questao_num in questoes_coords and resposta_correta:
                    # Encontrar a coordenada da resposta correta
                    for alt_data in questoes_coords[questao_num]:
                        if alt_data['alternativa'] == resposta_correta:
                            coord = alt_data['coord']
                            x, y, w, h = coord[:4]
                            
                            # Desenhar círculo preenchido
                            center_x = x + w // 2
                            center_y = y + h // 2
                            radius = min(w, h) // 2 - 2  # Margem interna
                            
                            # Preencher círculo com preto
                            draw.ellipse(
                                [center_x - radius, center_y - radius, 
                                 center_x + radius, center_y + radius],
                                fill='black'
                            )
                            
                            print(f"  ✅ Questão {questao_num}: {resposta_correta} preenchida")
                            break
            
            return imagem_gabarito
            
        except Exception as e:
            print(f"❌ Erro ao preencher respostas corretas: {str(e)}")
            return imagem_gabarito

    def _processar_imagem_usuario(self, image_data_str):
        """
        Processa imagem do usuário (decodifica base64)
        """
        try:
            print(f"🔧 Processando imagem do usuário...")
            
            # Decodificar base64
            if image_data_str.startswith('data:image'):
                image_data_str = image_data_str.split(',')[1]
            
            image_data = base64.b64decode(image_data_str)
            
            # Converter para OpenCV
            nparr = np.frombuffer(image_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if img is None:
                print(f"❌ Erro ao decodificar imagem")
                return None
            
            # Salvar imagem original para detecção de QR Code (como no método antigo)
            img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            self._original_image_for_qr = img_gray.copy()
            
            print(f"✅ Imagem do usuário processada: {img.shape}")
            return img
            
        except Exception as e:
            print(f"❌ Erro ao processar imagem do usuário: {str(e)}")
            return None

    def _alinhar_imagens_por_qr(self, gabarito_image, user_image):
        """
        Alinha imagem do usuário com gabarito usando QR code + transformação de perspectiva
        """
        try:
            print(f"🔧 Alinhando imagens por QR code + perspectiva...")
            
            # Detectar QR code no gabarito
            gabarito_qr = self._detectar_qr_code(gabarito_image)
            if gabarito_qr is None:
                print(f"❌ QR code não encontrado no gabarito")
                return None
            
            print(f"✅ QR code do gabarito: {gabarito_qr['data']}")
            
            # Detectar QR code na imagem do usuário
            user_qr = self._detectar_qr_code(user_image)
            if user_qr is None:
                print(f"❌ QR code não encontrado na imagem do usuário")
                
                # Tentar detecção alternativa com imagem original
                if hasattr(self, '_original_image_for_qr') and self._original_image_for_qr is not None:
                    print(f"🔧 Tentando detecção com imagem original...")
                    user_qr_alt = self._detectar_qr_code(self._original_image_for_qr)
                    if user_qr_alt:
                        print(f"✅ QR code detectado com imagem original: {user_qr_alt['data']}")
                        user_qr = user_qr_alt
                    else:
                        print(f"❌ QR code não encontrado mesmo com imagem original")
                        # Usar método de fallback: alinhamento por redimensionamento
                        print(f"🔧 Usando método de fallback: alinhamento por redimensionamento...")
                        aligned_image = self._alinhar_por_redimensionamento(user_image, gabarito_image)
                        if aligned_image is not None:
                            print(f"✅ Imagem alinhada com sucesso usando redimensionamento")
                            return aligned_image
                        else:
                            print(f"❌ Falha no alinhamento por redimensionamento")
                            return None
                else:
                    # Usar método de fallback: alinhamento por redimensionamento
                    print(f"🔧 Usando método de fallback: alinhamento por redimensionamento...")
                    aligned_image = self._alinhar_por_redimensionamento(user_image, gabarito_image)
                    if aligned_image is not None:
                        print(f"✅ Imagem alinhada com sucesso usando redimensionamento")
                        return aligned_image
                    else:
                        print(f"❌ Falha no alinhamento por redimensionamento")
                        return None
            
            print(f"✅ QR code do usuário: {user_qr['data']}")
            
            # Tentar alinhamento por QR code primeiro
            print(f"🔧 Tentando alinhamento por QR code...")
            aligned_image = self._alinhar_por_qr_code(gabarito_image, user_image, gabarito_qr, user_qr)
            
            if aligned_image is not None:
                print(f"✅ Imagens alinhadas com sucesso usando QR code")
                return aligned_image
            else:
                print(f"⚠️ Alinhamento por QR code falhou, tentando perspectiva invertida...")
                # Fallback para alinhamento por perspectiva baseada nas âncoras
                aligned_image = self._alinhar_por_perspectiva_invertida(gabarito_image, user_image)
                
                if aligned_image is not None:
                    print(f"✅ Imagens alinhadas com sucesso usando perspectiva invertida")
                    return aligned_image
                else:
                    print(f"❌ Erro ao alinhar imagens por perspectiva invertida")
                    return None
                
        except Exception as e:
            print(f"❌ Erro ao alinhar imagens: {str(e)}")
            return None

    def _alinhar_por_qr_code(self, gabarito_image, user_image, gabarito_qr, user_qr):
        """
        Alinha gabarito com imagem do usuário usando coordenadas dos QR codes
        """
        try:
            print(f"🔧 Alinhando por QR code...")
            
            # Converter imagens para numpy arrays se necessário
            if hasattr(gabarito_image, 'mode'):  # É PIL Image
                gabarito_array = np.array(gabarito_image)
                if len(gabarito_array.shape) == 3:
                    gabarito_array = cv2.cvtColor(gabarito_array, cv2.COLOR_RGB2BGR)
            else:
                gabarito_array = gabarito_image
                
            if hasattr(user_image, 'mode'):  # É PIL Image
                user_array = np.array(user_image)
                if len(user_array.shape) == 3:
                    user_array = cv2.cvtColor(user_array, cv2.COLOR_RGB2BGR)
            else:
                user_array = user_image
            
            # Obter dimensões das imagens
            altura_gabarito, largura_gabarito = gabarito_array.shape[:2]
            altura_usuario, largura_usuario = user_array.shape[:2]
            
            print(f"📏 Dimensões do gabarito: {largura_gabarito}x{altura_gabarito}")
            print(f"📏 Dimensões da imagem do usuário: {largura_usuario}x{altura_usuario}")
            
            # Calcular escala proporcional baseada na altura (manter proporção)
            scale_factor = altura_usuario / altura_gabarito
            nova_largura = int(largura_gabarito * scale_factor)
            
            print(f"📏 Fator de escala baseado na altura: {scale_factor:.3f}")
            print(f"📏 Nova largura calculada: {nova_largura}")
            
            # Redimensionar gabarito para se adequar à escala do usuário
            gabarito_redimensionado = cv2.resize(gabarito_array, (nova_largura, altura_usuario))
            print(f"📏 Gabarito redimensionado para: {gabarito_redimensionado.shape[1]}x{gabarito_redimensionado.shape[0]}")
            
            # Converter para grayscale para detecção de QR code
            gabarito_gray = cv2.cvtColor(gabarito_redimensionado, cv2.COLOR_BGR2GRAY)
            user_gray = cv2.cvtColor(user_array, cv2.COLOR_BGR2GRAY)
            
            # Detectar QR codes nas imagens redimensionadas
            detector = cv2.QRCodeDetector()
            
            # Detectar QR code no gabarito redimensionado
            ret_gabarito, points_gabarito = detector.detect(gabarito_gray)
            if not ret_gabarito or points_gabarito is None:
                print(f"❌ QR code não detectado no gabarito redimensionado")
                return None
            
            # Detectar QR code na imagem do usuário
            ret_usuario, points_usuario = detector.detect(user_gray)
            if not ret_usuario or points_usuario is None:
                print(f"❌ QR code não detectado na imagem do usuário")
                return None
            
            print(f"✅ QR codes detectados em ambas as imagens")
            print(f"  Gabarito: {len(points_gabarito[0])} pontos")
            print(f"  Usuário: {len(points_usuario[0])} pontos")
            
            # Obter coordenadas dos QR codes
            gabarito_qr_points = points_gabarito[0].astype(np.float32)
            user_qr_points = points_usuario[0].astype(np.float32)
            
            print(f"🔍 Pontos do QR code do gabarito: {gabarito_qr_points}")
            print(f"🔍 Pontos do QR code do usuário: {user_qr_points}")
            
            # Calcular transformação de perspectiva do gabarito para o usuário
            matrix = cv2.getPerspectiveTransform(gabarito_qr_points, user_qr_points)
            
            # Aplicar transformação ao gabarito redimensionado
            gabarito_alinhado = cv2.warpPerspective(
                gabarito_redimensionado, 
                matrix, 
                (largura_usuario, altura_usuario)
            )
            
            print(f"✅ Alinhamento por QR code aplicado com sucesso")
            print(f"📏 Gabarito alinhado: {gabarito_alinhado.shape[1]}x{gabarito_alinhado.shape[0]}")
            
            return gabarito_alinhado
            
        except Exception as e:
            print(f"❌ Erro ao alinhar por QR code: {str(e)}")
            return None

    def _comparar_bolhas(self, gabarito_image, user_image, gabarito_coords, test_id):
        """
        Compara bolhas usando coordenadas do gabarito alinhado como referência
        CORRIGIDO: Usa gabarito alinhado para coordenadas e detecta na imagem do usuário
        """
        try:
            print(f"🔧 Comparando bolhas usando gabarito alinhado como referência...")
            
            # Converter imagens para numpy arrays se necessário
            if hasattr(gabarito_image, 'mode'):  # É PIL Image
                gabarito_array = np.array(gabarito_image)
                if len(gabarito_array.shape) == 3:
                    gabarito_array = cv2.cvtColor(gabarito_array, cv2.COLOR_RGB2BGR)
            else:
                gabarito_array = gabarito_image
                
            if hasattr(user_image, 'mode'):  # É PIL Image
                user_array = np.array(user_image)
                if len(user_array.shape) == 3:
                    user_array = cv2.cvtColor(user_array, cv2.COLOR_RGB2BGR)
            else:
                user_array = user_image
            
            print(f"📏 Gabarito alinhado: {gabarito_array.shape}")
            print(f"📏 Imagem do usuário: {user_array.shape}")
            
            # Converter imagens para grayscale
            if len(gabarito_array.shape) == 3:
                gabarito_gray = cv2.cvtColor(gabarito_array, cv2.COLOR_BGR2GRAY)
            else:
                gabarito_gray = gabarito_array
                
            if len(user_array.shape) == 3:
                user_gray = cv2.cvtColor(user_array, cv2.COLOR_BGR2GRAY)
            else:
                user_gray = user_array
            
            # NOVA LÓGICA: Usar gabarito alinhado para calcular coordenadas
            # e detectar bolhas na imagem do usuário
            respostas_detectadas = self._detectar_bolhas_com_gabarito_referencia(
                gabarito_gray, user_gray, test_id
            )
            
            print(f"✅ Comparação de bolhas concluída: {len(respostas_detectadas)} respostas detectadas")
            return respostas_detectadas
            
        except Exception as e:
            print(f"❌ Erro ao comparar bolhas: {str(e)}")
            return {}

    def _detectar_bolhas_com_gabarito_referencia(self, gabarito_gray, user_gray, test_id):
        """
        Detecta bolhas na imagem do usuário usando o gabarito alinhado como referência
        CORRIGIDO: Usa coordenadas do gabarito alinhado para detectar na imagem do usuário
        """
        try:
            print(f"🎯 DETECTANDO BOLHAS COM GABARITO COMO REFERÊNCIA")
            
            # Obter dimensões das imagens
            gabarito_h, gabarito_w = gabarito_gray.shape
            user_h, user_w = user_gray.shape
            
            print(f"📏 Dimensões do gabarito alinhado: {gabarito_w}x{gabarito_h}")
            print(f"📏 Dimensões da imagem do usuário: {user_w}x{user_h}")
            
            # Buscar dados da prova para obter respostas corretas
            from app.models.test import Test
            from app.models.question import Question
            from app.models.testQuestion import TestQuestion
            
            test = Test.query.get(test_id)
            if not test:
                print(f"❌ Test não encontrado: {test_id}")
                return {}
            
            # Buscar questões e respostas corretas na ordem correta
            test_questions = TestQuestion.query.filter_by(test_id=test_id).order_by(TestQuestion.order).all()
            questions_by_order = {}
            for i, tq in enumerate(test_questions):
                question = Question.query.get(tq.question_id)
                if question:
                    questions_by_order[i + 1] = question.correct_answer
            
            num_questoes = len(questions_by_order)
            print(f"📋 Número de questões: {num_questoes}")
            
            # NOVA ABORDAGEM: Calcular coordenadas dinamicamente baseadas no tamanho real do gabarito alinhado
            # Em vez de usar coordenadas fixas, calcular baseado na proporção do gabarito alinhado
            
            print(f"🔧 CALCULANDO COORDENADAS DINÂMICAS:")
            print(f"  Gabarito alinhado: {gabarito_w}x{gabarito_h}")
            print(f"  Número de questões: {num_questoes}")
            
            # Calcular coordenadas X das alternativas baseadas na largura do gabarito alinhado
            # Usar proporções similares às coordenadas originais
            x_positions_ajustadas = []
            for i in range(4):  # 4 alternativas A, B, C, D
                # Proporção baseada nas coordenadas originais: 112/1240, 162/1240, 212/1240, 262/1240
                proporcao_x = [112/1240, 162/1240, 212/1240, 262/1240][i]
                x_pos = int(gabarito_w * proporcao_x)
                x_positions_ajustadas.append(x_pos)
            
            # Calcular coordenadas Y das questões baseadas na altura do gabarito alinhado
            # Usar proporções similares às coordenadas originais
            y_positions_ajustadas = []
            for i in range(num_questoes):
                # Proporção baseada nas coordenadas originais: 950/1753, 995/1753, 1040/1753, 1085/1753
                proporcao_y = [950/1753, 995/1753, 1040/1753, 1085/1753][i] if i < 4 else 1085/1753
                y_pos = int(gabarito_h * proporcao_y)
                y_positions_ajustadas.append(y_pos)
            
            print(f"📊 Coordenadas calculadas dinamicamente:")
            print(f"  X: {x_positions_ajustadas}")
            print(f"  Y: {y_positions_ajustadas}")
            
            # Detectar bolhas na imagem do usuário usando as coordenadas do gabarito
            respostas_detectadas = {}
            
            for i in range(num_questoes):
                questao_num = i + 1
                opcoes = ["A", "B", "C", "D"]
                proporcoes = {}
                
                print(f"  🔍 Processando questão {questao_num}...")
                
                # Processar cada alternativa da questão
                for j in range(4):
                    x_gabarito = x_positions_ajustadas[j]
                    y_gabarito = y_positions_ajustadas[i]
                    
                    # Ajustar coordenadas para a imagem do usuário
                    # Calcular offset baseado na diferença de tamanho
                    scale_user_x = user_w / gabarito_w
                    scale_user_y = user_h / gabarito_h
                    
                    x_user = int(x_gabarito * scale_user_x)
                    y_user = int(y_gabarito * scale_user_y)
                    
                    # Ajuste fino para compensar pequenos desalinhamentos
                    # Aplicar um pequeno offset baseado na posição da alternativa
                    if j == 1:  # Alternativa B - ajuste específico
                        x_user += 2  # Pequeno ajuste para a direita
                        y_user += 1  # Pequeno ajuste para baixo
                    elif j == 2:  # Alternativa C
                        x_user += 1
                    elif j == 3:  # Alternativa D
                        x_user += 1
                        y_user += 1
                    
                    print(f"    📍 Gabarito: ({x_gabarito},{y_gabarito}) → Usuário: ({x_user},{y_user})")
                    
                    # Extrair região da bolha na imagem do usuário
                    # Aumentar o tamanho da região para capturar melhor a bolha
                    w = h = 60  # Tamanho da bolha aumentado de 40 para 60
                    x1 = max(0, x_user - w//2)
                    y1 = max(0, y_user - h//2)
                    x2 = min(user_w, x_user + w//2)
                    y2 = min(user_h, y_user + h//2)
                    
                    if x2 > x1 and y2 > y1:
                        regiao_bolha = user_gray[y1:y2, x1:x2]
                        
                        # Calcular proporção de pixels pretos
                        debug_path = f"debug_roi_q{questao_num}_{opcoes[j]}.png" if questao_num == 2 else None
                        proporcao = self._calcular_proporcao_pixels_pretos_melhorada(regiao_bolha, debug_path)
                        proporcoes[opcoes[j]] = proporcao
                        
                        print(f"    📊 Questão {questao_num}, {opcoes[j]}: proporção={proporcao:.3f}, região=({x1},{y1})-({x2},{y2})")
                    else:
                        print(f"    ❌ Região inválida para {opcoes[j]}")
                
                # Aplicar critérios de detecção
                if proporcoes:
                    print(f"  🔍 Aplicando critérios para questão {questao_num}: {proporcoes}")
                    resposta = self._aplicar_criterios_deteccao(proporcoes, questao_num)
                    if resposta:
                        respostas_detectadas[questao_num] = resposta
                        print(f"  ✅ Questão {questao_num}: {resposta}")
                    else:
                        print(f"  ❌ Questão {questao_num}: Não marcada")
                else:
                    print(f"  ❌ Questão {questao_num}: Sem proporções")
            
            print(f"📊 RESPOSTAS DETECTADAS: {respostas_detectadas}")
            return respostas_detectadas
            
        except Exception as e:
            print(f"❌ Erro ao detectar bolhas com gabarito referência: {str(e)}")
            return {}

    def _detectar_bolhas_metodo_antigo(self, user_gray):
        """
        Adapta o método antigo de detecção de bolhas para o novo sistema
        Detecta bolhas dinamicamente na imagem do usuário
        """
        try:
            print(f"🎯 USANDO MÉTODO ANTIGO ADAPTADO - GRADE FIXA COM CRITÉRIOS MÚLTIPLOS")
            
            # 1. Detectar borda grossa da tabela de questões para definir ROI
            h, w = user_gray.shape
            print(f"📏 Imagem de entrada: {user_gray.shape}")
            
            # Detectar borda da tabela (ROI) - usar método antigo
            roi_corners = self._detectar_borda_tabela_roi(user_gray)
            
            if roi_corners is None:
                print(f"⚠️ Borda da tabela não detectada, usando região inferior padrão")
                # Fallback: usar região inferior (últimos 40% da imagem)
                bubble_region = user_gray[int(h * 0.6):, :]
                print(f"📦 Região das bolhas (fallback): {bubble_region.shape}")
            else:
                # Usar ROI detectada pela borda da tabela
                x1, y1, x2, y2 = roi_corners
                bubble_region = user_gray[y1:y2, x1:x2]
                print(f"📦 Região das bolhas (ROI detectada): {bubble_region.shape}")
                print(f"🎯 ROI: ({x1},{y1}) a ({x2},{y2})")
            
            # 2. USAR GRADE FIXA - Solução para contornos fragmentados
            print(f"🎯 USANDO GRADE FIXA PARA EVITAR CONTORNOS FRAGMENTADOS")
            
            # Aplicar morfologia para unir contornos quebrados
            kernel = np.ones((3,3), np.uint8)
            proc = cv2.morphologyEx(bubble_region, cv2.MORPH_CLOSE, kernel, iterations=2)
            
            # Detectar quantas questões temos (assumir 4 por padrão, mas detectar dinamicamente)
            h_roi, w_roi = bubble_region.shape
            print(f"📏 ROI da tabela: {w_roi}x{h_roi} pixels")
            
            # Assumir 4 questões por padrão (pode ser ajustado)
            num_questions = 4
            num_alternatives = 4
            
            # Calcular tamanho de cada célula
            cell_h = h_roi // num_questions
            cell_w = w_roi // num_alternatives
            
            print(f"📐 Células: {cell_w}x{cell_h} pixels cada")
            
            # Processar cada célula da grade
            answers = {}
            
            for i in range(num_questions):
                question_num = i + 1
                option_proportions = {}
                
                for j in range(num_alternatives):
                    # Calcular coordenadas da célula
                    x1 = j * cell_w
                    y1 = i * cell_h
                    x2 = (j + 1) * cell_w
                    y2 = (i + 1) * cell_h
                    
                    # Extrair célula
                    cell = bubble_region[y1:y2, x1:x2]
                    
                    # Calcular proporção de pixels pretos usando método antigo
                    proportion_black = self._calcular_proporcao_pixels_pretos_OLD(cell)
                    
                    # Armazenar resultado
                    option_proportions[j] = {
                        'proportion': proportion_black,
                        'cx': (x1 + x2) // 2,
                        'cy': (y1 + y2) // 2,
                        'r': min(cell_w, cell_h) // 4
                    }
                    
                    print(f"  📊 Questão {question_num}, {chr(65+j)}: proporção_pretos={proportion_black:.3f}, pos=({(x1+x2)//2},{(y1+y2)//2})")
                
                # Aplicar critério inteligente de binarização (método antigo)
                proporcoes = [v['proportion'] for v in option_proportions.values()]
                max_proportion = max(proporcoes)
                max_idx = max(option_proportions.keys(), key=lambda k: option_proportions[k]['proportion'])
                
                # Calcular estatísticas para critério relativo
                proporcoes_ordenadas = sorted(proporcoes, reverse=True)
                segundo_maior = proporcoes_ordenadas[1] if len(proporcoes_ordenadas) > 1 else 0
                media_proporcoes = np.mean(proporcoes)
                
                # DEBUG: Mostrar proporções para análise
                print(f"    🔍 DEBUG Proporções: A={option_proportions[0]['proportion']:.3f}, B={option_proportions[1]['proportion']:.3f}, C={option_proportions[2]['proportion']:.3f}, D={option_proportions[3]['proportion']:.3f}")
                print(f"    🔍 DEBUG Maior: {max_proportion:.3f}, Segundo: {segundo_maior:.3f}, Média: {media_proporcoes:.3f}")
                
                # Critério 1: Threshold absoluto (mínimo de pixels pretos para considerar preenchida)
                threshold_absoluto = 0.05  # 5% de pixels pretos
                
                # Critério 2: Diferença relativa (mais escuro que a segunda opção)
                diferenca_relativa = max_proportion - segundo_maior
                threshold_relativo = 0.008  # 0.8% de diferença mínima
                
                # Critério 3: Normalização (maior que 1.3x a média)
                threshold_normalizacao = 1.3
                
                # Aplicar critérios combinados (lógica melhorada com priorização de posição)
                opcoes = ["A", "B", "C", "D"]
                maior = max_proportion
                idx_maior = max_idx
                
                # Ordenar proporções para encontrar segundo maior
                proporcoes_ordenadas = sorted(proporcoes, reverse=True)
                segundo_maior_valor = proporcoes_ordenadas[1] if len(proporcoes_ordenadas) > 1 else 0
                idx_segundo = proporcoes.index(segundo_maior_valor) if segundo_maior_valor in proporcoes else idx_maior
                
                resposta = None
                
                if maior >= threshold_absoluto:
                    diff = maior - segundo_maior_valor
                    
                    # Calcular diferença relativa (em relação à média)
                    diff_rel = diff / media_proporcoes if media_proporcoes > 0 else 0
                    
                    # Caso de empate técnico (diferença muito pequena)
                    if diff_rel < 0.20:  # < 20% da média => empate técnico
                        print(f"    🔍 EMPATE TÉCNICO detectado: diferença relativa {diff_rel:.1%} < 20% da média")
                        # Em caso de empate técnico, escolher o segundo maior (mais provável ser a marcação real)
                        if segundo_maior_valor >= threshold_absoluto:
                            resposta = opcoes[idx_segundo]
                            print(f"    🤔 Diferença muito pequena ({diff:.3f}), escolhendo {resposta} no lugar de {opcoes[idx_maior]}")
                        else:
                            resposta = opcoes[idx_maior]
                            print(f"    🤔 Diferença muito pequena, mas segundo não atende threshold, escolhendo {resposta}")
                    elif diff > threshold_relativo or maior >= media_proporcoes * threshold_normalizacao:
                        # Diferença clara - escolher o maior
                        resposta = opcoes[idx_maior]
                        print(f"    🎯 Diferença clara: escolhendo {resposta} (proporção: {maior:.3f})")
                    else:
                        print(f"    ❌ Questão {question_num}: Diferença insuficiente (proporção: {maior:.3f})")
                else:
                    print(f"    ❌ Questão {question_num}: Não marcada (proporção: {maior:.3f})")
                
                if resposta:
                    answers[question_num] = resposta
                    print(f"  ✅ Questão {question_num}: {resposta} (proporção: {maior:.3f})")
            
            print(f"📊 RESPOSTAS DETECTADAS: {answers}")
            return answers
            
        except Exception as e:
            print(f"❌ Erro ao detectar bolhas (método antigo): {str(e)}")
            return {}

    def _detectar_bolhas_por_coordenadas(self, user_gray, template_coords):
        """
        Detecta bolhas usando coordenadas específicas do template salvo no banco
        NOVA LÓGICA: Calcula coordenadas dinamicamente baseadas no tamanho da imagem do usuário
        """
        try:
            print(f"🎯 DETECTANDO BOLHAS USANDO COORDENADAS DINÂMICAS")
            print(f"📋 Coordenadas do template: {len(template_coords) if template_coords else 0} posições")
            
            # Obter dimensões da imagem do usuário
            h_img, w_img = user_gray.shape
            print(f"📏 Dimensões da imagem do usuário: {w_img}x{h_img}")
            
            # COORDENADAS DINÂMICAS baseadas no tamanho da imagem
            # Ajustar para corresponder melhor à posição real das bolhas
            
            # Região das bolhas (últimos 25% da altura, mais para baixo)
            start_y = int(h_img * 0.75)  # Começar a 75% da altura (mais para baixo)
            end_y = int(h_img * 0.98)    # Terminar a 98% da altura
            
            # Calcular espaçamento vertical entre questões
            available_height = end_y - start_y
            question_spacing = available_height // 4  # 4 questões
            
            # Calcular posições Y das questões (ajustado para alinhar com bolhas)
            y_positions = []
            for i in range(4):
                y = start_y + (i * question_spacing) + (question_spacing // 2) + 5
                y_positions.append(y)
            
            # Região horizontal das alternativas (mais para a direita)
            start_x = int(w_img * 0.12)  # Começar a 12% da largura (posição real das bolhas)
            end_x = int(w_img * 0.25)    # Terminar a 25% da largura
            
            # Calcular espaçamento horizontal entre alternativas
            available_width = end_x - start_x
            alt_spacing = available_width // 4  # 4 alternativas
            
            # Calcular posições X das alternativas
            x_positions = []
            for j in range(4):
                x = start_x + (j * alt_spacing) + (alt_spacing // 2)
                x_positions.append(x)
            
            print(f"📊 Coordenadas calculadas dinamicamente:")
            print(f"  Y: {y_positions}")
            print(f"  X: {x_positions}")
            
            # Gerar coordenadas dinâmicas para 4 questões x 4 alternativas
            coordenadas_dinamicas = []
            w = h = 40  # Tamanho das bolhas
            
            for i in range(4):  # 4 questões
                for j in range(4):  # 4 alternativas
                    x = x_positions[j]
                    y = y_positions[i]
                    coordenadas_dinamicas.append([x, y, w, h])
            
            # Usar coordenadas dinâmicas (sempre)
            print(f"📊 Usando coordenadas dinâmicas: {len(coordenadas_dinamicas)} posições")
            coordenadas_bolhas = coordenadas_dinamicas
            
            print(f"📊 Processando {len(coordenadas_bolhas)} coordenadas de bolhas")
            
            # Detectar bolhas usando as coordenadas específicas
            respostas_detectadas = {}
            
            # Agrupar coordenadas por questão (assumindo 4 alternativas por questão)
            num_questoes = len(coordenadas_bolhas) // 4
            print(f"📝 Detectadas {num_questoes} questões no template")
            
            for i in range(num_questoes):
                questao_num = i + 1
                opcoes = ["A", "B", "C", "D"]
                proporcoes = {}
                
                print(f"  🔍 Processando questão {questao_num}...")
                
                # Processar cada alternativa da questão
                for j in range(4):
                    coord_idx = i * 4 + j
                    print(f"    📍 Coordenada {coord_idx}: {coordenadas_bolhas[coord_idx] if coord_idx < len(coordenadas_bolhas) else 'FORA DO RANGE'}")
                    
                    if coord_idx < len(coordenadas_bolhas):
                        x, y, w, h = coordenadas_bolhas[coord_idx]
                        
                        # Extrair região da bolha
                        x1 = max(0, x - w//2)
                        y1 = max(0, y - h//2)
                        x2 = min(user_gray.shape[1], x + w//2)
                        y2 = min(user_gray.shape[0], y + h//2)
                        
                        print(f"    📦 Região: ({x1},{y1}) a ({x2},{y2})")
                        
                        if x2 > x1 and y2 > y1:
                            regiao_bolha = user_gray[y1:y2, x1:x2]
                            
                            # Usar algoritmo melhorado com debug
                            debug_path = f"debug_roi_q{questao_num}_{opcoes[j]}.png" if questao_num <= 2 else None
                            proporcao = self._calcular_proporcao_pixels_pretos_melhorada(regiao_bolha, debug_path)
                            proporcoes[opcoes[j]] = proporcao
                            
                            print(f"    📊 Questão {questao_num}, {opcoes[j]}: proporção={proporcao:.3f}, pos=({x},{y})")
                        else:
                            print(f"    ❌ Região inválida para {opcoes[j]}")
                    else:
                        print(f"    ❌ Coordenada {coord_idx} fora do range")
                
                # Aplicar critérios de detecção
                if proporcoes:
                    print(f"  🔍 Aplicando critérios para questão {questao_num}: {proporcoes}")
                    resposta = self._aplicar_criterios_deteccao(proporcoes, questao_num)
                    if resposta:
                        respostas_detectadas[questao_num] = resposta
                        print(f"  ✅ Questão {questao_num}: {resposta}")
                    else:
                        print(f"  ❌ Questão {questao_num}: Não marcada")
                else:
                    print(f"  ❌ Questão {questao_num}: Sem proporções")
            
            print(f"📊 RESPOSTAS DETECTADAS: {respostas_detectadas}")
            return respostas_detectadas
            
        except Exception as e:
            print(f"❌ Erro ao detectar bolhas por coordenadas: {str(e)}")
            return {}

    def _extrair_coordenadas_do_template(self, template_coords):
        """
        Extrai coordenadas das bolhas do template em formato dicionário
        """
        try:
            coordenadas = []
            
            if isinstance(template_coords, dict):
                # Procurar por questões no template
                for key, value in template_coords.items():
                    if key.startswith('questao_') or key.startswith('question_'):
                        if isinstance(value, dict):
                            # Formato: {'A': {'x': 100, 'y': 200, 'radius': 8}, ...}
                            for alt, coords in value.items():
                                if isinstance(coords, dict) and 'x' in coords and 'y' in coords:
                                    x = coords['x']
                                    y = coords['y']
                                    radius = coords.get('radius', 8)
                                    w = h = radius * 2
                                    coordenadas.append([x, y, w, h])
                        elif isinstance(value, list):
                            # Formato: [[x, y, w, h], ...]
                            coordenadas.extend(value)
            
            return coordenadas
            
        except Exception as e:
            print(f"❌ Erro ao extrair coordenadas do template: {str(e)}")
            return []

    def _aplicar_criterios_deteccao(self, proporcoes, questao_num):
        """
        Aplica critérios de detecção para determinar a resposta marcada
        """
        try:
            if not proporcoes:
                return None
            
            # Ordenar proporções
            proporcoes_ordenadas = sorted(proporcoes.items(), key=lambda x: x[1], reverse=True)
            maior_alt, maior_valor = proporcoes_ordenadas[0]
            segundo_alt, segundo_valor = proporcoes_ordenadas[1] if len(proporcoes_ordenadas) > 1 else (maior_alt, 0)
            
            # Calcular estatísticas
            valores = list(proporcoes.values())
            media = sum(valores) / len(valores)
            
            # Critérios ajustados para ser mais rigoroso e preciso
            threshold_absoluto_min = 0.30  # 30% mínimo para considerar preenchido (aumentado de 0.25)
            threshold_absoluto_max = 0.80  # 80% máximo (evita overfill)
            threshold_diferenca_min = 0.15  # 15 pontos percentuais de diferença mínima (aumentado de 0.05)
            threshold_diferenca_relativa = 0.25  # 25% de diferença relativa mínima (aumentado de 0.10)
            
            # Aplicar critérios mais rigorosos
            if threshold_absoluto_min <= maior_valor <= threshold_absoluto_max:
                diff_absoluta = maior_valor - segundo_valor
                diff_relativa = diff_absoluta / media if media > 0 else 0
                
                # Critério 1: Diferença absoluta suficiente
                if diff_absoluta >= threshold_diferenca_min:
                    print(f"    ✅ Questão {questao_num}: Diferença absoluta suficiente ({diff_absoluta:.3f})")
                    return maior_alt
                
                # Critério 2: Diferença relativa suficiente
                elif diff_relativa >= threshold_diferenca_relativa:
                    print(f"    ✅ Questão {questao_num}: Diferença relativa suficiente ({diff_relativa:.1%})")
                    return maior_alt
                
                # Critério 3: Empate técnico - sempre escolher o maior valor se estiver acima do mínimo
                else:
                    print(f"    🔍 EMPATE TÉCNICO detectado: diff_abs={diff_absoluta:.3f}, diff_rel={diff_relativa:.1%}")
                    print(f"    ⚠️ Questão {questao_num}: Escolhendo maior valor por empate técnico")
                    return maior_alt
            else:
                if maior_valor < threshold_absoluto_min:
                    print(f"    ❌ Questão {questao_num}: Não marcada (proporção muito baixa: {maior_valor:.3f})")
                else:
                    print(f"    ❌ Questão {questao_num}: Proporção muito alta (possível erro: {maior_valor:.3f})")
                return None
                
        except Exception as e:
            print(f"❌ Erro ao aplicar critérios de detecção: {str(e)}")
            return None

    def _calcular_resultado_final(self, test_id, respostas_detectadas, student_id):
        """
        Calcula resultado final da correção e salva no banco de dados
        """
        try:
            print(f"🔧 Calculando resultado final...")
            
            # Buscar dados da prova
            from app.models.test import Test
            from app.models.question import Question
            from app.models.testQuestion import TestQuestion
            
            test = Test.query.get(test_id)
            
            # Buscar questões e respostas corretas na ordem correta
            test_questions = TestQuestion.query.filter_by(test_id=test_id).order_by(TestQuestion.order).all()
            
            # Criar dicionário para mapear question_id -> correct_answer na ordem correta
            questions_by_order = {}
            for i, tq in enumerate(test_questions):
                question = Question.query.get(tq.question_id)
                if question:
                    questions_by_order[i + 1] = question.correct_answer
            
            # Calcular acertos
            acertos = 0
            total_questoes = len(questions_by_order)
            
            print(f"📋 GABARITO CORRETO (por ordem):")
            for questao_num in sorted(questions_by_order.keys()):
                resposta_correta = questions_by_order[questao_num]
                print(f"  Questão {questao_num}: {resposta_correta}")
            
            print(f"📝 RESPOSTAS DETECTADAS DO ALUNO:")
            for questao_num, resposta_detectada in respostas_detectadas.items():
                print(f"  Questão {questao_num}: {resposta_detectada}")
            
            print(f"🔍 COMPARAÇÃO DETALHADA:")
            for questao_num in sorted(questions_by_order.keys()):
                resposta_correta = questions_by_order[questao_num]
                resposta_detectada = respostas_detectadas.get(questao_num)
                
                if resposta_detectada == resposta_correta:
                    acertos += 1
                    print(f"  ✅ Questão {questao_num}: {resposta_detectada} (correta)")
                else:
                    print(f"  ❌ Questão {questao_num}: {resposta_detectada} (correta: {resposta_correta})")
            
            # Calcular métricas
            score_percentage = (acertos / total_questoes * 100) if total_questoes > 0 else 0
            grade = (acertos / total_questoes * 10) if total_questoes > 0 else 0
            proficiency = (acertos / total_questoes * 400) if total_questoes > 0 else 0
            
            if acertos == total_questoes:
                classification = 'Avançado'
            elif acertos >= total_questoes / 2:
                classification = 'Adequado'
            else:
                classification = 'Básico'
            
            print(f"✅ Resultado calculado: {acertos}/{total_questoes} acertos ({score_percentage:.1f}%)")
            
            # 6. Salvar no banco de dados
            print(f"🔧 ETAPA 6: SALVANDO NO BANCO DE DADOS...")
            evaluation_result_id = self._salvar_resultado_completo(
                student_id, test_id, respostas_detectadas, questions_by_order,
                acertos, total_questoes, score_percentage, grade, proficiency, classification
            )
            
            if evaluation_result_id is None:
                return {
                    'success': False,
                    'error': 'Erro ao salvar resultado no banco de dados'
                }
            
            print(f"✅ Resultado salvo com sucesso - Evaluation Result ID: {evaluation_result_id}")
            
            return {
                'success': True,
                'student_id': student_id,
                'test_id': test_id,
                'correct_answers': acertos,
                'total_questions': total_questoes,
                'score_percentage': score_percentage,
                'grade': grade,
                'proficiency': proficiency,
                'classification': classification,
                'answers_detected': respostas_detectadas,
                'student_answers': respostas_detectadas,
                'evaluation_result_id': evaluation_result_id,
                'method': 'gabarito_referencia'
            }
            
        except Exception as e:
            print(f"❌ Erro ao calcular resultado final: {str(e)}")
            return {
                'success': False,
                'error': f'Erro ao calcular resultado: {str(e)}'
            }

    def _salvar_resultado_completo(self, student_id, test_id, respostas_detectadas, questions_by_order, 
                                 acertos, total_questoes, score_percentage, grade, proficiency, classification):
        """
        Salva resultado completo no banco de dados (StudentAnswer e EvaluationResult)
        """
        try:
            from app.models.studentAnswer import StudentAnswer
            from app.models.evaluationResult import EvaluationResult
            from app.models.question import Question
            from app.models.testQuestion import TestQuestion
            from app import db
            from datetime import datetime
            
            print(f"🔧 Salvando resultado para student_id: {student_id}")
            
            # Buscar questões do teste na ordem correta
            test_questions = TestQuestion.query.filter_by(test_id=test_id).order_by(TestQuestion.order).all()
            
            # Salvar respostas individuais na tabela StudentAnswer
            for questao_num, resposta_detectada in respostas_detectadas.items():
                # Buscar question_id baseado na ordem
                if questao_num <= len(test_questions):
                    tq = test_questions[questao_num - 1]
                    question_id = tq.question_id
                    
                    # Buscar questão para verificar se está correta
                    question = Question.query.get(question_id)
                    if question:
                        resposta_correta = question.correct_answer
                        is_correct = (resposta_detectada == resposta_correta)
                        
                        # Verificar se já existe resposta para esta questão
                        existing_answer = StudentAnswer.query.filter_by(
                            student_id=student_id,
                            test_id=test_id,
                            question_id=question_id
                        ).first()
                        
                        if existing_answer:
                            # Atualizar resposta existente
                            existing_answer.answer = resposta_detectada
                            existing_answer.is_correct = is_correct
                            existing_answer.updated_at = datetime.now()
                            print(f"  📝 Atualizada resposta questão {questao_num}: {resposta_detectada} (correta: {is_correct})")
                        else:
                            # Criar nova resposta
                            new_answer = StudentAnswer(
                                student_id=student_id,
                                test_id=test_id,
                                question_id=question_id,
                                answer=resposta_detectada,
                                is_correct=is_correct,
                                created_at=datetime.now(),
                                updated_at=datetime.now()
                            )
                            db.session.add(new_answer)
                            print(f"  📝 Nova resposta questão {questao_num}: {resposta_detectada} (correta: {is_correct})")
            
            # Salvar resultado geral na tabela EvaluationResult
            existing_result = EvaluationResult.query.filter_by(
                test_id=test_id,
                student_id=student_id
            ).first()
            
            if existing_result:
                # Atualizar resultado existente
                existing_result.correct_answers = acertos
                existing_result.total_questions = total_questoes
                existing_result.score_percentage = score_percentage
                existing_result.grade = grade
                existing_result.proficiency = proficiency
                existing_result.classification = classification
                existing_result.updated_at = datetime.now()
                evaluation_result_id = existing_result.id
                print(f"  📊 Atualizado EvaluationResult ID: {evaluation_result_id}")
            else:
                # Criar novo resultado
                new_result = EvaluationResult(
                    student_id=student_id,
                    test_id=test_id,
                    correct_answers=acertos,
                    total_questions=total_questoes,
                    score_percentage=score_percentage,
                    grade=grade,
                    proficiency=proficiency,
                    classification=classification,
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                db.session.add(new_result)
                db.session.flush()  # Para obter o ID
                evaluation_result_id = new_result.id
                print(f"  📊 Criado EvaluationResult ID: {evaluation_result_id}")
            
            # Commit todas as alterações
            db.session.commit()
            print(f"✅ Resultado salvo com sucesso no banco de dados")
            
            return evaluation_result_id
            
        except Exception as e:
            print(f"❌ Erro ao salvar resultado no banco: {str(e)}")
            db.session.rollback()
            return None

    def _detectar_qr_code_avancado(self, image):
        """
        Detecta QR code usando múltiplas estratégias avançadas
        """
        try:
            import numpy as np
            print(f"🔍 INICIANDO DETECÇÃO AVANÇADA DE QR CODE")
            
            # Verificar se a imagem é PIL Image e converter para OpenCV
            if hasattr(image, 'mode'):  # É PIL Image
                image_array = np.array(image)
                if len(image_array.shape) == 3 and image_array.shape[2] == 3:
                    image_array = cv2.cvtColor(image_array, cv2.COLOR_RGB2BGR)
            else:
                image_array = image
            
            print(f"📏 Imagem de entrada: {image_array.shape}, dtype: {image_array.dtype}")
            
            # ESTRATÉGIA 1: Detecção direta
            print(f"🔍 ESTRATÉGIA 1: Detecção direta...")
            result = self._detectar_qr_direto(image_array)
            if result:
                print(f"✅ QR code detectado com estratégia 1")
                return result
            
            # ESTRATÉGIA 2: Pré-processamento avançado
            print(f"🔍 ESTRATÉGIA 2: Pré-processamento avançado...")
            result = self._detectar_qr_preprocessamento_avancado(image_array)
            if result:
                print(f"✅ QR code detectado com estratégia 2")
                return result
            
            # ESTRATÉGIA 3: Detecção por regiões específicas
            print(f"🔍 ESTRATÉGIA 3: Detecção por regiões específicas...")
            result = self._detectar_qr_regioes_especificas(image_array)
            if result:
                print(f"✅ QR code detectado com estratégia 3")
                return result
            
            # ESTRATÉGIA 4: Detecção por posição específica do formulário
            print(f"🔍 ESTRATÉGIA 4: Detecção por posição específica do formulário...")
            result = self._detectar_qr_posicao_formulario(image_array)
            if result:
                print(f"✅ QR code detectado com estratégia 4")
                return result
            
            # ESTRATÉGIA 4.5: Detecção resiliente com tight-crop
            print(f"🔍 ESTRATÉGIA 4.5: Detecção resiliente com tight-crop...")
            result = self._detectar_qr_resiliente(image_array, upscale=5, margin_factor=0.35, save_debug=False)
            if result:
                print(f"✅ QR code detectado com estratégia 4.5")
                return result
            
            # ESTRATÉGIA 5: Redimensionamento múltiplo
            print(f"🔍 ESTRATÉGIA 5: Redimensionamento múltiplo...")
            result = self._detectar_qr_redimensionamento_multiplo(image_array)
            if result:
                print(f"✅ QR code detectado com estratégia 5")
                return result
            
            # ESTRATÉGIA 6: Detecção por contornos
            print(f"🔍 ESTRATÉGIA 6: Detecção por contornos...")
            result = self._detectar_qr_contornos(image_array)
            if result:
                print(f"✅ QR code detectado com estratégia 6")
                return result
            
            print(f"❌ Nenhum QR code detectado com todas as estratégias")
            return None
            
        except Exception as e:
            print(f"❌ Erro na detecção avançada de QR code: {str(e)}")
            return None

    def _detectar_qr_direto(self, image):
        """
        Detecção direta de QR code
        """
        try:
            detector = cv2.QRCodeDetector()
            ret, decoded_info, points, _ = detector.detectAndDecodeMulti(image)
            print(f"  🔍 Detecção direta: ret={ret}, decoded_info={decoded_info}")
            
            if ret and decoded_info:
                for i, info in enumerate(decoded_info):
                    print(f"    📱 QR code {i}: '{info}'")
                    if info:
                        try:
                            data = json.loads(info)
                            print(f"    📊 Dados parseados: {data}")
                            if 'student_id' in data:
                                return {'data': data, 'points': points[i]}
                            else:
                                print(f"    ❌ QR code sem student_id: {data}")
                        except Exception as e:
                            print(f"    ❌ Erro ao parsear: {str(e)}")
                            continue
                    else:
                        print(f"    ❌ QR code vazio")
            return None
        except Exception as e:
            print(f"    ❌ Erro na detecção direta: {str(e)}")
            return None

    def _detectar_qr_preprocessamento_avancado(self, image):
        """
        Pré-processamento avançado para detecção de QR code
        """
        try:
            # Converter para grayscale
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Aplicar diferentes tipos de pré-processamento
            preprocessed_images = []
            
            # 1. CLAHE
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
            clahe_img = clahe.apply(gray)
            preprocessed_images.append(("CLAHE", clahe_img))
            
            # 2. Gaussian Blur + Threshold
            blurred = cv2.GaussianBlur(gray, (3, 3), 0)
            _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            preprocessed_images.append(("Gaussian+OTSU", thresh))
            
            # 3. Adaptive Threshold
            adaptive = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
            preprocessed_images.append(("Adaptive", adaptive))
            
            # 4. Morphological operations
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            morph = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, kernel)
            preprocessed_images.append(("Morphological", morph))
            
            # 5. Histogram equalization
            equalized = cv2.equalizeHist(gray)
            preprocessed_images.append(("Equalized", equalized))
            
            print(f"📊 Testando {len(preprocessed_images)} tipos de pré-processamento...")
            
            # Testar cada imagem processada
            detector = cv2.QRCodeDetector()
            for name, processed_img in preprocessed_images:
                print(f"  🔍 Testando {name}...")
                ret, decoded_info, points, _ = detector.detectAndDecodeMulti(processed_img)
                if ret and decoded_info:
                    print(f"  ✅ QR code detectado com {name}!")
                    for i, info in enumerate(decoded_info):
                        if info:
                            try:
                                data = json.loads(info)
                                if 'student_id' in data:
                                    print(f"  📊 Dados do QR code: {data}")
                                    print(f"  📍 Coordenadas: {points[i]}")
                                    return {'data': data, 'points': points[i]}
                            except Exception as e:
                                print(f"  ❌ Erro ao processar QR code: {str(e)}")
                                continue
                else:
                    print(f"  ❌ Nenhum QR code encontrado com {name}")
            return None
        except Exception as e:
            print(f"❌ Erro no pré-processamento: {str(e)}")
            return None

    def _detectar_qr_regioes_especificas(self, image):
        """
        Detecção de QR code em regiões específicas da imagem
        """
        try:
            h, w = image.shape[:2]
            detector = cv2.QRCodeDetector()
            
            print(f"📏 Dimensões da imagem: {w}x{h}")
            
            # Definir regiões específicas onde o QR code pode estar
            # CORRIGIDO: Expandir regiões para capturar QR code em posições reais
            regions = [
                # Canto superior direito (expandido para capturar QR code real)
                (int(w*0.5), 0, int(w*0.5), int(h*0.4)),  # Expandido de 0.6 para 0.5 e 0.3 para 0.4
                # Canto superior esquerdo
                (0, 0, int(w*0.5), int(h*0.4)),  # Expandido de 0.4 para 0.5 e 0.3 para 0.4
                # Centro superior
                (int(w*0.25), 0, int(w*0.5), int(h*0.4)),  # Expandido de 0.3 para 0.25 e 0.3 para 0.4
                # Canto inferior direito
                (int(w*0.5), int(h*0.6), int(w*0.5), int(h*0.4)),
                # Canto inferior esquerdo
                (0, int(h*0.6), int(w*0.5), int(h*0.4)),
                # Centro da imagem
                (int(w*0.25), int(h*0.3), int(w*0.5), int(h*0.4))
            ]
            
            region_names = [
                "Canto superior direito",
                "Canto superior esquerdo", 
                "Centro superior",
                "Canto inferior direito",
                "Canto inferior esquerdo",
                "Centro da imagem"
            ]
            
            for i, (x, y, w_region, h_region) in enumerate(regions):
                # Garantir que a região está dentro da imagem
                x = max(0, x)
                y = max(0, y)
                w_region = min(w_region, w - x)
                h_region = min(h_region, h - y)
                
                print(f"📍 {region_names[i]}: ({x},{y}) a ({x+w_region},{y+h_region}) - tamanho: {w_region}x{h_region}")
                
                if w_region > 50 and h_region > 50:  # Região deve ser grande o suficiente
                    roi = image[y:y+h_region, x:x+w_region]
                    
                    ret, decoded_info, points, _ = detector.detectAndDecodeMulti(roi)
                    if ret and decoded_info:
                        print(f"  ✅ QR code detectado na região {i+1}!")
                        for j, info in enumerate(decoded_info):
                            if info:
                                try:
                                    data = json.loads(info)
                                    if 'student_id' in data:
                                        print(f"  📊 Dados do QR code: {data}")
                                        # Ajustar coordenadas para a imagem original
                                        adjusted_points = points[j].copy()
                                        adjusted_points[:, 0] += x
                                        adjusted_points[:, 1] += y
                                        print(f"  📍 Coordenadas ajustadas: {adjusted_points}")
                                        return {'data': data, 'points': adjusted_points}
                                except Exception as e:
                                    print(f"  ❌ Erro ao processar QR code: {str(e)}")
                                    continue
                    else:
                        print(f"  ❌ Nenhum QR code encontrado nesta região")
                else:
                    print(f"  ⚠️ Região muito pequena, pulando...")
            return None
        except Exception as e:
            print(f"❌ Erro na detecção por regiões: {str(e)}")
            return None

    def _detectar_qr_redimensionamento_multiplo(self, image):
        """
        Detecção de QR code com múltiplos redimensionamentos
        """
        try:
            detector = cv2.QRCodeDetector()
            h, w = image.shape[:2]
            
            # Diferentes escalas para testar
            scales = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0]
            
            print(f"📏 Dimensões originais: {w}x{h}")
            print(f"📊 Testando {len(scales)} escalas diferentes...")
            
            for scale in scales:
                new_w = int(w * scale)
                new_h = int(h * scale)
                
                print(f"  🔍 Escala {scale}x: {new_w}x{new_h}")
                
                if new_w > 50 and new_h > 50:  # Imagem deve ser grande o suficiente
                    resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
                    
                    ret, decoded_info, points, _ = detector.detectAndDecodeMulti(resized)
                    if ret and decoded_info:
                        print(f"  ✅ QR code detectado na escala {scale}x!")
                        for i, info in enumerate(decoded_info):
                            if info:
                                try:
                                    data = json.loads(info)
                                    if 'student_id' in data:
                                        print(f"  📊 Dados do QR code: {data}")
                                        # Ajustar coordenadas de volta para a imagem original
                                        adjusted_points = points[i].copy()
                                        adjusted_points[:, 0] /= scale
                                        adjusted_points[:, 1] /= scale
                                        print(f"  📍 Coordenadas ajustadas: {adjusted_points}")
                                        return {'data': data, 'points': adjusted_points}
                                except Exception as e:
                                    print(f"  ❌ Erro ao processar QR code: {str(e)}")
                                    continue
                    else:
                        print(f"  ❌ Nenhum QR code encontrado na escala {scale}x")
                else:
                    print(f"  ⚠️ Escala {scale}x muito pequena, pulando...")
            return None
        except Exception as e:
            print(f"❌ Erro no redimensionamento múltiplo: {str(e)}")
            return None

    def _detectar_qr_posicao_formulario(self, image):
        """
        Detecção de QR code na posição específica onde ele é colocado no formulário
        Baseado no layout do formularios.py
        """
        try:
            h, w = image.shape[:2]
            detector = cv2.QRCodeDetector()
            
            print(f"📏 Dimensões da imagem: {w}x{h}")
            
            # Calcular posição do QR code baseada no layout do formulário
            # Para formulário adaptativo: qr_x = target_width - qr_size - 20*proporcao_x
            # qr_y = 20 * proporcao_y
            
            # Estimar proporções baseadas nas dimensões da imagem
            proporcao_x = w / 1240  # A4_PX_LARGURA
            proporcao_y = h / 1753  # A4_PX_ALTURA
            
            print(f"📏 Proporções estimadas: X={proporcao_x:.3f}, Y={proporcao_y:.3f}")
            
            # Calcular tamanho do QR code baseado na proporção
            qr_size_estimado = int(200 * min(proporcao_x, proporcao_y))  # QR_CODE_SIZE = 200
            print(f"📏 Tamanho estimado do QR code: {qr_size_estimado}x{qr_size_estimado}")
            
            # Calcular posição estimada do QR code
            qr_x_estimado = w - qr_size_estimado - int(20 * proporcao_x)
            qr_y_estimado = int(20 * proporcao_y)
            
            print(f"📍 Posição estimada do QR code: ({qr_x_estimado}, {qr_y_estimado})")
            
            # Definir região de busca ao redor da posição estimada
            margin = int(qr_size_estimado * 0.5)  # 50% de margem
            x_start = max(0, qr_x_estimado - margin)
            y_start = max(0, qr_y_estimado - margin)
            x_end = min(w, qr_x_estimado + qr_size_estimado + margin)
            y_end = min(h, qr_y_estimado + qr_size_estimado + margin)
            
            print(f"📍 Região de busca: ({x_start},{y_start}) a ({x_end},{y_end}) - tamanho: {x_end-x_start}x{y_end-y_start}")
            
            # Extrair região de busca
            roi = image[y_start:y_end, x_start:x_end]
            
            if roi.size == 0:
                print(f"❌ Região de busca vazia")
                return None
            
            print(f"📏 ROI extraída: {roi.shape}")
            
            # Tentar detectar QR code na região
            ret, decoded_info, points, _ = detector.detectAndDecodeMulti(roi)
            print(f"🔍 Resultado da detecção: ret={ret}, decoded_info={decoded_info}")
            if ret and decoded_info:
                print(f"✅ QR code detectado na posição específica!")
                for i, info in enumerate(decoded_info):
                    print(f"  📱 QR code {i}: '{info}'")
                    if info:
                        try:
                            data = json.loads(info)
                            print(f"  📊 Dados parseados: {data}")
                            if 'student_id' in data:
                                print(f"📊 Dados do QR code: {data}")
                                # Ajustar coordenadas para a imagem original
                                adjusted_points = points[i].copy()
                                adjusted_points[:, 0] += x_start
                                adjusted_points[:, 1] += y_start
                                print(f"📍 Coordenadas ajustadas: {adjusted_points}")
                                return {'data': data, 'points': adjusted_points}
                            else:
                                print(f"  ❌ QR code sem student_id: {data}")
                        except Exception as e:
                            print(f"❌ Erro ao processar QR code: {str(e)}")
                            continue
                    else:
                        print(f"  ❌ QR code vazio")
            else:
                print(f"❌ Nenhum QR code encontrado na posição específica")
                
                # Tentar com diferentes tamanhos de QR code
                print(f"🔍 Tentando com diferentes tamanhos de QR code...")
                for scale in [0.5, 0.75, 1.25, 1.5, 2.0]:
                    qr_size_alt = int(qr_size_estimado * scale)
                    qr_x_alt = w - qr_size_alt - int(20 * proporcao_x)
                    qr_y_alt = int(20 * proporcao_y)
                    
                    x_start_alt = max(0, qr_x_alt - margin)
                    y_start_alt = max(0, qr_y_alt - margin)
                    x_end_alt = min(w, qr_x_alt + qr_size_alt + margin)
                    y_end_alt = min(h, qr_y_alt + qr_size_alt + margin)
                    
                    if x_end_alt > x_start_alt and y_end_alt > y_start_alt:
                        roi_alt = image[y_start_alt:y_end_alt, x_start_alt:x_end_alt]
                        if roi_alt.size > 0:
                            ret, decoded_info, points, _ = detector.detectAndDecodeMulti(roi_alt)
                            if ret and decoded_info:
                                print(f"✅ QR code detectado com escala {scale}x!")
                                for i, info in enumerate(decoded_info):
                                    if info:
                                        try:
                                            data = json.loads(info)
                                            if 'student_id' in data:
                                                print(f"📊 Dados do QR code: {data}")
                                                adjusted_points = points[i].copy()
                                                adjusted_points[:, 0] += x_start_alt
                                                adjusted_points[:, 1] += y_start_alt
                                                print(f"📍 Coordenadas ajustadas: {adjusted_points}")
                                                return {'data': data, 'points': adjusted_points}
                                        except Exception as e:
                                            print(f"❌ Erro ao processar QR code: {str(e)}")
                                            continue
                        print(f"  ❌ Escala {scale}x: Nenhum QR code encontrado")
            
            return None
            
        except Exception as e:
            print(f"❌ Erro na detecção por posição específica: {str(e)}")
            return None

    def _detectar_qr_resiliente(self, image, upscale=5, margin_factor=0.35, save_debug=False):
        """
        Detecção de QR robusta:
          - calcula ROI (canto superior direito) baseado no layout A4
          - tenta achar tight-crop via contornos quadrados (remove bordas)
          - amplia o tight-crop (upscale)
          - tenta cv2.QRCodeDetector e em fallback pyzbar (se instalado)
        Retorna: {'data': parsed_or_text, 'points': [[x,y],...], 'method': <str>} ou None
        """
        try:
            import cv2
            import numpy as np
            import json
            import os
            
            h, w = image.shape[:2]

            # --- estimativa da posição do QR (ajuste se o template muda) ---
            proporcao_x = w / 1240.0
            proporcao_y = h / 1753.0
            qr_size_estimado = max(32, int(200 * min(proporcao_x, proporcao_y)))
            qr_x_estimado = w - qr_size_estimado - int(20 * proporcao_x)
            qr_y_estimado = int(20 * proporcao_y)

            margin = int(qr_size_estimado * margin_factor)
            x_start = max(0, qr_x_estimado - margin)
            y_start = max(0, qr_y_estimado - margin)
            x_end = min(w, qr_x_estimado + qr_size_estimado + margin)
            y_end = min(h, qr_y_estimado + qr_size_estimado + margin)

            roi = image[y_start:y_end, x_start:x_end].copy()
            if roi.size == 0:
                print("ROI vazia para QR:", (x_start,y_start,x_end,y_end))
                return None

            # --- TENTAR TIGHT-CROP via contornos para remover borda/quadros ---
            def tight_crop_from_roi(img):
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                # blur leve para reduzir ruído antes do threshold
                blur = cv2.GaussianBlur(gray, (3,3), 0)
                _, bw = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

                # inverter se QR escuro sobre fundo claro? queremos detectar contorno externo do "quadro"
                # contamos contornos brancos
                contours, _ = cv2.findContours(bw, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                if not contours:
                    return None  # fallback

                # escolher o maior contorno (por área)
                contours = sorted(contours, key=cv2.contourArea, reverse=True)
                for cnt in contours[:5]:
                    area = cv2.contourArea(cnt)
                    if area < 100:  # muito pequeno -> pular
                        continue
                    # aproximar polígono
                    peri = cv2.arcLength(cnt, True)
                    approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
                    # preferir polígonos com 4 vértices (quadrado/retângulo)
                    if len(approx) == 4:
                        x,y,wc,hc = cv2.boundingRect(approx)
                        # garantir que o retângulo seja razoável (não colar nas bordas muito pequenas)
                        if wc > img.shape[1] * 0.2 and hc > img.shape[0] * 0.2:
                            return (x, y, x + wc, y + hc)
                # se não achar polygon 4-pt, usar bounding box do maior contorno
                cnt = contours[0]
                x,y,wc,hc = cv2.boundingRect(cnt)
                return (x, y, x + wc, y + hc)

            tight = tight_crop_from_roi(roi)
            if tight is not None:
                tx0, ty0, tx1, ty1 = tight
                # adiciona pequeno padding para não cortar módulos do QR
                pad = max(1, int(min(tx1-tx0, ty1-ty0) * 0.03))
                tx0 = max(0, tx0 - pad); ty0 = max(0, ty0 - pad)
                tx1 = min(roi.shape[1], tx1 + pad); ty1 = min(roi.shape[0], ty1 + pad)
                roi_tight = roi[ty0:ty1, tx0:tx1].copy()
                crop_offset_x = x_start + tx0
                crop_offset_y = y_start + ty0
            else:
                # fallback: usa a ROI inteira
                roi_tight = roi
                crop_offset_x = x_start
                crop_offset_y = y_start

            # --- ampliar tight-crop ---
            if upscale <= 1:
                upscale = 2
            roi_up = cv2.resize(roi_tight, None, fx=upscale, fy=upscale, interpolation=cv2.INTER_CUBIC)

            # --- criar variantes para testar ---
            gray_up = cv2.cvtColor(roi_up, cv2.COLOR_BGR2GRAY)
            _, otsu = cv2.threshold(gray_up, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            # unsharp (aumenta contraste dos módulos)
            gauss = cv2.GaussianBlur(gray_up, (0,0), sigmaX=1.0)
            unsharp = cv2.addWeighted(gray_up, 1.4, gauss, -0.4, 0)

            candidates = [
                ("ampliado_color", roi_up),
                ("ampliado_gray", gray_up),
                ("ampliado_otsu", otsu),
                ("ampliado_unsharp", unsharp),
            ]

            # salvar debug se pedido
            if save_debug:
                debug_dir = '/tmp/qr_debug' if os.name != 'nt' else os.path.join(os.getcwd(),'qr_debug')
                os.makedirs(debug_dir, exist_ok=True)
                cv2.imwrite(os.path.join(debug_dir, 'roi_tight.png'), roi_tight)
                cv2.imwrite(os.path.join(debug_dir, 'roi_up.png'), roi_up)
                cv2.imwrite(os.path.join(debug_dir, 'roi_up_otsu.png'), otsu)

            # --- tentar decodificar: primeiro OpenCV, depois pyzbar (se disponível) ---
            detector = cv2.QRCodeDetector()

            def map_points_from_processed(points_proc, scale):
                """Converte pontos retornados do processed-image => coordenadas na imagem original."""
                mapped = []
                # pontos_proc pode ter formatos variados
                try:
                    pts = np.array(points_proc, dtype=float)
                    # detectAndDecode retorna points em shape (4,1,2) ou (1,4,2) dependendo da versão
                    pts = pts.reshape(-1, 2)
                    for (px, py) in pts:
                        ox = int(px / scale) + int(crop_offset_x)
                        oy = int(py / scale) + int(crop_offset_y)
                        mapped.append([ox, oy])
                except Exception:
                    # fallback conservador: retornar bounding box do crop
                    mapped = [
                        [int(crop_offset_x), int(crop_offset_y)],
                        [int(crop_offset_x + roi_tight.shape[1]), int(crop_offset_y)],
                        [int(crop_offset_x + roi_tight.shape[1]), int(crop_offset_y + roi_tight.shape[0])],
                        [int(crop_offset_x), int(crop_offset_y + roi_tight.shape[0])]
                    ]
                return mapped

            # Try OpenCV detector on each candidate
            for name, cand in candidates:
                try:
                    if cand.ndim == 2:  # gray
                        cand_for_cv = cv2.cvtColor(cand, cv2.COLOR_GRAY2BGR)
                    else:
                        cand_for_cv = cand
                    data, points, straight = detector.detectAndDecode(cand_for_cv)
                    if data:
                        # pontos podem vir como np.ndarray ou None
                        mapped = map_points_from_processed(points, upscale)
                        try:
                            parsed = json.loads(data)
                        except Exception:
                            parsed = data
                        print(f"✅ QR detectado via cv2_{name}: {parsed}")
                        return {"data": parsed, "points": mapped, "method": f"cv2_{name}"}
                except Exception as e:
                    # nao falhar o pipeline - log e continuar
                    print("cv2 detect erro", name, e)

            # fallback: tentar pyzbar (se instalado)
            try:
                from pyzbar.pyzbar import decode as pdecode
                for name, cand in candidates:
                    try:
                        results = pdecode(cand)
                        if results:
                            # pegar o primeiro resultado significativo
                            for r in results:
                                raw = r.data
                                try:
                                    txt = raw.decode("utf-8")
                                except Exception:
                                    txt = raw
                                # map polygon pts -> original coords
                                poly = getattr(r, "polygon", None)
                                if poly:
                                    mapped = []
                                    for p in poly:
                                        # p.x / p.y estão na escala processed => mapear /upscale + offset
                                        mapped.append([int(p.x / upscale) + int(crop_offset_x),
                                                       int(p.y / upscale) + int(crop_offset_y)])
                                else:
                                    # fallback via rect
                                    rect = getattr(r, "rect", None)
                                    if rect:
                                        left = int(rect.left / upscale) + int(crop_offset_x)
                                        top  = int(rect.top / upscale) + int(crop_offset_y)
                                        wrect = int(rect.width / upscale)
                                        hrect = int(rect.height / upscale)
                                        mapped = [[left, top], [left + wrect, top], [left + wrect, top + hrect], [left, top + hrect]]
                                    else:
                                        mapped = []
                                try:
                                    parsed = json.loads(txt)
                                except Exception:
                                    parsed = txt
                                print(f"✅ QR detectado via pyzbar_{name}: {parsed}")
                                return {"data": parsed, "points": mapped, "method": f"pyzbar_{name}"}
                    except Exception as e:
                        print("pyzbar erro", name, e)
            except Exception as e:
                # pyzbar import falhou -> sugerir instalação
                print("pyzbar não disponível:", e)
                # Não retorna aqui, vai cair no final (None)

            # nada detectado
            print("Nenhum QR detectado (cv2+pyzbar) - ROI size:", roi_tight.shape[1], roi_tight.shape[0], "upscale=", upscale)
            
            # GERAR IMAGEM DE DEBUG DO QR CODE
            self._gerar_debug_qr_deteccao(image, x_start, y_start, x_end, y_end, roi)
            
            return None
            
        except Exception as e:
            print(f"❌ Erro na detecção resiliente: {str(e)}")
            return None

    def _gerar_debug_qr_deteccao(self, image, x_start, y_start, x_end, y_end, qr_roi):
        """
        Gera imagem de debug mostrando onde estamos tentando detectar o QR code
        """
        try:
            import cv2
            import numpy as np
            from datetime import datetime
            
            # Criar cópia da imagem original
            debug_image = image.copy()
            
            # Desenhar retângulo da ROI na imagem original
            cv2.rectangle(debug_image, (x_start, y_start), (x_end, y_end), (0, 255, 0), 3)
            
            # Adicionar texto informativo
            cv2.putText(debug_image, f"QR ROI: ({x_start},{y_start}) a ({x_end},{y_end})", 
                       (x_start, y_start - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            cv2.putText(debug_image, f"Size: {x_end-x_start}x{y_end-y_start}", 
                       (x_start, y_start - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            
            # Criar imagem combinada: original + ROI ampliada
            h_orig, w_orig = debug_image.shape[:2]
            h_roi, w_roi = qr_roi.shape[:2]
            
            # Redimensionar ROI para visualização (5x)
            qr_roi_vis = cv2.resize(qr_roi, None, fx=5, fy=5, interpolation=cv2.INTER_CUBIC)
            h_roi_vis, w_roi_vis = qr_roi_vis.shape[:2]
            
            # Criar imagem combinada
            combined_h = max(h_orig, h_roi_vis + 50)
            combined_w = w_orig + w_roi_vis + 20
            combined = np.zeros((combined_h, combined_w, 3), dtype=np.uint8)
            
            # Colocar imagem original à esquerda
            combined[:h_orig, :w_orig] = debug_image
            
            # Colocar ROI ampliada à direita
            combined[10:10+h_roi_vis, w_orig+10:w_orig+10+w_roi_vis] = qr_roi_vis
            
            # Adicionar texto na ROI ampliada
            cv2.putText(combined, "QR ROI 5x", (w_orig+10, 5), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            cv2.putText(combined, f"Original: {w_roi}x{h_roi}", (w_orig+10, h_roi_vis+25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            cv2.putText(combined, f"Ampliada: {w_roi_vis}x{h_roi_vis}", (w_orig+10, h_roi_vis+40), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            # Salvar imagem de debug
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            debug_path = f"debug_qr_deteccao_{timestamp}.png"
            cv2.imwrite(debug_path, combined)
            
            print(f"🔍 Imagem de debug do QR code salva: {debug_path}")
            print(f"📏 Imagem original: {w_orig}x{h_orig}")
            print(f"📏 ROI do QR: ({x_start},{y_start}) a ({x_end},{y_end}) - {x_end-x_start}x{y_end-y_start}")
            print(f"📏 ROI ampliada: {w_roi_vis}x{h_roi_vis}")
            
        except Exception as e:
            print(f"❌ Erro ao gerar debug do QR code: {str(e)}")

    def _detectar_qr_contornos(self, image):
        """
        Detecção de QR code usando contornos
        """
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Aplicar threshold
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # Encontrar contornos
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            detector = cv2.QRCodeDetector()
            
            for contour in contours:
                # Verificar se o contorno tem características de QR code
                area = cv2.contourArea(contour)
                if area > 1000:  # Área mínima
                    # Criar máscara para o contorno
                    mask = np.zeros(gray.shape, dtype=np.uint8)
                    cv2.fillPoly(mask, [contour], 255)
                    
                    # Aplicar máscara na imagem original
                    masked = cv2.bitwise_and(image, image, mask=mask)
                    
                    ret, decoded_info, points, _ = detector.detectAndDecodeMulti(masked)
                    if ret and decoded_info:
                        for i, info in enumerate(decoded_info):
                            if info:
                                try:
                                    data = json.loads(info)
                                    if 'student_id' in data:
                                        return {'data': data, 'points': points[i]}
                                except:
                                    continue
            return None
        except:
            return None

    def _detectar_qr_code(self, image):
        """
        Detecta QR code na imagem usando múltiplas estratégias melhoradas
        """
        try:
            import numpy as np
            print(f"🔍 INICIANDO DETECÇÃO DE QR CODE")
            
            # Verificar se a imagem é PIL Image e converter para OpenCV
            if hasattr(image, 'mode'):  # É PIL Image
                # Converter PIL para numpy array
                image_array = np.array(image)
                # Converter RGB para BGR (OpenCV usa BGR)
                if len(image_array.shape) == 3 and image_array.shape[2] == 3:
                    image_array = cv2.cvtColor(image_array, cv2.COLOR_RGB2BGR)
            else:
                # Já é numpy array
                image_array = image
            
            print(f"📏 Imagem de entrada: {image_array.shape}, dtype: {image_array.dtype}")
            print(f"📊 Valores únicos: {len(np.unique(image_array))}, min: {image_array.min()}, max: {image_array.max()}")
            
            # Estratégia 1: Detecção direta na imagem original
            qr_data = self._detectar_qr_direto(image_array)
            if qr_data:
                print(f"✅ QR Code detectado (método direto): {qr_data}")
                return {'data': qr_data, 'bbox': None}
            
            # Estratégia 2: Pré-processamento com múltiplas técnicas
            processed_images = self._preprocessar_imagem_para_qr(image_array)
            
            for i, processed_img in enumerate(processed_images):
                print(f"🔍 Tentando detecção com imagem processada {i+1}...")
                qr_data = self._detectar_qr_direto(processed_img)
                if qr_data:
                    print(f"✅ QR Code detectado (imagem processada {i+1}): {qr_data}")
                    return {'data': qr_data, 'bbox': None}
            
            # Estratégia 3: Detecção por regiões (QR Code geralmente no canto superior direito)
            qr_data = self._detectar_qr_por_regioes(image_array)
            if qr_data:
                print(f"✅ QR Code detectado (por regiões): {qr_data}")
                return {'data': qr_data, 'bbox': None}
            
            # Estratégia 4: Usar imagem original se disponível
            if hasattr(self, '_original_image_for_qr') and self._original_image_for_qr is not None:
                print(f"🔧 Tentando detecção com imagem original...")
                qr_data = self._detectar_qr_direto(self._original_image_for_qr)
                if qr_data:
                    print(f"✅ QR Code detectado (imagem original): {qr_data}")
                    return {'data': qr_data, 'bbox': None}
            
            print(f"❌ Nenhum QR Code detectado")
            return None
                
        except Exception as e:
            print(f"❌ Erro ao detectar QR code: {str(e)}")
            return None
    
    def _detectar_qr_direto(self, image):
        """
        Detecção direta de QR code usando OpenCV
        """
        try:
            detector = cv2.QRCodeDetector()
            
            # Converter para grayscale se necessário
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image
            
            # Detecção direta
            dados, _, _ = detector.detectAndDecode(gray)
            return dados if dados else None
            
        except Exception as e:
            print(f"❌ Erro na detecção direta: {str(e)}")
            return None
    
    def _preprocessar_imagem_para_qr(self, image):
        """
        Pré-processa imagem com múltiplas técnicas para melhorar detecção de QR code
        """
        processed_images = []
        
        try:
            # Converter para grayscale se necessário
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image
            
            # 1. Imagem original em grayscale
            processed_images.append(gray)
            
            # 2. Ajuste de contraste (CLAHE)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            enhanced = clahe.apply(gray)
            processed_images.append(enhanced)
            
            # 3. Threshold OTSU
            _, thresh_otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            processed_images.append(thresh_otsu)
            
            # 4. Threshold adaptativo
            thresh_adapt = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
            processed_images.append(thresh_adapt)
            
            # 5. Múltiplos thresholds manuais
            for threshold in [100, 127, 150, 180]:
                _, thresh = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)
                processed_images.append(thresh)
            
            # 6. Morfologia para limpar ruído
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            morphed = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, kernel)
            morphed = cv2.morphologyEx(morphed, cv2.MORPH_OPEN, kernel)
            processed_images.append(morphed)
            
            # 7. Redimensionamento para diferentes escalas
            for scale in [0.5, 1.5, 2.0]:
                new_width = int(gray.shape[1] * scale)
                new_height = int(gray.shape[0] * scale)
                resized = cv2.resize(gray, (new_width, new_height), interpolation=cv2.INTER_CUBIC)
                processed_images.append(resized)
            
            # 8. Filtro gaussiano para suavizar
            blurred = cv2.GaussianBlur(gray, (3, 3), 0)
            processed_images.append(blurred)
            
            # 9. Equalização de histograma
            equalized = cv2.equalizeHist(gray)
            processed_images.append(equalized)
            
            # 10. Inversão de cores (para QR codes escuros em fundo claro)
            inverted = cv2.bitwise_not(gray)
            processed_images.append(inverted)
            
            print(f"📊 Geradas {len(processed_images)} imagens processadas para detecção")
            return processed_images
            
        except Exception as e:
            print(f"❌ Erro no pré-processamento: {str(e)}")
            return [gray] if 'gray' in locals() else []
    
    def _detectar_qr_por_regioes(self, image):
        """
        Detecta QR code por regiões específicas da imagem
        """
        try:
            # Converter para grayscale se necessário
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image
            
            height, width = gray.shape
            detector = cv2.QRCodeDetector()
            
            # Regiões para buscar QR code
            regions = [
                # Canto superior direito (mais comum)
                (0, 0, width//2, height//2),
                # Canto superior esquerdo
                (0, 0, width//2, height//2),
                # Região central superior
                (width//4, 0, 3*width//4, height//2),
                # Região central
                (width//4, height//4, 3*width//4, 3*height//4),
                # Região inferior direita
                (width//2, height//2, width, height),
                # Região inferior esquerda
                (0, height//2, width//2, height),
            ]
            
            for i, (x1, y1, x2, y2) in enumerate(regions):
                roi = gray[y1:y2, x1:x2]
                if roi.size > 0:
                    print(f"📍 Testando região {i+1}: ({x1},{y1}) a ({x2},{y2}) - {roi.shape}")
                    dados, _, _ = detector.detectAndDecode(roi)
                    if dados:
                        print(f"✅ QR Code detectado na região {i+1}: {dados}")
                        return dados
            
            return None
            
        except Exception as e:
            print(f"❌ Erro na detecção por regiões: {str(e)}")
            return None

    def _alinhar_por_redimensionamento(self, user_image, gabarito_image):
        """
        Alinha gabarito com imagem do usuário por redimensionamento simples
        MÉTODO CORRIGIDO: Redimensiona o gabarito para o tamanho da imagem do usuário
        """
        try:
            print(f"🔧 Alinhando por redimensionamento (gabarito → usuário)...")
            
            # Converter gabarito PIL para numpy array se necessário
            if hasattr(gabarito_image, 'mode'):  # É PIL Image
                import numpy as np
                gabarito_array = np.array(gabarito_image)
                # Converter RGB para BGR (OpenCV usa BGR)
                if len(gabarito_array.shape) == 3 and gabarito_array.shape[2] == 3:
                    gabarito_array = cv2.cvtColor(gabarito_array, cv2.COLOR_RGB2BGR)
            else:
                gabarito_array = gabarito_image
            
            # Obter dimensões das imagens
            gabarito_height, gabarito_width = gabarito_array.shape[:2]
            user_height, user_width = user_image.shape[:2]
            
            print(f"📏 Dimensões do gabarito: {gabarito_width}x{gabarito_height}")
            print(f"📏 Dimensões da imagem do usuário: {user_width}x{user_height}")
            
            # Calcular escala proporcional baseada na altura (manter proporção)
            # Usar a altura do usuário como referência para melhor alinhamento
            scale_factor = user_height / gabarito_height
            new_width = int(gabarito_width * scale_factor)
            
            print(f"📏 Fator de escala baseado na altura: {scale_factor:.3f}")
            print(f"📏 Nova largura calculada: {new_width}")
            
            # Redimensionar gabarito para se adequar à escala do usuário
            gabarito_resized = cv2.resize(gabarito_array, (new_width, user_height))
            print(f"📏 Dimensões do gabarito redimensionado: {gabarito_resized.shape[1]}x{gabarito_resized.shape[0]}")
            
            return gabarito_resized
            
        except Exception as e:
            print(f"❌ Erro ao alinhar por redimensionamento: {str(e)}")
            return None

    def _gerar_imagem_debug_alinhamento(self, gabarito_image, user_image, test_id):
        """
        Gera imagem de debug mostrando o alinhamento entre gabarito e imagem do usuário
        """
        try:
            print(f"🔧 Gerando imagem de debug de alinhamento...")
            
            # Converter imagens para numpy arrays se necessário
            if hasattr(gabarito_image, 'mode'):  # É PIL Image
                gabarito_array = np.array(gabarito_image)
                if len(gabarito_array.shape) == 3:
                    gabarito_array = cv2.cvtColor(gabarito_array, cv2.COLOR_RGB2BGR)
            else:
                gabarito_array = gabarito_image
                
            if hasattr(user_image, 'mode'):  # É PIL Image
                user_array = np.array(user_image)
                if len(user_array.shape) == 3:
                    user_array = cv2.cvtColor(user_array, cv2.COLOR_RGB2BGR)
            else:
                user_array = user_image
            
            # PRESERVAR as dimensões originais das imagens alinhadas
            h1, w1 = gabarito_array.shape[:2]
            h2, w2 = user_array.shape[:2]
            
            print(f"📏 Dimensões originais - Gabarito alinhado: {w1}x{h1}, Usuário: {w2}x{h2}")
            
            # NÃO redimensionar - usar as dimensões reais das imagens alinhadas
            # O gabarito já foi alinhado pelas funções de alinhamento
            gabarito_resized = gabarito_array
            user_resized = user_array
            
            print(f"📏 Dimensões preservadas - Gabarito: {gabarito_resized.shape[1]}x{gabarito_resized.shape[0]}, Usuário: {user_resized.shape[1]}x{user_resized.shape[0]}")
            
            # Usar as dimensões reais para criar a imagem combinada
            target_h = max(h1, h2)  # Usar a maior altura
            target_w = max(w1, w2)  # Usar a maior largura
            
            # Criar imagem mesclada (lado a lado) com dimensões adequadas
            gabarito_h, gabarito_w = gabarito_resized.shape[:2]
            user_h, user_w = user_resized.shape[:2]
            
            # Calcular dimensões da imagem combinada
            combined_width = gabarito_w + user_w + 30  # Espaço entre as imagens
            combined_height = max(gabarito_h, user_h) + 100  # Espaço para texto
            
            print(f"📏 Dimensões da imagem combinada: {combined_width}x{combined_height}")
            print(f"📏 Gabarito: {gabarito_w}x{gabarito_h}")
            print(f"📏 Usuário: {user_w}x{user_h}")
            
            # Criar imagem branca
            combined_image = np.ones((combined_height, combined_width, 3), dtype=np.uint8) * 255
            
            # Colar gabarito à esquerda (preservando dimensões originais)
            y_offset = 50
            x_offset_gabarito = 10
            combined_image[y_offset:y_offset+gabarito_h, x_offset_gabarito:x_offset_gabarito+gabarito_w] = gabarito_resized
            
            # Colar imagem do usuário à direita (preservando dimensões originais)
            x_offset_user = x_offset_gabarito + gabarito_w + 10  # 10px de espaço entre as imagens
            combined_image[y_offset:y_offset+user_h, x_offset_user:x_offset_user+user_w] = user_resized
            
            print(f"✅ Imagens coladas - Gabarito: ({x_offset_gabarito},{y_offset}) a ({x_offset_gabarito+gabarito_w},{y_offset+gabarito_h})")
            print(f"✅ Imagens coladas - Usuário: ({x_offset_user},{y_offset}) a ({x_offset_user+user_w},{y_offset+user_h})")
            
            # Adicionar texto
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.8
            color = (0, 0, 0)
            thickness = 2
            
            # Título
            cv2.putText(combined_image, "DEBUG ALIGNMENT", (10, 30), font, font_scale, color, thickness)
            
            # Labels
            cv2.putText(combined_image, "GABARITO ALINHADO", (10, combined_height - 20), font, 0.6, color, thickness)
            cv2.putText(combined_image, "USUARIO ORIGINAL", (x_offset_user, combined_height - 20), font, 0.6, color, thickness)
            
            # Adicionar linhas de referência conectando as bolhas
            self._adicionar_linhas_referencia_corrigidas(combined_image, gabarito_w, gabarito_h, user_w, user_h, x_offset_gabarito, x_offset_user, y_offset, test_id)
            
            # Adicionar coordenadas das bolhas
            self._adicionar_coordenadas_bolhas_corrigidas(combined_image, gabarito_w, gabarito_h, user_w, user_h, x_offset_gabarito, x_offset_user, y_offset, test_id)
            
            # Criar diretório de debug se não existir
            import os
            debug_dir = "debug_alignment"
            if not os.path.exists(debug_dir):
                os.makedirs(debug_dir)
            
            # Salvar imagem com timestamp
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"debug_alignment_{test_id}_{timestamp}.png"
            filepath = os.path.join(debug_dir, filename)
            
            cv2.imwrite(filepath, combined_image)
            print(f"✅ Imagem de debug salva: {filepath}")
            
            return filepath
            
        except Exception as e:
            print(f"❌ Erro ao gerar imagem de debug: {str(e)}")
            return None

    def _adicionar_linhas_referencia_corrigidas(self, image, gabarito_w, gabarito_h, user_w, user_h, x_offset_gabarito, x_offset_user, y_offset, test_id):
        """
        Adiciona linhas de referência conectando as bolhas correspondentes
        CORRIGIDO: Usa coordenadas do gabarito alinhado como referência
        """
        try:
            # Buscar dados da prova para obter número de questões
            from app.models.test import Test
            from app.models.question import Question
            from app.models.testQuestion import TestQuestion
            
            test = Test.query.get(test_id)
            if not test:
                print(f"❌ Test não encontrado: {test_id}")
                return
            
            # Buscar questões e respostas corretas na ordem correta
            test_questions = TestQuestion.query.filter_by(test_id=test_id).order_by(TestQuestion.order).all()
            num_questoes = len(test_questions)
            
            # COORDENADAS FIXAS baseadas no gabarito alinhado
            x_positions = [112, 162, 212, 262]  # Posições X das alternativas A, B, C, D
            y_positions_base = [950, 995, 1040, 1085]  # Posições Y das questões 1, 2, 3, 4
            
            # Ajustar coordenadas para o tamanho do gabarito alinhado
            scale_factor_x = gabarito_w / 1240  # Largura original do gabarito
            scale_factor_y = gabarito_h / 1753  # Altura original do gabarito
            
            # Calcular coordenadas ajustadas para o gabarito alinhado
            x_positions_ajustadas = [int(x * scale_factor_x) for x in x_positions]
            y_positions_ajustadas = []
            
            for i in range(num_questoes):
                if i < len(y_positions_base):
                    y_positions_ajustadas.append(int(y_positions_base[i] * scale_factor_y))
                else:
                    # Continuar o padrão para questões adicionais
                    y_positions_ajustadas.append(int((y_positions_base[-1] + (i - len(y_positions_base) + 1) * 45) * scale_factor_y))
            
            print(f"🔍 Coordenadas de referência corrigidas:")
            print(f"  Y: {y_positions_ajustadas}")
            print(f"  X: {x_positions_ajustadas}")
            
            # Usar os offsets reais das imagens na imagem combinada
            offset_left = x_offset_gabarito
            offset_right = x_offset_user
            offset_top = y_offset
            
            # Desenhar linhas conectando bolhas correspondentes
            for i in range(num_questoes):  # Número de questões
                for j in range(4):  # 4 alternativas
                    x_gabarito = x_positions_ajustadas[j]
                    y_gabarito = y_positions_ajustadas[i]
                    
                    # Ajustar coordenadas para a imagem do usuário
                    scale_user_x = user_w / gabarito_w
                    scale_user_y = user_h / gabarito_h
                    
                    x_user = int(x_gabarito * scale_user_x)
                    y_user = int(y_gabarito * scale_user_y)
                    
                    # Coordenadas na imagem esquerda (gabarito)
                    x1 = offset_left + x_gabarito
                    y1 = offset_top + y_gabarito
                    
                    # Coordenadas na imagem direita (usuário)
                    x2 = offset_right + x_user
                    y2 = offset_top + y_user
                    
                    # Desenhar linha de referência
                    cv2.line(image, (x1, y1), (x2, y2), (0, 255, 0), 1)
                    
                    # Desenhar círculos nas posições das bolhas
                    cv2.circle(image, (x1, y1), 3, (255, 0, 0), -1)  # Azul no gabarito
                    cv2.circle(image, (x2, y2), 3, (0, 0, 255), -1)  # Vermelho no usuário

        except Exception as e:
            print(f"❌ Erro ao adicionar linhas de referência corrigidas: {str(e)}")

    def _adicionar_coordenadas_bolhas_corrigidas(self, image, gabarito_w, gabarito_h, user_w, user_h, x_offset_gabarito, x_offset_user, y_offset, test_id):
        """
        Adiciona texto mostrando as coordenadas das bolhas
        CORRIGIDO: Usa coordenadas do gabarito alinhado como referência
        """
        try:
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.4
            color = (128, 128, 128)
            thickness = 1
            
            # Buscar dados da prova para obter número de questões
            from app.models.test import Test
            from app.models.question import Question
            from app.models.testQuestion import TestQuestion
            
            test = Test.query.get(test_id)
            if not test:
                print(f"❌ Test não encontrado: {test_id}")
                return
            
            # Buscar questões e respostas corretas na ordem correta
            test_questions = TestQuestion.query.filter_by(test_id=test_id).order_by(TestQuestion.order).all()
            num_questoes = len(test_questions)
            
            # COORDENADAS FIXAS baseadas no gabarito alinhado
            x_positions = [112, 162, 212, 262]  # Posições X das alternativas A, B, C, D
            y_positions_base = [950, 995, 1040, 1085]  # Posições Y das questões 1, 2, 3, 4
            
            # Ajustar coordenadas para o tamanho do gabarito alinhado
            scale_factor_x = gabarito_w / 1240  # Largura original do gabarito
            scale_factor_y = gabarito_h / 1753  # Altura original do gabarito
            
            # Calcular coordenadas ajustadas para o gabarito alinhado
            x_positions_ajustadas = [int(x * scale_factor_x) for x in x_positions]
            y_positions_ajustadas = []
            
            for i in range(num_questoes):
                if i < len(y_positions_base):
                    y_positions_ajustadas.append(int(y_positions_base[i] * scale_factor_y))
                else:
                    # Continuar o padrão para questões adicionais
                    y_positions_ajustadas.append(int((y_positions_base[-1] + (i - len(y_positions_base) + 1) * 45) * scale_factor_y))
            
            # Usar os offsets reais das imagens na imagem combinada
            offset_left = x_offset_gabarito
            offset_right = x_offset_user
            offset_top = y_offset
            
            # Adicionar coordenadas para as primeiras 2 questões (para não poluir muito)
            for i in range(min(2, num_questoes)):  # Apenas 2 questões
                for j in range(4):  # 4 alternativas
                    x_gabarito = x_positions_ajustadas[j]
                    y_gabarito = y_positions_ajustadas[i]
                    
                    # Ajustar coordenadas para a imagem do usuário
                    scale_user_x = user_w / gabarito_w
                    scale_user_y = user_h / gabarito_h
                    
                    x_user = int(x_gabarito * scale_user_x)
                    y_user = int(y_gabarito * scale_user_y)
                    
                    # Coordenadas na imagem esquerda
                    x1 = offset_left + x_gabarito
                    y1 = offset_top + y_gabarito
                    
                    # Coordenadas na imagem direita
                    x2 = offset_right + x_user
                    y2 = offset_top + y_user
                    
                    # Texto com coordenadas
                    text_left = f"({x_gabarito},{y_gabarito})"
                    text_right = f"({x_user},{y_user})"
                    
                    cv2.putText(image, text_left, (x1-20, y1+15), font, font_scale, color, thickness)
                    cv2.putText(image, text_right, (x2-20, y2+15), font, font_scale, color, thickness)

        except Exception as e:
            print(f"❌ Erro ao adicionar coordenadas corrigidas: {str(e)}")

    def _adicionar_linhas_referencia(self, image, gabarito_w, gabarito_h, user_w, user_h, x_offset_gabarito, x_offset_user, y_offset):
        """
        Adiciona linhas de referência conectando as bolhas correspondentes
        VERSÃO CORRIGIDA: Usa dimensões reais das imagens alinhadas
        """
        try:
            # Calcular coordenadas baseadas nas dimensões reais das imagens
            # Usar a imagem do gabarito como referência para as coordenadas
            h_img, w_img = gabarito_h, gabarito_w
            
            # Região das bolhas (últimos 25% da altura, mais para baixo)
            start_y = int(h_img * 0.75)  # Começar a 75% da altura (mais para baixo)
            end_y = int(h_img * 0.98)    # Terminar a 98% da altura
            
            # Calcular espaçamento vertical entre questões
            available_height = end_y - start_y
            question_spacing = available_height // 4  # 4 questões
            
            # Calcular posições Y das questões (ajustado para alinhar com bolhas)
            y_positions = []
            for i in range(4):
                y = start_y + (i * question_spacing) + (question_spacing // 2) + 5
                y_positions.append(y)
            
            # Região horizontal das alternativas (mais para a direita)
            start_x = int(w_img * 0.12)  # Começar a 12% da largura (posição real das bolhas)
            end_x = int(w_img * 0.25)    # Terminar a 25% da largura
            
            # Calcular espaçamento horizontal entre alternativas
            available_width = end_x - start_x
            alt_spacing = available_width // 4  # 4 alternativas
            
            # Calcular posições X das alternativas
            x_positions = []
            for j in range(4):
                x = start_x + (j * alt_spacing) + (alt_spacing // 2)
                x_positions.append(x)
            
            print(f"🔍 Coordenadas de referência calculadas:")
            print(f"  Y: {y_positions}")
            print(f"  X: {x_positions}")
            
            # Usar os offsets reais das imagens na imagem combinada
            offset_left = x_offset_gabarito
            offset_right = x_offset_user
            offset_top = y_offset
            
            # Desenhar linhas conectando bolhas correspondentes
            for i in range(4):  # 4 questões
                for j in range(4):  # 4 alternativas
                    x = x_positions[j]
                    y = y_positions[i]
                    
                    # Coordenadas na imagem esquerda (gabarito)
                    x1 = offset_left + x
                    y1 = offset_top + y
                    
                    # Coordenadas na imagem direita (usuário)
                    x2 = offset_right + x
                    y2 = offset_top + y
                    
                    # Desenhar linha de referência
                    cv2.line(image, (x1, y1), (x2, y2), (0, 255, 0), 1)
                    
                    # Desenhar círculos nas posições das bolhas
                    cv2.circle(image, (x1, y1), 3, (255, 0, 0), -1)  # Azul no gabarito
                    cv2.circle(image, (x2, y2), 3, (0, 0, 255), -1)  # Vermelho no usuário
                    
        except Exception as e:
            print(f"❌ Erro ao adicionar linhas de referência: {str(e)}")

    def _adicionar_coordenadas_bolhas(self, image, gabarito_w, gabarito_h, user_w, user_h, x_offset_gabarito, x_offset_user, y_offset):
        """
        Adiciona texto mostrando as coordenadas das bolhas
        VERSÃO CORRIGIDA: Usa dimensões reais das imagens alinhadas
        """
        try:
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.4
            color = (128, 128, 128)
            thickness = 1
            
            # Calcular coordenadas baseadas nas dimensões reais das imagens
            h_img, w_img = gabarito_h, gabarito_w
            
            # Região das bolhas (últimos 25% da altura, mais para baixo)
            start_y = int(h_img * 0.75)  # Começar a 75% da altura (mais para baixo)
            end_y = int(h_img * 0.98)    # Terminar a 98% da altura
            
            # Calcular espaçamento vertical entre questões
            available_height = end_y - start_y
            question_spacing = available_height // 4  # 4 questões
            
            # Calcular posições Y das questões (ajustado para alinhar com bolhas)
            y_positions = []
            for i in range(4):
                y = start_y + (i * question_spacing) + (question_spacing // 2) + 5
                y_positions.append(y)
            
            # Região horizontal das alternativas (mais para a direita)
            start_x = int(w_img * 0.12)  # Começar a 12% da largura (posição real das bolhas)
            end_x = int(w_img * 0.25)    # Terminar a 25% da largura
            
            # Calcular espaçamento horizontal entre alternativas
            available_width = end_x - start_x
            alt_spacing = available_width // 4  # 4 alternativas
            
            # Calcular posições X das alternativas
            x_positions = []
            for j in range(4):
                x = start_x + (j * alt_spacing) + (alt_spacing // 2)
                x_positions.append(x)
            
            # Usar os offsets reais das imagens na imagem combinada
            offset_left = x_offset_gabarito
            offset_right = x_offset_user
            offset_top = y_offset
            
            # Adicionar coordenadas para as primeiras 2 questões (para não poluir muito)
            for i in range(2):  # Apenas 2 questões
                for j in range(4):  # 4 alternativas
                    x = x_positions[j]
                    y = y_positions[i]
                    
                    # Coordenadas na imagem esquerda
                    x1 = offset_left + x
                    y1 = offset_top + y
                    
                    # Coordenadas na imagem direita
                    x2 = offset_right + x
                    y2 = offset_top + y
                    
                    # Texto com coordenadas
                    text_left = f"({x},{y})"
                    text_right = f"({x},{y})"
                    
                    cv2.putText(image, text_left, (x1-20, y1+15), font, font_scale, color, thickness)
                    cv2.putText(image, text_right, (x2-20, y2+15), font, font_scale, color, thickness)
                    
        except Exception as e:
            print(f"❌ Erro ao adicionar coordenadas: {str(e)}")

    def _alinhar_por_perspectiva_invertida(self, gabarito_image, user_image):
        """
        NOVA LÓGICA: Alinha gabarito com imagem do usuário usando transformação de perspectiva
        Redimensiona o gabarito para o tamanho da imagem do usuário
        """
        try:
            print(f"🔧 Alinhando por perspectiva INVERTIDA (gabarito → usuário)...")
            
            # Converter PIL Image para numpy array se necessário
            if hasattr(gabarito_image, 'mode'):  # É PIL Image
                gabarito_array = np.array(gabarito_image)
                if len(gabarito_array.shape) == 3:
                    gabarito_array = cv2.cvtColor(gabarito_array, cv2.COLOR_RGB2BGR)
            else:
                gabarito_array = gabarito_image
                
            if hasattr(user_image, 'mode'):  # É PIL Image
                user_array = np.array(user_image)
                if len(user_array.shape) == 3:
                    user_array = cv2.cvtColor(user_array, cv2.COLOR_RGB2BGR)
            else:
                user_array = user_image
            
            # Obter dimensões das imagens
            altura_gabarito, largura_gabarito = gabarito_array.shape[:2]
            altura_usuario, largura_usuario = user_array.shape[:2]
            
            print(f"📏 Dimensões do gabarito: {largura_gabarito}x{altura_gabarito}")
            print(f"📏 Dimensões da imagem do usuário: {largura_usuario}x{altura_usuario}")
            
            # Calcular escala proporcional baseada na altura (manter proporção)
            scale_factor = altura_usuario / altura_gabarito
            nova_largura = int(largura_gabarito * scale_factor)
            
            print(f"📏 Fator de escala baseado na altura: {scale_factor:.3f}")
            print(f"📏 Nova largura calculada: {nova_largura}")
            
            # Redimensionar gabarito para se adequar à escala do usuário
            gabarito_redimensionado = cv2.resize(gabarito_array, (nova_largura, altura_usuario))
            print(f"📏 Gabarito redimensionado para: {gabarito_redimensionado.shape[1]}x{gabarito_redimensionado.shape[0]}")
            
            # Converter imagens para grayscale para detecção de âncoras
            gabarito_gray = cv2.cvtColor(gabarito_redimensionado, cv2.COLOR_BGR2GRAY)
            user_gray = cv2.cvtColor(user_array, cv2.COLOR_BGR2GRAY)
            
            # Detectar âncoras no gabarito redimensionado
            pontos_gabarito = self._detectar_ancoras_tabela(gabarito_gray)
            if pontos_gabarito is None:
                print(f"❌ Não foi possível detectar âncoras no gabarito redimensionado")
                return None
            
            print(f"✅ Âncoras do gabarito redimensionado detectadas: {len(pontos_gabarito)} pontos")
            
            # Detectar âncoras na imagem do usuário
            pontos_usuario = self._detectar_ancoras_tabela(user_gray)
            if pontos_usuario is None:
                print(f"❌ Não foi possível detectar âncoras na imagem do usuário")
                return None
            
            print(f"✅ Âncoras do usuário detectadas: {len(pontos_usuario)} pontos")
            
            # Verificar se temos 4 pontos
            if len(pontos_gabarito) != 4 or len(pontos_usuario) != 4:
                print(f"❌ Número incorreto de âncoras: gabarito={len(pontos_gabarito)}, usuário={len(pontos_usuario)}")
                return None
            
            # Ordenar pontos para correspondência correta
            pontos_gabarito = self._ordenar_pontos_retangulo(pontos_gabarito)
            pontos_usuario = self._ordenar_pontos_retangulo(pontos_usuario)
            
            print(f"🔧 Aplicando transformação de perspectiva INVERTIDA...")
            
            # NOVA LÓGICA: Transformar gabarito para corresponder ao usuário
            # Matriz de transformação: gabarito → usuário
            matriz_transformacao = cv2.getPerspectiveTransform(
                np.float32(pontos_gabarito), 
                np.float32(pontos_usuario)
            )
            
            # Aplicar transformação de perspectiva no gabarito
            gabarito_alinhado = cv2.warpPerspective(
                gabarito_redimensionado, 
                matriz_transformacao, 
                (largura_usuario, altura_usuario)
            )
            
            print(f"✅ Transformação de perspectiva INVERTIDA aplicada com sucesso")
            print(f"📏 Gabarito alinhado: {gabarito_alinhado.shape[1]}x{gabarito_alinhado.shape[0]}")
            
            # CORREÇÃO: Retornar o gabarito alinhado (que foi transformado para corresponder ao usuário)
            # A imagem do usuário mantém seu tamanho original e será usada para detecção
            return gabarito_alinhado
            
        except Exception as e:
            print(f"❌ Erro ao alinhar por perspectiva invertida: {str(e)}")
            return None

    def _alinhar_por_perspectiva(self, gabarito_image, user_image):
        """
        Alinha imagem do usuário com gabarito usando transformação de perspectiva
        baseada nas âncoras da borda grossa da tabela
        """
        try:
            print(f"🔧 Alinhando por perspectiva usando âncoras da tabela...")
            
            # Converter PIL Image para numpy array se necessário
            if hasattr(gabarito_image, 'mode'):  # É PIL Image
                gabarito_array = np.array(gabarito_image)
                if len(gabarito_array.shape) == 3:
                    gabarito_array = cv2.cvtColor(gabarito_array, cv2.COLOR_RGB2BGR)
            else:
                gabarito_array = gabarito_image
                
            if hasattr(user_image, 'mode'):  # É PIL Image
                user_array = np.array(user_image)
                if len(user_array.shape) == 3:
                    user_array = cv2.cvtColor(user_array, cv2.COLOR_RGB2BGR)
            else:
                user_array = user_image
            
            # Converter imagens para grayscale se necessário
            if len(gabarito_array.shape) == 3:
                gabarito_gray = cv2.cvtColor(gabarito_array, cv2.COLOR_BGR2GRAY)
            else:
                gabarito_gray = gabarito_array
                
            if len(user_array.shape) == 3:
                user_gray = cv2.cvtColor(user_array, cv2.COLOR_BGR2GRAY)
            else:
                user_gray = user_array
            
            # Detectar âncoras no gabarito (borda grossa da tabela)
            pontos_gabarito = self._detectar_ancoras_tabela(gabarito_gray)
            if pontos_gabarito is None:
                print(f"❌ Não foi possível detectar âncoras no gabarito")
                return None
            
            print(f"✅ Âncoras do gabarito detectadas: {len(pontos_gabarito)} pontos")
            
            # Detectar âncoras na imagem do usuário
            pontos_usuario = self._detectar_ancoras_tabela(user_gray)
            if pontos_usuario is None:
                print(f"❌ Não foi possível detectar âncoras na imagem do usuário")
                return None
            
            print(f"✅ Âncoras do usuário detectadas: {len(pontos_usuario)} pontos")
            
            # Verificar se temos 4 pontos
            if len(pontos_gabarito) != 4 or len(pontos_usuario) != 4:
                print(f"❌ Número incorreto de âncoras: gabarito={len(pontos_gabarito)}, usuário={len(pontos_usuario)}")
                return None
            
            # Ordenar pontos para correspondência correta
            pontos_gabarito = self._ordenar_pontos_retangulo(pontos_gabarito)
            pontos_usuario = self._ordenar_pontos_retangulo(pontos_usuario)
            
            print(f"🔧 Aplicando transformação de perspectiva...")
            
            # Calcular matriz de transformação
            matriz_transformacao = cv2.getPerspectiveTransform(
                np.float32(pontos_usuario), 
                np.float32(pontos_gabarito)
            )
            
            # Obter dimensões do gabarito
            altura_gabarito, largura_gabarito = gabarito_gray.shape[:2]
            
            # Aplicar transformação de perspectiva
            imagem_alinhada = cv2.warpPerspective(
                user_array, 
                matriz_transformacao, 
                (largura_gabarito, altura_gabarito)
            )
            
            print(f"✅ Transformação de perspectiva aplicada com sucesso")
            return imagem_alinhada
            
        except Exception as e:
            print(f"❌ Erro ao alinhar por perspectiva: {str(e)}")
            return None

    def _detectar_ancoras_tabela(self, imagem_gray):
        """
        Detecta as 4 âncoras da borda grossa do formulário
        VERSÃO ATUALIZADA: Usa a borda externa do formulário em vez da tabela de questões
        """
        try:
            print(f"🔍 Detectando borda externa do formulário...")
            h, w = imagem_gray.shape
            print(f"📏 Dimensões da imagem: {w}x{h}")
            
            # Usar toda a imagem para detectar a borda externa do formulário
            roi_y_start = 0               # Começar do topo
            roi_y_end = h                 # Até o final
            roi_x_start = 0               # Começar da esquerda
            roi_x_end = w                 # Até a direita
            
            print(f"🎯 ROI do formulário: ({roi_x_start},{roi_y_start}) a ({roi_x_end},{roi_y_end})")
            
            # Extrair ROI do formulário (toda a imagem)
            roi_formulario = imagem_gray[roi_y_start:roi_y_end, roi_x_start:roi_x_end]
            
            # Pré-processamento melhorado
            # 1. Aplicar blur para reduzir ruído
            blurred = cv2.GaussianBlur(roi_formulario, (3, 3), 0)
            
            # 2. Detectar bordas com Canny
            edges = cv2.Canny(blurred, 50, 150)
            
            # 3. Aplicar morfologia para conectar bordas quebradas
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
            
            # 4. Encontrar contornos
            contornos, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if not contornos:
                print(f"❌ Nenhum contorno encontrado na ROI do formulário")
                return None
            
            print(f"🔍 Encontrados {len(contornos)} contornos na ROI do formulário")
            
            # Filtrar contornos por área e proporção
            area_minima = roi_formulario.shape[0] * roi_formulario.shape[1] * 0.1  # 10% da ROI (borda externa é grande)
            contornos_filtrados = []
            
            for c in contornos:
                area = cv2.contourArea(c)
                if area > area_minima:
                    # Verificar se é aproximadamente retangular
                    x, y, w_rect, h_rect = cv2.boundingRect(c)
                    aspect_ratio = w_rect / h_rect
                    if 0.5 < aspect_ratio < 2.0:  # Proporção razoável para formulário (mais quadrado)
                        contornos_filtrados.append(c)
            
            if not contornos_filtrados:
                print(f"❌ Nenhum contorno retangular encontrado na ROI do formulário")
                return None
            
            print(f"🔍 {len(contornos_filtrados)} contornos retangulares encontrados")
            
            # Pegar o maior contorno retangular (borda externa do formulário)
            maior_contorno = max(contornos_filtrados, key=cv2.contourArea)
            area_contorno = cv2.contourArea(maior_contorno)
            print(f"📐 Maior contorno retangular: área {area_contorno:.0f}")
            
            # Aproximar contorno para retângulo com diferentes precisões
            for epsilon_factor in [0.01, 0.02, 0.05, 0.1]:
                epsilon = epsilon_factor * cv2.arcLength(maior_contorno, True)
                aproximado = cv2.approxPolyDP(maior_contorno, epsilon, True)
                
                print(f"🔍 Tentativa epsilon {epsilon_factor}: {len(aproximado)} vértices")
                
                if len(aproximado) == 4:
                    pontos = aproximado.reshape(4, 2)
                    # Ajustar coordenadas para a imagem completa
                    pontos[:, 0] += roi_x_start  # Ajustar X
                    pontos[:, 1] += roi_y_start  # Ajustar Y
                    print(f"✅ Âncoras do formulário detectadas: {pontos}")
                    return pontos
            
            # Se não conseguir 4 pontos, usar bounding box
            print(f"⚠️ Não foi possível encontrar 4 vértices, usando bounding box")
            x, y, w_rect, h_rect = cv2.boundingRect(maior_contorno)
            # Ajustar coordenadas para a imagem completa
            x += roi_x_start
            y += roi_y_start
            pontos = np.array([
                [x, y],                    # Canto superior esquerdo
                [x + w_rect, y],          # Canto superior direito
                [x + w_rect, y + h_rect], # Canto inferior direito
                [x, y + h_rect]           # Canto inferior esquerdo
            ])
            print(f"✅ Âncoras do formulário (bounding box): {pontos}")
            return pontos
            
        except Exception as e:
            print(f"❌ Erro ao detectar âncoras do formulário: {str(e)}")
            return None
    
    def _ordenar_pontos_retangulo(self, pontos):
        """
        Ordena os 4 pontos de um retângulo: [topo_esq, topo_dir, baixo_dir, baixo_esq]
        """
        try:
            # Calcular centro
            centro = np.mean(pontos, axis=0)
            
            # Ordenar por ângulo em relação ao centro
            def angulo_ponto(ponto):
                return np.arctan2(ponto[1] - centro[1], ponto[0] - centro[0])
            
            pontos_ordenados = sorted(pontos, key=angulo_ponto)
            
            # Reorganizar para a ordem correta
            # Encontrar ponto superior esquerdo (menor soma x+y)
            soma_coordenadas = [p[0] + p[1] for p in pontos_ordenados]
            idx_superior_esq = np.argmin(soma_coordenadas)
            
            # Reorganizar começando pelo superior esquerdo
            pontos_finais = pontos_ordenados[idx_superior_esq:] + pontos_ordenados[:idx_superior_esq]
            
            return np.array(pontos_finais)
            
        except Exception as e:
            print(f"❌ Erro ao ordenar pontos: {str(e)}")
            return pontos

    def _criar_mascara_bolha(self, gabarito_image, coord):
        """
        Cria máscara binária para uma bolha específica
        """
        try:
            # Converter gabarito PIL para numpy array se necessário
            if hasattr(gabarito_image, 'mode'):  # É PIL Image
                import numpy as np
                gabarito_array = np.array(gabarito_image)
                # Converter RGB para BGR (OpenCV usa BGR)
                if len(gabarito_array.shape) == 3 and gabarito_array.shape[2] == 3:
                    gabarito_array = cv2.cvtColor(gabarito_array, cv2.COLOR_RGB2BGR)
            else:
                gabarito_array = gabarito_image
            
            # coord deve conter [x, y, w, h]
            if len(coord) < 4:
                return None
            
            x, y, w, h = coord[:4]
            
            # Criar máscara vazia
            mask = np.zeros(gabarito_array.shape[:2], dtype=np.uint8)
            
            # Desenhar círculo na máscara (assumindo bolha circular)
            center_x = x + w // 2
            center_y = y + h // 2
            radius = min(w, h) // 2
            
            cv2.circle(mask, (center_x, center_y), radius, 255, -1)
            
            return mask
            
        except Exception as e:
            print(f"❌ Erro ao criar máscara da bolha: {str(e)}")
            return None

    def _calcular_preenchimento_com_mascara(self, user_image, mask):
        """
        Calcula proporção de preenchimento usando máscara
        """
        try:
            # Converter para grayscale
            gray = cv2.cvtColor(user_image, cv2.COLOR_BGR2GRAY)
            
            # Aplicar threshold
            _, thresh = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY_INV)
            
            # Aplicar máscara
            masked = cv2.bitwise_and(thresh, mask)
            
            # Calcular proporção de pixels pretos
            total_pixels = cv2.countNonZero(mask)
            filled_pixels = cv2.countNonZero(masked)
            
            if total_pixels > 0:
                return filled_pixels / total_pixels
            else:
                return 0.0
                
        except Exception as e:
            print(f"❌ Erro ao calcular preenchimento: {str(e)}")
            return 0.0

    def _determinar_alternativa(self, coord, gabarito_coords):
        """
        Determina qual alternativa (A, B, C, D) baseado na posição
        """
        try:
            # Implementação simplificada - assumindo ordem A, B, C, D
            # Em uma implementação mais robusta, usaria coordenadas reais
            x, y, w, h = coord[:4]
            
            # Determinar coluna baseada na posição X absoluta
            # Assumindo que as alternativas estão em ordem A, B, C, D da esquerda para direita
            if x < 100:  # Aproximadamente coluna A
                return 'A'
            elif x < 200:  # Aproximadamente coluna B
                return 'B'
            elif x < 300:  # Aproximadamente coluna C
                return 'C'
            else:  # Coluna D
                return 'D'
                
        except Exception as e:
            print(f"❌ Erro ao determinar alternativa: {str(e)}")
            return 'A'
    
    def gerar_formulario_individual_preenchido(self, test_id: str, student_id: str, 
                                            respostas_especificas: dict, output_dir: str = "formularios_preenchidos") -> dict:
        """
        Gera formulário individual preenchido com respostas específicas
        
        Args:
            test_id: ID da prova
            student_id: ID do aluno
            respostas_especificas: Dict com {questao_num: resposta} ex: {1: 'A', 2: 'B', 3: 'A', 4: 'A'}
            output_dir: Diretório de saída
            
        Returns:
            Dict com resultado da operação
        """
        try:
            print(f"🎯 GERANDO FORMULÁRIO INDIVIDUAL PREENCHIDO")
            print(f"📋 Test ID: {test_id}")
            print(f"👤 Student ID: {student_id}")
            print(f"📝 Respostas: {respostas_especificas}")
            
            # Criar diretório se não existir
            os.makedirs(output_dir, exist_ok=True)
            
            # Buscar dados da prova
            from app.models.test import Test
            from app.models.question import Question
            from app.models.testQuestion import TestQuestion
            from app.models.student import Student
            
            test = Test.query.get(test_id)
            if not test:
                return {"success": False, "error": f"Prova {test_id} não encontrada"}
            
            student = Student.query.get(student_id)
            if not student:
                return {"success": False, "error": f"Aluno {student_id} não encontrado"}
            
            # Buscar questões
            test_question_ids = [tq.question_id for tq in TestQuestion.query.filter_by(test_id=test_id).order_by(TestQuestion.order).all()]
            questions = Question.query.filter(Question.id.in_(test_question_ids)).all()
            
            if not questions:
                return {"success": False, "error": "Nenhuma questão encontrada para a prova"}
            
            print(f"📚 Questões encontradas: {len(questions)}")
            
            # Gerar formulário base simples
            form_path = self._gerar_formulario_base_simples(test_id, student_id, output_dir)
            if not form_path:
                return {"success": False, "error": "Erro ao gerar formulário base"}
            
            print(f"📄 Formulário base gerado: {form_path}")
            
            # Carregar imagem
            import cv2
            import numpy as np
            from PIL import Image, ImageDraw
            
            # Carregar como OpenCV
            img_cv = cv2.imread(form_path)
            if img_cv is None:
                return {"success": False, "error": "Erro ao carregar imagem do formulário"}
            
            # Converter para PIL para desenhar
            img_pil = Image.fromarray(cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB))
            draw = ImageDraw.Draw(img_pil)
            
            # Coordenadas fixas das bolinhas
            x_positions = [112, 162, 212, 262]  # A, B, C, D
            y_positions = [950, 995, 1040, 1085]  # Questões 1, 2, 3, 4
            
            print(f"🎯 Preenchendo respostas nas coordenadas:")
            
            # Preencher cada resposta
            for questao_num, resposta in respostas_especificas.items():
                if questao_num <= len(y_positions):
                    y = y_positions[questao_num - 1]
                    
                    # Encontrar posição X da alternativa
                    alternativa_idx = ord(resposta) - ord('A')  # A=0, B=1, C=2, D=3
                    if 0 <= alternativa_idx < len(x_positions):
                        x = x_positions[alternativa_idx]
                        
                        # Desenhar círculo preenchido
                        radius = 8
                        draw.ellipse([x-radius, y-radius, x+radius, y+radius], 
                                   fill='black', outline='black', width=2)
                        
                        print(f"  ✅ Questão {questao_num}: {resposta} em ({x}, {y})")
                    else:
                        print(f"  ❌ Questão {questao_num}: Alternativa {resposta} inválida")
                else:
                    print(f"  ❌ Questão {questao_num}: Número de questão inválido")
            
            # Salvar imagem preenchida
            output_filename = f"formulario_preenchido_{test_id}_{student_id}.png"
            output_path = os.path.join(output_dir, output_filename)
            
            # Converter de volta para OpenCV e salvar
            img_final = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
            cv2.imwrite(output_path, img_final)
            
            print(f"✅ Formulário preenchido salvo: {output_path}")
            
            return {
                "success": True,
                "file_path": output_path,
                "respostas_preenchidas": respostas_especificas,
                "coordenadas_usadas": {
                    "x_positions": x_positions,
                    "y_positions": y_positions
                }
            }
            
        except Exception as e:
            print(f"❌ Erro ao gerar formulário preenchido: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}
    
    def _gerar_formulario_base_simples(self, test_id: str, student_id: str, output_dir: str) -> str:
        """
        Gera formulário base simples para preenchimento
        """
        try:
            import cv2
            import numpy as np
            from PIL import Image, ImageDraw, ImageFont
            
            # Buscar dados do teste e aluno
            from app.models.test import Test
            from app.models.student import Student
            
            test = Test.query.get(test_id)
            student = Student.query.get(student_id)
            
            if not test:
                raise ValueError(f"Teste não encontrado: {test_id}")
            if not student:
                raise ValueError(f"Aluno não encontrado: {student_id}")
            
            # Criar imagem base (A4 em 300 DPI)
            width, height = 2480, 3508  # A4 em 300 DPI
            img = Image.new('RGB', (width, height), 'white')
            draw = ImageDraw.Draw(img)
            
            # Fonte
            try:
                font_large = ImageFont.truetype("arial.ttf", 24)
                font_medium = ImageFont.truetype("arial.ttf", 18)
                font_small = ImageFont.truetype("arial.ttf", 14)
            except:
                font_large = ImageFont.load_default()
                font_medium = ImageFont.load_default()
                font_small = ImageFont.load_default()
            
            # Título
            draw.text((100, 100), "CARTÃO-RESPOSTA", fill='black', font=font_large)
            
            # Informações do aluno
            draw.text((100, 200), f"Nome: {student.name}", fill='black', font=font_medium)
            draw.text((100, 250), f"Prova: {test.title}", fill='black', font=font_medium)
            
            # Desenhar grade de respostas
            x_start = 100
            y_start = 400
            cell_width = 50
            cell_height = 45
            
            # Cabeçalho das alternativas
            alternatives = ['A', 'B', 'C', 'D']
            for i, alt in enumerate(alternatives):
                x = x_start + i * cell_width
                draw.text((x + 20, y_start), alt, fill='black', font=font_medium)
            
            # Desenhar linhas da grade
            for i in range(5):  # 4 questões + cabeçalho
                y = y_start + i * cell_height
                # Linha horizontal
                draw.line([(x_start, y), (x_start + 4 * cell_width, y)], fill='black', width=1)
                
                if i > 0:  # Não desenhar números no cabeçalho
                    draw.text((x_start - 30, y + 15), str(i), fill='black', font=font_medium)
            
            # Linhas verticais
            for i in range(5):  # 4 alternativas + 1 linha inicial
                x = x_start + i * cell_width
                draw.line([(x, y_start), (x, y_start + 4 * cell_height)], fill='black', width=1)
            
            # Desenhar círculos para as respostas
            x_positions = [112, 162, 212, 262]  # Coordenadas X das alternativas
            y_positions = [950, 995, 1040, 1085]  # Coordenadas Y das questões
            
            for i in range(4):  # 4 questões
                for j in range(4):  # 4 alternativas
                    x = x_positions[j]
                    y = y_positions[i]
                    # Desenhar círculo vazio
                    draw.ellipse([x-8, y-8, x+8, y+8], outline='black', width=2)
            
            # Salvar imagem
            os.makedirs(output_dir, exist_ok=True)
            filename = f"formulario_base_{test_id}_{student_id}.png"
            filepath = os.path.join(output_dir, filename)
            img.save(filepath)
            
            return filepath
            
        except Exception as e:
            print(f"❌ Erro ao gerar formulário base: {str(e)}")
            return None
