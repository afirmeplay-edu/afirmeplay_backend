# 🚀 Como Executar a Constraint no Container VPS

## 📋 Opções de Execução

### **Opção 1: Copiar e executar** (Recomendado)

```bash
# 1. Copiar o script SQL atualizado para o VPS
scp add_class_constraint.sql root@147.79.87.213:/root/

# 2. Na VPS, copiar para o container
docker cp add_class_constraint.sql <container_id>:/tmp/add_class_constraint.sql

# 3. Executar o script dentro do container
docker exec -it <container_id> psql -U postgres -d afirmeplay_dev -f /tmp/add_class_constraint.sql

# 4. (Opcional) Remover o arquivo do container
docker exec -it <container_id> rm /tmp/add_class_constraint.sql
```

### **Opção 2: Pipe direto** (Mais rápido - após copiar para VPS)

```bash
# Na VPS
docker exec -i <container_id> psql -U postgres -d afirmeplay_dev < /root/add_class_constraint.sql
```

---

## ✨ Novidades da Versão 2.0

### 🛡️ Proteções Adicionadas:

- ✅ **Verifica se tabela existe** antes de processar cada schema
- ✅ **Tratamento de erros** - continua processando mesmo se um schema falhar
- ✅ **Pula schemas vazios** automaticamente (sem tabela `class`)
- ✅ **Relatório detalhado** com schemas pulados e com erro
- ⚠️ **Nota:** Todas as alterações são feitas em uma única transação (COMMIT ao final)

### 📊 Output Melhorado:

```
NOTICE:  📍 Processando schema: city_56ab4f5d_179d_4a28_833c_cac5bb6e74cd
NOTICE:  ⚠️  Tabela class não existe - PULANDO
...
NOTICE:  ========================================
NOTICE:  ✨ RESUMO FINAL
NOTICE:  ========================================
NOTICE:  📊 Total de schemas encontrados: 45
NOTICE:  ✅ Schemas processados com sucesso: 42
NOTICE:  ⚠️  Schemas pulados (sem tabela class): 3
NOTICE:  ❌ Schemas com erro: 0
NOTICE:  🔧 Total de turmas renomeadas: 12
NOTICE:
NOTICE:  📋 Schemas pulados:
NOTICE:     city_56ab4f5d_179d_4a28_833c_cac5bb6e74cd, city_test_empty, ...
```

---

## 🔍 Verificar se funcionou

Após executar, você pode verificar se as constraints foram adicionadas:

```bash
# Verificar constraints em um schema específico
docker exec -it <container_id> psql -U postgres -d afirmeplay_dev -c "
SELECT constraint_name, constraint_type
FROM information_schema.table_constraints
WHERE table_schema = 'city_034b3bc3_8441_4344_b3f6_35d0727625a6'
  AND table_name = 'class'
ORDER BY constraint_name;
"

# Contar quantos schemas têm a constraint
docker exec -it <container_id> psql -U postgres -d afirmeplay_dev -c "
SELECT COUNT(DISTINCT table_schema) as schemas_com_constraint
FROM information_schema.table_constraints
WHERE table_name = 'class'
  AND constraint_name = 'unique_class_name_per_school';
"

# Listar todos os schemas city_* com tabela class para comparar
docker exec -it <container_id> psql -U postgres -d afirmeplay_dev -c "
SELECT COUNT(DISTINCT table_schema) as total_schemas_com_class
FROM information_schema.tables
WHERE table_schema LIKE 'city_%'
  AND table_name = 'class';
"

# Ver quais schemas NÃO têm a constraint ainda
docker exec -it <container_id> psql -U postgres -d afirmeplay_dev -c "
SELECT t.table_schema
FROM information_schema.tables t
WHERE t.table_schema LIKE 'city_%'
  AND t.table_name = 'class'
  AND NOT EXISTS (
    SELECT 1
    FROM information_schema.table_constraints tc
    WHERE tc.table_schema = t.table_schema
      AND tc.table_name = 'class'
      AND tc.constraint_name = 'unique_class_name_per_school'
  )
ORDER BY t.table_schema;
"
```

---

## 🐛 Troubleshooting

### Se der erro "permission denied"

```bash
# Garantir que o usuário postgres tem permissão
docker exec -it <container_id> chown postgres:postgres /tmp/add_class_constraint.sql
```

### Para ver o que está sendo executado com mais detalhes

```bash
# Adicionar flag -v (verbose)
docker exec -it <container_id> psql -U postgres -d afirmeplay_dev -v ON_ERROR_STOP=0 -f /tmp/add_class_constraint.sql
```

### Se quiser rodar novamente após erro

O script é **idempotente** e seguro para rodar múltiplas vezes:

- Schemas já processados = já têm constraint (detectado e pulado)
- Schemas com erro = serão reprocessados na próxima execução
- Schemas pulados = continuarão sendo pulados (são vazios)

