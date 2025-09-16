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
        
        # Estilo para número da questão
        self.styles.add(ParagraphStyle(
            name='QuestionNumber',
            parent=self.styles['Normal'],
            fontSize=16,
            spaceAfter=8,
            spaceBefore=20,
            alignment=TA_LEFT,
            textColor=colors.HexColor('#1f2937'),
            fontName='Helvetica-Bold'
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
        from app.models.physicalTestForm import PhysicalTestForm
        from app import db
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
                    # Salvar no banco de dados
                    physical_form = PhysicalTestForm(
                        test_id=test_data['id'],
                        student_id=student['id'],
                        class_test_id=class_test_id or 'default',
                        form_pdf_data=pdf_data,
                        answer_sheet_data=None,  # Gabarito do professor não deve ser salvo aqui
                        qr_code_data=json.dumps(qr_data),  # NOVO: QR Code com metadados
                        status='gerado'
                    )
                    
                    db.session.add(physical_form)
                    db.session.commit()
                    
                    # NOVO: Salvar coordenadas no banco
                    coordinates_saved = self._save_form_coordinates(
                        test_data['id'], qr_code_id, student['id'], coordinates
                    )
                    
                    generated_files.append({
                        'student_id': student['id'],
                        'student_name': student['nome'],
                        'form_id': physical_form.id,
                        'qr_code_data': json.dumps(qr_data),
                        'qr_code_id': qr_code_id,  # NOVO: ID do QR Code
                        'coordinates_saved': coordinates_saved,  # NOVO: Status das coordenadas
                        'has_pdf_data': True,
                        'has_answer_sheet_data': False  # Não salvamos gabarito do professor aqui
                    })
                    
            except Exception as e:
                logging.error(f"Erro ao gerar PDF institucional para aluno {student['id']}: {str(e)}")
                db.session.rollback()
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
            questions_by_subject = self._organize_questions_by_subject(questions_data)
            
            # 3. Adicionar capa de disciplina e questões para cada disciplina
            for block_number, (subject_name, subject_questions) in enumerate(questions_by_subject.items(), 1):
                # Capa da disciplina
                story.extend(self._create_subject_cover(subject_name, len(subject_questions), block_number))
                story.append(PageBreak())
                
                # Questões da disciplina
                story.extend(self._create_subject_questions(subject_questions))
                story.append(PageBreak())
            
            # 4. Adicionar gabarito (usando o gerador existente com frame maior)
            from app.services.physical_test_pdf_generator import PhysicalTestPDFGenerator
            physical_generator = PhysicalTestPDFGenerator()
            story.extend(physical_generator._create_answer_sheet(test_data, student, questions_data))
            
            # Construir PDF com frame maior (margens de 1cm)
            success = physical_generator.create_pdf_with_large_frame(pdf_buffer, story)
            if not success:
                logging.error("Erro ao criar PDF com frame maior")
                return None
            
            # Retornar dados do PDF
            pdf_buffer.seek(0)
            return pdf_buffer.getvalue()
            
        except Exception as e:
            logging.error(f"Erro ao gerar PDF institucional individual em memória: {str(e)}")
            return None

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
            safe_name = "".join(c for c in student['nome'] if c.isalnum() or c in (' ', '_')).rstrip().replace(" ", "_")
            filename = f"prova_institucional_{test_data['id']}_{student['id']}_{safe_name}.pdf"
            pdf_path = os.path.join(output_dir, filename)
            
            # Criar documento PDF
            doc = SimpleDocTemplate(pdf_path, pagesize=portrait(A4))
            story = []
            
            # 1. Adicionar capa institucional
            story.extend(self._create_institutional_cover(test_data, student))
            story.append(PageBreak())
            
            # 2. Organizar questões por disciplina
            questions_by_subject = self._organize_questions_by_subject(questions_data)
            
            # 3. Adicionar capa de disciplina e questões para cada disciplina
            for block_number, (subject_name, subject_questions) in enumerate(questions_by_subject.items(), 1):
                # Capa da disciplina
                story.extend(self._create_subject_cover(subject_name, len(subject_questions), block_number))
                story.append(PageBreak())
                
                # Questões da disciplina
                story.extend(self._create_subject_questions(subject_questions))
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
        """Cria capa institucional baseada na imagem 1"""
        story = []
        
        # Logo placeholder (será enviado pelo frontend)
        story.append(Paragraph("LOGO SASMIC", self.styles['InstitutionalTitle']))
        story.append(Spacer(1, 20))
        
        # Caixa verde com mensagem
        message = """
        Caro (a) aluno (a)<br/>
        A SEMED quer melhorar o ensino no município.<br/>
        Você pode ajudar respondendo a esta prova.<br/>
        Sua participação é muito importante.<br/>
        Obrigado!
        """
        story.append(Paragraph(message, self.styles['GreenBox']))
        story.append(Spacer(1, 20))
        
        # Título da avaliação (dinâmico)
        test_title = test_data.get('title', 'AVALIAÇÃO INSTITUCIONAL')
        story.append(Paragraph(test_title, self.styles['InstitutionalTitle']))
        story.append(Spacer(1, 10))
        
        # Subtítulo
        story.append(Spacer(1, 30))
        
        # Espaço para ilustração (placeholder)
        story.append(Spacer(1, 100))
        
        # Caixas ovais com informações da avaliação
        info_data = self._get_test_info_boxes(test_data)
        story.extend(self._create_info_boxes(info_data, test_data))
        story.append(Spacer(1, 20))
        
        # Nome do aluno
        student_name = student.get('nome', 'Nome não informado')
        story.append(Paragraph(f"NOME: {student_name}", self.styles['StudentName']))
        story.append(Spacer(1, 20))
        
        # Caderno
        story.append(Paragraph("CADERNO 1", self.styles['CoverInfo']))
        story.append(Spacer(1, 30))
        
        # Logo SEMED
        story.append(Paragraph("SEMED", self.styles['CoverInfo']))
        story.append(Paragraph("Secretaria Municipal de Educação", self.styles['Normal']))
        
        return story

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

    def _organize_questions_by_subject(self, questions_data: List[Dict]) -> Dict[str, List[Dict]]:
        """Organiza questões por disciplina"""
        questions_by_subject = {}
        
        for question in questions_data:
            # Tentar obter nome da disciplina
            subject_name = "Geral"  # Padrão
            
            if question.get('subject'):
                if isinstance(question['subject'], dict):
                    subject_name = question['subject'].get('name', 'Geral')
                else:
                    subject_name = str(question['subject'])
            
            if subject_name not in questions_by_subject:
                questions_by_subject[subject_name] = []
            
            questions_by_subject[subject_name].append(question)
        
        return questions_by_subject

    def _create_subject_cover(self, subject_name: str, num_questions: int, block_number: int = 1) -> List:
        """Cria capa de disciplina baseada na imagem 2"""
        story = []
        
        # Borda verde ao redor da página
        story.append(Paragraph("", self.styles['Normal']))  # Placeholder para borda
        
        # Título do bloco
        story.append(Paragraph(f"BLOCO {block_number:02d}", self.styles['BlockTitle']))
        story.append(Spacer(1, 10))
        
        # Nome da matéria
        story.append(Paragraph(subject_name.upper(), self.styles['SubjectTitle']))
        story.append(Spacer(1, 50))
        
        # Octógono com instrução
        octagon_instruction = "AGUARDE INSTRUÇÕES PARA VIRAR A PÁGINA."
        story.append(Paragraph(octagon_instruction, self.styles['OctagonInstruction']))
        story.append(Spacer(1, 30))
        
        # Instrução de tempo
        time_instruction = f"Você terá 25 minutos para responder a este bloco."
        story.append(Paragraph(time_instruction, self.styles['TimeInstruction']))
        story.append(Spacer(1, 100))
        
        # Logo SEMED
        story.append(Paragraph("SEMED", self.styles['CoverInfo']))
        story.append(Paragraph("Secretaria Municipal de Educação", self.styles['Normal']))
        
        return story

    def _create_subject_questions(self, questions: List[Dict]) -> List:
        """Cria páginas com questões da disciplina"""
        story = []
        
        for i, question in enumerate(questions, 1):
            story.extend(self._create_single_question(question, i))
            story.append(Spacer(1, 20))
        
        return story

    def _create_single_question(self, question: Dict, question_number: int) -> List:
        """Cria uma questão individual"""
        story = []
        
        # Número da questão e código da habilidade
        skill_code = self._get_skill_code(question)
        if skill_code:
            story.append(Paragraph(f"QUESTÃO {question_number} - {skill_code}", self.styles['QuestionNumber']))
        else:
            story.append(Paragraph(f"QUESTÃO {question_number}", self.styles['QuestionNumber']))
        
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
            story.append(Spacer(1, 10))
            for alt in alternatives:
                letter = alt.get('id', '')
                text = alt.get('text', '')
                story.append(Paragraph(f"{letter}) {text}", self.styles['Alternative']))
        
        return story

    def _get_skill_code(self, question: Dict) -> Optional[str]:
        """Extrai código da habilidade da questão"""
        try:
            skills = question.get('skills', [])
            if skills and len(skills) > 0:
                # Retornar o primeiro código de habilidade
                return str(skills[0])
            return None
        except:
            return None

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
            
            # Mapear questões por disciplina
            subjects = self._group_questions_by_subject(questions_data)
            
            for subject_name, subject_questions in subjects.items():
                subject_key = subject_name.lower().replace(' ', '_')
                coordinates["subjects"][subject_key] = {}
                
                for i, question in enumerate(subject_questions):
                    question_key = f"question_{i+1}"
                    coordinates["subjects"][subject_key][question_key] = {}
                    
                    # Mapear coordenadas baseadas no layout atual
                    for j, alt_id in enumerate(question['alternative_ids']):
                        x, y, radius = self._get_coordinate_from_layout(
                            subject_name, i, j, len(question['alternative_ids'])
                        )
                        
                        coordinates["subjects"][subject_key][question_key][alt_id] = {
                            "x": x, "y": y, "radius": radius
                        }
            
            return coordinates
            
        except Exception as e:
            logging.error(f"Erro ao mapear coordenadas: {str(e)}")
            return {}
    
    def _group_questions_by_subject(self, questions_data: List[Dict]) -> Dict:
        """
        Agrupa questões por disciplina
        """
        try:
            subjects = {}
            
            for question in questions_data:
                subject_name = question.get('subject', {}).get('name', 'Outras')
                
                if subject_name not in subjects:
                    subjects[subject_name] = []
                
                subjects[subject_name].append(question)
            
            return subjects
            
        except Exception as e:
            logging.error(f"Erro ao agrupar questões por disciplina: {str(e)}")
            return {}
    
    def _get_coordinate_from_layout(self, subject_name: str, question_index: int, alt_index: int, total_alts: int) -> Tuple[int, int, int]:
        """
        Obtém coordenadas baseadas no layout real do formulário
        Usa coordenadas EXATAS do projeto.py que são testadas e funcionam
        """
        try:
            # Coordenadas EXATAS do arquivo projeto.py que funcionam
            # Estas são as coordenadas que realmente detectam as respostas na imagem
            
            if subject_name.lower() == "português":
                # Coluna esquerda (Português) - coordenadas EXATAS do projeto.py
                base_x = 198
                base_y = 14
            else:
                # Coluna direita (Matemática) - coordenadas EXATAS do projeto.py  
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
    
