# 📐 PLANO DE REFATORAÇÃO - PIPELINE OMR ROBUSTO E DETERMINÍSTICO

**Data:** 21 de Janeiro de 2026  
**Arquivo:** `app/services/cartao_resposta/correction_n.py`  
**Status:** ANÁLISE E PLANEJAMENTO (SEM ALTERAÇÕES AINDA)

---

## 🎯 OBJETIVO

Refatorar o sistema atual de correção OMR para seguir um **pipeline ROBUSTO, DETERMINÍSTICO e SEM MACHINE LEARNING**, baseado 100% em:
- Template HTML controlado
- JSON de topologia como fonte da verdade
- Visão computacional determinística (OpenCV)

---

## 📊 ANÁLISE DO CÓDIGO ATUAL (6031 linhas)

### ✅ O QUE JÁ EXISTE E ESTÁ CORRETO

#### 1. Template HTML (`answer_sheet.html`)
- ✅ 4 quadrados pretos A4 nos cantos (20x20px)
- ✅ 4 triângulos pretos delimitando área do grid (0.6cm)
- ✅ Blocos com bordas pretas de 2px
- ✅ Estrutura variável baseada em JSON
- ✅ Bolhas de 15px com espaçamento de 4px

#### 2. Funções Existentes Alinhadas ao Pipeline

| ETAPA DO PIPELINE | FUNÇÃO EXISTENTE | STATUS |
|-------------------|------------------|--------|
| 1️⃣ Pré-processamento | `_decode_image()` | ✅ PODE MANTER |
| 2️⃣ Detecção Âncoras A4 | `_detectar_quadrados_a4()` | ⚠️ REVISAR |
| 3️⃣ Normalização A4 | `_normalizar_para_a4()` | ⚠️ REVISAR |
| 4️⃣ Detecção Triângulos | `_detectar_triangulos_na_area_blocos()` | ⚠️ REVISAR |
| 5️⃣ Detecção Blocos | `_detectar_blocos_resposta()` | ⚠️ REVISAR |
| 6️⃣ Mapeamento JSON→Grid | ❌ NÃO EXISTE | 🔴 CRIAR |
| 7️⃣ Cálculo Centros Bolhas | `_gerar_grade_virtual()` | ⚠️ REFATORAR |
| 8️⃣ Detecção Marcação | `_medir_preenchimento_bolha()` | ⚠️ SIMPLIFICAR |
| 9️⃣ Resultado Final | `_calcular_correcao()` | ✅ PODE MANTER |

---

## ⚠️ PROBLEMAS IDENTIFICADOS NO CÓDIGO ATUAL

### 🔴 PROBLEMA 1: Mistura de Abordagens
**Localização:** Múltiplas funções  
**Descrição:** O código atual mistura:
- Detecção por Hough Circles (`_detectar_bolhas_hough()`)
- Grid virtual (`_gerar_grade_virtual()`)
- Template matching (`_comparar_roi_com_template()`)
- Coordenadas fixas (`_gerar_grade_virtual_com_coordenadas_fixas()`)

**Solução:** Usar APENAS grid matemático baseado no JSON (etapa 6-7 do pipeline)

---

### 🔴 PROBLEMA 2: Números Fixos Hardcoded
**Localização:** Linhas 38-42  
```python
LINE_Y_THRESHOLD = 8
STANDARD_BLOCK_WIDTH = 431
STANDARD_BLOCK_HEIGHT = 362
```

**Solução:** Remover números fixos. Calcular tudo dinamicamente baseado no JSON.

---

### 🔴 PROBLEMA 3: Tentativa de Detectar Bolhas por Contornos
**Localização:** `_detectar_todas_bolhas()`, `_detectar_bolhas_hough()`  
**Descrição:** Tenta detectar bolhas pela imagem, mas o JSON já define tudo.

**Solução:** Eliminar detecção de bolhas. Calcular posições matematicamente a partir do JSON.

---

