# ✅ CHECKLIST DE IMPLEMENTAÇÃO - PIPELINE OMR ROBUSTO

**Data:** 21 de Janeiro de 2026  
**Versão:** 1.0  
**Desenvolvedor:** ___________________  
**Data Início:** ___/___/_____  
**Data Fim:** ___/___/_____

---

## 📋 INSTRUÇÕES DE USO

- [ ] Imprimir ou abrir este checklist
- [ ] Marcar cada item após conclusão
- [ ] Testar cada etapa antes de avançar
- [ ] Fazer commit após cada fase completada
- [ ] Anotar dificuldades encontradas

---

## 🎯 FASE 0: PREPARAÇÃO (Tempo estimado: 1h)

### 0.1. Backup e Controle de Versão
- [ ] Criar branch Git: `git checkout -b refactor/omr-robusto-pipeline`
- [ ] Fazer backup do arquivo atual:
  ```bash
  cp app/services/cartao_resposta/correction_n.py app/services/cartao_resposta/correction_n_backup_YYYYMMDD.py
  ```
- [ ] Verificar que backup foi criado com sucesso
- [ ] Adicionar backup ao `.gitignore`:
  ```bash
  echo "*_backup_*.py" >> .gitignore
  ```

### 0.2. Preparar Ambiente de Teste
- [ ] Criar pasta `test_images/` na raiz do projeto
- [ ] Adicionar pelo menos 10 imagens de teste:
  - [ ] 3 imagens válidas (scanners diferentes)
  - [ ] 2 imagens com qualidade ruim
  - [ ] 2 imagens com múltiplas marcações
  - [ ] 2 imagens com marcações parciais
  - [ ] 1 imagem sem quadrados A4 (para teste de rejeição)
- [ ] Criar arquivo `test_topology.json` com estrutura de teste

### 0.3. Revisar Documentação
- [ ] Ler completamente `PLANO_REFATORACAO_OMR_ROBUSTO.md`
- [ ] Ler completamente `ANALISE_CODIGO_ATUAL_OMR.md`
- [ ] Ler completamente `ESPECIFICACAO_JSON_TOPOLOGIA.md`
- [ ] Ler completamente `GUIA_VISUAL_PIPELINE_OMR.md`
- [ ] Entender o fluxo completo das 9 etapas
- [ ] Tirar dúvidas com o time (se houver)

### 0.4. Configurar Debug
- [ ] Criar pasta `debug_corrections/` (se não existir)
- [ ] Configurar logs para nível DEBUG
- [ ] Testar salvamento de imagens de debug

**STATUS FASE 0:** ⬜ Não iniciada | 🟡 Em progresso | ✅ Concluída

---

## 🗑️ FASE 1: LIMPEZA (Tempo estimado: 2h)

### 1.1. Remover Funções de Templates (422 linhas)
- [ ] Localizar função `gerar_templates_blocos()` (linhas ~278-398)
- [ ] Remover função completa
- [ ] Localizar função `_gerar_pdf_template()` (linhas ~399-468)
- [ ] Remover função completa
- [ ] Localizar função `salvar_templates_no_gabarito()` (linhas ~469-506)
- [ ] Remover função completa
- [ ] Localizar função `_carregar_template_bloco()` (linhas ~507-576)
- [ ] Remover função completa
- [ ] Localizar função `_comparar_roi_com_template()` (linhas ~577-625)
- [ ] Remover função completa
- [ ] Localizar função `_medir_preenchimento_com_template()` (linhas ~626-699)
- [ ] Remover função completa
- [ ] Verificar que nenhuma outra função chama essas funções removidas
- [ ] **COMMIT:** `git commit -m "Fase 1.1: Remove template system (422 lines)"`

### 1.2. Remover Funções de Detecção de Bolhas (425 linhas)
- [ ] Localizar função `_detectar_todas_bolhas()` (linhas ~2325-2429)
- [ ] Remover função completa
- [ ] Localizar função `_detectar_bolhas_hough()` (linhas ~2551-2621)
- [ ] Remover função completa
- [ ] Localizar função `_agrupar_bolhas_por_linha_fisica()` (linhas ~2746-2804)
- [ ] Remover função completa
- [ ] Localizar função `_agrupar_bolhas_por_linha()` (linhas ~4401-4501)
- [ ] Remover função completa
- [ ] Localizar função `_validar_grupo_questao()` (linhas ~4502-4516)
- [ ] Remover função completa
- [ ] Localizar função `_dividir_grupo_invalido()` (linhas ~4517-4569)
- [ ] Remover função completa
- [ ] **COMMIT:** `git commit -m "Fase 1.2: Remove bubble detection functions (425 lines)"`

