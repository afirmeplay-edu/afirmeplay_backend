# Otimização: Gabarito Central para Provas Físicas

## 📋 Resumo

Este documento descreve a otimização implementada para **centralizar os dados de correção** das provas físicas, reduzindo drasticamente o tempo de geração e o espaço no banco de dados.

---

## 🎯 Problema Original

**Antes da otimização:**
- Para cada aluno (PhysicalTestForm), o sistema salvava:
  - `blocks_config` completo (topology com todos os blocos, questões e alternativas)
  - `correct_answers` completo (gabarito inteiro)
- **Resultado**: 500 alunos = 500× os mesmos dados pesados
- **Impacto**: Geração lenta + banco de dados inchado

---

## ✅ Solução Implementada (Fase 1)

### O que foi feito?

1. **Criado AnswerSheetGabarito Central** (1 por prova)
   - Salva `blocks_config`, `correct_answers`, `num_questions`, `use_blocks`
   - Todos os alunos referenciam este gabarito único

2. **QR Code Modificado**
   - Agora inclui `gabarito_id` além de `student_id` e `test_id`
   - Correção vai direto no gabarito central

3. **Correção Prioriza Gabarito Central**
   - Busca primeiro em `AnswerSheetGabarito`
   - Fallback em `PhysicalTestForm` (compatibilidade com provas antigas)

### Arquivos Modificados

- ✅ `app/physical_tests/tasks.py` (linhas 436-483)
- ✅ `app/services/institutional_test_weasyprint_generator.py` (linhas 559-570, 1091-1096, 1187-1207)
- ✅ `app/services/cartao_resposta/correction_new_grid.py` (linhas 1853-1887, 2373-2391)

### Status Atual

✅ **FUNCIONANDO E TESTADO**
- Gabarito central está sendo criado
- QR Code inclui `gabarito_id`
- Correção usa gabarito central
- **MAS**: Ainda salvando dados em `PhysicalTestForm` (redundância segura)

---

## 🚀 Próximos Passos (Fase 2)

### Objetivo: Parar de Salvar Dados Pesados em PhysicalTestForm

Depois de validar que tudo está funcionando perfeitamente (gerar várias provas, corrigir várias provas), você pode **remover a redundância** para ganhar ainda mais performance.

### O que fazer:

#### 1. Modificar `app/physical_tests/form_service.py`

**Localização**: Linhas 547-588 (método `_save_physical_forms_to_db`)

**Ação**: Comentar o salvamento de `blocks_config` e `correct_answers`

```python
# ✅ FASE 2: Não salvar mais dados pesados em PhysicalTestForm
# (dados estão centralizados em AnswerSheetGabarito)

if correction_data:
    # Salvar apenas dados leves (úteis para queries)
    physical_form.num_questions = correction_data.get('num_questions')
    physical_form.use_blocks = correction_data.get('use_blocks', False)
    
    # ❌ COMENTADO: Não salvar mais dados pesados
    # physical_form.blocks_config = correction_data.get('blocks_config')
    # physical_form.correct_answers = correction_data.get('correct_answers')
    
    logging.info(f"✅ Dados leves salvos em PhysicalTestForm (dados pesados estão em AnswerSheetGabarito)")
```

**Linhas específicas para comentar:**
- Linha 576: `physical_form.blocks_config = blocks_config_to_save`
- Linha 582: `physical_form.correct_answers = correction_data.get('correct_answers')`

#### 2. Testar Novamente

Depois de fazer a mudança:
1. Gere uma nova prova física
2. Verifique que `PhysicalTestForm.blocks_config` e `PhysicalTestForm.correct_answers` estão NULL
3. Corrija a prova e confirme que funciona
4. Verifique os logs: deve aparecer "✅ Gabarito encontrado em AnswerSheetGabarito (fonte central)"

---

## 🧹 Limpeza (Fase 3 - Opcional)

