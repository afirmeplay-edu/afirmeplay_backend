# Relatório técnico: coordenadas dos elementos variáveis do cartão-resposta (OMR)

Objetivo: coordenadas exatas para desenhar **nome do aluno**, **escola**, **turma** e **QR code** em um sistema de PDF overlay, sem alterar o layout atual.

---

## 1. Conversões e referência de página

- **A4:** 210 mm × 297 mm → **595.28 pt × 841.89 pt** (1 in = 72 pt, 1 in = 25.4 mm). Uso **595.28 × 841.89** como referência; em implementação pode-se usar 595 × 842.
- **1 cm = 28.35 pt** (72 / 2.54).
- **1 px = 0.75 pt** (96 DPI: 72/96).
- **Origem:** CSS/WeasyPrint = canto **superior esquerdo**. PDF (ex.: ReportLab) = **inferior esquerdo**. Todas as posições são dadas em “top-left” (y para baixo); para overlay em PDF, **y_pdf = 841.89 - y_css - height** (ou y_pdf = 841.89 - baseline para texto).

---

## 2. Estrutura da página e do cabeçalho

- **@page answer-sheet-omr:** `margin: 0`, `size: A4 portrait`.
- **.answer-sheet:** `width: 21cm`, `height: 29.7cm`, `padding: 1.2cm 2cm 2.2cm 2cm` (top, right, bottom, left).

Área útil (dentro do padding):

- **x_min = 2 cm = 56.70 pt**
- **y_min = 1.2 cm = 34.02 pt** (topo)
- **Largura útil = 17 cm = 481.95 pt**
- **Altura útil = 26.3 cm = 745.56 pt**

**.answer-sheet-header:**

- `height: 6.4cm` → **181.44 pt**
- `border: 1px`, `padding: 4px` (box-sizing: border-box)
- Ocupa de **y = 34.02 pt** a **y = 215.46 pt** (topo do header ao fim do header).
- Conteúdo interno do header: a partir de **y = 34.02 + 0.75 + 3 ≈ 37.77 pt** (considerando borda e padding).

**.header-right (área do QR):**

- `width: 140px` → **105 pt**
- `margin-left: 10px` → **7.5 pt**
- Início do bloco (esquerda): 56.7 + 481.95 - 105 - 7.5 = **426.15 pt** (a partir da esquerda da página).
- O bloco vai de **x = 426.15 pt** a **x = 531.15 pt**.

**.qr-code-box:**

- `width: 120px` → **90 pt**, `height: 120px` → **90 pt**
- `margin-bottom: 8px` → **6 pt**
- Dentro de .header-right com `align-items: center` → deslocamento horizontal (140−120)/2 = 10px = **7.5 pt**.
- **x (esquerda da caixa QR):** 426.15 + 7.5 = **433.65 pt**
- Centro vertical do header (conteúdo): 34.02 + 0.75 + 3 + (181.44 − 1.5 − 6)/2 ≈ **124.74 pt** (topo). Caixa de 90 pt centralizada → topo da caixa = 124.74 − 45 = **79.74 pt**.
- **y (topo da caixa QR):** **79.74 pt**
- **Base da caixa:** 79.74 + 90 = **169.74 pt**

**Dependência:** Número de questões e blocos **não** alteram o header nem a área do QR; posições do QR são **fixas**.

---

## 3. Textos no .header-left (nome, escola, turma)

Estrutura (ordem no HTML):

1. .test-name-section (NOME DA PROVA)
2. .header-info-line → **NOME COMPLETO** (`student.name` / `student.nome`)
3. .header-info-line → ESTADO
4. .header-info-line → MUNICÍPIO
5. .header-info-line → **ESCOLA** (`student.school_name`)
6. .header-info-line → **TURMA** (`test_data.grade_name` + `student.class_name`)

CSS relevante:

- `.header-info-line`: `font-size: 7pt`, `margin: 0.5px 0` (≈ 0.375 pt), `text-transform: uppercase`, `white-space: nowrap`.
- `.test-name-section`: `border-top: 1px`, `padding-top: 2px`, `margin-top/margin-bottom: 2px`.
- body: `font-family: Helvetica, Arial, sans-serif`.

Cálculo de X para os valores (texto após o label):

- Início do conteúdo do header (esquerda): 56.7 + 0.75 + 3 = **60.45 pt**.
- Coluna de labels (estimada): largura máxima dos labels em 7pt (ex.: "NOME DA PROVA:") ≈ **90 pt**.
- **Início da coluna "value" (X para nome, escola, turma):** 60.45 + 90 = **150.45 pt** (valor conservador; pode ser ~151 pt).
- **Largura máxima para o valor:** até o início do .header-right (com margem): 426.15 − 7.5 − 150.45 = **268.2 pt**.

Cálculo de Y (topo de cada linha, fluxo normal dentro do primeiro bloco):

