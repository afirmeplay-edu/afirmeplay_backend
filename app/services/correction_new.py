# -*- coding: utf-8 -*-
"""
Serviço de Correção de Provas Físicas SEM IA
Adapta o sistema de app/test_correction/ para funcionar com o sistema atual
Usa detecção de triângulos, quadrados e círculos ao invés de IA
"""

import cv2
import numpy as np
import logging
import sys
import os
import json
from typing import Dict, List, Optional, Tuple, Any
from app import db
from app.models.testQuestion import TestQuestion
from app.models.question import Question
from app.models.studentAnswer import StudentAnswer
from app.models.student import Student
from app.models.testSession import TestSession
from app.models.physicalTestForm import PhysicalTestForm
from datetime import datetime

# Importar funções do sistema antigo (sem modificar)
# Adicionar o caminho do test_correction ao sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
test_correction_path = os.path.join(current_dir, '..', 'test_correction')
if test_correction_path not in sys.path:
    sys.path.insert(0, test_correction_path)

# Importar módulos do sistema antigo
try:
    from util import paper90, getOurSqr, getAnswers, getGrades
    from libQr import leQr
except ImportError as e:
    logging.error(f"Erro ao importar módulos do sistema antigo: {str(e)}")
    raise


class CorrecaoNova:
    """
    Serviço para correção de provas físicas SEM IA
    Usa processamento de imagem (triângulos, quadrados, círculos)
    """
    
    def __init__(self, debug: bool = False):
        """
        Inicializa o serviço de correção sem IA
        
        Args:
            debug: Se True, gera logs detalhados
        """
        self.debug = debug
        self.logger = logging.getLogger(__name__)
    
    def corrigir_prova_sem_ia(self, image_data: bytes, test_id: str) -> Dict[str, Any]:
        """
        Processa correção completa SEM IA:
        1. Decodifica imagem
        2. Orienta página usando triângulos (paper90)
        3. Detecta QR Code para identificar aluno
        4. Detecta quadrados (questões e alternativas)
        5. Detecta círculos preenchidos (respostas)
        6. Compara com gabarito
        7. Salva no banco
        
        Args:
            image_data: Imagem em bytes (JPEG/PNG)
            test_id: ID da prova
            
        Returns:
            Dict com resultados da correção
        """
        try:
            # 1. Decodificar imagem
            print("🔍 [DEBUG] Iniciando decodificação da imagem...")
            print(f"🔍 [DEBUG] Tamanho dos bytes recebidos: {len(image_data)} bytes")
            img = self._decode_image(image_data)
            if img is None:
                print("❌ [DEBUG] ERRO: Imagem não foi decodificada (img is None)")
                return {"success": False, "error": "Erro ao decodificar imagem"}
            
            print(f"✅ [DEBUG] Imagem decodificada com sucesso!")
            print(f"🔍 [DEBUG] Dimensões da imagem original: {img.shape} (altura x largura x canais)")
            
            # Tentar detectar QR code ANTES de orientar (para usar se paper90 falhar)
            print("🔍 [DEBUG] Tentando detectar QR code na imagem ORIGINAL (antes de paper90)...")
            qr_result_antes = self._detectar_qr_code_adaptado(img)
            if qr_result_antes and 'student_id' in qr_result_antes:
                print(f"✅ [DEBUG] QR Code detectado na imagem ORIGINAL: {qr_result_antes}")
            else:
                print("⚠️ [DEBUG] QR Code NÃO detectado na imagem ORIGINAL")
            
            # 2. Orientar página usando triângulos (paper90)
            # Se não forem encontrados quatro triângulos 'homogêneos', retorna None
            print("🔍 [DEBUG] Iniciando orientação da página (paper90)...")
            img_oriented = paper90(img)
            
            # Se paper90 falhar, usar imagem original e QR code já detectado
            if img_oriented is None:
                print("⚠️ [DEBUG] AVISO: paper90 retornou None (triângulos não detectados)")
                print("🔍 [DEBUG] Tentando continuar com imagem original...")
                
                # Se já detectamos o QR code na imagem original, usar ele
                if qr_result_antes and 'student_id' in qr_result_antes:
                    print("✅ [DEBUG] Usando QR code detectado na imagem ORIGINAL (paper90 falhou)")
                    qr_result = qr_result_antes
                    img_oriented = img  # Usar imagem original ao invés de orientada
                    print(f"🔍 [DEBUG] Usando imagem original: {img_oriented.shape}")
                else:
                    print("❌ [DEBUG] ERRO: paper90 falhou E QR code não foi detectado na imagem original")
                    return {"success": False, "error": "Não foi possível orientar a página e QR Code não detectado"}
            else:
                print(f"✅ [DEBUG] Página orientada com sucesso!")
                print(f"🔍 [DEBUG] Dimensões da imagem orientada: {img_oriented.shape} (altura x largura x canais)")
                
                # 3. Detectar QR Code na imagem orientada (suporta formato antigo e JSON)
                print("🔍 [DEBUG] Tentando detectar QR code na imagem ORIENTADA...")
                qr_result = self._detectar_qr_code_adaptado(img_oriented)
                if not qr_result or 'student_id' not in qr_result:
                    print(f"⚠️ [DEBUG] QR Code não detectado na imagem orientada, tentando usar o da imagem original...")
                    # Se não detectou na orientada, tentar usar o da original
                    if qr_result_antes and 'student_id' in qr_result_antes:
                        print("✅ [DEBUG] Usando QR code da imagem ORIGINAL (não detectado na orientada)")
                        qr_result = qr_result_antes
                    else:
                        print(f"❌ [DEBUG] ERRO: QR Code não detectado em nenhuma imagem")
                        print(f"🔍 [DEBUG] Resultado de _detectar_qr_code_adaptado: {qr_result}")
                        return {"success": False, "error": "QR Code não detectado ou inválido"}
                else:
                    print(f"✅ [DEBUG] QR Code detectado na imagem ORIENTADA: {qr_result}")
            
            student_id = str(qr_result['student_id'])
            test_id_from_qr = str(qr_result.get('test_id', test_id))
            
            # Validar test_id
            if test_id_from_qr != test_id:
                self.logger.warning(f"Test ID do QR ({test_id_from_qr}) diferente do fornecido ({test_id})")
            
            # 4. Buscar gabarito do teste
            gabarito_dict, num_questions, num_alternatives = self._buscar_gabarito_adaptado(test_id)
            if not gabarito_dict:
                return {"success": False, "error": "Gabarito não encontrado para esta prova"}
            
            # 5. Detectar quadrados (questões e alternativas)
            question_squares, alternative_squares, img_cropped = getOurSqr(img_oriented)
            
            # Validar quantidade de quadrados detectados
            if len(question_squares) != num_questions:
                self.logger.warning(f"Quantidade de questões detectadas ({len(question_squares)}) diferente do esperado ({num_questions})")
            
            if len(alternative_squares) != num_alternatives:
                self.logger.warning(f"Quantidade de alternativas detectadas ({len(alternative_squares)}) diferente do esperado ({num_alternatives})")
            
            # 6. Detectar respostas (círculos preenchidos)
            gabarito_aluno = getAnswers(img_oriented)
            
            if not gabarito_aluno:
                return {"success": False, "error": "Nenhuma resposta detectada"}
            
            # 7. Converter gabarito_aluno para formato do sistema antigo
            # gabarito_aluno é lista de tuplas: [(questão, alternativa), ...]
            # onde alternativa é 1-4 (A-D) ou 0 se não marcada
            
            # Converter gabarito do sistema atual para formato do sistema antigo
            gabarito_antigo = self._converter_gabarito_para_formato_antigo(gabarito_dict)
            
            # 8. Calcular notas usando função do sistema antigo
            notas, answ_clear, warnings = getGrades(gabarito_antigo, gabarito_aluno)
            
            # 9. Converter respostas para formato do sistema atual
            respostas_detectadas = self._converter_respostas_para_formato_atual(
                answ_clear, num_questions
            )
            
            # 10. Calcular estatísticas
            correction = self._calcular_correcao(respostas_detectadas, gabarito_dict)
            
            # 11. Salvar respostas no banco
            saved_answers = self._salvar_respostas_no_banco(
                test_id=test_id,
                student_id=student_id,
                respostas_detectadas=respostas_detectadas,
                gabarito=gabarito_dict
            )
            
            # 12. Criar sessão temporária para correção física
            session_id = self._criar_sessao_temporaria_para_correcao_fisica(
                test_id=test_id,
                student_id=student_id
            )
            
            if not session_id:
                self.logger.error("Erro ao criar sessão temporária para correção física")
                return {"success": False, "error": "Erro ao criar sessão temporária"}
            
            # 13. Calcular nota, proficiência e classificação usando EvaluationResultService
            from app.services.evaluation_result_service import EvaluationResultService
            
            evaluation_result = EvaluationResultService.calculate_and_save_result(
                test_id=test_id,
                student_id=student_id,
                session_id=session_id
            )
            
            # 14. Calcular resultado final
            correct_count = correction['correct']
            total_count = correction['total_questions']
            percentage = correction['score_percentage']
            
            # Preparar resposta com todos os campos
            response_data = {
                "success": True,
                "student_id": student_id,
                "test_id": test_id,
                "correct": correct_count,
                "total": total_count,
                "percentage": percentage,
                "answers": respostas_detectadas,
                "correction": correction,
                "details": self._criar_detalhes(respostas_detectadas, gabarito_dict, warnings),
                "saved_answers": saved_answers,
                "warnings": warnings
            }
            
            # Adicionar campos calculados pelo EvaluationResultService
            if evaluation_result:
                response_data["grade"] = evaluation_result.get('grade', 0.0)
                response_data["proficiency"] = evaluation_result.get('proficiency', 0.0)
                response_data["classification"] = evaluation_result.get('classification', 'Não definido')
                response_data["evaluation_result_id"] = evaluation_result.get('id')
                response_data["score_percentage"] = evaluation_result.get('score_percentage', percentage)
                response_data["correct_answers"] = correct_count
                response_data["total_questions"] = total_count
            else:
                # Fallback se não conseguir calcular
                self.logger.warning("EvaluationResultService não retornou resultado")
                response_data["grade"] = (correct_count / total_count * 10) if total_count > 0 else 0.0
                response_data["proficiency"] = 0.0
                response_data["classification"] = "Não calculado"
                response_data["evaluation_result_id"] = None
                response_data["score_percentage"] = percentage
                response_data["correct_answers"] = correct_count
                response_data["total_questions"] = total_count
            
            # 15. Marcar formulário físico como corrigido
            self._marcar_formulario_como_corrigido(test_id, student_id)
            
            return response_data
            
        except Exception as e:
            self.logger.error(f"Erro na correção sem IA: {str(e)}", exc_info=True)
            return {"success": False, "error": f"Erro interno: {str(e)}"}
    
    def _decode_image(self, image_data: bytes) -> Optional[np.ndarray]:
        """Decodifica imagem de bytes para numpy array"""
        try:
            print(f"🔍 [DEBUG _decode_image] Decodificando {len(image_data)} bytes...")
            nparr = np.frombuffer(image_data, np.uint8)
            print(f"🔍 [DEBUG _decode_image] Array numpy criado: {len(nparr)} elementos")
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                print("❌ [DEBUG _decode_image] cv2.imdecode retornou None - formato de imagem inválido")
            else:
                print(f"✅ [DEBUG _decode_image] Imagem decodificada: shape={img.shape}, dtype={img.dtype}")
            return img
        except Exception as e:
            print(f"❌ [DEBUG _decode_image] Exceção ao decodificar: {str(e)}")
            self.logger.error(f"Erro ao decodificar imagem: {str(e)}")
            return None
    
    def _detectar_qr_code_adaptado(self, img: np.ndarray) -> Optional[Dict[str, str]]:
        """
        Detecta QR Code adaptado para suportar formato antigo e JSON
        Tenta primeiro formato antigo (leQr), depois formato JSON
        """
        try:
            print(f"🔍 [DEBUG _detectar_qr_code] Iniciando detecção de QR code...")
            print(f"🔍 [DEBUG _detectar_qr_code] Dimensões da imagem: {img.shape}")
            
            # Tentar formato antigo primeiro (sistema test_correction)
            print("🔍 [DEBUG _detectar_qr_code] Tentando formato antigo (leQr)...")
            qr_result_antigo = leQr(img)
            print(f"🔍 [DEBUG _detectar_qr_code] Resultado de leQr: {qr_result_antigo}")
            
            if qr_result_antigo and 'id_aluno' in qr_result_antigo:
                print(f"✅ [DEBUG _detectar_qr_code] QR Code detectado no formato antigo!")
                # Converter formato antigo para novo
                result = {
                    'student_id': str(qr_result_antigo['id_aluno']),
                    'test_id': str(qr_result_antigo.get('id_prova', ''))
                }
                print(f"✅ [DEBUG _detectar_qr_code] Resultado convertido: {result}")
                return result
            else:
                print("⚠️ [DEBUG _detectar_qr_code] leQr não encontrou QR code válido")
            
            # Tentar formato JSON (sistema atual)
            try:
                import pyzbar.pyzbar as pyzbar_module
                pyzbar_available = True
                print("✅ [DEBUG _detectar_qr_code] pyzbar disponível")
            except ImportError:
                print("⚠️ [DEBUG _detectar_qr_code] pyzbar não disponível")
                self.logger.debug("pyzbar não disponível, tentando apenas cv2.QRCodeDetector")
                pyzbar_available = False
            
            if pyzbar_available:
                try:
                    print("🔍 [DEBUG _detectar_qr_code] Tentando pyzbar para formato JSON...")
                    im_gray = cv2.split(cv2.cvtColor(img, cv2.COLOR_BGR2HSV))[2]
                    _, im_bw = cv2.threshold(im_gray, 0, 255, cv2.THRESH_OTSU | cv2.THRESH_BINARY)
                    
                    qr_info = pyzbar_module.decode(im_bw)
                    print(f"🔍 [DEBUG _detectar_qr_code] pyzbar encontrou {len(qr_info)} QR code(s)")
                    
                    for obj in qr_info:
                        try:
                            text = obj.data.decode('utf-8')
                            print(f"🔍 [DEBUG _detectar_qr_code] Texto do QR code (pyzbar): '{text}' (tamanho: {len(text)})")
                            # Tentar parsear como JSON
                            qr_json = json.loads(text)
                            if 'student_id' in qr_json:
                                result = {
                                    'student_id': str(qr_json['student_id']),
                                    'test_id': str(qr_json.get('test_id', ''))
                                }
                                print(f"✅ [DEBUG _detectar_qr_code] QR Code JSON detectado: {result}")
                                return result
                        except (json.JSONDecodeError, UnicodeDecodeError) as e:
                            print(f"⚠️ [DEBUG _detectar_qr_code] Erro ao parsear como JSON: {str(e)}")
                            # Se não for JSON, tentar formato antigo
                            continue
                except Exception as e:
                    print(f"❌ [DEBUG _detectar_qr_code] Erro ao usar pyzbar: {str(e)}")
                    self.logger.debug(f"Erro ao usar pyzbar: {str(e)}")
            
            # Tentar também com cv2.QRCodeDetector
            print("🔍 [DEBUG _detectar_qr_code] Tentando cv2.QRCodeDetector...")
            detector = cv2.QRCodeDetector()
            data, _, _ = detector.detectAndDecode(img)
            if data:
                print(f"🔍 [DEBUG _detectar_qr_code] cv2.QRCodeDetector encontrou: '{data}' (tamanho: {len(data)})")
                try:
                    qr_json = json.loads(data)
                    if 'student_id' in qr_json:
                        result = {
                            'student_id': str(qr_json['student_id']),
                            'test_id': str(qr_json.get('test_id', ''))
                        }
                        print(f"✅ [DEBUG _detectar_qr_code] QR Code JSON detectado (cv2): {result}")
                        return result
                except json.JSONDecodeError as e:
                    print(f"⚠️ [DEBUG _detectar_qr_code] Erro ao parsear JSON do cv2: {str(e)}")
            else:
                print("⚠️ [DEBUG _detectar_qr_code] cv2.QRCodeDetector não encontrou QR code")
            
            print("❌ [DEBUG _detectar_qr_code] Nenhum QR code válido encontrado")
            return None
            
        except Exception as e:
            print(f"❌ [DEBUG _detectar_qr_code] Exceção: {str(e)}")
            self.logger.error(f"Erro ao detectar QR Code: {str(e)}")
            return None
    
    def _buscar_gabarito_adaptado(self, test_id: str) -> Tuple[Dict[int, str], int, int]:
        """
        Busca gabarito do teste no banco de dados (adaptado do sistema antigo)
        Retorna: (gabarito_dict, num_questions, num_alternatives)
        """
        try:
            test_questions = TestQuestion.query.filter_by(test_id=test_id).order_by(TestQuestion.order).all()
            
            gabarito_dict = {}
            num_questions = len(test_questions)
            num_alternatives = 4  # Padrão: A, B, C, D
            
            for idx, tq in enumerate(test_questions, start=1):
                question = Question.query.get(tq.question_id)
                if question and question.correct_answer:
                    # Converter A, B, C, D para 1, 2, 3, 4
                    answer_letter = question.correct_answer.upper()
                    if answer_letter in ['A', 'B', 'C', 'D']:
                        answer_num = ord(answer_letter) - ord('A') + 1
                        gabarito_dict[idx] = {
                            'question_num': idx,
                            'answer_num': answer_num,
                            'answer_letter': answer_letter,
                            'weight': question.value or 1.0
                        }
            
            return gabarito_dict, num_questions, num_alternatives
            
        except Exception as e:
            self.logger.error(f"Erro ao buscar gabarito: {str(e)}")
            return {}, 0, 0
    
    def _converter_gabarito_para_formato_antigo(self, gabarito_dict: Dict[int, Dict]) -> List[Tuple[int, int, float]]:
        """
        Converte gabarito do formato atual para formato do sistema antigo
        Formato antigo: [(n_questao, opcao, peso), ...]
        """
        gabarito_antigo = []
        for q_num, q_data in gabarito_dict.items():
            gabarito_antigo.append((
                q_data['question_num'],
                q_data['answer_num'],
                q_data['weight']
            ))
        return gabarito_antigo
    
    def _converter_respostas_para_formato_atual(self, answ_clear: List[int], num_questions: int) -> Dict[int, Optional[str]]:
        """
        Converte respostas do formato antigo para formato atual
        Formato antigo: [1, 2, -1, 4, ...] onde 1-4 = A-D, -1 = não marcada
        Formato atual: {1: "A", 2: "B", 3: None, 4: "D", ...}
        """
        respostas = {}
        letras = ['A', 'B', 'C', 'D']
        
        for i in range(num_questions):
            q_num = i + 1
            if i < len(answ_clear):
                answer_num = answ_clear[i]
                if answer_num > 0 and answer_num <= 4:
                    respostas[q_num] = letras[answer_num - 1]
                else:
                    respostas[q_num] = None
            else:
                respostas[q_num] = None
        
        return respostas
    
    def _calcular_correcao(self, answers: Dict[int, Optional[str]], gabarito: Dict[int, Dict]) -> Dict[str, Any]:
        """
        Calcula estatísticas de correção
        """
        total_questions = len(gabarito)
        answered = 0
        correct = 0
        incorrect = 0
        unanswered = 0
        
        for q_num in range(1, total_questions + 1):
            detected = answers.get(q_num)
            correct_data = gabarito.get(q_num)
            
            if not detected:
                unanswered += 1
            elif correct_data and detected == correct_data.get('answer_letter'):
                correct += 1
                answered += 1
            else:
                incorrect += 1
                answered += 1
        
        score_percentage = (correct / total_questions * 100) if total_questions > 0 else 0.0
        
        return {
            "total_questions": total_questions,
            "answered": answered,
            "correct": correct,
            "incorrect": incorrect,
            "unanswered": unanswered,
            "score_percentage": round(score_percentage, 2)
        }
    
    def _criar_detalhes(self, answers: Dict[int, Optional[str]], gabarito: Dict[int, Dict], warnings: List[str]) -> Dict[str, Any]:
        """
        Cria dicionário de detalhes para cada questão
        """
        details = {}
        warnings_dict = {}
        
        # Processar warnings
        for warning in warnings:
            # Formato: "Nenhuma ou mais de uma opção foi marcada na questão X"
            if "questão" in warning.lower():
                try:
                    q_num = int(warning.split("questão")[1].strip())
                    warnings_dict[q_num] = warning
                except:
                    pass
        
        for q_num, detected_answer in answers.items():
            correct_data = gabarito.get(q_num, {})
            correct_answer = correct_data.get('answer_letter', '')
            
            is_correct = None
            if detected_answer and correct_answer:
                is_correct = (detected_answer.upper() == correct_answer.upper())
            
            details[str(q_num)] = {
                "detected": detected_answer,
                "correct": correct_answer,
                "is_correct": is_correct,
                "confidence": 0.95 if detected_answer else 0.0,  # Sistema sem IA não tem confiança real
                "warning": warnings_dict.get(q_num)
            }
        
        return details
    
    def _salvar_respostas_no_banco(self, test_id: str, student_id: str,
                                   respostas_detectadas: Dict[int, Optional[str]],
                                   gabarito: Dict[int, Dict]) -> List[Dict[str, Any]]:
        """
        Salva respostas detectadas no banco de dados
        """
        try:
            # Buscar questões do teste
            test_questions = TestQuestion.query.filter_by(test_id=test_id).order_by(TestQuestion.order).all()
            
            # Criar mapeamento: índice sequencial -> test_question
            questions_by_index = {}
            for idx, tq in enumerate(test_questions, start=1):
                questions_by_index[idx] = tq
            
            saved_answers = []
            
            for q_num, detected_answer in respostas_detectadas.items():
                if q_num not in questions_by_index:
                    continue
                
                test_question = questions_by_index[q_num]
                question_id = test_question.question_id
                correct_data = gabarito.get(q_num, {})
                correct_answer = correct_data.get('answer_letter', '')
                
                # Verificar se está correta
                is_correct = None
                if detected_answer and correct_answer:
                    is_correct = (detected_answer.upper() == correct_answer.upper())
                
                # Verificar se já existe resposta
                existing_answer = StudentAnswer.query.filter_by(
                    student_id=student_id,
                    test_id=test_id,
                    question_id=question_id
                ).first()
                
                if existing_answer:
                    # Atualizar resposta existente
                    existing_answer.answer = detected_answer if detected_answer else ''
                    existing_answer.is_correct = is_correct
                    existing_answer.answered_at = datetime.utcnow()
                    student_answer = existing_answer
                else:
                    # Criar nova resposta
                    student_answer = StudentAnswer(
                        student_id=student_id,
                        test_id=test_id,
                        question_id=question_id,
                        answer=detected_answer if detected_answer else '',
                        is_correct=is_correct
                    )
                    db.session.add(student_answer)
                
                saved_answers.append({
                    'question_number': q_num,
                    'question_id': question_id,
                    'detected_answer': detected_answer,
                    'correct_answer': correct_answer,
                    'is_correct': is_correct
                })
            
            # Commit
            db.session.commit()
            
            return saved_answers
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Erro ao salvar respostas: {str(e)}", exc_info=True)
            return []
    
    def _criar_sessao_temporaria_para_correcao_fisica(self, test_id: str, student_id: str) -> Optional[str]:
        """
        Cria uma sessão temporária (TestSession) para correções físicas
        """
        try:
            # Verificar se já existe uma sessão para esta correção física
            existing_session = TestSession.query.filter_by(
                test_id=test_id,
                student_id=student_id,
                status='corrigida'
            ).first()
            
            if existing_session:
                return existing_session.id
            
            # Criar nova sessão temporária para correção física
            session = TestSession(
                student_id=student_id,
                test_id=test_id,
                time_limit_minutes=None,
                ip_address=None,
                user_agent='Physical Test Correction (OMR)',  # Identificador de correção física sem IA
                status='corrigida',
                started_at=datetime.utcnow(),
                submitted_at=datetime.utcnow()
            )
            
            db.session.add(session)
            db.session.commit()
            
            return session.id
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Erro ao criar sessão temporária: {str(e)}", exc_info=True)
            return None
    
    def _marcar_formulario_como_corrigido(self, test_id: str, student_id: str) -> bool:
        """
        Marca o PhysicalTestForm como corrigido após processar a correção
        """
        try:
            # Buscar formulário físico do aluno para esta prova
            form = PhysicalTestForm.query.filter_by(
                test_id=test_id,
                student_id=student_id
            ).first()
            
            if not form:
                self.logger.warning(f"Formulário físico não encontrado para test_id={test_id}, student_id={student_id}")
                return False
            
            # Marcar como enviado (se ainda não foi marcado)
            if not form.answer_sheet_sent_at:
                form.answer_sheet_sent_at = datetime.utcnow()
            
            # Marcar como corrigido
            form.is_corrected = True
            form.corrected_at = datetime.utcnow()
            form.status = 'corrigido'
            
            db.session.commit()
            
            return True
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Erro ao marcar formulário como corrigido: {str(e)}", exc_info=True)
            return False