### 🔴 PROBLEMA 4: Sistema de Templates Desnecessário
**Localização:** Funções 278-700  
- `gerar_templates_blocos()`
- `_carregar_template_bloco()`
- `_comparar_roi_com_template()`

**Solução:** Não precisamos de templates porque temos o JSON de topologia + validação dos triângulos.

---

### 🔴 PROBLEMA 5: Falta de Validação Rigorosa
**Descrição:** Não rejeita imagens inválidas com firmeza.

**Solução:** Pipeline deve REJEITAR se:
- Não encontrar exatamente 4 quadrados A4
- Não encontrar exatamente 4 triângulos
- Número de blocos != JSON.num_blocks

---

## 🏗️ ARQUITETURA DO NOVO PIPELINE

### ESTRUTURA DE CLASSES

```python
class AnswerSheetCorrectionN:
    """Pipeline OMR Robusto e Determinístico"""
    
    # ========== CONFIGURAÇÃO ==========
    def __init__(self, debug: bool = False)
    
    # ========== PIPELINE PRINCIPAL ==========
    def corrigir_cartao_resposta(self, image_data: bytes, topology_json: Dict) -> Dict
        """
        Pipeline principal - chama todas as etapas em sequência
        
        Args:
            image_data: Bytes da imagem escaneada
            topology_json: JSON com estrutura de blocos/questões
            
        Returns:
            Dict com respostas detectadas ou erro
        """
    
    # ========== ETAPA 1: PRÉ-PROCESSAMENTO ==========
    def _preprocess_image(self, img: np.ndarray) -> Dict[str, np.ndarray]
        """
        Retorna:
            - gray: Imagem em grayscale
            - blur: Gaussian blur aplicado
            - thresh: Threshold adaptativo
            - edges: Detecção de bordas (Canny)
        """
    
    # ========== ETAPA 2: DETECÇÃO ÂNCORAS A4 ==========
    def _detect_a4_anchors(self, img: np.ndarray, edges: np.ndarray) -> Optional[List[Dict]]
        """
        Detecta exatamente 4 quadrados pretos nos cantos
        
        Critérios:
            - 4 vértices (approxPolyDP)
            - Área entre 300-600 px²
            - Aspect ratio ~1:1
            - Posição nos cantos da imagem
            
        Retorna:
            Lista ordenada [TL, TR, BR, BL] ou None se inválido
        """
    
    # ========== ETAPA 3: NORMALIZAÇÃO A4 ==========
    def _normalize_to_a4(self, img: np.ndarray, anchors: List[Dict]) -> np.ndarray
        """
        Aplica transformação de perspectiva para A4 lógico fixo
        
        Args:
            anchors: 4 pontos [TL, TR, BR, BL]
            
        Retorna:
            Imagem normalizada (2480x3508 pixels - A4 a 300 DPI)
        """
    
    # ========== ETAPA 4: DETECÇÃO TRIÂNGULOS ==========
    def _detect_grid_triangles(self, img_a4: np.ndarray, edges: np.ndarray) -> Optional[List[Dict]]
        """
        Detecta exatamente 4 triângulos pretos delimitando o grid
        
        Critérios:
            - 3 vértices (approxPolyDP)
            - Área grande (>1000 px²)
            - Totalmente pretos
            
        Retorna:
            Lista ordenada [TL, TR, BR, BL] ou None se inválido
        """
    
    # ========== ETAPA 5: DETECÇÃO BLOCOS ==========
    def _detect_answer_blocks(self, img_a4: np.ndarray, grid_area: Dict, 
                              num_blocks_expected: int) -> Optional[List[Dict]]
        """
        Detecta blocos com bordas pretas de 2px
        
        Critérios:
            - Contornos retangulares (4 vértices)
            - Área significativa
            - Dentro da área do grid
            - Borda preta contínua
            
        Validação:
            - len(blocks) DEVE ser == num_blocks_expected
            - Se diferente → REJEITAR imagem
            
        Retorna:
            Lista de blocos ordenados (cima→baixo) ou None se inválido
        """
    
    # ========== ETAPA 6: MAPEAMENTO JSON → GRID (CRÍTICO) ==========
    def _map_topology_to_grid(self, block_roi: np.ndarray, block_config: Dict) -> Dict
        """
        🔴 FUNÇÃO MAIS IMPORTANTE DO SISTEMA
        
        Esta função NÃO olha para a imagem para decidir linhas/colunas.
        ELA APENAS LIDA COM O JSON.
        
        Args:
            block_roi: ROI do bloco (apenas para dimensões)
            block_config: Configuração do bloco do JSON
                {
                    "block_id": 1,
                    "questions": [
                        {"q": 1, "alternatives": ["A","B","C"]},
                        {"q": 2, "alternatives": ["A","B","C","D"]},
                        ...
                    ]
                }
        
        Retorna:
            {
                "num_rows": len(questions),
                "row_height": block_height / num_rows,
                "questions": [
                    {
                        "q_num": 1,
                        "y": row_height * 0 + row_height/2,
                        "num_cols": 3,
                        "col_width": block_width / 3,
                        "alternatives": [
                            {"letter": "A", "x": col_width * 0 + col_width/2},
                            {"letter": "B", "x": col_width * 1 + col_width/2},
                            {"letter": "C", "x": col_width * 2 + col_width/2}
                        ]
                    },
                    ...
                ]
            }
        """
    
    # ========== ETAPA 7: CÁLCULO CENTROS BOLHAS ==========
    def _calculate_bubble_centers(self, grid_map: Dict, block_roi: np.ndarray) -> List[Dict]
        """
        Calcula centros e raios de TODAS as bolhas do bloco
        
        Para cada questão no grid_map:
            Para cada alternativa:
                cx = block_x + alternative["x"]
                cy = block_y + question["y"]
                r = row_height * 0.35
        
        Retorna:
            Lista de dicionários:
            [
                {
                    "q_num": 1,
                    "alternative": "A",
                    "cx": 150,
                    "cy": 50,
                    "r": 12
                },
                ...
            ]
        """
    
    # ========== ETAPA 8: DETECÇÃO DE MARCAÇÃO ==========
    def _detect_marked_bubbles(self, block_roi: np.ndarray, bubbles: List[Dict]) -> Dict[int, str]
        """
        Para cada bolha:
            1. Criar máscara circular centrada em (cx, cy) com raio r
            2. Contar pixels escuros dentro da máscara
            3. Calcular fill_ratio = black_pixels / total_pixels
        
        Para cada questão:
            - Selecionar alternativa com maior fill_ratio
            - Se fill_ratio > 0.45 → marcada
            - Se múltiplas com fill_ratio > 0.45 → INVÁLIDA
            - Se nenhuma com fill_ratio > 0.45 → em branco
        
        Retorna:
            {
                1: "C",      # Questão 1 → alternativa C
                2: None,     # Questão 2 → em branco
                3: "INVALID" # Questão 3 → múltiplas marcadas
            }
        """
    
    # ========== ETAPA 9: RESULTADO FINAL ==========
    def _build_result(self, answers: Dict[int, str], gabarito: Dict[int, str]) -> Dict
        """
        Compara respostas detectadas com gabarito
        
        Retorna:
            {
                "success": True,
                "total_questions": 48,
                "correct_answers": 35,
                "wrong_answers": 10,
                "blank_answers": 2,
                "invalid_answers": 1,
                "score": 72.9,
                "answers": [
                    {
                        "question": 1,
                        "marked": "C",
                        "correct": "C",
                        "is_correct": True,
                        "fill_ratio": 0.78
                    },
                    ...
                ]
            }
        """
```