### 1.3. Remover Funções de Cálculos Dinâmicos (320 linhas)
- [ ] Localizar função `_calcular_top_padding_dinamico()` (linhas ~2430-2484)
- [ ] Remover função completa
- [ ] Localizar função `_calcular_line_height_dinamico()` (linhas ~2485-2550)
- [ ] Remover função completa
- [ ] Localizar função `_calcular_grid_baseado_em_bolhas_reais()` (linhas ~2622-2745)
- [ ] Remover função completa
- [ ] **COMMIT:** `git commit -m "Fase 1.3: Remove dynamic calculation functions (320 lines)"`

### 1.4. Remover Métodos Legados (410 linhas)
- [ ] Localizar função `_processar_bloco_sem_referencia()` (linhas ~3380-3671)
- [ ] Remover função completa
- [ ] Localizar função `_corrigir_com_metodo_antigo()` (linhas ~3993-4087)
- [ ] Remover função completa
- [ ] Localizar função `_validar_distancia_grid()` (linhas ~3250-3275)
- [ ] Remover função completa
- [ ] **COMMIT:** `git commit -m "Fase 1.4: Remove legacy methods (410 lines)"`

### 1.5. Remover Constantes Fixas
- [ ] Localizar constantes no início da classe (linhas ~30-46)
- [ ] Comentar ou remover:
  ```python
  # REMOVIDO: LINE_Y_THRESHOLD = 8
  # REMOVIDO: STANDARD_BLOCK_WIDTH = 431
  # REMOVIDO: STANDARD_BLOCK_HEIGHT = 362
  # REMOVIDO: BUBBLE_MIN_SIZE = 20
  # REMOVIDO: BUBBLE_MAX_SIZE = 50
  # REMOVIDO: ASPECT_RATIO_MIN = 0.9
  # REMOVIDO: ASPECT_RATIO_MAX = 1.1
  ```
- [ ] Deixar apenas:
  ```python
  # Constantes de normalização A4
  A4_WIDTH_PX = 2480   # 21cm a 300 DPI
  A4_HEIGHT_PX = 3508  # 29.7cm a 300 DPI
  
  # Threshold de detecção de marcação
  FILL_THRESHOLD = 0.45  # 45% da área preenchida
  ```
- [ ] **COMMIT:** `git commit -m "Fase 1.5: Remove hardcoded constants"`

### 1.6. Verificação de Limpeza
- [ ] Executar `grep -n "TODO\|FIXME\|XXX" correction_n.py`
- [ ] Verificar que arquivo compilar sem erros de sintaxe:
  ```bash
  python -m py_compile app/services/cartao_resposta/correction_n.py
  ```
- [ ] Contar linhas removidas:
  ```bash
  # Backup: ~6031 linhas
  # Atual: ~4454 linhas
  # Removidas: ~1577 linhas
  ```
- [ ] **COMMIT:** `git commit -m "Fase 1: Cleanup complete - removed 1577 lines"`

**STATUS FASE 1:** ⬜ Não iniciada | 🟡 Em progresso | ✅ Concluída

---

## 🔨 FASE 2: REFATORAÇÃO (Tempo estimado: 8h)

### 2.1. Criar Função _preprocess_image()
- [ ] Adicionar função nova após `__init__()`:
  ```python
  def _preprocess_image(self, img: np.ndarray) -> Dict[str, np.ndarray]:
      """Pré-processamento padrão: gray, blur, thresh, edges"""
  ```
- [ ] Implementar conforme especificação do PLANO
- [ ] Testar com imagem de exemplo:
  ```python
  img = cv2.imread("test_images/test_001.jpg")
  result = self._preprocess_image(img)
  assert "gray" in result
  assert "blur" in result
  assert "thresh" in result
  assert "edges" in result
  ```
- [ ] Salvar imagens de debug (edges, thresh)
- [ ] **COMMIT:** `git commit -m "Fase 2.1: Add _preprocess_image() function"`

### 2.2. Refatorar _detectar_quadrados_a4() → _detect_a4_anchors()
- [ ] Renomear função para `_detect_a4_anchors()`
- [ ] Simplificar lógica conforme especificação
- [ ] Adicionar validação rigorosa (DEVE ser exatamente 4)
- [ ] Adicionar logs detalhados
- [ ] Remover múltiplas tentativas com thresholds diferentes
- [ ] Testar com 3 imagens válidas (deve retornar 4 âncoras)
- [ ] Testar com 1 imagem inválida (deve retornar None)
- [ ] **COMMIT:** `git commit -m "Fase 2.2: Refactor _detect_a4_anchors() with strict validation"`

