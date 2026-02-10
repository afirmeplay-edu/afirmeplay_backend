# 🎯 Script de Calibração Visual de Grid OMR

## 📋 Objetivo

Script **não-interativo** para ajustar empiricamente as constantes do pipeline OMR até que os círculos calculados alinhem perfeitamente com as bolhas reais do template.

---

## 🚀 Como Usar

### 1️⃣ Preparar

Tenha em mãos:
- ✅ Uma imagem de teste (escaneada ou foto)
- ✅ O `gabarito_id` (UUID) correspondente

### 2️⃣ Executar pela primeira vez

```bash
python scripts/calibrate_grid_visual.py \
    --image path/to/test_image.jpg \
    --gabarito_id 96a02fc0-1234-5678-abcd-1234567890ab
```

### 3️⃣ Verificar as imagens geradas

Vá para a pasta `calibration_output/`:

- `01_original.jpg` - Imagem original
- `02_normalized_a4.jpg` - Imagem normalizada
- `block1_calibrated.jpg` - Bloco 1 com grid sobreposto
- `block2_calibrated.jpg` - Bloco 2 com grid sobreposto
- `block3_calibrated.jpg` - Bloco 3 com grid sobreposto
- `block4_calibrated.jpg` - Bloco 4 com grid sobreposto

### 4️⃣ Analisar o alinhamento

Nas imagens `blockX_calibrated.jpg`:

**✅ Alinhamento correto:**
- Linhas amarelas horizontais passam **entre** as linhas de questões
- Círculos verdes **cobrem exatamente** as bolhas roxas
- Centros vermelhos ficam no **centro** das bolhas

**❌ Desalinhado:**
- Linhas amarelas cortam as bolhas
- Círculos verdes pequenos demais ou grandes demais
- Círculos deslocados para esquerda/direita/cima/baixo

### 5️⃣ Ajustar constantes

Edite o arquivo `scripts/calibrate_grid_visual.py` no topo:

```python
# ============================================================================
# 🎯 CONSTANTES DE CALIBRAÇÃO - AJUSTE AQUI!
# ============================================================================

# Testes incrementais (ajuste esses valores)
TEST_ROW_HEIGHT_OFFSET = 0   # Ex: +2 se linhas muito juntas, -2 se muito separadas
TEST_RADIUS_OFFSET = 0       # Ex: +5 se círculos pequenos, -5 se grandes
TEST_OFFSET_X_ADJUST = 0     # Ex: +10 se círculos à esquerda das bolhas
TEST_OFFSET_Y_ADJUST = 0     # Ex: +5 se círculos acima das bolhas
```

**Exemplos de ajustes:**

| Problema | Ajuste |
|----------|--------|
| Círculos **pequenos demais** | `TEST_RADIUS_OFFSET = +5` |
| Círculos **grandes demais** | `TEST_RADIUS_OFFSET = -5` |
| Círculos **à esquerda** das bolhas | `TEST_OFFSET_X_ADJUST = +10` |
| Círculos **à direita** das bolhas | `TEST_OFFSET_X_ADJUST = -10` |
| Círculos **acima** das bolhas | `TEST_OFFSET_Y_ADJUST = +5` |
| Círculos **abaixo** das bolhas | `TEST_OFFSET_Y_ADJUST = -5` |
| Linhas **muito juntas** | `TEST_ROW_HEIGHT_OFFSET = +2` |
| Linhas **muito separadas** | `TEST_ROW_HEIGHT_OFFSET = -2` |

### 6️⃣ Executar novamente

```bash
python scripts/calibrate_grid_visual.py \
    --image path/to/test_image.jpg \
    --gabarito_id 96a02fc0-1234-5678-abcd-1234567890ab
```

### 7️⃣ Repetir até alinhar perfeitamente

Continue ajustando e testando até que os círculos verdes cubram **exatamente** as bolhas roxas!

### 8️⃣ Copiar valores finais

Quando estiver perfeito, copie os valores finais para `correction_new_grid.py`:

```python
# No arquivo: app/services/cartao_resposta/correction_new_grid.py

# Valores calibrados empiricamente
ROW_HEIGHT_PX = 51.97 + TEST_ROW_HEIGHT_OFFSET  # Ex: 53.97
BUBBLE_RADIUS_PX = 25 + TEST_RADIUS_OFFSET       # Ex: 30
BLOCK_OFFSET_X = 31 + TEST_OFFSET_X_ADJUST       # Ex: 41
BLOCK_OFFSET_Y = 10 + TEST_OFFSET_Y_ADJUST       # Ex: 15
```