---

## 📝 PLANO DE IMPLEMENTAÇÃO (PASSO A PASSO)

### FASE 1: LIMPEZA (Remover Código Legado)

#### 1.1. Remover Funções Desnecessárias
- [ ] Remover `gerar_templates_blocos()`
- [ ] Remover `_carregar_template_bloco()`
- [ ] Remover `_comparar_roi_com_template()`
- [ ] Remover `_medir_preenchimento_com_template()`
- [ ] Remover `_detectar_bolhas_hough()`
- [ ] Remover `_detectar_todas_bolhas()`
- [ ] Remover `_agrupar_bolhas_por_linha_fisica()`
- [ ] Remover `_validar_distancia_grid()`
- [ ] Remover `_processar_bloco_sem_referencia()`

#### 1.2. Remover Constantes Fixas
- [ ] Remover `LINE_Y_THRESHOLD`
- [ ] Remover `STANDARD_BLOCK_WIDTH`
- [ ] Remover `STANDARD_BLOCK_HEIGHT`
- [ ] Remover `BUBBLE_MIN_SIZE` / `BUBBLE_MAX_SIZE`

#### 1.3. Simplificar Funções Complexas
- [ ] `_gerar_grade_virtual()` → substituir por `_map_topology_to_grid()`
- [ ] `_medir_preenchimento_bolha()` → simplificar lógica

