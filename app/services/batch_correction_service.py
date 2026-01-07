import threading
import time
import json
import base64
from datetime import datetime, timedelta
from app import db
from app.models.batchCorrectionJob import BatchCorrectionJob
from app.models.test import Test
from app.models.student import Student
from app.services.physical_test_pdf_generator import PhysicalTestPDFGenerator
import logging

class BatchCorrectionService:
    """
    Serviço para gerenciar correção em lote de formulários físicos
    """
    
    def __init__(self):
        self.active_jobs = {}  # Cache de jobs ativos
        self.pdf_generator = PhysicalTestPDFGenerator()
    
    def create_batch_job(self, test_id, created_by, images_data):
        """
        Cria um novo job de correção em lote
        
        Args:
            test_id: ID da prova
            created_by: ID do usuário que criou o job
            images_data: Lista com dados das imagens
            
        Returns:
            BatchCorrectionJob: Job criado
        """
        try:
            # Validar prova
            test = Test.query.get(test_id)
            if not test:
                raise ValueError(f"Prova não encontrada: {test_id}")
            
            # Criar job
            job = BatchCorrectionJob(
                test_id=test_id,
                created_by=created_by,
                total_images=len(images_data),
                images_data=json.dumps(images_data)
            )
            
            db.session.add(job)
            db.session.commit()
            
            logging.info(f"Job de correção em lote criado: {job.id} para {len(images_data)} imagens")
            return job
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Erro ao criar job de correção em lote: {str(e)}")
            raise
    
    def start_batch_processing(self, job_id):
        """
        Inicia processamento do job em lote (assíncrono)
        
        Args:
            job_id: ID do job a ser processado
        """
        try:
            job = BatchCorrectionJob.query.get(job_id)
            if not job:
                raise ValueError(f"Job não encontrado: {job_id}")
            
            # Atualizar status para processando
            job.set_status('processing')
            
            # Iniciar thread de processamento
            thread = threading.Thread(
                target=self._process_batch_async,
                args=(job_id,),
                daemon=True
            )
            thread.start()
            
            # Armazenar referência do job ativo
            self.active_jobs[job_id] = job
            
            logging.info(f"Processamento iniciado para job: {job_id}")
            
        except Exception as e:
            logging.error(f"Erro ao iniciar processamento do job {job_id}: {str(e)}")
            # Marcar job como falhou
            job = BatchCorrectionJob.query.get(job_id)
            if job:
                job.set_status('failed')
                job.add_error(0, f"Erro ao iniciar processamento: {str(e)}")
            raise
    
    def _process_batch_async(self, job_id):
        """
        Processa job de correção em lote de forma assíncrona
        
        Args:
            job_id: ID do job a ser processado
        """
        from app import create_app
        
        # Criar contexto da aplicação para a thread
        app = create_app()
        
        with app.app_context():
            job = None
            try:
                job = BatchCorrectionJob.query.get(job_id)
                if not job:
                    logging.error(f"Job não encontrado: {job_id}")
                    return
                
                logging.info(f"Iniciando processamento assíncrono do job: {job_id}")
                
                # Carregar dados das imagens
                images_data = json.loads(job.images_data) if job.images_data else []
                
                if not images_data:
                    job.set_status('failed')
                    job.add_error(0, "Nenhuma imagem fornecida")
                    return
                
                # 1. GERAR GABARITO ÚNICO (otimização crítica)
                logging.info(f"Gerando gabarito único para {len(images_data)} imagens...")
                gabarito_data = self._generate_single_gabarito(job.test_id, images_data[0])
                
                if not gabarito_data:
                    job.set_status('failed')
                    job.add_error(0, "Erro ao gerar gabarito de referência")
                    return
                
                # Salvar dados do gabarito no job
                job.set_gabarito_data(gabarito_data)
                
                # 2. PROCESSAR CADA IMAGEM INDIVIDUALMENTE
                processed_count = 0
                successful_count = 0
                failed_count = 0
                
                for i, image_data in enumerate(images_data):
                    try:
                        # Atualizar progresso atual
                        student_id = image_data.get('student_id')
                        student_name = image_data.get('student_name', f'Imagem {i+1}')
                        
                        job.update_progress(
                            processed_count, successful_count, failed_count,
                            student_id, student_name
                        )
                        
                        # Processar imagem individual
                        result = self._process_single_image(
                            job.test_id, 
                            image_data['image'], 
                            gabarito_data,
                            student_id
                        )
                        
                        if result['success']:
                            successful_count += 1
                            job.add_result(
                                result['student_id'],
                                result.get('student_name', student_name),
                                result
                            )
                            logging.info(f"Imagem {i+1} processada com sucesso: {result['student_id']}")
                        else:
                            failed_count += 1
                            job.add_error(i, result['error'], student_id)
                            logging.warning(f"Erro ao processar imagem {i+1}: {result['error']}")
                        
                        processed_count += 1
                        
                        # Pequena pausa para não sobrecarregar o sistema
                        time.sleep(0.5)
                        
                    except Exception as e:
                        failed_count += 1
                        error_msg = f"Erro inesperado ao processar imagem {i+1}: {str(e)}"
                        job.add_error(i, error_msg, image_data.get('student_id'))
                        logging.error(error_msg)
                        processed_count += 1
                
                # 3. FINALIZAR JOB
                job.update_progress(processed_count, successful_count, failed_count)
                job.set_status('completed')
                
                # Remover do cache de jobs ativos
                if job_id in self.active_jobs:
                    del self.active_jobs[job_id]
                
                logging.info(f"Job {job_id} concluído: {successful_count} sucessos, {failed_count} falhas")
                
            except Exception as e:
                logging.error(f"Erro crítico no processamento do job {job_id}: {str(e)}")
                if job:
                    job.set_status('failed')
                    job.add_error(0, f"Erro crítico: {str(e)}")
                
                # Remover do cache
                if job_id in self.active_jobs:
                    del self.active_jobs[job_id]
    
    def _generate_single_gabarito(self, test_id, first_image_data):
        """
        Gera gabarito único baseado na primeira imagem
        
        Args:
            test_id: ID da prova
            first_image_data: Dados da primeira imagem
            
        Returns:
            dict: Dados do gabarito gerado
        """
        try:
            # Usar a primeira imagem para gerar gabarito de referência
            image_data_str = first_image_data['image']
            
            # Processar imagem para obter dimensões
            user_image = self.pdf_generator._processar_imagem_usuario(image_data_str)
            if user_image is None:
                return None
            
            # Gerar gabarito adaptativo
            height, width = user_image.shape[:2]
            gabarito_image, coordenadas_respostas = self.pdf_generator._gerar_gabarito_referencia_adaptativo(
                test_id, (width, height)  # Passar dimensões (width, height)
            )
            
            if gabarito_image is None or coordenadas_respostas is None:
                return None
            
            # Converter imagem PIL para base64
            import io
            import base64
            from PIL import Image
            
            if isinstance(gabarito_image, Image.Image):
                # Converter PIL Image para base64
                buffer = io.BytesIO()
                gabarito_image.save(buffer, format='PNG')
                gabarito_image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
                gabarito_image_str = f"data:image/png;base64,{gabarito_image_base64}"
            else:
                # Se já for string base64, usar diretamente
                gabarito_image_str = gabarito_image
            
            return {
                'test_id': test_id,
                'gabarito_image': gabarito_image_str,
                'gabarito_dimensions': (width, height),
                'questions_data': coordenadas_respostas,
                'generated_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logging.error(f"Erro ao gerar gabarito único: {str(e)}")
            return None
    
    def _generate_single_gabarito_test(self, test_id, first_image_data):
        """
        Gera gabarito único para teste (sem validação de prova)
        """
        try:
            # Usar a primeira imagem para gerar gabarito de referência
            image_data_str = first_image_data['image']
            
            # Processar imagem para obter dimensões
            user_image = self.pdf_generator._processar_imagem_usuario(image_data_str)
            if user_image is None:
                return None
            
            # Simular dados de gabarito para teste
            height, width = user_image.shape[:2]
            
            # Converter numpy array para PIL Image
            from PIL import Image
            import numpy as np
            
            # Converter numpy array para PIL Image
            if isinstance(user_image, np.ndarray):
                # Converter de BGR para RGB se necessário
                if len(user_image.shape) == 3 and user_image.shape[2] == 3:
                    user_image = user_image[:, :, ::-1]  # BGR to RGB
                gabarito_image = Image.fromarray(user_image.astype(np.uint8))
            else:
                gabarito_image = user_image
            
            # Converter para base64
            import io
            import base64
            
            buffer = io.BytesIO()
            gabarito_image.save(buffer, format='PNG')
            gabarito_image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            gabarito_image_str = f"data:image/png;base64,{gabarito_image_base64}"
            
            return {
                'test_id': test_id,
                'gabarito_image': gabarito_image_str,
                'gabarito_dimensions': (width, height),
                'questions_data': [],  # Lista vazia para teste
                'generated_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logging.error(f"Erro ao gerar gabarito único (teste): {str(e)}")
            return None
    
    def _process_single_image(self, test_id, image_data_str, gabarito_data, student_id_hint=None):
        """
        Processa uma única imagem usando gabarito pré-gerado
        
        Args:
            test_id: ID da prova
            image_data_str: Dados da imagem em base64
            gabarito_data: Dados do gabarito pré-gerado
            student_id_hint: ID do aluno (se conhecido)
            
        Returns:
            dict: Resultado do processamento
        """
        try:
            # Processar imagem do usuário
            user_image = self.pdf_generator._processar_imagem_usuario(image_data_str)
            if user_image is None:
                return {
                    'success': False,
                    'error': 'Erro ao processar imagem do usuário'
                }
            
            # Detectar QR code para identificar aluno (usando mesmo método da rota que funciona)
            user_qr = self.pdf_generator._detectar_qr_code_avancado(user_image)
            if user_qr is None and student_id_hint:
                student_id = student_id_hint
            elif user_qr is not None:
                student_id = user_qr['data'].get('student_id')
            else:
                student_id = None
            
            if not student_id:
                return {
                    'success': False,
                    'error': 'QR code não detectado e student_id não fornecido'
                }
            
            # Buscar dados do aluno
            student = Student.query.get(student_id)
            student_name = student.name if student else f"Aluno {student_id}"
            
            # Usar gabarito pré-gerado para correção
            result = self.pdf_generator._corrigir_com_gabarito_pre_gerado(
                user_image, gabarito_data, test_id, student_id
            )
            
            if not result['success']:
                return {
                    'success': False,
                    'error': result['error']
                }
            
            # Adicionar informações do aluno ao resultado
            result['student_id'] = student_id
            result['student_name'] = student_name
            
            return result
            
        except Exception as e:
            logging.error(f"Erro ao processar imagem individual: {str(e)}")
            return {
                'success': False,
                'error': f"Erro inesperado: {str(e)}"
            }
    
    def get_job_status(self, job_id):
        """
        Obtém status atual do job
        
        Args:
            job_id: ID do job
            
        Returns:
            dict: Status do job
        """
        job = BatchCorrectionJob.query.get(job_id)
        if not job:
            return None
        
        return job.get_progress_data()
    
    def get_job_results(self, job_id):
        """
        Obtém resultados finais do job
        
        Args:
            job_id: ID do job
            
        Returns:
            dict: Resultados do job
        """
        job = BatchCorrectionJob.query.get(job_id)
        if not job:
            return None
        
        return job.get_results()
    
    def cancel_job(self, job_id):
        """
        Cancela um job em andamento
        
        Args:
            job_id: ID do job a ser cancelado
            
        Returns:
            bool: True se cancelado com sucesso
        """
        try:
            job = BatchCorrectionJob.query.get(job_id)
            if not job:
                return False
            
            if job.status in ['completed', 'failed', 'cancelled']:
                return False
            
            job.set_status('cancelled')
            
            # Remover do cache
            if job_id in self.active_jobs:
                del self.active_jobs[job_id]
            
            logging.info(f"Job {job_id} cancelado")
            return True
            
        except Exception as e:
            logging.error(f"Erro ao cancelar job {job_id}: {str(e)}")
            return False
    
    def cleanup_old_jobs(self, hours=24):
        """
        Remove jobs antigos do banco de dados
        
        Args:
            hours: Idade em horas para considerar job como antigo
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            
            old_jobs = BatchCorrectionJob.query.filter(
                BatchCorrectionJob.created_at < cutoff_time
            ).all()
            
            for job in old_jobs:
                db.session.delete(job)
            
            db.session.commit()
            
            logging.info(f"Removidos {len(old_jobs)} jobs antigos")
            
        except Exception as e:
            logging.error(f"Erro ao limpar jobs antigos: {str(e)}")
            db.session.rollback()

    def process_batch_sync(self, test_id, created_by, images_data):
        """
        Processa correção em lote de forma síncrona
        
        Args:
            test_id: ID da prova
            created_by: ID do usuário que criou o job
            images_data: Lista de dados das imagens
            
        Returns:
            Dict com resultados da correção
        """
        try:
            logging.info(f"🔧 Iniciando correção em lote síncrona para {len(images_data)} imagens")
            
            # Gerar gabarito único para toda a prova
            gabarito_data = self._generate_single_gabarito(test_id, images_data[0]['image'])
            if not gabarito_data:
                return {
                    'successful_corrections': 0,
                    'failed_corrections': len(images_data),
                    'success_rate': 0.0,
                    'results': [],
                    'errors': ['Erro ao gerar gabarito único']
                }
            
            results = []
            errors = []
            successful_corrections = 0
            failed_corrections = 0
            
            # Processar cada imagem
            for i, img_data in enumerate(images_data):
                try:
                    logging.info(f"🔧 Processando imagem {i+1}/{len(images_data)}")
                    
                    result = self._process_single_image(
                        test_id=test_id,
                        image_data_str=img_data['image'],
                        gabarito_data=gabarito_data,
                        student_id_hint=img_data.get('student_id')
                    )
                    
                    if result['success']:
                        successful_corrections += 1
                        results.append({
                            'image_index': i,
                            'student_id': result['student_id'],
                            'student_name': img_data.get('student_name', f"Aluno {result['student_id']}"),
                            'correct_answers': result['correct_answers'],
                            'total_questions': result['total_questions'],
                            'score_percentage': result['score_percentage'],
                            'grade': result['grade'],
                            'proficiency': result['proficiency'],
                            'classification': result['classification'],
                            'answers_detected': result['answers_detected'],
                            'evaluation_result_id': result.get('evaluation_result_id')
                        })
                    else:
                        failed_corrections += 1
                        error_msg = f"Imagem {i+1}: {result['error']}"
                        errors.append(error_msg)
                        results.append({
                            'image_index': i,
                            'student_id': img_data.get('student_id'),
                            'student_name': img_data.get('student_name', f"Aluno {i+1}"),
                            'error': result['error'],
                            'success': False
                        })
                        
                except Exception as e:
                    failed_corrections += 1
                    error_msg = f"Imagem {i+1}: Erro inesperado - {str(e)}"
                    errors.append(error_msg)
                    results.append({
                        'image_index': i,
                        'student_id': img_data.get('student_id'),
                        'student_name': img_data.get('student_name', f"Aluno {i+1}"),
                        'error': str(e),
                        'success': False
                    })
                    logging.error(f"Erro ao processar imagem {i+1}: {str(e)}")
            
            success_rate = (successful_corrections / len(images_data)) * 100 if images_data else 0
            
            logging.info(f"✅ Correção em lote concluída: {successful_corrections} sucessos, {failed_corrections} falhas")
            
            return {
                'successful_corrections': successful_corrections,
                'failed_corrections': failed_corrections,
                'success_rate': success_rate,
                'results': results,
                'errors': errors
            }
            
        except Exception as e:
            logging.error(f"Erro crítico na correção em lote síncrona: {str(e)}")
            return {
                'successful_corrections': 0,
                'failed_corrections': len(images_data),
                'success_rate': 0.0,
                'results': [],
                'errors': [f"Erro crítico: {str(e)}"]
            }

# Instância global do serviço
batch_correction_service = BatchCorrectionService()

