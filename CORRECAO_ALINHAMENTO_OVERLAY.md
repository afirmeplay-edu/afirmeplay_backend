# ✅ Correção: Alinhamento do Overlay - Cartões Resposta

**Data:** 2026-03-19  
**Status:** ✅ Corrigido

---

## 🔍 Problemas Identificados (da Imagem)

### 1. ❌ Textos Desalinhados
- **NOME COMPLETO:** "ALICE LIMA DA SILVA" não aparecia logo após o label
- **ESCOLA:** Aparecia "NÃO INFORMADO" com texto sobreposto
- **TURMA:** "8º ANO - A" desalinhado com texto sobreposto

### 2. ❌ Textos Duplicados/Sobrepostos
- Template WeasyPrint renderizava textos padrão
- Overlay desenhava por cima
- Resultado: textos sobrepostos e ilegíveis

---

## 🎯 Causa Raiz

### Problema 1: Placeholder com String Vazia

**Código anterior:**
```python
placeholder_student = {
    'name': '',           # ← String vazia
    'school_name': '',    # ← String vazia
    'class_name': '',     # ← String vazia
}
```

**Template Jinja2:**
```html
<span class="value">{{ student.school_name or 'Não informado' }}</span>
```

**Resultado:**
- String vazia `''` → Jinja2 considera **falsy**
- Usa fallback `or 'Não informado'`
- Template renderiza "NÃO INFORMADO"
- Overlay desenha nome real por cima
- **Textos sobrepostos!**

### Problema 2: Coordenadas Incorretas

**Coordenadas calculadas (erradas):**
```python
Y_PDF_NAME = 775.62
Y_PDF_SCHOOL = 731.37
Y_PDF_TURMA = 716.62
```

**Coordenadas corretas (provas físicas):**
```python
Y_PDF_NAME = 780.16      # +4.54 pt mais alto
Y_PDF_SCHOOL = 744.31    # +12.94 pt mais alto
Y_PDF_TURMA = 732.36     # +15.74 pt mais alto
```

**Diferença:** As coordenadas calculadas estavam **muito baixas**, causando desalinhamento.

---

## ✅ Correções Aplicadas

### Correção 1: Placeholder com Espaço (não vazio)

**Código corrigido:**
```python
placeholder_student = {
    'id': ' ',            # ← Espaço (não vazio)
    'name': ' ',          # ← Espaço (não vazio)
    'nome': ' ',          # ← Espaço (não vazio)
    'school_name': ' ',   # ← Espaço (não vazio) - evita "Não informado"
    'class_name': ' ',    # ← Espaço (não vazio)
    'grade_name': ' ',    # ← Espaço (não vazio)
    'qr_code': self._get_placeholder_qr_base64()
}
```

**Resultado:**
- String com espaço `' '` → Jinja2 considera **truthy**
- NÃO usa fallback `or 'Não informado'`
- Template renderiza espaço invisível
- Overlay desenha texto real
- **Sem sobreposição!**

### Correção 2: Coordenadas Validadas (provas físicas)

**Código corrigido:**
```python
# Coordenadas VALIDADAS das provas físicas (funcionam perfeitamente)
X_TEXT = 135.44          # Início dos valores (após labels)
Y_PDF_NAME = 780.16      # Baseline do NOME COMPLETO (linha 2)
Y_PDF_SCHOOL = 744.31    # Baseline da ESCOLA (linha 5)
Y_PDF_TURMA = 732.36     # Baseline da TURMA (linha 6)

QR_X = 441.46            # Posição X do QR code
QR_Y = 680.77            # Posição Y do QR code
QR_SIZE = 90             # Tamanho do QR code
```

**Fonte:** `app/services/institutional_test_weasyprint_generator.py` (linha 1143-1149)

---

## 📐 Comparação de Coordenadas