---

### FASE 2: IMPLEMENTAR PIPELINE ROBUSTO

#### 2.1. Etapa 1: Pré-processamento
```python
def _preprocess_image(self, img: np.ndarray) -> Dict[str, np.ndarray]:
    """
    Converte para grayscale, aplica blur, threshold e Canny
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    
    # Threshold adaptativo (melhor para iluminação irregular)
    thresh = cv2.adaptiveThreshold(
        blur, 255, 
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
        cv2.THRESH_BINARY_INV, 
        11, 2
    )
    
    # Detecção de bordas para encontrar contornos
    edges = cv2.Canny(blur, 50, 150)
    
    return {
        "gray": gray,
        "blur": blur,
        "thresh": thresh,
        "edges": edges
    }
```

#### 2.2. Etapa 2: Detecção Âncoras A4
```python
def _detect_a4_anchors(self, img: np.ndarray, edges: np.ndarray) -> Optional[List[Dict]]:
    """
    Detecta exatamente 4 quadrados pretos nos cantos
    """
    # Encontrar contornos
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    
    squares = []
    for cnt in contours:
        # Aproximar para polígono
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
        
        # Deve ter 4 vértices
        if len(approx) != 4:
            continue
        
        # Calcular área
        area = cv2.contourArea(cnt)
        if not (300 <= area <= 600):  # 20x20px = 400px²
            continue
        
        # Calcular aspect ratio
        x, y, w, h = cv2.boundingRect(approx)
        aspect_ratio = w / float(h)
        if not (0.9 <= aspect_ratio <= 1.1):
            continue
        
        # Calcular centróide
        M = cv2.moments(cnt)
        if M["m00"] == 0:
            continue
        cx = int(M["m10"] / M["m00"])
        cy = int(M["m01"] / M["m00"])
        
        squares.append({
            "contour": approx,
            "cx": cx,
            "cy": cy,
            "area": area
        })
    
    # Deve encontrar exatamente 4
    if len(squares) != 4:
        self.logger.error(f"❌ Esperava 4 quadrados A4, encontrou {len(squares)}")
        return None
    
    # Ordenar: TL, TR, BR, BL
    squares.sort(key=lambda s: (s["cy"], s["cx"]))
    top_row = squares[:2]
    bottom_row = squares[2:]
    top_row.sort(key=lambda s: s["cx"])
    bottom_row.sort(key=lambda s: s["cx"])
    
    ordered = [top_row[0], top_row[1], bottom_row[1], bottom_row[0]]
    
    self.logger.info("✅ 4 quadrados A4 detectados e ordenados")
    return ordered
```

