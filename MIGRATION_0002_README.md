# Migration 0002: Consolidação de Questões em public.question

## 📋 Resumo

Esta migration consolida **TODAS** as questões em `public.question`, eliminando a necessidade da tabela `city_xxx.question` e simplificando a arquitetura multitenant.

## 🎯 Objetivos Alcançados

### Antes (Arquitetura Antiga)

- ❌ Questões em múltiplas tabelas: `public.question` E `city_xxx.question`
- ❌ FK constraint de `city_xxx.test_questions` apontando apenas para `public.question` (conflito!)
- ❌ Professores não conseguiam adicionar questões privadas em avaliações
- ❌ Lógica complexa de search_path causando bugs

### Depois (Nova Arquitetura)

- ✅ **TODAS** as questões em `public.question`
- ✅ Três scopes claros: `GLOBAL`, `CITY`, `PRIVATE`
- ✅ FK funciona perfeitamente (todas as questões em um só lugar)
- ✅ Professores podem criar e usar questões privadas

## 📊 Estrutura de Scopes

| Scope       | Criado por                    | Visível para      | owner_city_id | owner_user_id |
| ----------- | ----------------------------- | ----------------- | ------------- | ------------- |
| **GLOBAL**  | Admin                         | Todos             | NULL          | NULL          |
| **CITY**    | Tecadm                        | Município inteiro | city_id       | NULL          |
| **PRIVATE** | Professor/Coordenador/Diretor | Apenas o criador  | NULL          | user_id       |

## 🗂️ Arquivos Modificados

### 1. Migration

- `migrations_multitenant/0002_consolidate_questions_to_public.py` ✨ NOVO

### 2. Model

- `app/models/question.py`
    - Adicionado: `owner_user_id` campo
    - Atualizado: Comentário do `scope_type` (agora inclui PRIVATE)

### 3. Rotas

