# -*- coding: utf-8 -*-
"""
Serviço para geração de PDFs de provas institucionais
Baseado no formato das imagens fornecidas - capa institucional, capas de disciplina e questões
"""

from PIL import Image as PILImage, ImageDraw, ImageFont
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, portrait
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle
import qrcode
import os
import io
import base64
import requests
import re
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional
import logging
import json
import uuid
from app.models.formCoordinates import FormCoordinates

class InstitutionalTestPDFGenerator:
    """
    Gerador de PDFs para provas institucionais
    Formato: Capa institucional + Capas de disciplina + Questões + Gabarito (inalterado)
    """
    
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
    
    def _setup_custom_styles(self):
        """Configura estilos personalizados para o PDF institucional"""
        
        # Estilo para título principal da capa
        self.styles.add(ParagraphStyle(
            name='InstitutionalTitle',
            parent=self.styles['Heading1'],
            fontSize=28,
            spaceAfter=20,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#1e40af'),  # Azul escuro
            fontName='Helvetica-Bold'
        ))
        
        # Estilo para subtítulo da capa
        self.styles.add(ParagraphStyle(
            name='InstitutionalSubtitle',
            parent=self.styles['Heading2'],
            fontSize=20,
            spaceAfter=30,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#1e40af'),  # Azul escuro
            fontName='Helvetica-Bold'
        ))
        
        # Estilo para caixa verde da capa
        self.styles.add(ParagraphStyle(
            name='GreenBox',
            parent=self.styles['Normal'],
            fontSize=12,
            spaceAfter=20,
            spaceBefore=20,
            alignment=TA_CENTER,
            textColor=colors.white,
            fontName='Helvetica',
            backColor=colors.HexColor('#22c55e'),  # Verde
            borderColor=colors.HexColor('#22c55e'),
            borderWidth=1,
            borderPadding=15
        ))
        
        # Estilo para informações da capa (edição, ano, etc.)
        self.styles.add(ParagraphStyle(
            name='CoverInfo',
            parent=self.styles['Normal'],
            fontSize=14,
            spaceAfter=10,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#1e40af'),
            fontName='Helvetica-Bold'
        ))
        
        # Estilo para nome do aluno
        self.styles.add(ParagraphStyle(
            name='StudentName',
            parent=self.styles['Normal'],
            fontSize=14,
            spaceAfter=20,
            alignment=TA_LEFT,
            textColor=colors.HexColor('#1e40af'),
            fontName='Helvetica-Bold'
        ))
        
        # Estilo para capa de disciplina - título do bloco
        self.styles.add(ParagraphStyle(
            name='BlockTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            spaceAfter=10,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#22c55e'),  # Verde
            fontName='Helvetica-Bold'
        ))
        
        # Estilo para capa de disciplina - nome da matéria
        self.styles.add(ParagraphStyle(
            name='SubjectTitle',
            parent=self.styles['Heading2'],
            fontSize=18,
            spaceAfter=30,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#166534'),  # Verde escuro
            fontName='Helvetica-Bold'
        ))
        
        # Estilo para instrução do octógono
        self.styles.add(ParagraphStyle(
            name='OctagonInstruction',
            parent=self.styles['Normal'],
            fontSize=14,
            spaceAfter=20,
            alignment=TA_CENTER,
            textColor=colors.white,
            fontName='Helvetica-Bold'
        ))
        
        # Estilo para instrução de tempo
        self.styles.add(ParagraphStyle(
            name='TimeInstruction',
            parent=self.styles['Normal'],
            fontSize=12,
            spaceAfter=20,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#22c55e'),
            fontName='Helvetica'
        ))
        
        # Estilo para número da questão (conforme imagem)
        self.styles.add(ParagraphStyle(
            name='QuestionNumber',
            parent=self.styles['Normal'],
            fontSize=14,
            spaceAfter=8,
            spaceBefore=20,
            alignment=TA_LEFT,
            textColor=colors.black,
            fontName='Helvetica-Bold'
        ))
        
        # Estilo para instruções da questão (conforme imagem)
        self.styles.add(ParagraphStyle(
            name='QuestionInstruction',
            parent=self.styles['Normal'],
            fontSize=12,
            spaceAfter=15,
            spaceBefore=5,
            alignment=TA_LEFT,
            textColor=colors.black,
            fontName='Helvetica'
        ))
        
        # Estilo para código da habilidade
        self.styles.add(ParagraphStyle(
            name='SkillCode',
            parent=self.styles['Normal'],
            fontSize=10,
            spaceAfter=8,
            alignment=TA_LEFT,
            textColor=colors.HexColor('#6b7280'),
            fontName='Helvetica'
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
        
        # Estilo para alternativas (conforme imagem)
        self.styles.add(ParagraphStyle(
            name='Alternative',
            parent=self.styles['Normal'],
            fontSize=12,
            spaceAfter=8,
            spaceBefore=3,
            alignment=TA_LEFT,
            textColor=colors.black,
            fontName='Helvetica'
        ))

    def generate_institutional_test_pdf(self, test_data: Dict, students_data: List[Dict], 
                                      questions_data: List[Dict], class_test_id: str = None) -> List[Dict]:
        """
        Gera PDFs de provas institucionais para todos os alunos e salva no banco de dados
        
        Args:
            test_data: Dados da prova (test_id, title, description, etc.)
            students_data: Lista de alunos com dados (id, nome, email, etc.)
            questions_data: Lista de questões ordenadas
            class_test_id: ID da aplicação da prova (ClassTest)
            
        Returns:
            Lista com informações dos PDFs gerados e salvos no banco
        """
        import io
        
        generated_files = []
        
        for student in students_data:
            try:
                # NOVO: Mapear coordenadas do formulário
                coordinates = self._map_existing_form_coordinates(questions_data)
                
                # NOVO: Gerar QR Code com metadados
                qr_data, qr_code_id = self._generate_qr_code_with_metadata(student['id'], test_data['id'])
                
                # Gerar PDF individual para cada aluno (em memória)
                pdf_data = self._generate_individual_institutional_pdf_data(
                    test_data, student, questions_data
                )
                
                if pdf_data:
                    # Retornar dados para salvamento posterior (evitar duplicação)
                    generated_files.append({
                        'student_id': student['id'],
                        'student_name': student.get('name', student.get('nome', 'Nome não informado')),
                        'pdf_data': pdf_data,  # Dados do PDF para salvamento posterior
                        'qr_code_data': json.dumps(qr_data),
                        'qr_code_id': qr_code_id,
                        'coordinates': coordinates,  # Coordenadas do formulário
                        'has_pdf_data': True,
                        'has_answer_sheet_data': False
                    })
                    
            except Exception as e:
                logging.error(f"Erro ao gerar PDF institucional para aluno {student['id']}: {str(e)}")
                continue
        
        return generated_files

    def _generate_individual_institutional_pdf_data(self, test_data: Dict, student: Dict, 
                                                  questions_data: List[Dict], class_test_id: str = None) -> Optional[bytes]:
        """
        Gera PDF individual institucional para um aluno específico em memória
        """
        try:
            import io
            
            # Criar buffer em memória
            pdf_buffer = io.BytesIO()
            
            # Criar story com todo o conteúdo
            story = []
            
            # 1. Adicionar capa institucional
            story.extend(self._create_institutional_cover(test_data, student))
            story.append(PageBreak())
            
            # 2. Organizar questões por disciplina
            questions_by_subject = self._organize_questions_by_subject(questions_data, test_data)
            
            # 3. Adicionar capa de disciplina e questões para cada disciplina
            question_counter = 1  # Contador sequencial de questões
            for block_number, (subject_name, subject_questions) in enumerate(questions_by_subject.items(), 1):
                # Capa da disciplina (usando o layout correto com octógono roxo)
                story.extend(self._create_block_cover(block_number, subject_name, 25))
                story.append(PageBreak())
                
                # Questões da disciplina com numeração sequencial
                story.extend(self._create_subject_questions_with_counter(subject_questions, question_counter))
                
                # Atualizar contador para próxima disciplina
                question_counter += len(subject_questions)
                story.append(PageBreak())
            
            # 4. Adicionar formulário de resposta usando formularios.py
            from app.formularios import gerar_formulario_com_qrcode
            from reportlab.platypus import Image as RLImage, Spacer
            from reportlab.lib.units import cm
            import io
            import tempfile
            
            try:
                # Gerar formulário de resposta
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    temp_path = tmp.name
                
                # Preparar dados do aluno
                student_data_complete = self._get_complete_student_data(student['id'])
                
                # Gerar formulário usando formularios.py
                imagem, coordenadas_respostas, coordenadas_qr = gerar_formulario_com_qrcode(
                    student['id'],
                    student.get('name', student.get('nome', 'Nome não informado')),
                    len(questions_data),
                    temp_path,
                    student_data=student_data_complete,
                    test_data=test_data
                )
                
                if imagem and coordenadas_respostas:
                    # Converter imagem para elemento ReportLab
                    img_buffer = io.BytesIO()
                    imagem.save(img_buffer, format='PNG')
                    img_buffer.seek(0)
                    
                    # Obter dimensões originais da imagem
                    original_width, original_height = imagem.size
                    
                    # Calcular proporção para manter aspecto original
                    # Usar largura máxima de 16cm para garantir que cabe na página
                    max_width_cm = 16
                    max_width_px = max_width_cm * cm
                    
                    # Calcular largura e altura proporcional
                    if original_width <= max_width_px:
                        # Imagem cabe na largura, usar tamanho original
                        display_width = original_width
                        display_height = original_height
                    else:
                        # Reduzir proporcionalmente
                        scale_factor = max_width_px / original_width
                        display_width = original_width * scale_factor
                        display_height = original_height * scale_factor
                    
                    # Verificar se a altura não excede 25cm (altura útil da página A4)
                    max_height_cm = 25
                    max_height_px = max_height_cm * cm
                    if display_height > max_height_px:
                        # Reduzir ainda mais proporcionalmente pela altura
                        height_scale_factor = max_height_px / display_height
                        display_width = display_width * height_scale_factor
                        display_height = display_height * height_scale_factor
                    
                    # Adicionar imagem ao PDF com dimensões proporcionais
                    img_element = RLImage(img_buffer, width=display_width, height=display_height)
                    img_element.hAlign = 'CENTER'
                    story.append(img_element)
                    story.append(Spacer(1, 20))
                    
                    # Limpar arquivo temporário
                    import os
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                else:
                    logging.error("Falha ao gerar formulário de resposta")
                    
            except Exception as e:
                logging.error(f"Erro ao gerar formulário de resposta: {str(e)}")
            
            # Construir PDF
            from reportlab.platypus import SimpleDocTemplate
            doc = SimpleDocTemplate(pdf_buffer, pagesize=portrait(A4))
            doc.build(story)
            
            # Retornar dados do PDF
            pdf_buffer.seek(0)
            return pdf_buffer.getvalue()
            
        except Exception as e:
            logging.error(f"Erro ao gerar PDF institucional individual em memória: {str(e)}")
            return None

    def _get_complete_student_data(self, student_id: str) -> Dict:
        """
        Busca dados completos do aluno incluindo escola, cidade, turma e série
        """
        try:
            from app.models.student import Student
            from app.models.studentClass import Class
            from app.models.school import School
            from app.models.city import City
            
            student = Student.query.get(student_id)
            if not student:
                return {
                    'student_id': student_id,
                    'student_name': 'Aluno não encontrado',
                    'class_name': 'Turma não informada',
                    'school_name': 'Escola não informada',
                    'city_name': 'Município não informado',
                    'state_name': 'Estado não informado'
                }
            
            # Buscar dados da turma
            class_name = 'Turma não informada'
            school_name = 'Escola não informada'
            city_name = 'Município não informado'
            state_name = 'Estado não informado'
            
            if student.class_id:
                student_class = Class.query.get(student.class_id)
                if student_class:
                    class_name = student_class.name or 'Turma não informada'
                    
                    # Buscar dados da escola
                    if student_class.school_id:
                        school = School.query.get(student_class.school_id)
                        if school:
                            school_name = school.name or 'Escola não informada'
                            
                            # Buscar dados da cidade
                            if school.city_id:
                                city = City.query.get(school.city_id)
                                if city:
                                    city_name = city.name or 'Município não informado'
                                    state_name = city.state or 'Estado não informado'
            
            return {
                'student_id': student.id,
                'student_name': student.name or 'Nome não informado',
                'class_name': class_name,
                'school_name': school_name,
                'city_name': city_name,
                'state_name': state_name
            }
            
        except Exception as e:
            logging.error(f"Erro ao buscar dados completos do aluno {student_id}: {str(e)}")
            return {
                'student_id': student_id,
                'student_name': 'Aluno não encontrado',
                'class_name': 'Turma não informada',
                'school_name': 'Escola não informada',
                'city_name': 'Município não informado',
                'state_name': 'Estado não informado'
            }

    def _generate_answer_key_pdf_data(self, test_data: Dict, questions_data: List[Dict]) -> Optional[bytes]:
        """
        Gera gabarito em memória
        """
        try:
            import io
            
            # Criar buffer em memória
            pdf_buffer = io.BytesIO()
            
            # Criar documento PDF
            doc = SimpleDocTemplate(pdf_buffer, pagesize=portrait(A4))
            story = []
            
            # Adicionar cabeçalho do gabarito
            story.append(Paragraph(f"<b>GABARITO - {test_data.get('title', 'Prova')}</b>", self.styles['TestTitle']))
            story.append(Spacer(1, 20))
            
            # Adicionar gabarito
            from app.services.physical_test_pdf_generator import PhysicalTestPDFGenerator
            physical_generator = PhysicalTestPDFGenerator()
            story.extend(physical_generator._create_answer_key(test_data, questions_data, None))
            
            # Construir PDF
            doc.build(story)
            
            # Retornar dados do PDF
            pdf_buffer.seek(0)
            return pdf_buffer.getvalue()
            
        except Exception as e:
            logging.error(f"Erro ao gerar gabarito em memória: {str(e)}")
            return None

    def _generate_individual_institutional_pdf(self, test_data: Dict, student: Dict, 
                                             questions_data: List[Dict], output_dir: str) -> Optional[str]:
        """
        Gera PDF individual institucional para um aluno específico
        """
        try:
            # Nome do arquivo
            student_name = student.get('name', student.get('nome', 'Nome não informado'))
            safe_name = "".join(c for c in student_name if c.isalnum() or c in (' ', '_')).rstrip().replace(" ", "_")
            filename = f"prova_institucional_{test_data['id']}_{student['id']}_{safe_name}.pdf"
            pdf_path = os.path.join(output_dir, filename)
            
            # Criar documento PDF
            doc = SimpleDocTemplate(pdf_path, pagesize=portrait(A4))
            story = []
            
            # 1. Adicionar capa institucional
            story.extend(self._create_institutional_cover(test_data, student))
            story.append(PageBreak())
            
            # 2. Organizar questões por disciplina
            questions_by_subject = self._organize_questions_by_subject(questions_data, test_data)
            
            # 3. Adicionar capa de disciplina e questões para cada disciplina
            question_counter = 1  # Contador sequencial de questões
            for block_number, (subject_name, subject_questions) in enumerate(questions_by_subject.items(), 1):
                # Capa da disciplina (usando o layout correto com octógono roxo)
                story.extend(self._create_block_cover(block_number, subject_name, 25))
                story.append(PageBreak())
                
                # Questões da disciplina com numeração sequencial
                story.extend(self._create_subject_questions_with_counter(subject_questions, question_counter))
                
                # Atualizar contador para próxima disciplina
                question_counter += len(subject_questions)
                story.append(PageBreak())
            
            # 4. Adicionar gabarito (usando o gerador existente)
            from app.services.physical_test_pdf_generator import PhysicalTestPDFGenerator
            physical_generator = PhysicalTestPDFGenerator()
            story.extend(physical_generator._create_answer_sheet(test_data, student, questions_data))
            
            # Construir PDF
            doc.build(story)
            
            return pdf_path
            
        except Exception as e:
            logging.error(f"Erro ao gerar PDF institucional individual: {str(e)}")
            return None

    def _create_institutional_cover(self, test_data: Dict, student: Dict) -> List:
        """Cria capa institucional baseada no layout da imagem de referência - TUDO EM UMA PÁGINA"""
        story = []
        
        # Buscar dados completos do aluno
        student_data = self._get_complete_student_data(student['id'])
        
        # 1. Cabeçalho - Logo do Município (separado no topo)
        story.extend(self._create_header_section())
        story.append(Spacer(1, 10))  # Reduzido de 20 para 10
        
        # 2. Logo Innov + Nome da Prova (centralizado)
        story.extend(self._create_center_section(test_data))
        story.append(Spacer(1, 8))   # Reduzido de 15 para 8
        
        # 3. Seção Amarela - Série + Disciplinas
        story.extend(self._create_yellow_middle_section(test_data))
        story.append(Spacer(1, 10))  # Reduzido de 20 para 10
        
        # 4. Rodapé - Campos do Estudante
        story.extend(self._create_footer_section(student_data))
        
        return story
    
    def _create_header_section(self) -> List:
        """Cria cabeçalho com Logo do Município separado no topo"""
        story = []
        
        # Logo do município centralizado no cabeçalho
        municipality_table = Table([['Logo do Município']], 
                                  colWidths=[18*cm], rowHeights=[2*cm])
        municipality_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, 0), colors.lightgrey),
            ('ALIGN', (0, 0), (0, 0), 'CENTER'),
            ('VALIGN', (0, 0), (0, 0), 'MIDDLE'),
            ('TEXTCOLOR', (0, 0), (0, 0), colors.black),
            ('FONTNAME', (0, 0), (0, 0), 'Helvetica'),
            ('FONTSIZE', (0, 0), (0, 0), 14),
            ('GRID', (0, 0), (0, 0), 1, colors.black),
        ]))
        
        story.append(municipality_table)
        return story
    
    def _create_center_section(self, test_data: Dict) -> List:
        """Cria seção central com logo Innov sem borda e 33% maior"""
        story = []
        
        # Logo Innov centralizado - SEM BORDA e 33% MAIOR
        try:
            logo_path = os.path.join(os.path.dirname(__file__), '..', 'assets', 'LOGO-1.png')
            if os.path.exists(logo_path):
                from reportlab.platypus import Image as RLImage
                
                # Logo reduzido para 8cm x 8cm (tamanho normal)
                logo_img = RLImage(logo_path, width=8*cm, height=8*cm)
                logo_img.hAlign = 'CENTER'
                
                story.append(logo_img)
                story.append(Spacer(1, 5))   # Reduzido de 10 para 5
            else:
                # Placeholder se logo não existir
                from reportlab.platypus import Table
                from reportlab.lib import colors
                placeholder_table = Table([['LOGO INNOV']], colWidths=[8*cm], rowHeights=[8*cm])
                placeholder_table.setStyle([
                    ('ALIGN', (0, 0), (0, 0), 'CENTER'),
                    ('VALIGN', (0, 0), (0, 0), 'MIDDLE'),
                    ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (0, 0), 28),
                    ('BACKGROUND', (0, 0), (0, 0), colors.lightgrey),
                ])
                story.append(placeholder_table)
                story.append(Spacer(1, 5))   # Reduzido de 10 para 5
                
        except Exception as e:
            logging.warning(f"Erro ao carregar logo Innov: {e}")
        
        # Nome da avaliação centralizado
        test_title = test_data.get('title', 'AVALIAÇÃO INSTITUCIONAL')
        story.append(Paragraph(f"<b>{test_title}</b>", 
                              self.styles['InstitutionalTitle']))
        
        return story
    
    
    def _create_yellow_middle_section(self, test_data: Dict) -> List:
        """Cria seção amarela com série e disciplinas"""
        story = []
        
        # Série centralizada (tamanho grande como na imagem)
        grade_name = test_data.get('grade_name', '9° ANO')
        story.append(Paragraph(f"<b>{grade_name}</b>", 
                              self.styles['InstitutionalTitle']))
        story.append(Spacer(1, 5))  # Reduzido de 8 para 5
        
        # Disciplinas (mesmo tamanho que a série)
        subjects = self._get_test_subjects_from_subjects_info(test_data)
        subjects_text = " E ".join(subjects)
        story.append(Paragraph(f"<b>{subjects_text}</b>", 
                              self.styles['InstitutionalTitle']))
        
        return story
    
    def _create_footer_section(self, student_data: Dict) -> List:
        """Cria rodapé com campos do estudante - CORRIGINDO OVERFLOW DA TURMA"""
        story = []
        
        # Dados do aluno
        student_name = student_data.get('student_name', 'Nome não informado')
        school_name = student_data.get('school_name', 'Escola não informada')
        class_name = student_data.get('class_name', 'Turma não informada')
        
        # Função para quebrar texto automaticamente
        def break_long_text(text, max_chars_per_line=25):
            """Quebra texto longo em múltiplas linhas"""
            if len(text) <= max_chars_per_line:
                return text
            
            words = text.split()
            lines = []
            current_line = ""
            
            for word in words:
                if len(current_line + word) <= max_chars_per_line:
                    if current_line:
                        current_line += " " + word
                    else:
                        current_line = word
                else:
                    if current_line:
                        lines.append(current_line)
                    current_line = word
            
            if current_line:
                lines.append(current_line)
            
            return "\n".join(lines)
        
        # Quebrar nome da escola se for muito longo
        school_name_broken = break_long_text(school_name, 25)
        
        # Campo do Estudante (linha completa) - com label e valor
        estudante_table = Table([[f'ESTUDANTE', student_name]], 
                               colWidths=[4*cm, 14*cm], rowHeights=[1.5*cm])
        estudante_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),  # Label
            ('FONTNAME', (1, 0), (1, 0), 'Helvetica'),       # Valor
            ('FONTSIZE', (0, 0), (-1, -1), 14),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),  # Bordas finas
            ('BACKGROUND', (0, 0), (0, 0), colors.lightgrey),  # Label cinza
            ('BACKGROUND', (1, 0), (1, 0), colors.white),      # Valor branco
        ]))
        
        story.append(estudante_table)
        
        # Espaçamento entre as linhas
        story.append(Spacer(1, 5))
        
        # Campo da Escola e Turma - DIMINUINDO ESPAÇO DA LINHA VERMELHA
        # Reduzindo espaço entre ESCOLA e TURMA para melhor encaixe
        # Calcular altura da linha baseada no número de linhas do texto quebrado
        num_lines = len(school_name_broken.split('\n')) if '\n' in school_name_broken else 1
        row_height = max(1.5*cm, num_lines * 0.6*cm)  # Mínimo 1.5cm, ou baseado no número de linhas
        
        escola_turma_table = Table([[f'ESCOLA', school_name_broken, '', f'TURMA', class_name]], 
                                  colWidths=[3*cm, 6.5*cm, 0.5*cm, 3*cm, 5*cm], rowHeights=[row_height])
        escola_turma_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),  # ESCOLA label
            ('FONTNAME', (1, 0), (1, 0), 'Helvetica'),       # Escola valor
            ('FONTNAME', (2, 0), (2, 0), 'Helvetica'),       # Espaço vazio
            ('FONTNAME', (3, 0), (3, 0), 'Helvetica-Bold'),  # TURMA label
            ('FONTNAME', (4, 0), (4, 0), 'Helvetica'),       # Turma valor
            ('FONTSIZE', (0, 0), (-1, -1), 14),
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),               # ESCOLA label
            ('ALIGN', (1, 0), (1, 0), 'CENTER'),             # Escola valor CENTRALIZADO
            ('ALIGN', (2, 0), (2, 0), 'LEFT'),               # Espaço vazio
            ('ALIGN', (3, 0), (3, 0), 'LEFT'),               # TURMA label
            ('ALIGN', (4, 0), (4, 0), 'CENTER'),             # Turma valor CENTRALIZADO
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (0, 0), 0.5, colors.black),  # ESCOLA label
            ('GRID', (1, 0), (1, 0), 0.5, colors.black),  # Escola valor
            ('GRID', (2, 0), (2, 0), 0, colors.white),    # Espaço sem borda
            ('GRID', (3, 0), (3, 0), 0.5, colors.black),  # TURMA label
            ('GRID', (4, 0), (4, 0), 0.5, colors.black),  # Turma valor
            ('BACKGROUND', (0, 0), (0, 0), colors.lightgrey),  # ESCOLA label cinza
            ('BACKGROUND', (1, 0), (1, 0), colors.white),      # Escola valor branco
            ('BACKGROUND', (2, 0), (2, 0), colors.white),      # Espaço branco
            ('BACKGROUND', (3, 0), (3, 0), colors.lightgrey),  # TURMA label cinza
            ('BACKGROUND', (4, 0), (4, 0), colors.white),      # Turma valor branco
        ]))
        
        story.append(escola_turma_table)
        return story
    
    def _create_block_cover(self, block_number: int, subject_name: str, time_minutes: int = 25) -> List:
        """Cria capa de bloco idêntica à imagem, mas com cor roxa"""
        story = []
        
        # Cor roxa do sistema (substituindo o verde da imagem)
        purple_color = colors.Color(0.6, 0.2, 0.8)  # Cor roxa
        dark_purple = colors.Color(0.4, 0.1, 0.6)    # Roxo escuro para borda
        
        # Criar todo o conteúdo dentro de uma única borda
        from reportlab.lib.units import cm
        from reportlab.graphics.shapes import Drawing, Polygon, String
        
        # 1. Criar octógono (MAIOR)
        octagon_drawing = Drawing(8*cm, 8*cm)
        
        # Coordenadas do octógono (centralizado)
        center_x, center_y = 4*cm, 4*cm
        radius = 3*cm  # Aumentado de 2.2cm para 3cm
        
        # Calcular pontos do octógono (8 lados)
        import math
        points = []
        for i in range(8):
            angle = i * math.pi / 4  # 45 graus entre cada ponto
            x = center_x + radius * math.cos(angle)
            y = center_y + radius * math.sin(angle)
            points.extend([x, y])
        
        # Criar octógono
        octagon = Polygon(points)
        octagon.fillColor = purple_color  # Roxo em vez de verde
        octagon.strokeColor = colors.white  # Borda branca como na imagem
        octagon.strokeWidth = 3
        octagon_drawing.add(octagon)
        
        # Adicionar texto no octógono (CENTRALIZADO UMA LINHA EMBAIXO DA OUTRA)
        text_lines = [
            String(center_x, center_y + 0.5*cm, "AGUARDE", 
                   textAnchor='middle', fontSize=14, fillColor=colors.white, fontName='Helvetica-Bold'),
            String(center_x, center_y, "INSTRUÇÕES", 
                   textAnchor='middle', fontSize=14, fillColor=colors.white, fontName='Helvetica-Bold'),
            String(center_x, center_y - 0.5*cm, "PARA VIRAR", 
                   textAnchor='middle', fontSize=14, fillColor=colors.white, fontName='Helvetica-Bold'),
            String(center_x, center_y - 1*cm, "A PÁGINA.", 
                   textAnchor='middle', fontSize=14, fillColor=colors.white, fontName='Helvetica-Bold')
        ]
        
        for text_line in text_lines:
            octagon_drawing.add(text_line)
        
        # 2. Criar octógono externo (apenas borda, sem preenchimento)
        outer_octagon_drawing = Drawing(9*cm, 9*cm)
        
        # Coordenadas do octógono externo (centralizado)
        outer_center_x, outer_center_y = 4.5*cm, 4.5*cm
        outer_radius = 3.5*cm  # Maior que o interno
        
        # Calcular pontos do octógono externo (8 lados)
        outer_points = []
        for i in range(8):
            angle = i * math.pi / 4  # 45 graus entre cada ponto
            x = outer_center_x + outer_radius * math.cos(angle)
            y = outer_center_y + outer_radius * math.sin(angle)
            outer_points.extend([x, y])
        
        # Criar octógono externo (apenas borda)
        outer_octagon = Polygon(outer_points)
        outer_octagon.fillColor = None  # Sem preenchimento
        outer_octagon.strokeColor = dark_purple  # Borda roxa
        outer_octagon.strokeWidth = 4
        outer_octagon_drawing.add(outer_octagon)
        
        # Adicionar o octógono interno dentro do externo
        # Ajustar posição do octógono interno para ficar centralizado no externo
        inner_offset_x = 0.5*cm  # Offset para centralizar
        inner_offset_y = 0.5*cm
        
        # Criar octógono interno (preenchido)
        inner_center_x = center_x + inner_offset_x
        inner_center_y = center_y + inner_offset_y
        
        inner_points = []
        for i in range(8):
            angle = i * math.pi / 4  # 45 graus entre cada ponto
            x = inner_center_x + radius * math.cos(angle)
            y = inner_center_y + radius * math.sin(angle)
            inner_points.extend([x, y])
        
        # Criar octógono interno
        inner_octagon = Polygon(inner_points)
        inner_octagon.fillColor = purple_color  # Preenchimento roxo
        inner_octagon.strokeColor = colors.white  # Borda branca
        inner_octagon.strokeWidth = 3
        outer_octagon_drawing.add(inner_octagon)
        
        # Adicionar texto no octógono interno (ajustado)
        inner_text_lines = [
            String(inner_center_x, inner_center_y + 0.5*cm, "AGUARDE", 
                   textAnchor='middle', fontSize=14, fillColor=colors.white, fontName='Helvetica-Bold'),
            String(inner_center_x, inner_center_y, "INSTRUÇÕES", 
                   textAnchor='middle', fontSize=14, fillColor=colors.white, fontName='Helvetica-Bold'),
            String(inner_center_x, inner_center_y - 0.5*cm, "PARA VIRAR", 
                   textAnchor='middle', fontSize=14, fillColor=colors.white, fontName='Helvetica-Bold'),
            String(inner_center_x, inner_center_y - 1*cm, "A PÁGINA.", 
                   textAnchor='middle', fontSize=14, fillColor=colors.white, fontName='Helvetica-Bold')
        ]
        
        for text_line in inner_text_lines:
            outer_octagon_drawing.add(text_line)
        
        # 3. Criar tabela com borda que fica em uma única página
        content_data = [
            [''],  # Espaçamento superior
            [Paragraph(f"<para align='center'><font color='purple' size='28'><b>BLOCO {block_number:02d}</b></font></para>", self.styles['Normal'])],
            [''],  # Espaçamento
            [Paragraph(f"<para align='center'><font size='20'><b>{subject_name.upper()}</b></font></para>", self.styles['Normal'])],
            [''],  # Espaçamento
            [outer_octagon_drawing],  # Octógono externo
            [''],  # Espaçamento
            [Paragraph(f"<para align='center'><font color='purple' size='16'>Você terá {time_minutes} minutos para responder a este bloco.</font></para>", self.styles['Normal'])],
            [''],  # Espaçamento para estender até o final da página
            [''],  # Mais espaçamento
        ]
        
        content_table = Table(content_data, colWidths=[16*cm])
        content_table.setStyle([
            ('BOX', (0, 0), (-1, -1), 1, dark_purple),  # Borda bem fina (1pt)
            ('BACKGROUND', (0, 0), (-1, -1), colors.white),
            ('LEFTPADDING', (0, 0), (-1, -1), 15),
            ('RIGHTPADDING', (0, 0), (-1, -1), 15),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ])
        
        story.append(content_table)
        
        return story
    
    # def _get_test_subjects(self, test_data: Dict) -> List[str]:
    #     """
    #     FUNÇÃO COMENTADA - NÃO USAR PARA ESTE CASO ESPECÍFICO
    #     Esta função usa inferência por título, mas para este caso específico
    #     devemos usar subjects_info que contém as disciplinas reais da avaliação
    #     """
    #     subjects = []
    #     
    #     # Tentar obter disciplinas do test_data
    #     if 'subjects' in test_data:
    #         subjects = test_data['subjects']
    #     elif 'subject' in test_data:
    #         subjects = [test_data['subject']]
    #     else:
    #         # Disciplinas padrão baseadas no título
    #         title = test_data.get('title', '').upper()
    #         if 'PORTUGUÊS' in title or 'LÍNGUA' in title:
    #             subjects.append('LÍNGUA PORTUGUESA')
    #         if 'MATEMÁTICA' in title:
    #             subjects.append('MATEMÁTICA')
    #         if 'CIÊNCIAS' in title:
    #             subjects.append('CIÊNCIAS')
    #         if 'HISTÓRIA' in title:
    #             subjects.append('HISTÓRIA')
    #         if 'GEOGRAFIA' in title:
    #             subjects.append('GEOGRAFIA')
    #     
    #     # Se não encontrou disciplinas, usar padrão
    #     if not subjects:
    #         subjects = ['LÍNGUA PORTUGUESA', 'MATEMÁTICA']
    #     
    #     return subjects
    
    def _get_test_subjects_from_subjects_info(self, test_data: Dict) -> List[str]:
        """Extrai disciplinas da prova usando subjects_info (CORRETO PARA ESTE CASO)"""
        subjects = []
        
        # Obter disciplinas do test_data.subjects_info
        subjects_info = test_data.get('subjects_info', [])
        
        if not subjects_info:
            logging.warning("subjects_info não encontrado no test_data - usando fallback")
            # FALLBACK: Se não tem subjects_info, tentar inferir do título
            title = test_data.get('title', '').upper()
            if 'PORTUGUÊS' in title or 'LÍNGUA' in title:
                subjects.append('LÍNGUA PORTUGUESA')
            if 'MATEMÁTICA' in title:
                subjects.append('MATEMÁTICA')
            if 'CIÊNCIAS' in title:
                subjects.append('CIÊNCIAS')
            if 'HISTÓRIA' in title:
                subjects.append('HISTÓRIA')
            if 'GEOGRAFIA' in title:
                subjects.append('GEOGRAFIA')
            
            # Se ainda não encontrou, usar padrão
            if not subjects:
                subjects = ['LÍNGUA PORTUGUESA', 'MATEMÁTICA']
            
            return subjects
        
        # Extrair nomes das disciplinas
        for subject_info in subjects_info:
            if isinstance(subject_info, dict) and 'name' in subject_info:
                subjects.append(subject_info['name'])
            elif isinstance(subject_info, str):
                # Se for apenas string (ID), buscar no banco
                from app.models.subject import Subject
                subject_obj = Subject.query.get(subject_info)
                if subject_obj:
                    subjects.append(subject_obj.name)
                else:
                    logging.warning(f"Disciplina com ID {subject_info} não encontrada no banco")
                    subjects.append(subject_info)  # Usar ID como fallback
        
        return subjects

    def _get_test_info_boxes(self, test_data: Dict) -> List[Dict]:
        """Extrai informações da avaliação para as caixas ovais"""
        info_boxes = []
        
        # Ano/série (do grade ou test_data)
        grade_name = test_data.get('grade_name', '9° ANO')
        info_boxes.append({'text': grade_name, 'label': 'Série'})
        
        # Ano atual
        current_year = datetime.now().year
        info_boxes.append({'text': str(current_year), 'label': 'Ano'})
        
        return info_boxes

    def _create_info_boxes(self, info_data: List[Dict], test_data: Dict) -> List:
        """Cria as caixas ovais com informações"""
        story = []
        
        # Criar tabela com as caixas
        box_data = []
        for info in info_data:
            box_data.append([info['text']])
        
        if box_data:
            info_table = Table(box_data, colWidths=[120] * len(box_data))
            info_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 12),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#1e40af')),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                ('TOPPADDING', (0, 0), (-1, -1), 10),
                ('LEFTPADDING', (0, 0), (-1, -1), 15),
                ('RIGHTPADDING', (0, 0), (-1, -1), 15),
                ('BOX', (0, 0), (-1, -1), 2, colors.HexColor('#1e40af')),
                ('BACKGROUND', (0, 0), (-1, -1), colors.white),
            ]))
            story.append(info_table)
        
        # Adicionar dados dinâmicos da educação
        story.append(Spacer(1, 10))
        
        # Buscar dados dinâmicos do test_data
        education_stage_name = test_data.get('education_stage_name', 'ENSINO FUNDAMENTAL')
        course_name = test_data.get('course_name', 'ANOS FINAIS')
        
        story.append(Paragraph(education_stage_name.upper(), self.styles['CoverInfo']))
        story.append(Spacer(1, 5))
        story.append(Paragraph(course_name.upper(), self.styles['CoverInfo']))
        
        return story

    def _organize_questions_by_subject(self, questions_data: List[Dict], test_data: Dict) -> Dict[str, List[Dict]]:
        """Organiza questões por disciplina mantendo a ordem original do campo 'order'"""
        questions_by_subject = {}
        
        # Obter disciplinas do test_data.subjects_info
        subjects_info = test_data.get('subjects_info', [])
        
        if not subjects_info:
            logging.warning("subjects_info não encontrado no test_data - usando fallback")
            # FALLBACK: Se não tem subjects_info, agrupar todas as questões em uma disciplina
            questions_by_subject['Geral'] = questions_data
            return questions_by_subject
        
        # Criar mapeamento de subject_id para nome da disciplina
        subject_id_to_name = {}
        for subject_info in subjects_info:
            if isinstance(subject_info, dict) and 'id' in subject_info and 'name' in subject_info:
                subject_id_to_name[subject_info['id']] = subject_info['name']
            elif isinstance(subject_info, str):
                # Se for apenas string (ID), buscar no banco
                from app.models.subject import Subject
                subject_obj = Subject.query.get(subject_info)
                if subject_obj:
                    subject_id_to_name[subject_info] = subject_obj.name
                else:
                    logging.warning(f"Disciplina com ID {subject_info} não encontrada no banco")
                    subject_id_to_name[subject_info] = subject_info  # Usar ID como fallback
        
        # Agrupar questões por disciplina mantendo a ordem original
        # As questões já vêm ordenadas pelo campo 'order' da tabela TestQuestion
        for question in questions_data:
            subject_id = question.get('subject_id')
            
            if not subject_id:
                logging.warning(f"Questão {question.get('id', 'unknown')} não tem subject_id - colocando em 'Geral'")
                if 'Geral' not in questions_by_subject:
                    questions_by_subject['Geral'] = []
                questions_by_subject['Geral'].append(question)
                continue
            
            # Obter nome da disciplina
            subject_name = subject_id_to_name.get(subject_id)
            if not subject_name:
                logging.warning(f"Disciplina com ID {subject_id} não encontrada em subjects_info - colocando em 'Geral'")
                if 'Geral' not in questions_by_subject:
                    questions_by_subject['Geral'] = []
                questions_by_subject['Geral'].append(question)
                continue
            
            # Adicionar questão ao grupo da disciplina (mantendo ordem original)
            if subject_name not in questions_by_subject:
                questions_by_subject[subject_name] = []
            questions_by_subject[subject_name].append(question)
        
        return questions_by_subject

    # def _create_subject_cover(self, subject_name: str, num_questions: int, block_number: int = 1) -> List:
    #     """Cria capa de disciplina baseada na imagem 2"""
    #     story = []
        
    #     # Borda verde ao redor da página
    #     story.append(Paragraph("", self.styles['Normal']))  # Placeholder para borda
        
    #     # Título do bloco
    #     story.append(Paragraph(f"BLOCO {block_number:02d}", self.styles['BlockTitle']))
    #     story.append(Spacer(1, 10))
        
    #     # Nome da matéria
    #     story.append(Paragraph(subject_name.upper(), self.styles['SubjectTitle']))
    #     story.append(Spacer(1, 50))
        
    #     # Octógono com instrução
    #     octagon_instruction = "AGUARDE INSTRUÇÕES PARA VIRAR A PÁGINA."
    #     story.append(Paragraph(octagon_instruction, self.styles['OctagonInstruction']))
    #     story.append(Spacer(1, 30))
        
    #     # Instrução de tempo
    #     time_instruction = f"Você terá 25 minutos para responder a este bloco."
    #     story.append(Paragraph(time_instruction, self.styles['TimeInstruction']))
    #     story.append(Spacer(1, 100))
        
    #     # Logo SEMED
    #     story.append(Paragraph("SEMED", self.styles['CoverInfo']))
    #     story.append(Paragraph("Secretaria Municipal de Educação", self.styles['Normal']))
        
    #     return story

    def _create_subject_questions(self, questions: List[Dict]) -> List:
        """Cria páginas com questões da disciplina (MÉTODO ANTIGO - NÃO USAR)"""
        story = []
        
        for i, question in enumerate(questions, 1):
            story.extend(self._create_single_question(question, i))
            story.append(Spacer(1, 20))
        
        return story
    
    def _create_subject_questions_with_counter(self, questions: List[Dict], start_counter: int) -> List:
        """Cria páginas com questões da disciplina com numeração sequencial"""
        story = []
        
        for i, question in enumerate(questions):
            question_number = start_counter + i  # Usar contador sequencial
            story.extend(self._create_single_question(question, question_number))
            story.append(Spacer(1, 20))
        
        return story

    def _create_single_question(self, question: Dict, question_number: int) -> List:
        """Cria uma questão individual conforme layout das imagens"""
        story = []
        
        # Título da questão com traços (conforme imagem)
        skill_code = self._get_skill_code(question)
        if skill_code:
            title_text = f"QUESTÃO {question_number} - ({skill_code}) "
        else:
            title_text = f"QUESTÃO {question_number} - (Código não informado) "
        
        # Adicionar traços para completar a linha
        dashes = "-" * (50 - len(title_text))
        story.append(Paragraph(f"{title_text}{dashes}", self.styles['QuestionNumber']))
        
        # Texto de instrução (conforme imagem)
        instruction_text = self._get_question_instruction(question)
        if instruction_text:
            story.append(Paragraph(instruction_text, self.styles['QuestionInstruction']))
        
        # Texto da questão
        question_text = question.get('formatted_text', question.get('text', ''))
        if question_text:
            # Processar HTML e imagens
            story.extend(self._process_question_content(question_text))
        
        # Segundo enunciado (se houver)
        second_statement = question.get('secondstatement', '')
        if second_statement:
            story.extend(self._process_question_content(second_statement))
        
        # Alternativas
        alternatives = question.get('alternatives', [])
        if alternatives:
            story.append(Spacer(1, 15))  # Espaçamento antes das alternativas
            for alt in alternatives:
                letter = alt.get('id', '')
                text = alt.get('text', '')
                story.append(Paragraph(f"{letter}) {text}", self.styles['Alternative']))
        
        return story

    def _get_skill_code(self, question: Dict) -> Optional[str]:
        """Extrai código da habilidade da questão buscando no banco"""
        try:
            skill_id = question.get('skill')
            if not skill_id:
                return None
            
            # Buscar a habilidade no banco usando o ID
            from app.models.skill import Skill
            skill_obj = Skill.query.get(skill_id)
            if skill_obj and skill_obj.code:
                return skill_obj.code
            
            return None
        except Exception as e:
            logging.warning(f"Erro ao buscar código da habilidade: {str(e)}")
            return None
    
    def _get_question_instruction(self, question: Dict) -> Optional[str]:
        """Extrai texto de instrução da questão (conforme imagem)"""
        # Baseado nas imagens, as instruções são:
        # Imagem 1: "Leia e observe o texto abaixo para responder à questão."
        # Imagem 2: "Leia o poema de Cruz e Souza e responda."
        
        # Por enquanto, usar instrução padrão baseada no tipo de conteúdo
        question_text = question.get('formatted_text', question.get('text', ''))
        
        if 'poema' in question_text.lower() or 'poetry' in question_text.lower():
            return "Leia o poema e responda."
        elif 'texto' in question_text.lower() or 'text' in question_text.lower():
            return "Leia e observe o texto abaixo para responder à questão."
        else:
            return "Leia e observe o texto abaixo para responder à questão."

    def _process_question_content(self, content: str) -> List:
        """Processa conteúdo da questão (HTML e imagens)"""
        story = []
        
        if not content.strip():
            return story
        
        # Dividir por tags de imagem
        parts = re.split(r'<img[^>]*src=["\']([^"\']*)["\'][^>]*>', content)
        
        for i, part in enumerate(parts):
            if i % 2 == 0:
                # Texto HTML
                if part.strip():
                    clean_html = self._clean_html_for_reportlab(part.strip())
                    story.extend(self._convert_html_to_reportlab(clean_html, self.styles['QuestionText']))
            else:
                # URL da imagem
                if part.strip():
                    img = self._process_image_from_text(part)
                    if img:
                        img.hAlign = 'CENTER'
                        story.append(img)
        
        return story

    def _clean_html_for_reportlab(self, html_text: str) -> str:
        """Limpa HTML para ser compatível com ReportLab"""
        if not html_text or not html_text.strip():
            return html_text
            
        clean_text = html_text
        
        # Remover tags complexas
        clean_text = re.sub(r'<span[^>]*>', '', clean_text)
        clean_text = re.sub(r'</span>', '', clean_text)
        clean_text = re.sub(r'<div[^>]*>', '', clean_text)
        clean_text = re.sub(r'</div>', '', clean_text)
        
        # Remover atributos
        clean_text = re.sub(r'\s+class=["\'][^"\']*["\']', '', clean_text)
        clean_text = re.sub(r'\s+style=["\'][^"\']*["\']', '', clean_text)
        
        # Converter <br> para <br/>
        clean_text = re.sub(r'<br\s*/?>', '<br/>', clean_text)
        
        # Limpar espaços extras
        clean_text = re.sub(r'\s+', ' ', clean_text)
        clean_text = clean_text.strip()
        
        return clean_text

    def _convert_html_to_reportlab(self, html_text: str, base_style) -> List:
        """Converte HTML para elementos ReportLab"""
        story = []
        
        if not html_text.strip():
            return story
        
        # Processar formatação básica
        formatted_text = html_text
        
        # Converter negrito
        formatted_text = re.sub(r'<strong[^>]*>(.*?)</strong>', r'<font name="Helvetica-Bold">\1</font>', formatted_text)
        formatted_text = re.sub(r'<b[^>]*>(.*?)</b>', r'<font name="Helvetica-Bold">\1</font>', formatted_text)
        
        # Converter itálico
        formatted_text = re.sub(r'<em[^>]*>(.*?)</em>', r'<font name="Helvetica-Oblique">\1</font>', formatted_text)
        formatted_text = re.sub(r'<i[^>]*>(.*?)</i>', r'<font name="Helvetica-Oblique">\1</font>', formatted_text)
        
        # Dividir por parágrafos
        paragraphs = re.split(r'</?p[^>]*>', formatted_text)
        
        for para_text in paragraphs:
            if para_text.strip():
                story.append(Paragraph(para_text.strip(), base_style))
                story.append(Spacer(1, 6))
        
        return story

    def _process_image_from_text(self, text: str) -> Optional[RLImage]:
        """Processa imagem de URL ou Base64"""
        try:
            import base64
            import requests
            from io import BytesIO
            
            # Verificar se é Base64
            if text.startswith('data:image'):
                header, data = text.split(',', 1)
                image_data = base64.b64decode(data)
                img_buffer = BytesIO(image_data)
                return RLImage(img_buffer, width=200, height=150)
            
            # Verificar se é URL
            elif text.startswith('http'):
                response = requests.get(text, timeout=10)
                if response.status_code == 200:
                    img_buffer = BytesIO(response.content)
                    return RLImage(img_buffer, width=200, height=150)
            
            return None
            
        except Exception as e:
            logging.error(f"Erro ao processar imagem: {str(e)}")
            return None
    
    def _map_existing_form_coordinates(self, questions_data: List[Dict]) -> Dict:
        """
        Mapeia coordenadas do layout atual do formulário
        Mantém o layout existente e apenas mapeia as posições
        """
        try:
            coordinates = {
                "subjects": {},
                "qr_code": {
                    "x": 10, "y": 100, "width": 100, "height": 100
                }
            }
            
            # Mapear questões por disciplina usando o método correto
            subjects = {}
            for question in questions_data:
                subject_id = question.get('subject_id')
                if subject_id:
                    # Buscar nome da disciplina no banco
                    from app.models.subject import Subject
                    subject_obj = Subject.query.get(subject_id)
                    if subject_obj:
                        subject_name = subject_obj.name
                        if subject_name not in subjects:
                            subjects[subject_name] = []
                        subjects[subject_name].append(question)
                    else:
                        # Fallback para "Geral" se não encontrar disciplina
                        if 'Geral' not in subjects:
                            subjects['Geral'] = []
                        subjects['Geral'].append(question)
                else:
                    # Questão sem disciplina, colocar em "Geral"
                    if 'Geral' not in subjects:
                        subjects['Geral'] = []
                    subjects['Geral'].append(question)
            
            for subject_name, subject_questions in subjects.items():
                subject_key = subject_name.lower().replace(' ', '_')
                coordinates["subjects"][subject_key] = {}
                
                for i, question in enumerate(subject_questions):
                    question_key = f"question_{i+1}"
                    coordinates["subjects"][subject_key][question_key] = {}
                    
                    # Mapear coordenadas baseadas no layout atual
                    alternatives = question.get('alternatives', [])
                    for j, alt in enumerate(alternatives):
                        alt_id = alt.get('id', chr(65 + j))  # A, B, C, D como fallback
                        x, y, radius = self._get_coordinate_from_layout(
                            subject_name, i, j, len(alternatives)
                        )
                        
                        coordinates["subjects"][subject_key][question_key][alt_id] = {
                            "x": x, "y": y, "radius": radius
                        }
            
            return coordinates
            
        except Exception as e:
            logging.error(f"Erro ao mapear coordenadas: {str(e)}")
            return {}
    
    # def _group_questions_by_subject(self, questions_data: List[Dict]) -> Dict:
    #     """
    #     FUNÇÃO COMENTADA - NÃO USAR PARA ESTE CASO ESPECÍFICO
    #     Esta função usa question.get('subject', {}).get('name', 'Outras')
    #     mas para este caso específico devemos usar _organize_questions_by_subject
    #     que usa subjects_info e subject_id
    #     """
    #     try:
    #         subjects = {}
    #         
    #         for question in questions_data:
    #             subject_name = question.get('subject', {}).get('name', 'Outras')
    #             
    #             if subject_name not in subjects:
    #                 subjects[subject_name] = []
    #             
    #             subjects[subject_name].append(question)
    #         
    #         return subjects
    #         
    #     except Exception as e:
    #         logging.error(f"Erro ao agrupar questões por disciplina: {str(e)}")
    #         return {}
    
    def _get_coordinate_from_layout(self, subject_name: str, question_index: int, alt_index: int, total_alts: int) -> Tuple[int, int, int]:
        """
        Obtém coordenadas baseadas no layout real do formulário
        Usa coordenadas EXATAS do projeto.py que são testadas e funcionam
        """
        try:
            # Coordenadas EXATAS do arquivo projeto.py que funcionam
            # Estas são as coordenadas que realmente detectam as respostas na imagem
            
            # NOTA: Esta implementação está INCORRETA - coordenadas do projeto.py são para 5 alternativas
            # O sistema correto usa as coordenadas do formularios.py: [112, 162, 212, 262] x [950, 995, 1040, 1085]
            # Esta função não é mais usada - o sistema usa gerar_formulario_com_qrcode do formularios.py
            if subject_name.lower() == "português":
                # Coluna esquerda (Português) - coordenadas EXATAS do projeto.py (INCORRETAS PARA 4 ALTERNATIVAS)
                base_x = 198
                base_y = 14
            else:
                # Coluna direita (Matemática) - coordenadas EXATAS do projeto.py (INCORRETAS PARA 4 ALTERNATIVAS)
                base_x = 479
                base_y = 14
            
            # Calcular posição da questão (28px entre questões)
            question_y = base_y + (question_index * 28)
            
            # Calcular posição da alternativa (40px entre alternativas)
            alt_x = base_x + (alt_index * 40)
            
            # Raio fixo baseado no projeto.py (20x20 = raio 10)
            # Mas vamos usar o tamanho exato do projeto.py: 20x20
            radius = 10  # Raio do círculo interno
            width = 20   # Largura da região
            height = 20  # Altura da região
            
            return int(alt_x), int(question_y), radius
            
        except Exception as e:
            logging.error(f"Erro ao calcular coordenada: {str(e)}")
            return 0, 0, 10
    
    def _generate_qr_code_with_metadata(self, student_id: str, test_id: str) -> Tuple[Dict, str]:
        """
        Gera QR Code com metadados para identificação
        """
        try:
            qr_code_id = str(uuid.uuid4())
            qr_data = {
                "student_id": student_id,
                "qr_code_id": qr_code_id,
                "test_id": test_id
            }
            
            # Gerar QR Code
            qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L)
            qr.add_data(json.dumps(qr_data))
            qr.make(fit=True)
            
            return qr_data, qr_code_id
            
        except Exception as e:
            logging.error(f"Erro ao gerar QR Code: {str(e)}")
            return {}, ""
    
    def _save_form_coordinates(self, test_id: str, qr_code_id: str, student_id: str, coordinates: Dict) -> bool:
        """
        Salva coordenadas no banco de dados
        """
        try:
            from app import db
            
            form_coords = FormCoordinates(
                test_id=test_id,
                qr_code_id=qr_code_id,
                student_id=student_id,
                coordinates=coordinates
            )
            
            db.session.add(form_coords)
            db.session.commit()
            
            logging.info(f"Coordenadas salvas para teste {test_id}, aluno {student_id}")
            return True
            
        except Exception as e:
            logging.error(f"Erro ao salvar coordenadas: {str(e)}")
            db.session.rollback()
            return False
    
    def _create_formulario_style_form(self, student_name: str, student_id: str, num_questoes: int) -> tuple:
        """
        NOTA: Esta função está OBSOLETA - não é mais usada pelo sistema
        O sistema correto usa diretamente gerar_formulario_com_qrcode do formularios.py
        através do physical_test_pdf_generator.py
        
        Cria formulário usando EXATAMENTE o formularios.py
        Retorna: (imagem_pil, coordenadas_respostas, coordenadas_qr)
        """
        try:
            # Importar e usar diretamente as funções do formularios.py
            import sys
            import os
            sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
            
            from app.formularios import gerar_formulario_com_qrcode
            
            # Temporariamente modificar ALTERNATIVAS para 4 alternativas
            import app.formularios as formularios_module
            original_alternativas = formularios_module.ALTERNATIVAS
            formularios_module.ALTERNATIVAS = ["A", "B", "C", "D"]  # Apenas 4 alternativas
            
            try:
                # Usar a função original do formularios.py
                imagem, coordenadas_respostas, coordenadas_qr = gerar_formulario_com_qrcode(
                    student_id, 
                    student_name, 
                    num_questoes, 
                    "temp_form.png"  # Arquivo temporário
                )
                
                # Limpar arquivo temporário
                if os.path.exists("temp_form.png"):
                    os.remove("temp_form.png")
                
                return imagem, coordenadas_respostas, coordenadas_qr
                
            finally:
                # Restaurar ALTERNATIVAS original
                formularios_module.ALTERNATIVAS = original_alternativas
            
        except Exception as e:
            logging.error(f"Erro ao criar formulário usando formularios.py: {str(e)}")
            return None, None, None
    