### Objetivo: Limpar Dados Antigos

Se quiser recuperar espaço no banco, você pode limpar os dados pesados de provas antigas.

### Script SQL para Limpeza

```sql
-- ⚠️ BACKUP ANTES DE EXECUTAR!
-- Este script limpa blocks_config e correct_answers de PhysicalTestForm
-- (os dados continuam disponíveis em AnswerSheetGabarito)

-- Ver quantos registros serão afetados
SELECT COUNT(*) 
FROM physical_test_forms 
WHERE blocks_config IS NOT NULL 
   OR correct_answers IS NOT NULL;

-- Limpar dados pesados (EXECUTAR APENAS APÓS VALIDAR FASE 2)
UPDATE physical_test_forms 
SET 
    blocks_config = NULL,
    correct_answers = NULL
WHERE blocks_config IS NOT NULL 
   OR correct_answers IS NOT NULL;

-- Verificar resultado
SELECT COUNT(*) 
FROM physical_test_forms 
WHERE blocks_config IS NOT NULL 
   OR correct_answers IS NOT NULL;
-- Deve retornar 0
```

---

## 📊 Benefícios Esperados

### Performance

| Métrica | Antes | Depois | Melhoria |
|---------|-------|--------|----------|
| **Dados salvos por aluno** | ~50KB | ~1KB | **98% menor** |
| **Tempo de salvamento** | 500× salvar JSON pesado | 500× salvar referência | **~70% mais rápido** |
| **Espaço no banco** | 500 alunos × 50KB = 25MB | 1× 50KB + 500× 1KB = 550KB | **98% menor** |

### Exemplo Prático

**Prova com 500 alunos:**
- **Antes**: ~25MB de dados duplicados
- **Depois**: ~550KB (1 gabarito + 500 referências)
- **Economia**: ~24.5MB por prova

---

## 🔍 Como Validar que Está Funcionando

### 1. Verificar Gabarito Central

```sql
-- Ver gabaritos criados para provas físicas
SELECT 
    id,
    test_id,
    num_questions,
    use_blocks,
    created_at,
    CASE 
        WHEN blocks_config IS NOT NULL THEN 'SIM'
        ELSE 'NÃO'
    END as tem_blocks_config,
    CASE 
        WHEN correct_answers IS NOT NULL THEN 'SIM'
        ELSE 'NÃO'
    END as tem_correct_answers
FROM answer_sheet_gabaritos
WHERE test_id IN (
    SELECT DISTINCT test_id 
    FROM physical_test_forms
)
ORDER BY created_at DESC;
```

### 2. Verificar QR Code

```sql
-- Ver QR Codes dos formulários (deve ter gabarito_id)
SELECT 
    id,
    student_id,
    test_id,
    qr_code_data,
    generated_at
FROM physical_test_forms
ORDER BY generated_at DESC
LIMIT 5;
```

O campo `qr_code_data` deve conter algo como:
```json
{"student_id": "abc-123", "test_id": "xyz-789", "gabarito_id": "gab-456"}
```

### 3. Verificar Logs da Correção

Ao corrigir uma prova, procure no log:
```
✅ Gabarito encontrado em AnswerSheetGabarito (fonte central) para test_id: abc12345...
```

Se aparecer isso, está usando o gabarito central! ✅

---

## ⚠️ Compatibilidade com Provas Antigas

### Provas Geradas ANTES da Otimização

✅ **Continuam funcionando normalmente!**

**Por quê?**
- QR Code antigo tem apenas `student_id` e `test_id`
- Correção faz fallback para `PhysicalTestForm`
- Dados ainda estão lá (não foram apagados)

### Fluxo de Fallback

```
1. Ler QR Code
   ↓
2. Tem gabarito_id? 
   → SIM: Buscar em AnswerSheetGabarito ✅
   → NÃO: Tem test_id?
      ↓
3. Buscar em AnswerSheetGabarito por test_id
   → Encontrou? ✅
   → Não encontrou? Buscar em PhysicalTestForm (fallback) ✅
```

