# Sistema de Overlay para Cartões Resposta - Architecture 4

## 📋 Resumo

Implementação do sistema de **Template Base + Overlay** para geração de cartões resposta, seguindo o padrão Architecture 4 já utilizado nas provas físicas.

**Status:** ✅ Implementado e pronto para testes

---

## 🎯 Objetivo

Otimizar a geração de cartões resposta reduzindo drasticamente o uso de WeasyPrint:

- **ANTES:** WeasyPrint roda N× (uma vez por aluno) → Lento e pesado
- **DEPOIS:** WeasyPrint roda 1× (template base) + overlay ReportLab por aluno → Rápido e eficiente

---

## 🏗️ Arquitetura

### Architecture 4: Template Base + Overlay

```
┌─────────────────────────────────────────────────────────────┐
│ 1. TEMPLATE BASE (1× WeasyPrint)                           │
│    - Gera PDF com layout completo mas dados vazios         │
│    - Quadrados de alinhamento, grid de respostas, etc.     │
│    - Labels fixos (NOME COMPLETO:, ESCOLA:, TURMA:)        │
│    - QR code placeholder                                    │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. OVERLAY POR ALUNO (ReportLab - rápido)                  │
│    - Nome do aluno                                          │
│    - Escola                                                 │
│    - Turma (série + turma)                                  │
│    - QR code personalizado                                  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. MERGE (pypdf)                                            │
│    - Base + Overlay = Cartão final                          │
│    - Repetir para cada aluno                                │
└─────────────────────────────────────────────────────────────┘
```

---

## 📁 Arquivos Modificados/Criados

### Novos Arquivos:
1. **`COORDENADAS_OVERLAY.md`** - Documentação técnica das coordenadas do overlay
2. **`README_OVERLAY.md`** - Este arquivo (documentação geral)

### Arquivos Modificados:
1. **`answer_sheet_generator.py`**
   - Adicionado import `pypdf` (PdfReader, PdfWriter)
   - Novo método: `generate_answer_sheets_arch4()` - Implementação Architecture 4
   - Novo método: `_generate_student_overlay_pdf()` - Gera overlay com ReportLab
   - Novo método: `_get_placeholder_qr_base64()` - QR placeholder para template base
   - Modificado: `generate_answer_sheets()` - Agora usa arch4 por padrão (parâmetro `use_arch4=True`)

---

## 🔧 Como Usar

### Uso Padrão (Architecture 4 - Recomendado):

```python
from app.services.cartao_resposta.answer_sheet_generator import AnswerSheetGenerator

generator = AnswerSheetGenerator()

result = generator.generate_answer_sheets(
    class_id='uuid-da-turma',
    test_data={'title': 'Prova de Matemática', ...},
    num_questions=30,
    use_blocks=True,
    blocks_config={...},
    correct_answers={1: 'A', 2: 'B', ...},
    gabarito_id='uuid-do-gabarito',
    questions_options={1: ['A', 'B', 'C'], ...},
    output_dir='/tmp/cartoes',
    use_arch4=True  # ← PADRÃO: usa overlay (rápido)
)
```

### Fallback (Método Antigo):

```python
result = generator.generate_answer_sheets(
    # ... mesmos parâmetros ...
    use_arch4=False  # ← Usa método antigo (WeasyPrint por aluno)
)
```

---

## 📐 Coordenadas do Overlay

As coordenadas são **FIXAS** e derivadas do layout do template `answer_sheet.html`.

**IMPORTANTE:** NÃO alterar o template HTML/CSS! Apenas ajustar coordenadas se necessário.

### Coordenadas Atuais (ReportLab - origem inferior esquerda):

```python
X_TEXT = 135.44          # Início dos valores (após labels)
Y_PDF_NAME = 775.62      # Baseline do NOME COMPLETO
Y_PDF_SCHOOL = 731.37    # Baseline da ESCOLA
Y_PDF_TURMA = 716.62     # Baseline da TURMA

QR_X = 434.39            # Posição X do QR code
QR_Y = 672.17            # Posição Y do QR code
QR_SIZE = 90             # Tamanho do QR code (90pt = 120px)

FONT_NAME = 'Helvetica'
FONT_SIZE = 7            # 7pt (mesmo do CSS)
```

Ver documentação completa em: **`COORDENADAS_OVERLAY.md`**

---

## ✅ Validação e Testes

### Checklist de Validação:

1. ✅ **Compilação:** Código sem erros de sintaxe
2. ⏳ **Geração:** Testar geração de 1 cartão
3. ⏳ **Alinhamento:** Verificar posicionamento dos textos e QR code
4. ⏳ **Múltiplos alunos:** Testar com turma completa
5. ⏳ **Performance:** Comparar tempo de geração (arch4 vs antigo)
6. ⏳ **Correção:** Validar que não quebrou o sistema de correção

