# Migração Multi-Tenant - Innovaplay Backend

Sistema de migração para arquitetura multi-tenant por schema PostgreSQL.

## 📋 Visão Geral

Este projeto migra o backend de um modelo single-tenant para multi-tenant usando schemas PostgreSQL separados por município (`city_<city_id>`).

### Arquitetura

```
┌─────────────────────────────────────────┐
│         SCHEMA: public (GLOBAL)         │
├─────────────────────────────────────────┤
│ • users (identidade global)             │
│ • manager (gestores globais)            │
│ • city (municípios)                     │
│ • subject, grade, education_stage       │
│ • question (com escopo GLOBAL/CITY)     │
│ • competition_templates                 │
│ • play_tv_videos, plantao_online        │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│      SCHEMA: city_<id> (TENANT)         │
├─────────────────────────────────────────┤
│ • school, class, student, teacher       │
│ • test, test_sessions, student_answers  │
│ • competitions (instanciadas)           │
│ • forms, certificates, games            │
│ • school_managers (vínculo manager↔school) │
└─────────────────────────────────────────┘
```

---

## 🗂️ Estrutura de Arquivos

```
migrations_multitenant/
├── README.md                    # Este arquivo
├── 0001_init_city_schemas.py    # Script de migração inicial
├── validate_migration.py        # Script de validação
└── logs/                        # Logs de execução (auto-gerado)
```

---

## 🚀 Execução

### Pré-requisitos

```bash
# Instalar dependências
pip install psycopg2-binary python-dotenv

# Configurar DATABASE_URL no app/.env
DATABASE_URL=postgresql://user:pass@host:port/afirmeplay_dev
```

### Modo DRY RUN (Simulação)

Executa sem alterar o banco, apenas loga o que seria feito:

```bash
python migrations_multitenant/0001_init_city_schemas.py --dry-run
```

### Execução REAL

⚠️ **ATENÇÃO:** Faz alterações no banco de dados!

```bash
# Fazer backup primeiro!
pg_dump -h host -U user -d afirmeplay_dev > backup_antes_migracao.sql

# Executar migração
python migrations_multitenant/0001_init_city_schemas.py
```

O script pedirá confirmação:

```
⚠️  ATENÇÃO: Esta migração irá ALTERAR o banco de dados!
⚠️  Certifique-se de ter backup antes de continuar.

Digite 'CONFIRMO' para continuar:
```

---

## 📝 O que o Script 0001 Faz

### ✅ Etapa 1: Criar Schemas

- Lê todos os municípios da tabela `public.city`
- Para cada município, cria schema `city_<uuid>` (ex: `city_123e4567_e89b_12d3_a456_426614174000`)
- Adiciona comentário no schema com nome do município

### ✅ Etapa 2: Criar Tabelas CITY

Cria 50+ tabelas operacionais em cada schema:

**Estrutura:**

- `school`, `class`, `student`, `teacher`
- `school_teacher`, `teacher_class`, `class_subject`
- `school_managers` ⭐ (novo - substitui manager.school_id)

**Avaliações:**

- `test`, `test_questions`, `class_test`
- `student_answers`, `test_sessions`, `evaluation_results`

**Formulários Físicos:**

- `physical_test_forms`, `physical_test_answers`
- `answer_sheet_gabaritos`, `answer_sheet_results`

**Competições:**

- `competitions`, `competition_enrollments`, `competition_results`

**Outros:**

- `forms`, `certificates`, `games`, `calendar_events`
- `student_coins`, `coin_transactions`
- E mais...

### ✅ Etapa 3: Ajustar public.questions

Adiciona colunas de escopo:

```sql
ALTER TABLE public.question ADD COLUMN:
- scope_type ENUM('GLOBAL', 'CITY')
- owner_city_id VARCHAR
- approved_by VARCHAR
- approved_at TIMESTAMP
```

**Regras:**

- Questões criadas por admin/tecadm → `GLOBAL`
- Questões criadas por professores → `CITY` + `owner_city_id`
- Questões existentes → marcadas como `GLOBAL`

### ✅ Etapa 4: Migrar school_managers

- Lê `manager.school_id` de todos os managers
- Para cada vínculo, cria registro em `city_<id>.school_managers`
- **NÃO remove** `manager.school_id` ainda (fazer em etapa futura)