#### 2.3. Etapa 3: Normalização A4
```python
def _normalize_to_a4(self, img: np.ndarray, anchors: List[Dict]) -> np.ndarray:
    """
    Transforma perspectiva para A4 lógico fixo (2480x3508 - 300 DPI)
    """
    # Pontos de origem (nos 4 quadrados detectados)
    src_pts = np.float32([
        [anchors[0]["cx"], anchors[0]["cy"]],  # TL
        [anchors[1]["cx"], anchors[1]["cy"]],  # TR
        [anchors[2]["cx"], anchors[2]["cy"]],  # BR
        [anchors[3]["cx"], anchors[3]["cy"]]   # BL
    ])
    
    # Pontos de destino (A4 lógico)
    A4_WIDTH = 2480   # 21cm a 300 DPI
    A4_HEIGHT = 3508  # 29.7cm a 300 DPI
    
    dst_pts = np.float32([
        [0, 0],                    # TL
        [A4_WIDTH, 0],             # TR
        [A4_WIDTH, A4_HEIGHT],     # BR
        [0, A4_HEIGHT]             # BL
    ])
    
    # Calcular matriz de transformação
    matrix = cv2.getPerspectiveTransform(src_pts, dst_pts)
    
    # Aplicar warp
    warped = cv2.warpPerspective(img, matrix, (A4_WIDTH, A4_HEIGHT))
    
    self.logger.info(f"✅ Imagem normalizada para A4 lógico ({A4_WIDTH}x{A4_HEIGHT})")
    return warped
```

#### 2.4. Etapa 4: Detecção Triângulos
```python
def _detect_grid_triangles(self, img_a4: np.ndarray, edges: np.ndarray) -> Optional[List[Dict]]:
    """
    Detecta exatamente 4 triângulos pretos delimitando o grid
    """
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    
    triangles = []
    for cnt in contours:
        # Aproximar para polígono
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
        
        # Deve ter 3 vértices
        if len(approx) != 3:
            continue
        
        # Área grande (0.6cm x 0.6cm a 300 DPI ≈ 70x70px ≈ 2450px²)
        area = cv2.contourArea(cnt)
        if area < 1000:  # Mínimo 1000px²
            continue
        
        # Calcular centróide
        M = cv2.moments(cnt)
        if M["m00"] == 0:
            continue
        cx = int(M["m10"] / M["m00"])
        cy = int(M["m01"] / M["m00"])
        
        triangles.append({
            "contour": approx,
            "cx": cx,
            "cy": cy,
            "area": area
        })
    
    # Deve encontrar exatamente 4
    if len(triangles) != 4:
        self.logger.error(f"❌ Esperava 4 triângulos, encontrou {len(triangles)}")
        return None
    
    # Ordenar: TL, TR, BR, BL
    triangles.sort(key=lambda t: (t["cy"], t["cx"]))
    top_row = triangles[:2]
    bottom_row = triangles[2:]
    top_row.sort(key=lambda t: t["cx"])
    bottom_row.sort(key=lambda t: t["cx"])
    
    ordered = [top_row[0], top_row[1], bottom_row[1], bottom_row[0]]
    
    self.logger.info("✅ 4 triângulos detectados e ordenados")
    return ordered
```

