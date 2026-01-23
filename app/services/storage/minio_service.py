# -*- coding: utf-8 -*-
"""
Serviço genérico para interação com MinIO (S3-compatible storage)
Suporta múltiplos tipos de arquivos: PDFs, imagens, logos, etc.
"""

import os
import logging
from datetime import timedelta
from typing import Optional, Dict, List
from minio import Minio
from minio.error import S3Error
from io import BytesIO

logger = logging.getLogger(__name__)


class MinIOService:
    """
    Serviço para upload/download de arquivos no MinIO
    Suporta múltiplos buckets e tipos de arquivo
    """
    
    # Mapeamento de extensões para MIME types
    MIME_TYPES = {
        'pdf': 'application/pdf',
        'zip': 'application/zip',
        'png': 'image/png',
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'gif': 'image/gif',
        'webp': 'image/webp',
        'svg': 'image/svg+xml',
        'json': 'application/json',
        'txt': 'text/plain',
    }
    
    # Buckets disponíveis
    BUCKETS = {
        'ANSWER_SHEETS': 'answer-sheets',
        'PHYSICAL_TESTS': 'physical-tests',
        'MUNICIPALITY_LOGOS': 'municipality-logos',
        'SCHOOL_LOGOS': 'school-logos',
        'QUESTION_IMAGES': 'question-images',
        'USER_UPLOADS': 'user-uploads',
    }
    
    def __init__(self):
        self.endpoint = os.getenv('MINIO_ENDPOINT', 'localhost:9000')
        self.access_key = os.getenv('MINIO_ACCESS_KEY', 'minioadmin')
        self.secret_key = os.getenv('MINIO_SECRET_KEY', 'minioadmin123')
        self.secure = os.getenv('MINIO_SECURE', 'false').lower() == 'true'
        
        # URL pública (se houver nginx/proxy na frente)
        self.public_endpoint = os.getenv('MINIO_ENDPOINT_PUBLIC', f"http://{self.endpoint}")
        
        self.client = Minio(
            self.endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=self.secure
        )
        
        logger.info(f"✅ MinIO client inicializado: {self.endpoint}")
    
    def _get_content_type(self, file_path: str) -> str:
        """Detecta MIME type baseado na extensão do arquivo"""
        ext = file_path.split('.')[-1].lower()
        return self.MIME_TYPES.get(ext, 'application/octet-stream')
    
    def upload_file(
        self, 
        bucket_name: str, 
        object_name: str, 
        data: bytes,
        content_type: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Dict[str, str]:
        """
        Upload genérico de arquivo para MinIO
        
        Args:
            bucket_name: Nome do bucket (use self.BUCKETS)
            object_name: Caminho/nome do arquivo no bucket
            data: Dados binários do arquivo
            content_type: MIME type (auto-detectado se None)
            metadata: Metadados opcionais
        
        Returns:
            Dict com 'url', 'object_name', 'bucket' e 'size'
        """
        try:
            if content_type is None:
                content_type = self._get_content_type(object_name)
            
            self.client.put_object(
                bucket_name,
                object_name,
                data=BytesIO(data),
                length=len(data),
                content_type=content_type,
                metadata=metadata or {}
            )
            
            url = f"{self.public_endpoint}/{bucket_name}/{object_name}"
            logger.info(f"✅ Arquivo enviado para MinIO: {url}")
            
            return {
                'url': url,
                'object_name': object_name,
                'bucket': bucket_name,
                'size': len(data)
            }
            
        except S3Error as e:
            logger.error(f"❌ Erro ao enviar arquivo para MinIO: {str(e)}")
            raise
    
    def upload_from_path(
        self, 
        bucket_name: str, 
        object_name: str, 
        file_path: str
    ) -> Dict[str, str]:
        """Upload de arquivo a partir de caminho no filesystem"""
        try:
            content_type = self._get_content_type(file_path)
            
            self.client.fput_object(
                bucket_name,
                object_name,
                file_path,
                content_type=content_type
            )
            
            # Obter tamanho do arquivo
            file_size = os.path.getsize(file_path)
            
            url = f"{self.public_endpoint}/{bucket_name}/{object_name}"
            logger.info(f"✅ Arquivo enviado para MinIO: {url}")
            
            return {
                'url': url,
                'object_name': object_name,
                'bucket': bucket_name,
                'size': file_size
            }
            
        except S3Error as e:
            logger.error(f"❌ Erro ao enviar arquivo para MinIO: {str(e)}")
            raise
    
    def get_presigned_url(
        self, 
        bucket_name: str, 
        object_name: str,
        expires: timedelta = timedelta(hours=1)
    ) -> str:
        """
        Gera URL pré-assinada para download temporário
        
        Args:
            bucket_name: Nome do bucket
            object_name: Nome do objeto
            expires: Tempo de expiração (padrão: 1 hora)
        
        Returns:
            URL pré-assinada para download
        """
        try:
            url = self.client.presigned_get_object(
                bucket_name,
                object_name,
                expires=expires
            )
            
            logger.info(f"✅ URL pré-assinada gerada (válida por {expires})")
            return url
            
        except S3Error as e:
            logger.error(f"❌ Erro ao gerar URL pré-assinada: {str(e)}")
            raise
    
    def download_file(self, bucket_name: str, object_name: str) -> bytes:
        """Download de arquivo do MinIO como bytes"""
        try:
            response = self.client.get_object(bucket_name, object_name)
            data = response.read()
            response.close()
            response.release_conn()
            
            logger.info(f"✅ Arquivo baixado do MinIO: {bucket_name}/{object_name}")
            return data
            
        except S3Error as e:
            logger.error(f"❌ Erro ao baixar arquivo: {str(e)}")
            raise
    
    def delete_file(self, bucket_name: str, object_name: str) -> bool:
        """Deleta um arquivo do MinIO"""
        try:
            self.client.remove_object(bucket_name, object_name)
            logger.info(f"✅ Arquivo deletado: {bucket_name}/{object_name}")
            return True
            
        except S3Error as e:
            logger.error(f"❌ Erro ao deletar arquivo: {str(e)}")
            return False
    
    def list_files(self, bucket_name: str, prefix: str = '') -> List[str]:
        """Lista arquivos no bucket"""
        try:
            objects = self.client.list_objects(bucket_name, prefix=prefix, recursive=True)
            return [obj.object_name for obj in objects]
            
        except S3Error as e:
            logger.error(f"❌ Erro ao listar arquivos: {str(e)}")
            return []
    
    def file_exists(self, bucket_name: str, object_name: str) -> bool:
        """Verifica se um arquivo existe no MinIO"""
        try:
            self.client.stat_object(bucket_name, object_name)
            return True
        except S3Error:
            return False
    
    # ========================================================================
    # MÉTODOS ESPECÍFICOS PARA CADA TIPO DE ARQUIVO
    # ========================================================================
    
    def upload_answer_sheet_zip(self, gabarito_id: str, zip_data: bytes) -> Dict[str, str]:
        """
        Upload de ZIP de cartões de resposta
        
        Args:
            gabarito_id: ID do gabarito
            zip_data: Dados binários do ZIP
        
        Returns:
            Dict com informações do upload
        """
        object_name = f"gabaritos/{gabarito_id}/cartoes.zip"
        return self.upload_file(
            bucket_name=self.BUCKETS['ANSWER_SHEETS'],
            object_name=object_name,
            data=zip_data,
            content_type='application/zip'
        )
    
    def upload_physical_test_zip(self, test_id: str, zip_data: bytes) -> Dict[str, str]:
        """
        Upload de ZIP de provas físicas
        
        Args:
            test_id: ID da prova
            zip_data: Dados binários do ZIP
        
        Returns:
            Dict com informações do upload
        """
        object_name = f"{test_id}/all_forms.zip"
        return self.upload_file(
            bucket_name=self.BUCKETS['PHYSICAL_TESTS'],
            object_name=object_name,
            data=zip_data,
            content_type='application/zip'
        )
    
    def upload_municipality_logo(self, city_id: str, image_data: bytes, extension: str = 'png') -> Dict[str, str]:
        """
        Upload de logo de município
        
        Args:
            city_id: ID da cidade
            image_data: Dados binários da imagem
            extension: Extensão do arquivo (padrão: png)
        
        Returns:
            Dict com informações do upload
        """
        object_name = f"{city_id}.{extension}"
        return self.upload_file(
            bucket_name=self.BUCKETS['MUNICIPALITY_LOGOS'],
            object_name=object_name,
            data=image_data
        )
    
    def upload_school_logo(self, school_id: str, image_data: bytes, extension: str = 'png') -> Dict[str, str]:
        """
        Upload de logo de escola
        
        Args:
            school_id: ID da escola
            image_data: Dados binários da imagem
            extension: Extensão do arquivo (padrão: png)
        
        Returns:
            Dict com informações do upload
        """
        object_name = f"{school_id}.{extension}"
        return self.upload_file(
            bucket_name=self.BUCKETS['SCHOOL_LOGOS'],
            object_name=object_name,
            data=image_data
        )
    
    def upload_question_image(self, question_id: str, image_data: bytes, image_name: str) -> Dict[str, str]:
        """
        Upload de imagem de questão
        
        Args:
            question_id: ID da questão
            image_data: Dados binários da imagem
            image_name: Nome do arquivo da imagem
        
        Returns:
            Dict com informações do upload
        """
        object_name = f"{question_id}/{image_name}"
        return self.upload_file(
            bucket_name=self.BUCKETS['QUESTION_IMAGES'],
            object_name=object_name,
            data=image_data
        )