### 2.3. Refatorar _normalizar_para_a4() → _normalize_to_a4()
- [ ] Renomear função para `_normalize_to_a4()`
- [ ] Simplificar lógica (remover cálculos complexos de escala)
- [ ] Usar tamanho A4 FIXO (2480x3508)
- [ ] Testar normalização com imagens de diferentes tamanhos
- [ ] Verificar que saída sempre tem dimensão (2480, 3508, 3)
- [ ] Salvar imagem normalizada para debug
- [ ] **COMMIT:** `git commit -m "Fase 2.3: Refactor _normalize_to_a4() with fixed size"`

### 2.4. Refatorar _detectar_triangulos_na_area_blocos() → _detect_grid_triangles()
- [ ] Renomear função para `_detect_grid_triangles()`
- [ ] Simplificar lógica (336 linhas → ~80 linhas)
- [ ] Remover tentativa de inferir 4º triângulo
- [ ] Remover uso de área padrão se não encontrar
- [ ] Adicionar validação rigorosa (DEVE ser exatamente 4)
- [ ] Testar com imagem válida (deve retornar 4 triângulos)
- [ ] Testar com imagem sem triângulos (deve retornar None)
- [ ] **COMMIT:** `git commit -m "Fase 2.4: Refactor _detect_grid_triangles() - strict validation"`

### 2.5. Criar Função _calculate_grid_area()
- [ ] Adicionar função nova:
  ```python
  def _calculate_grid_area(self, triangles: List[Dict]) -> Dict:
      """Calcula área do grid baseado nos 4 triângulos"""
  ```
- [ ] Implementar conforme especificação
- [ ] Testar cálculo com triângulos de exemplo
- [ ] Verificar que área cobre todos os triângulos
- [ ] **COMMIT:** `git commit -m "Fase 2.5: Add _calculate_grid_area() function"`

### 2.6. Refatorar _detectar_blocos_resposta() → _detect_answer_blocks()
- [ ] Renomear função para `_detect_answer_blocks()`
- [ ] Adicionar parâmetro `num_blocks_expected` do JSON
- [ ] Adicionar validação: `len(blocks) DEVE == num_blocks_expected`
- [ ] Simplificar lógica de detecção
- [ ] Testar com JSON de 4 blocos + imagem com 4 blocos (deve aceitar)
- [ ] Testar com JSON de 4 blocos + imagem com 3 blocos (deve rejeitar)
- [ ] **COMMIT:** `git commit -m "Fase 2.6: Refactor _detect_answer_blocks() with JSON validation"`

### 2.7. Criar Função _map_topology_to_grid() (🔴 CRÍTICA)
- [ ] Adicionar função nova:
  ```python
  def _map_topology_to_grid(self, block_roi: np.ndarray, block_config: Dict) -> Dict:
      """Mapeia topologia do JSON para grid matemático"""
  ```
- [ ] Implementar conforme especificação do PLANO (100 linhas)
- [ ] Testar com bloco de 4 questões, todas com 4 alternativas
- [ ] Testar com bloco de alternativas variáveis: [2, 3, 4, 5]
- [ ] Verificar que `col_width` varia por questão
- [ ] Verificar que `row_height` é constante para o bloco
- [ ] Salvar logs detalhados do grid calculado
- [ ] **COMMIT:** `git commit -m "Fase 2.7: Add _map_topology_to_grid() - CRITICAL FUNCTION"`

### 2.8. Criar Função _calculate_bubble_centers()
- [ ] Adicionar função nova:
  ```python
  def _calculate_bubble_centers(self, grid_map: Dict, block_roi: np.ndarray) -> List[Dict]:
      """Calcula centros e raios de todas as bolhas"""
  ```
- [ ] Implementar conforme especificação
- [ ] Calcular raio: `r = row_height * 0.35`
- [ ] Testar com grid_map de teste
- [ ] Verificar que retorna lista com todas as bolhas
- [ ] Verificar que cada bolha tem: q_num, alternative, cx, cy, r
- [ ] **COMMIT:** `git commit -m "Fase 2.8: Add _calculate_bubble_centers() function"`