#### 2.5. Etapa 5: Detecção Blocos
```python
def _detect_answer_blocks(self, img_a4: np.ndarray, grid_area: Dict,
                          num_blocks_expected: int) -> Optional[List[Dict]]:
    """
    Detecta blocos com bordas pretas de 2px
    """
    # Crop área do grid
    x, y, w, h = grid_area["x"], grid_area["y"], grid_area["w"], grid_area["h"]
    grid_roi = img_a4[y:y+h, x:x+w]
    
    # Pré-processar
    gray = cv2.cvtColor(grid_roi, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 50, 150)
    
    # Detectar contornos
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    
    blocks = []
    for cnt in contours:
        # Aproximar para polígono
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
        
        # Deve ter 4 vértices (retângulo)
        if len(approx) != 4:
            continue
        
        # Área significativa (pelo menos 10% da área do grid)
        area = cv2.contourArea(cnt)
        min_area = (w * h) * 0.10
        if area < min_area:
            continue
        
        # Bounding box
        bx, by, bw, bh = cv2.boundingRect(approx)
        
        # Proporção vertical (blocos são mais altos que largos)
        aspect_ratio = bh / float(bw)
        if aspect_ratio < 1.2:  # Pelo menos 20% mais alto
            continue
        
        blocks.append({
            "contour": approx,
            "x": x + bx,  # Coordenadas absolutas no A4
            "y": y + by,
            "w": bw,
            "h": bh,
            "area": area
        })
    
    # Ordenar por Y (cima para baixo)
    blocks.sort(key=lambda b: b["y"])
    
    # Validar número de blocos
    if len(blocks) != num_blocks_expected:
        self.logger.error(
            f"❌ Esperava {num_blocks_expected} blocos, encontrou {len(blocks)}"
        )
        return None
    
    self.logger.info(f"✅ {num_blocks_expected} blocos detectados e ordenados")
    return blocks
```

#### 2.6. Etapa 6: Mapeamento JSON → Grid (CRÍTICO)
```python
def _map_topology_to_grid(self, block_roi: np.ndarray, block_config: Dict) -> Dict:
    """
    🔴 FUNÇÃO MAIS IMPORTANTE
    
    A imagem NÃO define linhas ou colunas.
    O JSON define TUDO.
    """
    block_height, block_width = block_roi.shape[:2]
    
    questions = block_config.get("questions", [])
    num_rows = len(questions)
    
    if num_rows == 0:
        self.logger.error("❌ Nenhuma questão no bloco")
        return None
    
    # Calcular altura da linha
    row_height = block_height / num_rows
    
    grid_map = {
        "num_rows": num_rows,
        "row_height": row_height,
        "block_width": block_width,
        "block_height": block_height,
        "questions": []
    }
    
    for row_idx, question in enumerate(questions):
        q_num = question.get("q")
        alternatives = question.get("alternatives", [])
        num_cols = len(alternatives)
        
        if num_cols == 0:
            self.logger.warning(f"⚠️ Questão {q_num} sem alternativas")
            continue
        
        # Calcular largura da coluna PARA ESTA QUESTÃO
        col_width = block_width / num_cols
        
        # Centro Y da linha
        cy = row_height * row_idx + row_height / 2
        
        question_map = {
            "q_num": q_num,
            "row_idx": row_idx,
            "cy": cy,
            "num_cols": num_cols,
            "col_width": col_width,
            "alternatives": []
        }
        
        for col_idx, alt_letter in enumerate(alternatives):
            # Centro X da coluna
            cx = col_width * col_idx + col_width / 2
            
            question_map["alternatives"].append({
                "letter": alt_letter,
                "col_idx": col_idx,
                "cx": cx
            })
        
        grid_map["questions"].append(question_map)
    
    self.logger.info(
        f"✅ Grid mapeado: {num_rows} questões, "
        f"larguras de coluna variáveis"
    )
    
    return grid_map
```

#### 2.7. Etapa 7: Cálculo Centros Bolhas
```python
def _calculate_bubble_centers(self, grid_map: Dict, block_roi: np.ndarray) -> List[Dict]:
    """
    Calcula centros e raios de TODAS as bolhas
    """
    row_height = grid_map["row_height"]
    
    # Raio proporcional à altura da linha
    bubble_radius = int(row_height * 0.35)
    
    bubbles = []
    
    for question in grid_map["questions"]:
        q_num = question["q_num"]
        cy = int(question["cy"])
        
        for alt in question["alternatives"]:
            cx = int(alt["cx"])
            letter = alt["letter"]
            
            bubbles.append({
                "q_num": q_num,
                "alternative": letter,
                "cx": cx,
                "cy": cy,
                "r": bubble_radius
            })
    
    self.logger.info(f"✅ {len(bubbles)} centros de bolhas calculados")
    return bubbles
```

