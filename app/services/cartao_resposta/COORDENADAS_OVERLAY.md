# Coordenadas do Overlay - Cartão Resposta (answer_sheet.html)

**IMPORTANTE:** Este documento define as coordenadas EXATAS para o overlay PDF.
**NÃO ALTERAR O TEMPLATE HTML/CSS!** Apenas ajustar coordenadas do overlay se necessário.

---

## 1. Referência de Página

- **A4:** 595.28 pt × 841.89 pt (ou 595 × 842 para simplificar)
- **Origem ReportLab:** Canto **inferior esquerdo** da página
- **Origem CSS/WeasyPrint:** Canto **superior esquerdo** da página
- **Conversão:** `y_pdf = 841.89 - y_css - height`

---

## 2. Estrutura do Template (answer_sheet.html)

### CSS Relevante (NÃO ALTERAR):

```css
@page { margin: 0; }
.answer-sheet { 
    padding: 1.2cm 2cm 2.2cm 2cm;  /* top right bottom left */
    width: 21cm; 
    height: 29.7cm; 
}
.answer-sheet-header { 
    height: 6.4cm; 
    border: 1px solid #000; 
    padding: 4px; 
}
.header-info-line { 
    font-size: 7pt; 
    margin: 0.5px 0; 
}
.header-info-line .label { 
    min-width: 100px;  /* Define onde termina o label */
}
.qr-code-box { 
    width: 120px; 
    height: 120px; 
}
```

### Conversões:
- 1.2cm = 34.02 pt
- 2cm = 56.69 pt
- 4px = 3 pt
- 1px = 0.75 pt
- 100px = 75 pt
- 120px = 90 pt

---

## 3. Cálculo das Coordenadas

### Área Útil (dentro do padding):
- **x_min** = 2cm = 56.69 pt (left padding)
- **y_top** = 1.2cm = 34.02 pt (top padding, origem CSS)

### Header (border + padding):
- Border: 1px = 0.75 pt
- Padding: 4px = 3 pt
- **Conteúdo começa em:**
  - x = 56.69 + 0.75 + 3 = **60.44 pt**
  - y_top = 34.02 + 0.75 + 3 = **37.77 pt**

### Linhas de Texto (.header-info-line):

**Estrutura HTML:**
1. NOME DA PROVA (dentro de .test-name-section)
2. **NOME COMPLETO** ← OVERLAY
3. ESTADO (estático)
4. MUNICÍPIO (estático)
5. **ESCOLA** ← OVERLAY
6. **TURMA** ← OVERLAY

**Cálculo Y (fluxo CSS normal):**
- Linha 1 (NOME DA PROVA): border-top + padding-top + margin ≈ 6.75 pt
  - Baseline ≈ 37.77 + 6.75 + 7 = **51.52 pt** (do topo)
- Linha 2 (NOME COMPLETO): + line-height (7pt) + margin (0.75pt) ≈ 7.75 pt
  - Baseline ≈ 51.52 + 7.75 + 7 = **66.27 pt** (do topo)
- Linha 3 (ESTADO): + 7.75 pt
  - Baseline ≈ 66.27 + 7.75 + 7 = **81.02 pt** (do topo)
- Linha 4 (MUNICÍPIO): + 7.75 pt
  - Baseline ≈ 81.02 + 7.75 + 7 = **95.77 pt** (do topo)
- Linha 5 (ESCOLA): + 7.75 pt
  - Baseline ≈ 95.77 + 7.75 + 7 = **110.52 pt** (do topo)
- Linha 6 (TURMA): + 7.75 pt
  - Baseline ≈ 110.52 + 7.75 + 7 = **125.27 pt** (do topo)

**Conversão para ReportLab (y_pdf = 841.89 - y_css):**
- NOME COMPLETO: 841.89 - 66.27 = **775.62 pt**
- ESCOLA: 841.89 - 110.52 = **731.37 pt**
- TURMA: 841.89 - 125.27 = **716.62 pt**

**Posição X dos valores:**
- Label width: min-width 100px = 75 pt
- **X_TEXT** = 60.44 + 75 = **135.44 pt**

### QR Code (.qr-code-box):