### 2.9. Simplificar _medir_preenchimento_bolha() → _detect_marked_bubbles()
- [ ] Renomear função para `_detect_marked_bubbles()`
- [ ] Receber lista de bubbles (da etapa 7) ao invés de grid
- [ ] Simplificar lógica de máscara (círculo completo, não anel)
- [ ] Implementar decisão por questão (1 marcada, 0 marcadas, 2+ marcadas)
- [ ] Usar THRESHOLD = 0.45
- [ ] Testar com imagem de uma marcação (deve retornar letra)
- [ ] Testar com imagem de múltiplas marcações (deve retornar "INVALID")
- [ ] Testar com imagem em branco (deve retornar None)
- [ ] **COMMIT:** `git commit -m "Fase 2.9: Simplify _detect_marked_bubbles() with threshold logic"`

**STATUS FASE 2:** ⬜ Não iniciada | 🟡 Em progresso | ✅ Concluída

---

## 🔗 FASE 3: INTEGRAÇÃO (Tempo estimado: 4h)

### 3.1. Criar Funções Auxiliares

#### 3.1.1. _get_block_config()
- [ ] Adicionar função:
  ```python
  def _get_block_config(self, topology_json: Dict, block_num: int) -> Optional[Dict]:
      """Extrai configuração de um bloco específico do JSON"""
  ```
- [ ] Implementar busca no JSON
- [ ] Testar com topology_json de teste
- [ ] **COMMIT:** `git commit -m "Fase 3.1.1: Add _get_block_config()"`

#### 3.1.2. _load_topology()
- [ ] Adicionar função:
  ```python
  def _load_topology(self, gabarito_id: str) -> Optional[Dict]:
      """Carrega JSON de topologia do banco"""
  ```
- [ ] Buscar campo `topology_json` da tabela
- [ ] Validar estrutura do JSON
- [ ] Testar com gabarito real do banco
- [ ] **COMMIT:** `git commit -m "Fase 3.1.2: Add _load_topology()"`

#### 3.1.3. _load_gabarito()
- [ ] Adicionar função:
  ```python
  def _load_gabarito(self, gabarito_id: str) -> Optional[Dict[int, str]]:
      """Carrega respostas corretas do gabarito"""
  ```
- [ ] Buscar campo `correct_answers` da tabela
- [ ] Converter para formato {1: "A", 2: "C", ...}
- [ ] Testar com gabarito real
- [ ] **COMMIT:** `git commit -m "Fase 3.1.3: Add _load_gabarito()"`

### 3.2. Criar Pipeline Principal

#### 3.2.1. _execute_omr_pipeline()
- [ ] Adicionar função:
  ```python
  def _execute_omr_pipeline(self, img: np.ndarray, topology_json: Dict) -> Dict[str, Any]:
      """Pipeline de 9 etapas"""
  ```
- [ ] Implementar chamada sequencial das 9 etapas:
  1. [ ] Chamar `_preprocess_image()`
  2. [ ] Chamar `_detect_a4_anchors()` + validar
  3. [ ] Chamar `_normalize_to_a4()`
  4. [ ] Reprocessar imagem normalizada
  5. [ ] Chamar `_detect_grid_triangles()` + validar
  6. [ ] Chamar `_calculate_grid_area()`
  7. [ ] Chamar `_detect_answer_blocks()` + validar
  8. [ ] Loop pelos blocos:
      - [ ] Chamar `_get_block_config()`
      - [ ] Chamar `_map_topology_to_grid()`
      - [ ] Chamar `_calculate_bubble_centers()`
      - [ ] Chamar `_detect_marked_bubbles()`
  9. [ ] Retornar `{"success": True, "answers": {...}}`
- [ ] Adicionar tratamento de erros em cada etapa
- [ ] Adicionar logs detalhados
- [ ] Testar pipeline completo com 1 imagem válida
- [ ] **COMMIT:** `git commit -m "Fase 3.2.1: Add _execute_omr_pipeline() - main pipeline"`

#### 3.2.2. Refatorar corrigir_cartao_resposta()
- [ ] Simplificar função principal (525 linhas → ~100 linhas)
- [ ] Estrutura nova:
  1. [ ] Validar entrada
  2. [ ] Decodificar imagem
  3. [ ] Detectar QR Code
  4. [ ] Carregar topologia
  5. [ ] Carregar gabarito
  6. [ ] **Chamar _execute_omr_pipeline()**
  7. [ ] Chamar _build_result()
  8. [ ] Salvar no banco
  9. [ ] Retornar resultado
- [ ] Remover múltiplos caminhos de execução
- [ ] Remover métodos alternativos
- [ ] Testar fluxo completo
- [ ] **COMMIT:** `git commit -m "Fase 3.2.2: Refactor corrigir_cartao_resposta() - linear pipeline"`

