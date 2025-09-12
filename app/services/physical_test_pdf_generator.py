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
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image as RLImage
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

    # FUNÇÃO NÃO UTILIZADA - comentada para teste
    # def generate_test_pdf(self, test_data: Dict, students_data: List[Dict], 
    #                      questions_data: List[Dict], output_dir: str) -> List[Dict]:
        # """
        # Gera PDFs de provas físicas para todos os alunos
        # 
        # Args:
        #     test_data: Dados da prova (test_id, title, description, etc.)
        #     students_data: Lista de alunos com dados (id, nome, email, etc.)
        #     questions_data: Lista de questões ordenadas
        #     output_dir: Diretório para salvar os PDFs
        #     
        # Returns:
        #     Lista com informações dos PDFs gerados
        # """
        # # Criar diretório absoluto
        # abs_output_dir = os.path.abspath(output_dir)
        # os.makedirs(abs_output_dir, exist_ok=True)
        # generated_files = []
        # 
        # # Gerar gabarito único para o professor
        # answer_key_path = self._generate_answer_key_pdf(test_data, questions_data, abs_output_dir)
        # 
        # for student in students_data:
        #     try:
        #         # Gerar PDF individual para cada aluno (SEM gabarito)
        #         pdf_path = self._generate_individual_test_pdf(
        #             test_data, student, questions_data, abs_output_dir
        #         )
        #         
        #         if pdf_path:
        #             generated_files.append({
        #                 'student_id': student['id'],
        #                 'student_name': student['nome'],
        #                 'pdf_path': pdf_path,
        #                 'answer_key_path': answer_key_path,  # Caminho do gabarito
        #                 'qr_code_data': f"{test_data['id']}_{student['id']}"
        #             })
        #                     
        #     except Exception as e:
        #         logging.error(f"Erro ao gerar PDF para aluno {student['id']}: {str(e)}")
        #         continue
        # 
        # return generated_files
        pass  # Função comentada - não utilizada

    # FUNÇÃO NÃO UTILIZADA - comentada para teste
    # def generate_combined_test_pdf(self, test_data: Dict, students_data: List[Dict], 
    #                               questions_data: List[Dict], output_dir: str) -> Optional[str]:
        # """
        # Gera 1 PDF único contendo todas as provas e gabaritos
        # 
        # Args:
        #     test_data: Dados da prova (test_id, title, description, etc.)
        #     students_data: Lista de alunos com dados (id, nome, email, etc.)
        #     questions_data: Lista de questões ordenadas
        #     output_dir: Diretório para salvar o PDF
        #     
        # Returns:
        #     Caminho do PDF gerado ou None se houver erro
        # """
        # try:
        #     # Criar diretório absoluto
        #     abs_output_dir = os.path.abspath(output_dir)
        #     os.makedirs(abs_output_dir, exist_ok=True)
        #     
        #     # Nome do arquivo combinado usando o nome da prova
        #     test_title = test_data.get('title', 'Prova').replace(' ', '_').replace('/', '_')
        #     filename = f"{test_title}_{test_data['id']}.pdf"
        #     pdf_path = os.path.join(abs_output_dir, filename)
        #     
        #     # Criar documento PDF
        #     doc = SimpleDocTemplate(pdf_path, pagesize=portrait(A4))
        #     story = []
        #     
        #     # Adicionar cada aluno
        #     for i, student in enumerate(students_data):
        #         # Cabeçalho da prova para este aluno
        #         story.extend(self._create_test_header(test_data, student))
        #         
        #         # Questões da prova
        #         story.extend(self._create_questions_section(questions_data))
        #         
        #         # Gabarito para este aluno (usando o mesmo método do gabarito separado)
        #         story.extend(self._create_answer_key(test_data, questions_data, student))
        #         
        #         # Quebra de página entre alunos (exceto no último)
        #         if i < len(students_data) - 1:
        #             story.append(PageBreak())
        #     
        #     # Construir PDF
        #     doc.build(story)
        #     
        #     return pdf_path
        #     
        # except Exception as e:
        #     logging.error(f"Erro ao gerar PDF combinado: {str(e)}")
        #     return None
        pass  # Função comentada - não utilizada

    # FUNÇÃO NÃO UTILIZADA - comentada para teste
    # def _generate_individual_test_pdf(self, test_data: Dict, student: Dict, 
    #                                 questions_data: List[Dict], output_dir: str) -> Optional[str]:
        # """
        # Gera PDF individual para um aluno específico
        # """
        # try:
        #     # Nome do arquivo
        #     safe_name = "".join(c for c in student['nome'] if c.isalnum() or c in (' ', '_')).rstrip().replace(" ", "_")
        #     filename = f"prova_{test_data['id']}_{student['id']}_{safe_name}.pdf"
        #     pdf_path = os.path.join(output_dir, filename)
        #     
        #     # Criar documento PDF
        #     doc = SimpleDocTemplate(pdf_path, pagesize=portrait(A4))
        #     story = []
        #     
        #     # Adicionar cabeçalho da prova
        #     story.extend(self._create_test_header(test_data, student))
        #     
        #     # Adicionar questões
        #     story.extend(self._create_questions_section(questions_data))
        #     
        #     # Adicionar formulário de resposta
        #     story.extend(self._create_answer_sheet(test_data, student, len(questions_data)))
        #     
        #     # NÃO adicionar gabarito no PDF do aluno!
        #     
        #     # Construir PDF
        #     doc.build(story)
        #     
        #     return pdf_path
        #     
        # except Exception as e:
        #     logging.error(f"Erro ao gerar PDF individual: {str(e)}")
        #     return None
        pass  # Função comentada - não utilizada

    # FUNÇÃO NÃO UTILIZADA - comentada para teste
    # def _create_test_header(self, test_data: Dict, student: Dict) -> List:
        # """Cria cabeçalho da prova com dados do aluno"""
        # from reportlab.platypus import Table, TableStyle
        # from reportlab.lib import colors
        # 
        # story = []
        # 
        # # Título da prova
        # story.append(Paragraph(f"{test_data.get('title', 'Prova')}", self.styles['TestTitle']))
        # 
        # # Dados do aluno em formato moderno
        # current_date = datetime.now().strftime("%d/%m/%Y")
        # 
        # # Criar tabela para layout moderno
        # header_data = [
        #     ['Aluno:', student['nome']],
        #     ['Data:', current_date],
        #     ['Prova:', test_data.get('description', '')]
        # ]
        # 
        # header_table = Table(header_data, colWidths=[80, 400])
        # header_table.setStyle(TableStyle([
        #     ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        #     ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        #     ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        #     ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        #     ('FONTSIZE', (0, 0), (-1, -1), 14),
        #     ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#374151')),
        #     ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        #     ('TOPPADDING', (0, 0), (-1, -1), 8),
        # ]))
        # 
        # story.append(header_table)
        # story.append(Spacer(1, 15))
        # 
        # return story
        pass  # Função comentada - não utilizada

    # FUNÇÃO NÃO UTILIZADA - comentada para teste
    # def _create_questions_section(self, questions_data: List[Dict]) -> List:
        # """Cria seção com todas as questões"""
        # story = []
        # 
        # # Adicionar cada questão
        # for i, question in enumerate(questions_data, 1):
        #     story.extend(self._create_single_question(question, i))
        #     story.append(Spacer(1, 35))  # Aumentado de 25 para 35
        # 
        # return story
        pass  # Função comentada - não utilizada

    # FUNÇÃO NÃO UTILIZADA - comentada para teste
    # def _create_single_question(self, question: Dict, question_number: int) -> List:
        # """Cria uma questão individual com layout moderno"""
        # from reportlab.platypus import Table, TableStyle, KeepTogether
        # from reportlab.lib import colors
        pass  # Função comentada - não utilizada (corpo muito grande)
        
        # story = []
        # 
        # # Container da questão com bordas e sombra
        # question_content = []
        # 
        # # Número da questão
        # question_content.append(Paragraph(f"Questão {question_number}", self.styles['QuestionNumber']))
        
        # # Adicionar espaçamento após o número da questão
        # question_content.append(Spacer(1, 8))
        
        # # Tags de informação
        # tags_data = []
        # if question.get('question_type'):
        #     # Traduzir multiple_choice para português
        #     question_type = question['question_type']
        #     if question_type == 'multiple_choice':
        #         question_type = 'Multipla Escolha'
        #     tags_data.append(question_type)
        # if question.get('value'):
        #     tags_data.append(f"{question['value']} pontos")
        # if question.get('difficulty_level'):
        #     tags_data.append(question['difficulty_level'])
        # if question.get('skills'):
        #     tags_data.append(f"{len(question['skills'])} habilidade(s)")
        # 
        # if tags_data:
        #     tags_text = " • ".join(tags_data)
        #     question_content.append(Paragraph(f"<font color='#6b7280'>{tags_text}</font>", self.styles['InfoTag']))
        
        # # Título da questão (se houver)
        # if question.get('title'):
        #     title_text = question['title']
        #     # Verificar se o título tem quebra de linha
        #     if '\n' in title_text or '<br' in title_text:
        #         # Criar estilo com leading aumentado para espaçamento entre linhas
        #         title_style = ParagraphStyle(
        #             'QuestionTitleMultiLine',
        #             parent=self.styles['QuestionTitle'],
        #             leading=24,  # controla o espaçamento entre linhas (fontSize=16 + 8 de espaçamento)
        #             fontSize=16,  # Garantir que o fontSize seja mantido
        #             fontName='Helvetica-Bold'  # Garantir que a fonte seja mantida
        #         )
        #         # Processar quebras de linha mantendo o texto como um único parágrafo
        #         processed_title = re.sub(r'\n|<br\s*/?>', '<br/>', title_text)
        #         title_para = Paragraph(processed_title, title_style)
        #         question_content.append(title_para)
        #     else:
        #         title_para = Paragraph(title_text, self.styles['QuestionTitle'])
        #         question_content.append(title_para)
        # 
        # # Texto da questão (renderizar HTML)
        # question_text = question.get('formatted_text', question.get('text', ''))
        # if question_text:
        #     # Processar HTML mantendo formatação
        #     question_content.extend(self._process_html_content(question_text, self.styles['QuestionText']))
        # 
        # # Segundo enunciado (se houver) - renderizar HTML
        # second_statement = question.get('secondstatement', '')
        # if second_statement:
        #     question_content.extend(self._process_html_content(second_statement, self.styles['SecondStatement']))
        # 
        # # Habilidades avaliadas
        # skill_codes = self._get_skill_codes(question)
        # if skill_codes:
        #     skills_text = " • ".join(skill_codes)
        #     question_content.append(Paragraph(f"<font color='#8b5cf6'>• Habilidades Avaliadas: {skills_text}</font>", self.styles['Skills']))
        
        # # Alternativas
        # alternatives = question.get('alternatives', [])
        # if alternatives:
        #     question_content.append(Paragraph("<font color='#8b5cf6'>• Alternativas:</font>", self.styles['Skills']))
            
        #     # Criar tabela para alternativas
        #     alt_data = []
        #     for alt in alternatives:
        #         letter = alt.get('id', '')  # Usar 'id' em vez de 'letter'
        #         text = alt.get('text', '')
        #         alt_data.append([f"{letter}: ( )", text])
        #     
        #     if alt_data:
        #         alt_table = Table(alt_data, colWidths=[40, 450])  # Aumentado espaçamento
        #         alt_table.setStyle(TableStyle([
        #             ('ALIGN', (0, 0), (0, -1), 'CENTER'),  # Letras centralizadas
        #             ('ALIGN', (1, 0), (1, -1), 'LEFT'),    # Texto alinhado à esquerda
        #             ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        #             ('FONTSIZE', (0, 0), (-1, -1), 12),  # Aumentado de 11 para 12
        #             ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#374151')),
        #             ('BOTTOMPADDING', (0, 0), (-1, -1), 12),  # Aumentado de 8 para 12
        #             ('TOPPADDING', (0, 0), (-1, -1), 12),     # Aumentado de 8 para 12
        #             ('LEFTPADDING', (0, 0), (-1, -1), 15),    # Aumentado de 10 para 15
        #             ('RIGHTPADDING', (0, 0), (-1, -1), 15),   # Aumentado de 10 para 15
        #             ('VALIGN', (0, 0), (-1, -1), 'TOP'),      # Alinhamento vertical no topo
        #         ]))
        #         question_content.append(alt_table)
        # 
        # # Criar container com bordas e estilo moderno como na imagem
        # container_table = Table([[question_content]], colWidths=[500])
        # container_table.setStyle(TableStyle([
        #     ('BORDER', (0, 0), (-1, -1), 1, colors.HexColor('#e5e7eb')),  # Borda cinza
        #     ('LEFTPADDING', (0, 0), (-1, -1), 10),  # Diminuído de 20 para 10
        #     ('RIGHTPADDING', (0, 0), (-1, -1), 10),  # Diminuído de 20 para 10
        #     ('TOPPADDING', (0, 0), (-1, -1), 20),
        #     ('BOTTOMPADDING', (0, 0), (-1, -1), 20),
        #     ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        # ]))
        # 
        # story.append(container_table)
        # story.append(Spacer(1, 20))  # Espaçamento entre questões
        # 
        # return story

    # FUNÇÃO NÃO UTILIZADA - comentada para teste
    # def _process_html_content(self, html_text: str, style) -> List:
        # """
        # Processa HTML convertendo para elementos ReportLab nativos
        # Mantém processamento de imagens intacto
        # """
        # story = []
        pass  # Função comentada - não utilizada
        
        # if not html_text.strip():
        #     return story
        # 
        # # Dividir texto por tags de imagem (manter processamento atual)
        # parts = re.split(r'<img[^>]*src=["\']([^"\']*)["\'][^>]*>', html_text)
        # 
        # for i, part in enumerate(parts):
        #     if i % 2 == 0:
        #         # Texto HTML - limpar e converter para elementos ReportLab
        #         if part.strip():
        #             # Aplicar limpeza HTML antes da conversão
        #             clean_html = self._clean_html_for_reportlab(part.strip())
        #             story.extend(self._convert_html_to_reportlab(clean_html, style))
        #     else:
        #         # URL da imagem - manter processamento atual
        #         if part.strip():
        #             img = self._process_image_from_text(part)
        #             if img:
        #                 # Centralizar a imagem
        #                 img.hAlign = 'CENTER'
        #                 story.append(img)
        # 
        # return story

    # FUNÇÃO NÃO UTILIZADA - comentada para teste
    # def _convert_html_to_reportlab(self, html_text: str, base_style) -> List:
        # """
        # Converte HTML de texto para elementos ReportLab nativos
        # """
        # try:
        #     story = []
        pass  # Função comentada - não utilizada
            
        # if not html_text.strip():
        #     return story
            
        # # Criar estilos específicos
        # bold_style = ParagraphStyle(
        #     'BoldStyle',
        #     parent=base_style,
        #     fontName='Helvetica-Bold'
        # )
        # 
        # italic_style = ParagraphStyle(
        #     'ItalicStyle', 
        #     parent=base_style,
        #     fontName='Helvetica-Oblique'
        # )
        # 
        # # Dividir por parágrafos
        # paragraphs = re.split(r'</?p[^>]*>', html_text)
        # 
        # for para_text in paragraphs:
        #     if not para_text.strip():
        #         continue
                    
        #     # Processar formatação dentro do parágrafo
        #     story.extend(self._process_paragraph_formatting(para_text.strip(), base_style, bold_style, italic_style))
        #     
        #     # Adicionar espaçamento entre parágrafos
        #     story.append(Spacer(1, 6))
        # 
        # return story
        # 
        # except Exception as e:
        # # Fallback: converter para texto simples
        # logging.warning(f"Erro ao converter HTML para ReportLab, usando fallback: {e}")
        # return self._fallback_html_to_text(html_text, base_style)

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

    # FUNÇÃO NÃO UTILIZADA - comentada para teste
    # def _generate_answer_key_pdf(self, test_data: Dict, questions_data: List[Dict], output_dir: str) -> Optional[str]:
        # """
        # Gera PDF separado com apenas o gabarito para o professor
        # """
        # try:
        #     # Nome do arquivo do gabarito
        pass  # Função comentada - não utilizada
        # filename = f"gabarito_{test_data['id']}.pdf"
        # pdf_path = os.path.join(output_dir, filename)
            
        # # Criar documento PDF
        # doc = SimpleDocTemplate(pdf_path, pagesize=portrait(A4))
        # story = []
            
        # # Adicionar cabeçalho do gabarito
        # story.append(Paragraph(f"<b>GABARITO - {test_data.get('title', 'Prova')}</b>", self.styles['TestTitle']))
        # story.append(Spacer(1, 20))
            
        # # Adicionar gabarito
        # story.extend(self._create_answer_key(test_data, questions_data, None))
        # 
        # # Construir PDF
        # doc.build(story)
        # 
        # return pdf_path
        # 
        # except Exception as e:
        # logging.error(f"Erro ao gerar gabarito: {str(e)}")
        # return None

    def _create_answer_sheet(self, test_data: Dict, student: Dict, questions_data: List[Dict], class_test_id: str = None) -> List:
        """Cria formulário de resposta com QR Code usando ReportLab"""
        story = []
        
        story.append(PageBreak())
        story.append(Paragraph("<b>GABARITO DE RESPOSTAS</b>", self.styles['TestTitle']))
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
            
            # Temporariamente modificar ALTERNATIVAS para 4 alternativas
            import app.formularios as formularios_module
            original_alternativas = formularios_module.ALTERNATIVAS
            formularios_module.ALTERNATIVAS = ["A", "B", "C", "D"]  # Apenas 4 alternativas
            
            try:
                # Dados do aluno
                student_id = student.get('id', 'unknown')
                student_name = student.get('nome', 'Nome não informado')
                
                # Contar total de questões
                total_questions = len(questions_data)
                
                # Usar a função original do formularios.py
                imagem, coordenadas_respostas, coordenadas_qr = gerar_formulario_com_qrcode(
                    student_id, 
                    student_name, 
                    total_questions, 
                    "temp_form.png"  # Arquivo temporário
                )
                
                if imagem and coordenadas_respostas and coordenadas_qr:
                    # Converter PIL Image para BytesIO
                    img_buffer = io.BytesIO()
                    imagem.save(img_buffer, format='PNG')
                    img_buffer.seek(0)
                    
                    # Adicionar imagem ao PDF com dimensões do formularios.py
                    elements.append(RLImage(img_buffer, width=15.58*cm, height=6.93*cm))
                    elements.append(Spacer(1, 20))
                    
                    # Limpar arquivo temporário
                    if os.path.exists("temp_form.png"):
                        os.remove("temp_form.png")
                else:
                    logging.error("Falha ao gerar formulário usando formularios.py")
                
            finally:
                # Restaurar ALTERNATIVAS original
                formularios_module.ALTERNATIVAS = original_alternativas
                
            return elements
            
        except Exception as e:
            logging.error(f"Erro ao gerar formulário usando formularios.py: {str(e)}")
            return []
    
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
        Lê QR Code da imagem com múltiplos métodos de detecção
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
        
        # Método 3: Detecção por regiões (QR Code geralmente no canto superior esquerdo)
        try:
            print(f"🔍 Tentando detecção por regiões...")
            height, width = imagem_gray.shape
            
            # Região superior esquerda (onde geralmente está o QR Code)
            roi_size = min(width, height) // 3
            roi_top_left = imagem_gray[0:roi_size, 0:roi_size]
            print(f"📍 ROI superior esquerda: {roi_top_left.shape}")
            
            dados, _, _ = detector.detectAndDecode(roi_top_left)
            if dados:
                print(f"✅ QR Code detectado com ROI: {dados}")
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
            
            # Redimensionar para tamanho FIXO (igual ao projeto.py)
            original_height, original_width = img_gray.shape
            print(f"📏 Dimensões originais: {original_width}x{original_height}")
            
            # FORÇAR redimensionamento para 720x320 (igual ao projeto.py)
            target_width = 720
            target_height = 320
            print(f"📐 Redimensionando para tamanho FIXO: {target_width}x{target_height} (igual projeto.py)")
            
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

    def detect_bubbles_robust(self, img, expected_cols=4, debug=True):
        """
        Pipeline robusto para detecção de bolhas baseado no código otimizado
        """
        print(f"🎯 INICIANDO DETECÇÃO ROBUSTA DE BOLHAS")
        print(f"📏 Imagem de entrada: {img.shape}")
        
        # 1. Correção de perspectiva (se detectar 4 cantos)
        img_corrigida = self.corrigir_perspectiva(img)
        print(f"✅ Perspectiva corrigida: {img_corrigida.shape}")
        
        # 2. Detectar candidatos globais e encontrar região densa
        gray = cv2.cvtColor(img_corrigida, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        thr = cv2.adaptiveThreshold(blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 3)
        
        contours, _ = cv2.findContours(thr, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        
        candidates = []
        for c in contours:
            area = cv2.contourArea(c)
            if area < 30 or area > 2000:
                continue
            peri = cv2.arcLength(c, True)
            if peri == 0:
                continue
            circularity = 4 * np.pi * area / (peri * peri)
            if circularity < 0.25 or circularity > 1.3:
                continue
            (cx, cy), r = cv2.minEnclosingCircle(c)
            if r < 3 or r > 40:
                continue
            candidates.append((int(cx), int(cy), int(r), area, circularity, c))
        
        print(f"🔍 Candidatos globais encontrados: {len(candidates)}")
        
        if not candidates:
            return {}
        
        # 3. Encontrar região densa (crop)
        centers_img = np.zeros(gray.shape, dtype=np.uint8)
        for (cx, cy, rr, area, circ, c) in candidates:
            cv2.circle(centers_img, (cx, cy), 8, 255, -1)
        
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (25, 25))
        dil = cv2.dilate(centers_img, kernel)
        blobs, _ = cv2.findContours(dil, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        best_bbox = None
        best_count = 0
        for b in blobs:
            x, y, w, h = cv2.boundingRect(b)
            cnt = sum(1 for (cx, cy, rr, area, circ, c) in candidates if x <= cx <= x + w and y <= cy <= y + h)
            if cnt > best_count:
                best_count = cnt
                best_bbox = (x, y, w, h)
        
        if best_bbox is None:
            sx, sy, ex, ey = 0, 0, img_corrigida.shape[1], img_corrigida.shape[0]
        else:
            x, y, w, h = best_bbox
            m = 8
            sx, sy = max(0, x - m), max(0, y - m)
            ex, ey = min(img_corrigida.shape[1], x + w + m), min(img_corrigida.shape[0], y + h + m)
        
        crop = img_corrigida[sy:ey, sx:ex]
        cgray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        cblur = cv2.GaussianBlur(cgray, (5, 5), 0)
        cth = cv2.adaptiveThreshold(cblur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 3)
        
        print(f"📦 Crop aplicado: {crop.shape}")
        
        # 4. Detectar contornos no crop
        conts_crop, _ = cv2.findContours(cth, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        cand2 = []
        for c in conts_crop:
            area = cv2.contourArea(c)
            if area < 50 or area > 2000:
                continue
            peri = cv2.arcLength(c, True)
            if peri == 0:
                continue
            circ = 4 * np.pi * area / (peri * peri)
            if circ < 0.25 or circ > 1.3:
                continue
            (cx, cy), r = cv2.minEnclosingCircle(c)
            if r < 3 or r > 40:
                continue
            cand2.append((int(cx), int(cy), int(r), area, circ, c))
        
        print(f"🔍 Candidatos no crop: {len(cand2)}")
        
        if not cand2:
            return {}
        
        # 5. Cluster por X para colunas (A, B, C, D)
        xs = sorted([c[0] for c in cand2])
        clusters = []
        cur = [xs[0]]
        for x in xs[1:]:
            if x - cur[-1] <= 20:
                cur.append(x)
            else:
                clusters.append(cur)
                cur = [x]
        clusters.append(cur)
        col_means = [np.mean(c) for c in clusters]
        
        if len(col_means) >= expected_cols + 1:
            col_means = sorted(col_means)[-expected_cols:]
        elif len(col_means) < expected_cols:
            col_means = sorted(col_means)
        
        print(f"📊 Centros das colunas: {[round(x, 1) for x in col_means]}")
        
        # 6. Cluster por Y para linhas (questões)
        ys = sorted([c[1] for c in cand2])
        row_clusters = []
        cur = [ys[0]]
        for y in ys[1:]:
            if y - cur[-1] <= 16:
                cur.append(y)
            else:
                row_clusters.append(cur)
                cur = [y]
        row_clusters.append(cur)
        row_means = [np.mean(r) for r in row_clusters]
        
        print(f"📊 Centros das linhas: {[round(y, 1) for y in row_means]}")
        
        # 7. Mapear contornos para grid
        def nearest_idx(val, arr):
            return int(np.argmin([abs(val - a) for a in arr]))
        
        grid = {}
        for cx, cy, r, area, circ, c in cand2:
            ri = nearest_idx(cy, row_means)
            ci = nearest_idx(cx, col_means)
            grid.setdefault(ri, []).append({'cx': cx, 'cy': cy, 'r': r, 'area': area, 'circ': circ, 'col': ci})
        
        print(f"📋 Grid: {len(grid)} linhas detectadas")
        
        # 8. Processar cada linha
        answers = {}
        question_number = 1
        
        row_indices_sorted = sorted(grid.keys(), key=lambda x: row_means[x])
        for ri in row_indices_sorted:
            cells = grid[ri]
            distinct_cols = set([c['col'] for c in cells])
            if len(distinct_cols) < 2:
                continue
            
            option_means = {}
            for ci in range(len(col_means)):
                candidates_in_cell = [c for c in cells if c['col'] == ci]
                if not candidates_in_cell:
                    continue
                
                # Escolher o candidato mais escuro
                cell_options = []
                for cand in candidates_in_cell:
                    cx, cy, r = cand['cx'], cand['cy'], cand['r']
                    mask = np.zeros(cgray.shape, dtype=np.uint8)
                    cv2.circle(mask, (cx, cy), max(1, int(r * 0.6)), 255, -1)
                    mean = float(cv2.mean(cgray, mask=mask)[0])
                    cell_options.append((mean, cand))
                
                min_mean, sel = min(cell_options, key=lambda x: x[0])
                option_means[ci] = {'mean': min_mean, 'cx': sel['cx'], 'cy': sel['cy'], 'r': sel['r']}
            
            if not option_means:
                continue
            
            # Regras de decisão adaptativas
            ordered = sorted([(v['mean'], k) for k, v in option_means.items()], key=lambda x: x[0])
            means = [m for m, k in ordered]
            cols_sorted = [k for m, k in ordered]
            median = np.median([v['mean'] for v in option_means.values()])
            min_mean = means[0]
            second = means[1] if len(means) > 1 else 9999
            
            marked_cols = []
            # Regra 1: se o mínimo for MUITO menor que a mediana
            if min_mean < median * 0.6:
                marked_cols = [cols_sorted[0]]
            # Regra 2: se gap entre 1º e 2º for grande
            elif (second - min_mean) > 40:
                marked_cols = [cols_sorted[0]]
            else:
                # Fallback: aceita todos abaixo de median*0.75
                marked_cols = [k for k, v in option_means.items() if v['mean'] < median * 0.75]
            
            letters = [chr(65 + c) for c in marked_cols]
            if len(letters) == 0:
                ans = None
            elif len(letters) == 1:
                ans = letters[0]
            else:
                ans = letters
            
            answers[question_number] = ans
            print(f"  ✅ Questão {question_number}: {ans}")
            question_number += 1
        
        print(f"📊 RESPOSTAS DETECTADAS: {answers}")
        return answers

    def processar_correcao_completa(self, test_id, image_data):
        """
        Processa correção completa: QR code + detecção de bolhas + salvamento no banco
        """
        from app import db
        
        print(f"🎯 INICIANDO PROCESSAMENTO DE CORREÇÃO COMPLETA")
        print(f"📋 Test ID: {test_id}")
        
        try:
            # 1. Decodificar imagem
            img_result = self.processar_imagem_formulario(image_data)
            if img_result is None or not img_result.get('success'):
                return {"success": False, "error": "Erro ao decodificar imagem"}
            
            # Usar imagem colorida para QR code e escala de cinza para detecção de bolhas
            img_color = self._decode_image_direct(image_data)
            img_gray = img_result['image_processed']
            
            print(f"🖼️ Imagem colorida: {img_color.shape}")
            print(f"🖼️ Imagem escala de cinza: {img_gray.shape}")
            
            # 2. Extrair QR code (student_id) da imagem colorida
            student_id = self._extrair_qr_code(img_color)
            if not student_id:
                return {"success": False, "error": "QR code não detectado ou inválido"}
            
            print(f"👤 Student ID detectado: {student_id}")
            
            # 3. Detectar respostas usando pipeline robusto na imagem colorida
            respostas_detectadas = self.detect_bubbles_robust(img_color, expected_cols=4, debug=True)
            if not respostas_detectadas:
                return {"success": False, "error": "Nenhuma resposta detectada"}
            
            print(f"📝 Respostas detectadas: {respostas_detectadas}")
            
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

    def _extrair_qr_code(self, img):
        """
        Extrai QR code da imagem e retorna o student_id
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
            respostas_detectadas = self._detectar_respostas_com_coordenadas(binary_image, coordinates)
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
        Gera coordenadas das alternativas baseado no sistema original
        """
        coordenadas = []
        
        # Coordenadas base do sistema original
        base_coords = [
            (198, 14, 20, 20), (238, 14, 20, 20), (278, 14, 20, 20), (318, 14, 20, 20), (358, 14, 20, 20),
            (198, 42, 20, 20), (238, 42, 20, 20), (278, 42, 20, 20), (318, 42, 20, 20), (358, 42, 20, 20),
            (198, 70, 20, 20), (238, 70, 20, 20), (278, 70, 20, 20), (318, 70, 20, 20), (358, 70, 20, 20),
            (198, 98, 20, 20), (238, 98, 20, 20), (278, 98, 20, 20), (318, 98, 20, 20), (358, 98, 20, 20),
            (198, 126, 20, 20), (238, 126, 20, 20), (278, 126, 20, 20), (318, 126, 20, 20), (358, 126, 20, 20),
            (198, 154, 20, 20), (238, 154, 20, 20), (278, 154, 20, 20), (318, 154, 20, 20), (358, 154, 20, 20),
            (198, 182, 20, 20), (238, 182, 20, 20), (278, 182, 20, 20), (318, 182, 20, 20), (358, 182, 20, 20),
            (198, 210, 20, 20), (238, 210, 20, 20), (278, 210, 20, 20), (318, 210, 20, 20), (358, 210, 20, 20),
            (198, 238, 20, 20), (238, 238, 20, 20), (278, 238, 20, 20), (318, 238, 20, 20), (358, 238, 20, 20),
            (198, 266, 20, 20), (238, 266, 20, 20), (278, 266, 20, 20), (318, 266, 20, 20), (358, 266, 20, 20),
            (479, 14, 20, 20), (519, 14, 20, 20), (559, 14, 20, 20), (599, 14, 20, 20), (639, 14, 20, 20),
            (479, 42, 20, 20), (519, 42, 20, 20), (559, 42, 20, 20), (599, 42, 20, 20), (639, 42, 20, 20),
            (479, 70, 20, 20), (519, 70, 20, 20), (559, 70, 20, 20), (599, 70, 20, 20), (639, 70, 20, 20),
            (479, 98, 20, 20), (519, 98, 20, 20), (559, 98, 20, 20), (599, 98, 20, 20), (639, 98, 20, 20),
            (479, 126, 20, 20), (519, 126, 20, 20), (559, 126, 20, 20), (599, 126, 20, 20), (639, 126, 20, 20),
            (479, 154, 20, 20), (519, 154, 20, 20), (559, 154, 20, 20), (599, 154, 20, 20), (639, 154, 20, 20),
            (479, 182, 20, 20), (519, 182, 20, 20), (278, 182, 20, 20), (318, 182, 20, 20), (358, 182, 20, 20),
            (479, 210, 20, 20), (519, 210, 20, 20), (559, 210, 20, 20), (599, 210, 20, 20), (639, 210, 20, 20),
            (479, 238, 20, 20), (519, 238, 20, 20), (559, 238, 20, 20), (599, 238, 20, 20), (639, 238, 20, 20),
            (479, 266, 20, 20), (519, 266, 20, 20), (559, 266, 20, 20), (599, 266, 20, 20), (639, 266, 20, 20)
        ]
        
        # Retornar apenas as coordenadas necessárias para o número de questões
        num_coords_needed = num_questions * 5  # 5 alternativas por questão
        return base_coords[:num_coords_needed]

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
        Desenha uma coluna do formulário usando as alternativas específicas de cada questão
        """
        if not questions_data:
            return
            
        # Calcular largura da coluna baseada no máximo de alternativas
        max_alternativas = max(len(q.get('alternative_ids', [])) for q in questions_data)
        largura_col_unica = LARGURA_COL_NUM + (max_alternativas * LARGURA_COL_ALT) + (PADDING_HORIZONTAL_COL * 2)
        
        altura_efetiva_linhas = len(questions_data) * ALTURA_LINHA
        y_final_borda_real = offset_y + altura_efetiva_linhas

        # Bordas da coluna
        desenho.line([(offset_x, offset_y), (offset_x, y_final_borda_real)], fill='black', width=ESPESSURA_LINHA)
        desenho.line([(offset_x + largura_col_unica - 1, offset_y), (offset_x + largura_col_unica - 1, y_final_borda_real)], fill='black', width=ESPESSURA_LINHA)
        
        # Linha vertical separando número das alternativas
        x_vert_num = offset_x + PADDING_HORIZONTAL_COL + LARGURA_COL_NUM
        desenho.line([(x_vert_num, offset_y), (x_vert_num, y_final_borda_real)], fill='black', width=ESPESSURA_LINHA)

        # Linha superior
        desenho.line([(offset_x, offset_y), (offset_x + largura_col_unica - 1, offset_y)], fill='black', width=ESPESSURA_LINHA)

        # Desenhar cada questão
        for i, question_data in enumerate(questions_data):
            y_linha_superior = offset_y + (i * ALTURA_LINHA)
            y_linha_inferior = y_linha_superior + ALTURA_LINHA
            centro_y_linha = y_linha_superior + (ALTURA_LINHA / 2)

            # Linha horizontal entre questões
            if i < len(questions_data) - 1:
                desenho.line([(offset_x, y_linha_inferior), (offset_x + largura_col_unica - 1, y_linha_inferior)], fill='black', width=ESPESSURA_LINHA)

            # Número da questão
            question_number = i + 1
            texto_num = str(question_number)
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

            # Alternativas específicas da questão
            alternative_ids = question_data.get('alternative_ids', [])
            for j, alt_id in enumerate(alternative_ids):
                centro_x_alt = offset_x + PADDING_HORIZONTAL_COL + LARGURA_COL_NUM + (j * LARGURA_COL_ALT) + (LARGURA_COL_ALT / 2)

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

    # FUNÇÃO NÃO UTILIZADA - comentada para teste
    # def generate_individual_test_pdf(self, test_data: Dict, student_data: Dict, 
    #                                questions_data: List[Dict], output_dir: str) -> Optional[str]:
        # """
        # Gera PDF individual para um aluno específico
        # 
        # Args:
        #     test_data: Dados da prova
        pass  # Função comentada - não utilizada
        # student_data: Dados do aluno
        # questions_data: Lista de questões
        # output_dir: Diretório de saída
        # 
        # Returns:
        #     Caminho do arquivo gerado ou None se erro
        # """
        # try:
        #     # Criar diretório se não existir
        #     os.makedirs(output_dir, exist_ok=True)
            
        # # Nome do arquivo
        # timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # filename = f"prova_individual_{test_data['id']}_{student_data['id']}_{timestamp}.pdf"
        # filepath = os.path.join(output_dir, filename)
            
        # # Gerar PDF usando o método existente, mas com dados de um aluno apenas
        # students_data = [student_data]  # Lista com apenas um aluno
        # 
        # # Usar o método existente de geração combinada, mas com apenas um aluno
        # result = self.generate_combined_test_pdf(test_data, students_data, questions_data, output_dir)
        # 
        # if result:
        #     # Renomear arquivo para individual
        #     if os.path.exists(result):
        # os.rename(result, filepath)
        # return filepath
        # 
        # return None
        # 
        # except Exception as e:
        # logging.error(f"Erro ao gerar PDF individual: {str(e)}")
        # return None

    # FUNÇÃO NÃO UTILIZADA - comentada para teste
    # def generate_individual_answer_key(self, test_data: Dict, questions_data: List[Dict], 
    #                                  output_dir: str) -> Optional[str]:
        # """
        # Gera gabarito individual para uma prova
        # 
        # Args:
        #     test_data: Dados da prova
        pass  # Função comentada - não utilizada
        # questions_data: Lista de questões
        # output_dir: Diretório de saída
        # 
        # Returns:
        #     Caminho do arquivo gerado ou None se erro
        # """
        # try:
        #     # Criar diretório se não existir
        #     os.makedirs(output_dir, exist_ok=True)
            
        # # Nome do arquivo
        # timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # filename = f"gabarito_individual_{test_data['id']}_{timestamp}.pdf"
        # filepath = os.path.join(output_dir, filename)
            
        # # Gerar gabarito usando o método existente
        # result = self.generate_answer_key_pdf(test_data, questions_data, output_dir)
        # 
        # if result:
        # # Renomear arquivo para individual
        # if os.path.exists(result):
        #     os.rename(result, filepath)
        #     return filepath
        # 
        # return None
        # 
        # except Exception as e:
        # logging.error(f"Erro ao gerar gabarito individual: {str(e)}")
        # return None

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
        Busca coordenadas específicas do formulário
        """
        try:
            from app import db
            
            print(f"🔍 BUSCANDO COORDENADAS ESPECÍFICAS...")
            print(f"   Test ID: {test_id}")
            print(f"   QR Code ID: {qr_code_id}")
            print(f"   Student ID: {student_id}")
            
            # Buscar todas as coordenadas para este teste
            all_coords = FormCoordinates.query.filter_by(test_id=test_id).all()
            print(f"📊 Total de coordenadas encontradas para este teste: {len(all_coords)}")
            
            for coord in all_coords:
                print(f"   - QR: {coord.qr_code_id}, Student: {coord.student_id}")
            
            # Primeiro tentar com qr_code_id específico
            form_coords = FormCoordinates.query.filter_by(
                test_id=test_id,
                qr_code_id=qr_code_id,
                student_id=student_id
            ).first()
            
            # Se não encontrar, tentar apenas com test_id e student_id
            if not form_coords:
                print(f"⚠️ Não encontrou com QR Code ID específico, tentando apenas com test_id e student_id...")
                form_coords = FormCoordinates.query.filter_by(
                    test_id=test_id,
                    student_id=student_id
                ).first()
                
                if form_coords:
                    print(f"✅ Encontrou coordenadas usando apenas test_id e student_id")
                    print(f"   QR Code ID salvo: {form_coords.qr_code_id}")
                    print(f"   QR Code ID detectado: {qr_code_id}")
                else:
                    print(f"❌ Não encontrou coordenadas nem com test_id e student_id")
            
            if form_coords:
                print(f"✅ Coordenadas encontradas!")
                print(f"   Coordenadas: {form_coords.coordinates}")
                return form_coords.coordinates
            else:
                print(f"❌ Coordenadas não encontradas para esta combinação específica")
                logging.warning(f"Coordenadas não encontradas para test_id={test_id}, qr_code_id={qr_code_id}, student_id={student_id}")
                return None
                
        except Exception as e:
            print(f"❌ Erro ao buscar coordenadas: {str(e)}")
            logging.error(f"Erro ao buscar coordenadas: {str(e)}")
            return None
    
    def _detectar_respostas_com_coordenadas(self, binary_image, coordinates: Dict) -> Dict:
        """
        Detecta respostas usando coordenadas específicas do formulário
        """
        try:
            print(f"🔍 DETECTANDO RESPOSTAS COM COORDENADAS ESPECÍFICAS")
            print(f"📏 Dimensões da imagem binária: {binary_image.shape}")
            print(f"🗺️ Coordenadas recebidas: {len(coordinates.get('subjects', {}))} disciplinas")
            
            respostas_por_disciplina = {}
            
            for subject_key, subject_coords in coordinates.get("subjects", {}).items():
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
                        
                        # Detectar se está marcado
                        is_marked = self._detectar_marcacao_circular(binary_image, x, y, radius)
                        respostas_por_disciplina[subject_key][question_key][alt_id] = is_marked
                        
                        print(f"    {alt_id}: {'✅ MARCADO' if is_marked else '❌ NÃO MARCADO'}")
            
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
            
            # Buscar coordenadas reais do banco de dados
            from app.models.formCoordinates import FormCoordinates
            form_coords = FormCoordinates.query.filter_by(
                qr_code_id=student_id,
                test_id=test_id
            ).first()
            
            if not form_coords:
                print(f"❌ Coordenadas não encontradas para QR: {student_id}, Test: {test_id}")
                return {
                    'success': False,
                    'error': f'Coordenadas não encontradas para o formulário do aluno {student_id}',
                    'method': 'projeto_style'
                }
            
            print(f"✅ Coordenadas encontradas: {len(form_coords.coordinates)} círculos")
            
            # USAR COORDENADAS DINÂMICAS DO FORMULARIOS.PY
            print(f"🎯 USANDO COORDENADAS DINÂMICAS DO FORMULARIOS.PY")
            
            # Ajustar coordenadas proporcionalmente de 720x320 para 688x301
            fator_x = 688 / 720
            fator_y = 301 / 320
            
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