### Como Testar:

```python
# 1. Gerar 1 cartão de teste
result = generator.generate_answer_sheets(
    class_id='uuid-turma-teste',
    # ... parâmetros ...
    use_arch4=True
)

# 2. Abrir PDF gerado
# result['pdf_path'] = '/tmp/celery_pdfs/answer_sheets/cartoes_turma_X.pdf'

# 3. Verificar visualmente:
#    - Textos aparecem após os labels?
#    - QR code está centralizado na caixa?
#    - Nada está desalinhado?
```

### Ajuste de Coordenadas (se necessário):

Se o alinhamento estiver incorreto:

1. **NÃO ALTERAR** o template HTML/CSS
2. Ajustar apenas as coordenadas em `answer_sheet_generator.py` (método `_generate_student_overlay_pdf`)
3. Documentar mudanças em `COORDENADAS_OVERLAY.md`
4. Testar novamente

---

## 📊 Benefícios Esperados

### Performance:
- **WeasyPrint:** 1× ao invés de N×
- **Tempo de geração:** ~10-50× mais rápido para turmas grandes
- **Memória:** Redução drástica de uso de RAM

### Exemplo (turma com 30 alunos):
- **Antes:** 30× WeasyPrint = ~30-60 segundos
- **Depois:** 1× WeasyPrint + 30× overlay = ~2-5 segundos

### Consistência:
- Layout idêntico para todos os alunos
- Overlay garante posicionamento exato
- Facilita manutenção (1 template base)

---

## 🔍 Detalhes Técnicos

### Template Base (Dados Vazios):

```python
placeholder_student = {
    'id': '',
    'name': '',
    'nome': '',
    'school_name': '',
    'class_name': '',
    'grade_name': '',
    'qr_code': '<qr_placeholder_base64>'
}
```

### Overlay (ReportLab):

```python
# Textos
c.setFont('Helvetica', 7)
c.setFillColor(HexColor('#374151'))
c.drawString(X_TEXT, Y_PDF_NAME, student_name.upper())
c.drawString(X_TEXT, Y_PDF_SCHOOL, school_name.upper())
c.drawString(X_TEXT, Y_PDF_TURMA, turma_display.upper())

# QR Code
qr_image_reader = ImageReader(qr_buffer)
c.drawImage(qr_image_reader, QR_X, QR_Y, width=QR_SIZE, height=QR_SIZE)
```

### Merge (pypdf):

```python
from pypdf import PdfReader, PdfWriter

# Clonar página base
base_page = base_reader.pages[0]

# Aplicar overlay
overlay_reader = PdfReader(io.BytesIO(overlay_bytes))
base_page.merge_page(overlay_reader.pages[0])

# Adicionar ao writer
writer.add_page(base_page)
```

---

## ⚠️ IMPORTANTE: Não Quebrar Correção

**CRÍTICO:** O sistema de correção OMR depende das coordenadas dos elementos do cartão.

### Garantias de Compatibilidade:

1. ✅ **Template HTML/CSS:** NÃO foi alterado
2. ✅ **Layout das bolhas:** Permanece idêntico
3. ✅ **Quadrados de alinhamento:** Posições fixas
4. ✅ **Triângulos fiduciais:** Posições fixas
5. ✅ **Grid de respostas:** Estrutura inalterada

### O Que Mudou:

- ✅ **Apenas os textos variáveis:** Nome, Escola, Turma, QR code
- ✅ **Método de inserção:** Antes via HTML, agora via overlay PDF
- ✅ **Posição final:** Idêntica (coordenadas calculadas do CSS)

**Resultado:** O sistema de correção **NÃO deve ser afetado**.

---

## 🚀 Próximos Passos

1. ✅ **Implementação:** Concluída
2. ⏳ **Testes unitários:** Validar geração de PDFs
3. ⏳ **Testes de integração:** Validar com sistema de correção
4. ⏳ **Ajuste de coordenadas:** Se necessário após testes visuais
5. ⏳ **Deploy:** Substituir método antigo por arch4 em produção

---

## 📞 Suporte

Em caso de problemas:

1. Verificar logs: `[GENERATOR ARCH4]` e `[GENERATOR]`
2. Validar coordenadas em `COORDENADAS_OVERLAY.md`
3. Testar com `use_arch4=False` (fallback para método antigo)
4. Verificar se pypdf está instalado: `pip list | grep pypdf`

---

**Data:** 2026-03-19  
**Versão:** 1.0  
**Status:** ✅ Implementado, aguardando testes