#### 2.8. Etapa 8: Detecção de Marcação
```python
def _detect_marked_bubbles(self, block_roi: np.ndarray, bubbles: List[Dict]) -> Dict[int, str]:
    """
    Detecta quais bolhas estão marcadas
    """
    # Pré-processar bloco
    gray = cv2.cvtColor(block_roi, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    
    # Threshold invertido (branco = marcado)
    _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    # Agrupar bolhas por questão
    questions_dict = defaultdict(list)
    for bubble in bubbles:
        q_num = bubble["q_num"]
        questions_dict[q_num].append(bubble)
    
    answers = {}
    
    for q_num, q_bubbles in questions_dict.items():
        fill_ratios = []
        
        for bubble in q_bubbles:
            cx, cy, r = bubble["cx"], bubble["cy"], bubble["r"]
            letter = bubble["alternative"]
            
            # Criar máscara circular
            mask = np.zeros_like(thresh)
            cv2.circle(mask, (cx, cy), r, 255, -1)
            
            # Contar pixels escuros na máscara
            masked = cv2.bitwise_and(thresh, mask)
            black_pixels = cv2.countNonZero(masked)
            total_pixels = cv2.countNonZero(mask)
            
            fill_ratio = black_pixels / total_pixels if total_pixels > 0 else 0
            
            fill_ratios.append({
                "letter": letter,
                "fill_ratio": fill_ratio
            })
        
        # Ordenar por fill_ratio
        fill_ratios.sort(key=lambda x: x["fill_ratio"], reverse=True)
        
        # Critérios de decisão
        THRESHOLD = 0.45
        
        # Verificar múltiplas marcações
        marked_count = sum(1 for fr in fill_ratios if fr["fill_ratio"] > THRESHOLD)
        
        if marked_count == 0:
            # Nenhuma marcada
            answers[q_num] = None
        elif marked_count == 1:
            # Exatamente uma marcada
            answers[q_num] = fill_ratios[0]["letter"]
        else:
            # Múltiplas marcadas → inválida
            answers[q_num] = "INVALID"
    
    self.logger.info(f"✅ {len(answers)} respostas detectadas")
    return answers
```

#### 2.9. Etapa 9: Resultado Final
```python
def _build_result(self, answers: Dict[int, str], gabarito: Dict[int, str]) -> Dict:
    """
    Constrói resultado final comparando com gabarito
    """
    total_questions = len(gabarito)
    correct = 0
    wrong = 0
    blank = 0
    invalid = 0
    
    detailed_answers = []
    
    for q_num in sorted(gabarito.keys()):
        marked = answers.get(q_num)
        correct_answer = gabarito[q_num]
        
        if marked == "INVALID":
            invalid += 1
            is_correct = False
        elif marked is None:
            blank += 1
            is_correct = False
        elif marked == correct_answer:
            correct += 1
            is_correct = True
        else:
            wrong += 1
            is_correct = False
        
        detailed_answers.append({
            "question": q_num,
            "marked": marked,
            "correct": correct_answer,
            "is_correct": is_correct
        })
    
    score = (correct / total_questions * 100) if total_questions > 0 else 0
    
    return {
        "success": True,
        "total_questions": total_questions,
        "correct_answers": correct,
        "wrong_answers": wrong,
        "blank_answers": blank,
        "invalid_answers": invalid,
        "score": round(score, 2),
        "answers": detailed_answers
    }
```

---

## 🧪 TESTES NECESSÁRIOS

### Teste 1: Rejeição de Imagens Inválidas
- [ ] Imagem sem quadrados A4 → deve rejeitar
- [ ] Imagem com apenas 3 quadrados → deve rejeitar
- [ ] Imagem sem triângulos → deve rejeitar
- [ ] Imagem com 3 blocos quando JSON espera 4 → deve rejeitar

### Teste 2: Questões com Alternativas Variáveis
- [ ] Questão com 2 alternativas (A, B)
- [ ] Questão com 3 alternativas (A, B, C)
- [ ] Questão com 4 alternativas (A, B, C, D)
- [ ] Questão com 5 alternativas (A, B, C, D, E)