### 3.3. Testar Integração Completa
- [ ] Testar com 3 imagens válidas
- [ ] Verificar que todas passam pelo pipeline
- [ ] Verificar que resultados são salvos no banco
- [ ] Verificar logs de cada etapa
- [ ] **COMMIT:** `git commit -m "Fase 3: Integration complete - tested with real images"`

**STATUS FASE 3:** ⬜ Não iniciada | 🟡 Em progresso | ✅ Concluída

---

## 🧪 FASE 4: TESTES (Tempo estimado: 6h)

### 4.1. Testes de Rejeição

#### 4.1.1. Teste: Imagem Sem Quadrados A4
- [ ] Preparar imagem sem os 4 quadrados
- [ ] Executar pipeline
- [ ] Verificar que retorna: `{"success": False, "error": "Âncoras A4 não detectadas"}`
- [ ] Verificar que não processou etapas seguintes
- [ ] **RESULTADO:** ⬜ Passou | ❌ Falhou

#### 4.1.2. Teste: Imagem Com 3 Quadrados
- [ ] Preparar imagem com apenas 3 quadrados
- [ ] Executar pipeline
- [ ] Verificar rejeição
- [ ] **RESULTADO:** ⬜ Passou | ❌ Falhou

#### 4.1.3. Teste: Imagem Sem Triângulos
- [ ] Preparar imagem sem triângulos do grid
- [ ] Executar pipeline
- [ ] Verificar que retorna: `{"success": False, "error": "Triângulos do grid não detectados"}`
- [ ] **RESULTADO:** ⬜ Passou | ❌ Falhou

#### 4.1.4. Teste: Número de Blocos Incompatível
- [ ] JSON diz 4 blocos, imagem tem 3
- [ ] Executar pipeline
- [ ] Verificar que retorna: `{"success": False, "error": "Esperava 4 blocos, encontrou 3"}`
- [ ] **RESULTADO:** ⬜ Passou | ❌ Falhou

### 4.2. Testes de Alternativas Variáveis

#### 4.2.1. Teste: 2 Alternativas (A, B)
- [ ] Criar topology_json com questão de 2 alternativas
- [ ] Criar imagem com 2 bolhas
- [ ] Marcar alternativa B
- [ ] Executar pipeline
- [ ] Verificar que detecta "B" corretamente
- [ ] **RESULTADO:** ⬜ Passou | ❌ Falhou

#### 4.2.2. Teste: 3 Alternativas (A, B, C)
- [ ] Criar topology_json com questão de 3 alternativas
- [ ] Marcar alternativa C
- [ ] Verificar detecção correta
- [ ] **RESULTADO:** ⬜ Passou | ❌ Falhou

#### 4.2.3. Teste: 4 Alternativas (A, B, C, D)
- [ ] Teste padrão com 4 alternativas
- [ ] **RESULTADO:** ⬜ Passou | ❌ Falhou

#### 4.2.4. Teste: 5 Alternativas (A, B, C, D, E)
- [ ] Criar topology_json com 5 alternativas
- [ ] Marcar alternativa E
- [ ] Verificar detecção correta
- [ ] **RESULTADO:** ⬜ Passou | ❌ Falhou

#### 4.2.5. Teste: Bloco com Alternativas Mistas
- [ ] Q1: 2 alternativas (A, B)
- [ ] Q2: 4 alternativas (A, B, C, D)
- [ ] Q3: 3 alternativas (A, B, C)
- [ ] Q4: 5 alternativas (A, B, C, D, E)
- [ ] Verificar que col_width varia por linha
- [ ] Verificar detecções corretas
- [ ] **RESULTADO:** ⬜ Passou | ❌ Falhou

### 4.3. Testes de Marcação

#### 4.3.1. Teste: Uma Marcação Clara
- [ ] Marcar apenas uma bolha com caneta preta
- [ ] fill_ratio esperado > 0.70
- [ ] Verificar detecção correta
- [ ] **RESULTADO:** ⬜ Passou | ❌ Falhou

#### 4.3.2. Teste: Marcação Parcial (Threshold Borderline)
- [ ] Marcar bolha com ~50% de preenchimento
- [ ] fill_ratio esperado ~0.50
- [ ] Verificar que detecta como marcada (> 0.45)
- [ ] **RESULTADO:** ⬜ Passou | ❌ Falhou

#### 4.3.3. Teste: Marcação Muito Fraca
- [ ] Marcar bolha com apenas 30% de preenchimento
- [ ] fill_ratio esperado ~0.30
- [ ] Verificar que NÃO detecta como marcada (< 0.45)
- [ ] **RESULTADO:** ⬜ Passou | ❌ Falhou

