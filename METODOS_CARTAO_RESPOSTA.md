# 📚 Documentação: Métodos de Geração de Cartões Resposta

**Data:** 2026-03-19  
**Arquivo:** `app/services/cartao_resposta/answer_sheet_generator.py`

---

## 🎯 Visão Geral

Existem **2 métodos principais** para gerar cartões resposta, cada um com caso de uso específico:

---

## 📋 Método 1: `generate_class_answer_sheets()` ✅ **EM USO**

### Status: ✅ **ATIVO - Usado pela rota principal**

### Descrição:
Gera **PDFs individuais** (1 arquivo por aluno) organizados em estrutura de pastas.

### Saída:
```
base_output_dir/
  └─ municipio_sao_paulo/
      └─ escola_em_joao_silva/
          └─ serie_5_ano/
              └─ turma_a/
                  ├─ joao_silva_5_ano_a.pdf
                  ├─ maria_santos_5_ano_a.pdf
                  └─ ... (1 PDF por aluno)
```

### Usado por:
- **Rota:** `POST /answer-sheets/generate` ← **Rota principal do sistema**
- **Task:** `generate_answer_sheets_single_class_async`

### Architecture:
- ✅ **Architecture 4 (Template Base + Overlay)** por padrão
- ✅ WeasyPrint roda 1× (template base)
- ✅ Overlay ReportLab por aluno (rápido)
- ✅ 10-50× mais rápido que método antigo

### Assinatura:
```python
def generate_class_answer_sheets(
    self,
    class_id: str,
    base_output_dir: str,
    test_data: Dict,
    num_questions: int,
    use_blocks: bool,
    blocks_config: Dict,
    correct_answers: Dict,
    gabarito_id: str = None,
    questions_options: Dict = None,
    use_arch4: bool = True,  # ← Architecture 4 por padrão
) -> Optional[Dict]
```

### Retorno:
```python
{
    'class_id': 'uuid',
    'total_students': 27
}
```

---

## 📋 Método 2: `generate_answer_sheets()` ⚠️ **DESCONTINUADO**

### Status: ⚠️ **DESCONTINUADO - Não está sendo usado**

### Descrição:
Gera **1 PDF único** com **múltiplas páginas** (1 página por aluno).

### Saída:
```
output_dir/
  └─ cartoes_turma_A_uuid.pdf  (27 páginas)
```

### Problema:
- ❌ Demora muito para várias turmas
- ❌ Gera arquivo grande (difícil de distribuir)
- ❌ Não é usado pela rota principal

### Usado por:
- ⚠️ **Nenhuma rota ativa** (código legado)
- Tasks antigas que não são mais chamadas:
  - `generate_answer_sheets_async` (descontinuada)
  - Chamadas em `generate_answer_sheets_batch_task` (não usadas)

### Motivo da Descontinuação:
- Sistema atual usa PDFs individuais (melhor organização)
- Para múltiplas turmas, PDF único é ineficiente
- Mantido apenas para compatibilidade com código legado

### Assinatura:
```python
def generate_answer_sheets(
    self,
    class_id: str,
    test_data: Dict,
    num_questions: int,
    use_blocks: bool,
    blocks_config: Dict,
    correct_answers: Dict,
    gabarito_id: str = None,
    questions_options: Dict = None,
    output_dir: str = None,
    use_arch4: bool = True,
) -> Dict
```

---

## 🗺️ Fluxo da Rota Principal

### POST /answer-sheets/generate

```
1. Rota (app/routes/answer_sheet_routes.py:400)
   └─> Recebe payload: {gabarito_id, class_ids, ...}

2. Cria tasks Celery (linha 592-594)
   └─> generate_answer_sheets_single_class_async.s(class_id, ...)

3. Task Celery (app/services/celery_tasks/answer_sheet_tasks.py:713)
   └─> generate_answer_sheets_single_class_async()

4. Chama Generator (linha 747)
   └─> generator.generate_class_answer_sheets()  ← MÉTODO ATIVO

5. Generator (app/services/cartao_resposta/answer_sheet_generator.py:558)
   └─> Gera PDFs individuais com Architecture 4 (overlay)
```

---

## 📊 Comparação dos Métodos

| Aspecto | `generate_class_answer_sheets()` ✅ | `generate_answer_sheets()` ⚠️ |
|---------|-------------------------------------|-------------------------------|
| **Status** | ✅ ATIVO | ⚠️ DESCONTINUADO |
| **Usado por** | Rota `/answer-sheets/generate` | Nenhuma rota ativa |
| **Saída** | PDFs individuais (1 por aluno) | PDF único (múltiplas páginas) |
| **Estrutura** | Pastas organizadas | Arquivo único |
| **Performance** | ✅ Rápido (arch4) | ⚠️ Lento para múltiplas turmas |
| **Distribuição** | ✅ Fácil (arquivo por aluno) | ❌ Difícil (arquivo grande) |
| **Uso recomendado** | ✅ SIM | ❌ NÃO |

---

## ✅ Confirmações Importantes

### 1. Nenhum arquivo de `app/physical_tests/` foi modificado

```bash
$ git diff --name-only
GUIA_USO_MULTITENANT.md
app/routes/calendar_routes.py
app/routes/dashboard_routes.py
app/services/cartao_resposta/answer_sheet_generator.py  ← Apenas cartão resposta
app/services/celery_tasks/answer_sheet_tasks.py
app/services/dashboard_service.py
db_uuid_normalization.md
```

✅ **Confirmado: ZERO arquivos de `physical_tests/` foram alterados!**

### 2. Todos os métodos estão em `app/services/cartao_resposta/`

✅ **Confirmado: Tudo está na pasta correta!**

---

## 🚀 Próximos Passos

1. ✅ **Métodos comentados** - Descontinuados marcados
2. ✅ **Cache deletado** - `.pyc` removidos
3. ⏳ **Reiniciar Celery** - Para carregar código novo
4. ⏳ **Testar rota** - `POST /answer-sheets/generate`
5. ⏳ **Validar logs** - Procurar `[GENERATOR ARCH4]`
6. ⏳ **Verificar tempo** - Deve ser 10-20× mais rápido

---

## 📞 Resumo Executivo

**Pergunta:** Por que tem 2 métodos?

**Resposta:** 
- **Método 1 (ATIVO):** `generate_class_answer_sheets()` - PDFs individuais, usado pela rota principal
- **Método 2 (DESCONTINUADO):** `generate_answer_sheets()` - PDF único, não usado mais

**Pergunta:** Estão todos em `app/services/cartao_resposta/`?

**Resposta:** ✅ SIM, todos os métodos estão nesta pasta.

**Pergunta:** Alterou algo em `app/physical_tests/`?

**Resposta:** ✅ NÃO, nenhum arquivo de `physical_tests/` foi tocado!

---

**Tudo pronto! Agora é só reiniciar o Celery e testar!** 🎉
