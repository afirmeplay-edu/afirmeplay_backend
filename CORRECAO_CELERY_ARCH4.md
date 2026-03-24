# ✅ Correção: Celery Usando Architecture 4 (Overlay)

**Data:** 2026-03-19  
**Problema:** Celery estava gerando cartões com WeasyPrint por aluno (método antigo)  
**Solução:** Adicionar `use_arch4=True` explicitamente nas tasks

---

## 🔍 Problema Identificado

### Sintomas:
- Geração de 27 alunos levou **289 segundos** (~10.7s por aluno)
- Logs do WeasyPrint processando fontes repetidamente
- Nenhum log `[GENERATOR ARCH4]` aparecendo

### Causa Raiz:
As tasks do Celery **não estavam passando** o parâmetro `use_arch4=True` explicitamente, e por algum motivo (cache de bytecode ou import cache) o valor padrão não estava sendo respeitado.

---

## ✅ Correção Aplicada

### Arquivo: `app/services/celery_tasks/answer_sheet_tasks.py`

**3 locais corrigidos:**

### 1. Task `generate_answer_sheet_for_class_task` (Linha ~219)

**ANTES:**
```python
result = generator.generate_answer_sheets(
    class_id=class_id,
    num_questions=num_questions,
    correct_answers=correct_answers,
    test_data=test_data,
    use_blocks=use_blocks,
    blocks_config=blocks_config,
    questions_options=questions_options,
    gabarito_id=gabarito_id
)
```

**DEPOIS:**
```python
result = generator.generate_answer_sheets(
    class_id=class_id,
    num_questions=num_questions,
    correct_answers=correct_answers,
    test_data=test_data,
    use_blocks=use_blocks,
    blocks_config=blocks_config,
    questions_options=questions_options,
    gabarito_id=gabarito_id,
    use_arch4=True  # ✅ Architecture 4: Template Base + Overlay (10-50× mais rápido)
)
```

---

### 2. Task `generate_answer_sheets_batch_task` - Gabarito Master (Linha ~364)

**ANTES:**
```python
pdf_result = generator.generate_answer_sheets(
    class_id=str(class_obj.id),
    test_data=test_data,
    num_questions=num_questions,
    use_blocks=use_blocks,
    blocks_config=blocks_config,
    correct_answers=correct_answers,
    gabarito_id=str(gabarito_master.id),
    questions_options=questions_options,
    output_dir=output_dir
)
```

**DEPOIS:**
```python
pdf_result = generator.generate_answer_sheets(
    class_id=str(class_obj.id),
    test_data=test_data,
    num_questions=num_questions,
    use_blocks=use_blocks,
    blocks_config=blocks_config,
    correct_answers=correct_answers,
    gabarito_id=str(gabarito_master.id),
    questions_options=questions_options,
    output_dir=output_dir,
    use_arch4=True  # ✅ Architecture 4: Template Base + Overlay (10-50× mais rápido)
)
```

---

### 3. Task `generate_answer_sheets_batch_task` - Gabaritos por Turma (Linha ~431)

**ANTES:**
```python
pdf_result = generator.generate_answer_sheets(
    class_id=str(gabarito.class_id),
    test_data=test_data,
    num_questions=num_questions,
    use_blocks=use_blocks,
    blocks_config=blocks_config,
    correct_answers=correct_answers,
    gabarito_id=str(gabarito.id),
    questions_options=questions_options,
    output_dir=output_dir
)
```

**DEPOIS:**
```python
pdf_result = generator.generate_answer_sheets(
    class_id=str(gabarito.class_id),
    test_data=test_data,
    num_questions=num_questions,
    use_blocks=use_blocks,
    blocks_config=blocks_config,
    correct_answers=correct_answers,
    gabarito_id=str(gabarito.id),
    questions_options=questions_options,
    output_dir=output_dir,
    use_arch4=True  # ✅ Architecture 4: Template Base + Overlay (10-50× mais rápido)
)
```

---

## 🚀 Resultado Esperado

### Performance Antes (Método Antigo):
- **27 alunos:** 289 segundos (~10.7s por aluno)
- **WeasyPrint:** 27× (uma vez por aluno)

### Performance Depois (Architecture 4):
- **27 alunos:** ~15-30 segundos (~0.5-1s por aluno)
- **WeasyPrint:** 1× (template base) + overlay ReportLab × 27
- **Ganho:** 10-20× mais rápido

---

## ✅ Validação

### Como Validar se Está Funcionando:

1. **Reiniciar Celery:**
   ```bash
   # Matar processos
   pkill -9 -f celery
   
   # Limpar cache (opcional mas recomendado)
   find . -type d -name __pycache__ -exec rm -rf {} +
   find . -name "*.pyc" -delete
   
   # Iniciar novamente
   celery -A app.report_analysis.celery_app worker --loglevel=info --concurrency=4 --prefetch-multiplier=1
   ```

2. **Gerar cartões de teste**

3. **Verificar logs:**
   ```
   ✅ Deve aparecer:
   [GENERATOR ARCH4] Turma: A (ID: uuid)
   [GENERATOR ARCH4] Estudantes encontrados: 27
   [GENERATOR ARCH4] Gerando template base com WeasyPrint...
   [GENERATOR ARCH4] ✅ Template base gerado (123456 bytes)
   [GENERATOR ARCH4] Gerando overlays para 27 alunos...
   [GENERATOR ARCH4] Processados 10/27 alunos
   [GENERATOR ARCH4] ✅ PDF gerado: cartoes_turma_A.pdf (654321 bytes, 27 páginas)
   ```

4. **Verificar tempo:**
   - Deve ser **10-20× mais rápido** que antes
   - 27 alunos: ~15-30 segundos (ao invés de 289s)

---

## 📊 Comparação

| Métrica | Antes (Antigo) | Depois (Arch4) | Ganho |
|---------|----------------|----------------|-------|
| **Tempo (27 alunos)** | 289s (~4min 49s) | ~15-30s | 10-20× |
| **WeasyPrint** | 27× | 1× | 27× menos |
| **Memória** | Alta (27 PDFs completos) | Baixa (1 base + overlays) | ~70% menos |
| **Tempo/aluno** | 10.7s | 0.5-1s | 10-20× |

---

## 🔧 Próximos Passos

1. ✅ **Correção aplicada** - `use_arch4=True` adicionado
2. ⏳ **Reiniciar Celery** - Para carregar código novo
3. ⏳ **Testar geração** - Validar performance
4. ⏳ **Validar alinhamento** - Verificar se textos estão alinhados
5. ⏳ **Validar correção** - Testar se sistema OMR continua funcionando

---

## 📝 Notas Técnicas

### Por Que o Padrão Não Funcionou?

Mesmo com `use_arch4=True` como valor padrão no método, o Python pode ter:
- Cache de bytecode (`.pyc`) com versão antiga
- Import cache não recarregado
- Ordem de parâmetros causando conflito

**Solução:** Passar explicitamente elimina qualquer ambiguidade.

### Arquivos Modificados:
- ✅ `app/services/celery_tasks/answer_sheet_tasks.py` (3 locais)

### Arquivos Criados (Implementação Original):
- ✅ `app/services/cartao_resposta/answer_sheet_generator.py` (métodos arch4)
- ✅ `app/services/cartao_resposta/COORDENADAS_OVERLAY.md`
- ✅ `app/services/cartao_resposta/README_OVERLAY.md`
- ✅ `IMPLEMENTACAO_OVERLAY_CARTOES.md`

---

**Status:** ✅ Correção aplicada, aguardando reinício do Celery para validação