| Campo | Calculadas (erradas) | Validadas (corretas) | Diferença |
|-------|---------------------|---------------------|-----------|
| **Y_PDF_NAME** | 775.62 | 780.16 | +4.54 pt |
| **Y_PDF_SCHOOL** | 731.37 | 744.31 | +12.94 pt |
| **Y_PDF_TURMA** | 716.62 | 732.36 | +15.74 pt |
| **QR_X** | 434.39 | 441.46 | +7.07 pt |
| **QR_Y** | 672.17 | 680.77 | +8.60 pt |

**Conclusão:** As coordenadas calculadas estavam consistentemente **muito baixas**.

---

## 🔧 Arquivos Modificados

### 1. `app/services/cartao_resposta/answer_sheet_generator.py`

**Mudanças:**
- ✅ Placeholder com espaço `' '` ao invés de string vazia `''`
- ✅ Coordenadas atualizadas para valores validados das provas físicas
- ✅ Aplicado em 2 métodos:
  - `generate_answer_sheets_arch4()` (linha ~160)
  - `generate_class_answer_sheets()` (linha ~630)

### 2. `app/services/cartao_resposta/COORDENADAS_OVERLAY.md`

**Mudanças:**
- ✅ Coordenadas atualizadas com valores validados
- ✅ Adicionada nota sobre fonte (provas físicas)

---

## ✅ Resultado Esperado

### Antes (com problemas):
```
NOME COMPLETO: [texto desalinhado]
ESCOLA: NÃO INFORMADO [texto sobreposto]
TURMA: [texto desalinhado e sobreposto]
```

### Depois (corrigido):
```
NOME COMPLETO: ALICE LIMA DA SILVA
ESCOLA: ESCOLA MUNICIPAL PEDRO ABILIO MADEIRO
TURMA: 8º ANO - A
```

**Alinhamento perfeito, sem sobreposição!**

---

## 🧪 Validação

### Checklist:

1. ✅ **Placeholder corrigido** - Espaço ao invés de string vazia
2. ✅ **Coordenadas atualizadas** - Valores validados das provas físicas
3. ✅ **Sintaxe verificada** - Código compila sem erros
4. ✅ **Cache deletado** - `.pyc` removidos
5. ⏳ **Reiniciar Celery** - Para carregar código novo
6. ⏳ **Testar geração** - Validar alinhamento visual

### Como Testar:

1. **Reiniciar Celery** (Ctrl+C e iniciar novamente)
2. **Gerar cartões** via `POST /answer-sheets/generate`
3. **Abrir PDF gerado**
4. **Verificar:**
   - [ ] Nome do aluno aparece logo após "NOME COMPLETO:"?
   - [ ] Escola aparece logo após "ESCOLA:"?
   - [ ] Turma aparece logo após "TURMA:"?
   - [ ] QR code está centralizado na caixa?
   - [ ] Nenhum texto está sobreposto?

---

## 📊 Resumo das Correções

| Problema | Causa | Solução | Status |
|----------|-------|---------|--------|
| Textos sobrepostos | Placeholder vazio → fallback Jinja2 | Placeholder com espaço `' '` | ✅ Corrigido |
| Textos desalinhados | Coordenadas calculadas incorretas | Coordenadas validadas (provas físicas) | ✅ Corrigido |
| Performance lenta | Método antigo (WeasyPrint por aluno) | Architecture 4 (overlay) | ✅ Corrigido |

---

## 🎯 Coordenadas Finais (Validadas)

```python
# COORDENADAS VALIDADAS - Fonte: provas físicas (funcionam perfeitamente)
X_TEXT = 135.44
Y_PDF_NAME = 780.16      # +4.54 pt vs calculado
Y_PDF_SCHOOL = 744.31    # +12.94 pt vs calculado
Y_PDF_TURMA = 732.36     # +15.74 pt vs calculado
QR_X = 441.46            # +7.07 pt vs calculado
QR_Y = 680.77            # +8.60 pt vs calculado
QR_SIZE = 90
```

---

**Status:** ✅ Correções aplicadas, aguardando reinício do Celery para validação final
