# 🚀 Guia Rápido de Migração Multi-Tenant

## ⏱️ Tempo Estimado

- **Backup:** 5-10 minutos
- **Dry Run:** 2-5 minutos
- **Migração Real:** 10-30 minutos (depende do número de municípios)
- **Validação:** 2-3 minutos

---

## 📋 Pré-requisitos

### 1. Instalar Dependências Python

```bash
pip install psycopg2-binary python-dotenv
```

### 2. Configurar DATABASE_URL

Editar `app/.env`:

```bash
# Para desenvolvimento
DATABASE_URL=postgresql://postgres:devpass@host:5432/afirmeplay_dev

# Para produção
DATABASE_URL=postgresql://postgres:prodpass@host:5432/afirmeplay_prod
```

### 3. Verificar Conexão

```bash
python -c "import psycopg2; from dotenv import load_dotenv; import os; load_dotenv('app/.env'); psycopg2.connect(os.getenv('DATABASE_URL')); print('✅ Conexão OK')"
```

---

## 🎯 Passo a Passo

### ETAPA 1️⃣: Backup (OBRIGATÓRIO)

```bash
# Ir para pasta de migrations
cd migrations_multitenant

# Criar backup completo
python backup_database.py

# Verificar se arquivos foram criados
ls -lh backup_*.dump backup_*.sql
```

**Arquivos gerados:**

- `backup_afirmeplay_dev_YYYYMMDD_HHMMSS.dump` (formato custom)
- `backup_afirmeplay_dev_YYYYMMDD_HHMMSS.sql` (formato SQL)

⚠️ **IMPORTANTE:** Guarde esses arquivos em local seguro!

---

### ETAPA 2️⃣: Dry Run (Simulação)

```bash
# Executar em modo simulação (não altera banco)
python 0001_init_city_schemas.py --dry-run
```

**O que observar:**

- ✅ Todos os municípios foram encontrados?
- ✅ Schemas seriam criados corretamente?
- ✅ Tabelas seriam criadas?
- ✅ Sem erros nos logs?

---

### ETAPA 3️⃣: Migração Real

```bash
# Executar migração (ALTERA O BANCO!)
python 0001_init_city_schemas.py
```

**Você verá:**

```
⚠️  ATENÇÃO: Esta migração irá ALTERAR o banco de dados!
⚠️  Certifique-se de ter backup antes de continuar.

Digite 'CONFIRMO' para continuar:
```

Digite: `CONFIRMO`

**Aguarde a execução:**

```
================================================================================
🚀 INICIANDO MIGRAÇÃO MULTI-TENANT - Script 0001
================================================================================

================================================================================
ETAPA 1: Criando schemas para municípios
================================================================================
  ➜ Criando schema 'city_abc123...' para São Paulo/SP
  ✓ Schema 'city_abc123...' já existe (Rio de Janeiro/RJ)
✅ Schemas criados/verificados para 3 municípios

================================================================================
ETAPA 2: Criando tabelas operacionais nos schemas CITY
================================================================================
...

✅ MIGRAÇÃO CONCLUÍDA COM SUCESSO!
```

---

### ETAPA 4️⃣: Validação

```bash
# Verificar se migração funcionou
python validate_migration.py
```

**Resultado esperado:**

```
🔍 VALIDAÇÃO DE MIGRAÇÃO MULTI-TENANT
================================================================================

1️⃣  Verificando schemas CITY...
  ✓ Schema 'city_abc123...' existe (São Paulo/SP)
  ✓ Schema 'city_def456...' existe (Rio de Janeiro/RJ)

2️⃣  Verificando tabelas nos schemas CITY...
  ✓ city_abc123...: 54 tabelas OK
  ✓ city_def456...: 54 tabelas OK

3️⃣  Verificando ajustes em public.question...
  ✓ Coluna 'question.scope_type' existe
  ✓ Coluna 'question.owner_city_id' existe
  ✓ ENUM 'question_scope_type' existe

4️⃣  Verificando school_managers...
  ✓ city_abc123.school_managers: 3 vínculos
  📊 Total de vínculos migrados: 5

================================================================================
📊 RESUMO DA VALIDAÇÃO
================================================================================
✅ Sucessos: 127
⚠️  Avisos: 2

✅ MIGRAÇÃO VALIDADA COM SUCESSO!
```