---

## 🎓 Entendendo a Solução (Analogia Simples)

### Antes (Biblioteca Ineficiente)
- Cada pessoa que pega um livro emprestado recebe uma **cópia completa** do livro
- 500 pessoas = 500 cópias do mesmo livro
- Muito papel, muito espaço, muito tempo para copiar

### Depois (Biblioteca Eficiente)
- O livro fica na **biblioteca central** (1 cópia só)
- Cada pessoa recebe uma **ficha** dizendo "você pegou o livro #123"
- Na hora de devolver, a biblioteca olha a ficha e sabe qual livro é
- 500 pessoas = 1 livro + 500 fichas pequenas

---

## 📞 Suporte

### Se algo der errado:

1. **Correção não funciona?**
   - Verifique os logs: qual fonte está sendo usada?
   - Se não achar gabarito, vai usar fallback (PhysicalTestForm)

2. **QR Code não tem gabarito_id?**
   - Verifique se `test_data['gabarito_id']` está sendo passado
   - Verifique logs do Celery: "✅ Gabarito central salvo: gabarito_id=..."

3. **Geração falhou?**
   - Verifique se `AnswerSheetGabarito` foi criado
   - Verifique se tem erros no log do Celery

### Reverter mudanças (se necessário):

As mudanças são **não-destrutivas**. Para reverter:
1. A correção já tem fallback automático
2. Dados ainda estão em `PhysicalTestForm`
3. Nada foi apagado

---

## 📈 Métricas de Sucesso

Após implementar, você deve observar:

✅ **Geração mais rápida**: 30-70% mais rápido (depende do número de alunos)
✅ **Menos espaço no banco**: ~98% menos dados duplicados
✅ **Logs mostram**: "Gabarito encontrado em AnswerSheetGabarito (fonte central)"
✅ **Correção funciona**: Sem erros, mesmos resultados

---

## 🔄 Histórico de Mudanças

| Data | Fase | Descrição | Status |
|------|------|-----------|--------|
| 2026-03-17 | Fase 1 | Criar gabarito central + modificar QR Code + priorizar na correção | ✅ CONCLUÍDO |
| Futuro | Fase 2 | Parar de salvar dados pesados em PhysicalTestForm | ⏳ PENDENTE |
| Futuro | Fase 3 | Limpar dados antigos (opcional) | ⏳ PENDENTE |

---

## 🎯 Checklist para Fase 2

Quando estiver pronto para continuar:

- [ ] Validar que provas novas estão sendo geradas com gabarito central
- [ ] Validar que correção está usando gabarito central (verificar logs)
- [ ] Validar que provas antigas ainda funcionam (fallback)
- [ ] Fazer backup do banco de dados
- [ ] Comentar linhas 576 e 582 do `app/physical_tests/form_service.py`
- [ ] Testar geração de nova prova
- [ ] Verificar que `PhysicalTestForm.blocks_config` e `correct_answers` estão NULL
- [ ] Testar correção e confirmar que funciona
- [ ] Monitorar logs por alguns dias

---

## 📝 Notas Técnicas

### Por que AnswerSheetGabarito?

- Já existia no sistema (usado por cartões-resposta)
- Tem todos os campos necessários
- Correção já sabia trabalhar com ele
- Unifica cartão-resposta e prova física

### Por que não criar uma nova tabela?

- Evita duplicação de código
- Reutiliza lógica existente
- Menos complexidade
- Correção unificada

### Por que manter num_questions e use_blocks em PhysicalTestForm?

- São dados leves (alguns bytes)
- Úteis para queries rápidas
- Não impactam performance
- Facilitam listagens

---

**Documentação criada em**: 2026-03-17  
**Versão**: 1.0  
**Status**: Fase 1 Concluída ✅
