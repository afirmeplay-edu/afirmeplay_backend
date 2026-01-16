# -*- coding: utf-8 -*-
"""
Nova Implementação de Correção de Cartões Resposta
Baseado no repositório OMR com adaptações:
- Duplo ROI: triângulos + blocos com borda preta
- Agrupamento por coordenada Y (linhas) ao invés de quantidade fixa
- Bolhas de 15px
- Suporta questões com 2, 3, 4 ou mais alternativas
"""

import cv2
import numpy as np
import json
import logging
import os
from typing import Dict, List, Optional, Tuple, Any
from app import db
from app.models.student import Student
from app.models.answerSheetGabarito import AnswerSheetGabarito
from app.models.answerSheetResult import AnswerSheetResult
from datetime import datetime


class AnswerSheetCorrectionN:
    """
    Nova implementação de correção com duplo ROI e agrupamento por linha
    """
    
    # Constantes para detecção de bolhas (baseado no código OMR original)
    BUBBLE_MIN_SIZE = 20  # Tamanho mínimo (px) - igual ao OMR original
    BUBBLE_MAX_SIZE = 50  # Tamanho máximo (px) - aumentado para ser mais flexível
    BUBBLE_TARGET_SIZE = 15  # Tamanho alvo (px)
    ASPECT_RATIO_MIN = 0.9  # Aspect ratio mínimo - igual ao OMR original
    ASPECT_RATIO_MAX = 1.1  # Aspect ratio máximo - igual ao OMR original
    
    # Threshold para agrupamento por linha
    LINE_Y_THRESHOLD = 8  # Reduzido de 15 para 8px - mais preciso para separar questões
    
    # Threshold mínimo de pixels brancos para considerar bolha marcada
    # REMOVIDO: O código OMR original não usa threshold, sempre seleciona a bolha com mais pixels
    # MIN_MARKED_PIXELS = 30  # Desabilitado - seguindo lógica do OMR original
    
    def __init__(self, debug: bool = False):
        """
        Inicializa o serviço de correção
        
        Args:
            debug: Se True, gera logs detalhados e salva imagens de debug
        """
        self.debug = debug
        self.save_debug_images = False  # Desativado: não salvar imagens de debug por padrão
        self.logger = logging.getLogger(__name__)
        self.debug_dir = "debug_corrections"
        self.debug_timestamp = None
        self.logger.info("✅ AnswerSheetCorrectionN inicializado (nova implementação)")
        
        # Diretório para arquivos de alinhamento (mesma pasta do módulo)
        self.alignment_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Criar diretório de debug se necessário (apenas se debug estiver ativo)
        if self.save_debug_images:
            if not os.path.exists(self.debug_dir):
                os.makedirs(self.debug_dir)
                self.logger.info(f"📁 Diretório de debug criado: {self.debug_dir}")
    
    def _load_manual_alignment(self, block_num: int = None) -> Optional[Dict]:
        """
        Carrega configuração de alinhamento manual se disponível
        
        Args:
            block_num: Número do bloco
            
        Returns:
            Dict com offset_x e offset_y, ou None se não encontrar
        """
        if block_num is None:
            return None
        
        config_filename = f"block_{block_num:02d}_alignment.json"
        
        # Tentar vários caminhos possíveis (prioridade: pasta do módulo)
        possible_paths = [
            os.path.join(self.alignment_dir, config_filename),  # app/services/cartao_resposta/block_XX_alignment.json (prioridade)
            os.path.join(self.debug_dir, config_filename),  # debug_corrections/block_XX_alignment.json (fallback)
            config_filename,  # Diretório atual (fallback)
        ]
        
        config_path = None
        for path in possible_paths:
            if os.path.exists(path):
                config_path = path
                break
        
        if not config_path:
            self.logger.debug(f"Bloco {block_num}: Arquivo de alinhamento manual não encontrado")
            return None
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                offset_x_raw = config.get('offset_x', 0)
                offset_y_raw = config.get('offset_y', 0)
                
                # IMPORTANTE: Inverter o sinal dos offsets
                # No script de alinhamento: offset_x = -25 significa "mover imagem real 25px à esquerda para alinhar"
                # Na correção: se a imagem real está 25px à direita da referência, precisamos procurar 25px à direita
                # Portanto: offset_correcao = -offset_script
                offset_x = -offset_x_raw
                offset_y = -offset_y_raw
                
                self.logger.info(f"Bloco {block_num}: Alinhamento manual carregado de {config_path}")
                self.logger.info(f"  Offset do script: X={offset_x_raw:+d}, Y={offset_y_raw:+d}")
                self.logger.info(f"  Offset aplicado na correção: X={offset_x:+d}, Y={offset_y:+d} (sinal invertido)")
                return {
                    'offset_x': offset_x,
                    'offset_y': offset_y
                }
        except Exception as e:
            self.logger.warning(f"Erro ao carregar alinhamento manual de {config_path}: {str(e)}")
            return None
    
    def corrigir_cartao_resposta(self, image_data: bytes) -> Dict[str, Any]:
        """
        Processa correção completa de cartão resposta:
        1. Detecta QR Code (gabarito_id + student_id)
        2. Detecta triângulos de alinhamento
        3. Aplica perspectiva transform
        4. Detecta blocos com borda preta (segundo ROI)
        5. Detecta bolhas marcadas em cada bloco
        6. Compara com gabarito
        7. Salva resultado
        
        Args:
            image_data: Imagem em bytes (JPEG/PNG)
            
        Returns:
            Dict com resultados da correção
        """
        try:
            # Criar timestamp único para esta correção
            self.debug_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            
            # 1. Decodificar imagem
            img = self._decode_image(image_data)
            if img is None:
                return {"success": False, "error": "Erro ao decodificar imagem"}
            
            self.logger.info(f"Imagem decodificada: {img.shape}")
            
            # Salvar imagem original
            self._save_debug_image("01_original.jpg", img)
            
            # 2. Detectar QR Code
            qr_result = self._detectar_qr_code(img)
            if not qr_result or 'student_id' not in qr_result:
                return {"success": False, "error": "QR Code não detectado ou inválido"}
            
            student_id = qr_result['student_id']
            gabarito_id_original = qr_result.get('gabarito_id')  # ID original do QR code
            test_id = qr_result.get('test_id')
            
            self.logger.info(f"QR Code detectado: student_id={student_id}, gabarito_id={gabarito_id_original}, test_id={test_id}")
            
            # 3. Validar aluno
            student = Student.query.get(student_id)
            if not student:
                return {"success": False, "error": f"Aluno com ID {student_id} não encontrado no sistema"}
            
            # 4. Buscar gabarito
            # Prioridade: gabarito_id > test_id
            gabarito_obj = None
            gabarito_id = gabarito_id_original  # Inicializar com valor do QR code
            
            if gabarito_id_original:
                gabarito_obj = AnswerSheetGabarito.query.get(gabarito_id_original)
                self.logger.info(f"Buscando gabarito por gabarito_id: {gabarito_id_original}")
            elif test_id:
                # Buscar gabarito pelo test_id (para provas físicas)
                gabarito_obj = AnswerSheetGabarito.query.filter_by(test_id=test_id).first()
                if gabarito_obj:
                    # ✅ CORREÇÃO: Atualizar gabarito_id quando encontrado pelo test_id
                    gabarito_id = str(gabarito_obj.id)
                    self.logger.info(f"Gabarito encontrado por test_id: {test_id}, gabarito_id atualizado: {gabarito_id}")
                else:
                    self.logger.info(f"Buscando gabarito por test_id: {test_id} (não encontrado)")
            
            if not gabarito_obj:
                error_msg = f"Gabarito não encontrado"
                if gabarito_id_original:
                    error_msg += f" (gabarito_id: {gabarito_id_original})"
                if test_id:
                    error_msg += f" (test_id: {test_id})"
                return {"success": False, "error": error_msg}
            
            # 5. Detectar tipo de correção baseado no QR code original
            # Se o QR code tinha gabarito_id → cartão resposta (salvar em answer_sheet_results)
            # Se o QR code só tinha test_id → prova física (salvar em evaluation_results)
            is_physical_test = (gabarito_id_original is None and test_id is not None)
            self.logger.info(f"Tipo de correção detectado: {'Prova Física' if is_physical_test else 'Cartão Resposta'}")
            
            # Converter correct_answers para dict
            correct_answers = gabarito_obj.correct_answers
            if isinstance(correct_answers, str):
                correct_answers = json.loads(correct_answers)
            
            gabarito = {}
            for key, value in correct_answers.items():
                try:
                    q_num = int(key)
                    gabarito[q_num] = str(value).upper() if value else None
                except (ValueError, TypeError):
                    continue
            
            num_questions = gabarito_obj.num_questions
            self.logger.info(f"Gabarito carregado: {num_questions} questões")
            
            # 6. Detectar triângulos e corrigir perspectiva
            img_warped = self._corrigir_perspectiva_com_triangulos(img)
            if img_warped is None:
                return {"success": False, "error": "Não foi possível detectar triângulos de alinhamento"}
            
            self.logger.info(f"Perspectiva corrigida: {img_warped.shape}")
            
            # Salvar imagem com perspectiva corrigida
            self._save_debug_image("02_warped.jpg", img_warped)
            
            # 7. Carregar estrutura do gabarito (se disponível)
            blocks_structure = None
            
            # Tratar blocks_config (pode ser dict, string JSON ou None)
            blocks_config_dict = None
            if gabarito_obj.blocks_config:
                if isinstance(gabarito_obj.blocks_config, str):
                    # Se for string, fazer parse
                    try:
                        blocks_config_dict = json.loads(gabarito_obj.blocks_config)
                        self.logger.debug("blocks_config parseado de string para dict")
                    except json.JSONDecodeError as e:
                        self.logger.error(f"Erro ao fazer parse de blocks_config: {str(e)}")
                elif isinstance(gabarito_obj.blocks_config, dict):
                    blocks_config_dict = gabarito_obj.blocks_config
                else:
                    self.logger.warning(f"blocks_config tem tipo inesperado: {type(gabarito_obj.blocks_config)}")
            
            # Buscar topology (padrão) ou structure (compatibilidade)
            if blocks_config_dict:
                blocks_structure = blocks_config_dict.get('topology')
                if not blocks_structure:
                    # Fallback para 'structure' (compatibilidade com versões antigas)
                    blocks_structure = blocks_config_dict.get('structure')
                    if blocks_structure:
                        self.logger.info("Usando 'structure' (formato antigo) - considere migrar para 'topology'")
            
            if not blocks_structure:
                self.logger.warning("Estrutura completa (topology) não encontrada no gabarito, usando método antigo")
                self.logger.debug(f"blocks_config_dict keys: {blocks_config_dict.keys() if blocks_config_dict else 'None'}")
                # Fallback: usar método antigo de agrupamento
                return self._corrigir_com_metodo_antigo(
                    img_warped, gabarito, num_questions, gabarito_obj, student_id, gabarito_id, test_id, is_physical_test
                )
            
            self.logger.info(f"✅ Estrutura do gabarito carregada: {len(blocks_structure.get('blocks', []))} blocos")
            
            # 8. Detectar blocos com borda preta (segundo ROI)
            answer_blocks, block_contours = self._detectar_blocos_resposta(img_warped)
            if not answer_blocks:
                return {"success": False, "error": "Nenhum bloco de resposta detectado"}
            
            self.logger.info(f"✅ Detectados {len(answer_blocks)} blocos de resposta")
            
            # Salvar imagem com blocos detectados
            img_blocks_debug = img_warped.copy()
            for block_cnt in block_contours:
                cv2.drawContours(img_blocks_debug, [block_cnt], -1, (0, 255, 0), 3)
            self._save_debug_image("03_blocks_detected.jpg", img_blocks_debug)
            
            # 8. Processar cada bloco SEPARADAMENTE usando estrutura do gabarito como guia
            all_answers = {}
            all_bubbles_info = []  # Para desenhar no resultado final
            
            # Criar mapa de blocos da topology por block_id
            topology_blocks_map = {}
            for block_config in blocks_structure.get('blocks', []):
                block_id = block_config.get('block_id', 1)
                topology_blocks_map[block_id] = block_config
            
            self.logger.info(f"Topology tem {len(topology_blocks_map)} blocos: {list(topology_blocks_map.keys())}")
            self.logger.info(f"Imagem detectou {len(answer_blocks)} blocos físicos")
            
            # Processar cada bloco detectado SEPARADAMENTE
            # Salvar offsets dos blocos para ajustar coordenadas na imagem final
            block_offsets = []  # Lista de (x_offset, y_offset) para cada bloco
            
            for block_idx, block_roi in enumerate(answer_blocks):
                block_num_detected = block_idx + 1  # Número do bloco detectado (1, 2, 3...)
                
                self.logger.info(f"═══════════════════════════════════════")
                self.logger.info(f"Processando BLOCO {block_num_detected} (separadamente)")
                self.logger.info(f"═══════════════════════════════════════")
                
                # Calcular offset deste bloco na imagem original
                # O block_roi foi extraído de img_warped, então precisamos saber onde está
                if block_idx < len(block_contours):
                    block_cnt = block_contours[block_idx]
                    x_offset, y_offset, _, _ = cv2.boundingRect(block_cnt)
                    # Ajustar pela margem que foi adicionada
                    margin = 5
                    x_offset = max(0, x_offset - margin)
                    y_offset = max(0, y_offset - margin)
                else:
                    # Se não tem contorno, assumir offset 0,0
                    x_offset, y_offset = 0, 0
                
                block_offsets.append((x_offset, y_offset))
                
                # 1. Buscar topology correspondente a este bloco
                block_ids_sorted = sorted(topology_blocks_map.keys())
                if block_num_detected <= len(block_ids_sorted):
                    block_id_topology = block_ids_sorted[block_num_detected - 1]
                else:
                    self.logger.warning(f"Bloco {block_num_detected} não tem correspondente na topology, usando último bloco")
                    block_id_topology = block_ids_sorted[-1] if block_ids_sorted else 1
                
                block_config = topology_blocks_map.get(block_id_topology)
                if not block_config:
                    self.logger.error(f"Bloco {block_num_detected}: Topology não encontrada para block_id={block_id_topology}")
                    continue
                
                questions_config = block_config.get('questions', [])
                self.logger.info(f"Bloco {block_num_detected} (block_id={block_id_topology}): {len(questions_config)} questões esperadas")
                
                # 2. Criar imagem de referência deste bloco usando topologia
                block_height, block_width = block_roi.shape[:2]
                img_referencia = self._criar_imagem_referencia_bloco(
                    block_config=block_config,
                    correct_answers=gabarito,
                    block_size=(block_width, block_height),
                    block_num=block_num_detected
                )
                
                if img_referencia is None:
                    self.logger.error(f"Bloco {block_num_detected}: Erro ao criar imagem de referência")
                    continue
                
                # 3. Detectar borda e extrair área interna do bloco real
                border_info = self._detectar_borda_bloco(block_roi, block_num_detected)
                
                if border_info is None:
                    self.logger.warning(f"Bloco {block_num_detected}: Borda não detectada, usando bloco completo")
                    # Usar bloco completo se não detectar borda
                    if len(block_roi.shape) == 3:
                        block_inner = cv2.cvtColor(block_roi, cv2.COLOR_BGR2GRAY)
                    else:
                        block_inner = block_roi.copy()
                    border_info = {'border_thickness': 0, 'inner_x': 0, 'inner_y': 0}
                else:
                    # Extrair área interna
                    border_thickness = border_info['border_thickness']
                    if len(block_roi.shape) == 3:
                        block_gray = cv2.cvtColor(block_roi, cv2.COLOR_BGR2GRAY)
                    else:
                        block_gray = block_roi.copy()
                    
                    x = border_info['x']
                    y = border_info['y']
                    w = border_info['w']
                    h = border_info['h']
                    
                    block_inner = block_gray[y+border_thickness:y+h-border_thickness,
                                            x+border_thickness:x+w-border_thickness]
                
                # 4. Redimensionar referência para corresponder ao tamanho do bloco interno
                ref_h, ref_w = img_referencia.shape[:2]
                inner_h, inner_w = block_inner.shape[:2]
                
                # Extrair área interna da referência
                border_thickness = border_info.get('border_thickness', 2)
                ref_inner = img_referencia[border_thickness:ref_h-border_thickness,
                                         border_thickness:ref_w-border_thickness]
                
                # Redimensionar referência interna para corresponder ao bloco interno real
                if ref_inner.shape != block_inner.shape:
                    ref_inner_resized = cv2.resize(ref_inner, 
                                                  (inner_w, inner_h),
                                                  interpolation=cv2.INTER_AREA)
                else:
                    ref_inner_resized = ref_inner
                
                # 5. Comparar usando posições fixas da topologia (sem depender de contornos)
                block_answers, bubbles_info_block = self._comparar_bloco_com_referencia(
                    block_real=block_inner,
                    block_reference=ref_inner_resized,
                    block_config=block_config,
                    correct_answers=gabarito,
                    block_num=block_num_detected,
                    border_info=border_info
                )
                
                # 6. Ajustar coordenadas das bolhas para coordenadas absolutas na imagem completa
                # Coordenadas atuais são relativas ao block_inner, precisamos ajustar para img_warped
                border_thickness = border_info.get('border_thickness', 0)
                block_x_offset = x_offset
                block_y_offset = y_offset
                
                # Se detectou borda, adicionar offset da borda
                if border_info and 'x' in border_info:
                    block_x_offset += border_info['x'] + border_thickness
                    block_y_offset += border_info['y'] + border_thickness
                
                # Ajustar coordenadas de todas as bolhas deste bloco
                for bubble_info in bubbles_info_block:
                    bubble_info['x'] += block_x_offset
                    bubble_info['y'] += block_y_offset
                    # Ajustar contorno também
                    if 'contour' in bubble_info:
                        contour = bubble_info['contour']
                        contour_adjusted = contour + np.array([block_x_offset, block_y_offset])
                        bubble_info['contour'] = contour_adjusted
                
                # 7. Adicionar respostas ao total
                for q_num, answer in block_answers.items():
                    all_answers[q_num] = answer
                
                all_bubbles_info.extend(bubbles_info_block)
                
                self.logger.info(f"Bloco {block_num_detected}: Processamento concluído ({len(block_answers)} questões processadas)")
            
            # 10. Validar respostas (garantir que temos todas as questões)
            validated_answers = {}
            for q_num in range(1, num_questions + 1):
                validated_answers[q_num] = all_answers.get(q_num)
            
            # 11. Calcular correção
            correction = self._calcular_correcao(validated_answers, gabarito)
            
            # 12. Calcular nota, proficiência e classificação
            correct_count = correction['correct']
            total_count = correction['total_questions']
            percentage = correction['score_percentage']
            grade = (correct_count / total_count * 10) if total_count > 0 else 0.0
            
            proficiency, classification = self._calcular_proficiencia_classificacao(
                correct_answers=correct_count,
                total_questions=total_count,
                gabarito_obj=gabarito_obj
            )
            
            # 13. Salvar resultado (detecta automaticamente o tipo)
            saved_result = self._salvar_resultado(
                gabarito_id=gabarito_id,
                student_id=student_id,
                detected_answers=validated_answers,
                correction=correction,
                grade=grade,
                proficiency=proficiency,
                classification=classification,
                test_id=test_id,
                is_physical_test=is_physical_test
            )
            
            # 14. Salvar imagem final com todas as detecções
            self._save_final_result_image(img_warped, all_bubbles_info, validated_answers, gabarito)
            
            # Preparar resposta baseada no tipo
            response = {
                "success": True,
                "student_id": student_id,
                "correct": correct_count,
                "total": total_count,
                "percentage": percentage,
                "answers": validated_answers,
                "correction": correction,
                "grade": grade,
                "proficiency": proficiency,
                "classification": classification,
                "score_percentage": percentage,
                "correct_answers": correct_count,
                "total_questions": total_count,
                "detection_method": "geometric_n_structured"
            }
            
            # Adicionar campos específicos baseado no tipo
            if is_physical_test:
                response["test_id"] = test_id
                response["evaluation_result_id"] = saved_result.get('id') if saved_result else None
            else:
                response["gabarito_id"] = gabarito_id
                response["answer_sheet_result_id"] = saved_result.get('id') if saved_result else None
            
            return response
            
            self.logger.info(f"✅ Total de questões processadas: {len(all_answers)}")
            self.logger.info(f"Respostas detectadas: {all_answers}")
            
            # Salvar imagem final com todas as detecções
            self._save_final_result_image(img_warped, all_bubbles_info, all_answers, gabarito)
            
            # 8. Validar respostas (garantir que temos todas as questões)
            validated_answers = {}
            for q_num in range(1, num_questions + 1):
                validated_answers[q_num] = all_answers.get(q_num)
            
            # 9. Calcular correção
            correction = self._calcular_correcao(validated_answers, gabarito)
            
            # 10. Calcular nota, proficiência e classificação
            correct_count = correction['correct']
            total_count = correction['total_questions']
            percentage = correction['score_percentage']
            grade = (correct_count / total_count * 10) if total_count > 0 else 0.0
            
            proficiency, classification = self._calcular_proficiencia_classificacao(
                correct_answers=correct_count,
                total_questions=total_count,
                gabarito_obj=gabarito_obj
            )
            
            # 11. Salvar resultado
            saved_result = self._salvar_resultado(
                gabarito_id=gabarito_id,
                student_id=student_id,
                detected_answers=validated_answers,
                correction=correction,
                grade=grade,
                proficiency=proficiency,
                classification=classification
            )
            
            return {
                "success": True,
                "student_id": student_id,
                "gabarito_id": gabarito_id,
                "correct": correct_count,
                "total": total_count,
                "percentage": percentage,
                "answers": validated_answers,
                "correction": correction,
                "grade": grade,
                "proficiency": proficiency,
                "classification": classification,
                "answer_sheet_result_id": saved_result.get('id') if saved_result else None,
                "score_percentage": percentage,
                "correct_answers": correct_count,
                "total_questions": total_count,
                "detection_method": "geometric_n"  # Indicador do novo método
            }
            
        except Exception as e:
            self.logger.error(f"Erro na correção: {str(e)}", exc_info=True)
            return {"success": False, "error": f"Erro interno: {str(e)}"}
    
    # ========================================================================
    # FUNÇÕES DE DETECÇÃO
    # ========================================================================
    
    def _decode_image(self, image_data: bytes) -> Optional[np.ndarray]:
        """Decodifica imagem de bytes para numpy array"""
        try:
            nparr = np.frombuffer(image_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            return img
        except Exception as e:
            self.logger.error(f"Erro ao decodificar imagem: {str(e)}")
            return None
    
    def _detectar_qr_code(self, img: np.ndarray) -> Optional[Dict[str, str]]:
        """Detecta QR Code - reutiliza do CorrecaoHybrid"""
        try:
            from app.services.correcao_hybrid import CorrecaoHybrid
            correcao_hybrid = CorrecaoHybrid(debug=self.debug)
            return correcao_hybrid._detectar_qr_code(img)
        except Exception as e:
            self.logger.error(f"Erro ao detectar QR Code: {str(e)}")
            return None
    
    def _corrigir_perspectiva_com_triangulos(self, img: np.ndarray) -> Optional[np.ndarray]:
        """
        Detecta triângulos e aplica correção de perspectiva
        Reutiliza lógica do CorrecaoHybrid
        """
        try:
            from app.services.correcao_hybrid import CorrecaoHybrid
            correcao_hybrid = CorrecaoHybrid(debug=self.debug)
            return correcao_hybrid._paper90(img)
        except Exception as e:
            self.logger.error(f"Erro ao corrigir perspectiva: {str(e)}")
            return None
    
    def _save_debug_image(self, filename: str, img: np.ndarray):
        """Salva imagem de debug no diretório debug_corrections"""
        if not self.save_debug_images or self.debug_timestamp is None:
            return
        
        try:
            filepath = os.path.join(self.debug_dir, f"{self.debug_timestamp}_{filename}")
            cv2.imwrite(filepath, img)
            self.logger.debug(f"💾 Imagem de debug salva: {filepath}")
        except Exception as e:
            self.logger.error(f"Erro ao salvar imagem de debug {filename}: {str(e)}")
    
    def _detectar_blocos_resposta(self, img_warped: np.ndarray) -> Tuple[List[np.ndarray], List]:
        """
        Detecta blocos com borda preta (answer-block)
        Segundo ROI: dentro da área entre triângulos
        
        Args:
            img_warped: Imagem já com perspectiva corrigida
            
        Returns:
            Tuple: (Lista de ROIs, Lista de contornos dos blocos)
        """
        try:
            # Converter para grayscale
            if len(img_warped.shape) == 3:
                gray = cv2.cvtColor(img_warped, cv2.COLOR_BGR2GRAY)
            else:
                gray = img_warped.copy()
            
            # Aplicar blur
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            
            # Detectar bordas usando Canny
            edged = cv2.Canny(blurred, 75, 200)
            
            # Encontrar contornos
            cnts = cv2.findContours(edged.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            cnts = cnts[0] if len(cnts) == 2 else cnts[1]
            
            # Filtrar contornos que são blocos (retângulos grandes com borda)
            img_height, img_width = gray.shape[:2]
            min_block_area = (img_width * img_height) * 0.02  # Pelo menos 2% da imagem
            max_block_area = (img_width * img_height) * 0.5    # No máximo 50% da imagem
            
            block_contours = []
            
            for c in cnts:
                area = cv2.contourArea(c)
                if min_block_area < area < max_block_area:
                    peri = cv2.arcLength(c, True)
                    approx = cv2.approxPolyDP(c, 0.02 * peri, True)
                    
                    # Procurar por retângulos (4 vértices)
                    if len(approx) == 4:
                        x, y, w, h = cv2.boundingRect(approx)
                        aspect_ratio = w / float(h) if h > 0 else 0
                        
                        # Verificar se é um retângulo razoável (não muito alongado)
                        if 0.3 < aspect_ratio < 3.0:
                            block_contours.append(approx)
            
            # Se não encontrou com Canny, tentar threshold adaptativo
            if len(block_contours) == 0:
                self.logger.debug("Canny não encontrou blocos, tentando threshold adaptativo")
                thresh_adapt = cv2.adaptiveThreshold(
                    blurred, 255,
                    cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                    cv2.THRESH_BINARY_INV, 11, 2
                )
                cnts = cv2.findContours(thresh_adapt, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                cnts = cnts[0] if len(cnts) == 2 else cnts[1]
                
                for c in cnts:
                    area = cv2.contourArea(c)
                    if min_block_area < area < max_block_area:
                        peri = cv2.arcLength(c, True)
                        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
                        if len(approx) == 4:
                            x, y, w, h = cv2.boundingRect(approx)
                            aspect_ratio = w / float(h) if h > 0 else 0
                            if 0.3 < aspect_ratio < 3.0:
                                block_contours.append(approx)
            
            # Ordenar blocos da esquerda para direita
            if len(block_contours) > 0:
                block_contours = sorted(block_contours, key=lambda c: cv2.boundingRect(c)[0])
            
            # Extrair ROIs dos blocos
            block_rois = []
            for block_cnt in block_contours:
                x, y, w, h = cv2.boundingRect(block_cnt)
                
                # Adicionar margem pequena
                margin = 5
                x = max(0, x - margin)
                y = max(0, y - margin)
                w = min(img_warped.shape[1] - x, w + 2 * margin)
                h = min(img_warped.shape[0] - y, h + 2 * margin)
                
                block_roi = img_warped[y:y+h, x:x+w]
                block_rois.append(block_roi)
            
            # Se não encontrou blocos, retornar imagem inteira como único bloco
            if not block_rois:
                self.logger.warning("Nenhum bloco detectado, processando imagem inteira")
                block_rois = [img_warped]
                block_contours = []  # Sem contornos se não detectou
            
            return block_rois, block_contours
            
        except Exception as e:
            self.logger.error(f"Erro ao detectar blocos: {str(e)}", exc_info=True)
            return [], []
    
    def _detectar_todas_bolhas(self, block_roi: np.ndarray, block_num: int = None) -> List[Dict]:
        """
        Detecta TODAS as bolhas em um bloco (sem agrupar por questões)
        Retorna apenas lista de bolhas com suas informações
        
        Args:
            block_roi: ROI do bloco
            block_num: Número do bloco (para debug)
            
        Returns:
            Lista de bolhas detectadas
        """
        try:
            # 1. Preprocessar
            if len(block_roi.shape) == 3:
                gray = cv2.cvtColor(block_roi, cv2.COLOR_BGR2GRAY)
            else:
                gray = block_roi.copy()
            
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            
            # Salvar bloco original
            if block_num:
                self._save_debug_image(f"04_block_{block_num:02d}_original.jpg", block_roi)
            
            # 2. Aplicar threshold binário invertido
            thresh = cv2.threshold(blurred, 0, 255, 
                                  cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
            
            # Salvar threshold
            if block_num:
                self._save_debug_image(f"05_block_{block_num:02d}_threshold.jpg", thresh)
            
            # 3. Detectar bolhas (mesma lógica de antes)
            edged_original = cv2.Canny(blurred, 50, 150)
            
            result_original = cv2.findContours(edged_original.copy(), 
                                              cv2.RETR_TREE, 
                                              cv2.CHAIN_APPROX_SIMPLE)
            cnts_original = result_original[0] if len(result_original) == 2 else result_original[1]
            
            result_thresh = cv2.findContours(thresh.copy(), 
                                            cv2.RETR_TREE, 
                                            cv2.CHAIN_APPROX_SIMPLE)
            cnts_thresh = result_thresh[0] if len(result_thresh) == 2 else result_thresh[1]
            
            all_cnts = list(cnts_original) + list(cnts_thresh)
            
            # Remover duplicatas
            unique_cnts = []
            for c in all_cnts:
                (x, y, w, h) = cv2.boundingRect(c)
                center = (x + w//2, y + h//2)
                area = cv2.contourArea(c)
                
                is_duplicate = False
                for existing in unique_cnts:
                    (ex, ey, ew, eh) = cv2.boundingRect(existing)
                    ecenter = (ex + ew//2, ey + eh//2)
                    distance = np.sqrt((center[0] - ecenter[0])**2 + (center[1] - ecenter[1])**2)
                    
                    if distance < 5 and abs(area - cv2.contourArea(existing)) < 50:
                        is_duplicate = True
                        break
                
                if not is_duplicate:
                    unique_cnts.append(c)
            
            # 4. Filtrar bolhas por tamanho e aspect ratio
            bubbles = []
            for c in unique_cnts:
                (x, y, w, h) = cv2.boundingRect(c)
                aspect_ratio = w / float(h) if h > 0 else 0
                
                if (self.BUBBLE_MIN_SIZE <= w <= self.BUBBLE_MAX_SIZE and
                    self.BUBBLE_MIN_SIZE <= h <= self.BUBBLE_MAX_SIZE and
                    self.ASPECT_RATIO_MIN <= aspect_ratio <= self.ASPECT_RATIO_MAX):
                    
                    # Calcular pixels brancos
                    mask = np.zeros(thresh.shape, dtype='uint8')
                    cv2.drawContours(mask, [c], -1, 255, -1)
                    masked_thresh = cv2.bitwise_and(thresh, thresh, mask=mask)
                    pixels_count = cv2.countNonZero(masked_thresh)
                    
                    contour_area = cv2.contourArea(c)
                    fill_ratio = pixels_count / contour_area if contour_area > 0 else 0
                    
                    bubbles.append({
                        'contour': c,
                        'x': x,
                        'y': y + h // 2,  # Centro Y
                        'w': w,
                        'h': h,
                        'pixels': pixels_count,
                        'area': contour_area,
                        'fill_ratio': fill_ratio
                    })
            
            self.logger.info(f"Bloco {block_num or 'único'}: {len(bubbles)} bolhas detectadas")
            return bubbles
            
        except Exception as e:
            self.logger.error(f"Erro ao detectar bolhas: {str(e)}", exc_info=True)
            return []
    
    def _agrupar_bolhas_por_linha_fisica(self, bubbles: List[Dict]) -> List[List[Dict]]:
        """
        Agrupa bolhas APENAS por linha física (Y)
        Não valida número de alternativas - apenas agrupa por proximidade Y
        
        Args:
            bubbles: Lista de todas as bolhas
            
        Returns:
            Lista de linhas, cada uma contendo bolhas daquela linha
        """
        if not bubbles:
            return []
        
        # Ordenar por Y
        bubbles_sorted = sorted(bubbles, key=lambda b: b['y'])
        
        # Calcular threshold adaptativo
        if len(bubbles_sorted) > 1:
            y_distances = []
            for i in range(len(bubbles_sorted) - 1):
                dist = abs(bubbles_sorted[i+1]['y'] - bubbles_sorted[i]['y'])
                if dist > 5:
                    y_distances.append(dist)
            
            if y_distances:
                y_distances_sorted = sorted(y_distances)
                median_distance = y_distances_sorted[len(y_distances_sorted) // 2]
                adaptive_threshold = max(4, min(8, median_distance / 3))
            else:
                adaptive_threshold = self.LINE_Y_THRESHOLD
        else:
            adaptive_threshold = self.LINE_Y_THRESHOLD
        
        # Agrupar por Y (sem validação de número de bolhas)
        linhas = []
        current_line = []
        line_y_values = []
        
        for bubble in bubbles_sorted:
            if line_y_values:
                median_y = sorted(line_y_values)[len(line_y_values) // 2]
            else:
                median_y = None
            
            if median_y is None or abs(bubble['y'] - median_y) <= adaptive_threshold:
                current_line.append(bubble)
                line_y_values.append(bubble['y'])
            else:
                if current_line:
                    linhas.append(current_line)
                current_line = [bubble]
                line_y_values = [bubble['y']]
        
        if current_line:
            linhas.append(current_line)
        
        return linhas
    
    def _decidir_resposta_com_estrutura(self, bolhas_validas: List[Dict],
                                        alternatives_esperadas: List[str],
                                        q_num: int, block_id: int) -> Tuple[Optional[str], List[Dict]]:
        """
        Decide qual bolha está marcada usando estrutura do gabarito
        
        Args:
            bolhas_validas: Lista de bolhas da linha (já ordenadas por X)
            alternatives_esperadas: Lista de alternativas esperadas ['A', 'B', 'C', 'D']
            q_num: Número da questão
            block_id: ID do bloco
            
        Returns:
            Tuple: (resposta detectada, lista de informações das bolhas)
        """
        if not bolhas_validas:
            self.logger.warning(f"Q{q_num}: Nenhuma bolha válida fornecida")
            return None, []
        
        # Encontrar bolha com mais pixels brancos
        bubbled = None
        bubble_pixels = []  # Para debug
        
        for j, bubble in enumerate(bolhas_validas):
            pixels = bubble.get('pixels', 0)
            bubble_pixels.append((j, pixels, alternatives_esperadas[j] if j < len(alternatives_esperadas) else '?'))
            
            if bubbled is None or bubbled[0] < pixels:
                bubbled = (pixels, j)
        
        # Log detalhado
        self.logger.debug(f"Q{q_num} - Pixels por bolha: {[(alt, p) for j, p, alt in bubble_pixels]}")
        
        # Converter índice para alternativa
        if bubbled and bubbled[1] < len(alternatives_esperadas):
            detected_answer = alternatives_esperadas[bubbled[1]]
            self.logger.info(f"✅ Q{q_num}: Resposta detectada = {detected_answer} ({bubbled[0]} pixels) - usando estrutura")
        else:
            detected_answer = None
            self.logger.warning(f"⚠️ Q{q_num}: Índice {bubbled[1] if bubbled else 'None'} fora do range de alternativas esperadas {alternatives_esperadas}")
        
        # Criar informações das bolhas para debug
        bubbles_info = []
        for j, bubble in enumerate(bolhas_validas):
            if j < len(alternatives_esperadas):
                option = alternatives_esperadas[j]
                is_marked = (bubbled and bubbled[1] == j)
                pixels = bubble.get('pixels', 0)
                
                bubbles_info.append({
                    'contour': bubble['contour'],
                    'x': bubble['x'],
                    'y': bubble['y'],
                    'question': q_num,
                    'option': option,
                    'is_marked': is_marked,
                    'pixels': pixels,
                    'was_selected': is_marked
                })
        
        return detected_answer, bubbles_info
    
    def _corrigir_com_metodo_antigo(self, img_warped: np.ndarray, gabarito: Dict[int, str],
                                    num_questions: int, gabarito_obj: AnswerSheetGabarito,
                                    student_id: str, gabarito_id: str,
                                    test_id: Optional[str] = None,
                                    is_physical_test: bool = False) -> Dict[str, Any]:
        """
        Método fallback: correção sem estrutura (método antigo de agrupamento)
        Usa agrupamento por Y com validação
        """
        try:
            # Detectar blocos
            answer_blocks, block_contours = self._detectar_blocos_resposta(img_warped)
            if not answer_blocks:
                return {"success": False, "error": "Nenhum bloco de resposta detectado"}
            
            # Processar cada bloco usando método antigo
            all_answers = {}
            question_counter = 1
            all_bubbles_info = []
            
            for block_idx, block_roi in enumerate(answer_blocks):
                block_answers, bubbles_info = self._processar_bloco(
                    block_roi, 
                    start_question=question_counter,
                    block_num=block_idx + 1
                )
                
                for q_num, answer in block_answers.items():
                    all_answers[q_num] = answer
                    question_counter += 1
                
                all_bubbles_info.extend(bubbles_info)
            
            # Validar e calcular (mesmo processo)
            validated_answers = {}
            for q_num in range(1, num_questions + 1):
                validated_answers[q_num] = all_answers.get(q_num)
            
            correction = self._calcular_correcao(validated_answers, gabarito)
            correct_count = correction['correct']
            total_count = correction['total_questions']
            percentage = correction['score_percentage']
            grade = (correct_count / total_count * 10) if total_count > 0 else 0.0
            
            proficiency, classification = self._calcular_proficiencia_classificacao(
                correct_answers=correct_count,
                total_questions=total_count,
                gabarito_obj=gabarito_obj
            )
            
            saved_result = self._salvar_resultado(
                gabarito_id=str(gabarito_obj.id),
                student_id=student_id,
                detected_answers=validated_answers,
                correction=correction,
                grade=grade,
                proficiency=proficiency,
                classification=classification,
                test_id=test_id,
                is_physical_test=is_physical_test
            )
            
            self._save_final_result_image(img_warped, all_bubbles_info, validated_answers, gabarito)
            
            # Preparar resposta baseada no tipo
            response = {
                "success": True,
                "student_id": student_id,
                "correct": correct_count,
                "total": total_count,
                "percentage": percentage,
                "answers": validated_answers,
                "correction": correction,
                "grade": grade,
                "proficiency": proficiency,
                "classification": classification,
                "score_percentage": percentage,
                "correct_answers": correct_count,
                "total_questions": total_count,
                "detection_method": "geometric_n_legacy"
            }
            
            # Adicionar campos específicos baseado no tipo
            if is_physical_test:
                response["test_id"] = test_id
                response["evaluation_result_id"] = saved_result.get('id') if saved_result else None
            else:
                response["gabarito_id"] = str(gabarito_obj.id)
                response["answer_sheet_result_id"] = saved_result.get('id') if saved_result else None
            
            return response
        except Exception as e:
            self.logger.error(f"Erro no método antigo: {str(e)}", exc_info=True)
            return {"success": False, "error": f"Erro no método antigo: {str(e)}"}
    
    def _processar_bloco(self, block_roi: np.ndarray, start_question: int, 
                         block_num: int = None) -> Tuple[Dict[int, Optional[str]], List[Dict]]:
        """
        Processa um bloco de resposta:
        1. Detecta todas as bolhas
        2. Agrupa por linha (coordenada Y)
        3. Detecta qual bolha está marcada em cada linha
        
        Args:
            block_roi: ROI do bloco
            start_question: Número da primeira questão neste bloco
            block_num: Número do bloco (para debug)
            
        Returns:
            Tuple: (Dict {question_num: 'A'|'B'|'C'|'D'|None}, Lista de informações das bolhas)
        """
        try:
            # 1. Preprocessar
            if len(block_roi.shape) == 3:
                gray = cv2.cvtColor(block_roi, cv2.COLOR_BGR2GRAY)
            else:
                gray = block_roi.copy()
            
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            
            # Salvar bloco original
            if block_num:
                self._save_debug_image(f"04_block_{block_num:02d}_original.jpg", block_roi)
            
            # 2. Aplicar threshold binário invertido (para contar pixels depois)
            thresh = cv2.threshold(blurred, 0, 255, 
                                  cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
            
            # Salvar threshold
            if block_num:
                self._save_debug_image(f"05_block_{block_num:02d}_threshold.jpg", thresh)
            
            # 3. Detectar bolhas na IMAGEM ORIGINAL (onde todas têm contorno visível)
            # Usar Canny para detectar bordas das bolhas na imagem original
            edged_original = cv2.Canny(blurred, 50, 150)
            
            # Encontrar contornos na imagem original (não no threshold)
            # Usar RETR_TREE para pegar contornos externos E internos
            result_original = cv2.findContours(edged_original.copy(), 
                                              cv2.RETR_TREE, 
                                              cv2.CHAIN_APPROX_SIMPLE)
            cnts_original = result_original[0] if len(result_original) == 2 else result_original[1]
            
            # Alternativa: também tentar detectar no threshold com RETR_TREE
            # para pegar contornos internos (bolhas preenchidas)
            result_thresh = cv2.findContours(thresh.copy(), 
                                            cv2.RETR_TREE, 
                                            cv2.CHAIN_APPROX_SIMPLE)
            cnts_thresh = result_thresh[0] if len(result_thresh) == 2 else result_thresh[1]
            
            # Combinar contornos de ambas as fontes (remover duplicatas aproximadas)
            all_cnts = list(cnts_original) + list(cnts_thresh)
            self.logger.debug(f"Bloco {block_num or 'único'}: {len(cnts_original)} contornos na imagem original, {len(cnts_thresh)} no threshold")
            
            # Remover contornos muito similares (mesma posição aproximada)
            unique_cnts = []
            for c in all_cnts:
                (x, y, w, h) = cv2.boundingRect(c)
                center = (x + w//2, y + h//2)
                area = cv2.contourArea(c)
                
                # Verificar se já existe contorno similar
                is_duplicate = False
                for existing in unique_cnts:
                    (ex, ey, ew, eh) = cv2.boundingRect(existing)
                    ecenter = (ex + ew//2, ey + eh//2)
                    distance = np.sqrt((center[0] - ecenter[0])**2 + (center[1] - ecenter[1])**2)
                    
                    # Se estão muito próximos (menos de 5px) e tamanho similar, é duplicata
                    if distance < 5 and abs(area - cv2.contourArea(existing)) < 50:
                        is_duplicate = True
                        break
                
                if not is_duplicate:
                    unique_cnts.append(c)
            
            cnts = unique_cnts
            self.logger.debug(f"Bloco {block_num or 'único'}: {len(cnts)} contornos únicos após remoção de duplicatas")
            
            # 4. Filtrar bolhas por tamanho e aspect ratio
            bubbles = []
            all_detected_contours = []  # Para debug: todas as bolhas detectadas
            
            for c in cnts:
                (x, y, w, h) = cv2.boundingRect(c)
                aspect_ratio = w / float(h) if h > 0 else 0
                
                # Filtrar por tamanho (15px ± margem)
                if (self.BUBBLE_MIN_SIZE <= w <= self.BUBBLE_MAX_SIZE and
                    self.BUBBLE_MIN_SIZE <= h <= self.BUBBLE_MAX_SIZE and
                    self.ASPECT_RATIO_MIN <= aspect_ratio <= self.ASPECT_RATIO_MAX):
                    
                    # Calcular pixels brancos no THRESHOLD INVERTIDO
                    # Criar máscara do contorno da bolha
                    mask = np.zeros(thresh.shape, dtype='uint8')
                    cv2.drawContours(mask, [c], -1, 255, -1)
                    
                    # Aplicar máscara no threshold invertido
                    # No threshold invertido: branco = marcado, preto = não marcado
                    masked_thresh = cv2.bitwise_and(thresh, thresh, mask=mask)
                    pixels_count = cv2.countNonZero(masked_thresh)
                    
                    # Debug: também calcular área total do contorno
                    contour_area = cv2.contourArea(c)
                    fill_ratio = pixels_count / contour_area if contour_area > 0 else 0
                    
                    bubbles.append({
                        'contour': c,
                        'x': x,
                        'y': y + h // 2,  # Centro Y
                        'w': w,
                        'h': h,
                        'pixels': pixels_count,  # Pixels brancos no threshold invertido
                        'area': contour_area,
                        'fill_ratio': fill_ratio
                    })
                    
                    all_detected_contours.append({
                        'contour': c,
                        'x': x,
                        'y': y,
                        'w': w,
                        'h': h,
                        'pixels': pixels_count,
                        'area': contour_area,
                        'fill_ratio': fill_ratio
                    })
            
            self.logger.info(f"Bloco {block_num or 'único'}: {len(bubbles)} bolhas detectadas (de {len(cnts)} contornos totais)")
            
            # Salvar imagem mostrando TODAS as bolhas detectadas (antes de determinar qual está marcada)
            if block_num and all_detected_contours:
                img_all_bubbles = block_roi.copy()
                if len(img_all_bubbles.shape) == 2:
                    img_all_bubbles = cv2.cvtColor(img_all_bubbles, cv2.COLOR_GRAY2BGR)
                
                for bubble_data in all_detected_contours:
                    contour = bubble_data['contour']
                    pixels = bubble_data['pixels']
                    x, y = bubble_data['x'], bubble_data['y']
                    w, h = bubble_data['w'], bubble_data['h']
                    
                    # Desenhar contorno roxo para todas as bolhas detectadas
                    cv2.drawContours(img_all_bubbles, [contour], -1, (255, 0, 255), 2)  # Roxo (BGR)
                    
                    # Adicionar texto com número de pixels e fill ratio
                    fill_ratio = bubble_data.get('fill_ratio', 0)
                    text = f"{pixels}px ({fill_ratio:.1%})"
                    cv2.putText(img_all_bubbles, text, (x, y-5), 
                              cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 0, 255), 1)
                
                self._save_debug_image(f"05b_block_{block_num:02d}_all_detected_bubbles.jpg", img_all_bubbles)
            
            # 5. Agrupar bolhas por linha (coordenada Y)
            questions = self._agrupar_bolhas_por_linha(bubbles)
            
            self.logger.debug(f"Bloco: {len(questions)} questões agrupadas")
            
            # Preparar lista de informações das bolhas para debug
            bubbles_info = []
            
            # 6. Detectar resposta marcada em cada questão
            answers = {}
            for q_idx, question_bubbles in enumerate(questions):
                q_num = start_question + q_idx
                
                # Ordenar bolhas da questão por X (esquerda para direita: A, B, C, D...)
                question_bubbles.sort(key=lambda b: b['x'])
                
                # Encontrar bolha mais preenchida
                bubbled = None
                bubble_pixels = []  # Para debug: armazenar pixels de cada bolha
                
                for j, bubble in enumerate(question_bubbles):
                    # Usar pixels já calculados (do threshold invertido)
                    # No threshold invertido: mais pixels brancos = mais marcada
                    if 'pixels' in bubble:
                        total = bubble['pixels']
                    else:
                        # Recalcular se não tiver (não deveria acontecer)
                        mask = np.zeros(thresh.shape, dtype='uint8')
                        cv2.drawContours(mask, [bubble['contour']], -1, 255, -1)
                        masked_thresh = cv2.bitwise_and(thresh, thresh, mask=mask)
                        total = cv2.countNonZero(masked_thresh)
                    
                    bubble_pixels.append((j, total))
                    
                    # Selecionar a bolha com MAIS pixels brancos no threshold invertido
                    if bubbled is None or bubbled[0] < total:
                        bubbled = (total, j)
                
                # Log detalhado de cada bolha da questão
                self.logger.debug(f"Q{q_num} - Pixels por bolha: {[(chr(ord('A')+j), p) for j, p in bubble_pixels]}")
                
                # Converter índice para letra (0=A, 1=B, 2=C, 3=D, ...)
                # SEM THRESHOLD: Sempre seleciona a bolha com mais pixels (igual ao OMR original)
                if bubbled:
                    detected_answer = chr(ord('A') + bubbled[1])
                    answers[q_num] = detected_answer
                    self.logger.info(f"✅ Q{q_num}: Resposta detectada = {detected_answer} ({bubbled[0]} pixels) - SEM THRESHOLD")
                else:
                    answers[q_num] = None
                    self.logger.warning(f"⚠️ Q{q_num}: Nenhuma bolha encontrada para esta questão")
                
                # Armazenar informações para desenho
                for j, bubble in enumerate(question_bubbles):
                    # Obter pixels desta bolha
                    bubble_pixels_count = bubble.get('pixels', 0)
                    if not bubble_pixels_count:
                        mask = np.zeros(thresh.shape, dtype='uint8')
                        cv2.drawContours(mask, [bubble['contour']], -1, 255, -1)
                        mask = cv2.bitwise_and(thresh, thresh, mask=mask)
                        bubble_pixels_count = cv2.countNonZero(mask)
                    
                    # SEM THRESHOLD: is_marked = se foi a bolha selecionada (a com mais pixels)
                    is_marked = (bubbled and bubbled[1] == j)
                    
                    bubbles_info.append({
                        'contour': bubble['contour'],
                        'x': bubble['x'],
                        'y': bubble['y'],
                        'question': q_num,
                        'option': chr(ord('A') + j),
                        'is_marked': is_marked,
                        'pixels': bubble_pixels_count,
                        'was_selected': is_marked  # Mesmo que is_marked agora (sem threshold)
                    })
            
            # Salvar imagem com bolhas detectadas e status (debug detalhado)
            if block_num:
                # Converter para BGR se necessário
                if len(block_roi.shape) == 2:
                    img_bubbles_debug = cv2.cvtColor(block_roi, cv2.COLOR_GRAY2BGR)
                else:
                    img_bubbles_debug = block_roi.copy()
                
                # Desenhar todas as bolhas com cores e informações
                for bubble_info in bubbles_info:
                    is_marked = bubble_info['is_marked']
                    pixels = bubble_info['pixels']
                    was_selected = bubble_info.get('was_selected', False)
                    option = bubble_info['option']
                    q_num = bubble_info['question']
                    
                    # Determinar cor baseado no status (SEM THRESHOLD)
                    if is_marked:
                        # Verde = bolha selecionada (a com mais pixels)
                        color = (0, 255, 0)  # Verde (BGR)
                        thickness = 3
                        status_text = f"✓ {pixels}px (selecionada)"
                    else:
                        # Vermelho = não selecionada
                        color = (0, 0, 255)  # Vermelho (BGR)
                        thickness = 2
                        status_text = f"{pixels}px"
                    
                    # Desenhar contorno
                    contour = bubble_info['contour']
                    cv2.drawContours(img_bubbles_debug, [contour], -1, color, thickness)
                    
                    # Desenhar círculo mais visível ao redor
                    (x, y, w, h) = cv2.boundingRect(contour)
                    center_x = x + w // 2
                    center_y = y + h // 2
                    radius = max(w, h) // 2 + 2
                    cv2.circle(img_bubbles_debug, (center_x, center_y), radius, color, thickness)
                    
                    # Adicionar texto com informações detalhadas
                    label = f"Q{q_num}{option}"
                    cv2.putText(img_bubbles_debug, label, (x, y-15), 
                              cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
                    cv2.putText(img_bubbles_debug, status_text, (x, y+h+15), 
                              cv2.FONT_HERSHEY_SIMPLEX, 0.35, color, 1)
                
                # Adicionar legenda (SEM THRESHOLD)
                legend_y = 20
                cv2.putText(img_bubbles_debug, "Verde=Selecionada (mais pixels) | Vermelho=Nao selecionada | SEM THRESHOLD", 
                          (10, legend_y), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
                cv2.putText(img_bubbles_debug, "Sempre seleciona a bolha com mais pixels (igual OMR original)", 
                          (10, legend_y + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
                
                self._save_debug_image(f"06_block_{block_num:02d}_bubbles_detailed.jpg", img_bubbles_debug)
                
                # Também salvar versão limpa (sem textos, apenas contornos)
                img_bubbles_clean = block_roi.copy()
                if len(img_bubbles_clean.shape) == 2:
                    img_bubbles_clean = cv2.cvtColor(img_bubbles_clean, cv2.COLOR_GRAY2BGR)
                
                for bubble_info in bubbles_info:
                    is_marked = bubble_info['is_marked']
                    color = (0, 255, 0) if is_marked else (0, 0, 255)  # Verde ou Vermelho
                    thickness = 3 if is_marked else 2
                    contour = bubble_info['contour']
                    cv2.drawContours(img_bubbles_clean, [contour], -1, color, thickness)
                    (x, y, w, h) = cv2.boundingRect(contour)
                    center_x = x + w // 2
                    center_y = y + h // 2
                    radius = max(w, h) // 2 + 2
                    cv2.circle(img_bubbles_clean, (center_x, center_y), radius, color, thickness)
                
                self._save_debug_image(f"06_block_{block_num:02d}_bubbles_clean.jpg", img_bubbles_clean)
            
            return answers, bubbles_info
            
        except Exception as e:
            self.logger.error(f"Erro ao processar bloco: {str(e)}", exc_info=True)
            return {}, []
    
    def _agrupar_bolhas_por_linha(self, bubbles: List[Dict]) -> List[List[Dict]]:
        """
        Agrupa bolhas por linha (coordenada Y) com validação
        Bolhas na mesma linha (Y similar) = mesma questão
        Valida que cada grupo tem número razoável de alternativas (2-5)
        
        Args:
            bubbles: Lista de bolhas com {'contour', 'x', 'y', 'w', 'h'}
            
        Returns:
            Lista de questões, cada uma contendo lista de bolhas
        """
        if not bubbles:
            return []
        
        # Ordenar por Y (top-to-bottom)
        bubbles_sorted = sorted(bubbles, key=lambda b: b['y'])
        
        # Calcular distância média entre bolhas para threshold adaptativo
        if len(bubbles_sorted) > 1:
            y_distances = []
            for i in range(len(bubbles_sorted) - 1):
                dist = abs(bubbles_sorted[i+1]['y'] - bubbles_sorted[i]['y'])
                if dist > 5:  # Ignorar distâncias muito pequenas (bolhas da mesma questão)
                    y_distances.append(dist)
            
            if y_distances:
                # Usar mediana das distâncias como referência
                y_distances_sorted = sorted(y_distances)
                median_distance = y_distances_sorted[len(y_distances_sorted) // 2]
                # Threshold adaptativo: 1/3 da distância mediana (mais restritivo), mínimo 4px, máximo 8px
                adaptive_threshold = max(4, min(8, median_distance / 3))
                self.logger.debug(f"Threshold Y adaptativo: {adaptive_threshold:.1f}px (distância mediana: {median_distance:.1f}px)")
            else:
                adaptive_threshold = self.LINE_Y_THRESHOLD
        else:
            adaptive_threshold = self.LINE_Y_THRESHOLD
        
        # Agrupar por proximidade Y com validação durante o agrupamento
        questions = []
        current_question = []
        group_y_values = []  # Para calcular mediana
        
        for bubble in bubbles_sorted:
            # Calcular mediana do Y do grupo atual (mais robusto que média)
            if group_y_values:
                median_y = sorted(group_y_values)[len(group_y_values) // 2]
            else:
                median_y = None
            
            # Verificar se bolha pertence ao grupo atual
            if median_y is None or abs(bubble['y'] - median_y) <= adaptive_threshold:
                # Validar ANTES de adicionar: se grupo já tem 4 bolhas, iniciar nova questão
                if len(current_question) >= 4:
                    # Grupo completo, iniciar nova questão
                    if self._validar_grupo_questao(current_question):
                        questions.append(current_question)
                    else:
                        self.logger.warning(f"Grupo com {len(current_question)} bolhas antes de validar, tentando dividir...")
                        divided_groups = self._dividir_grupo_invalido(current_question)
                        questions.extend(divided_groups)
                    
                    # Iniciar nova questão
                    current_question = [bubble]
                    group_y_values = [bubble['y']]
                else:
                    # Adicionar ao grupo atual
                    current_question.append(bubble)
                    group_y_values.append(bubble['y'])
            else:
                # Nova linha (nova questão) - Y muito diferente
                if current_question:
                    # Validar grupo antes de adicionar
                    if self._validar_grupo_questao(current_question):
                        questions.append(current_question)
                    else:
                        # Se grupo inválido, tentar dividir
                        self.logger.warning(f"Grupo inválido detectado ({len(current_question)} bolhas), tentando dividir...")
                        divided_groups = self._dividir_grupo_invalido(current_question)
                        questions.extend(divided_groups)
                
                # Iniciar nova questão
                current_question = [bubble]
                group_y_values = [bubble['y']]
        
        # Adicionar última questão
        if current_question:
            if self._validar_grupo_questao(current_question):
                questions.append(current_question)
            else:
                self.logger.warning(f"Último grupo inválido ({len(current_question)} bolhas), tentando dividir...")
                divided_groups = self._dividir_grupo_invalido(current_question)
                questions.extend(divided_groups)
        
        # Log de validação
        self.logger.debug(f"Agrupamento: {len(questions)} questões detectadas")
        for i, q in enumerate(questions, 1):
            self.logger.debug(f"  Questão {i}: {len(q)} bolhas")
        
        return questions
    
    def _validar_grupo_questao(self, group: List[Dict]) -> bool:
        """
        Valida se um grupo de bolhas é uma questão válida
        Uma questão válida deve ter entre 2 e 4 alternativas (A, B, C, D)
        
        Args:
            group: Lista de bolhas do grupo
            
        Returns:
            True se válido, False caso contrário
        """
        num_bubbles = len(group)
        # Uma questão válida deve ter entre 2 e 4 alternativas
        return 2 <= num_bubbles <= 4
    
    def _dividir_grupo_invalido(self, group: List[Dict]) -> List[List[Dict]]:
        """
        Divide um grupo inválido (muitas bolhas) em grupos menores
        Usa clustering por Y mais preciso
        
        Args:
            group: Grupo de bolhas que precisa ser dividido
            
        Returns:
            Lista de grupos válidos
        """
        if len(group) <= 4:
            return [group] if self._validar_grupo_questao(group) else []
        
        # Ordenar por Y
        sorted_group = sorted(group, key=lambda b: b['y'])
        
        # Agrupar usando threshold menor (mais restritivo) e mediana
        strict_threshold = 4  # Muito mais restritivo
        subgroups = []
        current_subgroup = []
        subgroup_y_values = []
        
        for bubble in sorted_group:
            # Calcular mediana do Y do subgrupo atual
            if subgroup_y_values:
                median_y = sorted(subgroup_y_values)[len(subgroup_y_values) // 2]
            else:
                median_y = None
            
            # Verificar se bolha pertence ao subgrupo atual
            if median_y is None or abs(bubble['y'] - median_y) <= strict_threshold:
                # Validar ANTES de adicionar: se subgrupo já tem 4 bolhas, iniciar novo
                if len(current_subgroup) >= 4:
                    if self._validar_grupo_questao(current_subgroup):
                        subgroups.append(current_subgroup)
                    current_subgroup = [bubble]
                    subgroup_y_values = [bubble['y']]
                else:
                    current_subgroup.append(bubble)
                    subgroup_y_values.append(bubble['y'])
            else:
                # Nova linha - Y muito diferente
                if current_subgroup and self._validar_grupo_questao(current_subgroup):
                    subgroups.append(current_subgroup)
                current_subgroup = [bubble]
                subgroup_y_values = [bubble['y']]
        
        if current_subgroup and self._validar_grupo_questao(current_subgroup):
            subgroups.append(current_subgroup)
        
        return subgroups
    
    def _save_final_result_image(self, img_warped: np.ndarray, bubbles_info: List[Dict],
                                 answers: Dict[int, Optional[str]], gabarito: Dict[int, str]):
        """
        Salva imagem final com todas as detecções e resultados
        Similar à imagem de exemplo do OMR:
        - Verde = resposta correta
        - Vermelho = resposta incorreta ou não marcada
        - Contornos circulares ao redor de todas as bolhas
        - Score destacado no topo
        """
        if not self.save_debug_images:
            return
        
        try:
            # Converter para BGR se necessário
            if len(img_warped.shape) == 2:
                img_result = cv2.cvtColor(img_warped, cv2.COLOR_GRAY2BGR)
            else:
                img_result = img_warped.copy()
            
            # Calcular estatísticas
            total = len(gabarito)
            correct = sum(1 for q, ans in answers.items() 
                          if ans and gabarito.get(q) == ans)
            percentage = (correct / total * 100) if total > 0 else 0
            
            # Agrupar bolhas por questão para melhor organização
            questions_dict = {}
            for bubble_info in bubbles_info:
                q_num = bubble_info['question']
                if q_num not in questions_dict:
                    questions_dict[q_num] = []
                questions_dict[q_num].append(bubble_info)
            
            # Desenhar todas as bolhas com cores baseadas no resultado
            # Similar à imagem de exemplo: todas as bolhas têm contornos, verde=correto, vermelho=incorreto
            for q_num in sorted(questions_dict.keys()):
                question_bubbles = questions_dict[q_num]
                detected_answer = answers.get(q_num)
                correct_answer = gabarito.get(q_num)
                
                # Ordenar bolhas por alternativa (A, B, C, D...)
                question_bubbles.sort(key=lambda b: b['option'])
                
                for bubble_info in question_bubbles:
                    option = bubble_info['option']
                    is_marked = bubble_info['is_marked']
                    
                    # Determinar cor baseado no resultado (igual à imagem de exemplo)
                    # SEM THRESHOLD: is_marked = se foi a bolha selecionada (a com mais pixels)
                    # Verde = resposta correta selecionada
                    # Vermelho = resposta incorreta selecionada OU não selecionada
                    if is_marked and correct_answer == option:
                        # Resposta correta selecionada - VERDE
                        color = (0, 255, 0)  # Verde (BGR)
                        thickness = 3
                    else:
                        # Resposta incorreta selecionada ou não selecionada - VERMELHO
                        color = (0, 0, 255)  # Vermelho (BGR)
                        thickness = 2
                    
                    # Obter contorno e coordenadas
                    contour = bubble_info['contour']
                    (x, y, w, h) = cv2.boundingRect(contour)
                    center_x = x + w // 2
                    center_y = y + h // 2
                    radius = max(w, h) // 2 + 3  # Raio um pouco maior para melhor visibilidade
                    
                    # Desenhar círculo ao redor da bolha (similar à imagem de exemplo)
                    cv2.circle(img_result, (center_x, center_y), radius, color, thickness)
                    
                    # Também desenhar o contorno original para mais precisão
                    cv2.drawContours(img_result, [contour], -1, color, thickness)
            
            # Adicionar score destacado no topo (similar à imagem de exemplo)
            # Criar retângulo semi-transparente para o fundo do score
            overlay = img_result.copy()
            cv2.rectangle(overlay, (10, 10), (300, 60), (0, 0, 0), -1)
            cv2.addWeighted(overlay, 0.3, img_result, 0.7, 0, img_result)
            
            # Adicionar texto do score em vermelho grande (como na imagem de exemplo)
            score_text = f"{percentage:.2f}%"
            font_scale = 1.2
            font_thickness = 3
            (text_width, text_height), baseline = cv2.getTextSize(
                score_text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, font_thickness
            )
            
            # Desenhar score
            cv2.putText(img_result, score_text, (20, 50), 
                       cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0, 0, 255), font_thickness)
            
            # Adicionar informações adicionais abaixo do score
            info_text = f"Correct: {correct}/{total}"
            cv2.putText(img_result, info_text, (20, 80), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            
            self._save_debug_image("07_final_result.jpg", img_result)
            
            self.logger.info(f"✅ Imagem final de debug salva: {percentage:.2f}% ({correct}/{total} corretas)")
            
        except Exception as e:
            self.logger.error(f"Erro ao salvar imagem final: {str(e)}", exc_info=True)
    
    # ========================================================================
    # FUNÇÕES DE CÁLCULO E SALVAMENTO
    # ========================================================================
    
    def _calcular_correcao(self, answers: Dict[int, Optional[str]], 
                          gabarito: Dict[int, str]) -> Dict[str, Any]:
        """Calcula estatísticas de correção"""
        total_questions = len(gabarito)
        answered = 0
        correct = 0
        incorrect = 0
        unanswered = 0
        
        for q_num in range(1, total_questions + 1):
            detected = answers.get(q_num)
            correct_answer = gabarito.get(q_num)
            
            if not detected:
                unanswered += 1
            elif detected == correct_answer:
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
    
    def _calcular_proficiencia_classificacao(self, correct_answers: int, total_questions: int,
                                            gabarito_obj: AnswerSheetGabarito) -> Tuple[float, str]:
        """
        Calcula proficiência e classificação
        
        Args:
            correct_answers: Número de acertos
            total_questions: Total de questões
            gabarito_obj: Objeto AnswerSheetGabarito com informações do gabarito
            
        Returns:
            Tuple: (proficiência, classificação)
        """
        try:
            from app.services.evaluation_calculator import EvaluationCalculator
            
            # Inferir nome do curso (string) baseado no grade_name
            grade_name = gabarito_obj.grade_name or ''
            course_name = 'Anos Iniciais'  # Padrão
            
            if any(x in grade_name.lower() for x in ['infantil', 'pré', 'pre']):
                course_name = 'Educação Infantil'
            elif any(x in grade_name.lower() for x in ['1º', '2º', '3º', '4º', '5º', 'anos iniciais']):
                course_name = 'Anos Iniciais'
            elif any(x in grade_name.lower() for x in ['6º', '7º', '8º', '9º', 'anos finais']):
                course_name = 'Anos Finais'
            elif any(x in grade_name.lower() for x in ['1º médio', '2º médio', '3º médio', 'ensino médio']):
                course_name = 'Ensino Médio'
            elif 'especial' in grade_name.lower():
                course_name = 'Educação Especial'
            elif 'eja' in grade_name.lower():
                course_name = 'EJA'
            
            # Inferir nome da disciplina (string) baseado no title
            title = gabarito_obj.title or ''
            subject_name = 'Outras'  # Padrão
            
            if 'matemática' in title.lower() or 'matematica' in title.lower():
                subject_name = 'Matemática'
            
            # Calcular proficiência usando os parâmetros corretos
            proficiency = EvaluationCalculator.calculate_proficiency(
                correct_answers=correct_answers,
                total_questions=total_questions,
                course_name=course_name,
                subject_name=subject_name
            )
            
            # Calcular classificação usando os parâmetros corretos
            classification = EvaluationCalculator.determine_classification(
                proficiency=proficiency,
                course_name=course_name,
                subject_name=subject_name
            )
            
            return proficiency, classification
            
        except Exception as e:
            self.logger.error(f"Erro ao calcular proficiência/classificação: {str(e)}", exc_info=True)
            return 0.0, "Não calculado"
    
    def _salvar_respostas_no_banco(self, test_id: str, student_id: str,
                                  respostas_detectadas: Dict[int, Optional[str]],
                                  gabarito: Dict[int, str]) -> List[Dict[str, Any]]:
        """
        Salva respostas detectadas no banco de dados (StudentAnswer)
        Necessário para que EvaluationResultService possa calcular o resultado
        """
        try:
            from app.models.testQuestion import TestQuestion
            from app.models.question import Question
            from app.models.studentAnswer import StudentAnswer
            
            # Buscar questões do teste
            test_questions = TestQuestion.query.filter_by(test_id=test_id).order_by(TestQuestion.order).all()
            
            if not test_questions:
                self.logger.warning(f"Nenhuma questão encontrada para test_id={test_id}")
                return []
            
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
                correct_answer = gabarito.get(q_num, '')
                
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
            self.logger.info(f"✅ {len(saved_answers)} respostas salvas em StudentAnswer")
            
            return saved_answers
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Erro ao salvar respostas no banco: {str(e)}", exc_info=True)
            return []
    
    def _criar_sessao_minima_para_evaluation_result(self, test_id: str, student_id: str) -> Optional[str]:
        """
        Cria uma sessão mínima apenas para satisfazer a foreign key do EvaluationResult
        Não é uma sessão real de teste, apenas um registro técnico
        
        Args:
            test_id: ID da prova
            student_id: ID do aluno
            
        Returns:
            session_id: ID da sessão criada ou None se erro
        """
        try:
            from app.models.testSession import TestSession
            import uuid
            
            # Verificar se já existe uma sessão para esta correção física
            existing_session = TestSession.query.filter_by(
                test_id=test_id,
                student_id=student_id,
                status='corrigida',
                user_agent='Physical Test Correction (CorrectionN)'
            ).first()
            
            if existing_session:
                self.logger.info(f"Sessão existente encontrada: {existing_session.id}")
                return existing_session.id
            
            # Criar nova sessão mínima para correção física
            session = TestSession(
                id=str(uuid.uuid4()),
                student_id=student_id,
                test_id=test_id,
                time_limit_minutes=None,
                ip_address=None,
                user_agent='Physical Test Correction (CorrectionN)',
                status='corrigida',
                started_at=datetime.utcnow(),
                submitted_at=datetime.utcnow()
            )
            
            db.session.add(session)
            db.session.commit()
            
            self.logger.info(f"✅ Sessão mínima criada: {session.id}")
            return session.id
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Erro ao criar sessão mínima: {str(e)}", exc_info=True)
            return None
    
    def _salvar_resultado(self, gabarito_id: str, student_id: str,
                         detected_answers: Dict[int, Optional[str]],
                         correction: Dict[str, Any],
                         grade: float, proficiency: float,
                         classification: str,
                         test_id: Optional[str] = None,
                         is_physical_test: bool = False) -> Optional[Dict[str, Any]]:
        """
        Salva resultado detectando automaticamente o tipo:
        - Se is_physical_test=True → salva em evaluation_results
        - Se is_physical_test=False → salva em answer_sheet_results
        """
        try:
            if is_physical_test and test_id:
                # Prova física: salvar em evaluation_results
                return self._salvar_resultado_evaluation(
                    test_id=test_id,
                    student_id=student_id,
                    detected_answers=detected_answers,
                    correction=correction,
                    grade=grade,
                    proficiency=proficiency,
                    classification=classification
                )
            else:
                # Cartão resposta: salvar em answer_sheet_results
                return self._salvar_resultado_answer_sheet(
                    gabarito_id=gabarito_id,
                    student_id=student_id,
                    detected_answers=detected_answers,
                    correction=correction,
                    grade=grade,
                    proficiency=proficiency,
                    classification=classification
                )
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Erro ao salvar resultado: {str(e)}", exc_info=True)
            return None
    
    def _salvar_resultado_answer_sheet(self, gabarito_id: str, student_id: str,
                                      detected_answers: Dict[int, Optional[str]],
                                      correction: Dict[str, Any],
                                      grade: float, proficiency: float,
                                      classification: str) -> Optional[Dict[str, Any]]:
        """Salva resultado em AnswerSheetResult (cartões resposta)"""
        try:
            # Verificar se já existe resultado
            existing_result = AnswerSheetResult.query.filter_by(
                gabarito_id=gabarito_id,
                student_id=student_id
            ).first()
            
            if existing_result:
                # Atualizar
                existing_result.detected_answers = detected_answers
                existing_result.correct_answers = correction.get('correct', 0)
                existing_result.total_questions = correction.get('total_questions', 0)
                existing_result.incorrect_answers = correction.get('incorrect', 0)
                existing_result.unanswered_questions = correction.get('unanswered', 0)
                existing_result.answered_questions = correction.get('answered', 0)
                existing_result.score_percentage = correction.get('score_percentage', 0.0)
                existing_result.grade = grade
                existing_result.proficiency = proficiency if proficiency > 0 else None
                existing_result.classification = classification
                existing_result.corrected_at = datetime.utcnow()
                existing_result.detection_method = 'geometric_n'
                
                db.session.commit()
                return existing_result.to_dict()
            else:
                # Criar novo
                result = AnswerSheetResult(
                    gabarito_id=gabarito_id,
                    student_id=student_id,
                    detected_answers=detected_answers,
                    correct_answers=correction.get('correct', 0),
                    total_questions=correction.get('total_questions', 0),
                    incorrect_answers=correction.get('incorrect', 0),
                    unanswered_questions=correction.get('unanswered', 0),
                    answered_questions=correction.get('answered', 0),
                    score_percentage=correction.get('score_percentage', 0.0),
                    grade=grade,
                    proficiency=proficiency if proficiency > 0 else None,
                    classification=classification,
                    detection_method='geometric_n'
                )
                
                db.session.add(result)
                db.session.commit()
                return result.to_dict()
                
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Erro ao salvar resultado em answer_sheet_results: {str(e)}", exc_info=True)
            return None
    
    def _salvar_resultado_evaluation(self, test_id: str, student_id: str,
                                    detected_answers: Dict[int, Optional[str]],
                                    correction: Dict[str, Any],
                                    grade: float, proficiency: float,
                                    classification: str) -> Optional[Dict[str, Any]]:
        """
        Salva resultado em evaluation_results (provas físicas)
        Primeiro salva respostas em StudentAnswer, depois calcula EvaluationResult
        """
        try:
            # 1. Buscar gabarito para obter respostas corretas
            gabarito_obj = AnswerSheetGabarito.query.filter_by(test_id=test_id).first()
            if not gabarito_obj:
                self.logger.error(f"Gabarito não encontrado para test_id={test_id}")
                return None
            
            # Converter correct_answers para dict
            correct_answers = gabarito_obj.correct_answers
            if isinstance(correct_answers, str):
                correct_answers = json.loads(correct_answers)
            
            gabarito = {}
            for key, value in correct_answers.items():
                try:
                    q_num = int(key)
                    gabarito[q_num] = str(value).upper() if value else None
                except (ValueError, TypeError):
                    continue
            
            # 2. Salvar respostas do aluno em StudentAnswer
            saved_answers = self._salvar_respostas_no_banco(
                test_id=test_id,
                student_id=student_id,
                respostas_detectadas=detected_answers,
                gabarito=gabarito
            )
            
            if not saved_answers:
                self.logger.warning(f"Nenhuma resposta salva para test_id={test_id}, student_id={student_id}")
            
            # 3. Criar sessão mínima para EvaluationResult
            session_id = self._criar_sessao_minima_para_evaluation_result(
                test_id=test_id,
                student_id=student_id
            )
            
            if not session_id:
                self.logger.warning("Não foi possível criar sessão mínima, continuando sem EvaluationResult")
                return {
                    'id': None,
                    'test_id': test_id,
                    'student_id': student_id,
                    'saved_answers': saved_answers
                }
            
            # 4. Calcular e salvar EvaluationResult usando EvaluationResultService
            from app.services.evaluation_result_service import EvaluationResultService
            
            evaluation_result = EvaluationResultService.calculate_and_save_result(
                test_id=test_id,
                student_id=student_id,
                session_id=session_id
            )
            
            if evaluation_result:
                return {
                    'id': evaluation_result.get('id'),
                    'test_id': test_id,
                    'student_id': student_id,
                    'session_id': session_id,
                    'correct_answers': evaluation_result.get('correct_answers', correction.get('correct', 0)),
                    'total_questions': evaluation_result.get('total_questions', correction.get('total_questions', 0)),
                    'score_percentage': evaluation_result.get('score_percentage', correction.get('score_percentage', 0.0)),
                    'grade': evaluation_result.get('grade', grade),
                    'proficiency': evaluation_result.get('proficiency', proficiency),
                    'classification': evaluation_result.get('classification', classification),
                    'saved_answers': saved_answers
                }
            else:
                self.logger.warning("EvaluationResultService não retornou resultado")
                return {
                    'id': None,
                    'test_id': test_id,
                    'student_id': student_id,
                    'saved_answers': saved_answers
                }
                
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Erro ao salvar resultado em evaluation_results: {str(e)}", exc_info=True)
            return None
    
    # ========================================================================
    # FUNÇÕES DE REFERÊNCIA E COMPARAÇÃO
    # ========================================================================
    
    def _criar_imagem_referencia_bloco(self, block_config: Dict, correct_answers: Dict[int, str],
                                       block_size: Tuple[int, int], block_num: int = None) -> Optional[np.ndarray]:
        """
        Cria imagem de referência de um bloco com bolhas corretas marcadas
        
        Args:
            block_config: Configuração do bloco da topology {'block_id': 1, 'questions': [...]}
            correct_answers: Dict {q_num: 'A'|'B'|'C'|'D'} com respostas corretas
            block_size: (width, height) do bloco real detectado
            block_num: Número do bloco (para debug)
            
        Returns:
            np.ndarray: Imagem de referência (grayscale, 255=branco, 0=preto)
        """
        try:
            width, height = block_size
            questions_config = block_config.get('questions', [])
            
            # Criar imagem branca
            ref_img = np.ones((height, width), dtype=np.uint8) * 255
            
            # Desenhar borda preta (2px) - mesma borda do template
            border_thickness = 2
            cv2.rectangle(ref_img, 
                         (0, 0), 
                         (width - 1, height - 1), 
                         (0, 0, 0), 
                         border_thickness)
            
            # Calcular dimensões internas (área dentro da borda)
            inner_x = border_thickness
            inner_y = border_thickness
            inner_width = width - 2 * border_thickness
            inner_height = height - 2 * border_thickness
            
            # Calcular espaçamentos baseados no template
            # Template: bolhas 15px (alterado de 25px), gap 8px, linha min 33px, padding 8px 10px
            bubble_size_template = 15  # px no template (alterado de 25px para 15px)
            bubble_gap_template = 8    # px no template
            line_height_template = 33  # px no template
            padding_x_template = 10    # px no template
            padding_y_template = 8     # px no template
            
            # Escalar proporcionalmente ao tamanho do bloco real
            # Usar altura como referência principal
            scale_factor = inner_height / (len(questions_config) * line_height_template + 2 * padding_y_template)
            scale_factor = max(0.5, min(2.0, scale_factor))  # Limitar escala
            
            bubble_size = int(bubble_size_template * scale_factor)
            bubble_gap = int(bubble_gap_template * scale_factor)
            line_height = int(line_height_template * scale_factor)
            padding_x = int(padding_x_template * scale_factor)
            padding_y = int(padding_y_template * scale_factor)
            
            # Calcular posições das questões
            start_y = inner_y + padding_y
            
            for q_idx, q_config in enumerate(questions_config):
                q_num = q_config.get('q')
                alternatives_esperadas = q_config.get('alternatives', [])
                correct_answer = correct_answers.get(q_num)
                
                # Posição Y da linha (centro vertical da linha)
                line_y = start_y + q_idx * line_height + line_height // 2
                
                # Calcular largura total necessária para as alternativas
                num_alternatives = len(alternatives_esperadas)
                total_width = num_alternatives * bubble_size + (num_alternatives - 1) * bubble_gap
                
                # Alinhar à esquerda (igual ao CSS: justify-content: flex-start)
                start_x = inner_x + padding_x
                
                # Desenhar bolhas para cada alternativa
                for alt_idx, alt_letter in enumerate(alternatives_esperadas):
                    bubble_x = start_x + alt_idx * (bubble_size + bubble_gap)
                    bubble_center_x = bubble_x + bubble_size // 2
                    bubble_center_y = line_y
                    bubble_radius = bubble_size // 2 - 1
                    
                    # Desenhar contorno da bolha (círculo vazio)
                    cv2.circle(ref_img, 
                              (bubble_center_x, bubble_center_y), 
                              bubble_radius, 
                              (0, 0, 0),  # Preto
                              1)  # Espessura 1px
                    
                    # Se esta é a resposta correta, preencher a bolha
                    if correct_answer == alt_letter:
                        cv2.circle(ref_img,
                                  (bubble_center_x, bubble_center_y),
                                  bubble_radius - 1,
                                  (0, 0, 0),  # Preto (preenchido)
                                  -1)  # Preenchido
            
            # Salvar imagem de referência para debug
            if block_num:
                self._save_debug_image(f"08_block_{block_num:02d}_reference.jpg", ref_img)
            
            self.logger.info(f"Bloco {block_num or 'único'}: Imagem de referência criada ({width}x{height})")
            return ref_img
            
        except Exception as e:
            self.logger.error(f"Erro ao criar imagem de referência: {str(e)}", exc_info=True)
            return None
    
    def _detectar_borda_bloco(self, block_roi: np.ndarray, block_num: int = None) -> Optional[Dict]:
        """
        Detecta borda preta do bloco e retorna informações
        
        Args:
            block_roi: ROI do bloco real
            block_num: Número do bloco (para debug)
            
        Returns:
            Dict com informações da borda ou None se não detectar
        """
        try:
            # Converter para grayscale se necessário
            if len(block_roi.shape) == 3:
                block_gray = cv2.cvtColor(block_roi, cv2.COLOR_BGR2GRAY)
            else:
                block_gray = block_roi.copy()
            
            border_thickness = 2
            
            # Aplicar threshold para detectar borda preta
            _, thresh = cv2.threshold(block_gray, 127, 255, cv2.THRESH_BINARY_INV)
            
            # Encontrar contornos externos
            cnts = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            cnts = cnts[0] if len(cnts) == 2 else cnts[1]
            
            if not cnts:
                return None
            
            # Encontrar maior contorno (deve ser a borda do bloco)
            largest_cnt = max(cnts, key=cv2.contourArea)
            x, y, w, h = cv2.boundingRect(largest_cnt)
            
            # Verificar se o contorno é aproximadamente retangular
            peri = cv2.arcLength(largest_cnt, True)
            approx = cv2.approxPolyDP(largest_cnt, 0.02 * peri, True)
            
            if len(approx) < 4:
                return None
            
            border_info = {
                'x': x,
                'y': y,
                'w': w,
                'h': h,
                'border_thickness': border_thickness,
                'inner_x': x + border_thickness,
                'inner_y': y + border_thickness,
                'inner_w': w - 2 * border_thickness,
                'inner_h': h - 2 * border_thickness
            }
            
            self.logger.debug(f"Bloco {block_num or 'único'}: Borda detectada ({w}x{h})")
            return border_info
            
        except Exception as e:
            self.logger.error(f"Erro ao detectar borda: {str(e)}", exc_info=True)
            return None
    
    def _detectar_primeira_bolha(self, block_real: np.ndarray, expected_x: int, expected_y: int, 
                                 expected_radius: int, block_num: int = None) -> Optional[Tuple[int, int]]:
        """
        Detecta a primeira bolha (Q1A) na imagem real usando detecção de contornos.
        Usa a posição esperada como região de busca para melhorar precisão.
        
        Args:
            block_real: Imagem do bloco real (área interna, sem borda)
            expected_x: Posição X esperada da primeira bolha (centro)
            expected_y: Posição Y esperada da primeira bolha (centro)
            expected_radius: Raio esperado da bolha
            block_num: Número do bloco (para debug)
            
        Returns:
            Tuple (x, y) com posição detectada do centro da primeira bolha, ou None se não detectar
        """
        try:
            # Converter para grayscale se necessário
            if len(block_real.shape) == 3:
                block_gray = cv2.cvtColor(block_real, cv2.COLOR_BGR2GRAY)
            else:
                block_gray = block_real.copy()
            
            h, w = block_gray.shape
            
            # OPÇÃO 1: Ampliar região de busca para compensar grandes desalinhamentos
            # Usar o maior entre: 5x o raio esperado, 20% da largura, ou 20% da altura
            search_radius_base = expected_radius * 5  # Aumentado de 3x para 5x
            search_radius_width = int(w * 0.2)  # 20% da largura do bloco
            search_radius_height = int(h * 0.2)  # 20% da altura do bloco
            search_radius = max(search_radius_base, search_radius_width, search_radius_height)
            
            # Garantir que a região de busca não ultrapasse os limites da imagem
            search_x1 = max(0, expected_x - search_radius)
            search_y1 = max(0, expected_y - search_radius)
            search_x2 = min(w, expected_x + search_radius)
            search_y2 = min(h, expected_y + search_radius)
            
            self.logger.debug(f"Bloco {block_num or 'único'}: Região de busca: raio={search_radius}px (base={search_radius_base}, w%={search_radius_width}, h%={search_radius_height})")
            
            # Extrair região de busca
            search_roi = block_gray[search_y1:search_y2, search_x1:search_x2]
            
            if search_roi.size == 0:
                self.logger.warning(f"Bloco {block_num or 'único'}: Região de busca vazia para primeira bolha")
                return None
            
            # Aplicar blur para suavizar
            blurred = cv2.GaussianBlur(search_roi, (5, 5), 0)
            
            # OPÇÃO 2: Melhorar detecção de bolhas (tanto vazias quanto preenchidas)
            # Método 1: Detectar bordas com Canny (para bolhas vazias)
            edges = cv2.Canny(blurred, 50, 150)
            
            # Método 2: Detectar áreas escuras (para bolhas preenchidas)
            # Aplicar threshold adaptativo para encontrar áreas escuras
            _, thresh_dark = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
            
            # Combinar ambas as detecções
            edges_combined = cv2.bitwise_or(edges, thresh_dark)
            
            # Encontrar contornos
            cnts = cv2.findContours(edges_combined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            cnts = cnts[0] if len(cnts) == 2 else cnts[1]
            
            if not cnts:
                # Tentar método alternativo: usar HoughCircles (com parâmetros relaxados)
                circles = cv2.HoughCircles(
                    blurred,
                    cv2.HOUGH_GRADIENT,
                    dp=1,
                    minDist=expected_radius * 2,
                    param1=50,
                    param2=25,  # Relaxado de 30 para 25 (mais sensível)
                    minRadius=max(3, expected_radius - 8),  # Relaxado: de -5 para -8
                    maxRadius=expected_radius + 15  # Relaxado: de +10 para +15
                )
                
                if circles is not None and len(circles) > 0:
                    # Pegar o círculo mais próximo da posição esperada
                    circles = np.round(circles[0, :]).astype("int")
                    best_circle = None
                    min_dist = float('inf')
                    
                    for (cx, cy, r) in circles:
                        # Converter coordenadas relativas para absolutas
                        abs_cx = search_x1 + cx
                        abs_cy = search_y1 + cy
                        # Calcular distância da posição esperada
                        dist = np.sqrt((abs_cx - expected_x)**2 + (abs_cy - expected_y)**2)
                        if dist < min_dist:
                            min_dist = dist
                            best_circle = (abs_cx, abs_cy)
                    
                    if best_circle and min_dist < search_radius:
                        self.logger.info(f"Bloco {block_num or 'único'}: Primeira bolha detectada via HoughCircles em ({best_circle[0]}, {best_circle[1]}), esperado ({expected_x}, {expected_y}), offset=({best_circle[0]-expected_x}, {best_circle[1]-expected_y})")
                        return best_circle
                
                self.logger.warning(f"Bloco {block_num or 'único'}: Não foi possível detectar primeira bolha")
                return None
            
            # OPÇÃO 2: Relaxar filtros de tamanho e circularidade
            valid_contours = []
            for cnt in cnts:
                area = cv2.contourArea(cnt)
                # Área esperada de um círculo: π * r²
                # Relaxado: de (r-3) a (r+5) para (r-5) a (r+10)
                expected_area_min = np.pi * (expected_radius - 5) ** 2
                expected_area_max = np.pi * (expected_radius + 10) ** 2
                
                # Aceitar contornos com área mínima (mesmo que menores que o esperado)
                min_area_absolute = np.pi * 3 ** 2  # Mínimo absoluto: raio de 3px
                
                if area >= min_area_absolute and area <= expected_area_max:
                    # Verificar circularidade (relaxado de 0.7 para 0.5)
                    peri = cv2.arcLength(cnt, True)
                    if peri > 0:
                        circularity = 4 * np.pi * area / (peri * peri)
                        if circularity > 0.5:  # Relaxado de 0.7 para 0.5
                            valid_contours.append(cnt)
                            self.logger.debug(f"Bloco {block_num or 'único'}: Contorno válido: área={area:.1f}, circularidade={circularity:.2f}")
            
            if not valid_contours:
                self.logger.warning(f"Bloco {block_num or 'único'}: Nenhum contorno válido encontrado para primeira bolha")
                return None
            
            # Pegar o contorno mais próximo da posição esperada
            best_contour = None
            min_dist = float('inf')
            
            for cnt in valid_contours:
                # Calcular centro do contorno
                M = cv2.moments(cnt)
                if M["m00"] != 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                    
                    # Converter coordenadas relativas para absolutas
                    abs_cx = search_x1 + cx
                    abs_cy = search_y1 + cy
                    
                    # Calcular distância da posição esperada
                    dist = np.sqrt((abs_cx - expected_x)**2 + (abs_cy - expected_y)**2)
                    
                    if dist < min_dist:
                        min_dist = dist
                        best_contour = (abs_cx, abs_cy)
            
            if best_contour and min_dist < search_radius:
                self.logger.info(f"Bloco {block_num or 'único'}: Primeira bolha detectada em ({best_contour[0]}, {best_contour[1]}), esperado ({expected_x}, {expected_y}), offset=({best_contour[0]-expected_x}, {best_contour[1]-expected_y})")
                return best_contour
            else:
                self.logger.warning(f"Bloco {block_num or 'único'}: Primeira bolha detectada muito longe da posição esperada (dist={min_dist:.1f}px)")
                return None
            
        except Exception as e:
            self.logger.error(f"Erro ao detectar primeira bolha: {str(e)}", exc_info=True)
            return None
    
    def _comparar_bloco_com_referencia(self, block_real: np.ndarray, block_reference: np.ndarray,
                                      block_config: Dict, correct_answers: Dict[int, str],
                                      block_num: int = None, border_info: Dict = None) -> Tuple[Dict[int, Optional[str]], List[Dict]]:
        """
        Compara bloco real com referência e detecta respostas marcadas
        
        Args:
            block_real: Bloco real alinhado
            block_reference: Imagem de referência
            block_config: Configuração do bloco da topology
            correct_answers: Dict com respostas corretas
            block_num: Número do bloco (para debug)
            border_info: Informações da borda (para calcular offsets)
            
        Returns:
            Tuple: (Dict {q_num: resposta}, Lista de informações das bolhas)
        """
        try:
            answers = {}
            bubbles_info = []
            questions_config = block_config.get('questions', [])
            
            # Garantir que ambas as imagens têm o mesmo tamanho (já devem estar alinhadas)
            ref_h, ref_w = block_reference.shape[:2]
            real_h, real_w = block_real.shape[:2]
            
            if (ref_h, ref_w) != (real_h, real_w):
                block_real = cv2.resize(block_real, (ref_w, ref_h), interpolation=cv2.INTER_AREA)
                real_h, real_w = ref_h, ref_w
            
            # Aplicar threshold na imagem real para análise de densidade
            # Usar threshold adaptativo para melhor detecção de bolhas marcadas
            if len(block_real.shape) == 3:
                block_gray = cv2.cvtColor(block_real, cv2.COLOR_BGR2GRAY)
            else:
                block_gray = block_real.copy()
            
            # Aplicar blur para suavizar
            blurred = cv2.GaussianBlur(block_gray, (5, 5), 0)
            
            # Threshold binário invertido: bolhas marcadas ficam brancas (255)
            _, thresh_real = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
            
            # Calcular dimensões (área interna - sem borda, pois já recebemos área interna)
            # Se border_info existe, usar para calcular offsets, senão assumir sem borda
            border_thickness = border_info.get('border_thickness', 0) if border_info else 0
            inner_x = 0  # Área interna começa em 0 (já está cortada)
            inner_y = 0
            inner_width = real_w
            inner_height = real_h
            
            # Calcular espaçamentos (mesmos da criação da referência)
            # Usar dimensões da área interna para calcular escala
            bubble_size_template = 15  # px no template (alterado de 25px para 15px)
            bubble_gap_template = 8
            line_height_template = 33
            padding_x_template = 10
            padding_y_template = 8
            
            # Calcular escala baseado na altura disponível
            total_height_needed = len(questions_config) * line_height_template + 2 * padding_y_template
            scale_factor = inner_height / total_height_needed if total_height_needed > 0 else 1.0
            scale_factor = max(0.5, min(2.0, scale_factor))  # Limitar escala
            
            bubble_size = int(bubble_size_template * scale_factor)
            bubble_gap = int(bubble_gap_template * scale_factor)
            line_height = int(line_height_template * scale_factor)
            padding_x = int(padding_x_template * scale_factor)
            padding_y = int(padding_y_template * scale_factor)
            
            # Posição inicial Y (dentro da área interna, já considerando padding)
            start_y = inner_y + padding_y
            
            self.logger.debug(f"Bloco {block_num or 'único'}: Escala={scale_factor:.2f}, bubble_size={bubble_size}px, line_height={line_height}px")
            
            # ====================================================================
            # OPÇÃO A: Detectar primeira bolha (Q1A) e usar como referência
            # Com suporte para offsets manuais salvos
            # ====================================================================
            offset_x = 0
            offset_y = 0
            
            # Tentar carregar offset manual se disponível
            manual_offset = self._load_manual_alignment(block_num)
            if manual_offset:
                offset_x = manual_offset.get('offset_x', 0)
                offset_y = manual_offset.get('offset_y', 0)
                self.logger.info(f"Bloco {block_num or 'único'}: Usando offset manual X={offset_x:+d}px, Y={offset_y:+d}px")
            
            if questions_config:
                first_q_config = questions_config[0]
                first_q_alternatives = first_q_config.get('alternatives', [])
                
                if first_q_alternatives:
                    # Calcular posição esperada da primeira bolha (Q1A)
                    first_line_y = start_y + line_height // 2
                    num_first_alternatives = len(first_q_alternatives)
                    total_width_first = num_first_alternatives * bubble_size + (num_first_alternatives - 1) * bubble_gap
                    # Alinhar à esquerda (igual ao CSS: justify-content: flex-start)
                    start_x_expected = inner_x + padding_x
                    
                    # Posição esperada do centro da primeira bolha (Q1A)
                    first_bubble_x_expected = start_x_expected + bubble_size // 2
                    first_bubble_y_expected = first_line_y
                    first_bubble_radius = bubble_size // 2 - 1
                    
                    # Tentar detectar primeira bolha na imagem real (apenas se não tiver offset manual)
                    first_bubble_detected = None
                    if not manual_offset:
                        first_bubble_detected = self._detectar_primeira_bolha(
                            block_real,
                            first_bubble_x_expected,
                            first_bubble_y_expected,
                            first_bubble_radius,
                            block_num
                        )
                        
                        if first_bubble_detected:
                            detected_x, detected_y = first_bubble_detected
                            # Calcular offset
                            offset_x = detected_x - first_bubble_x_expected
                            offset_y = detected_y - first_bubble_y_expected
                            
                            self.logger.info(f"Bloco {block_num or 'único'}: Offset calculado automaticamente: X={offset_x:+d}px, Y={offset_y:+d}px")
                            
                            # Salvar imagem de debug mostrando primeira bolha detectada
                            if self.save_debug_images and block_num is not None:
                                debug_img = block_real.copy()
                                if len(debug_img.shape) == 2:
                                    debug_img = cv2.cvtColor(debug_img, cv2.COLOR_GRAY2BGR)
                                
                                # Desenhar posição esperada (vermelho)
                                cv2.circle(debug_img, 
                                         (first_bubble_x_expected, first_bubble_y_expected),
                                         first_bubble_radius + 2,
                                         (0, 0, 255),  # Vermelho
                                         2)
                                cv2.putText(debug_img, "Esperado", 
                                          (first_bubble_x_expected - 30, first_bubble_y_expected - first_bubble_radius - 5),
                                          cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)
                                
                                # Desenhar posição detectada (verde)
                                cv2.circle(debug_img,
                                         (detected_x, detected_y),
                                         first_bubble_radius + 2,
                                         (0, 255, 0),  # Verde
                                         2)
                                cv2.putText(debug_img, "Detectado",
                                          (detected_x - 30, detected_y - first_bubble_radius - 5),
                                          cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
                                
                                # Desenhar linha conectando esperado e detectado
                                cv2.line(debug_img,
                                       (first_bubble_x_expected, first_bubble_y_expected),
                                       (detected_x, detected_y),
                                       (255, 0, 255),  # Magenta
                                       1)
                                
                                # Adicionar texto com offset
                                offset_text = f"Offset: X={offset_x:+d}, Y={offset_y:+d}"
                                cv2.putText(debug_img, offset_text,
                                          (10, 20),
                                          cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
                                
                                self._save_debug_image(f"09_block_{block_num:02d}_first_bubble_alignment.jpg", debug_img)
                        else:
                            # Se não detectou primeira bolha E não tem offset manual, usar fallback
                            self.logger.warning(f"Bloco {block_num or 'único'}: Não foi possível detectar primeira bolha, usando offset=0")
                            # Fallback: usar offset baseado no template (número da questão = 30px)
                            # Considerando que as bolhas estão mais à esquerda, vamos adicionar um offset fixo
                            # baseado no número da questão (30px) + gap
                            question_num_width = int(30 * scale_factor)  # 30px do template escalado
                            offset_x = question_num_width + int(5 * scale_factor)  # 30px + pequeno gap
                            self.logger.info(f"Bloco {block_num or 'único'}: Usando offset fixo do template: X={offset_x:+d}px")
                    else:
                        # Se tem offset manual, não precisa detectar
                        self.logger.debug(f"Bloco {block_num or 'único'}: Pulando detecção automática (usando offset manual)")
            
            # Processar cada questão
            for q_idx, q_config in enumerate(questions_config):
                q_num = q_config.get('q')
                alternatives_esperadas = q_config.get('alternatives', [])
                
                line_y = start_y + q_idx * line_height + line_height // 2
                num_alternativas = len(alternatives_esperadas)
                total_width = num_alternativas * bubble_size + (num_alternativas - 1) * bubble_gap
                # Alinhar à esquerda (igual ao CSS: justify-content: flex-start)
                start_x = inner_x + padding_x
                
                # Aplicar offset calculado da primeira bolha
                start_x += offset_x
                line_y += offset_y
                
                # Comparar cada bolha
                bubble_densities = []
                
                for alt_idx, alt_letter in enumerate(alternatives_esperadas):
                    bubble_x = start_x + alt_idx * (bubble_size + bubble_gap)
                    bubble_center_x = bubble_x + bubble_size // 2
                    bubble_center_y = line_y
                    bubble_radius = bubble_size // 2 - 1
                    
                    # Extrair ROI da bolha na imagem real usando posição fixa da topologia
                    # Não depende de detecção de contornos - usa posição calculada
                    y1 = max(0, bubble_center_y - bubble_radius)
                    y2 = min(real_h, bubble_center_y + bubble_radius)
                    x1 = max(0, bubble_center_x - bubble_radius)
                    x2 = min(real_w, bubble_center_x + bubble_radius)
                    
                    # Extrair ROI do threshold invertido
                    bubble_roi_thresh = thresh_real[y1:y2, x1:x2]
                    
                    # Também extrair ROI da imagem original (grayscale) para análise de intensidade
                    bubble_roi_original = block_gray[y1:y2, x1:x2]
                    
                    # Calcular densidade de pixels brancos no threshold invertido
                    # No threshold invertido: branco (255) = marcado, preto (0) = não marcado
                    if bubble_roi_thresh.size > 0:
                        white_pixels = cv2.countNonZero(bubble_roi_thresh)
                        total_pixels = bubble_roi_thresh.size
                        density_thresh = white_pixels / total_pixels if total_pixels > 0 else 0
                    else:
                        density_thresh = 0
                    
                    # Calcular intensidade média na imagem original
                    # Bolha marcada = mais escura (menor intensidade média)
                    if bubble_roi_original.size > 0:
                        mean_intensity = np.mean(bubble_roi_original)
                        # Normalizar: 0 (preto) = 1.0, 255 (branco) = 0.0
                        intensity_score = 1.0 - (mean_intensity / 255.0)
                    else:
                        intensity_score = 0
                    
                    # Combinar ambas as métricas (densidade de threshold + intensidade)
                    # Peso maior para threshold (mais confiável)
                    density = (density_thresh * 0.7) + (intensity_score * 0.3)
                    
                    bubble_densities.append((alt_idx, alt_letter, density))
                
                # Selecionar bolha com maior densidade (mais marcada)
                bubble_densities.sort(key=lambda x: x[2], reverse=True)
                selected_idx, selected_letter, selected_density = bubble_densities[0]
                
                # Apenas considerar marcada se densidade for acima de um threshold mínimo
                # Threshold mais baixo porque agora usamos posições fixas (não depende de contornos)
                min_density_threshold = 0.10  # 10% da área preenchida (reduzido de 15%)
                
                # Log detalhado de todas as densidades
                self.logger.debug(f"Q{q_num} - Densidades: {[(alt, f'{d:.2%}') for _, alt, d in bubble_densities]}")
                
                if selected_density >= min_density_threshold:
                    answers[q_num] = selected_letter
                    self.logger.info(f"✅ Q{q_num}: Resposta detectada = {selected_letter} (densidade: {selected_density:.2%})")
                else:
                    answers[q_num] = None
                    self.logger.warning(f"⚠️ Q{q_num}: Nenhuma bolha suficientemente marcada (max: {selected_density:.2%}, threshold: {min_density_threshold:.2%})")
                
                # Criar informações das bolhas para debug
                for alt_idx, alt_letter, density in bubble_densities:
                    # Usar as mesmas posições já calculadas (já com offset aplicado)
                    bubble_x = start_x + alt_idx * (bubble_size + bubble_gap)
                    bubble_center_x = bubble_x + bubble_size // 2
                    bubble_center_y = line_y
                    bubble_radius = bubble_size // 2 - 1
                    
                    is_marked = (alt_idx == selected_idx and selected_density >= min_density_threshold)
                    
                    # Criar contorno aproximado para desenho
                    contour = np.array([
                        [bubble_center_x - bubble_radius, bubble_center_y - bubble_radius],
                        [bubble_center_x + bubble_radius, bubble_center_y - bubble_radius],
                        [bubble_center_x + bubble_radius, bubble_center_y + bubble_radius],
                        [bubble_center_x - bubble_radius, bubble_center_y + bubble_radius]
                    ], dtype=np.int32)
                    
                    bubbles_info.append({
                        'contour': contour,
                        'x': bubble_center_x - bubble_radius,
                        'y': bubble_center_y - bubble_radius,
                        'question': q_num,
                        'option': alt_letter,
                        'is_marked': is_marked,
                        'pixels': int(density * bubble_size * bubble_size * np.pi),
                        'was_selected': is_marked,
                        'density': density
                    })
            
            # Salvar imagem de comparação para debug
            if block_num:
                img_comparison = cv2.cvtColor(block_real, cv2.COLOR_GRAY2BGR)
                
                # Desenhar bolhas detectadas usando posições fixas
                for bubble_info in bubbles_info:
                    color = (0, 255, 0) if bubble_info['is_marked'] else (0, 0, 255)
                    thickness = 3 if bubble_info['is_marked'] else 2
                    
                    # Usar coordenadas da bolha
                    center_x = bubble_info['x'] + bubble_size // 2
                    center_y = bubble_info['y'] + bubble_size // 2
                    bubble_radius = bubble_size // 2 - 1
                    
                    # Desenhar círculo ao redor da bolha
                    cv2.circle(img_comparison, (center_x, center_y), bubble_radius + 3, color, thickness)
                    
                    # Desenhar contorno retangular também
                    contour = bubble_info['contour']
                    cv2.drawContours(img_comparison, [contour], -1, color, thickness)
                    
                    # Adicionar texto com informação
                    q_num = bubble_info['question']
                    option = bubble_info['option']
                    density = bubble_info.get('density', 0)
                    label = f"Q{q_num}{option} {density:.1%}"
                    cv2.putText(img_comparison, label, 
                              (bubble_info['x'], bubble_info['y'] - 5),
                              cv2.FONT_HERSHEY_SIMPLEX, 0.3, color, 1)
                
                # Adicionar legenda
                legend_y = 15
                cv2.putText(img_comparison, "Verde=Marcada | Vermelho=Nao marcada | Posicoes fixas da topologia", 
                          (5, legend_y), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
                
                self._save_debug_image(f"10_block_{block_num:02d}_comparison.jpg", img_comparison)
            
            return answers, bubbles_info
            
        except Exception as e:
            self.logger.error(f"Erro ao comparar bloco: {str(e)}", exc_info=True)
            return {}, []
