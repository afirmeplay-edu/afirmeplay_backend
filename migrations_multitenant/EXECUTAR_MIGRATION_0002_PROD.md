# COMO EXECUTAR A MIGRATION 0002 EM PRODUÇÃO

## 📋 Pré-requisitos
- Acesso SSH ao servidor de produção
- Acesso ao container do PostgreSQL
- Arquivo `0002_migration.sql` no servidor

---

## 🚀 PASSO A PASSO

### 1. Copiar o arquivo SQL para o servidor

```bash
# No seu computador local (PowerShell)
scp migrations_multitenant/0002_migration.sql usuario@servidor:/tmp/
```

### 2. Acessar o servidor e entrar no container do Postgres

```bash
# SSH no servidor
ssh usuario@servidor

# Entrar no container do PostgreSQL
docker exec -it <nome-container-postgres> bash

# OU se o container se chama 'postgres' ou 'db':
docker exec -it postgres bash
docker exec -it db bash
```

### 3. Executar a migration no banco DEV (teste primeiro)

```bash
# Dentro do container, conectar ao banco DEV
psql -U postgres -d afirmeplay_dev

# Executar o script
\i /tmp/0002_migration.sql

# Verificar resultado
\q
```

### 4. Executar a migration no banco PROD

```bash
# Conectar ao banco PROD
psql -U postgres -d afirmeplay_prod

# Executar o script
\i /tmp/0002_migration.sql

# Verificar resultado
\q
```

---

## ✅ ALTERNATIVA: Executar direto via pipe (sem copiar arquivo)

### Opção 1: Do seu computador (via stdin)

```bash
# Executar no DEV
cat migrations_multitenant/0002_migration.sql | ssh usuario@servidor "docker exec -i postgres psql -U postgres -d afirmeplay_dev"

# Executar no PROD
cat migrations_multitenant/0002_migration.sql | ssh usuario@servidor "docker exec -i postgres psql -U postgres -d afirmeplay_prod"
```

### Opção 2: Dentro do servidor (se já copiou o arquivo)

```bash
# No servidor
docker exec -i postgres psql -U postgres -d afirmeplay_dev < /tmp/0002_migration.sql
docker exec -i postgres psql -U postgres -d afirmeplay_prod < /tmp/0002_migration.sql
```

---

## 📊 O que a migration faz:

1. ✅ Adiciona scope `PRIVATE` ao enum `question_scope_type`
2. ✅ Adiciona coluna `owner_user_id` em `public.question`
3. ✅ Migra questões de `city_xxx.question` → `public.question` (com scope=PRIVATE)
4. ✅ Remove tabelas `city_xxx.question` de todos os schemas

---

## ⚠️ IMPORTANTE:

- ✅ **Script é IDEMPOTENTE** - pode executar múltiplas vezes sem problema
- ✅ **NÃO perde dados** - migra antes de deletar
- ✅ **Teste primeiro no DEV** antes de executar no PROD
- ⚠️ Ajustar nome do container do Postgres conforme seu ambiente
- ⚠️ Ajustar usuário do PostgreSQL se não for `postgres`

---

## 🔍 Validar após migration:

```sql
-- Conectar ao banco
\c afirmeplay_prod

-- 1. Verificar se enum tem PRIVATE
SELECT enumlabel FROM pg_enum 
WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'question_scope_type');
-- Deve retornar: GLOBAL, CITY, PRIVATE

-- 2. Verificar coluna owner_user_id
\d public.question
-- Deve mostrar coluna owner_user_id

-- 3. Contar questões por scope
SELECT scope_type, COUNT(*) 
FROM public.question 
GROUP BY scope_type;

-- 4. Verificar que tabelas city_xxx.question não existem mais
SELECT schema_name, table_name 
FROM information_schema.tables 
WHERE table_name = 'question' 
AND schema_name LIKE 'city_%';
-- Deve retornar vazio (0 rows)
```

---

## 🆘 Em caso de problemas:

A migration é segura e idempotente, mas se precisar reverter:

```sql
-- Reverter apenas se algo der muito errado
-- (NÃO recomendado - você perderá as migrações de questões)

-- Remover coluna owner_user_id
ALTER TABLE public.question DROP COLUMN IF EXISTS owner_user_id;

-- Remover scope PRIVATE do enum (mais complexo, precisa recriar enum)
-- Consulte DBA antes de fazer isso
```