### Teste 3: Múltiplas Marcações
- [ ] Uma bolha marcada → detectar corretamente
- [ ] Duas bolhas marcadas → retornar "INVALID"
- [ ] Nenhuma bolha marcada → retornar None

### Teste 4: Diferentes Scanners/Câmeras
- [ ] Scanner profissional 300 DPI
- [ ] Scanner básico 150 DPI
- [ ] Foto de celular com boa iluminação
- [ ] Foto de celular com sombra

---

## 📋 CHECKLIST DE IMPLEMENTAÇÃO

### FASE 1: LIMPEZA
- [ ] Backup do arquivo original (`correction_n.py` → `correction_n_backup.py`)
- [ ] Remover 15 funções desnecessárias
- [ ] Remover constantes fixas hardcoded
- [ ] Limpar imports não utilizados

### FASE 2: IMPLEMENTAÇÃO
- [ ] Implementar `_preprocess_image()`
- [ ] Refatorar `_detect_a4_anchors()` com validação rigorosa
- [ ] Refatorar `_normalize_to_a4()` com tamanho fixo
- [ ] Refatorar `_detect_grid_triangles()` com validação rigorosa
- [ ] Refatorar `_detect_answer_blocks()` com validação de quantidade
- [ ] **CRIAR** `_map_topology_to_grid()` (nova função)
- [ ] **CRIAR** `_calculate_bubble_centers()` (nova função)
- [ ] Simplificar `_detect_marked_bubbles()`
- [ ] Manter `_build_result()` (já existe)

### FASE 3: INTEGRAÇÃO
- [ ] Refatorar `corrigir_cartao_resposta()` para chamar pipeline em ordem
- [ ] Adicionar logs detalhados em cada etapa
- [ ] Adicionar salvamento de imagens de debug
- [ ] Tratar exceções com mensagens claras

### FASE 4: TESTES
- [ ] Testar com imagens reais
- [ ] Validar todas as rejeições
- [ ] Testar questões com 2-5 alternativas
- [ ] Testar múltiplas marcações
- [ ] Medir taxa de acerto

---

## ⚠️ AVISOS IMPORTANTES

### 🚨 NÃO FAZER
- ❌ NÃO usar machine learning
- ❌ NÃO usar OCR
- ❌ NÃO tentar detectar texto
- ❌ NÃO tentar inferir layout pela imagem
- ❌ NÃO assumir números fixos de questões/alternativas
- ❌ NÃO usar Hough Circle Transform

### ✅ FAZER
- ✅ Usar apenas o JSON como fonte da verdade
- ✅ Validar rigorosamente em cada etapa
- ✅ Rejeitar imagens inválidas sem tentar "adivinhar"
- ✅ Calcular tudo matematicamente
- ✅ Logar cada decisão importante
- ✅ Salvar imagens de debug quando necessário

---

## 📊 MÉTRICAS DE SUCESSO

### Objetivo: Taxa de Acerto > 99%
- Questões com 1 alternativa marcada: 99.5% de acerto
- Questões em branco: 98% de detecção correta
- Múltiplas marcações: 100% de detecção

### Objetivo: Taxa de Rejeição Correta
- Imagens inválidas: 100% de rejeição
- Falsos positivos: < 0.1%

---

## 🎯 PRÓXIMOS PASSOS

1. **REVISAR** este plano com o time
2. **APROVAR** a arquitetura proposta
3. **CRIAR BACKUP** do código atual
4. **IMPLEMENTAR** fase por fase
5. **TESTAR** cada etapa isoladamente
6. **INTEGRAR** o pipeline completo
7. **VALIDAR** com imagens reais

---

**Autor:** Sistema de Análise OMR  
**Versão:** 1.0  
**Status:** 🟡 AGUARDANDO APROVAÇÃO PARA IMPLEMENTAÇÃO
