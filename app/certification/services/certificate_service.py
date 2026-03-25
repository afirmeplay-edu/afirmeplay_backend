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
import base64
import logging
import mimetypes
import re
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

from app.services.storage.minio_service import MinIOService

logger = logging.getLogger(__name__)


def _mime_to_ext_certificate(mime: str) -> str:
    m = (mime or "").lower()
    if "png" in m:
        return "png"
    if "jpeg" in m or "jpg" in m:
        return "jpg"
    if "gif" in m:
        return "gif"
    if "webp" in m:
        return "webp"
    if "svg" in m:
        return "svg"
    return "png"


def _data_url_to_minio_certificate_image_url(
    evaluation_id: str, data_url: str, role: str
) -> str:
    """
    Envia data URL de imagem ao MinIO e retorna URL pública armazenável em logo_url/signature_url.
    """
    raw = data_url.strip()
    match = re.match(r"^data:image/([^;]+);base64,(.+)$", raw, re.DOTALL)
    if not match:
        raise ValueError(
            "Formato de imagem inválido (esperado data:image/...;base64,...)"
        )
    mime_subtype = match.group(1).strip().lower()
    b64 = match.group(2).strip()
    mime_type = (
        mime_subtype if "/" in mime_subtype else f"image/{mime_subtype}"
    )
    try:
        image_bytes = base64.b64decode(b64, validate=False)
    except Exception as e:
        raise ValueError(f"Base64 da imagem inválido: {e}") from e
    if not image_bytes:
        raise ValueError("Imagem vazia após decodificação")
    ext = _mime_to_ext_certificate(mime_type)
    minio = MinIOService()
    result = minio.upload_certificate_template_image(
        evaluation_id, role, image_bytes, ext
    )
    if not result or not result.get("url"):
        raise ValueError("Falha ao enviar imagem do certificado para o armazenamento")
    url = result["url"]
    if len(url) > 500:
        logger.warning(
            "URL MinIO do template de certificado tem %s caracteres; limite do banco é 500",
            len(url),
        )
    return url


def _resolve_certificate_template_image_field(
    evaluation_id: str, value: Optional[str], role: str
) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    s = value.strip()
    if not s:
        return None
    if s.startswith("data:image/"):
        return _data_url_to_minio_certificate_image_url(evaluation_id, s, role)
    return s


def _parse_certificate_template_minio_location(stored_url: str) -> Tuple[str, str]:
    """
    Extrai bucket e chave do objeto a partir da URL persistida (upload_file do MinIO).
    """
    path = urlparse(stored_url).path.lstrip("/")
    bucket = MinIOService.BUCKETS["CERTIFICATE_TEMPLATES"]
    prefix = f"{bucket}/"
    if not path.startswith(prefix):
        raise ValueError("URL de arquivo não pertence ao armazenamento de certificados")
    object_name = path[len(prefix) :]
    if not object_name:
        raise ValueError("Caminho do objeto inválido")
    return bucket, object_name


class CertificateService:
    """Serviço para operações de certificados"""
    
    @staticmethod
    def load_template_asset(evaluation_id: str, asset_kind: str) -> Tuple[bytes, str]:
        """
        Baixa logo ou assinatura do MinIO para servir via proxy autenticado.

        Args:
            evaluation_id: ID da avaliação (test.id)
            asset_kind: 'logo' ou 'signature'

        Returns:
            (bytes, content_type)

        Raises:
            LookupError: template ou arquivo ausente
            ValueError: URL inválida ou imagem ainda em base64
        """
        if asset_kind not in ("logo", "signature"):
            raise ValueError("Tipo de arquivo inválido (use logo ou signature)")
        template = CertificateService.get_template_by_evaluation(evaluation_id)
        if not template:
            raise LookupError("Template não encontrado")
        stored = (
            template.logo_url if asset_kind == "logo" else template.signature_url
        )
        if not stored or not str(stored).strip():
            raise LookupError("Imagem não disponível para este template")
        stored = stored.strip()
        if stored.startswith("data:image/"):
            raise ValueError(
                "Imagem ainda não foi enviada ao armazenamento; salve o template novamente"
            )
        bucket, object_name = _parse_certificate_template_minio_location(stored)
        minio = MinIOService()
        data = minio.download_file(bucket, object_name)
        ctype, _ = mimetypes.guess_type(object_name)
        return data, ctype or "application/octet-stream"

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
            ev_id = template_data['evaluation_id']
            template.logo_url = _resolve_certificate_template_image_field(
                ev_id, template_data.get('logo_url'), 'logo'
            )
            template.signature_url = _resolve_certificate_template_image_field(
                ev_id, template_data.get('signature_url'), 'signature'
            )
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

    @staticmethod
    def count_issued(school_ids: Optional[List[str]] = None) -> int:
        """
        Retorna a quantidade de certificados emitidos.
        Se school_ids for None, conta todos. Se for lista vazia, retorna 0.
        Se for lista de IDs, filtra por alunos dessas escolas.
        """
        try:
            query = Certificate.query.join(Student, Certificate.student_id == Student.id)
            if school_ids is not None:
                if not school_ids:
                    return 0
                school_ids_str = [str(sid) for sid in school_ids]
                query = query.filter(Student.school_id.in_(school_ids_str))
            return query.count()
        except SQLAlchemyError as e:
            logger.error(f"Erro ao contar certificados emitidos: {str(e)}")
            raise