- Topo do conteúdo do header: **37.77 pt**.
- test-name-section: + 0.75 + 2 + 2 + 2 ≈ **6.75 pt** → topo da 1ª linha ≈ **44.52 pt**.
- Cada .header-info-line com ~7 pt de fonte + 0.375×2 de margem → altura de linha ≈ **7.75–8 pt**.
- Topo das linhas (em pt, origem no topo):
  - Linha 1 (NOME DA PROVA): **44.52**
  - Linha 2 (**NOME COMPLETO**): **52.52**
  - Linha 3 (ESTADO): **60.52**
  - Linha 4 (MUNICÍPIO): **68.52**
  - Linha 5 (**ESCOLA**): **76.52**
  - Linha 6 (**TURMA**): **84.52**

Baseline de texto (aproximada, 7pt): **topo + 7 pt**.

**Dependência:** Essas Y são **fixas para esta estrutura de 6 linhas**. Não dependem de número de questões nem de blocos. Dependem apenas do flex do header (`.header-left` com `justify-content: space-between`); se o primeiro bloco tiver sempre as mesmas 6 linhas, as posições permanecem fixas; se no futuro mudar número de linhas ou espaçamento, as Y devem ser recalculadas.

---

## 4. Tabela de coordenadas para overlay (origem top-left, página A4)

| Elemento | X (pt) | Y (pt) | Largura (pt) | Altura (pt) | Fonte | Tamanho |
|----------|--------|--------|--------------|-------------|-------|---------|
| **QR_CODE** | 433.65 | 79.74 | 90 | 90 | — | — |
| **STUDENT_NAME** (NOME COMPLETO) | 150.45 | 52.52 (topo) / 59.52 (baseline) | 268.2 | ~8 | Helvetica | 7 pt |
| **SCHOOL** (ESCOLA) | 150.45 | 76.52 (topo) / 83.52 (baseline) | 268.2 | ~8 | Helvetica | 7 pt |
| **TURMA** (TURMA) | 150.45 | 84.52 (topo) / 91.52 (baseline) | 268.2 | ~8 | Helvetica | 7 pt |

- **QR_CODE:** posição e tamanho **fixos**; desenhar imagem 90×90 pt com canto superior esquerdo em (433.65, 79.74) em coordenadas "top-left". Para ReportLab (origem embaixo): **x = 433.65**, **y_pdf = 841.89 - 79.74 - 90 = 672.15** (canto inferior esquerdo da imagem).
- **Textos:** usar **baseline** para desenho em PDF. Em ReportLab, y para `drawString` é a baseline; **y_pdf = 841.89 - baseline**. Ex.: nome baseline 59.52 → **y_pdf = 782.37**; escola 83.52 → **y_pdf = 758.37**; turma 91.52 → **y_pdf = 750.37**.

---

## 5. Resumo em pontos PDF (para uso direto em overlay)

- **QR_CODE (imagem 90×90 pt):**
  - Top-left (CSS): x = **433.65**, y_top = **79.74**.
  - ReportLab (bottom-left): x = **433.65**, y = **672.15**, width = **90**, height = **90**.

- **STUDENT_NAME:** x = **150.45**, baseline (top-left) = **59.52** → y_pdf = **782.37**, font = **Helvetica**, size = **7**.

- **SCHOOL:** x = **150.45**, baseline = **83.52** → y_pdf = **758.37**, font = **Helvetica**, size = **7**.

- **TURMA:** x = **150.45**, baseline = **91.52** → y_pdf = **750.37**, font = **Helvetica**, size = **7**.

Largura máxima útil para cada texto: **268.2 pt** (evitar sobrepor a área do QR).

---

## 6. Confirmação: fixo vs dinâmico

- **QR_CODE:** posição e tamanho **fixos**; não dependem de número de questões nem de blocos.
- **STUDENT_NAME, SCHOOL, TURMA:** X e a **diferença de Y entre linhas** são fixos para o layout atual (6 linhas no primeiro bloco do header). Não dependem de número de questões nem da grade de respostas. Dependem apenas da estrutura do cabeçalho (flex, mesma quantidade de linhas). Qualquer mudança futura no HTML/CSS do header pode exigir recalcular as Y.

---

## 7. Observações para implementação do overlay

- O projeto usa A4 a 96 DPI como **794 × 1123 px** em `pdf_generator.py`; em pontos continua 595.28 × 841.89. Use **595.28 × 841.89** (ou 595 × 842) no overlay para manter alinhamento com o PDF gerado pelo WeasyPrint.
- As Y dos textos foram obtidas por fluxo normal do primeiro bloco do header; `justify-content: space-between` no .header-left pode alterar levemente as posições reais. Recomenda-se **validar com um PDF de referência** (gerar um cartão pelo WeasyPrint e medir posições no PDF) antes de fixar os valores no overlay.
- Para **truncamento**: o CSS usa `text-overflow: ellipsis` e `overflow: hidden`; no overlay, limitar o texto à largura de **268 pt** (ou cortar/ajustar fonte) para não invadir a área do QR.
