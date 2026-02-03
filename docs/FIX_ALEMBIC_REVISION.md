# Corrigir erro "Can't locate revision identified by 'e7b299c54c80'"

O banco está marcado com uma revisão que não existe mais no projeto.

## Passos

1. **Marcar o banco na revisão atual do código (e65e9db85b23):**
   ```bash
   flask db stamp e65e9db85b23
   ```
   Isso só atualiza a tabela `alembic_version`; não executa migrations.

2. **Aplicar as migrations pendentes (incluindo student_coins):**
   ```bash
   flask db upgrade
   ```

## Quando usar

- Use só se o schema do banco **já estiver** em dia com as migrations até `e65e9db85b23` (todas as tabelas que existem no código já existem no banco).
- Se o banco for novo ou estiver desatualizado, em vez de `stamp` use `flask db upgrade` a partir de um backup ou de um banco zerado com `flask db upgrade` desde o início.

## Se ainda der erro

Conferir o que está gravado no banco:
```sql
SELECT * FROM alembic_version;
```
Depois ajustar com `flask db stamp <revision_que_existe>`.
