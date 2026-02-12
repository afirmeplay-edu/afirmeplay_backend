# Passo a passo: migração afirmeplay_dev → afirmeplay_prod

Execute manualmente, na ordem. **Nada é removido de afirmeplay_dev** (apenas leitura).  
Referência de tabelas: `SCHEMA_TABLES_MAPPING.md`.

---

## Variáveis que você vai usar

Ajuste conforme seu ambiente (PowerShell ou CMD):

```powershell
$HOST_DEV = "localhost"      # host do banco dev
$HOST_PROD = "localhost"     # host do banco prod (pode ser o mesmo)
$USER_DEV = "seu_usuario"
$USER_PROD = "seu_usuario"
$PORT = "5432"
```

Em bash, use `export HOST_DEV=...` etc.

---

## Passo 1 — Backups (obrigatório)

Execute **antes** de qualquer alteração em prod.

```powershell
# Backup completo afirmeplay_dev (só leitura no dev)
pg_dump -h $HOST_DEV -U $USER_DEV -d afirmeplay_dev -F c -b -v -f backup_afirmeplay_dev_YYYYMMDD.dump

# Backup completo afirmeplay_prod (se já existir dados)
pg_dump -h $HOST_PROD -U $USER_PROD -d afirmeplay_prod -F c -b -v -f backup_afirmeplay_prod_antes_YYYYMMDD.dump
```

Substitua `YYYYMMDD` pela data. Guarde os arquivos em local seguro.

---

## Passo 2 — Garantir que o banco afirmeplay_prod existe

Se o banco de produção ainda não existir:

```sql
-- Conectar em algum banco (ex: postgres) e executar:
CREATE DATABASE afirmeplay_prod;
```

Se já existir e estiver vazio ou puder ser recriado, pode usar como está. **Não drope o prod se já tiver dados que precise manter** — nesse caso pule a criação.

---

## Passo 3 — Estrutura do schema `public` em prod (somente tabelas globais + question)

Exportar **apenas a estrutura** (sem dados) das tabelas que ficam no `public` a partir do **dev** e importar no **prod**.

Tabelas: `alembic_version`, `users`, `user_settings`, `user_quick_links`, `manager`, `city`, `education_stage`, `grade`, `subject`, `skills`, `games`, `game_classes`, `competition_templates`, `competition_rewards`, `certificate_templates`, `play_tv_videos`, `question`.

**Um comando por tabela** (ou agrupe várias `-t` no mesmo `pg_dump`). Exemplo agrupado:

```powershell
pg_dump -h $HOST_DEV -U $USER_DEV -d afirmeplay_dev --schema-only `
  -t public.alembic_version `
  -t public.users `
  -t public.user_settings `
  -t public.user_quick_links `
  -t public.manager `
  -t public.city `
  -t public.education_stage `
  -t public.grade `
  -t public.subject `
  -t public.skills `
  -t public.games `
  -t public.game_classes `
  -t public.competition_templates `
  -t public.competition_rewards `
  -t public.certificate_templates `
  -t public.play_tv_videos `
  -t public.question `
  | psql -h $HOST_PROD -U $USER_PROD -d afirmeplay_prod
```

**Se der erro de tipo/enum já existente**, ignore ou crie os tipos antes. Se o prod já tiver parte da estrutura (ex.: Alembic), pode ser necessário ajustar: exportar só as tabelas que faltam.

---

## Passo 4 — Dados das tabelas globais (dev → prod.public)

Carregar **dados** das mesmas tabelas, na **ordem** que respeite FKs (ex.: `city` antes de quem referencia `city_id`).

**4.1 — Tabelas sem dependência de `users` (carregar primeiro)**

```powershell
pg_dump -h $HOST_DEV -U $USER_DEV -d afirmeplay_dev --data-only `
  -t public.alembic_version `
  -t public.education_stage `
  -t public.grade `
  -t public.subject `
  -t public.skills `
  | psql -h $HOST_PROD -U $USER_PROD -d afirmeplay_prod
```

**4.2 — City (necessário para FKs e para o 0001)**

