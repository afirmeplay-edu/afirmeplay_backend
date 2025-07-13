# Script de Migração - InnovaPlay Backend

Este script aplica todas as alterações de banco de dados realizadas durante o desenvolvimento do sistema de avaliações.

## 📋 Alterações Incluídas

### 1. Remoção da coluna `actual_start_time`
- Remove a coluna `actual_start_time` da tabela `test_sessions`
- Simplifica o controle de tempo (agora gerenciado pelo frontend)

### 2. Campos de Correção Manual
Adiciona os seguintes campos:

**Tabela `student_answers`:**
- `is_correct` (BOOLEAN) - Se a resposta está correta
- `manual_score` (DECIMAL) - Pontuação manual atribuída
- `feedback` (TEXT) - Feedback específico da questão
- `corrected_by` (VARCHAR) - ID do professor que corrigiu
- `corrected_at` (TIMESTAMP) - Data/hora da correção

**Tabela `test_sessions`:**
- `manual_score` (DECIMAL) - Pontuação manual total
- `feedback` (TEXT) - Feedback geral da avaliação
- `corrected_by` (VARCHAR) - ID do professor que corrigiu
- `corrected_at` (TIMESTAMP) - Data/hora da correção

### 3. Foreign Keys
- Adiciona foreign keys para os campos `corrected_by` referenciando a tabela `users`

### 4. Índices de Performance
Cria índices para melhorar a performance das consultas:
- `idx_test_sessions_student_test` - (student_id, test_id)
- `idx_test_sessions_status` - (status)
- `idx_student_answers_student_test` - (student_id, test_id)
- `idx_student_answers_question` - (question_id)
- `idx_test_sessions_submitted_at` - (submitted_at)
- `idx_test_sessions_started_at` - (started_at)

### 5. View para Correção
- Cria a view `evaluations_for_correction` para facilitar consultas de avaliações prontas para correção

### 6. Atualização de Status
- Corrige valores de status vazios ou nulos para valores padrão

## 🚀 Como Executar

### Pré-requisitos

1. **Python 3.7+** instalado
2. **PostgreSQL** configurado
3. **Backup** do banco de dados (IMPORTANTE!)

### Instalação

1. Instale as dependências:
```bash
pip install -r requirements_migration.txt
```

2. Configure as credenciais do banco no arquivo `migration_all_changes.py`:
```python
DB_CONFIG = {
    'host': 'localhost',
    'database': 'innovaplay_db',
    'user': 'postgres',
    'password': 'sua_senha_aqui',
    'port': 5432
}
```

### Execução

1. Execute o script:
```bash
python migration_all_changes.py
```

2. Confirme a execução quando solicitado

### Verificação

Após a execução, verifique se:

1. A coluna `actual_start_time` foi removida da tabela `test_sessions`
2. Os novos campos foram adicionados nas tabelas `student_answers` e `test_sessions`
3. Os índices foram criados
4. A view `evaluations_for_correction` foi criada

## ⚠️ Avisos Importantes

1. **SEMPRE faça backup** antes de executar
2. Teste primeiro em um ambiente de desenvolvimento
3. O script é idempotente (pode ser executado múltiplas vezes sem problemas)
4. Se alguma migração falhar, o script para e faz rollback

## 🔧 Solução de Problemas

### Erro de Conexão
- Verifique as credenciais do banco
- Confirme se o PostgreSQL está rodando
- Verifique se o banco existe

### Erro de Permissão
- Certifique-se de que o usuário tem permissões para:
  - ALTER TABLE
  - CREATE INDEX
  - CREATE VIEW
  - DROP COLUMN

### Coluna já existe
- O script verifica se as colunas existem antes de criar
- Se uma coluna já existe, ela é pulada

## 📊 Logs

O script gera logs detalhados mostrando:
- ✅ Operações bem-sucedidas
- ❌ Erros encontrados
- ℹ️ Informações sobre operações puladas
- ⚠️ Avisos sobre operações que não puderam ser executadas

## 🔄 Rollback

Se precisar reverter as alterações, você precisará:

1. Restaurar o backup
2. Ou executar comandos SQL manualmente para reverter cada alteração

## 📞 Suporte

Se encontrar problemas:
1. Verifique os logs gerados
2. Confirme se o banco está acessível
3. Verifique as permissões do usuário
4. Teste em um banco de desenvolvimento primeiro 