#### 4.3.4. Teste: Múltiplas Marcações
- [ ] Marcar 2 bolhas na mesma questão
- [ ] Ambas com fill_ratio > 0.45
- [ ] Verificar que retorna "INVALID"
- [ ] **RESULTADO:** ⬜ Passou | ❌ Falhou

#### 4.3.5. Teste: Questão em Branco
- [ ] Não marcar nenhuma bolha
- [ ] Verificar que retorna None
- [ ] **RESULTADO:** ⬜ Passou | ❌ Falhou

### 4.4. Testes de Qualidade de Imagem

#### 4.4.1. Teste: Scanner Profissional 300 DPI
- [ ] Processar imagem de scanner profissional
- [ ] Verificar taxa de acerto > 99%
- [ ] **RESULTADO:** ⬜ Passou | ❌ Falhou

#### 4.4.2. Teste: Scanner Básico 150 DPI
- [ ] Processar imagem de scanner básico
- [ ] Verificar taxa de acerto > 98%
- [ ] **RESULTADO:** ⬜ Passou | ❌ Falhou

#### 4.4.3. Teste: Foto de Celular Boa Iluminação
- [ ] Processar foto de celular com boa luz
- [ ] Verificar taxa de acerto > 97%
- [ ] **RESULTADO:** ⬜ Passou | ❌ Falhou

#### 4.4.4. Teste: Foto de Celular com Sombra
- [ ] Processar foto com sombra parcial
- [ ] Verificar se normalização corrige
- [ ] Taxa de acerto aceitável > 95%
- [ ] **RESULTADO:** ⬜ Passou | ❌ Falhou

### 4.5. Testes de Estrutura Variável

#### 4.5.1. Teste: Prova com 10 Questões por Bloco
- [ ] JSON: 4 blocos × 10 questões = 40 questões
- [ ] Processar imagem correspondente
- [ ] Verificar row_height = block_height / 10
- [ ] **RESULTADO:** ⬜ Passou | ❌ Falhou

#### 4.5.2. Teste: Prova com 26 Questões por Bloco
- [ ] JSON: 4 blocos × 26 questões = 104 questões
- [ ] Processar imagem correspondente
- [ ] Verificar row_height = block_height / 26
- [ ] Verificar que bolhas não se sobrepõem
- [ ] **RESULTADO:** ⬜ Passou | ❌ Falhou

#### 4.5.3. Teste: Número Desigual de Questões por Bloco
- [ ] Bloco 1: 10 questões
- [ ] Bloco 2: 15 questões
- [ ] Bloco 3: 8 questões
- [ ] Bloco 4: 12 questões
- [ ] Verificar que cada bloco calcula row_height independentemente
- [ ] **RESULTADO:** ⬜ Passou | ❌ Falhou

### 4.6. Estatísticas de Testes

```
┌────────────────────────────┬─────────┬─────────┬──────────┐
│ Categoria de Teste         │ Total   │ Passou  │ Taxa (%) │
├────────────────────────────┼─────────┼─────────┼──────────┤
│ Rejeições                  │    4    │         │          │
│ Alternativas Variáveis     │    5    │         │          │
│ Marcações                  │    5    │         │          │
│ Qualidade de Imagem        │    4    │         │          │
│ Estrutura Variável         │    3    │         │          │
├────────────────────────────┼─────────┼─────────┼──────────┤
│ TOTAL                      │   21    │         │          │
└────────────────────────────┴─────────┴─────────┴──────────┘
```

**STATUS FASE 4:** ⬜ Não iniciada | 🟡 Em progresso | ✅ Concluída

---

## 📊 FASE 5: VALIDAÇÃO E MEDIÇÃO (Tempo estimado: 3h)

### 5.1. Métricas de Performance

#### 5.1.1. Tempo de Processamento
- [ ] Medir tempo de cada etapa com `time.time()`
- [ ] Registrar tempos médios:
  - [ ] Etapa 1 (Pré-processamento): _____ ms
  - [ ] Etapa 2 (Detectar âncoras): _____ ms
  - [ ] Etapa 3 (Normalizar): _____ ms
  - [ ] Etapa 4 (Detectar triângulos): _____ ms
  - [ ] Etapa 5 (Detectar blocos): _____ ms
  - [ ] Etapa 6 (Mapear grid): _____ ms
  - [ ] Etapa 7 (Calcular centros): _____ ms
  - [ ] Etapa 8 (Detectar marcações): _____ ms
  - [ ] Etapa 9 (Resultado): _____ ms
  - [ ] **TOTAL:** _____ ms
