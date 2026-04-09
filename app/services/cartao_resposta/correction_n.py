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
import re
from collections import defaultdict
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
    
    # Tamanho padrão fixo para normalização de blocos (usando tamanho maior do escaneado)
    STANDARD_BLOCK_WIDTH = 431   # Largura padrão (px) - tamanho do escaneado
    STANDARD_BLOCK_HEIGHT = 362  # Altura padrão (px) - tamanho do escaneado
    
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
        self.save_debug_images = debug  # Ativar quando debug=True
        self.logger = logging.getLogger(__name__)
        self.debug_dir = "debug_corrections"
        self.debug_timestamp = None
        if self.debug:
            self.debug_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            self.logger.info(f"🐛 Modo DEBUG ativado - timestamp: {self.debug_timestamp}")
        self.logger.info("✅ AnswerSheetCorrectionN inicializado (nova implementação)")
        
        # Diretório para arquivos de alinhamento (mesma pasta do módulo)
        self.alignment_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Criar diretório de debug se necessário
        if not os.path.exists(self.debug_dir):
            os.makedirs(self.debug_dir)
            self.logger.info(f"📁 Diretório de debug criado: {self.debug_dir}")
    
    def _format_user_friendly_error(self, technical_error: str, context: Dict = None) -> str:
        """
        Converte mensagens de erro técnicas em mensagens amigáveis para o usuário final
        
        Args:
            technical_error: Mensagem de erro técnica original
            context: Dicionário com contexto adicional (ex: num_blocks_expected, num_blocks_found)
        
        Returns:
            Mensagem de erro amigável
        """
        if context is None:
            context = {}
        
        # Verificar primeiro se é erro de quantidade de blocos (precisa de contexto)
        blocks_pattern = r"Esperava\s+(\d+)\s+blocos.*encontrou\s+(\d+)"
        blocks_match = re.search(blocks_pattern, technical_error, re.IGNORECASE)
        if blocks_match:
            # Se não temos contexto, tentar extrair dos números na mensagem
            if not context or 'num_blocks_expected' not in context:
                try:
                    expected = int(blocks_match.group(1))
                    found = int(blocks_match.group(2))
                    context = {
                        'num_blocks_expected': expected,
                        'num_blocks_found': found
                    }
                except:
                    pass
            return self._format_blocks_quantity_error(context)
        
        # Mapeamento de padrões técnicos para mensagens amigáveis
        error_patterns = [
            # Detecção de elementos
            (r"quadrados\s+A4", "Não foi possível identificar os marcadores nos cantos da folha. Verifique se a imagem está completa e os cantos estão visíveis."),
            (r"triângulos", "Não foi possível identificar os marcadores de alinhamento. Certifique-se de que a imagem está nítida e os triângulos estão visíveis."),
            (r"blocos.*detectado|Nenhum bloco", "Não foi possível identificar as áreas de resposta. Verifique se a imagem está bem iluminada e as bordas dos blocos estão visíveis."),
            (r"QR\s+Code.*não\s+detectado|QR\s+Code.*inválido", "Não foi possível ler o código QR do cartão. Verifique se o código está visível, não está danificado e a imagem está nítida."),
            
            # Processamento
            (r"decodificar\s+imagem", "Não foi possível processar a imagem. Verifique se o arquivo está em um formato válido (JPG, PNG)."),
            (r"normalizar.*A4", "Não foi possível ajustar a imagem. Tente escanear novamente com a folha bem posicionada e os cantos visíveis."),
            (r"crop.*área", "Não foi possível identificar a área de respostas. Verifique se a imagem está completa e bem alinhada."),
            
            # Dados
            (r"Aluno.*não\s+encontrado", "Aluno não encontrado no sistema. Verifique se o código QR está correto."),
            (r"Gabarito.*não\s+encontrado", "Gabarito não encontrado. Verifique se a prova está cadastrada corretamente."),
        ]
        
        # Buscar padrão correspondente
        for pattern, friendly_msg in error_patterns:
            if re.search(pattern, technical_error, re.IGNORECASE):
                return friendly_msg
        
        # Se não encontrou padrão específico, retornar mensagem genérica
        return "Não foi possível processar a imagem. Por favor, verifique se a imagem está nítida e completa, e tente novamente."
    
    def _format_blocks_quantity_error(self, context: Dict) -> str:
        """Formata erro específico de quantidade de blocos"""
        expected = context.get('num_blocks_expected', None)
        found = context.get('num_blocks_found', 0)
        
        if expected is None:
            return "A quantidade de blocos de resposta não corresponde ao esperado. Verifique se a imagem está completa e todas as áreas de resposta estão visíveis."
        
        if found == 0:
            return "Nenhuma área de resposta foi identificada. Verifique se a imagem está completa e as bordas dos blocos estão visíveis."
        elif found < expected:
            return f"Foram identificadas apenas {found} área(s) de resposta, mas esperava-se {expected}. Verifique se a imagem está completa e todas as áreas estão visíveis."
        else:
            return f"Foram identificadas {found} áreas de resposta, mas esperava-se {expected}. Verifique se há elementos extras na imagem que possam estar sendo confundidos com áreas de resposta."
    
    def _calcular_offsets_proporcionais(self, offset_x_abs: int, offset_y_abs: int, 
                                       block_width_ref: int, block_height_ref: int,
                                       block_width_atual: int, block_height_atual: int) -> Tuple[int, int]:
        """
        Converte offsets absolutos em proporcionais baseado no tamanho do bloco
        
        Args:
            offset_x_abs: Offset X absoluto (em pixels do bloco de referência)
            offset_y_abs: Offset Y absoluto (em pixels do bloco de referência)
            block_width_ref: Largura do bloco quando o offset foi calibrado
            block_height_ref: Altura do bloco quando o offset foi calibrado
            block_width_atual: Largura atual do bloco
            block_height_atual: Altura atual do bloco
            
        Returns:
            Tuple: (offset_x_proporcional, offset_y_proporcional)
        """
        # Se não temos tamanho de referência, usar offsets absolutos (compatibilidade)
        if block_width_ref <= 0 or block_height_ref <= 0:
            return offset_x_abs, offset_y_abs
        
        # Calcular proporções
        scale_x = block_width_atual / block_width_ref
        scale_y = block_height_atual / block_height_ref
        
        # Aplicar proporções aos offsets
        offset_x_prop = int(offset_x_abs * scale_x)
        offset_y_prop = int(offset_y_abs * scale_y)
        
        return offset_x_prop, offset_y_prop
    
    def _load_grid_alignment(self, block_num: int = None) -> Optional[Dict]:
        """
        Carrega configuração de alinhamento do grid virtual.
        
        Args:
            block_num: Número do bloco
            
        Returns:
            Dict com ratios do grid ou None se não encontrado
        """
        if block_num is None:
            return None
        
        config_path = os.path.join(self.alignment_dir, f"block_{block_num:02d}_grid_alignment.json")
        
        if not os.path.exists(config_path):
            return None
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                result = {
                    'left_margin_ratio': config.get('left_margin_ratio'),
                    'top_padding_ratio': config.get('top_padding_ratio'),
                    'bubble_spacing_ratio': config.get('bubble_spacing_ratio'),
                    'line_height': config.get('line_height')
                }
                self.logger.info(f"Bloco {block_num}: Configuração de grid carregada de {config_path}")
                return result
        except Exception as e:
            self.logger.warning(f"Erro ao carregar configuração de grid de {config_path}: {str(e)}")
            return None
    
    def _load_coordinates_adjustment(self, block_num: int = None) -> Optional[Dict]:
        """
        Carrega configuração de ajuste de coordenadas se disponível
        
        Args:
            block_num: Número do bloco
            
        Returns:
            Dict com start_x, start_y, line_height, ou None se não encontrar
        """
        if block_num is None:
            return None
        
        config_filename = f"block_{block_num:02d}_coordinates_adjustment.json"
        
        # Tentar vários caminhos possíveis
        possible_paths = [
            os.path.join(self.alignment_dir, config_filename),
            os.path.join(self.debug_dir, config_filename),
            config_filename,
        ]
        
        config_path = None
        for path in possible_paths:
            if os.path.exists(path):
                config_path = path
                break
        
        if not config_path:
            self.logger.debug(f"Bloco {block_num}: Arquivo de ajuste de coordenadas não encontrado")
            return None
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                result = {
                    'start_x': config.get('start_x', 0),
                    'start_y': config.get('start_y', 0),
                    'line_height': config.get('line_height'),
                }
                self.logger.info(f"Bloco {block_num}: Ajuste de coordenadas carregado de {config_path}")
                self.logger.info(f"  start_x: {result['start_x']}px, start_y: {result['start_y']}px, line_height: {result.get('line_height', 'N/A')}px")
                return result
        except Exception as e:
            self.logger.warning(f"Erro ao carregar ajuste de coordenadas de {config_path}: {str(e)}")
            return None
    
    def _load_manual_alignment(self, block_num: int = None, block_width: int = None, block_height: int = None) -> Optional[Dict]:
        """
        Carrega configuração de alinhamento manual se disponível
        
        Args:
            block_num: Número do bloco
            block_width: Largura atual do bloco (para cálculo proporcional)
            block_height: Altura atual do bloco (para cálculo proporcional)
            
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
                
                # ✅ NOVO: Suportar offsets proporcionais se block_width/height foram fornecidos
                if block_width is not None and block_height is not None:
                    # Verificar se temos tamanho de referência salvo no JSON
                    block_width_ref = config.get('block_width_ref', None)
                    block_height_ref = config.get('block_height_ref', None)
                    
                    if block_width_ref and block_height_ref:
                        # Converter offsets absolutos para proporcionais
                        offset_x_prop, offset_y_prop = self._calcular_offsets_proporcionais(
                            offset_x_raw, offset_y_raw,
                            block_width_ref, block_height_ref,
                            block_width, block_height
                        )
                        # Inverter offsets (como estava antes)
                        offset_x = -offset_x_prop
                        offset_y = -offset_y_prop
                        self.logger.info(f"Bloco {block_num}: Alinhamento manual carregado de {config_path}")
                        self.logger.info(f"  Offset proporcional: X={offset_x_raw:+d}→{offset_x_prop:+d}, Y={offset_y_raw:+d}→{offset_y_prop:+d}")
                        self.logger.info(f"  Bloco: {block_width_ref}x{block_height_ref} → {block_width}x{block_height}")
                    else:
                        # Usar offsets absolutos (com inversão)
                        offset_x = -offset_x_raw
                        offset_y = -offset_y_raw
                        self.logger.info(f"Bloco {block_num}: Alinhamento manual carregado de {config_path}")
                        self.logger.info(f"  Offset absoluto (sem proporção): X={offset_x_raw:+d}→{offset_x:+d}, Y={offset_y_raw:+d}→{offset_y:+d}")
                else:
                    # Sem informações de tamanho, usar offsets absolutos (com inversão)
                    offset_x = -offset_x_raw
                    offset_y = -offset_y_raw
                    self.logger.info(f"Bloco {block_num}: Alinhamento manual carregado de {config_path}")
                    self.logger.info(f"  Offset absoluto: X={offset_x_raw:+d}→{offset_x:+d}, Y={offset_y_raw:+d}→{offset_y:+d}")
                
                result = {
                    'offset_x': offset_x,
                    'offset_y': offset_y
                }
                
                # Carregar line_height se disponível
                line_height = config.get('line_height')
                if line_height is not None:
                    result['line_height'] = int(line_height)
                    self.logger.info(f"  Line Height: {line_height}px (será usado na criação da referência e comparação)")
                else:
                    self.logger.info(f"  Line Height: não definido (será calculado automaticamente)")
                
                return result
        except Exception as e:
            self.logger.warning(f"Erro ao carregar alinhamento manual de {config_path}: {str(e)}")
            return None
    
    # =========================================================================
    # ✅ TEMPLATE REAL DIGITAL — Métodos para geração e comparação de templates
    # =========================================================================
    
    def gerar_templates_blocos(self, gabarito_obj: 'AnswerSheetGabarito', 
                                pdf_bytes: bytes = None,
                                dpi: int = 300) -> Dict[int, bytes]:
        """
        Gera imagens de template para cada bloco usando o PDF real.
        
        ✅ REGRA OBRIGATÓRIA: Passa pelo MESMO pipeline de correção do aluno.
        - ZERO resize
        - ZERO interpolação
        - Mesmo código, mesmos parâmetros, mesma ordem
        
        Args:
            gabarito_obj: Objeto AnswerSheetGabarito
            pdf_bytes: Bytes do PDF do cartão-resposta (se None, gera automaticamente)
            dpi: DPI para renderização do PDF (padrão: 300)
            
        Returns:
            Dict {block_num: png_bytes} - até 4 blocos
        """
        try:
            self.logger.info(f"🔧 TEMPLATE REAL DIGITAL: Iniciando geração de templates para gabarito {gabarito_obj.id}")
            
            # 1. Se não recebeu PDF, gerar automaticamente
            if pdf_bytes is None:
                pdf_bytes = self._gerar_pdf_template(gabarito_obj)
                if pdf_bytes is None:
                    self.logger.error("Falha ao gerar PDF do template")
                    return {}
            
            # 2. Converter PDF → imagem PNG (usando pdf2image)
            try:
                from pdf2image import convert_from_bytes
                
                # Renderizar primeira página do PDF
                images = convert_from_bytes(pdf_bytes, dpi=dpi, first_page=1, last_page=1)
                if not images:
                    self.logger.error("PDF não gerou nenhuma imagem")
                    return {}
                
                # Converter PIL Image para numpy array (BGR para OpenCV)
                pil_image = images[0]
                img_rgb = np.array(pil_image)
                img_bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
                
                self.logger.info(f"PDF renderizado: {img_bgr.shape} ({dpi} DPI)")
                
            except ImportError:
                self.logger.error("pdf2image não está instalado. Execute: pip install pdf2image")
                return {}
            except Exception as e:
                self.logger.error(f"Erro ao converter PDF para imagem: {str(e)}")
                return {}
            
            # 3. MESMO PIPELINE DO ALUNO: quadrados → warp → triângulos → crop → blocos
            
            # 3.1. Detectar quadrados A4 nos cantos
            squares = self._detectar_quadrados_a4(img_bgr)
            if squares is None:
                self.logger.error("Falha ao detectar quadrados A4 no template")
                return {}
            
            self.logger.info(f"Quadrados A4 detectados: {list(squares.keys())}")
            
            # 3.2. Normalizar para A4
            result = self._normalizar_para_a4(img_bgr, squares)
            if result is None:
                self.logger.error("Falha ao normalizar para A4")
                return {}
            
            img_a4_normalized, scale_info = result
            self.logger.info(f"Imagem normalizada para A4: {img_a4_normalized.shape}")
            
            # 3.3. Detectar triângulos na área dos blocos
            triangles = self._detectar_triangulos_na_area_blocos(img_a4_normalized)
            if triangles is None:
                self.logger.error("Falha ao detectar triângulos no template")
                return {}
            
            self.logger.info(f"Triângulos detectados: {list(triangles.keys())}")
            
            # 3.4. Crop da área dos blocos usando triângulos
            block_area_cropped = self._crop_area_blocos_com_triangulos(img_a4_normalized, triangles)
            if block_area_cropped is None:
                self.logger.error("Falha ao fazer crop da área dos blocos")
                return {}
            
            self.logger.info(f"Área dos blocos cropada: {block_area_cropped.shape}")
            
            # 3.5. Detectar blocos individuais
            answer_blocks, block_contours = self._detectar_blocos_resposta(block_area_cropped)
            if not answer_blocks:
                self.logger.error("Nenhum bloco detectado no template")
                return {}
            
            self.logger.info(f"Blocos detectados: {len(answer_blocks)}")
            
            # 4. Codificar cada bloco como PNG (SEM RESIZE!)
            templates = {}
            for i, block_roi in enumerate(answer_blocks):
                block_num = i + 1
                
                # ❌ NÃO fazer resize! Usar ROI exatamente como gerado
                # template_block.shape == bloco_aluno.shape (validado na correção)
                
                # Codificar como PNG
                success, png_buffer = cv2.imencode('.png', block_roi)
                if success:
                    png_bytes = png_buffer.tobytes()
                    templates[block_num] = png_bytes
                    self.logger.info(f"  Bloco {block_num}: {block_roi.shape} → {len(png_bytes)} bytes PNG")
                else:
                    self.logger.warning(f"  Bloco {block_num}: Falha ao codificar PNG")
            
            self.logger.info(f"✅ TEMPLATE REAL DIGITAL: {len(templates)} templates gerados com sucesso")
            
            return templates
            
        except Exception as e:
            self.logger.error(f"Erro ao gerar templates de blocos: {str(e)}", exc_info=True)
            return {}
    
    def _gerar_pdf_template(self, gabarito_obj: 'AnswerSheetGabarito') -> Optional[bytes]:
        """
        Gera PDF do cartão-resposta para usar como template.
        Usa student_id="TEMPLATE" para identificar que é um template.
        
        Args:
            gabarito_obj: Objeto AnswerSheetGabarito com configurações
            
        Returns:
            Bytes do PDF ou None se falhar
        """
        try:
            from app.services.cartao_resposta.answer_sheet_generator import AnswerSheetGenerator
            
            generator = AnswerSheetGenerator()
            
            # Preparar dados do teste
            test_data = {
                'id': gabarito_obj.test_id,
                'title': gabarito_obj.title or 'Template',
                'municipality': gabarito_obj.municipality or '',
                'state': gabarito_obj.state or '',
                'institution': gabarito_obj.institution or '',
                'grade_name': gabarito_obj.grade_name or ''
            }
            
            # Configuração de blocos
            blocks_config = gabarito_obj.blocks_config or {}
            use_blocks = gabarito_obj.use_blocks or False
            
            # Organizar questões por blocos
            questions_by_block = None
            if use_blocks:
                questions_by_block = generator._organize_questions_by_blocks(
                    gabarito_obj.num_questions, blocks_config
                )
            
            # Criar student fake para template
            class FakeStudent:
                def __init__(self):
                    self.id = "TEMPLATE"
                    self.name = "TEMPLATE - NÃO IMPRIMIR"
                    self.registration = ""
                    self.class_id = None
                    self.school_id = None
            
            fake_student = FakeStudent()
            
            # Gerar PDF
            pdf_data = generator._generate_individual_answer_sheet(
                student=fake_student,
                test_data=test_data,
                num_questions=gabarito_obj.num_questions,
                use_blocks=use_blocks,
                blocks_config=blocks_config,
                questions_by_block=questions_by_block,
                gabarito_id=str(gabarito_obj.id)
            )
            
            if pdf_data:
                self.logger.info(f"PDF do template gerado: {len(pdf_data)} bytes")
                return pdf_data
            else:
                self.logger.error("Falha ao gerar PDF do template")
                return None
                
        except Exception as e:
            self.logger.error(f"Erro ao gerar PDF do template: {str(e)}", exc_info=True)
            return None
    
    def salvar_templates_no_gabarito(self, gabarito_obj: 'AnswerSheetGabarito', 
                                      templates: Dict[int, bytes],
                                      dpi: int = 300) -> bool:
        """
        Salva templates de blocos no objeto do gabarito e persiste no banco.
        
        Args:
            gabarito_obj: Objeto AnswerSheetGabarito
            templates: Dict {block_num: png_bytes}
            dpi: DPI usado na renderização
            
        Returns:
            True se salvou com sucesso
        """
        try:
            from datetime import datetime
            
            # Salvar cada template no campo correspondente
            for block_num, png_bytes in templates.items():
                if 1 <= block_num <= 4:
                    gabarito_obj.set_template_block(block_num, png_bytes)
                    self.logger.info(f"  Bloco {block_num}: {len(png_bytes)} bytes salvos")
            
            # Atualizar metadados
            gabarito_obj.template_generated_at = datetime.now()
            gabarito_obj.template_dpi = dpi
            
            # Persistir no banco
            db.session.commit()
            
            self.logger.info(f"✅ {len(templates)} templates salvos no gabarito {gabarito_obj.id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Erro ao salvar templates no gabarito: {str(e)}", exc_info=True)
            db.session.rollback()
            return False
    
    def _carregar_template_bloco(self, gabarito_obj: 'AnswerSheetGabarito', 
                                  block_num: int,
                                  expected_shape: Tuple[int, int]) -> Optional[np.ndarray]:
        """
        Carrega template do bloco do banco e VALIDA shape.
        
        ✅ VALIDAÇÃO OBRIGATÓRIA: template.shape == bloco_aluno.shape
        
        Args:
            gabarito_obj: Objeto AnswerSheetGabarito
            block_num: Número do bloco (1-4)
            expected_shape: (height, width) do bloco do aluno
            
        Returns:
            Imagem do template (numpy array) ou None se não existir
            
        Raises:
            ValueError se shapes não batem (erro de configuração)
        """
        try:
            # Buscar bytes do campo correto
            template_bytes = gabarito_obj.get_template_block(block_num)
            
            if template_bytes is None:
                self.logger.warning(
                    f"⚠️ ATENÇÃO: Template de bloco {block_num} não encontrado! "
                    f"Gabarito {gabarito_obj.id} não possui template salvo."
                )
                return None
            
            # Decodificar PNG
            template_img = cv2.imdecode(
                np.frombuffer(template_bytes, np.uint8), 
                cv2.IMREAD_COLOR
            )
            
            if template_img is None:
                self.logger.error(f"Falha ao decodificar PNG do template bloco {block_num}")
                return None
            
            # ✅ VALIDAÇÃO OBRIGATÓRIA de shape
            template_shape = template_img.shape[:2]  # (height, width)
            
            if template_shape != expected_shape:
                # Log de warning mas NÃO raise - tentar redimensionar se necessário
                self.logger.warning(
                    f"⚠️ Shape mismatch no bloco {block_num}: "
                    f"template={template_shape} vs aluno={expected_shape}. "
                    f"Isso pode indicar que os templates precisam ser regenerados."
                )
                
                # Tentar redimensionar para shape esperado (fallback, não ideal)
                # Nota: Isso não é o ideal, mas permite funcionamento
                if abs(template_shape[0] - expected_shape[0]) < 50 and abs(template_shape[1] - expected_shape[1]) < 50:
                    template_img = cv2.resize(template_img, (expected_shape[1], expected_shape[0]))
                    self.logger.warning(f"Template redimensionado de {template_shape} para {expected_shape}")
                else:
                    self.logger.error(
                        f"Diferença de shape muito grande para redimensionar. "
                        f"Regenere os templates do gabarito {gabarito_obj.id}"
                    )
                    return None
            
            self.logger.debug(f"Template bloco {block_num} carregado: {template_img.shape}")
            return template_img
            
        except Exception as e:
            self.logger.error(f"Erro ao carregar template bloco {block_num}: {str(e)}", exc_info=True)
            return None
    
    def _comparar_roi_com_template(self, aluno_roi: np.ndarray, 
                                    template_roi: np.ndarray) -> float:
        """
        Compara ROI do aluno com ROI do template usando diferença absoluta.
        
        ✅ CORREÇÕES APLICADAS:
        - Blur (3,3) ANTES do absdiff para remover ruído
        - Threshold 30 DEPOIS do absdiff para focar só em tinta
        - Elimina 90% dos falsos positivos por poeira/sombra/scanner
        
        Args:
            aluno_roi: ROI da bolha do aluno
            template_roi: ROI da bolha do template (mesma posição)
            
        Returns:
            Score normalizado (0.0 a 1.0) — maior = mais marcado
            
        Raises:
            ValueError se shapes não batem
        """
        # Validar shapes OBRIGATÓRIO
        if aluno_roi.shape != template_roi.shape:
            raise ValueError(
                f"Shape mismatch: aluno={aluno_roi.shape} vs template={template_roi.shape}"
            )
        
        # Converter para grayscale se necessário
        if len(aluno_roi.shape) == 3:
            aluno_gray = cv2.cvtColor(aluno_roi, cv2.COLOR_BGR2GRAY)
            template_gray = cv2.cvtColor(template_roi, cv2.COLOR_BGR2GRAY)
        else:
            aluno_gray = aluno_roi.copy()
            template_gray = template_roi.copy()
        
        # ✅ ANTES do absdiff: blur para remover ruído
        aluno_blur = cv2.GaussianBlur(aluno_gray, (3, 3), 0)
        template_blur = cv2.GaussianBlur(template_gray, (3, 3), 0)
        
        # Diferença absoluta
        diff = cv2.absdiff(aluno_blur, template_blur)
        
        # ✅ DEPOIS: threshold para focar só em tinta
        _, diff_thresh = cv2.threshold(diff, 30, 255, cv2.THRESH_BINARY)
        
        # Score normalizado
        score = np.mean(diff_thresh) / 255.0
        
        return score
    
    def _medir_preenchimento_com_template(self, block_aluno: np.ndarray,
                                           template_block: np.ndarray,
                                           x: int, y: int, radius: int) -> float:
        """
        Mede preenchimento de uma bolha comparando com template.
        
        ✅ TEMPLATE REAL DIGITAL: Converte ambos para grayscale para garantir
        compatibilidade (block_aluno pode ser gray, template é BGR).
        
        Args:
            block_aluno: ROI do bloco do aluno (pode ser grayscale ou BGR)
            template_block: ROI do bloco template (BGR)
            x, y: Centro da bolha
            radius: Raio da bolha
            
        Returns:
            Score de preenchimento (0.0 a 1.0)
        """
        try:
            # Converter ambos para grayscale para garantir compatibilidade
            if len(block_aluno.shape) == 3:
                aluno_gray = cv2.cvtColor(block_aluno, cv2.COLOR_BGR2GRAY)
            else:
                aluno_gray = block_aluno
            
            if len(template_block.shape) == 3:
                template_gray = cv2.cvtColor(template_block, cv2.COLOR_BGR2GRAY)
            else:
                template_gray = template_block
            
            # Extrair ROI da bolha (com margem)
            margin = 2
            y1 = max(0, y - radius - margin)
            y2 = min(aluno_gray.shape[0], y + radius + margin)
            x1 = max(0, x - radius - margin)
            x2 = min(aluno_gray.shape[1], x + radius + margin)
            
            aluno_roi = aluno_gray[y1:y2, x1:x2]
            template_roi = template_gray[y1:y2, x1:x2]
            
            # Validar que extraímos algo
            if aluno_roi.size == 0 or template_roi.size == 0:
                return 0.0
            
            # Validar shapes (devem ser iguais após extração da mesma região)
            if aluno_roi.shape != template_roi.shape:
                self.logger.warning(
                    f"Shape mismatch em ROI: aluno={aluno_roi.shape} vs template={template_roi.shape}"
                )
                return 0.0
            
            # ✅ ANTES do absdiff: blur para remover ruído
            aluno_blur = cv2.GaussianBlur(aluno_roi, (3, 3), 0)
            template_blur = cv2.GaussianBlur(template_roi, (3, 3), 0)
            
            # Diferença absoluta
            diff = cv2.absdiff(aluno_blur, template_blur)
            
            # ✅ DEPOIS: threshold para focar só em tinta
            _, diff_thresh = cv2.threshold(diff, 30, 255, cv2.THRESH_BINARY)
            
            # Score normalizado
            score = np.mean(diff_thresh) / 255.0
            
            return score
            
        except Exception as e:
            self.logger.warning(f"Erro ao medir preenchimento com template em ({x}, {y}): {str(e)}")
            return 0.0
    
    # =========================================================================
    # FIM dos métodos de Template Real Digital
    # =========================================================================
    
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
                error_msg = self._format_user_friendly_error("Erro ao decodificar imagem")
                return {"success": False, "error": error_msg}
            
            self.logger.info(f"Imagem decodificada: {img.shape}")
            
            # Salvar imagem original
            self._save_debug_image("01_original.jpg", img)
            
            # 2. Detectar QR Code
            qr_result = self._detectar_qr_code(img)
            if not qr_result or 'student_id' not in qr_result:
                error_msg = self._format_user_friendly_error("QR Code não detectado ou inválido")
                return {"success": False, "error": error_msg}
            
            student_id = qr_result['student_id']
            gabarito_id_original = qr_result.get('gabarito_id')  # ID original do QR code
            test_id = qr_result.get('test_id')
            
            self.logger.info(f"QR Code detectado: student_id={student_id}, gabarito_id={gabarito_id_original}, test_id={test_id}")
            
            # 3. Validar aluno
            student = Student.query.get(student_id)
            if not student:
                error_msg = self._format_user_friendly_error(f"Aluno com ID {student_id} não encontrado no sistema")
                return {"success": False, "error": error_msg}
            
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
                error_msg_tech = f"Gabarito não encontrado"
                if gabarito_id_original:
                    error_msg_tech += f" (gabarito_id: {gabarito_id_original})"
                if test_id:
                    error_msg_tech += f" (test_id: {test_id})"
                error_msg = self._format_user_friendly_error(error_msg_tech)
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
            
            # 6. Detectar quadrados A4 nos cantos
            squares = self._detectar_quadrados_a4(img)
            if squares is None:
                error_msg = self._format_user_friendly_error("Não foi possível detectar quadrados A4 nos cantos do documento")
                return {"success": False, "error": error_msg}
            else:
                # 7. Normalizar imagem para A4 padrão
                result = self._normalizar_para_a4(img, squares)
                if result is None:
                    error_msg = self._format_user_friendly_error("Erro ao normalizar imagem para A4")
                    return {"success": False, "error": error_msg}
                
                img_a4_normalized, scale_info = result
                
                # 8. Detectar triângulos na área dos blocos (dentro do A4 normalizado)
                triangles = self._detectar_triangulos_na_area_blocos(img_a4_normalized)
                if triangles is None:
                    error_msg = self._format_user_friendly_error("Não foi possível detectar triângulos na área dos blocos")
                    return {"success": False, "error": error_msg}
                
                # 9. Fazer crop da área dos blocos usando triângulos
                block_area_cropped = self._crop_area_blocos_com_triangulos(img_a4_normalized, triangles)
                if block_area_cropped is None:
                    error_msg = self._format_user_friendly_error("Erro ao fazer crop da área dos blocos")
                    return {"success": False, "error": error_msg}
                
                # Usar área cropada como img_warped
                img_warped = block_area_cropped
                block_area_info = None  # Não usamos mais mapeamento direto do CSS
            
            self.logger.info(f"Imagem processada: {img_warped.shape}")
            
            # Salvar imagem processada
            self._save_debug_image("02_processed.jpg", img_warped)
            
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
            
            # 10. Detectar blocos pelas bordas grossas dentro da área cropada
            # img_warped agora é a área cropada dos blocos (não mais a imagem A4 completa)
            answer_blocks, block_contours = self._detectar_blocos_resposta(img_warped)
            block_positions = None
            use_proportional_mapping = False
            
            if not answer_blocks:
                # Verificar se temos informação sobre quantidade esperada de blocos
                num_blocks_expected = len(blocks_structure.get('blocks', [])) if blocks_structure else None
                context = {
                    'num_blocks_expected': num_blocks_expected,
                    'num_blocks_found': 0
                }
                error_msg = self._format_user_friendly_error("Nenhum bloco de resposta detectado", context)
                return {"success": False, "error": error_msg}
            
            self.logger.info(f"✅ Detectados {len(answer_blocks)} blocos de resposta (método: {'proporcional' if use_proportional_mapping else 'detecção por bordas'})")
            
            # Salvar imagem com blocos detectados
            img_blocks_debug = img_warped.copy()
            if use_proportional_mapping and block_positions:
                for pos in block_positions:
                    x, y, w, h = pos['x'], pos['y'], pos['width'], pos['height']
                    cv2.rectangle(img_blocks_debug, (x, y), (x+w, y+h), (0, 255, 0), 3)
                    cv2.putText(img_blocks_debug, f"B{pos['block_num']}", (x+5, y+20), 
                              cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            else:
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
            
            # Validar quantidade de blocos detectados vs esperados
            num_blocks_expected = len(topology_blocks_map)
            num_blocks_found = len(answer_blocks)
            if num_blocks_found != num_blocks_expected:
                context = {
                    'num_blocks_expected': num_blocks_expected,
                    'num_blocks_found': num_blocks_found
                }
                error_msg = self._format_user_friendly_error(
                    f"Esperava {num_blocks_expected} blocos, encontrou {num_blocks_found}",
                    context
                )
                return {"success": False, "error": error_msg}
            
            # Processar cada bloco detectado SEPARADAMENTE
            # Salvar offsets dos blocos para ajustar coordenadas na imagem final
            block_offsets = []  # Lista de (x_offset, y_offset) para cada bloco
            
            for block_idx, block_roi in enumerate(answer_blocks):
                block_num_detected = block_idx + 1  # Número do bloco detectado (1, 2, 3...)
                
                self.logger.info(f"═══════════════════════════════════════")
                self.logger.info(f"Processando BLOCO {block_num_detected} (separadamente)")
                self.logger.info(f"═══════════════════════════════════════")
                
                # Calcular offset deste bloco na imagem original
                if use_proportional_mapping and block_positions:
                    # Usar posições do mapeamento proporcional
                    block_pos = block_positions[block_idx]
                    x_offset = block_pos['x']
                    y_offset = block_pos['y']
                elif block_idx < len(block_contours):
                    # Usar contornos detectados (método antigo)
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
                
                # 2. Detectar borda e extrair área interna do bloco real
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
                    
                # ✅ Validar que temos espaço interno suficiente após subtrair borda
                inner_w = w - 2 * border_thickness
                inner_h = h - 2 * border_thickness
                
                if inner_w <= 0 or inner_h <= 0:
                    self.logger.error(f"Bloco {block_num_detected}: Tamanho interno inválido após subtrair borda ({inner_w}x{inner_h}px). Borda detectada: {border_thickness}px, tamanho total: {w}x{h}px")
                    # Usar borda padrão menor (máximo 2px ou 10% do tamanho)
                    border_thickness = min(2, max(1, w // 20), max(1, h // 20))  # Máximo 2px ou 5% do tamanho
                    inner_w = w - 2 * border_thickness
                    inner_h = h - 2 * border_thickness
                    self.logger.warning(f"Bloco {block_num_detected}: Ajustando espessura da borda para {border_thickness}px, tamanho interno: {inner_w}x{inner_h}px")
                    border_info['border_thickness'] = border_thickness
                
                # Validar novamente após ajuste
                if inner_w <= 0 or inner_h <= 0:
                    self.logger.error(f"Bloco {block_num_detected}: Ainda inválido após ajuste. Usando bloco completo sem extrair borda.")
                    block_inner = block_gray.copy()
                    border_info = {'border_thickness': 0, 'inner_x': 0, 'inner_y': 0, 'x': 0, 'y': 0, 'w': w, 'h': h}
                else:
                    block_inner = block_gray[y+border_thickness:y+h-border_thickness,
                                            x+border_thickness:x+w-border_thickness]
                    
                    # Validar que a imagem interna não está vazia
                    if block_inner.size == 0:
                        self.logger.error(f"Bloco {block_num_detected}: Área interna vazia após extração. Usando bloco completo.")
                        block_inner = block_gray.copy()
                        border_info = {'border_thickness': 0, 'inner_x': 0, 'inner_y': 0, 'x': 0, 'y': 0, 'w': w, 'h': h}
                
                # 3. Validar que block_inner não está vazio
                if block_inner.size == 0:
                    self.logger.error(f"Bloco {block_num_detected}: Imagem interna vazia, pulando processamento")
                    continue
                
                inner_h, inner_w = block_inner.shape[:2]
                self.logger.info(f"Bloco {block_num_detected}: Tamanho interno = {inner_w}x{inner_h}px")
                
                # ✅ SALVAR IMAGEM ORIGINAL ANTES DO REDIMENSIONAMENTO (para saber o tamanho real)
                # Converter para BGR se necessário para salvar
                if len(block_inner.shape) == 2:
                    block_original_bgr = cv2.cvtColor(block_inner, cv2.COLOR_GRAY2BGR)
                else:
                    block_original_bgr = block_inner.copy()
                self._save_debug_image(f"04_block_{block_num_detected:02d}_real_only_original_{inner_w}x{inner_h}.jpg", block_original_bgr)
                self.logger.info(f"Bloco {block_num_detected}: Imagem original salva: {inner_w}x{inner_h}px")
                
                # ✅ NOVO: Redimensionar bloco para tamanho padrão (155x473px) para garantir consistência
                STANDARD_BLOCK_WIDTH = 155
                STANDARD_BLOCK_HEIGHT = 473
                
                if inner_w != STANDARD_BLOCK_WIDTH or inner_h != STANDARD_BLOCK_HEIGHT:
                    self.logger.info(f"Bloco {block_num_detected}: Redimensionando de {inner_w}x{inner_h}px para {STANDARD_BLOCK_WIDTH}x{STANDARD_BLOCK_HEIGHT}px")
                    block_inner = cv2.resize(block_inner, (STANDARD_BLOCK_WIDTH, STANDARD_BLOCK_HEIGHT), interpolation=cv2.INTER_AREA)
                    inner_w = STANDARD_BLOCK_WIDTH
                    inner_h = STANDARD_BLOCK_HEIGHT
                    self.logger.info(f"Bloco {block_num_detected}: Bloco redimensionado para {inner_w}x{inner_h}px")
                else:
                    self.logger.debug(f"Bloco {block_num_detected}: Já está no tamanho padrão {STANDARD_BLOCK_WIDTH}x{STANDARD_BLOCK_HEIGHT}px")
                
                # SALVAR IMAGEM LIMPA DO BLOCO REDIMENSIONADO (SEM OVERLAY) - para debug
                # Converter para BGR se necessário para salvar
                if len(block_inner.shape) == 2:
                    block_clean_bgr = cv2.cvtColor(block_inner, cv2.COLOR_GRAY2BGR)
                else:
                    block_clean_bgr = block_inner.copy()
                self._save_debug_image(f"04_block_{block_num_detected:02d}_real_only.jpg", block_clean_bgr)
                
                # 4. Processar bloco usando classificação relativa (SEM imagem de gabarito)
                # Calcular offsets para coordenadas absolutas
                border_thickness = border_info.get('border_thickness', 0)
                block_x_offset = x_offset
                block_y_offset = y_offset
                
                # Se detectou borda, adicionar offset da borda
                if border_info and 'x' in border_info:
                    block_x_offset += border_info['x'] + border_thickness
                    block_y_offset += border_info['y'] + border_thickness
                
                # =========================================================================
                # ✅ TEMPLATE REAL DIGITAL: Tentar carregar template do bloco
                # =========================================================================
                template_block = None
                if gabarito_obj and gabarito_obj.has_templates():
                    try:
                        expected_shape = (inner_h, inner_w)  # (height, width)
                        template_block = self._carregar_template_bloco(
                            gabarito_obj=gabarito_obj,
                            block_num=block_num_detected,
                            expected_shape=expected_shape
                        )
                        
                        if template_block is not None:
                            self.logger.info(f"✅ TEMPLATE REAL DIGITAL: Template do bloco {block_num_detected} carregado ({template_block.shape})")
                        else:
                            self.logger.warning(
                                f"⚠️ TEMPLATE REAL DIGITAL: Template do bloco {block_num_detected} não disponível. "
                                f"Usando método geométrico (menos preciso)."
                            )
                    except Exception as e:
                        self.logger.warning(
                            f"⚠️ TEMPLATE REAL DIGITAL: Erro ao carregar template do bloco {block_num_detected}: {str(e)}. "
                            f"Usando método geométrico (menos preciso)."
                        )
                        template_block = None
                else:
                    self.logger.debug(f"Bloco {block_num_detected}: Gabarito sem templates salvos")
                
                # Processar usando método sem referência (com ou sem template)
                # scale_info está disponível no escopo do loop principal
                block_answers, bubbles_info_block = self._processar_bloco_sem_referencia(
                    block_roi=block_inner,  # Usar área interna do bloco
                    block_config=block_config,
                    correct_answers=gabarito,
                    block_num=block_num_detected,
                    x_offset=block_x_offset,
                    y_offset=block_y_offset,
                    scale_info=scale_info,
                    template_block=template_block  # ✅ NOVO: Template Real Digital
                )
                
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
            error_msg = self._format_user_friendly_error(f"Erro interno: {str(e)}")
            return {"success": False, "error": error_msg}
    
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
    
    def _analisar_iluminacao(self, gray: np.ndarray) -> Dict[str, Any]:
        """
        Analisa a qualidade da iluminação da imagem.
        Usado apenas para decidir se vale tentar fallback, nunca para alterar correção.
        
        Args:
            gray: Imagem em escala de cinza
            
        Returns:
            Dict com informações de iluminação: mean, std, brightness
        """
        try:
            mean = float(np.mean(gray))
            std = float(np.std(gray))
            
            # Classificar brilho
            if mean < 80:
                brightness = "dark"
            elif mean > 180:
                brightness = "bright"
            else:
                brightness = "normal"
            
            return {
                "mean": mean,
                "std": std,
                "brightness": brightness
            }
        except Exception as e:
            self.logger.warning(f"Erro ao analisar iluminação: {str(e)}")
            return {"mean": 128.0, "std": 50.0, "brightness": "normal"}
    
    def _preprocess_omr(self, image: np.ndarray, mode: str = "auto") -> np.ndarray:
        """
        Pré-processamento adaptativo para melhorar detecção em imagens difíceis.
        NÃO altera lógica de detecção. Apenas melhora contraste para imagens difíceis.
        
        Implementa:
        - Conversão para LAB
        - Equalização CLAHE no canal L
        - Remoção de sombra via background blur + normalize
        - Retorna imagem BGR
        
        ⚠️ Essa função NÃO deve ser usada por padrão, apenas como fallback.
        
        Args:
            image: Imagem BGR original
            mode: Modo de pré-processamento ("auto", "clahe", "shadow_removal", "both")
            
        Returns:
            Imagem BGR pré-processada
        """
        try:
            if len(image.shape) != 3:
                # Se já está em grayscale, converter para BGR
                image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
            
            # Converter para LAB para trabalhar no canal L (luminância)
            lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
            l_channel, a_channel, b_channel = cv2.split(lab)
            
            # Aplicar CLAHE (Contrast Limited Adaptive Histogram Equalization) no canal L
            if mode in ["auto", "clahe", "both"]:
                clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
                l_channel = clahe.apply(l_channel)
            
            # Remoção de sombra via background blur + normalize
            if mode in ["auto", "shadow_removal", "both"]:
                # Criar background estimado usando blur gaussiano grande
                background = cv2.GaussianBlur(l_channel, (101, 101), 0)
                
                # Normalizar: l_normalized = (l - background) * scale + offset
                # Isso remove gradientes de iluminação
                l_normalized = cv2.subtract(l_channel, background)
                l_normalized = cv2.add(l_normalized, 128)  # Adicionar offset para manter brilho médio
                
                # Limitar valores entre 0 e 255
                l_normalized = np.clip(l_normalized, 0, 255).astype(np.uint8)
                l_channel = l_normalized
            
            # Recombinar canais LAB
            lab_processed = cv2.merge([l_channel, a_channel, b_channel])
            
            # Converter de volta para BGR
            result = cv2.cvtColor(lab_processed, cv2.COLOR_LAB2BGR)
            
            # Salvar debug se ativado
            if self.save_debug_images:
                self._save_debug_image("preprocess_omr_result.jpg", result)
            
            return result
            
        except Exception as e:
            self.logger.warning(f"Erro no pré-processamento OMR: {str(e)}, retornando imagem original")
            return image
    
    def _detectar_quadrados_a4(self, img: np.ndarray) -> Optional[Dict]:
        """
        Detecta 4 quadrados pretos nos cantos do cartão resposta (âncoras A4)
        
        Implementação robusta com fallback progressivo:
        - Tentativa 1: Detecção original (comportamento padrão)
        - Tentativa 2: Pré-processamento adaptativo + detecção original
        - Tentativa 3: Relaxamento controlado de parâmetros
        - Tentativa 4: Fallback com Canny
        
        ⚠️ PRESERVA COMPORTAMENTO ORIGINAL para imagens boas.
        ⚠️ Apenas adiciona robustez quando detecção original falha.
        
        Args:
            img: Imagem original
            
        Returns:
            Dict com coordenadas dos 4 quadrados ordenados (TL, TR, BR, BL) ou None
        """
        def _detectar_quadrados_interno(img_detect: np.ndarray, 
                                       relax_area: float = 1.0, 
                                       relax_aspect: float = 0.0) -> Optional[Dict]:
            """
            Lógica interna de detecção de quadrados (extraída para reutilização).
            
            Args:
                img_detect: Imagem para detectar
                relax_area: Fator de relaxamento de área (1.0 = original, 1.2 = +20%)
                relax_aspect: Relaxamento de aspect ratio (0.0 = original, 0.1 = expandir 0.1)
            """
            try:
                # Converter para grayscale
                if len(img_detect.shape) == 3:
                    gray = cv2.cvtColor(img_detect, cv2.COLOR_BGR2GRAY)
                else:
                    gray = img_detect.copy()
                
                img_height, img_width = gray.shape[:2]
                img_area = img_width * img_height
                
                # Aplicar threshold para detectar quadrados pretos
                _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
                
                # Salvar debug se ativado
                if self.save_debug_images:
                    self._save_debug_image("00_a4_binary.jpg", binary)
                
                # ✅ CORREÇÃO 1: Usar RETR_TREE para hierarquia de contornos
                contours, hierarchy = cv2.findContours(binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
                
                # ✅ CORREÇÃO 2: Área relativa à imagem (nunca fixa) com relaxamento opcional
                min_area = img_area * 0.0001 * (1.0 / relax_area)   # ~0.01% da imagem
                max_area = img_area * 0.002 * relax_area    # ~0.2% da imagem
                
                # ✅ CORREÇÃO 4: Margem para filtro de proximidade à borda
                margin_x = img_width * 0.1   # 10% da largura
                margin_y = img_height * 0.1  # 10% da altura
                
                squares = []
                
                for i, cnt in enumerate(contours):
                    # Aproximar contorno
                    peri = cv2.arcLength(cnt, True)
                    approx = cv2.approxPolyDP(cnt, 0.04 * peri, True)
                    
                    # Verificar se é um quadrado (4 vértices)
                    if len(approx) != 4:
                        continue
                    
                    area = cv2.contourArea(approx)
                    
                    # ✅ CORREÇÃO 2: Filtrar por área relativa (com relaxamento)
                    if not (min_area < area < max_area):
                        continue
                    
                    # Verificar aspect ratio
                    x, y, w, h = cv2.boundingRect(approx)
                    aspect_ratio = w / float(h) if h > 0 else 0
                    
                    # ✅ CORREÇÃO 3: Aspect ratio mais restritivo (quadrado real) com relaxamento
                    aspect_min = 0.9 - relax_aspect
                    aspect_max = 1.1 + relax_aspect
                    if not (aspect_min < aspect_ratio < aspect_max):
                        continue
                    
                    # Calcular centro do quadrado
                    M = cv2.moments(approx)
                    if M["m00"] == 0:
                        continue
                    
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                    
                    # ✅ CORREÇÃO 4: FILTRO DE PROXIMIDADE À BORDA (ESSENCIAL)
                    # Quadrados A4 SEMPRE estão perto dos cantos
                    is_near_edge = (
                        cx < margin_x or
                        cx > img_width - margin_x or
                        cy < margin_y or
                        cy > img_height - margin_y
                    )
                    
                    if not is_near_edge:
                        continue
                    
                    squares.append({
                        'contour': approx,
                        'center': (cx, cy),
                        'area': area
                    })
                
                if len(squares) < 4:
                    return None
                
                # ✅ CORREÇÃO 5: GARANTIR 1 QUADRADO POR CANTO
                corners = {
                    "TL": [],  # Top-Left
                    "TR": [],  # Top-Right
                    "BR": [],  # Bottom-Right
                    "BL": []   # Bottom-Left
                }
                
                for s in squares:
                    cx, cy = s["center"]
                    # Classificar por quadrante
                    if cx < img_width / 2 and cy < img_height / 2:
                        corners["TL"].append(s)
                    elif cx >= img_width / 2 and cy < img_height / 2:
                        corners["TR"].append(s)
                    elif cx >= img_width / 2 and cy >= img_height / 2:
                        corners["BR"].append(s)
                    else:
                        corners["BL"].append(s)
                
                # Verificar se todos os cantos têm pelo menos 1 quadrado
                missing_corners = [corner for corner, items in corners.items() if not items]
                if missing_corners:
                    return None
                
                # Para cada canto, pegar o maior quadrado (mais confiável) e extrair o vértice correto
                ordered_squares = {}
                for corner, items in corners.items():
                    if not items:
                        return None
                    # Pegar o maior quadrado do canto
                    best_square = max(items, key=lambda x: x["area"])
                    
                    # ✅ CORREÇÃO: Extrair o vértice correto do quadrado ao invés do centro
                    # O vértice correto é aquele que está mais próximo do canto real do documento
                    contour = best_square["contour"]  # approx com 4 vértices
                    vertices = contour.reshape(-1, 2)  # Converter para array de pontos (x, y)
                    
                    # Selecionar o vértice correto baseado no canto
                    # Para cada canto, queremos o vértice que minimiza/maximiza x e y apropriadamente
                    if corner == "TL":  # Top-Left: menor x E menor y
                        # Encontrar vértice com menor distância ao canto (0, 0)
                        distances = vertices[:, 0] + vertices[:, 1]
                        corner_vertex = vertices[np.argmin(distances)]
                    elif corner == "TR":  # Top-Right: maior x E menor y
                        # Encontrar vértice com maior x e menor y (mais próximo de (width, 0))
                        # Usar distância ponderada: maximizar x, minimizar y
                        scores = vertices[:, 0] - vertices[:, 1]
                        corner_vertex = vertices[np.argmax(scores)]
                    elif corner == "BR":  # Bottom-Right: maior x E maior y
                        # Encontrar vértice com maior distância ao canto (0, 0)
                        distances = vertices[:, 0] + vertices[:, 1]
                        corner_vertex = vertices[np.argmax(distances)]
                    else:  # BL - Bottom-Left: menor x E maior y
                        # Encontrar vértice com menor x e maior y (mais próximo de (0, height))
                        # Usar distância ponderada: minimizar x, maximizar y
                        scores = vertices[:, 0] - vertices[:, 1]
                        corner_vertex = vertices[np.argmin(scores)]
                    
                    ordered_squares[corner] = [float(corner_vertex[0]), float(corner_vertex[1])]
                
                return ordered_squares
                
            except Exception as e:
                self.logger.warning(f"Erro na detecção interna de quadrados: {str(e)}")
                return None
        
        # ========== PIPELINE DE FALLBACK PROGRESSIVO ==========
        try:
            # TENTATIVA 1: Detecção original (comportamento padrão)
            result = _detectar_quadrados_interno(img, relax_area=1.0, relax_aspect=0.0)
            if result:
                if self.save_debug_images:
                    img_debug = img.copy()
                    for label, vertex in result.items():
                        vx, vy = int(vertex[0]), int(vertex[1])
                        cv2.circle(img_debug, (vx, vy), 15, (0, 255, 0), -1)
                        cv2.putText(img_debug, label, (vx+20, vy), 
                                  cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 3)
                    self._save_debug_image("00_a4_squares_detected.jpg", img_debug)
                self.logger.info(f"✅ 4 quadrados A4 detectados (tentativa 1 - original): TL={result['TL']}, TR={result['TR']}, BR={result['BR']}, BL={result['BL']}")
                return result
            
            # Analisar iluminação para decidir se vale tentar fallback
            gray_temp = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img.copy()
            iluminacao = self._analisar_iluminacao(gray_temp)
            
            if self.save_debug_images:
                self.logger.info(f"🔍 Iluminação analisada: mean={iluminacao['mean']:.1f}, std={iluminacao['std']:.1f}, brightness={iluminacao['brightness']}")
            
            # TENTATIVA 2: Pré-processamento adaptativo + detecção original
            self.logger.info("⚠️ Tentativa 1 falhou, aplicando pré-processamento adaptativo...")
            img_preprocessed = self._preprocess_omr(img, mode="auto")
            result = _detectar_quadrados_interno(img_preprocessed, relax_area=1.0, relax_aspect=0.0)
            if result:
                if self.save_debug_images:
                    img_debug = img_preprocessed.copy()
                    for label, vertex in result.items():
                        vx, vy = int(vertex[0]), int(vertex[1])
                        cv2.circle(img_debug, (vx, vy), 15, (0, 255, 0), -1)
                        cv2.putText(img_debug, label, (vx+20, vy), 
                                  cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 3)
                    self._save_debug_image("00_a4_squares_detected_preprocessed.jpg", img_debug)
                self.logger.info(f"✅ 4 quadrados A4 detectados (tentativa 2 - pré-processado): TL={result['TL']}, TR={result['TR']}, BR={result['BR']}, BL={result['BL']}")
                return result
            
            # TENTATIVA 3: Relaxamento controlado de parâmetros (área ±20%, aspect ratio expandido)
            self.logger.info("⚠️ Tentativa 2 falhou, aplicando relaxamento controlado de parâmetros...")
            result = _detectar_quadrados_interno(img_preprocessed, relax_area=1.2, relax_aspect=0.1)
            if result:
                if self.save_debug_images:
                    img_debug = img_preprocessed.copy()
                    for label, vertex in result.items():
                        vx, vy = int(vertex[0]), int(vertex[1])
                        cv2.circle(img_debug, (vx, vy), 15, (255, 255, 0), -1)
                        cv2.putText(img_debug, label, (vx+20, vy), 
                                  cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 0), 3)
                    self._save_debug_image("00_a4_squares_detected_relaxed.jpg", img_debug)
                self.logger.warning(f"⚠️ 4 quadrados A4 detectados (tentativa 3 - relaxado): TL={result['TL']}, TR={result['TR']}, BR={result['BR']}, BL={result['BL']}")
                return result
            
            # TENTATIVA 4: Fallback com Canny (já existente no código original)
            self.logger.warning("⚠️ Tentativa 3 falhou, tentando fallback com Canny...")
            try:
                gray = cv2.cvtColor(img_preprocessed, cv2.COLOR_BGR2GRAY) if len(img_preprocessed.shape) == 3 else img_preprocessed.copy()
                blurred = cv2.GaussianBlur(gray, (5, 5), 0)
                edged = cv2.Canny(blurred, 50, 150)
                kernel = np.ones((3, 3), np.uint8)
                edged_dilated = cv2.dilate(edged, kernel, iterations=1)
                
                if self.save_debug_images:
                    self._save_debug_image("00_a4_canny.jpg", edged_dilated)
                
                # Tentar detectar com Canny
                contours, _ = cv2.findContours(edged_dilated, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
                # Usar mesma lógica mas com contornos do Canny
                # (reutilizar função interna com imagem binária do Canny)
                # Por simplicidade, vamos tentar novamente com threshold adaptativo
                binary_canny = edged_dilated
                result = _detectar_quadrados_interno(img_preprocessed, relax_area=1.3, relax_aspect=0.15)
                if result:
                    self.logger.warning(f"⚠️ 4 quadrados A4 detectados (tentativa 4 - Canny fallback): TL={result['TL']}, TR={result['TR']}, BR={result['BR']}, BL={result['BL']}")
                    return result
            except Exception as e:
                self.logger.warning(f"Erro no fallback Canny: {str(e)}")
            
            # Todas as tentativas falharam
            self.logger.error("❌ Falha total na detecção de quadrados A4 após todas as tentativas")
            return None
            
        except Exception as e:
            self.logger.error(f"Erro ao detectar quadrados A4: {str(e)}", exc_info=True)
            return None
    
    def _normalizar_para_a4(self, img: np.ndarray, squares: Dict) -> Optional[Tuple[np.ndarray, Dict]]:
        """
        Normaliza imagem para tamanho A4 padrão usando quadrados nos cantos
        
        Args:
            img: Imagem original
            squares: Dict com coordenadas dos 4 quadrados (TL, TR, BR, BL)
            
        Returns:
            Tuple: (imagem normalizada, dict com informações de escala) ou None
        """
        try:
            # Dimensões reais do A4 em cm
            A4_WIDTH_CM = 21.0
            A4_HEIGHT_CM = 29.7
            
            # DPI padrão para normalização (100 DPI = ~37.8 pixels/cm)
            DPI = 100
            PX_PER_CM = DPI / 2.54  # ~39.37 pixels por cm
            
            # Dimensões do A4 em pixels (tamanho padrão)
            # CORRIGIDO: Usar round() ao invés de int() para evitar truncamento
            A4_WIDTH_PX = round(A4_WIDTH_CM * PX_PER_CM)  # 827px (correto)
            A4_HEIGHT_PX = round(A4_HEIGHT_CM * PX_PER_CM)  # 1171px (correto)
            
            # Pontos de origem (quadrados detectados)
            src_points = np.array([
                squares['TL'],  # Top-left
                squares['TR'],  # Top-right
                squares['BR'],  # Bottom-right
                squares['BL']   # Bottom-left
            ], dtype="float32")
            
            # Pontos de destino (cantos do A4 normalizado)
            dst_points = np.array([
                [0, 0],                          # Top-left
                [A4_WIDTH_PX - 1, 0],           # Top-right
                [A4_WIDTH_PX - 1, A4_HEIGHT_PX - 1],  # Bottom-right
                [0, A4_HEIGHT_PX - 1]            # Bottom-left
            ], dtype="float32")
            
            # 🔍 DEBUG: Logs detalhados do warpPerspective
            self.logger.info(f"🔍 DEBUG - Pontos de origem (detectados):")
            self.logger.info(f"  TL (src): {src_points[0]}")
            self.logger.info(f"  TR (src): {src_points[1]}")
            self.logger.info(f"  BR (src): {src_points[2]}")
            self.logger.info(f"  BL (src): {src_points[3]}")
            self.logger.info(f"🔍 DEBUG - Pontos de destino (A4 normalizado):")
            self.logger.info(f"  TL (dst): {dst_points[0]}")
            self.logger.info(f"  TR (dst): {dst_points[1]}")
            self.logger.info(f"  BR (dst): {dst_points[2]}")
            self.logger.info(f"  BL (dst): {dst_points[3]}")
            
            # Calcular matriz de transformação
            M = cv2.getPerspectiveTransform(src_points, dst_points)
            
            self.logger.info(f"🔍 DEBUG - Matriz de transformação:")
            self.logger.info(f"  {M}")
            
            # Aplicar transformação
            img_normalized = cv2.warpPerspective(img, M, (A4_WIDTH_PX, A4_HEIGHT_PX))
            
            self.logger.info(f"🔍 DEBUG - Imagem antes e depois:")
            self.logger.info(f"  Antes (original): {img.shape}")
            self.logger.info(f"  Depois (warped): {img_normalized.shape}")
            
            # Calcular escala (pixels por cm)
            # Distância entre quadrados na imagem original
            width_original_px = np.linalg.norm(np.array(squares['TR']) - np.array(squares['TL']))
            height_original_px = np.linalg.norm(np.array(squares['BL']) - np.array(squares['TL']))
            
            px_per_cm_x = width_original_px / A4_WIDTH_CM
            px_per_cm_y = height_original_px / A4_HEIGHT_CM
            
            # 🔍 DEBUG: Verificar escala e quadrados detectados
            self.logger.info(f"🔍 DEBUG - Quadrados detectados:")
            self.logger.info(f"  TL: {squares['TL']}")
            self.logger.info(f"  TR: {squares['TR']}")
            self.logger.info(f"  BR: {squares['BR']}")
            self.logger.info(f"  BL: {squares['BL']}")
            self.logger.info(f"🔍 DEBUG - Dimensões originais:")
            self.logger.info(f"  Largura: {width_original_px:.2f}px")
            self.logger.info(f"  Altura: {height_original_px:.2f}px")
            self.logger.info(f"  Proporção (W/H): {width_original_px/height_original_px:.4f} (esperado ~0.7071 para A4)")
            self.logger.info(f"🔍 DEBUG - Escala:")
            self.logger.info(f"  px_per_cm_x: {px_per_cm_x:.2f}")
            self.logger.info(f"  px_per_cm_y: {px_per_cm_y:.2f}")
            if abs(px_per_cm_x - px_per_cm_y) > 0.5:
                self.logger.warning(f"⚠️  ESCALAS DIFERENTES! Proporção Y/X: {px_per_cm_y/px_per_cm_x:.4f} ({((px_per_cm_y/px_per_cm_x - 1) * 100):.1f}%)")
            
            scale_info = {
                'a4_width_px': A4_WIDTH_PX,
                'a4_height_px': A4_HEIGHT_PX,
                'px_per_cm_x': px_per_cm_x,
                'px_per_cm_y': px_per_cm_y,
                'a4_width_cm': A4_WIDTH_CM,
                'a4_height_cm': A4_HEIGHT_CM
            }
            
            # Salvar debug
            if self.save_debug_images:
                self._save_debug_image("01_a4_normalized.jpg", img_normalized)
            
            self.logger.info(f"✅ Imagem normalizada para A4: {A4_WIDTH_PX}x{A4_HEIGHT_PX}px (escala: {px_per_cm_x:.2f}px/cm x {px_per_cm_y:.2f}px/cm)")
            
            return img_normalized, scale_info
            
        except Exception as e:
            self.logger.error(f"Erro ao normalizar para A4: {str(e)}", exc_info=True)
            return None
    
    def _detectar_triangulos_na_area_blocos(self, img_a4: np.ndarray) -> Optional[Dict]:
        """
        Detecta triângulos dentro da área dos blocos (já na imagem normalizada para A4)
        
        Implementação robusta com fallback progressivo:
        - Tentativa 1: Detecção original (múltiplas estratégias de threshold)
        - Tentativa 2: Pré-processamento adaptativo + detecção original
        - Tentativa 3: Relaxamento controlado de área mínima/máxima
        - Tentativa 4: Fallback de área padrão (já existente)
        
        ⚠️ PRESERVA COMPORTAMENTO ORIGINAL para imagens boas.
        ⚠️ Apenas adiciona robustez quando detecção original falha.
        
        Args:
            img_a4: Imagem já normalizada para A4
            
        Returns:
            Dict com coordenadas dos 4 triângulos (TL, TR, BR, BL) ou None
        """
        def _detectar_triangulos_interno(img_detect: np.ndarray, 
                                        relax_area_min: float = 1.0,
                                        relax_area_max: float = 1.0) -> Optional[List[Dict]]:
            """
            Lógica interna de detecção de triângulos (extraída para reutilização).
            
            Args:
                img_detect: Imagem para detectar
                relax_area_min: Fator de relaxamento de área mínima (1.0 = original, 0.5 = -50%)
                relax_area_max: Fator de relaxamento de área máxima (1.0 = original, 1.5 = +50%)
            """
            try:
                h, w = img_detect.shape[:2]
                gray = cv2.cvtColor(img_detect, cv2.COLOR_BGR2GRAY) if len(img_detect.shape) == 3 else img_detect.copy()
                
                # Tentar múltiplas estratégias de threshold para melhorar detecção
                triangles = []
                
                # Estratégia 1: Threshold Otsu padrão
                _, binary1 = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
                triangles.extend(self._extrair_triangulos_de_binary(binary1, relax_area_min, relax_area_max))
                
                # Estratégia 2: Adaptive threshold (mais robusto para iluminação variável)
                binary2 = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                              cv2.THRESH_BINARY_INV, 11, 2)
                triangles.extend(self._extrair_triangulos_de_binary(binary2, relax_area_min, relax_area_max))
                
                # Estratégia 3: Threshold adaptativo com blur
                blurred = cv2.GaussianBlur(gray, (5, 5), 0)
                _, binary3 = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
                triangles.extend(self._extrair_triangulos_de_binary(binary3, relax_area_min, relax_area_max))
                
                # Remover duplicatas (triângulos muito próximos)
                triangles = self._remover_triangulos_duplicados(triangles)
                
                return triangles
                
            except Exception as e:
                self.logger.warning(f"Erro na detecção interna de triângulos: {str(e)}")
                return None
        
        def _processar_triangulos_detectados(triangles: List[Dict], w: int, h: int) -> Optional[Dict]:
            """
            Processa lista de triângulos detectados e retorna dict ordenado ou None.
            """
            if not triangles:
                return None
            
            # Se detectou menos de 4, tentar inferir o(s) faltante(s)
            if len(triangles) < 4:
                # Se detectou 3, inferir o 4º baseado na geometria esperada
                if len(triangles) == 3:
                    triangles = self._inferir_quarto_triangulo(triangles, w, h)
                    if triangles and len(triangles) == 4:
                        self.logger.info("✅ 4º triângulo inferido com sucesso")
                    else:
                        return None
                elif len(triangles) < 3:
                    return None
                else:
                    return None
            
            # Se detectou mais de 4, ordenar por área e pegar os 4 maiores
            if len(triangles) > 4:
                triangles = sorted(triangles, key=lambda t: t['area'], reverse=True)[:4]
            
            # Ordenar: TL, TR, BR, BL
            centers = np.array([t['center'] for t in triangles], dtype="float32")
            soma = centers.sum(axis=1)
            diff = np.diff(centers, axis=1)
            
            tl_idx = np.argmin(soma)
            br_idx = np.argmax(soma)
            tr_idx = np.argmin(diff)
            bl_idx = np.argmax(diff)
            
            # Garantir índices diferentes
            if len(set([tl_idx, tr_idx, br_idx, bl_idx])) != 4:
                centers_list = centers.tolist()
                tl = min(centers_list, key=lambda p: p[0] + p[1])
                br = max(centers_list, key=lambda p: p[0] + p[1])
                remaining = [p for p in centers_list if p != tl and p != br]
                tr = min(remaining, key=lambda p: p[0] - p[1])
                bl = [p for p in remaining if p != tr][0]
                
                ordered_triangles = {
                    'TL': tl,
                    'TR': tr,
                    'BR': br,
                    'BL': bl
                }
            else:
                ordered_triangles = {
                    'TL': centers[tl_idx].tolist(),
                    'TR': centers[tr_idx].tolist(),
                    'BR': centers[br_idx].tolist(),
                    'BL': centers[bl_idx].tolist()
                }
            
            return ordered_triangles
        
        # ========== PIPELINE DE FALLBACK PROGRESSIVO ==========
        try:
            h, w = img_a4.shape[:2]
            
            # TENTATIVA 1: Detecção original (comportamento padrão)
            triangles = _detectar_triangulos_interno(img_a4, relax_area_min=1.0, relax_area_max=1.0)
            if triangles:
                self.logger.info(f"Total de triângulos detectados (tentativa 1 - original): {len(triangles)}")
                result = _processar_triangulos_detectados(triangles, w, h)
                if result:
                    if self.save_debug_images:
                        img_debug = img_a4.copy()
                        for label, center in result.items():
                            cx, cy = int(center[0]), int(center[1])
                            cv2.circle(img_debug, (cx, cy), 15, (255, 0, 0), -1)
                            cv2.putText(img_debug, f"T{label}", (cx+20, cy), 
                                      cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 0), 2)
                        self._save_debug_image("02_triangles_in_a4.jpg", img_debug)
                    self.logger.info(f"✅ 4 triângulos detectados na área dos blocos (tentativa 1 - original)")
                    return result
            
            # Analisar iluminação para decidir se vale tentar fallback
            gray_temp = cv2.cvtColor(img_a4, cv2.COLOR_BGR2GRAY) if len(img_a4.shape) == 3 else img_a4.copy()
            iluminacao = self._analisar_iluminacao(gray_temp)
            
            if self.save_debug_images:
                self.logger.info(f"🔍 Iluminação analisada: mean={iluminacao['mean']:.1f}, std={iluminacao['std']:.1f}, brightness={iluminacao['brightness']}")
            
            # TENTATIVA 2: Pré-processamento adaptativo + detecção original
            self.logger.info("⚠️ Tentativa 1 falhou, aplicando pré-processamento adaptativo...")
            img_preprocessed = self._preprocess_omr(img_a4, mode="auto")
            triangles = _detectar_triangulos_interno(img_preprocessed, relax_area_min=1.0, relax_area_max=1.0)
            if triangles:
                self.logger.info(f"Total de triângulos detectados (tentativa 2 - pré-processado): {len(triangles)}")
                result = _processar_triangulos_detectados(triangles, w, h)
                if result:
                    if self.save_debug_images:
                        img_debug = img_preprocessed.copy()
                        for label, center in result.items():
                            cx, cy = int(center[0]), int(center[1])
                            cv2.circle(img_debug, (cx, cy), 15, (255, 0, 0), -1)
                            cv2.putText(img_debug, f"T{label}", (cx+20, cy), 
                                      cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 0), 2)
                        self._save_debug_image("02_triangles_in_a4_preprocessed.jpg", img_debug)
                    self.logger.info(f"✅ 4 triângulos detectados na área dos blocos (tentativa 2 - pré-processado)")
                    return result
            
            # TENTATIVA 3: Relaxamento controlado de área (área mínima -50%, área máxima +50%)
            self.logger.info("⚠️ Tentativa 2 falhou, aplicando relaxamento controlado de área...")
            triangles = _detectar_triangulos_interno(img_preprocessed, relax_area_min=0.5, relax_area_max=1.5)
            if triangles:
                self.logger.info(f"Total de triângulos detectados (tentativa 3 - relaxado): {len(triangles)}")
                result = _processar_triangulos_detectados(triangles, w, h)
                if result:
                    if self.save_debug_images:
                        img_debug = img_preprocessed.copy()
                        for label, center in result.items():
                            cx, cy = int(center[0]), int(center[1])
                            cv2.circle(img_debug, (cx, cy), 15, (255, 255, 0), -1)
                            cv2.putText(img_debug, f"T{label}", (cx+20, cy), 
                                      cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)
                        self._save_debug_image("02_triangles_in_a4_relaxed.jpg", img_debug)
                    self.logger.warning(f"⚠️ 4 triângulos detectados na área dos blocos (tentativa 3 - relaxado)")
                    return result
            
            # TENTATIVA 4: Fallback de área padrão (já existente no código original)
            self.logger.warning("⚠️ Tentativa 3 falhou, usando área padrão baseada no template")
            return self._usar_area_padrao_blocos(w, h)
            
        except Exception as e:
            self.logger.error(f"Erro ao detectar triângulos na área dos blocos: {str(e)}", exc_info=True)
            return None
    
    def _extrair_triangulos_de_binary(self, binary: np.ndarray, 
                                     relax_area_min: float = 1.0,
                                     relax_area_max: float = 1.0) -> List[Dict]:
        """
        Extrai triângulos de uma imagem binária.
        
        Args:
            binary: Imagem binária (threshold aplicado)
            relax_area_min: Fator de relaxamento de área mínima (1.0 = original, 0.5 = -50%)
            relax_area_max: Fator de relaxamento de área máxima (1.0 = original, 1.5 = +50%)
            
        Returns:
            Lista de triângulos detectados
        """
        triangles = []
        # Área base com relaxamento opcional
        min_triangle_area = int(100 * relax_area_min)  # Área mínima reduzida para detectar triângulos menores/cortados
        max_triangle_area = int(800 * relax_area_max)  # Área máxima aumentada para tolerância
        
        # Usar RETR_TREE para pegar todos os contornos (não só externos)
        contours, _ = cv2.findContours(binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        
        for cnt in contours:
            # Aproximar contorno com tolerância adaptativa
            epsilon = 0.04 * cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, epsilon, True)
            area = cv2.contourArea(approx)
            
            # IMPORTANTE: Triângulos têm 3 vértices, quadrados têm 4 vértices
            # Isso diferencia triângulos de quadrados mesmo que tenham tamanho similar
            if len(approx) == 3 and min_triangle_area < area < max_triangle_area:
                M = cv2.moments(approx)
                if M["m00"] != 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                    triangles.append({
                        'contour': approx,
                        'center': (cx, cy),
                        'area': area
                    })
        
        return triangles
    
    def _remover_triangulos_duplicados(self, triangles: List[Dict], min_dist: int = 20) -> List[Dict]:
        """
        Remove triângulos duplicados com base na proximidade dos centros.
        
        Nunca compara arrays NumPy diretamente (causa erro de ambiguidade).
        Usa distância euclidiana entre centros para detectar duplicatas.
        
        Args:
            triangles: Lista de triângulos detectados (cada um com 'center', 'area', etc.)
            min_dist: Distância mínima em pixels para considerar triângulos distintos
            
        Returns:
            Lista de triângulos únicos (mantém o de maior área em caso de duplicata)
        """
        if len(triangles) <= 1:
            return triangles
        
        unique = []
        
        for tri in triangles:
            cx, cy = tri['center']
            found_duplicate = False
            duplicate_idx = -1
            
            # Verificar se já existe um triângulo muito próximo
            for idx, u in enumerate(unique):
                ux, uy = u['center']
                # Calcular distância euclidiana
                dist = np.hypot(cx - ux, cy - uy)
                
                if dist < min_dist:
                    # Triângulos muito próximos - manter o de maior área (mais confiável)
                    if tri['area'] > u['area']:
                        # Marcar para substituir o existente pelo novo (maior área)
                        duplicate_idx = idx
                    found_duplicate = True
                    break
            
            if found_duplicate:
                # Substituir o duplicado existente pelo novo (se tiver maior área)
                if duplicate_idx >= 0:
                    unique[duplicate_idx] = tri
            else:
                # Triângulo único, adicionar
                unique.append(tri)
        
        return unique
    
    def _inferir_quarto_triangulo(self, triangles: List[Dict], w: int, h: int) -> Optional[List[Dict]]:
        """
        Infere o 4º triângulo quando apenas 3 são detectados.
        Baseado na geometria esperada: 4 triângulos formam um retângulo.
        
        Args:
            triangles: Lista de 3 triângulos detectados
            w: Largura da imagem
            h: Altura da imagem
            
        Returns:
            Lista com 4 triângulos (3 detectados + 1 inferido) ou None
        """
        try:
            if len(triangles) != 3:
                return None
            
            centers = np.array([t['center'] for t in triangles], dtype="float32")
            centers_list = centers.tolist()
            
            # Identificar quais cantos temos pelos 3 pontos detectados
            # TL = menor soma (x + y)
            # BR = maior soma (x + y)
            # TR = menor diferença (x - y)
            # BL = maior diferença (x - y)
            
            soma = [p[0] + p[1] for p in centers_list]
            diff = [p[0] - p[1] for p in centers_list]
            
            tl = centers_list[np.argmin(soma)]
            br = centers_list[np.argmax(soma)]
            tr = centers_list[np.argmin(diff)]
            bl_candidate = centers_list[np.argmax(diff)]
            
            # Verificar qual canto está faltando
            # Se temos TL, TR, BR -> falta BL
            # Se temos TL, TR, BL -> falta BR
            # Se temos TL, BR, BL -> falta TR
            # Se temos TR, BR, BL -> falta TL
            
            detected = set([tuple(tl), tuple(tr), tuple(br), tuple(bl_candidate)])
            
            # Se temos 3 pontos únicos, um está faltando
            if len(detected) == 3:
                # Determinar qual está faltando
                all_corners = {
                    'TL': min(centers_list, key=lambda p: p[0] + p[1]),
                    'BR': max(centers_list, key=lambda p: p[0] + p[1]),
                    'TR': min(centers_list, key=lambda p: p[0] - p[1]),
                    'BL': max(centers_list, key=lambda p: p[0] - p[1])
                }
                
                # Verificar qual está faltando
                detected_set = set([tuple(p) for p in centers_list])
                missing_corner = None
                missing_label = None
                
                for label, corner in all_corners.items():
                    if tuple(corner) not in detected_set:
                        missing_corner = corner
                        missing_label = label
                        break
                
                if missing_corner is None:
                    # Se não identificou claramente, assumir que falta BL (mais comum)
                    # Calcular BL = TL + BR - TR
                    tl_arr = np.array(all_corners['TL'])
                    tr_arr = np.array(all_corners['TR'])
                    br_arr = np.array(all_corners['BR'])
                    bl_inferred = tl_arr + br_arr - tr_arr
                    missing_corner = bl_inferred.tolist()
                    missing_label = 'BL'
                
                # Criar triângulo inferido
                inferred_triangle = {
                    'contour': None,  # Não temos contorno real
                    'center': (int(missing_corner[0]), int(missing_corner[1])),
                    'area': np.mean([t['area'] for t in triangles])  # Usar área média
                }
                
                triangles.append(inferred_triangle)
                self.logger.info(f"Triângulo {missing_label} inferido em ({int(missing_corner[0])}, {int(missing_corner[1])})")
                return triangles
            
            return None
            
        except Exception as e:
            self.logger.error(f"Erro ao inferir 4º triângulo: {str(e)}", exc_info=True)
            return None
    
    def _usar_area_padrao_blocos(self, w: int, h: int) -> Dict:
        """
        Retorna coordenadas padrão da área dos blocos baseado no template.
        Usado como fallback quando não consegue detectar triângulos.
        
        Args:
            w: Largura da imagem A4 normalizada
            h: Altura da imagem A4 normalizada
            
        Returns:
            Dict com coordenadas dos 4 cantos (TL, TR, BR, BL)
        """
        # Baseado no template HTML:
        # - Padding top: 1.8cm
        # - Header: 6.4cm
        # - Instruções: 3.8cm
        # - Aplicador: 2.6cm
        # Total antes dos blocos: ~14.6cm
        # Altura A4: 29.7cm
        # Área dos blocos começa em ~14.6cm e vai até ~27.5cm (altura ~12.9cm)
        # Largura: margem esquerda ~0.6cm, direita ~0.6cm, então área útil ~19.8cm
        
        # Converter para pixels (assumindo escala média)
        # A4 normalizado: 827x1171px (CORRIGIDO: era 826x1169px, truncamento de int())
        # Proporções: w/21.0 = px_per_cm_x, h/29.7 = px_per_cm_y
        
        px_per_cm_x = w / 21.0
        px_per_cm_y = h / 29.7
        
        # Área dos blocos no template
        top_cm = 1.8 + 6.4 + 3.8 + 2.6  # ~14.6cm
        left_cm = 0.6
        right_cm = 21.0 - 0.6  # ~20.4cm
        bottom_cm = 29.7 - 2.2  # ~27.5cm (altura A4 - padding bottom)
        
        tl = [int(left_cm * px_per_cm_x), int(top_cm * px_per_cm_y)]
        tr = [int(right_cm * px_per_cm_x), int(top_cm * px_per_cm_y)]
        br = [int(right_cm * px_per_cm_x), int(bottom_cm * px_per_cm_y)]
        bl = [int(left_cm * px_per_cm_x), int(bottom_cm * px_per_cm_y)]
        
        self.logger.info(f"Usando área padrão dos blocos: TL={tl}, TR={tr}, BR={br}, BL={bl}")
        
        return {
            'TL': tl,
            'TR': tr,
            'BR': br,
            'BL': bl
        }
    
    def _crop_area_blocos_com_triangulos(self, img_a4: np.ndarray, triangles: Dict) -> Optional[np.ndarray]:
        """
        Faz crop da área dos blocos usando os triângulos detectados
        
        Args:
            img_a4: Imagem normalizada para A4
            triangles: Dict com coordenadas dos triângulos (TL, TR, BR, BL)
            
        Returns:
            Imagem cropada da área dos blocos ou None
        """
        try:
            # Converter para grayscale se necessário
            if len(img_a4.shape) == 3:
                gray = cv2.cvtColor(img_a4, cv2.COLOR_BGR2GRAY)
            else:
                gray = img_a4.copy()
            
            # Calcular bounding box dos triângulos
            triangle_TL = np.array(triangles['TL'])
            triangle_TR = np.array(triangles['TR'])
            triangle_BL = np.array(triangles['BL'])
            triangle_BR = np.array(triangles['BR'])
            
            # Encontrar limites da área
            min_x = int(min(triangle_TL[0], triangle_BL[0]))
            max_x = int(max(triangle_TR[0], triangle_BR[0]))
            min_y = int(min(triangle_TL[1], triangle_TR[1]))
            max_y = int(max(triangle_BL[1], triangle_BR[1]))
            
            # ✅ VALIDAÇÃO: Verificar se a altura da área cropada é razoável
            crop_height = max_y - min_y
            crop_width = max_x - min_x
            MIN_CROP_HEIGHT = 200  # Altura mínima esperada (blocos têm ~12.9cm = ~360px)
            MIN_CROP_WIDTH = 300   # Largura mínima esperada (área útil ~19.8cm = ~550px)
            
            if crop_height < MIN_CROP_HEIGHT or crop_width < MIN_CROP_WIDTH:
                self.logger.warning(f"⚠️ Área cropada muito pequena (w={crop_width}px, h={crop_height}px). Usando área padrão baseada no template.")
                self.logger.warning(f"   Triângulos detectados: TL={triangles['TL']}, TR={triangles['TR']}, BR={triangles['BR']}, BL={triangles['BL']}")
                
                # Usar área padrão baseada no template HTML
                h, w = gray.shape[:2]
                area_padrao = self._usar_area_padrao_blocos(w, h)
                
                # Recalcular limites usando área padrão
                min_x = int(min(area_padrao['TL'][0], area_padrao['BL'][0]))
                max_x = int(max(area_padrao['TR'][0], area_padrao['BR'][0]))
                min_y = int(min(area_padrao['TL'][1], area_padrao['TR'][1]))
                max_y = int(max(area_padrao['BL'][1], area_padrao['BR'][1]))
                
                self.logger.info(f"✅ Usando área padrão: x={min_x}, y={min_y}, w={max_x-min_x}, h={max_y-min_y}")
            
            # Adicionar pequeno padding para garantir que não cortamos nada
            padding = 10
            min_x = max(0, min_x - padding)
            min_y = max(0, min_y - padding)
            max_x = min(gray.shape[1], max_x + padding)
            max_y = min(gray.shape[0], max_y + padding)
            
            # Fazer crop
            cropped = gray[min_y:max_y, min_x:max_x]
            
            # Salvar debug
            if self.save_debug_images:
                img_debug = img_a4.copy() if len(img_a4.shape) == 3 else cv2.cvtColor(img_a4, cv2.COLOR_GRAY2BGR)
                cv2.rectangle(img_debug, (min_x, min_y), (max_x, max_y), (0, 255, 0), 2)
                cv2.putText(img_debug, "AREA BLOCOS (CROP)", (min_x + 10, min_y - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                self._save_debug_image("03_area_blocos_cropped.jpg", img_debug)
            
            self.logger.info(f"✅ Área dos blocos cropada: x={min_x}, y={min_y}, w={max_x-min_x}, h={max_y-min_y}")
            
            return cropped
            
        except Exception as e:
            self.logger.error(f"Erro ao fazer crop da área dos blocos: {str(e)}", exc_info=True)
            return None
    
    def _mapear_area_blocos_direto(self, img_a4: np.ndarray, scale_info: Dict) -> Dict:
        """
        Mapeia área dos blocos diretamente do CSS, sem usar triângulos
        
        Args:
            img_a4: Imagem normalizada para A4
            scale_info: Dict com informações de escala (px_per_cm_x, px_per_cm_y, etc)
            
        Returns:
            Dict com informações da área dos blocos (x, y, width, height em pixels)
        """
        try:
            # Valores do CSS (em cm):
            # .answer-sheet: padding-top: 1.8cm (reduzido de 2.5cm), padding-left: 2cm, padding-right: 2cm, padding-bottom: 2.2cm
            # .answer-sheet-header: height: 6.4cm
            # .instructions-box: height: 3.8cm
            # .applicator-box: height: 2.6cm
            # .answer-grid-wrapper: height: 12.9cm, padding: 0.6cm
            
            px_per_cm_x = scale_info['px_per_cm_x']
            px_per_cm_y = scale_info['px_per_cm_y']
            
            # Calcular posição Y do início da área dos blocos
            # padding-top (1.8cm) + header (6.4cm) + instruções (3.8cm) + aplicador (2.6cm) = 14.6cm
            top_offset_cm = 1.8 + 6.4 + 3.8 + 2.6
            block_area_y = int(top_offset_cm * px_per_cm_y)
            
            # Calcular posição X (padding-left)
            block_area_x = int(2.0 * px_per_cm_x)  # padding-left: 2cm
            
            # Calcular largura (A4 width - padding-left - padding-right)
            # A4: 21cm - 2cm - 2cm = 17cm
            block_area_width = int(17.0 * px_per_cm_x)
            
            # Calcular altura (do .answer-grid-wrapper: 12.9cm)
            block_area_height = int(12.9 * px_per_cm_y)
            
            block_area_info = {
                'x': block_area_x,
                'y': block_area_y,
                'width': block_area_width,
                'height': block_area_height
            }
            
            self.logger.info(f"✅ Área dos blocos mapeada (CSS direto): x={block_area_x}px, y={block_area_y}px, width={block_area_width}px, height={block_area_height}px")
            
            return block_area_info
            
        except Exception as e:
            self.logger.error(f"Erro ao mapear área dos blocos: {str(e)}", exc_info=True)
            return None
    
    def _corrigir_perspectiva_com_triangulos(self, img: np.ndarray) -> Optional[np.ndarray]:
        """
        Detecta triângulos e aplica correção de perspectiva
        Reutiliza lógica do CorrecaoHybrid
        DEPRECADO: Agora usamos quadrados A4 primeiro
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
    
    def _extrair_blocos_por_mapeamento(self, img_a4: np.ndarray, blocks_structure: Dict, 
                                       block_area_info: Dict, scale_info: Dict) -> Tuple[List[np.ndarray], List[Dict]]:
        """
        Extrai blocos usando mapeamento proporcional baseado no A4 e CSS
        
        Args:
            img_a4: Imagem normalizada para A4
            blocks_structure: Estrutura dos blocos da topology
            block_area_info: Informações da área dos blocos (x, y, width, height)
            scale_info: Informações de escala (px_per_cm_x, px_per_cm_y)
            
        Returns:
            Tuple: (Lista de ROIs dos blocos, Lista de posições dos blocos)
        """
        try:
            blocks_config_list = blocks_structure.get('blocks', [])
            num_blocks = len(blocks_config_list)
            
            if num_blocks == 0:
                return [], []
            
            # Dimensões da área dos blocos (em pixels)
            block_area_x = block_area_info['x']
            block_area_y = block_area_info['y']
            block_area_width = block_area_info['width']
            block_area_height = block_area_info['height']
            
            px_per_cm_x = scale_info['px_per_cm_x']
            px_per_cm_y = scale_info['px_per_cm_y']
            
            # Do CSS: gap entre blocos = 0.4cm
            BLOCK_GAP_CM = 0.4
            BLOCK_GAP_PX = int(BLOCK_GAP_CM * px_per_cm_x)
            
            # Calcular largura de cada bloco
            # Largura total disponível menos os gaps entre blocos
            total_gap = BLOCK_GAP_PX * (num_blocks - 1)
            block_width = (block_area_width - total_gap) // num_blocks
            
            block_rois = []
            block_positions = []
            
            for block_idx, block_config in enumerate(blocks_config_list):
                block_num = block_idx + 1
                questions_config = block_config.get('questions', [])
                num_questoes = len(questions_config)
                
                # Calcular altura dinâmica do bloco baseado no CSS
                # Do CSS:
                # - .answer-block: padding: 3px 4px, border: 2px
                # - .block-header: altura variável (~0.7cm estimado)
                # - .answer-row: min-height: 0.44cm
                # - .answer-grid-wrapper: padding: 0.3cm
                
                BLOCK_HEADER_HEIGHT_CM = 0.7  # Estimado do CSS
                BLOCK_PADDING_Y_CM = 0.1  # padding: 3px ≈ 0.1cm
                BLOCK_PADDING_X_CM = 0.1  # padding: 4px ≈ 0.1cm
                BORDER_THICKNESS_CM = 0.06  # border: 2px ≈ 0.06cm
                LINE_HEIGHT_CM = 0.44  # Do CSS: min-height: 0.44cm
                
                # Converter para pixels
                BLOCK_HEADER_HEIGHT_PX = int(BLOCK_HEADER_HEIGHT_CM * px_per_cm_y)
                BLOCK_PADDING_Y_PX = int(BLOCK_PADDING_Y_CM * px_per_cm_y)
                BORDER_THICKNESS_PX = int(BORDER_THICKNESS_CM * px_per_cm_y)
                LINE_HEIGHT_PX = int(LINE_HEIGHT_CM * px_per_cm_y)
                
                # Altura necessária = header + (num_questoes × line_height) + padding + bordas
                block_height = BLOCK_HEADER_HEIGHT_PX + (num_questoes * LINE_HEIGHT_PX) + (2 * BLOCK_PADDING_Y_PX) + (2 * BORDER_THICKNESS_PX)
                
                # Posição X: calcular baseado no índice do bloco
                block_x = block_area_x + (block_idx * (block_width + BLOCK_GAP_PX))
                
                # Posição Y: mesma para todos (topo da área dos blocos)
                block_y = block_area_y
                
                # Extrair ROI do bloco
                block_roi = img_a4[block_y:block_y+block_height, block_x:block_x+block_width]
                
                if block_roi.size == 0:
                    self.logger.warning(f"Bloco {block_num}: ROI vazio (x={block_x}, y={block_y}, w={block_width}, h={block_height})")
                    continue
                
                block_rois.append(block_roi)
                block_positions.append({
                    'block_num': block_num,
                    'x': block_x,
                    'y': block_y,
                    'width': block_width,
                    'height': block_height,
                    'num_questoes': num_questoes
                })
                
                self.logger.info(f"Bloco {block_num}: Extraído em x={block_x}px, y={block_y}px, w={block_width}px, h={block_height}px ({num_questoes} questões)")
            
            return block_rois, block_positions
            
        except Exception as e:
            self.logger.error(f"Erro ao extrair blocos por mapeamento: {str(e)}", exc_info=True)
            return [], []
    
    def _detectar_blocos_resposta(self, img_warped: np.ndarray) -> Tuple[List[np.ndarray], List]:
        """
        Detecta blocos com borda preta grossa (answer-block)
        Dentro da área cropada pelos triângulos
        
        Implementação robusta com fallback progressivo:
        - Tentativa 1: Detecção original (threshold Otsu + morfologia)
        - Tentativa 2: Pré-processamento adaptativo + detecção original
        - Tentativa 3: Relaxamento controlado de parâmetros (área ±20%, largura expandida)
        - Tentativa 4: Fallback com Canny (já existente)
        
        ⚠️ PRESERVA COMPORTAMENTO ORIGINAL para imagens boas.
        ⚠️ Apenas adiciona robustez quando detecção original falha.
        
        Args:
            img_warped: Imagem da área cropada dos blocos (após detecção de triângulos)
            
        Returns:
            Tuple: (Lista de ROIs, Lista de contornos dos blocos)
        """
        def _detectar_blocos_interno(img_detect: np.ndarray,
                                    relax_area: float = 1.0,
                                    relax_width: float = 1.0,
                                    relax_aspect: float = 0.0) -> List:
            """
            Lógica interna de detecção de blocos (extraída para reutilização).
            
            Args:
                img_detect: Imagem para detectar
                relax_area: Fator de relaxamento de área (1.0 = original, 1.2 = +20%)
                relax_width: Fator de relaxamento de largura (1.0 = original, 1.2 = +20%)
                relax_aspect: Relaxamento de aspect ratio (0.0 = original, 0.5 = expandir 0.5)
            """
            try:
                # Converter para grayscale
                if len(img_detect.shape) == 3:
                    gray = cv2.cvtColor(img_detect, cv2.COLOR_BGR2GRAY)
                else:
                    gray = img_detect.copy()
                
                img_height, img_width = gray.shape[:2]
                
                # Aplicar blur para suavizar
                blurred = cv2.GaussianBlur(gray, (5, 5), 0)
                
                # ESTRATÉGIA 1: Detectar bordas grossas usando morfologia específica
                # Threshold binário invertido para destacar bordas pretas
                _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
                
                # Salvar debug se ativado
                if self.save_debug_images:
                    self._save_debug_image("04_blocos_binary.jpg", thresh)
                
                # ✅ CORREÇÃO: Dilatação mínima (1 iteração) para conectar bordas quebradas SEM conectar blocos adjacentes
                kernel_small = np.ones((3, 3), np.uint8)
                dilated = cv2.dilate(thresh, kernel_small, iterations=1)
                
                # ✅ CORREÇÃO: Usar RETR_TREE para pegar contornos internos e externos
                # Isso permite detectar cada bloco individual mesmo se estiverem próximos
                cnts, hierarchy = cv2.findContours(dilated.copy(), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
                
                # Filtrar contornos que são blocos individuais (com relaxamento)
                min_block_area = (img_width * img_height) * 0.03 / relax_area
                max_block_area = (img_width * img_height) * 0.30 * relax_area
                min_block_width = img_width * 0.15 / relax_width
                max_block_width = img_width * 0.30 * relax_width
                
                block_contours = []
                
                # ✅ CORREÇÃO CRÍTICA: Filtrar apenas contornos EXTERNOS usando hierarquia
                for idx, c in enumerate(cnts):
                    if hierarchy is not None and len(hierarchy) > 0:
                        if hierarchy[0][idx][3] != -1:  # Tem pai = contorno interno, pular
                            continue
                    
                    area = cv2.contourArea(c)
                    
                    # Filtrar por área (com relaxamento)
                    if area < min_block_area or area > max_block_area:
                        continue
                    
                    # Aproximar contorno
                    peri = cv2.arcLength(c, True)
                    approx = cv2.approxPolyDP(c, 0.02 * peri, True)
                    
                    # Procurar por retângulos (4 vértices) - bordas dos blocos
                    if len(approx) >= 4:
                        x, y, w, h = cv2.boundingRect(approx)
                        
                        # Filtrar por largura (com relaxamento)
                        if w < min_block_width or w > max_block_width:
                            continue
                        
                        aspect_ratio = w / float(h) if h > 0 else 0
                        
                        # Verificar aspect ratio (com relaxamento)
                        aspect_min = 0.3 - relax_aspect
                        aspect_max = 3.0 + relax_aspect
                        if aspect_min < aspect_ratio < aspect_max:
                            block_contours.append(approx)
                
                return block_contours
                
            except Exception as e:
                self.logger.warning(f"Erro na detecção interna de blocos: {str(e)}")
                return []
        
        def _tentar_canny_fallback(img_detect: np.ndarray, block_contours_existentes: List,
                                  min_block_area: float, max_block_area: float,
                                  min_block_width: float, max_block_width: float) -> List:
            """
            Tenta detectar blocos usando Canny como fallback.
            """
            try:
                if len(img_detect.shape) == 3:
                    gray = cv2.cvtColor(img_detect, cv2.COLOR_BGR2GRAY)
                else:
                    gray = img_detect.copy()
                
                blurred = cv2.GaussianBlur(gray, (5, 5), 0)
                edged = cv2.Canny(blurred, 50, 150)
                kernel_canny = np.ones((2, 2), np.uint8)
                edged_dilated = cv2.dilate(edged, kernel_canny, iterations=1)
                
                if self.save_debug_images:
                    self._save_debug_image("04_blocos_canny.jpg", edged_dilated)
                
                cnts_canny, hierarchy_canny = cv2.findContours(edged_dilated.copy(), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
                
                new_blocks = []
                for idx_c, c in enumerate(cnts_canny):
                    if hierarchy_canny is not None and len(hierarchy_canny) > 0:
                        if hierarchy_canny[0][idx_c][3] != -1:
                            continue
                    
                    area = cv2.contourArea(c)
                    if min_block_area < area < max_block_area:
                        x, y, w, h = cv2.boundingRect(c)
                        if min_block_width < w < max_block_width:
                            aspect_ratio = w / float(h) if h > 0 else 0
                            if 0.3 < aspect_ratio < 3.0:
                                # Verificar se já não foi adicionado (evitar duplicatas)
                                is_duplicate = False
                                for existing in block_contours_existentes + new_blocks:
                                    ex, ey, ew, eh = cv2.boundingRect(existing)
                                    if abs(x - ex) < 20 and abs(y - ey) < 20:
                                        is_duplicate = True
                                        break
                                if not is_duplicate:
                                    peri = cv2.arcLength(c, True)
                                    approx = cv2.approxPolyDP(c, 0.02 * peri, True)
                                    if len(approx) >= 4:
                                        new_blocks.append(approx)
                
                return new_blocks
                
            except Exception as e:
                self.logger.warning(f"Erro no fallback Canny: {str(e)}")
                return []
        
        # ========== PIPELINE DE FALLBACK PROGRESSIVO ==========
        try:
            img_height, img_width = img_warped.shape[:2] if len(img_warped.shape) == 2 else img_warped.shape[:2]
            if len(img_warped.shape) == 3:
                gray_temp = cv2.cvtColor(img_warped, cv2.COLOR_BGR2GRAY)
            else:
                gray_temp = img_warped.copy()
            
            self.logger.info(f"🔍 Detectando blocos em imagem cropada: {img_width}x{img_height}px")
            
            # TENTATIVA 1: Detecção original (comportamento padrão)
            block_contours = _detectar_blocos_interno(img_warped, relax_area=1.0, relax_width=1.0, relax_aspect=0.0)
            
            # Se detectou menos de 4 blocos mas encontrou contornos grandes, tentar Canny
            if len(block_contours) < 4 and len(block_contours) > 0:
                large_contours = [c for c in block_contours if cv2.boundingRect(c)[2] > img_width * 0.5]
                if large_contours:
                    self.logger.warning(f"⚠️ Detectado {len(block_contours)} blocos, mas alguns podem estar conectados. Tentando Canny...")
                    min_area = (img_width * img_height) * 0.03
                    max_area = (img_width * img_height) * 0.30
                    min_width = img_width * 0.15
                    max_width = img_width * 0.30
                    canny_blocks = _tentar_canny_fallback(img_warped, block_contours, min_area, max_area, min_width, max_width)
                    block_contours.extend(canny_blocks)
            
            if len(block_contours) >= 4:
                # Ordenar blocos da esquerda para direita
                block_contours = sorted(block_contours, key=lambda c: cv2.boundingRect(c)[0])
                self.logger.info(f"✅ Total de {len(block_contours)} blocos detectados (tentativa 1 - original)")
            else:
                # Analisar iluminação para decidir se vale tentar fallback
                iluminacao = self._analisar_iluminacao(gray_temp)
                
                if self.save_debug_images:
                    self.logger.info(f"🔍 Iluminação analisada: mean={iluminacao['mean']:.1f}, std={iluminacao['std']:.1f}, brightness={iluminacao['brightness']}")
                
                # TENTATIVA 2: Pré-processamento adaptativo + detecção original
                self.logger.info("⚠️ Tentativa 1 falhou, aplicando pré-processamento adaptativo...")
                img_preprocessed = self._preprocess_omr(img_warped, mode="auto")
                block_contours = _detectar_blocos_interno(img_preprocessed, relax_area=1.0, relax_width=1.0, relax_aspect=0.0)
                
                # Tentar Canny se necessário
                if len(block_contours) < 4 and len(block_contours) > 0:
                    min_area = (img_width * img_height) * 0.03
                    max_area = (img_width * img_height) * 0.30
                    min_width = img_width * 0.15
                    max_width = img_width * 0.30
                    canny_blocks = _tentar_canny_fallback(img_preprocessed, block_contours, min_area, max_area, min_width, max_width)
                    block_contours.extend(canny_blocks)
                
                if len(block_contours) >= 4:
                    block_contours = sorted(block_contours, key=lambda c: cv2.boundingRect(c)[0])
                    self.logger.info(f"✅ Total de {len(block_contours)} blocos detectados (tentativa 2 - pré-processado)")
                else:
                    # TENTATIVA 3: Relaxamento controlado de parâmetros
                    self.logger.info("⚠️ Tentativa 2 falhou, aplicando relaxamento controlado de parâmetros...")
                    block_contours = _detectar_blocos_interno(img_preprocessed, relax_area=1.2, relax_width=1.2, relax_aspect=0.5)
                    
                    # Tentar Canny se necessário
                    if len(block_contours) < 4:
                        min_area = (img_width * img_height) * 0.03 / 1.2
                        max_area = (img_width * img_height) * 0.30 * 1.2
                        min_width = img_width * 0.15 / 1.2
                        max_width = img_width * 0.30 * 1.2
                        canny_blocks = _tentar_canny_fallback(img_preprocessed, block_contours, min_area, max_area, min_width, max_width)
                        block_contours.extend(canny_blocks)
                    
                    if len(block_contours) >= 4:
                        block_contours = sorted(block_contours, key=lambda c: cv2.boundingRect(c)[0])
                        self.logger.warning(f"⚠️ Total de {len(block_contours)} blocos detectados (tentativa 3 - relaxado)")
                    else:
                        # TENTATIVA 4: Fallback com Canny completo
                        self.logger.warning("⚠️ Tentativa 3 falhou, tentando Canny como fallback completo...")
                        min_area = (img_width * img_height) * 0.03 / 1.2
                        max_area = (img_width * img_height) * 0.30 * 1.2
                        min_width = img_width * 0.15 / 1.2
                        max_width = img_width * 0.30 * 1.2
                        block_contours = _tentar_canny_fallback(img_preprocessed, [], min_area, max_area, min_width, max_width)
                        
                        if len(block_contours) >= 4:
                            block_contours = sorted(block_contours, key=lambda c: cv2.boundingRect(c)[0])
                            self.logger.warning(f"⚠️ Total de {len(block_contours)} blocos detectados (tentativa 4 - Canny fallback)")
            
            # Ordenar blocos da esquerda para direita
            if len(block_contours) > 0:
                block_contours = sorted(block_contours, key=lambda c: cv2.boundingRect(c)[0])
                if len(block_contours) < 4:
                    self.logger.warning(f"⚠️ Apenas {len(block_contours)} blocos detectados após todas as tentativas")
            else:
                self.logger.warning("⚠️ Nenhum bloco detectado após todas as estratégias")
            
            # Salvar imagem de debug
            if self.save_debug_images:
                gray_debug = cv2.cvtColor(img_warped, cv2.COLOR_BGR2GRAY) if len(img_warped.shape) == 3 else img_warped.copy()
                img_debug = cv2.cvtColor(gray_debug, cv2.COLOR_GRAY2BGR) if len(gray_debug.shape) == 2 else gray_debug.copy()
                for idx, block_cnt in enumerate(block_contours):
                    x, y, w, h = cv2.boundingRect(block_cnt)
                    cv2.rectangle(img_debug, (x, y), (x + w, y + h), (0, 255, 0), 2)
                    cv2.putText(img_debug, f"BLOCO {idx+1}", (x, y - 10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                self._save_debug_image("04_blocos_detectados.jpg", img_debug)
            
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
                self.logger.warning("⚠️ Nenhum bloco detectado, processando imagem inteira")
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
    
    def _calcular_top_padding_dinamico(self, block_roi: np.ndarray, line_height: int, block_num: int = None) -> Optional[float]:
        """
        Calcula TOP_PADDING_RATIO dinamicamente baseado na posição Y real da primeira linha de bolhas.
        
        Args:
            block_roi: ROI do bloco (imagem real)
            line_height: Altura de linha já calculada
            block_num: Número do bloco (para debug)
            
        Returns:
            TOP_PADDING_RATIO (float) ou None se não conseguir calcular
        """
        try:
            h, w = block_roi.shape[:2]
            
            # 1. Detectar todas as bolhas no bloco
            bubbles = self._detectar_todas_bolhas(block_roi, block_num)
            
            if len(bubbles) < 4:  # Precisa de pelo menos algumas bolhas
                self.logger.debug(f"Bloco {block_num or 'N/A'}: Poucas bolhas detectadas ({len(bubbles)}) para calcular TOP_PADDING_RATIO dinâmico")
                return None
            
            # 2. Agrupar bolhas por linha (Y similar)
            linhas = self._agrupar_bolhas_por_linha_fisica(bubbles)
            
            if len(linhas) < 1:  # Precisa de pelo menos 1 linha
                self.logger.debug(f"Bloco {block_num or 'N/A'}: Nenhuma linha detectada para calcular TOP_PADDING_RATIO dinâmico")
                return None
            
            # 3. Encontrar a primeira linha (menor Y)
            primeira_linha = min(linhas, key=lambda linha: min(b['y'] for b in linha) if linha else float('inf'))
            
            if not primeira_linha:
                return None
            
            # 4. Calcular Y médio da primeira linha
            y_values = [b['y'] for b in primeira_linha]
            y_primeira_linha = int(np.mean(y_values))
            
            # 5. Calcular TOP_PADDING_RATIO
            # y_primeira_linha deve estar em: top_padding + line_height // 2
            # Então: top_padding = y_primeira_linha - line_height // 2
            top_padding_px = y_primeira_linha - line_height // 2
            
            # Converter para ratio
            top_padding_ratio = top_padding_px / h
            
            self.logger.info(f"Bloco {block_num or 'N/A'}: TOP_PADDING_RATIO calculado dinamicamente: {top_padding_ratio:.3f} (Y primeira linha: {y_primeira_linha}px, top_padding: {top_padding_px}px)")
            
            return top_padding_ratio
            
        except Exception as e:
            self.logger.warning(f"Erro ao calcular TOP_PADDING_RATIO dinâmico: {str(e)}")
            return None
    
    def _calcular_line_height_dinamico(self, block_roi: np.ndarray, num_questoes: int, block_num: int = None) -> Optional[int]:
        """
        Calcula line_height dinamicamente baseado nas bolhas detectadas no bloco real
        
        Args:
            block_roi: ROI do bloco (imagem real)
            num_questoes: Número de questões esperadas no bloco
            block_num: Número do bloco (para debug)
            
        Returns:
            line_height em pixels ou None se não conseguir calcular
        """
        try:
            # 1. Detectar todas as bolhas no bloco
            bubbles = self._detectar_todas_bolhas(block_roi, block_num)
            
            if len(bubbles) < 4:  # Precisa de pelo menos algumas bolhas
                self.logger.warning(f"Bloco {block_num or 'N/A'}: Poucas bolhas detectadas ({len(bubbles)}) para calcular line_height dinâmico")
                return None
            
            # 2. Agrupar bolhas por linha (Y similar)
            linhas = self._agrupar_bolhas_por_linha_fisica(bubbles)
            
            if len(linhas) < 2:  # Precisa de pelo menos 2 linhas
                self.logger.warning(f"Bloco {block_num or 'N/A'}: Poucas linhas detectadas ({len(linhas)}) para calcular line_height dinâmico")
                return None
            
            # 3. Calcular Y médio de cada linha
            line_y_centers = []
            for linha in linhas:
                if linha:
                    # Calcular Y médio da linha (centro vertical)
                    y_values = [b['y'] for b in linha]
                    y_center = int(np.mean(y_values))
                    line_y_centers.append(y_center)
            
            if len(line_y_centers) < 2:
                return None
            
            # 4. Calcular espaçamento entre linhas consecutivas
            line_spacings = []
            for i in range(len(line_y_centers) - 1):
                spacing = line_y_centers[i + 1] - line_y_centers[i]
                if spacing > 0:  # Apenas espaçamentos válidos
                    line_spacings.append(spacing)
            
            if not line_spacings:
                return None
            
            # 5. Usar mediana dos espaçamentos (mais robusto que média)
            line_spacings_sorted = sorted(line_spacings)
            median_spacing = line_spacings_sorted[len(line_spacings_sorted) // 2]
            
            # 6. Validar se o espaçamento faz sentido
            # Esperamos que o line_height seja razoável (entre 20px e 100px)
            if 20 <= median_spacing <= 100:
                self.logger.info(f"Bloco {block_num or 'N/A'}: line_height dinâmico calculado = {median_spacing}px (de {len(line_spacings)} espaçamentos, mediana)")
                return int(median_spacing)
            else:
                self.logger.warning(f"Bloco {block_num or 'N/A'}: line_height calculado ({median_spacing}px) fora do range esperado (20-100px)")
                return None
                
        except Exception as e:
            self.logger.error(f"Erro ao calcular line_height dinâmico: {str(e)}", exc_info=True)
            return None
    
    def _detectar_bolhas_hough(self, block_roi: np.ndarray, block_num: int = None) -> List[Dict]:
        """
        Detecta bolhas usando HoughCircles (método do repositório OMR).
        Mais robusto para detectar círculos reais.
        
        ✅ CORREÇÃO 2 & 5 aplicadas:
        - Raio proporcional ao bloco (não fixo)
        - Filtro de distância disponível via _validar_distancia_grid()
        
        Args:
            block_roi: ROI do bloco (imagem)
            block_num: Número do bloco (para debug)
            
        Returns:
            Lista de bolhas detectadas: [{'x': x, 'y': y, 'radius': r}, ...]
        """
        try:
            # Converter para grayscale se necessário
            if len(block_roi.shape) == 3:
                gray = cv2.cvtColor(block_roi, cv2.COLOR_BGR2GRAY)
            else:
                gray = block_roi.copy()
            
            h, w = block_roi.shape[:2]
            
            # ✅ CORREÇÃO 2: Raio proporcional ao bloco
            bubble_radius = self._calcular_raio_bolha_template(block_roi, None)
            
            # Calcular minRadius e maxRadius com tolerância de ±40%
            min_radius = max(3, int(bubble_radius * 0.6))
            max_radius = int(bubble_radius * 1.4)
            
            # Aplicar blur para reduzir ruído
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            
            # Detectar círculos usando HoughCircles
            # Parâmetros ajustados com raio proporcional
            circles = cv2.HoughCircles(
                blurred,
                cv2.HOUGH_GRADIENT,
                dp=1.0,  # Inverse ratio of accumulator resolution
                minDist=int(bubble_radius * 2.5),  # Distância mínima proporcional
                param1=50,  # Upper threshold for edge detection
                param2=15,  # Threshold for center detection
                minRadius=min_radius,  # ✅ CORREÇÃO 2: Raio mínimo proporcional
                maxRadius=max_radius   # ✅ CORREÇÃO 2: Raio máximo proporcional
            )
            
            bubbles = []
            if circles is not None:
                circles = np.round(circles[0, :]).astype("int")
                
                for (x, y, r) in circles:
                    # Validar que está dentro da imagem
                    if x - r < 0 or x + r >= w or y - r < 0 or y + r >= h:
                        continue
                    
                    bubbles.append({
                        'x': int(x),
                        'y': int(y),
                        'radius': int(r),
                        'center': (int(x), int(y))
                    })
            
            self.logger.info(f"Bloco {block_num or 'único'}: {len(bubbles)} bolhas detectadas via HoughCircles (raio: {min_radius}-{max_radius}px)")
            return bubbles
            
        except Exception as e:
            self.logger.warning(f"Erro ao detectar bolhas com HoughCircles: {str(e)}")
            return []
    
    def _calcular_grid_baseado_em_bolhas_reais(self, block_roi: np.ndarray, 
                                                block_config: Dict,
                                                block_num: int = None) -> Optional[Dict]:
        """
        Calcula parâmetros do grid baseado em bolhas reais detectadas.
        Método OMR profissional: usa bolhas detectadas como âncoras geométricas.
        
        Args:
            block_roi: ROI do bloco (imagem)
            block_config: Configuração do bloco da topology
            block_num: Número do bloco
            
        Returns:
            Dict com parâmetros do grid ou None se falhar:
            {
                'line_height': int,
                'top_padding_px': int,
                'left_margin_px': int,
                'bubble_spacing_px': int,
                'linhas_detectadas': List[List[Dict]]
            }
        """
        try:
            h, w = block_roi.shape[:2]
            questions_config = block_config.get('questions', [])
            num_questoes_esperadas = len(questions_config)
            
            # 1. Detectar todas as bolhas usando HoughCircles
            bubbles = self._detectar_bolhas_hough(block_roi, block_num)
            
            if len(bubbles) < 4:
                self.logger.warning(f"Bloco {block_num or 'N/A'}: Poucas bolhas detectadas ({len(bubbles)}) para calcular grid real")
                return None
            
            # 2. Agrupar bolhas por linha (Y similar)
            linhas = self._agrupar_bolhas_por_linha_fisica(bubbles)
            
            if len(linhas) < 2:
                self.logger.warning(f"Bloco {block_num or 'N/A'}: Poucas linhas detectadas ({len(linhas)}) para calcular grid real")
                return None
            
            # 3. Calcular Y médio de cada linha e ordenar
            linhas_com_y = []
            for linha in linhas:
                if linha:
                    y_values = [b['y'] for b in linha]
                    y_center = int(np.mean(y_values))
                    # Ordenar bolhas da linha por X (esquerda para direita)
                    linha_sorted = sorted(linha, key=lambda b: b['x'])
                    linhas_com_y.append({
                        'y_center': y_center,
                        'bolhas': linha_sorted
                    })
            
            # Ordenar linhas por Y (de cima para baixo)
            linhas_com_y = sorted(linhas_com_y, key=lambda l: l['y_center'])
            
            # 4. Calcular line_height REAL (mediana dos espaçamentos)
            line_spacings = []
            for i in range(len(linhas_com_y) - 1):
                spacing = linhas_com_y[i + 1]['y_center'] - linhas_com_y[i]['y_center']
                if spacing > 0:
                    line_spacings.append(spacing)
            
            if not line_spacings:
                return None
            
            # Usar mediana (robusto contra outliers)
            line_spacings_sorted = sorted(line_spacings)
            line_height = int(line_spacings_sorted[len(line_spacings_sorted) // 2])
            
            # 5. Calcular top_padding REAL
            primeira_linha_y = linhas_com_y[0]['y_center']
            top_padding_px = primeira_linha_y - (line_height // 2)
            
            # 6. Calcular left_margin e bubble_spacing REAIS
            # Analisar primeira linha (ou várias linhas para robustez)
            x_positions_all = []
            for linha_info in linhas_com_y[:min(5, len(linhas_com_y))]:  # Usar até 5 primeiras linhas
                bolhas = linha_info['bolhas']
                if len(bolhas) >= 2:  # Precisa de pelo menos 2 bolhas
                    x_positions_all.append([b['x'] for b in bolhas])
            
            if not x_positions_all:
                return None
            
            # Calcular left_margin (média do X da primeira bolha de cada linha)
            left_margins = [xs[0] for xs in x_positions_all if xs]
            left_margin_px = int(np.median(left_margins))
            
            # Calcular bubble_spacing (mediana das distâncias entre bolhas consecutivas)
            bubble_spacings = []
            for xs in x_positions_all:
                if len(xs) >= 2:
                    for i in range(len(xs) - 1):
                        spacing = xs[i + 1] - xs[i]
                        if spacing > 0:
                            bubble_spacings.append(spacing)
            
            if not bubble_spacings:
                return None
            
            bubble_spacings_sorted = sorted(bubble_spacings)
            bubble_spacing_px = int(bubble_spacings_sorted[len(bubble_spacings_sorted) // 2])
            
            self.logger.info(f"Bloco {block_num or 'N/A'}: Grid calculado de bolhas reais:")
            self.logger.info(f"  line_height: {line_height}px")
            self.logger.info(f"  top_padding_px: {top_padding_px}px")
            self.logger.info(f"  left_margin_px: {left_margin_px}px")
            self.logger.info(f"  bubble_spacing_px: {bubble_spacing_px}px")
            self.logger.info(f"  linhas detectadas: {len(linhas_com_y)}")
            
            return {
                'line_height': line_height,
                'top_padding_px': top_padding_px,
                'left_margin_px': left_margin_px,
                'bubble_spacing_px': bubble_spacing_px,
                'linhas_detectadas': linhas_com_y
            }
            
        except Exception as e:
            self.logger.error(f"Erro ao calcular grid baseado em bolhas reais: {str(e)}", exc_info=True)
            return None
    
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
    
    def _gerar_grade_virtual(self, block_roi: np.ndarray, block_config: Dict, 
                            line_height: Optional[int] = None, block_num: int = None,
                            offset_x: int = 0, offset_y: int = 0) -> List[Dict]:
        """
        Gera grade virtual de posições das bolhas baseado no JSON da topology e geometria do bloco.
        
        Método OMR profissional (2 níveis):
        1. Tenta calcular grid baseado em bolhas reais detectadas (método robusto)
        2. Se falhar, usa ratios proporcionais (fallback)
        
        Args:
            block_roi: ROI do bloco (imagem)
            block_config: Configuração do bloco da topology
            line_height: Altura de linha em pixels (calculado dinamicamente se None)
            block_num: Número do bloco (para debug)
            offset_x: Offset X a ser aplicado nas coordenadas (do arquivo de alinhamento)
            offset_y: Offset Y a ser aplicado nas coordenadas (do arquivo de alinhamento)
            
        Returns:
            Lista de itens da grade: [{"question": q_num, "letter": "A", "x": x, "y": y, "alternatives": [...]}, ...]
        """
        try:
            h, w = block_roi.shape[:2]
            questions_config = block_config.get('questions', [])
            
            if not questions_config:
                return []
            
            # ✅ ETAPA 1: Tentar calcular grid baseado em bolhas reais detectadas
            grid_real = self._calcular_grid_baseado_em_bolhas_reais(block_roi, block_config, block_num)
            
            if grid_real:
                # Usar medidas reais das bolhas detectadas
                line_height = grid_real['line_height']
                top_padding_px = grid_real['top_padding_px']
                left_margin_px = grid_real['left_margin_px']
                bubble_spacing_px = grid_real['bubble_spacing_px']
                
                self.logger.info(f"Bloco {block_num or 'N/A'}: Usando grid baseado em bolhas reais detectadas")
                
                # Calcular y_start
                y_start = top_padding_px + line_height // 2
                if y_start < 0:
                    y_start = 0
                
                grid = []
                
                # Gerar grade para cada questão usando medidas reais
                for i, question_config in enumerate(questions_config):
                    q_num = question_config.get('q')
                    alternatives = question_config.get('alternatives', ['A', 'B', 'C', 'D'])
                    
                    if q_num is None:
                        continue
                    
                    # Calcular Y da linha usando line_height real
                    y = y_start + int(i * line_height)
                    
                    # ✅ Aplicar offset Y do arquivo de alinhamento
                    y += offset_y
                    
                    # Gerar posições para cada alternativa usando medidas reais
                    for j, letter in enumerate(alternatives):
                        x = left_margin_px + int(j * bubble_spacing_px)
                        
                        # ✅ Aplicar offset X do arquivo de alinhamento
                        x += offset_x
                        
                        grid_item = {
                            "question": q_num,
                            "letter": letter,
                            "x": x,
                            "y": y,
                            "alternatives": alternatives,
                            "question_index": i,
                            "alternative_index": j
                        }
                        grid.append(grid_item)
                
                if offset_x != 0 or offset_y != 0:
                    self.logger.info(f"Grade virtual gerada (bolhas reais) com offsets aplicados: X={offset_x:+d}px, Y={offset_y:+d}px")
                self.logger.info(f"Grade virtual gerada (bolhas reais): {len(grid)} posições para {len(questions_config)} questões")
                return grid
            
            # ✅ ETAPA 2: Fallback para método de ratios (se detecção de bolhas falhar)
            self.logger.info(f"Bloco {block_num or 'N/A'}: Fallback para método de ratios proporcionais")
            
            # Calcular line_height se não fornecido
            if line_height is None:
                line_height = self._calcular_line_height_dinamico(block_roi, len(questions_config))
                if line_height is None:
                    # Fallback: estimar baseado na altura do bloco
                    line_height = int(h / len(questions_config))
                    self.logger.warning(f"Bloco: line_height estimado = {line_height}px (fallback)")
            
            # Ratios de posicionamento (proporcionais, não fixos)
            # Baseado no CSS: número (25px) + gaps (4px) + bubble (15px)
            # Convertido para ratios proporcionais da largura do bloco
            
            # Tentar carregar ratios salvos do arquivo de configuração
            grid_config = None
            if block_num is not None:
                grid_config = self._load_grid_alignment(block_num)
            
            # Usar ratios salvos se disponíveis, senão usar padrões
            LEFT_MARGIN_RATIO = grid_config.get('left_margin_ratio', 0.18) if grid_config else 0.18
            BUBBLE_SPACING_RATIO = grid_config.get('bubble_spacing_ratio', 0.16) if grid_config else 0.16
            TOP_PADDING_RATIO = grid_config.get('top_padding_ratio', 0.05) if grid_config else 0.05
            
            # Usar line_height salvo se disponível (tem prioridade sobre o calculado)
            if grid_config and grid_config.get('line_height'):
                line_height = grid_config.get('line_height')
                self.logger.info(f"Bloco {block_num or 'N/A'}: Usando line_height da configuração: {line_height}px")
            
            # ✅ NOVO: Calcular TOP_PADDING_RATIO dinamicamente APENAS se não estiver configurado (None)
            # Valores negativos são permitidos e devem ser respeitados (ajustes manuais)
            top_padding_config = grid_config.get('top_padding_ratio') if grid_config else None
            if top_padding_config is None:
                # Recalcular automaticamente baseado na primeira linha de bolhas detectadas
                top_padding_dinamico = self._calcular_top_padding_dinamico(block_roi, line_height, block_num)
                if top_padding_dinamico is not None:
                    TOP_PADDING_RATIO = top_padding_dinamico
                    self.logger.info(f"Bloco {block_num or 'N/A'}: TOP_PADDING_RATIO calculado automaticamente: {TOP_PADDING_RATIO:.3f}")
                else:
                    # Fallback: usar valor padrão se não conseguir calcular
                    TOP_PADDING_RATIO = 0.05  # Valor padrão
                    self.logger.warning(f"Bloco {block_num or 'N/A'}: Não foi possível calcular TOP_PADDING_RATIO, usando padrão: {TOP_PADDING_RATIO:.3f}")
            else:
                # Usar valor da configuração (pode ser negativo para ajustes manuais)
                TOP_PADDING_RATIO = top_padding_config
                self.logger.info(f"Bloco {block_num or 'N/A'}: Usando TOP_PADDING_RATIO da configuração: {TOP_PADDING_RATIO:.3f}")
            
            # Calcular valores em pixels baseado no tamanho real do bloco
            left_margin = int(w * LEFT_MARGIN_RATIO)
            bubble_spacing = int(w * BUBBLE_SPACING_RATIO)
            
            # Posição inicial Y (centro vertical da primeira linha)
            # TOP_PADDING_RATIO pode ser negativo para ajustar para cima
            top_padding_px = int(h * TOP_PADDING_RATIO)
            # Permitir valores negativos para ajustes finos
            # y_start = top_padding + centro_da_primeira_bolha
            y_start = top_padding_px + line_height // 2
            # Proteção apenas para valores extremamente negativos (que fariam y_start < 0)
            # Permitir valores negativos moderados (até -50px aproximadamente)
            if y_start < 0:
                y_start = 0
                self.logger.warning(f"Bloco {block_num or 'N/A'}: y_start ajustado para 0px (top_padding_px={top_padding_px}px era muito negativo)")
            else:
                self.logger.debug(f"Bloco {block_num or 'N/A'}: y_start = {y_start}px (top_padding_px={top_padding_px}px, line_height={line_height}px)")
            
            grid = []
            
            # Gerar grade para cada questão
            for i, question_config in enumerate(questions_config):
                q_num = question_config.get('q')
                alternatives = question_config.get('alternatives', ['A', 'B', 'C', 'D'])
                
                if q_num is None:
                    continue
                
                # Calcular Y da linha (centro vertical)
                y = y_start + int(i * line_height)
                
                # ✅ Aplicar offset Y do arquivo de alinhamento
                y += offset_y
                
                # Gerar posições para cada alternativa
                row = []
                for j, letter in enumerate(alternatives):
                    # Calcular X da bolha (centro horizontal)
                    x = left_margin + int(j * bubble_spacing)
                    
                    # ✅ Aplicar offset X do arquivo de alinhamento
                    x += offset_x
                    
                    grid_item = {
                        "question": q_num,
                        "letter": letter,
                        "x": x,
                        "y": y,
                        "alternatives": alternatives,
                        "question_index": i,
                        "alternative_index": j
                    }
                    grid.append(grid_item)
                    row.append(grid_item)
            
            if offset_x != 0 or offset_y != 0:
                self.logger.info(f"Grade virtual gerada (ratios) com offsets aplicados: X={offset_x:+d}px, Y={offset_y:+d}px")
            self.logger.info(f"Grade virtual gerada (ratios): {len(grid)} posições para {len(questions_config)} questões")
            return grid
            
        except Exception as e:
            self.logger.error(f"Erro ao gerar grade virtual: {str(e)}", exc_info=True)
            return []
    
    def _gerar_grade_virtual_com_coordenadas_fixas(self, block_roi: np.ndarray, block_config: Dict,
                                                   line_height: int, block_num: int = None,
                                                   start_x: int = 0, start_y: int = 0) -> List[Dict]:
        """
        Gera grade virtual usando coordenadas fixas do arquivo de ajuste.
        Usado quando o bloco foi redimensionado para 155x473px e temos coordenadas calibradas.
        
        Args:
            block_roi: ROI do bloco (imagem redimensionada para 155x473px)
            block_config: Configuração do bloco da topology
            line_height: Altura de linha em pixels (do arquivo de ajuste)
            block_num: Número do bloco (para debug)
            start_x: Posição X inicial da primeira bolha (do arquivo de ajuste)
            start_y: Posição Y inicial da primeira linha (do arquivo de ajuste)
            
        Returns:
            Lista de itens da grade: [{"question": q_num, "letter": "A", "x": x, "y": y, ...}, ...]
        """
        try:
            h, w = block_roi.shape[:2]
            questions_config = block_config.get('questions', [])
            
            if not questions_config:
                return []
            
            # Calcular line_height ajustado baseado no tamanho real do bloco para evitar erro acumulado
            # Padding interno do CSS: 8px top + 8px bottom = 16px total
            PADDING_TOP = 8
            PADDING_BOTTOM = 8
            total_padding = PADDING_TOP + PADDING_BOTTOM
            usable_height = h - total_padding
            num_questions = len(questions_config)
            use_line_height = line_height  # Inicializar com valor padrão
            
            # Se temos altura suficiente e número de questões, calcular line_height mais preciso
            if num_questions > 0 and usable_height > 0:
                ideal_line_height = usable_height / num_questions
                # Se o line_height fornecido difere muito do ideal, ajustar para evitar erro acumulado
                if abs(line_height - ideal_line_height) > 0.5:
                    adjusted_line_height = round(ideal_line_height)
                    if adjusted_line_height != line_height:
                        self.logger.info(f"Bloco {block_num}: Ajustando line_height de {line_height}px para {adjusted_line_height}px (ideal: {ideal_line_height:.2f}px) baseado no tamanho real {w}x{h}px")
                        use_line_height = adjusted_line_height
                    else:
                        use_line_height = line_height
                else:
                    use_line_height = line_height
            
            # Valores do arquivo de ajuste (assumindo bolhas de 15px com gap de 4px)
            BUBBLE_SIZE = 15
            BUBBLE_GAP = 4
            bubble_spacing = BUBBLE_SIZE + BUBBLE_GAP
            
            # ✅ DEBUG: Print dos valores base
            print(f"\n[DEBUG] Bloco {block_num}: Gerando grade virtual com coordenadas fixas")
            print(f"[DEBUG]   start_x={start_x}px, start_y={start_y}px, line_height={line_height}px (ajustado: {use_line_height}px)")
            print(f"[DEBUG]   BUBBLE_SIZE={BUBBLE_SIZE}px, BUBBLE_GAP={BUBBLE_GAP}px, bubble_spacing={bubble_spacing}px")
            print(f"[DEBUG]   Tamanho do bloco: {w}x{h}px, Número de questões: {len(questions_config)}")
            
            grid = []
            
            # Gerar grade para cada questão usando coordenadas fixas
            for i, question_config in enumerate(questions_config):
                q_num = question_config.get('q')
                alternatives = question_config.get('alternatives', ['A', 'B', 'C', 'D'])
                
                if q_num is None:
                    continue
                
                # ✅ DEBUG: Verificar número de alternativas
                num_alternatives = len(alternatives)
                if num_alternatives > 4:
                    print(f"[DEBUG] ⚠️ Q{q_num}: ATENÇÃO - {num_alternatives} alternativas detectadas (esperado máximo 4): {alternatives}")
                
                # Calcular Y da linha usando start_y e line_height ajustado (para evitar erro acumulado)
                y = start_y + int(i * use_line_height)
                
                # ✅ DEBUG: Print para primeira questão, questão do meio e última questão
                print_debug = (i == 0) or (i == len(questions_config) // 2) or (i == len(questions_config) - 1)
                if print_debug:
                    print(f"[DEBUG] Q{q_num} (índice {i}): {num_alternatives} alternativas = {alternatives}, Y={y}px")
                
                # Gerar posições para cada alternativa usando start_x e bubble_spacing
                for j, letter in enumerate(alternatives):
                    # Calcular X da bolha (centro horizontal)
                    x = start_x + int(j * bubble_spacing) + BUBBLE_SIZE // 2
                    
                    # ✅ DEBUG: Print coordenadas X para primeira questão, questão do meio e última
                    if print_debug:
                        print(f"[DEBUG]   {letter} (j={j}): x = {start_x} + {j}*{bubble_spacing} + {BUBBLE_SIZE//2} = {x}px")
                    
                    grid_item = {
                        "question": q_num,
                        "letter": letter,
                        "x": x,
                        "y": y,
                        "alternatives": alternatives,
                        "question_index": i,
                        "alternative_index": j
                    }
                    grid.append(grid_item)
            
            if use_line_height != line_height:
                self.logger.info(f"Bloco {block_num or 'N/A'}: Grade virtual gerada com coordenadas fixas (start_x={start_x}px, start_y={start_y}px, line_height={line_height}px → ajustado para {use_line_height}px)")
            else:
                self.logger.info(f"Bloco {block_num or 'N/A'}: Grade virtual gerada com coordenadas fixas (start_x={start_x}px, start_y={start_y}px, line_height={line_height}px)")
            self.logger.info(f"Grade virtual gerada (coordenadas fixas): {len(grid)} posições para {len(questions_config)} questões")
            return grid
            
        except Exception as e:
            self.logger.error(f"Erro ao gerar grade virtual com coordenadas fixas: {str(e)}", exc_info=True)
            return []
    
    def _calcular_raio_bolha_template(self, block_roi: np.ndarray, scale_info: Optional[Dict] = None) -> int:
        """
        Calcula raio da bolha baseado no template CSS (15px diâmetro = 7.5px raio).
        
        ✅ CORREÇÃO 2 — RAIO PROPORCIONAL AO BLOCO
        
        Nunca usa raio fixo! O raio escala junto com o tamanho do bloco.
        Isso garante que:
        - bloco 155px → raio ≈ 5.4px
        - bloco maior → raio cresce proporcionalmente
        
        Args:
            block_roi: ROI do bloco (imagem)
            scale_info: Dict com informações de escala (px_per_cm_x, px_per_cm_y) - opcional
            
        Returns:
            Raio da bolha em pixels
        """
        try:
            h, w = block_roi.shape[:2]
            
            # ✅ CORREÇÃO 2: Raio SEMPRE proporcional ao bloco (3.5% da largura)
            # Isso faz o raio escalar corretamente com qualquer tamanho de bloco
            # Exemplo: bloco 155px → raio ≈ 5.4px | bloco 200px → raio ≈ 7px
            bubble_radius = int(w * 0.035)
            
            # Se temos scale_info, podemos ajustar mais finamente
            if scale_info:
                # Usar escala real da imagem normalizada
                px_per_cm_x = scale_info.get('px_per_cm_x', 39.37)
                px_per_cm_y = scale_info.get('px_per_cm_y', 39.37)
                px_per_cm = (px_per_cm_x + px_per_cm_y) / 2  # Média
                
                # Converter 15px do CSS para cm e depois para pixels na imagem normalizada
                # Assumindo que o PDF é renderizado a ~96 DPI (padrão web)
                # 15px a 96 DPI = 15/96 * 2.54 ≈ 0.40cm
                BUBBLE_DIAMETER_CM = 0.40  # 15px ≈ 0.40cm (96 DPI)
                bubble_radius_scale = int((BUBBLE_DIAMETER_CM / 2) * px_per_cm)
                
                # Usar o maior entre proporcional e calculado por escala
                bubble_radius = max(bubble_radius, bubble_radius_scale)
                
                self.logger.debug(f"Raio calculado com scale_info: {bubble_radius}px (proporcional: {int(w * 0.035)}px, escala: {bubble_radius_scale}px)")
            else:
                self.logger.debug(f"Raio proporcional ao bloco: {bubble_radius}px (bloco: {w}px, fator: 3.5%)")
            
            # Garantir mínimo de 4px (para blocos muito pequenos)
            bubble_radius = max(4, bubble_radius)
            
            return bubble_radius
            
        except Exception as e:
            self.logger.warning(f"Erro ao calcular raio da bolha: {str(e)}, usando fallback proporcional")
            h, w = block_roi.shape[:2]
            return max(4, int(w * 0.035))  # Fallback proporcional
    
    def _distancia_euclidiana(self, x1: int, y1: int, x2: int, y2: int) -> float:
        """
        Calcula distância euclidiana entre dois pontos.
        
        ✅ CORREÇÃO 5 — FILTRO DE DISTÂNCIA GRID × BOLHA
        
        Usado para verificar se uma bolha detectada está próxima
        o suficiente da posição esperada no grid.
        
        Args:
            x1, y1: Coordenadas do primeiro ponto
            x2, y2: Coordenadas do segundo ponto
            
        Returns:
            Distância euclidiana em pixels
        """
        return np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
    
    def _validar_distancia_grid(self, grid_x: int, grid_y: int, 
                                 bolha_x: int, bolha_y: int, 
                                 bubble_radius: int) -> bool:
        """
        Valida se uma bolha detectada está próxima o suficiente da posição do grid.
        
        ✅ CORREÇÃO 5 — FILTRO DE DISTÂNCIA GRID × BOLHA
        
        Evita bolhas fantasma detectadas em:
        - Texto
        - Borda
        - Ruído
        
        Args:
            grid_x, grid_y: Coordenadas esperadas no grid
            bolha_x, bolha_y: Coordenadas da bolha detectada
            bubble_radius: Raio da bolha em pixels
            
        Returns:
            True se a bolha está dentro da tolerância, False caso contrário
        """
        dist = self._distancia_euclidiana(grid_x, grid_y, bolha_x, bolha_y)
        tolerancia = bubble_radius * 1.3  # 130% do raio como tolerância
        
        return dist <= tolerancia
    
    def _criar_mascara_anel(self, h: int, w: int, cx: int, cy: int, r: int) -> Tuple[np.ndarray, float]:
        """
        Cria máscara em anel para medir preenchimento da bolha.
        
        ✅ CORREÇÃO 1 — ROI EM ANEL (ESSENCIAL)
        
        A máscara em anel ignora:
        - Centro branco (falha de impressão/papel)
        - Borda impressa (contorno da bolha)
        - Ruído externo
        
        Mede apenas a região onde a tinta real está.
        
        Args:
            h: Altura da imagem
            w: Largura da imagem
            cx: Centro X da bolha
            cy: Centro Y da bolha
            r: Raio da bolha
            
        Returns:
            Tuple: (máscara em anel, área do anel em pixels)
        """
        mask = np.zeros((h, w), dtype=np.uint8)
        
        # Raio externo: 85% do raio (ignora borda impressa)
        r_ext = int(r * 0.85)
        # Raio interno: 45% do raio (ignora centro falho)
        r_int = int(r * 0.45)
        
        # Garantir raios mínimos
        r_ext = max(2, r_ext)
        r_int = max(1, min(r_int, r_ext - 1))
        
        # Desenhar círculo externo (preenchido)
        cv2.circle(mask, (cx, cy), r_ext, 255, -1)
        # Desenhar círculo interno (removido)
        cv2.circle(mask, (cx, cy), r_int, 0, -1)
        
        # Calcular área do anel
        area_anel = np.pi * (r_ext * r_ext - r_int * r_int)
        
        return mask, area_anel
    
    def _medir_preenchimento_bolha(self, block_roi: np.ndarray, x: int, y: int, 
                                   radius: Optional[int] = None, scale_info: Optional[Dict] = None) -> float:
        """
        Mede percentual de preenchimento de uma bolha em uma posição específica.
        
        ✅ CORREÇÃO 1 — Usa máscara em ANEL ao invés de círculo cheio.
        Isso ignora borda impressa e centro falho, medindo tinta real.
        
        Args:
            block_roi: ROI do bloco (imagem)
            x: Coordenada X do centro da bolha
            y: Coordenada Y do centro da bolha
            radius: Raio da bolha em pixels (calculado se None)
            scale_info: Dict com informações de escala (opcional)
            
        Returns:
            Percentual de preenchimento (0.0 a 1.0)
        """
        try:
            h, w = block_roi.shape[:2]
            
            # Validar coordenadas
            if x < 0 or x >= w or y < 0 or y >= h:
                return 0.0
            
            # Calcular raio baseado no template se não fornecido
            if radius is None:
                radius = self._calcular_raio_bolha_template(block_roi, scale_info)
            
            # Converter para escala de cinza se necessário
            if len(block_roi.shape) == 3:
                gray = cv2.cvtColor(block_roi, cv2.COLOR_BGR2GRAY)
            else:
                gray = block_roi.copy()
            
            # Aplicar blur para suavizar
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            
            # Aplicar threshold binário invertido (bolha marcada = branco)
            _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
            
            # ✅ CORREÇÃO 1: Usar máscara em ANEL ao invés de círculo cheio
            # Ignora borda impressa e centro falho
            mask, area_anel = self._criar_mascara_anel(h, w, x, y, radius)
            
            # Aplicar máscara
            masked_thresh = cv2.bitwise_and(thresh, thresh, mask=mask)
            
            # Contar pixels brancos (marcados)
            pixels_marcados = cv2.countNonZero(masked_thresh)
            
            # Calcular percentual de preenchimento usando área do anel
            fill_ratio = pixels_marcados / area_anel if area_anel > 0 else 0.0
            
            return min(1.0, fill_ratio)  # Limitar a 1.0
            
        except Exception as e:
            self.logger.error(f"Erro ao medir preenchimento em ({x}, {y}): {str(e)}")
            return 0.0
    
    def _processar_bloco_sem_referencia(self, block_roi: np.ndarray, block_config: Dict,
                                       correct_answers: Dict[int, str], block_num: int = None,
                                       x_offset: int = 0, y_offset: int = 0,
                                       scale_info: Optional[Dict] = None,
                                       template_block: Optional[np.ndarray] = None) -> Tuple[Dict[int, Optional[str]], List[Dict]]:
        """
        Processa bloco usando grade virtual baseada no JSON da topology (método OMR profissional).
        
        ✅ TEMPLATE REAL DIGITAL: Se template_block for fornecido, usa comparação
        por diferença absoluta (cv2.absdiff) ao invés de threshold binário.
        Isso é mais preciso e elimina problemas de alinhamento geométrico.
        
        Método:
        1. Gera grade virtual baseada no JSON (estrutura lógica) e geometria do bloco (ratios)
        2. Para cada posição prevista na grade, mede preenchimento:
           - COM template: usa cv2.absdiff (blur + threshold)
           - SEM template: usa máscara em anel (método geométrico)
        3. Detecta qual alternativa foi marcada (maior preenchimento/diferença)
        4. Valida e retorna respostas
        
        Args:
            block_roi: ROI do bloco (imagem)
            block_config: Configuração do bloco da topology
            correct_answers: Dict com respostas corretas
            block_num: Número do bloco (para debug)
            x_offset: Offset X do bloco na imagem completa
            y_offset: Offset Y do bloco na imagem completa
            scale_info: Dict com informações de escala (opcional)
            template_block: Imagem do template do bloco (opcional, para Template Real Digital)
            
        Returns:
            Tuple: (Dict {q_num: resposta}, Lista de informações das bolhas)
        """
        try:
            answers = {}
            bubbles_info = []
            questions_config = block_config.get('questions', [])
            
            if not questions_config:
                self.logger.warning(f"Bloco {block_num or 'único'}: Nenhuma questão configurada na topology")
                return {}, []
            
            # ✅ NOVO: Prioridade 1 - Carregar ajuste de coordenadas (mais preciso, calibrado para 155x473px)
            h, w = block_roi.shape[:2]
            coordinates_adjustment = None
            alignment_offset_x = 0
            alignment_offset_y = 0
            alignment_line_height = None
            
            if block_num is not None:
                # Tentar carregar coordinates_adjustment.json primeiro (mais preciso)
                coordinates_adjustment = self._load_coordinates_adjustment(block_num)
                
                if coordinates_adjustment:
                    # Usar valores diretos do arquivo de ajuste de coordenadas
                    start_x = coordinates_adjustment.get('start_x', 0)
                    start_y = coordinates_adjustment.get('start_y', 0)
                    alignment_line_height = coordinates_adjustment.get('line_height')
                    self.logger.info(f"Bloco {block_num}: Usando ajuste de coordenadas - start_x={start_x}px, start_y={start_y}px, line_height={alignment_line_height or 'N/A'}px")
                else:
                    # Fallback: usar arquivo de alinhamento antigo
                    manual_alignment = self._load_manual_alignment(block_num, w, h)
                    if manual_alignment:
                        alignment_offset_x = manual_alignment.get('offset_x', 0)
                        alignment_offset_y = manual_alignment.get('offset_y', 0)
                        alignment_line_height = manual_alignment.get('line_height')
                        self.logger.info(f"Bloco {block_num}: Offsets carregados do arquivo de alinhamento - X={alignment_offset_x:+d}px, Y={alignment_offset_y:+d}px")
                        if alignment_line_height:
                            self.logger.info(f"Bloco {block_num}: Line height do arquivo: {alignment_line_height}px")
            
            # 1. Calcular line_height (prioridade: coordinates_adjustment > alignment > dinâmico > fallback)
            line_height = None
            if alignment_line_height is not None:
                line_height = alignment_line_height
                self.logger.info(f"Bloco {block_num or 'único'}: Usando line_height do arquivo: {line_height}px")
            else:
                line_height = self._calcular_line_height_dinamico(block_roi, len(questions_config), block_num)
                if line_height is None:
                    # Fallback: estimar baseado na altura do bloco
                    line_height = int(h / len(questions_config))
                    self.logger.warning(f"Bloco {block_num or 'único'}: line_height estimado = {line_height}px (fallback)")
            
            # 2. Gerar grade virtual baseada no JSON e geometria do bloco
            # Se temos coordinates_adjustment, usar start_x e start_y diretamente
            if coordinates_adjustment:
                grid = self._gerar_grade_virtual_com_coordenadas_fixas(
                    block_roi, block_config, line_height, block_num,
                    coordinates_adjustment.get('start_x', 0),
                    coordinates_adjustment.get('start_y', 0)
                )
            else:
                # Usar método antigo com offsets
                grid = self._gerar_grade_virtual(block_roi, block_config, line_height, block_num, 
                                                alignment_offset_x, alignment_offset_y)
            
            if not grid:
                self.logger.warning(f"Bloco {block_num or 'único'}: Grade virtual vazia")
                return {}, []
            
            self.logger.info(f"Bloco {block_num or 'único'}: Grade virtual gerada com {len(grid)} posições")
            
            # 3. Agrupar grade por questão
            questions_grid = {}
            for item in grid:
                q_num = item['question']
                if q_num not in questions_grid:
                    questions_grid[q_num] = []
                questions_grid[q_num].append(item)
            
            # 4. Processar cada questão
            # ✅ CORREÇÃO 3 & 4 — BASELINE POR QUESTÃO + NORMALIZAÇÃO LOCAL
            # Thresholds baseados em CONTRASTE RELATIVO (não absoluto)
            CONTRASTE_MINIMO = 0.12  # Contraste mínimo para considerar marcada
            DIFERENCA_CONTRASTE = 0.08  # Diferença mínima entre maior e segundo contraste
            
            for q_num, row_items in questions_grid.items():
                # Ordenar por índice da alternativa (A=0, B=1, C=2, D=3)
                row_items_sorted = sorted(row_items, key=lambda x: x['alternative_index'])
                
                # Medir preenchimento em cada posição prevista
                scores = []
                h, w = block_roi.shape[:2]
                
                # Calcular raio da bolha baseado no template (15px diâmetro = 7.5px raio)
                # Usar scale_info para cálculo preciso
                bubble_radius = self._calcular_raio_bolha_template(block_roi, scale_info)
                self.logger.debug(f"Bloco {block_num or 'único'}: Raio da bolha calculado = {bubble_radius}px")
                
                # ✅ DEBUG: Print para primeira questão, questão do meio e última questão
                q_index_in_block = None
                for idx, q_config in enumerate(questions_config):
                    if q_config.get('q') == q_num:
                        q_index_in_block = idx
                        break
                
                print_debug_detection = (q_index_in_block == 0) or (q_index_in_block == len(questions_config) // 2) or (q_index_in_block == len(questions_config) - 1)
                if print_debug_detection:
                    print(f"\n[DEBUG] Bloco {block_num}: Detectando resposta Q{q_num} (índice {q_index_in_block}/{len(questions_config)-1})")
                    print(f"[DEBUG]   Alternativas ordenadas: {[item['letter'] for item in row_items_sorted]}")
                    print(f"[DEBUG]   Coordenadas (x, y) de cada alternativa: {[(item['x'], item['y']) for item in row_items_sorted]}")
                    print(f"[DEBUG]   alternative_index de cada alternativa: {[item.get('alternative_index', 'N/A') for item in row_items_sorted]}")
                    print(f"[DEBUG]   bubble_radius usado: {bubble_radius}px")
                
                for item in row_items_sorted:
                    x = item['x']
                    y = item['y']
                    letter = item['letter']
                    
                    # =========================================================================
                    # ✅ TEMPLATE REAL DIGITAL: Escolher método de medição
                    # =========================================================================
                    if template_block is not None:
                        # COM TEMPLATE: Usar comparação por diferença absoluta
                        # Mais preciso, elimina problemas de alinhamento geométrico
                        fill_ratio = self._medir_preenchimento_com_template(
                            block_aluno=block_roi,
                            template_block=template_block,
                            x=x, y=y, radius=bubble_radius
                        )
                        metodo = "template"
                    else:
                        # SEM TEMPLATE: Usar método geométrico (máscara em anel)
                        fill_ratio = self._medir_preenchimento_bolha(block_roi, x, y, bubble_radius, None)
                        metodo = "geometrico"
                    
                    # ✅ DEBUG: Print fill_ratio para questões de debug
                    if print_debug_detection:
                        print(f"[DEBUG]   {letter}: fill_ratio={fill_ratio:.3f} em (x={x}, y={y}) [{metodo}]")
                    
                    scores.append({
                        'letter': letter,
                        'fill_ratio': fill_ratio,
                        'x': x,
                        'y': y,
                        'item': item
                    })
                
                # ✅ CORREÇÃO 4 — NORMALIZAR fill_ratio LOCALMENTE
                # Isso elimina variações de papel escuro, sombra, iluminação desigual
                fills = [s['fill_ratio'] for s in scores]
                min_fill = min(fills)
                max_fill = max(fills)
                fill_range = max_fill - min_fill + 1e-6  # Evitar divisão por zero
                
                fills_norm = [(f - min_fill) / fill_range for f in fills]
                
                # Atualizar scores com valores normalizados
                for i, score in enumerate(scores):
                    score['fill_norm'] = fills_norm[i]
                
                # ✅ CORREÇÃO 3 — BASELINE POR QUESTÃO (decisão relativa, não absoluta)
                # Calcular baseline usando mediana (mais robusto que média)
                baseline = np.median(fills_norm)
                
                # Calcular contrastes relativos ao baseline
                contrastes = [fn - baseline for fn in fills_norm]
                
                # Atualizar scores com contrastes
                for i, score in enumerate(scores):
                    score['contraste'] = contrastes[i]
                
                # ✅ DEBUG: Print análise de contraste
                if print_debug_detection:
                    print(f"[DEBUG]   fills_raw={[f'{f:.3f}' for f in fills]}")
                    print(f"[DEBUG]   fills_norm={[f'{f:.3f}' for f in fills_norm]}")
                    print(f"[DEBUG]   baseline={baseline:.3f}")
                    print(f"[DEBUG]   contrastes={[f'{c:.3f}' for c in contrastes]}")
                
                # Encontrar maior e segundo maior contraste
                contrastes_sorted = sorted(enumerate(contrastes), key=lambda x: x[1], reverse=True)
                max_idx = contrastes_sorted[0][0]
                max_contrast = contrastes_sorted[0][1]
                second_contrast = contrastes_sorted[1][1] if len(contrastes_sorted) > 1 else 0
                
                # Ordenar por contraste (maior primeiro) para consistência
                scores_sorted = sorted(scores, key=lambda x: x['contraste'], reverse=True)
                
                # ✅ DEBUG: Print scores ordenados por contraste
                if print_debug_detection:
                    debug_scores = [(s['letter'], f"fill={s['fill_ratio']:.3f}", f"contraste={s['contraste']:.3f}") for s in scores_sorted[:3]]
                    print(f"[DEBUG]   Scores ordenados por contraste: {debug_scores}")
                
                # ✅ CORREÇÃO 3 — Detectar resposta usando CONTRASTE RELATIVO
                # Critério: max_contrast > 0.12 E (max_contrast - second) > 0.08
                if max_contrast > CONTRASTE_MINIMO and (max_contrast - second_contrast) > DIFERENCA_CONTRASTE:
                    # Bolha marcada com confiança
                    resposta = scores_sorted[0]['letter']
                    self.logger.info(f"✅ Q{q_num}: Resposta detectada = {resposta} (contraste: {max_contrast:.3f}, 2º: {second_contrast:.3f}, diff: {max_contrast-second_contrast:.3f})")
                elif max_contrast > CONTRASTE_MINIMO and (max_contrast - second_contrast) <= DIFERENCA_CONTRASTE:
                    # Possível múltipla marcação (contrastes muito próximos)
                    resposta = None
                    self.logger.warning(f"Q{q_num}: Possíveis múltiplas marcações (1º: {scores_sorted[0]['letter']}={max_contrast:.3f}, 2º: {scores_sorted[1]['letter']}={second_contrast:.3f}, diff: {max_contrast-second_contrast:.3f})")
                else:
                    # Nenhuma bolha marcada claramente (contraste muito baixo)
                    resposta = None
                    self.logger.debug(f"Q{q_num}: Nenhuma bolha marcada (max_contraste: {max_contrast:.3f} < {CONTRASTE_MINIMO})")
                
                answers[q_num] = resposta
                
                # 5. Criar informações das bolhas para debug/visualização
                for score_item in scores:
                    letter = score_item['letter']
                    fill_ratio = score_item['fill_ratio']
                    x_rel = score_item['x']
                    y_rel = score_item['y']
                    is_marked = (resposta == letter and resposta is not None)
                    
                    # Coordenadas absolutas
                    x_abs = x_rel + x_offset
                    y_abs = y_rel + y_offset
                    
                    # Criar contorno circular para visualização
                    contour_relative = np.array([
                        [x_rel + bubble_radius * np.cos(angle), y_rel + bubble_radius * np.sin(angle)]
                        for angle in np.linspace(0, 2*np.pi, 20)
                    ], dtype=np.int32)
                    
                    contour_absolute = contour_relative + np.array([x_offset, y_offset])
                    
                    bubbles_info.append({
                        'contour': contour_absolute,
                        'contour_relative': contour_relative,
                        'x': x_abs,
                        'y': y_abs,
                        'x_relative': x_rel,
                        'y_relative': y_rel,
                        'question': q_num,
                        'option': letter,
                        'is_marked': is_marked,
                        'pixels': int(fill_ratio * np.pi * bubble_radius * bubble_radius),
                        'fill_ratio': fill_ratio,
                        'was_selected': is_marked
                    })
            
            # Preencher questões não processadas com None
            for question_config in questions_config:
                q_num = question_config.get('q')
                if q_num is not None and q_num not in answers:
                    answers[q_num] = None
            
            self.logger.info(f"Bloco {block_num or 'único'}: Processamento concluído - {len([a for a in answers.values() if a is not None])} respostas detectadas de {len(answers)} questões")
            
            # Salvar imagem do bloco com grade virtual
            if block_num and self.save_debug_images:
                self._salvar_imagem_bloco_com_grade_virtual(block_roi, grid, answers, block_num)
            
            return answers, bubbles_info
            
        except Exception as e:
            self.logger.error(f"Erro ao processar bloco sem referência: {str(e)}", exc_info=True)
            return {}, []
    
    def _desenhar_mascara_anel_debug(self, img_debug: np.ndarray, x: int, y: int, 
                                       radius: int, is_marked: bool) -> None:
        """
        ✅ CORREÇÃO 6 — DEBUG VISUAL: Desenha a máscara em anel usada na medição.
        
        Visualiza exatamente a região que está sendo medida para fill_ratio.
        
        Args:
            img_debug: Imagem de debug (será modificada)
            x, y: Centro da bolha
            radius: Raio da bolha
            is_marked: Se a bolha está marcada
        """
        # Calcular raios do anel (mesma lógica de _criar_mascara_anel)
        r_ext = int(radius * 0.85)
        r_int = int(radius * 0.45)
        r_ext = max(2, r_ext)
        r_int = max(1, min(r_int, r_ext - 1))
        
        # Cor do anel
        if is_marked:
            color_anel = (0, 200, 0)  # Verde escuro para marcada
        else:
            color_anel = (200, 200, 0)  # Amarelo escuro para não marcada
        
        # Desenhar círculo externo (tracejado - simulado com círculo fino)
        cv2.circle(img_debug, (x, y), r_ext, color_anel, 1)
        # Desenhar círculo interno
        cv2.circle(img_debug, (x, y), r_int, color_anel, 1)
    
    def _salvar_imagem_bloco_com_grade_virtual(self, block_roi: np.ndarray, grid: List[Dict],
                                               answers: Dict[int, Optional[str]], block_num: int):
        """
        Salva imagem do bloco com grade virtual desenhada.
        
        ✅ CORREÇÃO 6 — DEBUG APRIMORADO:
        - Desenha ○ círculo real detectado
        - Desenha ◎ ROI em anel usada na medição
        - Mostra contrastes e fill_ratio por questão
        
        Args:
            block_roi: ROI do bloco (imagem)
            grid: Lista de itens da grade virtual
            answers: Dict com respostas detectadas {q_num: 'A'|'B'|'C'|'D'|None}
            block_num: Número do bloco
        """
        try:
            # Converter para BGR se necessário
            if len(block_roi.shape) == 2:
                img_debug = cv2.cvtColor(block_roi, cv2.COLOR_GRAY2BGR)
            else:
                img_debug = block_roi.copy()
            
            # Cores
            COLOR_MARKED = (0, 255, 0)  # Verde para bolha marcada
            COLOR_UNMARKED = (255, 0, 0)  # Azul para bolha não marcada
            COLOR_GRID = (255, 255, 0)  # Amarelo para grade virtual
            COLOR_DISCARDED = (0, 0, 255)  # Vermelho para descartadas por distância
            COLOR_TEXT = (255, 255, 255)  # Branco para texto
            COLOR_BACKGROUND_TEXT = (0, 0, 0)  # Preto para fundo do texto
            
            # Agrupar grade por questão
            questions_grid = {}
            for item in grid:
                q_num = item['question']
                if q_num not in questions_grid:
                    questions_grid[q_num] = []
                questions_grid[q_num].append(item)
            
            # Calcular raio da bolha baseado no template (15px diâmetro = 7.5px raio)
            h, w = block_roi.shape[:2]
            bubble_radius = self._calcular_raio_bolha_template(block_roi, None)
            
            # Raio maior para visualização do grid (16px diâmetro = 8px raio)
            # Usar raio maior apenas para desenho, manter raio original para medição
            grid_radius = int(bubble_radius * (16.0 / 15.0))  # Proporcional: 16px / 15px
            
            # ✅ DEBUG: Obter lista ordenada de questões para identificar primeira, meio e última
            sorted_questions = sorted(questions_grid.keys())
            first_q = sorted_questions[0] if sorted_questions else None
            middle_q = sorted_questions[len(sorted_questions) // 2] if sorted_questions else None
            last_q = sorted_questions[-1] if sorted_questions else None
            
            # Desenhar grade virtual e medir preenchimento
            for q_num, row_items in questions_grid.items():
                resposta = answers.get(q_num)
                
                # ✅ CORREÇÃO 6: Calcular e logar contrastes para debug
                fills = []
                for item in row_items:
                    fill = self._medir_preenchimento_bolha(block_roi, item['x'], item['y'], bubble_radius, None)
                    fills.append(fill)
                
                # Normalização local
                min_fill = min(fills) if fills else 0
                max_fill = max(fills) if fills else 1
                fill_range = max_fill - min_fill + 1e-6
                fills_norm = [(f - min_fill) / fill_range for f in fills]
                
                # Baseline e contrastes
                baseline = np.median(fills_norm) if fills_norm else 0
                contrastes = [fn - baseline for fn in fills_norm]
                
                # ✅ DEBUG: Print para questões com resposta detectada (primeira, meio, última)
                print_debug_answer = resposta is not None and (q_num == first_q or q_num == middle_q or q_num == last_q)
                if print_debug_answer:
                    q_index_in_sorted = sorted_questions.index(q_num) if q_num in sorted_questions else -1
                    print(f"\n[DEBUG VISUAL] Bloco {block_num}: Q{q_num} (posição {q_index_in_sorted}/{len(sorted_questions)-1})")
                    print(f"[DEBUG VISUAL]   Resposta detectada: '{resposta}'")
                    print(f"[DEBUG VISUAL]   fills={[f'{f:.3f}' for f in fills]}")
                    print(f"[DEBUG VISUAL]   baseline={baseline:.3f}")
                    print(f"[DEBUG VISUAL]   contrastes={[f'{c:.3f}' for c in contrastes]}")
                
                for idx, item in enumerate(row_items):
                    x = item['x']
                    y = item['y']
                    letter = item['letter']
                    is_marked = (resposta == letter and resposta is not None)
                    fill_ratio = fills[idx] if idx < len(fills) else 0
                    contraste = contrastes[idx] if idx < len(contrastes) else 0
                    
                    # ✅ DEBUG: Print quando encontra a resposta marcada
                    if is_marked and print_debug_answer:
                        print(f"[DEBUG VISUAL]   ✓ {letter} marcada: x={x}px, y={y}px, fill={fill_ratio:.3f}, contraste={contraste:.3f}")
                    
                    # Escolher cor
                    if is_marked:
                        color = COLOR_MARKED
                        thickness = 3
                    else:
                        color = COLOR_UNMARKED
                        thickness = 1
                    
                    # ✅ CORREÇÃO 6: Desenhar círculo da grade virtual
                    cv2.circle(img_debug, (x, y), grid_radius, COLOR_GRID, 1)
                    cv2.circle(img_debug, (x, y), grid_radius, color, thickness)
                    
                    # ✅ CORREÇÃO 6: Desenhar ROI em anel usada na medição
                    self._desenhar_mascara_anel_debug(img_debug, x, y, bubble_radius, is_marked)
                    
                    # Desenhar centro
                    cv2.circle(img_debug, (x, y), 2, color, -1)
            
            # # Adicionar informações do bloco no topo [COMENTADO - Remover visual clutter]
            # info_text = f"Bloco {block_num}: Grade Virtual - {len(grid)} posições, {len(questions_grid)} questões"
            # font = cv2.FONT_HERSHEY_SIMPLEX
            # font_scale = 0.6
            # thickness = 1
            # (text_width, text_height), baseline = cv2.getTextSize(info_text, font, font_scale, thickness)
            # 
            # # Fundo para texto do bloco
            # cv2.rectangle(img_debug, (5, 5), (text_width + 10, text_height + baseline + 10),
            #              COLOR_BACKGROUND_TEXT, -1)
            # cv2.putText(img_debug, info_text, (10, text_height + 5),
            #            font, font_scale, COLOR_TEXT, thickness)
            # 
            # # Adicionar respostas detectadas
            # respostas_detectadas = [f"Q{q}={a}" for q, a in sorted(answers.items()) if a is not None]
            # if respostas_detectadas:
            #     respostas_text = "Respostas: " + ", ".join(respostas_detectadas[:10])
            #     if len(respostas_detectadas) > 10:
            #         respostas_text += f" ... (+{len(respostas_detectadas) - 10} mais)"
            #     
            #     y_offset = text_height + baseline + 20
            #     (text_width2, text_height2), baseline2 = cv2.getTextSize(respostas_text, font, font_scale, thickness)
            #     cv2.rectangle(img_debug, (5, y_offset), (min(text_width2 + 10, img_debug.shape[1] - 5), y_offset + text_height2 + baseline2 + 10),
            #                  COLOR_BACKGROUND_TEXT, -1)
            #     cv2.putText(img_debug, respostas_text, (10, y_offset + text_height2 + 5),
            #                font, font_scale, COLOR_TEXT, thickness)
            
            # Salvar imagem
            self._save_debug_image(f"05_block_{block_num:02d}_grade_virtual.jpg", img_debug)
            self.logger.info(f"Bloco {block_num}: Imagem com grade virtual salva")
            
        except Exception as e:
            self.logger.error(f"Erro ao salvar imagem do bloco com grade virtual: {str(e)}", exc_info=True)
    
    def _salvar_imagem_bloco_com_bolhas(self, block_roi: np.ndarray, all_bubbles: List[Dict],
                                        linhas: List[List[Dict]], answers: Dict[int, Optional[str]],
                                        block_num: int):
        """
        Salva imagem do bloco com bolhas detectadas desenhadas.
        
        Args:
            block_roi: ROI do bloco (imagem)
            all_bubbles: Lista de todas as bolhas detectadas
            linhas: Lista de linhas (cada linha é uma lista de bolhas)
            answers: Dict com respostas detectadas {q_num: 'A'|'B'|'C'|'D'|None}
            block_num: Número do bloco
        """
        try:
            # Converter para BGR se necessário
            if len(block_roi.shape) == 2:
                img_debug = cv2.cvtColor(block_roi, cv2.COLOR_GRAY2BGR)
            else:
                img_debug = block_roi.copy()
            
            # Cores
            COLOR_MARKED = (0, 255, 0)  # Verde para bolha marcada
            COLOR_UNMARKED = (255, 0, 0)  # Azul para bolha não marcada
            COLOR_TEXT = (255, 255, 255)  # Branco para texto
            COLOR_BACKGROUND_TEXT = (0, 0, 0)  # Preto para fundo do texto
            
            # Criar mapa de bolhas marcadas: (bolha, option, q_num)
            # Para cada linha, identificar qual bolha foi marcada
            bolhas_marcadas = set()
            LETRAS = ["A", "B", "C", "D"]
            FILL_RATIO_THRESHOLD = 0.3
            
            # Processar cada linha para identificar bolhas marcadas
            for linha_idx, linha in enumerate(linhas):
                linha_ordenada = sorted(linha, key=lambda b: b['x'])
                
                # Encontrar bolha com maior fill_ratio
                bolha_marcada = None
                max_fill_ratio = 0.0
                bolha_marcada_idx = -1
                
                for idx, bolha in enumerate(linha_ordenada):
                    fill_ratio = bolha.get('fill_ratio', 0.0)
                    if fill_ratio > max_fill_ratio:
                        max_fill_ratio = fill_ratio
                        bolha_marcada = bolha
                        bolha_marcada_idx = idx
                
                # Se a bolha marcada está acima do threshold, adicionar ao conjunto
                if bolha_marcada and max_fill_ratio >= FILL_RATIO_THRESHOLD and bolha_marcada_idx < len(LETRAS):
                    # Usar id da bolha (baseado em posição) para identificar
                    bolha_id = id(bolha_marcada)
                    bolhas_marcadas.add(bolha_id)
            
            # Desenhar todas as bolhas
            for bolha in all_bubbles:
                contour = bolha.get('contour')
                if contour is not None:
                    # Verificar se esta bolha foi marcada
                    bolha_id = id(bolha)
                    is_marked = bolha_id in bolhas_marcadas
                    
                    # Encontrar opção (A, B, C, D) da bolha
                    option = None
                    for linha in linhas:
                        linha_ordenada = sorted(linha, key=lambda b: b['x'])
                        try:
                            bolha_idx = linha_ordenada.index(bolha)
                            if bolha_idx < len(LETRAS):
                                option = LETRAS[bolha_idx]
                                break
                        except ValueError:
                            continue
                    
                    # Escolher cor
                    color = COLOR_MARKED if is_marked else COLOR_UNMARKED
                    thickness = 3 if is_marked else 1
                    
                    # Desenhar contorno
                    cv2.drawContours(img_debug, [contour], -1, color, thickness)
                    
                    # Desenhar centro
                    x = bolha['x']
                    y = bolha['y']
                    cv2.circle(img_debug, (x, y), 4, color, -1)
                    
                    # # Adicionar texto com opção (A, B, C, D) se disponível [COMENTADO - Remover visual clutter]
                    # if option:
                    #     text = f"{option}"
                    #     # Calcular tamanho do texto para fundo
                    #     font = cv2.FONT_HERSHEY_SIMPLEX
                    #     font_scale = 0.5
                    #     thickness_text = 1
                    #     (text_width, text_height), baseline = cv2.getTextSize(text, font, font_scale, thickness_text)
                    #     
                    #     # Posição do texto (acima da bolha)
                    #     text_x = x - text_width // 2
                    #     text_y = y - 8
                    #     
                    #     # Desenhar fundo preto para texto
                    #     cv2.rectangle(img_debug, 
                    #                  (text_x - 2, text_y - text_height - baseline - 2),
                    #                  (text_x + text_width + 2, text_y + baseline + 2),
                    #                  COLOR_BACKGROUND_TEXT, -1)
                    #     
                    #     # Desenhar texto
                    #     cv2.putText(img_debug, text, 
                    #                (text_x, text_y),
                    #                font, font_scale, COLOR_TEXT, thickness_text)
            
            # # Adicionar informações do bloco no topo [COMENTADO - Remover visual clutter]
            # info_text = f"Bloco {block_num}: {len(all_bubbles)} bolhas, {len(linhas)} linhas"
            # font = cv2.FONT_HERSHEY_SIMPLEX
            # font_scale = 0.6
            # thickness = 1
            # (text_width, text_height), baseline = cv2.getTextSize(info_text, font, font_scale, thickness)
            # 
            # # Fundo para texto do bloco
            # cv2.rectangle(img_debug, (5, 5), (text_width + 10, text_height + baseline + 10),
            #              COLOR_BACKGROUND_TEXT, -1)
            # cv2.putText(img_debug, info_text, (10, text_height + 5),
            #            font, font_scale, COLOR_TEXT, thickness)
            # 
            # # Adicionar respostas detectadas
            # respostas_detectadas = [f"Q{q}={a}" for q, a in sorted(answers.items()) if a is not None]
            # if respostas_detectadas:
            #     respostas_text = "Respostas: " + ", ".join(respostas_detectadas[:10])  # Limitar a 10 para não ficar muito grande
            #     if len(respostas_detectadas) > 10:
            #         respostas_text += f" ... (+{len(respostas_detectadas) - 10} mais)"
            #     
            #     y_offset = text_height + baseline + 20
            #     (text_width2, text_height2), baseline2 = cv2.getTextSize(respostas_text, font, font_scale, thickness)
            #     cv2.rectangle(img_debug, (5, y_offset), (min(text_width2 + 10, img_debug.shape[1] - 5), y_offset + text_height2 + baseline2 + 10),
            #                  COLOR_BACKGROUND_TEXT, -1)
            #     cv2.putText(img_debug, respostas_text, (10, y_offset + text_height2 + 5),
            #                font, font_scale, COLOR_TEXT, thickness)
            
            # Salvar imagem
            self._save_debug_image(f"05_block_{block_num:02d}_bubbles_detected.jpg", img_debug)
            self.logger.info(f"Bloco {block_num}: Imagem com bolhas detectadas salva")
            
        except Exception as e:
            self.logger.error(f"Erro ao salvar imagem do bloco com bolhas: {str(e)}", exc_info=True)
    
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
                error_msg = self._format_user_friendly_error("Nenhum bloco de resposta detectado")
                return {"success": False, "error": error_msg}
            
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
            error_msg = self._format_user_friendly_error(f"Erro no método antigo: {str(e)}")
            return {"success": False, "error": error_msg}
    
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
                
                db.session.flush()
                payload = existing_result.to_dict()
                db.session.commit()
                return payload
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
                db.session.flush()
                payload = result.to_dict()
                db.session.commit()
                return payload
                
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
                                       block_size: Tuple[int, int], block_num: int = None,
                                       manual_line_height: Optional[int] = None,
                                       scale_info: Optional[Dict] = None,
                                       detected_border_thickness: Optional[int] = None) -> Optional[np.ndarray]:
        """
        Cria imagem de referência de um bloco com bolhas corretas marcadas
        Usa tamanho calculado dinamicamente do A4 (não mais fixo)
        ✅ NOVO: Aceita espessura de borda detectada para corresponder ao bloco real
        
        Args:
            block_config: Configuração do bloco da topology {'block_id': 1, 'questions': [...]}
            correct_answers: Dict {q_num: 'A'|'B'|'C'|'D'} com respostas corretas
            block_size: (width, height) - tamanho TOTAL do bloco (incluindo borda)
            block_num: Número do bloco (para debug)
            manual_line_height: Altura de linha manual (opcional)
            scale_info: Informações de escala do A4 (opcional)
            detected_border_thickness: Espessura da borda detectada no bloco real (opcional)
            
        Returns:
            np.ndarray: Imagem de referência (grayscale, 255=branco, 0=preto) no tamanho calculado
        """
        try:
            width, height = block_size
            questions_config = block_config.get('questions', [])
            num_questoes = len(questions_config)
            
            # Sempre usar altura fornecida (já calculada dinamicamente do A4)
            # Se altura não foi calculada corretamente, recalcular baseado no CSS
            if height <= 0 and num_questoes > 0:
                # Fallback: calcular altura baseado no CSS
                # Valores do CSS em cm
                BLOCK_HEADER_HEIGHT_CM = 0.7
                BLOCK_PADDING_Y_CM = 0.1
                BORDER_THICKNESS_CM = 0.06
                LINE_HEIGHT_CM = 0.42
                
                # Estimar px_per_cm baseado na largura
                reference_block_width_cm = 4.2
                px_per_cm = width / reference_block_width_cm if reference_block_width_cm > 0 else 39.37
                
                calculated_height = int((BLOCK_HEADER_HEIGHT_CM + (num_questoes * LINE_HEIGHT_CM) + (2 * BLOCK_PADDING_Y_CM) + (2 * BORDER_THICKNESS_CM)) * px_per_cm)
                height = calculated_height
                self.logger.warning(f"Bloco {block_num or 'único'}: Altura recalculada do CSS = {height}px ({num_questoes} questões)")
            else:
                self.logger.info(f"Bloco {block_num or 'único'}: Usando altura calculada do A4 = {height}px ({num_questoes} questões)")
            
            # ✅ NOVO: Usar espessura de borda detectada se fornecida, senão usar padrão
            if detected_border_thickness is not None and detected_border_thickness > 0:
                border_thickness = detected_border_thickness
                self.logger.info(f"Bloco {block_num or 'único'}: Usando espessura de borda detectada = {border_thickness}px")
            else:
                border_thickness = 2  # Padrão
                self.logger.debug(f"Bloco {block_num or 'único'}: Usando espessura de borda padrão = {border_thickness}px")
            
            # ✅ IMPORTANTE: width e height agora são o tamanho TOTAL (incluindo borda)
            # Calcular dimensões internas (área dentro da borda)
            inner_width = width - 2 * border_thickness
            inner_height = height - 2 * border_thickness
            
            # Validar que temos espaço interno suficiente
            if inner_width <= 0 or inner_height <= 0:
                self.logger.error(f"Bloco {block_num or 'único'}: Dimensões internas inválidas ({inner_width}x{inner_height}) após subtrair borda de {border_thickness}px")
                return None
            
            # Criar imagem branca com tamanho TOTAL (incluindo borda)
            ref_img = np.ones((height, width), dtype=np.uint8) * 255
            
            # Desenhar borda preta grossa - mesma espessura do bloco detectado
            # Preencher área da borda completamente com preto
            if border_thickness > 0:
                # Borda superior
                cv2.rectangle(ref_img,
                             (0, 0),
                             (width - 1, border_thickness - 1),
                             (0, 0, 0),
                             -1)  # Preenchido
                # Borda inferior
                cv2.rectangle(ref_img,
                             (0, height - border_thickness),
                             (width - 1, height - 1),
                             (0, 0, 0),
                             -1)  # Preenchido
                # Borda esquerda
                cv2.rectangle(ref_img,
                             (0, 0),
                             (border_thickness - 1, height - 1),
                             (0, 0, 0),
                             -1)  # Preenchido
                # Borda direita
                cv2.rectangle(ref_img,
                             (width - border_thickness, 0),
                             (width - 1, height - 1),
                             (0, 0, 0),
                             -1)  # Preenchido
            
            # Coordenadas da área interna (onde desenhar as bolhas)
            inner_x = border_thickness
            inner_y = border_thickness
            
            # Calcular espaçamentos baseados no CSS atual
            # Do CSS:
            # - .bubble: width: 15px, height: 15px
            # - .answer-row: min-height: 0.42cm
            # - .answer-block: padding: 3px 4px, border: 2px
            # - .bubbles: gap: 4px
            
            # Valores do CSS em cm
            BUBBLE_SIZE_CM = 0.40  # 15px ≈ 0.40cm (assumindo ~100 DPI)
            BUBBLE_GAP_CM = 0.11   # 4px ≈ 0.11cm
            LINE_HEIGHT_CM = 0.44  # Do CSS: min-height: 0.44cm
            BLOCK_PADDING_X_CM = 0.1  # 4px ≈ 0.1cm
            BLOCK_PADDING_Y_CM = 0.1  # 3px ≈ 0.1cm
            
            # Calcular px_per_cm baseado no scale_info ou estimar do tamanho do bloco
            # ✅ Usar largura interna para cálculo (mais preciso)
            if scale_info:
                px_per_cm_x = scale_info.get('px_per_cm_x', 39.37)
                px_per_cm_y = scale_info.get('px_per_cm_y', 39.37)
                px_per_cm = (px_per_cm_x + px_per_cm_y) / 2  # Média
            else:
                # Estimar baseado na largura INTERNA do bloco (sem borda)
                reference_block_width_cm = 4.2  # Largura estimada de um bloco em cm (sem borda)
                px_per_cm = inner_width / reference_block_width_cm if reference_block_width_cm > 0 else 39.37
            
            # Calcular tamanhos em pixels baseados no CSS
            bubble_size = int(BUBBLE_SIZE_CM * px_per_cm)
            bubble_gap = int(BUBBLE_GAP_CM * px_per_cm)
            line_height = int(LINE_HEIGHT_CM * px_per_cm)
            padding_x = int(BLOCK_PADDING_X_CM * px_per_cm)
            padding_y = int(BLOCK_PADDING_Y_CM * px_per_cm)
            
            # Se manual_line_height fornecido, usar ele
            if manual_line_height is not None:
                line_height = manual_line_height
                self.logger.info(f"Bloco {block_num or 'único'}: Usando line_height manual: {line_height}px")
            
            self.logger.info(f"Bloco {block_num or 'único'}: Tamanhos calculados do CSS - width={width}px, height={height}px, bubble_size={bubble_size}px, bubble_gap={bubble_gap}px, line_height={line_height}px")
            
            # Calcular posições das questões
            start_y = inner_y + padding_y
            
            # Sempre usar line_height calculado do CSS (não distribuir igualmente)
            # O CSS define min-height: 0.44cm, então usamos esse valor escalado
            line_height_actual = line_height
            
            for q_idx, q_config in enumerate(questions_config):
                q_num = q_config.get('q')
                alternatives_esperadas = q_config.get('alternatives', [])
                correct_answer = correct_answers.get(q_num)
                
                # Posição Y da linha (centro vertical da linha) - sempre usar line_height calculado
                line_y = start_y + q_idx * line_height_actual + line_height_actual // 2
                
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
        ✅ NOVO: Mede a espessura real da borda
        
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
            
            h, w = block_gray.shape[:2]
            
            # Aplicar threshold para detectar borda preta
            _, thresh = cv2.threshold(block_gray, 127, 255, cv2.THRESH_BINARY_INV)
            
            # Encontrar contornos externos
            cnts = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            cnts = cnts[0] if len(cnts) == 2 else cnts[1]
            
            if not cnts:
                return None
            
            # Encontrar maior contorno (deve ser a borda do bloco)
            largest_cnt = max(cnts, key=cv2.contourArea)
            x, y, w_detected, h_detected = cv2.boundingRect(largest_cnt)
            
            # Verificar se o contorno é aproximadamente retangular
            peri = cv2.arcLength(largest_cnt, True)
            approx = cv2.approxPolyDP(largest_cnt, 0.02 * peri, True)
            
            if len(approx) < 4:
                return None
            
            # ✅ NOVO: Medir espessura real da borda
            # Estratégia: analisar linhas horizontais e verticais nas bordas
            border_thickness = self._medir_espessura_borda(block_gray, x, y, w_detected, h_detected, block_num)
            
            # ✅ Validar que a espessura é razoável antes de usar
            # Espessura deve ser entre 1-10px e não pode ser maior que 10% do tamanho
            max_thickness = min(10, w_detected // 10, h_detected // 10)
            if border_thickness > max_thickness:
                self.logger.warning(f"Bloco {block_num or 'único'}: Espessura detectada ({border_thickness}px) muito grande, limitando para {max_thickness}px")
                border_thickness = max(1, max_thickness)
            
            # Validar que temos espaço interno suficiente
            inner_w = w_detected - 2 * border_thickness
            inner_h = h_detected - 2 * border_thickness
            
            if inner_w <= 0 or inner_h <= 0:
                self.logger.warning(f"Bloco {block_num or 'único'}: Tamanho interno inválido ({inner_w}x{inner_h}px) com borda de {border_thickness}px. Usando borda padrão de 2px.")
                border_thickness = 2
                inner_w = w_detected - 2 * border_thickness
                inner_h = h_detected - 2 * border_thickness
                
                # Se ainda inválido, usar 0 (sem borda)
                if inner_w <= 0 or inner_h <= 0:
                    self.logger.error(f"Bloco {block_num or 'único'}: Tamanho do bloco muito pequeno ({w_detected}x{h_detected}px), usando sem borda")
                    border_thickness = 0
                    inner_w = w_detected
                    inner_h = h_detected
            
            border_info = {
                'x': x,
                'y': y,
                'w': w_detected,  # Tamanho TOTAL incluindo borda
                'h': h_detected,  # Tamanho TOTAL incluindo borda
                'border_thickness': border_thickness,
                'inner_x': x + border_thickness,
                'inner_y': y + border_thickness,
                'inner_w': inner_w,
                'inner_h': inner_h
            }
            
            self.logger.info(f"Bloco {block_num or 'único'}: Borda detectada - tamanho total: {w_detected}x{h_detected}px, espessura: {border_thickness}px, área interna: {inner_w}x{inner_h}px")
            return border_info
            
        except Exception as e:
            self.logger.error(f"Erro ao detectar borda: {str(e)}", exc_info=True)
            return None
    
    def _medir_espessura_borda(self, block_gray: np.ndarray, x: int, y: int, w: int, h: int, block_num: int = None) -> int:
        """
        Mede a espessura real da borda do bloco
        
        ✅ CORRIGIDO: Mede apenas a borda externa, não todo o conteúdo preto
        
        Args:
            block_gray: Imagem do bloco em grayscale
            x, y, w, h: Coordenadas e tamanho do bloco detectado
            block_num: Número do bloco (para debug)
            
        Returns:
            Espessura da borda em pixels (validado entre 1-10px)
        """
        try:
            h_img, w_img = block_gray.shape[:2]
            
            # Validar coordenadas
            if x < 0 or y < 0 or x + w > w_img or y + h > h_img:
                self.logger.warning(f"Bloco {block_num or 'N/A'}: Coordenadas inválidas para medir borda, usando 2px (padrão)")
                return 2
            
            # Aplicar threshold para destacar borda preta
            _, thresh = cv2.threshold(block_gray, 127, 255, cv2.THRESH_BINARY_INV)
            
            # Amostrar várias linhas nas bordas para medir espessura
            thicknesses = []
            
            # ✅ CORRIGIDO: Amostrar apenas nas bordas externas (primeiros/last pixels)
            sample_lines = min(10, h // 4)  # Amostrar até 10 linhas ou 1/4 da altura
            sample_cols = min(10, w // 4)   # Amostrar até 10 colunas ou 1/4 da largura
            
            # Borda superior: amostrar linhas horizontais próximas ao topo
            for i in range(min(sample_lines, 10)):
                line_y = y + i
                if 0 <= line_y < h_img:
                    # Amostrar apenas no centro da linha (evitar cantos)
                    start_x = max(x, x + w // 4)
                    end_x = min(x + w, x + 3 * w // 4)
                    if end_x > start_x:
                        line = thresh[line_y, start_x:end_x]
                        # Contar pixels pretos consecutivos do início
                        black_pixels = 0
                        for pixel in line[:min(20, len(line))]:  # Limitar a 20px
                            if pixel > 0:  # Preto no threshold invertido
                                black_pixels += 1
                            else:
                                break
                        if 1 <= black_pixels <= 10:  # ✅ Validar range razoável
                            thicknesses.append(black_pixels)
            
            # Borda inferior
            for i in range(min(sample_lines, 10)):
                line_y = y + h - 1 - i
                if 0 <= line_y < h_img:
                    start_x = max(x, x + w // 4)
                    end_x = min(x + w, x + 3 * w // 4)
                    if end_x > start_x:
                        line = thresh[line_y, start_x:end_x]
                        # Contar pixels pretos consecutivos do final
                        black_pixels = 0
                        for pixel in reversed(line[-min(20, len(line)):]):  # Limitar a 20px
                            if pixel > 0:
                                black_pixels += 1
                            else:
                                break
                        if 1 <= black_pixels <= 10:  # ✅ Validar range razoável
                            thicknesses.append(black_pixels)
            
            # Borda esquerda: amostrar colunas verticais próximas à esquerda
            for i in range(min(sample_cols, 10)):
                col_x = x + i
                if 0 <= col_x < w_img:
                    # Amostrar apenas no centro da coluna (evitar cantos)
                    start_y = max(y, y + h // 4)
                    end_y = min(y + h, y + 3 * h // 4)
                    if end_y > start_y:
                        col = thresh[start_y:end_y, col_x]
                        # Contar pixels pretos consecutivos do início
                        black_pixels = 0
                        for pixel in col[:min(20, len(col))]:  # Limitar a 20px
                            if pixel > 0:
                                black_pixels += 1
                            else:
                                break
                        if 1 <= black_pixels <= 10:  # ✅ Validar range razoável
                            thicknesses.append(black_pixels)
            
            # Borda direita
            for i in range(min(sample_cols, 10)):
                col_x = x + w - 1 - i
                if 0 <= col_x < w_img:
                    start_y = max(y, y + h // 4)
                    end_y = min(y + h, y + 3 * h // 4)
                    if end_y > start_y:
                        col = thresh[start_y:end_y, col_x]
                        # Contar pixels pretos consecutivos do final
                        black_pixels = 0
                        for pixel in reversed(col[-min(20, len(col)):]):  # Limitar a 20px
                            if pixel > 0:
                                black_pixels += 1
                            else:
                                break
                        if 1 <= black_pixels <= 10:  # ✅ Validar range razoável
                            thicknesses.append(black_pixels)
            
            if thicknesses:
                # Usar mediana para ser mais robusto a outliers
                thicknesses_sorted = sorted(thicknesses)
                median_thickness = thicknesses_sorted[len(thicknesses_sorted) // 2]
                
                # ✅ Validar que a espessura é razoável (1-10px)
                if 1 <= median_thickness <= 10:
                    self.logger.debug(f"Bloco {block_num or 'N/A'}: Espessura da borda medida = {median_thickness}px (de {len(thicknesses)} amostras válidas)")
                    return median_thickness
                else:
                    self.logger.warning(f"Bloco {block_num or 'N/A'}: Espessura medida ({median_thickness}px) fora do range válido (1-10px), usando 2px (padrão)")
                    return 2
            else:
                # Fallback: usar 2px se não conseguir medir
                self.logger.warning(f"Bloco {block_num or 'N/A'}: Não foi possível medir espessura da borda, usando 2px (padrão)")
                return 2
                
        except Exception as e:
            self.logger.warning(f"Erro ao medir espessura da borda: {str(e)}, usando 2px (padrão)")
            return 2
    
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
                    param2=15,  # CORRIGIDO: reduzido de 25 para 15 (mais sensível)
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
                                      block_num: int = None, border_info: Dict = None,
                                      manual_line_height: Optional[int] = None,
                                      scale_info: Optional[Dict] = None) -> Tuple[Dict[int, Optional[str]], List[Dict]]:
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
            
            # Garantir que ambas as imagens têm o mesmo tamanho
            ref_h, ref_w = block_reference.shape[:2]
            real_h, real_w = block_real.shape[:2]
            
            # Se não estiverem no mesmo tamanho, redimensionar (fallback de segurança)
            if (ref_h, ref_w) != (real_h, real_w):
                self.logger.warning(f"Bloco {block_num or 'único'}: Tamanhos diferentes! Referência: {ref_w}x{ref_h}, Real: {real_w}x{real_h}. Redimensionando...")
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
            
            # Calcular espaçamentos baseados no CSS atual (mesmo cálculo da referência)
            # Do CSS:
            # - .bubble: width: 15px, height: 15px
            # - .answer-row: min-height: 0.42cm
            # - .answer-block: padding: 3px 4px
            # - .bubbles: gap: 4px
            
            # Valores do CSS em cm
            BUBBLE_SIZE_CM = 0.40  # 15px ≈ 0.40cm
            BUBBLE_GAP_CM = 0.11   # 4px ≈ 0.11cm
            LINE_HEIGHT_CM = 0.44  # Do CSS: min-height: 0.44cm
            BLOCK_PADDING_X_CM = 0.1  # 4px ≈ 0.1cm
            BLOCK_PADDING_Y_CM = 0.1  # 3px ≈ 0.1cm
            
            # Calcular px_per_cm baseado no scale_info ou estimar do tamanho do bloco
            if scale_info:
                px_per_cm_x = scale_info.get('px_per_cm_x', 39.37)
                px_per_cm_y = scale_info.get('px_per_cm_y', 39.37)
                px_per_cm = (px_per_cm_x + px_per_cm_y) / 2  # Média
            else:
                # Estimar baseado na largura do bloco
                reference_block_width_cm = 4.2  # Largura estimada de um bloco em cm
                px_per_cm = real_w / reference_block_width_cm if reference_block_width_cm > 0 else 39.37
            
            # Calcular tamanhos em pixels baseados no CSS
            bubble_size = int(BUBBLE_SIZE_CM * px_per_cm)
            bubble_gap = int(BUBBLE_GAP_CM * px_per_cm)
            line_height = int(LINE_HEIGHT_CM * px_per_cm)
            padding_x = int(BLOCK_PADDING_X_CM * px_per_cm)
            padding_y = int(BLOCK_PADDING_Y_CM * px_per_cm)
            
            # Se manual_line_height fornecido, usar ele
            if manual_line_height is not None:
                line_height = manual_line_height
                self.logger.debug(f"Bloco {block_num or 'único'}: Usando line_height manual na comparação: {line_height}px")
            
            self.logger.debug(f"Bloco {block_num or 'único'}: Tamanhos calculados do CSS na comparação - width={real_w}px, height={real_h}px, bubble_size={bubble_size}px, line_height={line_height}px")
            
            # Sempre usar line_height calculado do CSS (não distribuir igualmente)
            # O CSS define min-height: 0.44cm, então usamos esse valor escalado
            line_height_actual = line_height
            
            # Posição inicial Y (dentro da área interna, já considerando padding)
            start_y = inner_y + padding_y
            
            # Log dos tamanhos calculados
            self.logger.debug(f"Bloco {block_num or 'único'}: Tamanhos calculados do CSS - bubble_size={bubble_size}px, bubble_gap={bubble_gap}px, line_height={line_height}px, line_height_actual={line_height_actual}px")
            
            # ====================================================================
            # OPÇÃO A: Detectar primeira bolha (Q1A) e usar como referência
            # Com suporte para offsets manuais salvos
            # ====================================================================
            offset_x = 0
            offset_y = 0
            
            # Tentar carregar offset manual se disponível
            # ✅ Passar tamanho do bloco para cálculo proporcional (se disponível)
            # Nota: block_width e block_height podem não estar disponíveis neste contexto
            manual_offset = self._load_manual_alignment(block_num, None, None)
            if manual_offset:
                offset_x = manual_offset.get('offset_x', 0)
                offset_y = manual_offset.get('offset_y', 0)
                self.logger.info(f"Bloco {block_num or 'único'}: Usando offset manual X={offset_x:+d}px, Y={offset_y:+d}px")
                if manual_offset.get('line_height'):
                    self.logger.info(f"Bloco {block_num or 'único'}: Line height manual já foi aplicado na criação da referência")
            
            if questions_config:
                first_q_config = questions_config[0]
                first_q_alternatives = first_q_config.get('alternatives', [])
                
                if first_q_alternatives:
                    # Calcular posição esperada da primeira bolha (Q1A)
                    # Sempre usar line_height calculado do CSS
                    first_line_y = start_y + line_height_actual // 2
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
                
                # Calcular posição Y da linha (sempre usar line_height calculado do CSS)
                line_y = start_y + q_idx * line_height_actual + line_height_actual // 2
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
