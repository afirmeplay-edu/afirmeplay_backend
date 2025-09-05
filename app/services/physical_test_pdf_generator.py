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
import requests
import re
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional
import logging

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
QR_CODE_SIZE = 150       # Aumentado de 120 para 150
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

    def generate_test_pdf(self, test_data: Dict, students_data: List[Dict], 
                         questions_data: List[Dict], output_dir: str) -> List[Dict]:
        """
        Gera PDFs de provas físicas para todos os alunos
        
        Args:
            test_data: Dados da prova (test_id, title, description, etc.)
            students_data: Lista de alunos com dados (id, nome, email, etc.)
            questions_data: Lista de questões ordenadas
            output_dir: Diretório para salvar os PDFs
            
        Returns:
            Lista com informações dos PDFs gerados
        """
        # Criar diretório absoluto
        abs_output_dir = os.path.abspath(output_dir)
        os.makedirs(abs_output_dir, exist_ok=True)
        generated_files = []
        
        # Gerar gabarito único para o professor
        answer_key_path = self._generate_answer_key_pdf(test_data, questions_data, abs_output_dir)
        
        for student in students_data:
            try:
                # Gerar PDF individual para cada aluno (SEM gabarito)
                pdf_path = self._generate_individual_test_pdf(
                    test_data, student, questions_data, abs_output_dir
                )
                
                if pdf_path:
                    generated_files.append({
                        'student_id': student['id'],
                        'student_name': student['nome'],
                        'pdf_path': pdf_path,
                        'answer_key_path': answer_key_path,  # Caminho do gabarito
                        'qr_code_data': f"{test_data['id']}_{student['id']}"
                    })
                    
            except Exception as e:
                logging.error(f"Erro ao gerar PDF para aluno {student['id']}: {str(e)}")
                continue
        
        return generated_files

    def generate_combined_test_pdf(self, test_data: Dict, students_data: List[Dict], 
                                  questions_data: List[Dict], output_dir: str) -> Optional[str]:
        """
        Gera 1 PDF único contendo todas as provas e gabaritos
        
        Args:
            test_data: Dados da prova (test_id, title, description, etc.)
            students_data: Lista de alunos com dados (id, nome, email, etc.)
            questions_data: Lista de questões ordenadas
            output_dir: Diretório para salvar o PDF
            
        Returns:
            Caminho do PDF gerado ou None se houver erro
        """
        try:
            # Criar diretório absoluto
            abs_output_dir = os.path.abspath(output_dir)
            os.makedirs(abs_output_dir, exist_ok=True)
            
            # Nome do arquivo combinado usando o nome da prova
            test_title = test_data.get('title', 'Prova').replace(' ', '_').replace('/', '_')
            filename = f"{test_title}_{test_data['id']}.pdf"
            pdf_path = os.path.join(abs_output_dir, filename)
            
            # Criar documento PDF
            doc = SimpleDocTemplate(pdf_path, pagesize=portrait(A4))
            story = []
            
            # Adicionar cada aluno
            for i, student in enumerate(students_data):
                # Cabeçalho da prova para este aluno
                story.extend(self._create_test_header(test_data, student))
                
                # Questões da prova
                story.extend(self._create_questions_section(questions_data))
                
                # Gabarito para este aluno (usando o mesmo método do gabarito separado)
                story.extend(self._create_answer_key(test_data, questions_data, student))
                
                # Quebra de página entre alunos (exceto no último)
                if i < len(students_data) - 1:
                    story.append(PageBreak())
            
            # Construir PDF
            doc.build(story)
            
            return pdf_path
            
        except Exception as e:
            logging.error(f"Erro ao gerar PDF combinado: {str(e)}")
            return None

    def _generate_individual_test_pdf(self, test_data: Dict, student: Dict, 
                                    questions_data: List[Dict], output_dir: str) -> Optional[str]:
        """
        Gera PDF individual para um aluno específico
        """
        try:
            # Nome do arquivo
            safe_name = "".join(c for c in student['nome'] if c.isalnum() or c in (' ', '_')).rstrip().replace(" ", "_")
            filename = f"prova_{test_data['id']}_{student['id']}_{safe_name}.pdf"
            pdf_path = os.path.join(output_dir, filename)
            
            # Criar documento PDF
            doc = SimpleDocTemplate(pdf_path, pagesize=portrait(A4))
            story = []
            
            # Adicionar cabeçalho da prova
            story.extend(self._create_test_header(test_data, student))
            
            # Adicionar questões
            story.extend(self._create_questions_section(questions_data))
            
            # Adicionar formulário de resposta
            story.extend(self._create_answer_sheet(test_data, student, len(questions_data)))
            
            # NÃO adicionar gabarito no PDF do aluno!
            
            # Construir PDF
            doc.build(story)
            
            return pdf_path
            
        except Exception as e:
            logging.error(f"Erro ao gerar PDF individual: {str(e)}")
            return None

    def _create_test_header(self, test_data: Dict, student: Dict) -> List:
        """Cria cabeçalho da prova com dados do aluno"""
        from reportlab.platypus import Table, TableStyle
        from reportlab.lib import colors
        
        story = []
        
        # Título da prova
        story.append(Paragraph(f"{test_data.get('title', 'Prova')}", self.styles['TestTitle']))
        
        # Dados do aluno em formato moderno
        current_date = datetime.now().strftime("%d/%m/%Y")
        
        # Criar tabela para layout moderno
        header_data = [
            ['Aluno:', student['nome']],
            ['Data:', current_date],
            ['Prova:', test_data.get('description', '')]
        ]
        
        header_table = Table(header_data, colWidths=[80, 400])
        header_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 14),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#374151')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
        ]))
        
        story.append(header_table)
        story.append(Spacer(1, 15))
        
        return story

    def _create_questions_section(self, questions_data: List[Dict]) -> List:
        """Cria seção com todas as questões"""
        story = []
        
        # Adicionar cada questão
        for i, question in enumerate(questions_data, 1):
            story.extend(self._create_single_question(question, i))
            story.append(Spacer(1, 35))  # Aumentado de 25 para 35
        
        return story

    def _create_single_question(self, question: Dict, question_number: int) -> List:
        """Cria uma questão individual com layout moderno"""
        from reportlab.platypus import Table, TableStyle, KeepTogether
        from reportlab.lib import colors
        
        story = []
        
        # Container da questão com bordas e sombra
        question_content = []
        
        # Número da questão
        question_content.append(Paragraph(f"Questão {question_number}", self.styles['QuestionNumber']))
        
        # Adicionar espaçamento após o número da questão
        question_content.append(Spacer(1, 8))
        
        # Tags de informação
        tags_data = []
        if question.get('question_type'):
            # Traduzir multiple_choice para português
            question_type = question['question_type']
            if question_type == 'multiple_choice':
                question_type = 'Multipla Escolha'
            tags_data.append(question_type)
        if question.get('value'):
            tags_data.append(f"{question['value']} pontos")
        if question.get('difficulty_level'):
            tags_data.append(question['difficulty_level'])
        if question.get('skills'):
            tags_data.append(f"{len(question['skills'])} habilidade(s)")
        
        if tags_data:
            tags_text = " • ".join(tags_data)
            question_content.append(Paragraph(f"<font color='#6b7280'>{tags_text}</font>", self.styles['InfoTag']))
        
        # Título da questão (se houver)
        if question.get('title'):
            title_text = question['title']
            # Verificar se o título tem quebra de linha
            if '\n' in title_text or '<br' in title_text:
                # Criar estilo com leading aumentado para espaçamento entre linhas
                title_style = ParagraphStyle(
                    'QuestionTitleMultiLine',
                    parent=self.styles['QuestionTitle'],
                    leading=24,  # controla o espaçamento entre linhas (fontSize=16 + 8 de espaçamento)
                    fontSize=16,  # Garantir que o fontSize seja mantido
                    fontName='Helvetica-Bold'  # Garantir que a fonte seja mantida
                )
                # Processar quebras de linha mantendo o texto como um único parágrafo
                processed_title = re.sub(r'\n|<br\s*/?>', '<br/>', title_text)
                title_para = Paragraph(processed_title, title_style)
                question_content.append(title_para)
            else:
                title_para = Paragraph(title_text, self.styles['QuestionTitle'])
                question_content.append(title_para)
        
        # Texto da questão (renderizar HTML)
        question_text = question.get('formatted_text', question.get('text', ''))
        if question_text:
            # Processar HTML mantendo formatação
            question_content.extend(self._process_html_content(question_text, self.styles['QuestionText']))
        
        # Segundo enunciado (se houver) - renderizar HTML
        second_statement = question.get('secondstatement', '')
        if second_statement:
            question_content.extend(self._process_html_content(second_statement, self.styles['SecondStatement']))
        
        # Habilidades avaliadas
        skill_codes = self._get_skill_codes(question)
        if skill_codes:
            skills_text = " • ".join(skill_codes)
            question_content.append(Paragraph(f"<font color='#8b5cf6'>• Habilidades Avaliadas: {skills_text}</font>", self.styles['Skills']))
        
        # Alternativas
        alternatives = question.get('alternatives', [])
        if alternatives:
            question_content.append(Paragraph("<font color='#8b5cf6'>• Alternativas:</font>", self.styles['Skills']))
            
            # Criar tabela para alternativas
            alt_data = []
            for alt in alternatives:
                letter = alt.get('id', '')  # Usar 'id' em vez de 'letter'
                text = alt.get('text', '')
                alt_data.append([f"{letter}: ( )", text])
            
            if alt_data:
                alt_table = Table(alt_data, colWidths=[40, 450])  # Aumentado espaçamento
                alt_table.setStyle(TableStyle([
                    ('ALIGN', (0, 0), (0, -1), 'CENTER'),  # Letras centralizadas
                    ('ALIGN', (1, 0), (1, -1), 'LEFT'),    # Texto alinhado à esquerda
                    ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 12),  # Aumentado de 11 para 12
                    ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#374151')),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 12),  # Aumentado de 8 para 12
                    ('TOPPADDING', (0, 0), (-1, -1), 12),     # Aumentado de 8 para 12
                    ('LEFTPADDING', (0, 0), (-1, -1), 15),    # Aumentado de 10 para 15
                    ('RIGHTPADDING', (0, 0), (-1, -1), 15),   # Aumentado de 10 para 15
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),      # Alinhamento vertical no topo
                ]))
                question_content.append(alt_table)
        
        # Criar container com bordas e estilo moderno como na imagem
        container_table = Table([[question_content]], colWidths=[500])
        container_table.setStyle(TableStyle([
            ('BORDER', (0, 0), (-1, -1), 1, colors.HexColor('#e5e7eb')),  # Borda cinza
            ('LEFTPADDING', (0, 0), (-1, -1), 10),  # Diminuído de 20 para 10
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),  # Diminuído de 20 para 10
            ('TOPPADDING', (0, 0), (-1, -1), 20),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 20),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        
        story.append(container_table)
        story.append(Spacer(1, 20))  # Espaçamento entre questões
        
        return story

    def _process_html_content(self, html_text: str, style) -> List:
        """
        Processa HTML convertendo para elementos ReportLab nativos
        Mantém processamento de imagens intacto
        """
        story = []
        
        if not html_text.strip():
            return story
        
        # Dividir texto por tags de imagem (manter processamento atual)
        parts = re.split(r'<img[^>]*src=["\']([^"\']*)["\'][^>]*>', html_text)
        
        for i, part in enumerate(parts):
            if i % 2 == 0:
                # Texto HTML - limpar e converter para elementos ReportLab
                if part.strip():
                    # Aplicar limpeza HTML antes da conversão
                    clean_html = self._clean_html_for_reportlab(part.strip())
                    story.extend(self._convert_html_to_reportlab(clean_html, style))
            else:
                # URL da imagem - manter processamento atual
                if part.strip():
                    img = self._process_image_from_text(part)
                    if img:
                        # Centralizar a imagem
                        img.hAlign = 'CENTER'
                        story.append(img)
        
        return story

    def _convert_html_to_reportlab(self, html_text: str, base_style) -> List:
        """
        Converte HTML de texto para elementos ReportLab nativos
        """
        try:
            story = []
            
            if not html_text.strip():
                return story
            
            # Criar estilos específicos
            bold_style = ParagraphStyle(
                'BoldStyle',
                parent=base_style,
                fontName='Helvetica-Bold'
            )
            
            italic_style = ParagraphStyle(
                'ItalicStyle', 
                parent=base_style,
                fontName='Helvetica-Oblique'
            )
            
            # Dividir por parágrafos
            paragraphs = re.split(r'</?p[^>]*>', html_text)
            
            for para_text in paragraphs:
                if not para_text.strip():
                    continue
                    
                # Processar formatação dentro do parágrafo
                story.extend(self._process_paragraph_formatting(para_text.strip(), base_style, bold_style, italic_style))
                
                # Adicionar espaçamento entre parágrafos
                story.append(Spacer(1, 6))
            
            return story
            
        except Exception as e:
            # Fallback: converter para texto simples
            logging.warning(f"Erro ao converter HTML para ReportLab, usando fallback: {e}")
            return self._fallback_html_to_text(html_text, base_style)

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

    def _generate_answer_key_pdf(self, test_data: Dict, questions_data: List[Dict], output_dir: str) -> Optional[str]:
        """
        Gera PDF separado com apenas o gabarito para o professor
        """
        try:
            # Nome do arquivo do gabarito
            filename = f"gabarito_{test_data['id']}.pdf"
            pdf_path = os.path.join(output_dir, filename)
            
            # Criar documento PDF
            doc = SimpleDocTemplate(pdf_path, pagesize=portrait(A4))
            story = []
            
            # Adicionar cabeçalho do gabarito
            story.append(Paragraph(f"<b>GABARITO - {test_data.get('title', 'Prova')}</b>", self.styles['TestTitle']))
            story.append(Spacer(1, 20))
            
            # Adicionar gabarito
            story.extend(self._create_answer_key(test_data, questions_data, None))
            
            # Construir PDF
            doc.build(story)
            
            return pdf_path
            
        except Exception as e:
            logging.error(f"Erro ao gerar gabarito: {str(e)}")
            return None

    def _create_answer_sheet(self, test_data: Dict, student: Dict, num_questions: int) -> List:
        """Cria formulário de resposta com QR Code"""
        story = []
        
        story.append(PageBreak())
        story.append(Paragraph("<b>GABARITO DE RESPOSTAS</b>", self.styles['TestTitle']))
        story.append(Spacer(1, 20))
        
        # Gerar imagem do formulário de resposta
        form_image = self._generate_answer_sheet_image(test_data, student, num_questions)
        
        if form_image:
            # Converter PIL Image para bytes
            img_buffer = io.BytesIO()
            form_image.save(img_buffer, format='PNG')
            img_buffer.seek(0)
            
            # Adicionar imagem ao PDF (aumentado para ficar maior)
            img = RLImage(img_buffer, width=20*cm, height=10*cm)
            img.hAlign = 'CENTER'
            story.append(img)
        
        return story

    def _create_answer_key(self, test_data: Dict, questions_data: List[Dict], student: Dict = None) -> List:
        """Cria gabarito idêntico à imagem usando o modelo fornecido"""
        from reportlab.platypus import Table, TableStyle, Paragraph
        from reportlab.lib import colors
        
        story = []
        
        # Criar QR Code
        qr_data = f"{test_data['id']}_gabarito"
        qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=4, border=2)
        qr.add_data(qr_data)
        qr.make(fit=True)
        img_qr = qr.make_image(fill_color="black", back_color="white").resize((80, 80))
        
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

    def _generate_answer_sheet_image(self, test_data: Dict, student: Dict, num_questions: int) -> Optional[PILImage.Image]:
        """
        Gera imagem do formulário de resposta baseado no formularios.py original
        """
        try:
            # Criar QR Code
            qr_data = f"{test_data['id']}_{student['id']}"
            qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=4, border=2)
            qr.add_data(qr_data)
            qr.make(fit=True)
            img_qr = qr.make_image(fill_color="black", back_color="white").resize((QR_CODE_SIZE, QR_CODE_SIZE))
            
            # Criar imagem base
            imagem = PILImage.new('RGB', (LARGURA_FINAL, ALTURA_FINAL), 'white')
            desenho = ImageDraw.Draw(imagem)
            
            # Configurar fontes
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
            
            # Posicionar QR Code
            x_qr = PADDING_LEFT_AREA_QR
            y_qr = (ALTURA_CONTEUDO / 2) - (QR_CODE_SIZE / 2)
            imagem.paste(img_qr, (int(x_qr), int(y_qr)))
            
            # Adicionar nome do aluno
            nome_texto = student['nome']
            try:
                desenho.text((x_qr, y_qr - 30), nome_texto, fill='black', font=fonte_nome)
            except:
                desenho.text((x_qr, y_qr - 30), nome_texto, fill='black')
            
            # Gerar coordenadas das alternativas
            coordenadas = self._generate_alternative_coordinates(num_questions)
            
            # Desenhar formulário de respostas
            self._draw_answer_form(desenho, fonte_num, fonte_alt, num_questions, coordenadas)
            
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

    def _draw_answer_form(self, desenho, fonte_num, fonte_alt, num_questions: int, coordenadas: List[Tuple]):
        """
        Desenha o formulário de respostas baseado no sistema original
        """
        # Ajustar posição do formulário (direita do QR Code)
        offset_x = 200  # Posição X do formulário
        
        # Desenhar bordas
        largura_col_unica = LARGURA_COL_NUM + (len(ALTERNATIVAS) * LARGURA_COL_ALT) + (PADDING_HORIZONTAL_COL * 2)
        altura_efetiva = num_questions * ALTURA_LINHA
        
        # Borda externa
        desenho.rectangle([(offset_x, 10), (offset_x + largura_col_unica, 10 + altura_efetiva)], 
                         outline='black', width=ESPESSURA_LINHA)
        
        # Linha vertical separando número da questão das alternativas
        x_vert = offset_x + PADDING_HORIZONTAL_COL + LARGURA_COL_NUM
        desenho.line([(x_vert, 10), (x_vert, 10 + altura_efetiva)], fill='black', width=ESPESSURA_LINHA)
        
        # Desenhar questões e alternativas
        for i in range(num_questions):
            y_linha = 10 + (i * ALTURA_LINHA)
            y_linha_inferior = y_linha + ALTURA_LINHA
            centro_y = y_linha + (ALTURA_LINHA / 2)
            
            # Linha horizontal entre questões
            if i < num_questions - 1:
                desenho.line([(offset_x, y_linha_inferior), (offset_x + largura_col_unica, y_linha_inferior)], 
                           fill='black', width=ESPESSURA_LINHA)
            
            # Número da questão
            texto_num = str(i + 1)
            centro_x_num = offset_x + PADDING_HORIZONTAL_COL + (LARGURA_COL_NUM / 2)
            try:
                desenho.text((centro_x_num, centro_y), texto_num, fill='black', font=fonte_num, anchor="mm")
            except:
                desenho.text((centro_x_num, centro_y), texto_num, fill='black')
            
            # Alternativas A, B, C, D, E
            for j, alt in enumerate(ALTERNATIVAS):
                centro_x_alt = offset_x + PADDING_HORIZONTAL_COL + LARGURA_COL_NUM + (j * LARGURA_COL_ALT) + (LARGURA_COL_ALT / 2)
                
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

    def generate_individual_test_pdf(self, test_data: Dict, student_data: Dict, 
                                   questions_data: List[Dict], output_dir: str) -> Optional[str]:
        """
        Gera PDF individual para um aluno específico
        
        Args:
            test_data: Dados da prova
            student_data: Dados do aluno
            questions_data: Lista de questões
            output_dir: Diretório de saída
            
        Returns:
            Caminho do arquivo gerado ou None se erro
        """
        try:
            # Criar diretório se não existir
            os.makedirs(output_dir, exist_ok=True)
            
            # Nome do arquivo
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"prova_individual_{test_data['id']}_{student_data['id']}_{timestamp}.pdf"
            filepath = os.path.join(output_dir, filename)
            
            # Gerar PDF usando o método existente, mas com dados de um aluno apenas
            students_data = [student_data]  # Lista com apenas um aluno
            
            # Usar o método existente de geração combinada, mas com apenas um aluno
            result = self.generate_combined_test_pdf(test_data, students_data, questions_data, output_dir)
            
            if result:
                # Renomear arquivo para individual
                if os.path.exists(result):
                    os.rename(result, filepath)
                    return filepath
            
            return None
            
        except Exception as e:
            logging.error(f"Erro ao gerar PDF individual: {str(e)}")
            return None

    def generate_individual_answer_key(self, test_data: Dict, questions_data: List[Dict], 
                                     output_dir: str) -> Optional[str]:
        """
        Gera gabarito individual para uma prova
        
        Args:
            test_data: Dados da prova
            questions_data: Lista de questões
            output_dir: Diretório de saída
            
        Returns:
            Caminho do arquivo gerado ou None se erro
        """
        try:
            # Criar diretório se não existir
            os.makedirs(output_dir, exist_ok=True)
            
            # Nome do arquivo
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"gabarito_individual_{test_data['id']}_{timestamp}.pdf"
            filepath = os.path.join(output_dir, filename)
            
            # Gerar gabarito usando o método existente
            result = self.generate_answer_key_pdf(test_data, questions_data, output_dir)
            
            if result:
                # Renomear arquivo para individual
                if os.path.exists(result):
                    os.rename(result, filepath)
                    return filepath
            
            return None
            
        except Exception as e:
            logging.error(f"Erro ao gerar gabarito individual: {str(e)}")
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
