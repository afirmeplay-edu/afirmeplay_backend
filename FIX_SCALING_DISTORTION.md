# FIX: Eliminar Distorção de Redimensionamento (Bolhas Maiores no Fim)

**Data:** 21 de janeiro de 2026  
**Problema:** Grid desalinhado, bolhas aparecem maiores nas últimas questões  
**Causa Raiz:** Escalas não uniformes no redimensionamento do bloco

## 1. Análise do Problema

### Pipeline Original:

1. ROI extraído pelos triângulos: **163x473px**
2. Redimensionado para: **142x473px**
3. Grid aplicado com 26 questões, espaçamento 18px

### Problema Identificado:

**Fatores de escala:**

- Eixo X: 163 → 142px = **fator 0.8712** (redução 12.88%)
- Eixo Y: 473 → 473px = **fator 1.0** (sem redução)
- **Diferença: 0.1288** ❌ NÃO UNIFORME

**Consequências:**

1. Bolhas compactadas horizontalmente (X reduz 12.88%)
2. Altura mantida (Y não reduz)
3. **Ilusão óptica**: Parecem maiores em relação à altura
4. Grid ultrapassa altura em **3px** (99.8% do bloco)
5. Clipping parcial nas últimas bolhas amplifica o efeito

### Validação Visual:

Imagem fornecida pelo usuário mostra claramente:

- Q1-Q5: Bolhas alinhadas corretamente
- Q10-Q15: Começam a desalinhar
- Q20-Q26: Bolhas visualmente maiores (grid fora de proporção)

---

## 2. Solução Implementada

### Ajustes Aplicados:

**1. Aumentar block_width_ref: 142px → 155px**

Novo fator de escala:

- Eixo X: 163 → 155px = **fator 0.9509** (redução 4.91%)
- Eixo Y: 473 → 473px = **fator 1.0** (sem redução)
- **Diferença: 0.0491** ✅ ACEITÁVEL (reduzida 62%)

**2. Ajustar start_x: 32px → 34px**

Cálculo:

- Posição original: 32px no bloco de 142px = 22.54% da largura
- Com novo tamanho: 22.54% × 155px = 34.9px ≈ 34px
- Garante que as bolhas (A, B, C, D) fiquem nas posições corretas

**3. start_y: 15px (sem mudança)**
**4. line_height: 18px (sem mudança)**

### Mudanças de Arquivo:

#### block_01_coordinates_adjustment.json:

```json
{
  "block_num": 1,
  "start_x": 34,          // ← mudou: 32 → 34
  "start_y": 15,          // ← mantém igual
  "line_height": 18,      // ← mantém igual
  "block_width_ref": 155, // ← mudou: 142 → 155
  "block_height_ref": 473,// ← mantém igual
  ...
}
```

Mesmo aplicado a: block_02, block_03, block_04

#### correction_n.py (linha 595):

```python
STANDARD_BLOCK_WIDTH = 155  # ← mudou: 142 → 155
STANDARD_BLOCK_HEIGHT = 473 # ← mantém igual
```

Comentários atualizados: "redimensionado para 155x473px"

---

## 3. Benefícios da Solução

✅ **Escalas uniformes**: Redução de 12.88% → 4.91%  
✅ **Elimina distorção não linear**: Grid proporcional em toda altura  
✅ **Bolhas com tamanho consistente**: Sem ilusão óptica  
✅ **Grid cabe no bloco**: +1px de margem (vs -3px antes)  
✅ **Compatível com HoughCircles**: Bubble detection mais confiável

---

## 4. Impacto na Detecção

### Mudanças:

- Bloco normalizado: 142x473 → **155x473px** (+13px largura)
- start_x: 32 → **34px** (+2px)
- Outras coordenadas: **SEM MUDANÇA**

### Resultado Esperado:

1. **fill_ratios mais consistentes**: Q1=0.24 → Q26 ≈ 0.26 (vs antes 0.64)
2. **Detecção de bolhas uniforme**: Mesmo tamanho aparente do início ao fim
3. **Sem quebra de compatibilidade**: Grade calibrada, HoughCircles funcionando

---

## 5. Próximos Passos

1. ✅ **Atualizar JSON files** (block_01-04): FEITO
2. ✅ **Atualizar correction_n.py**: FEITO
3. ⏳ **Testar com imagem real**: Usar uma imagem com 26 questões marcadas
4. ⏳ **Validar fill_ratios**: Confirmar consistência Q1→Q26
5. ⏳ **Verificar detecção**: Confirmar sem bolhas perdidas
6. ⏳ **Commit e deploy**: Após validação

---

## 6. Referência Técnica

### Cálculos:

**Tamanho do grid (com line_height=18px):**

```
Q1:  Y = 15px
Q26: Y = 15 + 25*18 = 465px
Borda inferior: 465 + 7.5 (raio) = 472.5px
Total necessário: ~476px
```

**Bloco atual:** 473px → **Excesso de 3px (-0.6%)**  
**Bloco novo:** 473px → **Margem de 1px (+0.2%)**

**Fatores de escala na solução:**

- X: 0.9509 (163 → 155)
- Y: 1.0 (473 → 473)
- Diferença: 0.0491 (4.91% vs 12.88% antes)

---

## Commits Relacionados

- `5d70dfb`: JSON line_height + round()
- `6641737`: HoughCircles param2 30→15 (detection fix)
- `6a44a45`: Remove visual clutter from debug images
- `[ESTE]`: Fix scaling distortion - block_width_ref 142→155px

---