---

## 🔍 Verificação Manual no Banco

```sql
-- Listar schemas criados
SELECT schema_name
FROM information_schema.schemata
WHERE schema_name LIKE 'city_%'
ORDER BY schema_name;

-- Verificar tabelas em um schema
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'city_abc123...'
ORDER BY table_name;

-- Verificar colunas de escopo em questions
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'question'
  AND column_name IN ('scope_type', 'owner_city_id');

-- Verificar vínculos em school_managers
SELECT COUNT(*) FROM city_abc123....school_managers;

-- Verificar questões globais
SELECT COUNT(*), scope_type
FROM public.question
GROUP BY scope_type;
```

---

## ❌ Em Caso de Erro

### 1. Revisar Logs

```bash
# Abrir o log gerado
cat migration_0001_YYYYMMDD_HHMMSS.log
```

### 2. Restaurar Backup (se necessário)

```bash
# Restaurar formato CUSTOM (.dump)
pg_restore -h host -p 5432 -U postgres \
           -d afirmeplay_dev -v --clean \
           backup_afirmeplay_dev_YYYYMMDD_HHMMSS.dump

# OU restaurar formato SQL (.sql)
psql -h host -p 5432 -U postgres \
     -d afirmeplay_dev < backup_afirmeplay_dev_YYYYMMDD_HHMMSS.sql
```

### 3. Limpar Schemas (se quiser rodar novamente)

```sql
-- ⚠️ CUIDADO: Isso remove TODOS os schemas city_*
DO $$
DECLARE
    schema_name TEXT;
BEGIN
    FOR schema_name IN
        SELECT nspname
        FROM pg_namespace
        WHERE nspname LIKE 'city_%'
    LOOP
        EXECUTE 'DROP SCHEMA IF EXISTS ' || schema_name || ' CASCADE';
    END LOOP;
END $$;

-- Reverter alterações em public.question
ALTER TABLE public.question
DROP COLUMN IF EXISTS scope_type,
DROP COLUMN IF EXISTS owner_city_id,
DROP COLUMN IF EXISTS approved_by,
DROP COLUMN IF EXISTS approved_at;

DROP TYPE IF EXISTS question_scope_type;
```

---

## 📊 Checklist Final

Antes de considerar a migração concluída:

- [ ] ✅ Backup criado e guardado
- [ ] ✅ Dry run executado sem erros
- [ ] ✅ Migração real executada
- [ ] ✅ Validação passou sem erros críticos
- [ ] ✅ Verificação manual no banco OK
- [ ] ✅ Logs revisados
- [ ] ✅ Time notificado

---

## 🎉 Próximos Passos

Após migração bem-sucedida:

1. **Ajustar Application Code:**
    - Implementar schema routing dinâmico
    - Atualizar SQLAlchemy models
    - Adicionar `search_path` nas queries

2. **Preparar Migração de Dados (Script 0002):**
    - Mover dados de `public.school` → `city_<id>.school`
    - Mover dados de `public.student` → `city_<id>.student`
    - E outros...

3. **Testar em Ambiente DEV:**
    - Criar testes de integração
    - Validar queries cross-schema
    - Testar performance

4. **Planejar Migração em PROD:**
    - Definir janela de manutenção
    - Preparar plano de rollback
    - Treinar equipe

---

## 📞 Ajuda

- **Erro de conexão:** Verificar DATABASE_URL
- **Erro de permissão:** Usuário precisa de CREATE DATABASE
- **Tabelas faltando:** Rodar validação para detalhes
- **Migração lenta:** Normal para muitos municípios

---

**Versão:** 1.0  
**Data:** 2026-02-10  
**Status:** Pronto para uso