**Nota:** O script processa tudo em uma transação única. Se ocorrer um erro fatal que cancele a transação inteira, será necessário rodar novamente.

---

## ⚠️ Importante

### Comportamento do Script:

- ✅ **Renomeia automaticamente** duplicatas antes de adicionar a constraint
- ✅ **Pula schemas vazios** (sem tabela `class`) automaticamente
- ✅ **Não quebra** se a constraint já existir em algum schema
- ✅ **Continua processando** mesmo se um schema der erro (usa EXCEPTION handler)
- ⚠️ **Transação única:** Todas as alterações são commitadas ao final (ou rollback se houver erro fatal)
- ✅ Processa **todos os schemas `city_*`** automaticamente
- ✅ Você verá mensagens de progresso no console com emojis

### Schemas que serão pulados:

- Schemas `city_*` sem a tabela `class` (provavelmente schemas criados mas não populados)
- Aparecerão como "⚠️ Tabela class não existe - PULANDO"
- Serão listados no resumo final

---

## 📊 Output Esperado (Versão 2.0)

```
NOTICE:  ========================================
NOTICE:  Iniciando processamento de schemas city_*
NOTICE:  ========================================
NOTICE:
NOTICE:  📍 Processando schema: city_034b3bc3_8441_4344_b3f6_35d0727625a6
NOTICE:  ----------------------------------------
NOTICE:  ✅ Renomeadas 3 turmas duplicadas
NOTICE:  ✅ Constraint adicionada com sucesso
NOTICE:
NOTICE:  📍 Processando schema: city_56ab4f5d_179d_4a28_833c_cac5bb6e74cd
NOTICE:  ----------------------------------------
NOTICE:  ⚠️  Tabela class não existe - PULANDO
NOTICE:
NOTICE:  📍 Processando schema: city_08355961_d23e_47b7_a97a_ddde4207f2a5
NOTICE:  ----------------------------------------
NOTICE:  ✅ Nenhuma duplicata encontrada
NOTICE:  ✅ Constraint adicionada com sucesso
...
NOTICE:
NOTICE:  ========================================
NOTICE:  ✨ RESUMO FINAL
NOTICE:  ========================================
NOTICE:  📊 Total de schemas encontrados: 45
NOTICE:  ✅ Schemas processados com sucesso: 42
NOTICE:  ⚠️  Schemas pulados (sem tabela class): 3
NOTICE:  ❌ Schemas com erro: 0
NOTICE:  🔧 Total de turmas renomeadas: 12
NOTICE:
NOTICE:  📋 Schemas pulados:
NOTICE:     city_56ab4f5d_179d_4a28_833c_cac5bb6e74cd, city_test, city_empty
NOTICE:
NOTICE:  ✨ Processo concluído!
DO
```

---

## 🔄 Se precisar reverter (USE COM CUIDADO!)

```bash
# Remover a constraint de todos os schemas que a possuem
docker exec -it <container_id> psql -U postgres -d afirmeplay_dev <<'EOF'
DO $$
DECLARE
    schema_rec RECORD;
    removed_count INTEGER := 0;
BEGIN
    RAISE NOTICE '🗑️  Removendo constraints unique_class_name_per_school...';
    RAISE NOTICE '';

    FOR schema_rec IN
        SELECT DISTINCT table_schema
        FROM information_schema.table_constraints
        WHERE table_name = 'class'
          AND constraint_name = 'unique_class_name_per_school'
        ORDER BY table_schema
    LOOP
        EXECUTE format('
            ALTER TABLE %I.class
            DROP CONSTRAINT IF EXISTS unique_class_name_per_school',
            schema_rec.table_schema
        );
        RAISE NOTICE '✅ Removida de: %', schema_rec.table_schema;
        removed_count := removed_count + 1;
    END LOOP;

    RAISE NOTICE '';
    RAISE NOTICE '✨ Total removido: % schemas', removed_count;
END $$;
EOF
```

---

## 📝 Notas Adicionais

### Por que alguns schemas não têm a tabela `class`?

- Schemas podem ser criados antecipadamente (provisionamento)
- Schemas de teste ou sandbox
- Schemas antigos não mais utilizados
- Migration incompleto ou em andamento

### Isso é um problema?

**Não!** O script agora:

- Detecta automaticamente schemas vazios
- Pula eles sem causar erro
- Continua processando os demais
- Lista no final quais foram pulados para análise

### Posso rodar o script múltiplas vezes?

**Sim!** O script é **idempotente**:

- Não adiciona constraint duplicada (verifica antes)
- Não renomeia turmas já renomeadas (não cria duplicatas novas)
- Pula schemas já com constraint
- Safe para executar quantas vezes precisar

---

**Última atualização:** 18/02/2026 - Versão 2.0 (com tratamento de erros)
