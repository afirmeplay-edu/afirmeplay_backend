# Correção: Overlay na Capa da Prova Física

## Problema Identificado

Ao gerar PDFs de provas físicas, a **capa** estava exibindo dados hardcoded incorretos:
- **ESCOLA:** "E.M.E.B JOÃO PAULO II" (fallback hardcoded no template)
- **SÉRIE:** "5º Ano" (fallback hardcoded no template)
- **TURMA:** "5º A MATUTINO" (fallback hardcoded no template)

Enquanto o **cartão-resposta** (OMR) exibia os dados corretos de cada aluno através do overlay ReportLab.

## Causa do Problema

A arquitetura Arch4 foi otimizada para gerar:
1. **1× PDF base** (capa + questões) - compartilhado por todos os alunos
2. **1× Template OMR** - compartilhado por todos os alunos
3. **N× Overlays** - um por aluno (apenas no cartão-resposta)

O PDF base era gerado com um `base_student` vazio:
```python
base_student = {'school_name': '', 'class_name': '', 'name': ''}
```

Isso fazia o template HTML usar os valores de fallback hardcoded.

## Solução Implementada

**Carimbar (overlay) TANTO a capa QUANTO o cartão-resposta** por aluno.

### Vantagens
✅ Mantém a otimização Arch4 (1 PDF base para todos)
✅ Cada aluno recebe capa personalizada com sua escola/turma
✅ Funciona para qualquer número de escolas/turmas diferentes
✅ Performance máxima (1× WeasyPrint base + 2N× overlays leves)

### Mudanças Realizadas

#### 1. Template HTML (`institutional_test_hybrid.html`)

**Antes:**
```html
<div class="info-value">
    {{ student.school_name or test_data.institution or 'E.M.E.B JOÃO PAULO II' }}
</div>
```

**Depois:**
```html
<div class="info-value">
    {{ student.school_name or test_data.institution or '' }}
</div>
```

Removidos os fallbacks hardcoded de:
- ESCOLA: `'E.M.E.B JOÃO PAULO II'` → `''`
- SÉRIE: `'5º Ano'` → `''`
- TURMA: `'5º A MATUTINO'` → `''`

#### 2. Gerador WeasyPrint (`institutional_test_weasyprint_generator.py`)

**Novo método `_generate_cover_overlay_pdf`:**
- Gera PDF overlay com dados da capa (escola, série, turma)
- Usa mesma fonte, tamanho e cor do template (Helvetica 11pt, cor #1f2937)
- Posiciona texto nas coordenadas exatas calculadas a partir do CSS

**Coordenadas da Capa:**
```python
X_VALUE = 148.43pt   # Posição X dos valores (após labels)
Y_ESCOLA = 84.57pt   # Baseline ESCOLA
Y_SERIE = 111.51pt   # Baseline SÉRIE
Y_TURMA = 138.45pt   # Baseline TURMA

FONT_NAME = 'Helvetica'
FONT_SIZE = 11pt
FONT_COLOR = HexColor('#1f2937')
```

**Atualização do método `generate_institutional_test_pdf_arch4`:**
```python
# Gerar overlays (capa + cartão-resposta)
cover_overlay_bytes = self._generate_cover_overlay_pdf(student, test_data)
omr_overlay_bytes = self._generate_student_overlay_pdf(student, test_data)

# Aplicar overlay na página 1 (capa)
for page_num, page in enumerate(base_reader.pages):
    if page_num == 0:
        page.merge_page(cover_overlay_reader.pages[0])
    writer.add_page(page)

# Aplicar overlay na última página (cartão OMR)
writer.add_page(omr_page)
```

## Fluxo Final

```
1. Gerar PDF Base (1×):
   - Capa com campos vazios
   - Questões
   
2. Gerar Template OMR (1×):
   - Cartão-resposta com campos vazios

3. Por cada aluno:
   a) Gerar overlay da CAPA (escola, série, turma)
   b) Gerar overlay do CARTÃO-RESPOSTA (nome, escola, turma, QR)
   c) Aplicar overlay na página 1 (capa)
   d) Aplicar overlay na última página (cartão)
   e) Merge: base + overlays = PDF final personalizado
```

## Testes Necessários

1. Gerar prova com alunos de **múltiplas escolas**
2. Verificar se cada PDF tem escola/turma corretas na capa
3. Verificar alinhamento visual (texto deve ficar próximo aos labels)
4. Verificar que não há sobreposição de texto

## Observações Técnicas

- As coordenadas foram calculadas com base no CSS do template
- Pode ser necessário ajuste fino das coordenadas X/Y após teste visual
- O texto é convertido para MAIÚSCULAS para consistência com o design
- Truncamento aplicado para textos muito longos (55 caracteres)
- Fonte e cor idênticas ao template original (Helvetica 11pt, #1f2937)

## Próximos Passos

Se o alinhamento não ficar perfeito no primeiro teste, ajustar as coordenadas:
- `X_VALUE`: posição horizontal dos valores
- `Y_ESCOLA`, `Y_SERIE`, `Y_TURMA`: posições verticais de cada linha

As coordenadas podem ser refinadas medindo um PDF de referência gerado pelo WeasyPrint.