### ✅ Extra: Criar Índices

Cria índices de performance em tabelas PUBLIC:

- `users(city_id, role, email)`
- `manager(city_id, user_id)`
- `city(state)`

---

## 🔍 Validação

Após executar a migração, valide:

```bash
python migrations_multitenant/validate_migration.py
```

O script verifica:

- ✅ Schemas criados para todos os municípios
- ✅ Tabelas criadas em cada schema
- ✅ Colunas de escopo em public.question
- ✅ Vínculos migrados para school_managers
- ✅ Integridade de Foreign Keys

---

## 📊 Logs

Cada execução gera log automático:

```
migration_0001_20260210_143025.log
```

Exemplo:

```
2026-02-10 14:30:25 - INFO - Conectado ao banco de dados
2026-02-10 14:30:25 - INFO - Buscando municípios cadastrados...
2026-02-10 14:30:25 - INFO - Encontrados 3 municípios
2026-02-10 14:30:26 - INFO - ➜ Criando schema 'city_abc123' para São Paulo/SP
2026-02-10 14:30:26 - INFO - ✅ Schemas criados/verificados para 3 municípios
...
```

---

## ⚠️ IMPORTANTE - O que NÃO É FEITO

Este script **NÃO:**

❌ Remove tabelas do `public`  
❌ Move dados de `public.school` para `city_<id>.school`  
❌ Altera Foreign Keys existentes  
❌ Remove colunas antigas (ex: `manager.school_id`)  
❌ Migra dados de produção automaticamente

**Por quê?**

- Segurança: evitar perda de dados
- Reversibilidade: manter estrutura antiga temporariamente
- Migração gradual: permitir coexistência durante transição

---

## 🔄 Próximos Scripts (Futuro)

### Script 0002: Migração de Dados

```python
# Mover dados de public.school → city_<id>.school
# Mover dados de public.student → city_<id>.student
# etc.
```

### Script 0003: Limpeza

```python
# Remover tabelas antigas de public
# Remover colunas obsoletas (manager.school_id)
# Validar integridade final
```

### Script 0004: Ajustes de Application

```python
# Atualizar SQLAlchemy models
# Implementar schema routing
# Ajustar queries para usar search_path
```

---

## 🛡️ Segurança

### Backup Antes de Executar

```bash
# Backup completo
pg_dump -h host -U user -d afirmeplay_dev -F c -b -v -f backup_completo.dump

# Backup apenas schema public
pg_dump -h host -U user -d afirmeplay_dev -n public > backup_public.sql

# Backup apenas dados
pg_dump -h host -U user -d afirmeplay_dev --data-only > backup_dados.sql
```

### Restaurar em Caso de Erro

```bash
# Restaurar backup completo
pg_restore -h host -U user -d afirmeplay_dev -v backup_completo.dump

# Restaurar apenas public
psql -h host -U user -d afirmeplay_dev < backup_public.sql
```

---

## 🐛 Troubleshooting

### Erro: "relation already exists"

**Causa:** Script já foi executado antes  
**Solução:** Normal! Script é idempotente, tabelas não são recriadas

### Erro: "permission denied for schema"

**Causa:** Usuário do banco sem permissão  
**Solução:**

```sql
GRANT CREATE ON DATABASE afirmeplay_dev TO seu_usuario;
GRANT ALL ON SCHEMA public TO seu_usuario;
```

### Erro: "database connection failed"

**Causa:** DATABASE_URL incorreto  
**Solução:** Verificar credenciais em `app/.env`

### Warning: "manager.school_id não foi removido"

**Causa:** Comportamento esperado  
**Solução:** Será removido em migração futura (0003)

---

## 📞 Suporte

- **Logs:** Verificar arquivo `.log` gerado
- **Validação:** Rodar `validate_migration.py`
- **Rollback:** Restaurar backup

---

## ✅ Checklist de Migração

Antes de executar em **PRODUÇÃO**:

- [ ] Testado em ambiente DEV
- [ ] Backup completo realizado
- [ ] Validação executada e passou
- [ ] Aplicação testada com nova estrutura
- [ ] Plano de rollback preparado
- [ ] Janela de manutenção agendada
- [ ] Equipe notificada

---

**Versão:** 0001  
**Data:** 2026-02-10  
**Autor:** Sistema de Migração Multi-Tenant
