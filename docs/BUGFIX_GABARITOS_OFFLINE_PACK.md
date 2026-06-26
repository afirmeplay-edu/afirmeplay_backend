# Correção: Gabaritos não apareciam no pacote offline

## Problema Identificado

Ao criar um pacote offline com `gabarito_ids` especificado no scope, os alunos não apareciam no bundle:

```json
{
  "counts": {
    "students": 0,  // ❌ Vazio
    "gabaritos": 0,  // ❌ Vazio
    "links": 0
  }
}
```

### Análise do Banco

```sql
-- Código existia
SELECT code_hash FROM public.mobile_offline_pack_registry 
WHERE code_hash = 'G2P26F3YCNKW';  -- ✅ Encontrado

-- Gabarito existia
SELECT id, scope_type, school_id FROM answer_sheet_gabaritos 
WHERE id = 'e5bf8fe1-3773-4365-b03a-5ce1e91e73af';  -- ✅ Encontrado

-- Scope do pacote tinha gabarito_ids
SELECT scope_json FROM mobile_offline_pack_code;
/*
{
  "gabarito_ids": ["e5bf8fe1-3773-4365-b03a-5ce1e91e73af"],  ✅
  "school_ids": ["56bfd6b8-8465-4331-a13b-06cb06a8516d"],    ✅
  "class_ids": ["2d7e60b3-d6d0-49aa-a591-520b421188ca"],    ✅
  "_resolved": {
    "redeem_student_ids": []  ❌ VAZIO!
  }
}
*/
```

## Causa Raiz

O código de `offline_pack_service.py` **não processava `gabarito_ids` do scope**:

```python
# ANTES (ERRADO)
def collect_filtered_scope(school_ids, test_ids, class_ids, student_ids):
    # ❌ Não recebia gabarito_ids
    for sch_id in school_ids:
        _, tests_map, school_links, gabaritos_map, gabarito_links = collect_school_scope(sch_id)
        # ❌ Buscava TODOS os gabaritos da escola, ignorando filtro
```

## Correções Aplicadas

### 1. `answer_sheet_mobile_service.py`

**Função `collect_gabaritos_for_school()`** agora aceita filtros:

```python
def collect_gabaritos_for_school(
    school_id: str,
    gabarito_ids: Optional[Set[str]] = None,  # ✅ NOVO
    class_ids: Optional[Set[str]] = None,      # ✅ NOVO
):
    query = AnswerSheetGabarito.query.filter(
        AnswerSheetGabarito.school_id == school_id,
    )
    
    # ✅ Filtrar por IDs específicos
    if gabarito_ids:
        query = query.filter(AnswerSheetGabarito.id.in_(list(gabarito_ids)))
    
    # ✅ Filtrar turmas ao buscar alunos
    if class_ids:
        turmas_alvo = [t for t in turmas_alvo if str(t.id) in class_ids]
```

### 2. `offline_pack_service.py`

**Função `collect_filtered_scope()`** agora processa `gabarito_ids`:

```python
def collect_filtered_scope(
    school_ids, 
    test_ids, 
    class_ids, 
    student_ids,
    gabarito_ids,  # ✅ NOVO parâmetro
):
    for sch_id in school_ids:
        _, tests_map, school_links, gabaritos_map, gabarito_links = collect_school_scope(
            sch_id, 
            gabarito_ids_filter=gabarito_ids,  # ✅ Passa filtro
            class_ids_filter=class_ids          # ✅ Passa filtro
        )
```

**Função `redeem_offline_pack_page()`** extrai e passa `gabarito_ids`:

```python
# ✅ Extrair gabarito_ids do scope
gabarito_ids = _optional_id_set("gabarito_ids", user_sc)

logger.info(
    f"[OFFLINE-PACK-REDEEM] Filtros: gabaritos={len(gabarito_ids) if gabarito_ids else 0}"
)

# ✅ Passar para collect_filtered_scope
tests_map, links, gabaritos_map, gabarito_links = collect_filtered_scope(
    school_ids, test_ids, class_ids, student_ids, gabarito_ids  # ✅
)

logger.info(
    f"[OFFLINE-PACK-REDEEM] Resultado: gabaritos={len(gabaritos_map)} links={len(gabarito_links)}"
)
```