- [ ] Verificar que total < 3000 ms (3 segundos)

#### 5.1.2. Linhas de Código
- [ ] Contar linhas finais:
  ```bash
  wc -l app/services/cartao_resposta/correction_n.py
  ```
- [ ] Linhas iniciais: 6031
- [ ] Linhas finais: _____
- [ ] Redução: _____ linhas (_____ %)
- [ ] Meta: < 2700 linhas (55% de redução)

#### 5.1.3. Complexidade Ciclomática
- [ ] Instalar radon: `pip install radon`
- [ ] Medir complexidade:
  ```bash
  radon cc app/services/cartao_resposta/correction_n.py -a
  ```
- [ ] Complexidade média: _____
- [ ] Meta: < 10 (complexidade baixa)

### 5.2. Taxa de Acerto

#### 5.2.1. Dataset de Teste
- [ ] Preparar 100 imagens de teste com gabaritos conhecidos
- [ ] Executar pipeline em todas
- [ ] Registrar resultados:
  - [ ] Corretas: _____ / 100
  - [ ] Taxa de acerto: _____ %
  - [ ] Meta: > 99%

#### 5.2.2. Taxa de Rejeição Correta
- [ ] Preparar 20 imagens inválidas
- [ ] Verificar que todas são rejeitadas
- [ ] Rejeições corretas: _____ / 20
- [ ] Taxa: _____ %
- [ ] Meta: 100%

### 5.3. Qualidade de Código

#### 5.3.1. Linter
- [ ] Executar pylint:
  ```bash
  pylint app/services/cartao_resposta/correction_n.py
  ```
- [ ] Score: _____ / 10
- [ ] Meta: > 8.0

#### 5.3.2. Type Hints
- [ ] Verificar que todas funções públicas têm type hints
- [ ] Executar mypy:
  ```bash
  mypy app/services/cartao_resposta/correction_n.py
  ```
- [ ] Erros: _____
- [ ] Meta: 0 erros

### 5.4. Documentação

#### 5.4.1. Docstrings
- [ ] Verificar que todas funções públicas têm docstrings
- [ ] Verificar formato Google/NumPy style
- [ ] Incluir Args, Returns, Raises

#### 5.4.2. README
- [ ] Atualizar documentação do módulo
- [ ] Incluir exemplos de uso
- [ ] Documentar estrutura do JSON

**STATUS FASE 5:** ⬜ Não iniciada | 🟡 Em progresso | ✅ Concluída

---

## 🚀 FASE 6: DEPLOY (Tempo estimado: 2h)

### 6.1. Preparação para Deploy

#### 6.1.1. Code Review
- [ ] Criar Pull Request no GitLab/GitHub
- [ ] Solicitar revisão de 2 desenvolvedores
- [ ] Endereçar comentários e sugestões
- [ ] Aprovação de revisores: [ ] Dev 1 | [ ] Dev 2

#### 6.1.2. Testes em Staging
- [ ] Deploy em ambiente de staging
- [ ] Executar suite de testes completa
- [ ] Processar 50 imagens reais
- [ ] Validar resultados com time de QA
- [ ] Aprovação QA: [ ] Sim | [ ] Não

### 6.2. Migração de Dados

#### 6.2.1. Adicionar Campo topology_json
- [ ] Criar migration do Alembic:
  ```bash
  alembic revision -m "add_topology_json_field"
  ```
- [ ] Adicionar campo JSONB na tabela answer_sheet_gabaritos
- [ ] Testar migration em ambiente de dev
- [ ] Testar rollback

#### 6.2.2. Migrar Dados Antigos
- [ ] Criar script de migração para gabaritos existentes
- [ ] Gerar topology_json para cada gabarito antigo
- [ ] Executar em staging
- [ ] Validar dados migrados
- [ ] Executar em produção

### 6.3. Deploy em Produção

#### 6.3.1. Backup
- [ ] Fazer backup completo do banco de dados
- [ ] Fazer backup do código atual em produção
- [ ] Verificar que backups estão acessíveis

#### 6.3.2. Deploy
- [ ] Executar migrations do banco
- [ ] Deploy do código novo
- [ ] Reiniciar serviços
- [ ] Verificar logs de inicialização
- [ ] Testar endpoint de saúde

#### 6.3.3. Smoke Tests
- [ ] Processar 5 imagens de teste em produção
- [ ] Verificar que resultados são corretos
- [ ] Verificar que salvamento no banco funciona
- [ ] Verificar logs de cada etapa