```powershell
pg_dump -h $HOST_DEV -U $USER_DEV -d afirmeplay_dev --data-only -t public.city `
  | psql -h $HOST_PROD -U $USER_PROD -d afirmeplay_prod
```

**4.3 — users (antes de games e game_classes)**

`games` tem FK `userId` → `users`; então **users deve ser carregado antes de games**.

```powershell
pg_dump -h $HOST_DEV -U $USER_DEV -d afirmeplay_dev --data-only `
  -t public.users `
  -t public.user_settings `
  -t public.user_quick_links `
  -t public.manager `
  -t public.competition_templates `
  -t public.competition_rewards `
  -t public.certificate_templates `
  -t public.play_tv_videos `
  | psql -h $HOST_PROD -U $USER_PROD -d afirmeplay_prod
```

**4.4 — games e game_classes (depois de users)**

```powershell
pg_dump -h $HOST_DEV -U $USER_DEV -d afirmeplay_dev --data-only `
  -t public.games `
  -t public.game_classes `
  | psql -h $HOST_PROD -U $USER_PROD -d afirmeplay_prod
```

**4.5 — question (public — questões de admin)**

```powershell
pg_dump -h $HOST_DEV -U $USER_DEV -d afirmeplay_dev --data-only -t public.question `
  | psql -h $HOST_PROD -U $USER_PROD -d afirmeplay_prod
```

Se houver conflito de chave (ex.: id já existe), corrija manualmente ou use `--clean` no restore (cuidado: pode apagar dados existentes no prod). O ideal é prod vazio até aqui.

---

## Passo 5 — Rodar o script 0001 em afirmeplay_prod

O script cria os schemas `city_<id>` e as tabelas em cada um. Ele usa `DATABASE_URL` do `.env`.

**5.1 — Apontar DATABASE_URL para prod**

Edite `app/.env` e deixe:

```env
DATABASE_URL=postgresql://USUARIO:SENHA@HOST:PORT/afirmeplay_prod
```

**5.2 — Executar (dry-run opcional)**

```powershell
cd c:\Users\Artur Calderon\Documents\Programming\innovaplay_backend
python migrations_multitenant/0001_init_city_schemas.py --dry-run
```

**5.3 — Executar de verdade**

```powershell
python migrations_multitenant/0001_init_city_schemas.py
```

Confirme quando pedir (ex.: digitar `CONFIRMO`).

**5.4 — Validação**

```powershell
python migrations_multitenant/validate_migration.py
```

---

## Passo 6 — Tabela `question` em cada schema city_xxx (se o 0001 não criar)

O 0001 atual **não** cria a tabela `question` dentro de `city_xxx`. Como na arquitetura desejada existe `public.question` (admin) e `city_xxx.question` (por município), é preciso criar `city_xxx.question` em cada schema.

**Opção A — Copiar estrutura a partir de `public.question` no prod**

Para cada schema `city_<id>` (liste com):

```sql
SELECT schema_name FROM information_schema.schemata WHERE schema_name LIKE 'city_%';
```

Em cada um, criar a tabela com a mesma estrutura de `public.question` (sem dados). Exemplo genérico (ajuste colunas conforme seu `public.question`):

```sql
-- Conectar em afirmeplay_prod e, para cada schema (ex.: city_abc_def):
CREATE TABLE city_abc_def.question (LIKE public.question INCLUDING ALL);
-- Repetir para cada city_xxx
```

**Opção B — Script que lista os schemas e executa CREATE TABLE ... (LIKE public.question)**  
Você pode fazer um script Python/psql que leia os schemas e execute o `CREATE TABLE ... (LIKE public.question)` em cada um.

---

## Passo 7 — Migrar dados por cidade (dev.public → prod.city_xxx)

Os dados que hoje estão em tabelas no `public` do dev (por exemplo `school`, `class`, `student`, …) devem ser **copiados** para os schemas `city_<id>` no prod, **por city_id**, **sem remover nada do dev**.

Tabelas a migrar para cada `city_xxx` (conforme `SCHEMA_TABLES_MAPPING.md`):

