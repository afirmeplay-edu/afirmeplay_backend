# -*- coding: utf-8 -*-
"""
Serviço de gerenciamento de certificados
"""
from app import db
from app.certification.models import CertificateTemplate, Certificate
from app.models.evaluationResult import EvaluationResult
from app.models.student import Student
from app.models.test import Test
from app.models.studentClass import Class
from sqlalchemy.exc import SQLAlchemyError
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class CertificateService:
    """Serviço para operações de certificados"""
    
    @staticmethod
    def get_template_by_evaluation(evaluation_id: str) -> Optional[CertificateTemplate]:
        """
        Busca template de certificado por evaluation_id
        
        Args:
            evaluation_id: ID da avaliação (test_id)
            
        Returns:
            CertificateTemplate ou None se não encontrado
        """
        try:
            return CertificateTemplate.query.filter_by(evaluation_id=evaluation_id).first()
        except SQLAlchemyError as e:
            logger.error(f"Erro ao buscar template: {str(e)}")
            raise
    
    @staticmethod
    def save_template(template_data: dict) -> CertificateTemplate:
        """
        Salva ou atualiza template de certificado
        
        Args:
            template_data: Dicionário com dados do template
            
        Returns:
            CertificateTemplate salvo/atualizado
        """
        try:
            template_id = template_data.get('id')
            
            if template_id:
                # Atualizar template existente
                template = CertificateTemplate.query.get(template_id)
                if not template:
                    raise ValueError(f"Template não encontrado: {template_id}")
            else:
                # Criar novo template
                template = CertificateTemplate()
            
            # Atualizar campos
            template.evaluation_id = template_data['evaluation_id']
            template.title = template_data.get('title')
            template.text_content = template_data['text_content']
            template.background_color = template_data['background_color']
            template.text_color = template_data['text_color']
            template.accent_color = template_data['accent_color']
            template.logo_url = template_data.get('logo_url')
            template.signature_url = template_data.get('signature_url')
            template.custom_date = template_data.get('custom_date')
            
            if not template_id:
                db.session.add(template)
            
            db.session.commit()
            return template
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Erro ao salvar template: {str(e)}")
            raise
    
    @staticmethod
    def get_approved_students(evaluation_id: str) -> List[Dict]:
        """
        Busca alunos aprovados (grade >= 6) de uma avaliação
        
        Args:
            evaluation_id: ID da avaliação (test_id)
            
        Returns:
            Lista de dicionários com: { id, name, grade, class_name }
        """
        try:
            # Buscar resultados de avaliação onde grade >= 6
            results = EvaluationResult.query.filter_by(
                test_id=evaluation_id
            ).filter(
                EvaluationResult.grade >= 6.0
            ).all()
            
            approved_students = []
            for result in results:
                student = Student.query.get(result.student_id)
                if not student:
                    continue
                
                class_name = None
                if student.class_id:
                    class_obj = Class.query.get(student.class_id)
                    class_name = class_obj.name if class_obj else None
                
                approved_students.append({
                    'id': student.id,
                    'name': student.name,
                    'grade': result.grade,
                    'class_name': class_name
                })
            
            return approved_students
            
        except SQLAlchemyError as e:
            logger.error(f"Erro ao buscar alunos aprovados: {str(e)}")
            raise
    
    @staticmethod
    def approve_certificates(evaluation_id: str, student_ids: Optional[List[str]] = None) -> Dict:
        """
        Aprova e emite certificados para alunos aprovados
        
        Args:
            evaluation_id: ID da avaliação (test_id)
            student_ids: Lista opcional de IDs de alunos. Se None, busca todos aprovados
            
        Returns:
            Dicionário com estatísticas: { certificates_issued, certificates_updated, errors }
        """
        try:
            # Verificar se template existe
            template = CertificateService.get_template_by_evaluation(evaluation_id)
            if not template:
                raise ValueError("Template de certificado não encontrado para esta avaliação")
            
            # Buscar avaliação para obter título
            test = Test.query.get(evaluation_id)
            if not test:
                raise ValueError("Avaliação não encontrada")
            
            evaluation_title = test.title or "Avaliação"
            
            # Determinar lista de alunos
            if student_ids:
                # Validar que os alunos têm resultado aprovado
                results = EvaluationResult.query.filter(
                    EvaluationResult.test_id == evaluation_id,
                    EvaluationResult.student_id.in_(student_ids),
                    EvaluationResult.grade >= 6.0
                ).all()
                student_result_map = {r.student_id: r for r in results}
            else:
                # Buscar todos alunos aprovados
                results = EvaluationResult.query.filter(
                    EvaluationResult.test_id == evaluation_id,
                    EvaluationResult.grade >= 6.0
                ).all()
                student_result_map = {r.student_id: r for r in results}
            
            if not student_result_map:
                raise ValueError("Nenhum aluno aprovado encontrado para esta avaliação")
            
            certificates_issued = 0
            certificates_updated = 0
            errors = []
            
            # Criar ou atualizar certificados
            for student_id, result in student_result_map.items():
                try:
                    student = Student.query.get(student_id)
                    if not student:
                        errors.append(f"Aluno {student_id} não encontrado")
                        continue
                    
                    # Verificar se certificado já existe
                    existing_certificate = Certificate.query.filter_by(
                        student_id=student_id,
                        evaluation_id=evaluation_id
                    ).first()
                    
                    if existing_certificate:
                        # Atualizar certificado existente
                        existing_certificate.student_name = student.name
                        existing_certificate.evaluation_title = evaluation_title
                        existing_certificate.grade = result.grade
                        existing_certificate.template_id = template.id
                        existing_certificate.status = 'approved'
                        certificates_updated += 1
                    else:
                        # Criar novo certificado
                        certificate = Certificate(
                            student_id=student_id,
                            student_name=student.name,
                            evaluation_id=evaluation_id,
                            evaluation_title=evaluation_title,
                            grade=result.grade,
                            template_id=template.id,
                            status='approved'
                        )
                        db.session.add(certificate)
                        certificates_issued += 1
                    
                except Exception as e:
                    logger.error(f"Erro ao processar certificado para aluno {student_id}: {str(e)}")
                    errors.append(f"Erro ao processar aluno {student_id}: {str(e)}")
            
            db.session.commit()
            
            return {
                'certificates_issued': certificates_issued,
                'certificates_updated': certificates_updated,
                'errors': errors,
                'total_processed': certificates_issued + certificates_updated
            }
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Erro ao aprovar certificados: {str(e)}")
            raise
    
    @staticmethod
    def get_student_certificates(student_id: str) -> List[Certificate]:
        """
        Busca certificados de um aluno
        
        Args:
            student_id: ID do aluno
            
        Returns:
            Lista de Certificate
        """
        try:
            return Certificate.query.filter_by(student_id=student_id).order_by(
                Certificate.issued_at.desc()
            ).all()
        except SQLAlchemyError as e:
            logger.error(f"Erro ao buscar certificados do aluno: {str(e)}")
            raise
    
    @staticmethod
    def get_certificate_by_id(certificate_id: str) -> Optional[Certificate]:
        """
        Busca certificado por ID
        
        Args:
            certificate_id: ID do certificado
            
        Returns:
            Certificate ou None se não encontrado
        """
        try:
            return Certificate.query.get(certificate_id)
        except SQLAlchemyError as e:
            logger.error(f"Erro ao buscar certificado: {str(e)}")
            raise