### 6.4. Monitoramento Pós-Deploy

#### 6.4.1. Primeiras 24h
- [ ] Monitorar logs de erro
- [ ] Monitorar tempo de processamento
- [ ] Monitorar taxa de rejeição
- [ ] Verificar alertas de exceções

#### 6.4.2. Primeira Semana
- [ ] Comparar métricas com sistema antigo
- [ ] Coletar feedback dos usuários
- [ ] Identificar edge cases não cobertos
- [ ] Ajustar thresholds se necessário

**STATUS FASE 6:** ⬜ Não iniciada | 🟡 Em progresso | ✅ Concluída

---

## 📝 FASE 7: DOCUMENTAÇÃO FINAL (Tempo estimado: 2h)

### 7.1. Atualizar Documentação Técnica
- [ ] Atualizar README.md principal
- [ ] Documentar mudanças no CHANGELOG.md
- [ ] Atualizar diagramas de arquitetura
- [ ] Atualizar Swagger/OpenAPI

### 7.2. Documentação de Usuário
- [ ] Criar guia de uso para professores
- [ ] Documentar limitações conhecidas
- [ ] Criar FAQ com problemas comuns
- [ ] Criar guia de troubleshooting

### 7.3. Treinamento
- [ ] Preparar apresentação do novo sistema
- [ ] Treinar equipe de suporte
- [ ] Treinar equipe de QA
- [ ] Documentar processo de debug

**STATUS FASE 7:** ⬜ Não iniciada | 🟡 Em progresso | ✅ Concluída

---

## 📊 RESUMO FINAL

### Estatísticas Gerais

```
┌────────────────────────────────┬──────────┬──────────┐
│ Métrica                        │ Antes    │ Depois   │
├────────────────────────────────┼──────────┼──────────┤
│ Linhas de código               │ 6031     │          │
│ Número de funções              │ 63       │          │
│ Complexidade ciclomática       │ Alta     │          │
│ Taxa de acerto                 │ ~95%     │          │
│ Tempo de processamento         │ ~5s      │          │
│ Suporte alternativas variáveis │ ❌       │          │
│ Validação rigorosa             │ ❌       │          │
│ Determinístico                 │ ❌       │          │
└────────────────────────────────┴──────────┴──────────┘
```

### Melhorias Alcançadas

- [ ] ✅ Redução de código (> 50%)
- [ ] ✅ Simplicidade (complexidade baixa)
- [ ] ✅ Taxa de acerto (> 99%)
- [ ] ✅ Performance (< 3s)
- [ ] ✅ Suporte a alternativas variáveis
- [ ] ✅ Validação rigorosa
- [ ] ✅ Sistema determinístico
- [ ] ✅ Fácil manutenção
- [ ] ✅ Bem documentado
- [ ] ✅ Bem testado

### Lições Aprendidas

```
┌─────────────────────────────────────────────────────────┐
│ 1.                                                      │
│                                                         │
│ 2.                                                      │
│                                                         │
│ 3.                                                      │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### Problemas Encontrados

```
┌─────────────────────────────────────────────────────────┐
│ 1.                                                      │
│                                                         │
│ 2.                                                      │
│                                                         │
│ 3.                                                      │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## ✅ APROVAÇÕES FINAIS

### Aprovação Técnica
- [ ] Tech Lead: _________________ Data: ___/___/_____
- [ ] Arquiteto: _________________ Data: ___/___/_____

### Aprovação de Negócio
- [ ] Product Owner: _____________ Data: ___/___/_____
- [ ] Stakeholder: ______________ Data: ___/___/_____

---

## 📞 CONTATOS E SUPORTE

**Desenvolvedor Responsável:** _________________  
**Email:** _________________  
**Slack/Discord:** _________________

**Documentação Completa:**
- PLANO_REFATORACAO_OMR_ROBUSTO.md
- ANALISE_CODIGO_ATUAL_OMR.md
- ESPECIFICACAO_JSON_TOPOLOGIA.md
- GUIA_VISUAL_PIPELINE_OMR.md
- CHECKLIST_IMPLEMENTACAO_OMR.md (este arquivo)

---

**PARABÉNS! 🎉**

Se você chegou até aqui e marcou todos os itens, você implementou com sucesso um pipeline OMR robusto, determinístico e de alto desempenho!

---

**Versão:** 1.0  
**Última Atualização:** 21 de Janeiro de 2026  
**Status:** 🟢 PRONTO PARA USO