- school, school_course, school_teacher, class, class_subject, class_test, teacher, teacher_class, student, student_password_log
- test, test_questions, test_sessions, evaluation_results, answer_sheet_gabaritos, answer_sheet_results, student_answers, student_test_olimpics
- forms, form_questions, form_coordinates, form_recipients, form_responses, form_result_cache
- competitions, competition_enrollments, competition_results, competition_ranking_payouts
- calendar_events, calendar_event_users, calendar_event_targets
- coin_transactions, student_coins
- physical_test_forms, physical_test_answers
- plantao_online, plantao_schools
- play_tv_video_classes, play_tv_video_schools
- report_aggregates
- question (dados por cidade, se houver em dev com owner_city_id ou equivalente)

**Ordem sugerida** (respeitar FKs):

1. school
2. school_course, teacher
3. school_teacher, class
4. class_subject, teacher_class, student
5. student_password_log
6. test
7. test_questions, class_test, student_test_olimpics
8. test_sessions, student_answers, evaluation_results
9. answer_sheet_gabaritos, answer_sheet_results
10. physical_test_forms, physical_test_answers
11. forms, form_questions, form_coordinates, form_recipients, form_responses, form_result_cache
12. competitions
13. competition_enrollments, competition_results, competition_ranking_payouts
14. calendar_events, calendar_event_users, calendar_event_targets
15. student_coins, coin_transactions
16. plantao_online, plantao_schools
17. play_tv_video_classes, play_tv_video_schools
18. report_aggregates
19. question (por cidade)

**Como fazer na prática:**

- **Script Python** (recomendado): um script que conecta em dev (somente leitura) e em prod, para cada cidade lê da tabela em `public` com `WHERE city_id = ...` e insere no schema `city_<id>` correspondente. Você pode criar `migrations_multitenant/0002_copy_city_data.py` e executar manualmente.
- **Manual com pg_dump + filtro**: mais trabalhoso; exige views temporárias no dev por cidade ou export/import por tabela e por city_id.

Não remova nem altere dados no dev; apenas leia e escreva no prod.

---

## Passo 8 — Validação final em prod

**8.1 — Validação do script**

```powershell
# Com DATABASE_URL ainda apontando para afirmeplay_prod
python migrations_multitenant/validate_migration.py
```

**8.2 — Conferência manual (exemplo em SQL)**

Conectar em `afirmeplay_prod` e conferir contagens, por exemplo:

```sql
-- Globais
SELECT 'city' AS t, COUNT(*) FROM public.city
UNION ALL SELECT 'users', COUNT(*) FROM public.users
UNION ALL SELECT 'question', COUNT(*) FROM public.question;

-- Por cidade (troque o schema pelo que existir)
SELECT COUNT(*) FROM city_<id>.school;
SELECT COUNT(*) FROM city_<id>.student;
```

Compare com contagens equivalentes no dev (ex.: `SELECT COUNT(*) FROM public.school WHERE city_id = '...'`) para garantir que nada ficou de fora.

**8.3 — Voltar DATABASE_URL para o ambiente desejado**

Depois de tudo, ajuste de novo o `app/.env` para o banco que a aplicação deve usar no dia a dia (dev ou prod).

---

## Resumo da ordem de execução

| #   | O que fazer                                                                               |
| --- | ----------------------------------------------------------------------------------------- |
| 1   | Backups de afirmeplay_dev e afirmeplay_prod                                               |
| 2   | Garantir que afirmeplay_prod existe                                                       |
| 3   | Estrutura do public em prod (schema-only, só tabelas globais + question)                  |
| 4   | Dados das tabelas globais em prod (alembic_version, city, users, manager, question, etc.) |
| 5   | DATABASE_URL → prod; rodar 0001_init_city_schemas.py; validate_migration.py               |
| 6   | Criar tabela question em cada city_xxx (se o 0001 não criar)                              |
| 7   | Migrar dados por city_id de dev.public para prod.city_xxx (script ou processo manual)     |
| 8   | Validação final e volta do DATABASE_URL                                                   |

Nenhum passo remove ou altera dados em **afirmeplay_dev**; apenas leitura (pg_dump / SELECT) no dev.