- `app/routes/question_routes.py`
    - **POST /questions/**: Atualizado para definir scope PRIVATE para professor/coordenador/diretor
    - **GET /questions/**: Removida lógica de buscar em city_xxx, agora usa apenas public com filtros de scope
    - **GET /questions/debug**: Adicionado contador de questões PRIVATE
- `app/routes/test_routes.py`
    - **POST /test**: Questões criadas durante criação de teste agora recebem scope apropriado
    - Adicionado: Import de `text` do SQLAlchemy
    - Adicionado: Obtenção de user info para definir scope

### 4. Helpers (Mantidos)

- `app/utils/question_helpers.py` - Ainda necessário (busca em public forçando search_path)
- `app/models/test.py` property `questions` - Ainda necessário (busca em public forçando search_path)

## 🚀 Como Rodar a Migration

### Ambiente Local (Docker)

```bash
# 1. Entrar no diretório da migration
cd migrations_multitenant

# 2. Rodar em modo DRY-RUN primeiro (para testar sem alterar nada)
python 0002_consolidate_questions_to_public.py --dry-run

# 3. Se tudo estiver OK, rodar de verdade
python 0002_consolidate_questions_to_public.py
```

### Ambiente de Produção (VPS Docker)

```bash
# 1. Conectar na VPS via SSH
ssh user@seu-servidor.com

# 2. Entrar no container do backend
docker exec -it <container_name> bash

# 3. Navegar até a pasta de migrations
cd migrations_multitenant

# 4. SEMPRE rodar dry-run primeiro em produção!
python 0002_consolidate_questions_to_public.py --dry-run

# 5. Verificar o log gerado
cat migration_0002_*.log

# 6. Se tudo OK, rodar de verdade
python 0002_consolidate_questions_to_public.py

# 7. Verificar o log final
cat migration_0002_*.log
```

### ⚠️ IMPORTANTE - Antes de Rodar

1. **Fazer backup do banco de dados**:

    ```bash
    # Local
    docker exec postgres_container pg_dump -U postgres database_name > backup_antes_migration_0002.sql

    # VPS
    docker exec postgres_container pg_dump -U postgres database_name > backup_antes_migration_0002.sql
    ```

2. **Verificar se há questões em city_xxx.question**:
    ```sql
    -- Conectar no banco e rodar:
    SELECT
        schema_name,
        (SELECT COUNT(*) FROM schema_name.question) as count
    FROM information_schema.schemata
    WHERE schema_name LIKE 'city_%';
    ```

## 📝 O Que a Migration Faz

1. **Adiciona 'PRIVATE' ao enum** `question_scope_type`
2. **Adiciona coluna** `owner_user_id` em `public.question`
3. **Migra dados** de `city_xxx.question` para `public.question` (se houver)
    - Define `scope_type='PRIVATE'`
    - Define `owner_user_id=created_by`
4. **Remove tabela** `city_xxx.question` de todos os schemas city

## ✅ Validação Pós-Migration

Após rodar a migration, validar:

```bash
# 1. Verificar se enum possui PRIVATE
SELECT enumlabel FROM pg_enum
WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'question_scope_type');
# Deve retornar: GLOBAL, CITY, PRIVATE

# 2. Verificar se owner_user_id existe
SELECT column_name, data_type FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = 'question' AND column_name = 'owner_user_id';
# Deve retornar uma linha

# 3. Verificar se tabelas city_xxx.question foram removidas
SELECT schema_name FROM information_schema.tables
WHERE table_schema LIKE 'city_%' AND table_name = 'question';
# Deve retornar 0 resultados

# 4. Contar questões por scope
SELECT scope_type, COUNT(*) FROM public.question GROUP BY scope_type;
```

## 🧪 Testar Funcionalidades

### 1. Criar questão como Professor

```bash
POST /questions/
Authorization: Bearer <token_professor>
{
  "text": "Teste questão privada",
  "type": "multipleChoice",
  ...
}
# Deve criar com scope_type='PRIVATE' e owner_user_id=<id_professor>
```

### 2. Criar questão como Tecadm

```bash
POST /questions/
Authorization: Bearer <token_tecadm>
{
  "text": "Teste questão cidade",
  "type": "multipleChoice",
  ...
}
# Deve criar com scope_type='CITY' e owner_city_id=<id_cidade>
```

### 3. Criar questão como Admin

```bash
POST /questions/
Authorization: Bearer <token_admin>
{
  "text": "Teste questão global",
  "type": "multipleChoice",
  ...
}
# Deve criar com scope_type='GLOBAL'
```

### 4. Listar questões

```bash
GET /questions/
Authorization: Bearer <token_qualquer>

# Professor deve ver:
# - Suas questões PRIVATE
# - Questões CITY do município dele
# - Questões GLOBAL

# Admin deve ver:
# - Questões GLOBAL
# (Admin normalmente não pertence a município, então não vê CITY nem PRIVATE de outros)
```

### 5. Criar avaliação com questão nova

```bash
POST /test
Authorization: Bearer <token_professor>
{
  "title": "Teste",
  "questions": [
    {
      "text": "Nova questão",
      "type": "multipleChoice",
      ...
    }
  ]
}
# Questão deve ser criada com scope='PRIVATE' e estar em public.question
```

## 🐛 Troubleshooting

### Erro: "type 'PRIVATE' does not exist"

**Causa**: Migration não rodou ou falhou ao adicionar o enum  
**Solução**:

```sql
ALTER TYPE question_scope_type ADD VALUE IF NOT EXISTS 'PRIVATE';
```

### Erro: "column 'owner_user_id' does not exist"

**Causa**: Migration não rodou ou falhou ao adicionar a coluna  
**Solução**:

```sql
ALTER TABLE public.question ADD COLUMN IF NOT EXISTS owner_user_id VARCHAR REFERENCES public.users(id);
CREATE INDEX IF NOT EXISTS idx_question_owner_user ON public.question(owner_user_id);
```

### Questões não aparecem no GET /questions/

**Verificar**:

1. scope_type está definido?
2. owner_city_id/owner_user_id estão corretos?
3. Usuário tem contexto de cidade se for questão CITY?

```sql
-- Ver questões e seus scopes
SELECT id, text, scope_type, owner_city_id, owner_user_id, created_by
FROM public.question
LIMIT 10;
```

## 📞 Suporte

Se houver problemas:

1. Verificar logs da migration: `migration_0002_*.log`
2. Verificar logs da aplicação: `app.log`
3. Verificar estado do banco com as queries de validação acima
4. Em último caso, restaurar backup e reportar o erro

## ✨ Benefícios da Nova Arquitetura

1. **Simplicidade**: Uma única tabela para todas as questões
2. **Performance**: Menos joins cross-schema, índices eficientes
3. **Funcionalidade**: FK funciona corretamente
4. **Manutenção**: Código mais limpo e fácil de entender
5. **Escalabilidade**: Adicionar novos scopes é trivial (basta adicionar ao enum)