**Estrutura:**
- `.header-right`: width 140px = 105 pt, margin-left 10px = 7.5 pt, border-left 1px = 0.75 pt
- Início do `.header-right` (da esquerda da página):
  - x = 56.69 (left padding) + 481.95 (largura útil 17cm) - 105 (width) - 7.5 (margin) = **426.14 pt**
- `.qr-code-box`: 120px = 90 pt, centralizado em 140px
  - Offset horizontal: (140 - 120) / 2 = 10px = 7.5 pt
  - **QR_X** = 426.14 + 7.5 + 0.75 (border-left) = **434.39 pt**

**Posição Y:**
- Header height: 6.4cm = 181.44 pt
- QR centralizado verticalmente no header
- Centro do header (do topo): 37.77 + (181.44 - 7.5) / 2 ≈ **124.72 pt**
- QR box: 90 pt → metade = 45 pt
- Topo do QR: 124.72 - 45 = **79.72 pt** (do topo)
- **QR_Y** (ReportLab, inferior): 841.89 - 79.72 - 90 = **672.17 pt**

---

## 4. Coordenadas Finais para Overlay (ReportLab)

**VALIDADAS: Coordenadas idênticas às provas físicas (testadas e funcionando)**

```python
# Coordenadas em pontos PDF (origem inferior esquerda)
X_TEXT = 135.44          # Início dos valores (após labels)
Y_PDF_NAME = 780.16      # Baseline do NOME COMPLETO (linha 2)
Y_PDF_SCHOOL = 744.31    # Baseline da ESCOLA (linha 5, após ESTADO e MUNICÍPIO)
Y_PDF_TURMA = 732.36     # Baseline da TURMA (linha 6, 1 linha abaixo de ESCOLA)

QR_X = 441.46            # Posição X do QR code (canto inferior esquerdo)
QR_Y = 680.77            # Posição Y do QR code (canto inferior esquerdo)
QR_SIZE = 90             # Tamanho do QR code (90pt = 120px)

FONT_NAME = 'Helvetica'
FONT_SIZE = 7            # 7pt (mesmo do CSS)
MAX_TEXT_WIDTH = 268     # Largura máxima para não invadir QR
```

**Fonte:** Coordenadas validadas em `app/services/institutional_test_weasyprint_generator.py` (provas físicas)

---

## 5. Campos Variáveis do Overlay

| Campo | Origem | Transformação | Posição |
|-------|--------|---------------|---------|
| **NOME COMPLETO** | `student.name` ou `student.nome` | `.upper()` | (135.44, 775.62) |
| **ESCOLA** | `student.school_name` | `.upper()` | (135.44, 731.37) |
| **TURMA** | `test_data.grade_name` + `student.class_name` | `.upper()`, formato: "SÉRIE - TURMA" | (135.44, 716.62) |
| **QR CODE** | Gerado com `student_id`, `test_id`, `gabarito_id` | Base64 → Image | (434.39, 672.17) |

---

## 6. Validação

**CRÍTICO:** Após implementar, validar visualmente:

1. Gerar 1 cartão com overlay
2. Imprimir ou visualizar em 100%
3. Verificar alinhamento:
   - Textos devem aparecer **imediatamente após os labels**
   - QR code deve estar **centralizado na caixa**
   - Nenhum texto deve **invadir a área do QR**

**Se desalinhado:** Ajustar APENAS as coordenadas neste arquivo, NÃO o template HTML!

---

## 7. Observações Técnicas

- **Font:** Helvetica 7pt (padrão ReportLab, compatível com CSS)
- **Color:** #374151 (mesmo do CSS)
- **Truncamento:** Limitar texto a 50 caracteres (~268pt) para não invadir QR
- **Upper case:** Aplicar `.upper()` em todos os textos (padrão do template)
- **QR Code:** Gerar com `qrcode` library, converter para ImageReader do ReportLab
- **Merge:** Usar `pypdf` (PdfReader/PdfWriter) para mesclar base + overlay

---

**Data:** 2026-03-19
**Autor:** Sistema de Overlay - Cartões Resposta
**Status:** Coordenadas calculadas, aguardando validação prática