---

## 📊 Saída do Script

```
================================================================================
🎯 CALIBRADOR VISUAL DE GRID OMR
================================================================================
📐 Parâmetros atuais:
   Row height: 51.97px
   Bubble radius: 25px
   Bubble gap: 4px
   Offset X: 31px
   Offset Y: 10px
📁 Output: calibration_output
================================================================================
✅ Imagem carregada: (848, 600, 3)
✅ 4 âncoras A4 detectadas
✅ Imagem normalizada: (3508, 2480, 3)
✅ 4 blocos detectados
✅ Topologia carregada: 4 blocos
💾 Salvo: calibration_output/20260121_174500_01_original.jpg
💾 Salvo: calibration_output/20260121_174500_02_normalized_a4.jpg

📦 BLOCO 1: 11 questões
   Dimensões: 446x1342px
💾 Salvo: calibration_output/20260121_174500_block1_calibrated.jpg

📦 BLOCO 2: 11 questões
   Dimensões: 446x1342px
💾 Salvo: calibration_output/20260121_174500_block2_calibrated.jpg

📦 BLOCO 3: 11 questões
   Dimensões: 446x1342px
💾 Salvo: calibration_output/20260121_174500_block3_calibrated.jpg

📦 BLOCO 4: 11 questões
   Dimensões: 446x1342px
💾 Salvo: calibration_output/20260121_174500_block4_calibrated.jpg

================================================================================
✅ CALIBRAÇÃO CONCLUÍDA!
================================================================================
📁 Imagens salvas em: calibration_output

🎯 PRÓXIMOS PASSOS:
1. Abra as imagens block*_calibrated.jpg
2. Verifique se os círculos verdes cobrem as bolhas roxas
3. Ajuste as constantes no topo deste script:
   - TEST_ROW_HEIGHT_OFFSET = 0
   - TEST_RADIUS_OFFSET = 0
   - TEST_OFFSET_X_ADJUST = 0
   - TEST_OFFSET_Y_ADJUST = 0
4. Execute novamente até alinhar perfeitamente
5. Copie os valores finais para correction_new_grid.py
================================================================================
```

---

## 🔧 Opções Avançadas

### Especificar diretório de saída

```bash
python scripts/calibrate_grid_visual.py \
    --image test.jpg \
    --gabarito_id UUID \
    --output custom_output_folder
```

---

## 💡 Dicas

1. **Comece com raio**: Ajuste `TEST_RADIUS_OFFSET` primeiro até os círculos cobrirem as bolhas
2. **Depois offsets**: Ajuste `TEST_OFFSET_X_ADJUST` e `TEST_OFFSET_Y_ADJUST` para centralizar
3. **Por último altura**: Ajuste `TEST_ROW_HEIGHT_OFFSET` se as linhas não estiverem alinhadas
4. **Teste múltiplas imagens**: Use imagens diferentes para garantir que funciona universalmente

---

## ⚠️ Troubleshooting

### "Apenas X âncoras detectadas"
- A imagem não tem os 4 quadrados pretos nos cantos
- Tente com outra imagem

### "Blocos detectados != topologia"
- A detecção de blocos falhou
- Verifique se a imagem está boa (não borrada, boa iluminação)

### "Gabarito não encontrado"
- Verifique se o `gabarito_id` está correto
- Verifique se o gabarito existe no banco

---

## 📝 Notas

- Este script é **não-interativo** - você ajusta as constantes no código e executa novamente
- As imagens são salvas com timestamp para não sobrescrever tentativas anteriores
- O script usa uma versão simplificada do pipeline OMR para focar na visualização

---

## 🎯 Objetivo Final

Encontrar os valores **empiricamente** que fazem os círculos calculados alinharem **perfeitamente** com as bolhas reais, considerando que:
- CSS pixels ≠ DPI pixels
- A normalização A4 pode introduzir pequenas distorções
- Padding, bordas e margens do template afetam as coordenadas

Uma vez calibrado, esses valores funcionarão para **todas** as imagens do mesmo template!
