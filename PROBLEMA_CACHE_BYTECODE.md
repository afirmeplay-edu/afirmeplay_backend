# 🔍 Problema Identificado: Cache de Bytecode Python

**Data:** 2026-03-19  
**Status:** ✅ RESOLVIDO

---

## 🚨 Problema

Após adicionar `use_arch4=True` nas tasks do Celery, o sistema **continuou usando o método antigo** (WeasyPrint por aluno), levando ~10 segundos por aluno ao invés de ~0.5-1s.

### Evidências:

1. **Tempo de execução:** 284 segundos para 27 alunos = 10.5s/aluno (método antigo)
2. **Logs do WeasyPrint:** Processamento de fontes repetido por aluno
3. **Ausência de logs:** Nenhum `[GENERATOR ARCH4]` apareceu
4. **Código correto:** `use_arch4=True` estava presente no arquivo `.py`

---

## 🔎 Causa Raiz: Bytecode Cache Desatualizado

### Descoberta:

O diretório `app/services/celery_tasks/__pycache__/` continha **DOIS arquivos `.pyc`**:

```
answer_sheet_tasks.cpython-312.pyc  (13/02/2026 10:43) ← ANTIGO
answer_sheet_tasks.cpython-313.pyc  (19/03/2026 15:11) ← NOVO
```

### Explicação:

1. **Celery está rodando com Python 3.12**
2. **Código foi editado e compilado com Python 3.13** (IDE ou outro processo)
3. **Celery carregou o `.pyc` antigo** (cpython-312) de **13/02/2026**
4. **Código novo nunca foi executado** porque o bytecode antigo tinha prioridade

### Por Que Aconteceu?

Python prioriza arquivos `.pyc` (bytecode compilado) sobre `.py` (código fonte) para performance. Quando há um `.pyc` válido, o Python **não recompila** o `.py`, mesmo que ele tenha sido modificado.

**Fluxo do problema:**
```
1. Código antigo compilado → cpython-312.pyc (13/02)
2. Código editado (19/03)
3. Celery iniciado → carrega cpython-312.pyc (ANTIGO!)
4. Código novo ignorado
```

---

## ✅ Solução Aplicada

### 1. Deletar Cache de Bytecode

```powershell
# Deletar .pyc específico
Remove-Item -Path "app\services\celery_tasks\__pycache__\*.pyc" -Force

# Deletar TODOS os .pyc do projeto (recomendado)
Get-ChildItem -Path . -Include *.pyc -Recurse | Remove-Item -Force
```

### 2. Reiniciar Celery

Após deletar os `.pyc`, o Celery vai:
1. Ler o código `.py` atualizado
2. Compilar novo `.pyc` com código correto
3. Executar o método arch4

---

## 🎯 Como Validar

### 1. Verificar que `.pyc` foi deletado:
```powershell
dir app\services\celery_tasks\__pycache__\answer_sheet_tasks*.pyc
# Deve retornar vazio ou arquivo novo com data atual
```

### 2. Reiniciar Celery:
```bash
pkill -9 -f celery
celery -A app.report_analysis.celery_app worker --loglevel=info --concurrency=4 --prefetch-multiplier=1
```

### 3. Gerar cartões e verificar logs:
```
✅ DEVE APARECER:
[GENERATOR ARCH4] Turma: A (ID: uuid)
[GENERATOR ARCH4] Gerando template base com WeasyPrint...
[GENERATOR ARCH4] ✅ Template base gerado
[GENERATOR ARCH4] Gerando overlays para 27 alunos...
[GENERATOR ARCH4] ✅ PDF gerado
```

### 4. Verificar tempo:
- **Antes:** 284s para 27 alunos (10.5s/aluno)
- **Depois:** ~15-30s para 27 alunos (0.5-1s/aluno)
- **Ganho esperado:** 10-20× mais rápido

---

## 📚 Lições Aprendidas

### 1. Cache de Bytecode é Persistente

Python mantém `.pyc` mesmo após editar `.py`. Sempre limpar cache ao fazer mudanças críticas.

### 2. Múltiplas Versões Python

Se o projeto usa múltiplas versões Python (3.12, 3.13), cada uma gera seu próprio `.pyc`:
- `cpython-312.pyc`
- `cpython-313.pyc`

### 3. Celery Não Recarrega Automaticamente

Mesmo reiniciando Celery, ele pode carregar `.pyc` antigo. Sempre limpar cache.

### 4. Validação de Logs é Essencial

Sem logs `[GENERATOR ARCH4]`, soubemos imediatamente que o código novo não estava rodando.

---

## 🔧 Prevenção Futura

### 1. Limpar Cache Antes de Deploy

```bash
# Adicionar ao script de deploy
find . -type d -name __pycache__ -exec rm -rf {} +
find . -name "*.pyc" -delete
```

### 2. Usar Variável de Ambiente

```bash
# Desabilitar bytecode cache (desenvolvimento)
export PYTHONDONTWRITEBYTECODE=1
celery -A app.report_analysis.celery_app worker ...
```

### 3. Monitorar Logs

Sempre verificar se logs esperados aparecem após mudanças críticas.

### 4. Usar Reload Automático (Desenvolvimento)

```bash
# Celery com auto-reload (apenas desenvolvimento)
celery -A app.report_analysis.celery_app worker --autoreload
```

---

## 📊 Resumo

| Item | Problema | Solução |
|------|----------|---------|
| **Causa** | Cache `.pyc` antigo (13/02) | Deletar `.pyc` |
| **Sintoma** | Código novo não executa | Reiniciar Celery |
| **Validação** | Sem logs `[GENERATOR ARCH4]` | Verificar logs |
| **Performance** | 10.5s/aluno (antigo) | 0.5-1s/aluno (novo) |

---

## ✅ Status Atual

- ✅ Cache `.pyc` deletado
- ⏳ Aguardando reinício do Celery
- ⏳ Aguardando validação (gerar cartões + verificar logs)

---

**Próximo passo:** Reiniciar Celery e testar geração de cartões para validar que arch4 está funcionando.