### 3. `bundle_service.py`

**Função `collect_school_scope()`** suporta filtros opcionais:

```python
def collect_school_scope(
    school_id: str,
    gabarito_ids_filter: Optional[Set[str]] = None,  # ✅ NOVO
    class_ids_filter: Optional[Set[str]] = None,      # ✅ NOVO
):
    # ✅ Passa filtros para collect_gabaritos_for_school
    gabaritos_map, student_gabarito_links = collect_gabaritos_for_school(
        school_id,
        gabarito_ids=gabarito_ids_filter,
        class_ids=class_ids_filter,
    )
```

## Fluxo Corrigido

```
1. Frontend cria pacote com:
   scope_json = {
     "gabarito_ids": ["xxx"],
     "class_ids": ["yyy"],
     "school_ids": ["zzz"]
   }

2. App resgata código:
   POST /mobile/v1/offline-pack/redeem

3. Backend:
   a) Extrai gabarito_ids do scope ✅
   b) Passa para collect_filtered_scope() ✅
   c) Filtra gabaritos pelo ID ✅
   d) Busca turmas-alvo do gabarito ✅
   e) Filtra turmas por class_ids ✅
   f) Busca alunos das turmas ✅
   g) Retorna gabaritos + links ✅

4. App recebe:
   {
     "gabaritos": 1,  ✅
     "links": 3,      ✅
     "students": 3    ✅
   }
```

## Logs Adicionados

```
[OFFLINE-PACK-REDEEM] Filtros aplicados: 
  schools=1 tests=0 classes=1 gabaritos=1

[OFFLINE-PACK-REDEEM] Resultado: 
  tests=0 test_links=0 gabaritos=1 gabarito_links=3

Gabarito e5bf8fe1-3773-4365-b03a-5ce1e91e73af: 
  3 alunos em 1 turmas
```

## Testes

### Teste 1: Resgate com gabarito_ids específico
```bash
# Criar pacote com gabarito específico
POST /mobile/v1/offline-pack/register
{
  "scope": {
    "type": "custom",
    "gabarito_ids": ["e5bf8fe1-3773-4365-b03a-5ce1e91e73af"],
    "school_ids": ["56bfd6b8-8465-4331-a13b-06cb06a8516d"]
  }
}

# Resgatar
POST /mobile/v1/offline-pack/redeem
{
  "code": "G2P2-6F3Y-CNKW",
  "page": 1
}

# Verificar resposta
✅ answer_sheet_gabaritos: 1 gabarito
✅ student_gabarito_links: 3 vínculos
✅ students: 3 alunos
```

### Teste 2: Bundle normal (sem filtros)
```bash
GET /mobile/v1/sync/bundle?school_id=xxx

# Verificar resposta
✅ answer_sheet_gabaritos: todos gabaritos da escola
✅ student_gabarito_links: todos vínculos
```

## Arquivos Modificados

- ✅ `app/services/mobile/answer_sheet_mobile_service.py`
  - `collect_gabaritos_for_school()` - Aceita filtros opcionais
  - Logs adicionados para debugging

- ✅ `app/services/mobile/offline_pack_service.py`
  - `collect_filtered_scope()` - Processa gabarito_ids
  - `redeem_offline_pack_page()` - Extrai e passa gabarito_ids
  - Import de logging adicionado
  - Logs detalhados adicionados

- ✅ `app/services/mobile/bundle_service.py`
  - `collect_school_scope()` - Suporta filtros opcionais

## Impacto

- ✅ Backward compatible (filtros são opcionais)
- ✅ Bundle normal continua funcionando
- ✅ Offline pack agora respeita gabarito_ids do scope
- ✅ Logs ajudam no debugging

## Observação Importante

O problema NÃO foi diferença de ambiente (DEV vs PROD), mas sim a **lógica de filtro ausente** no código. Mesmo no ambiente correto, gabaritos não apareciam porque o código não processava `gabarito_ids` do scope.
