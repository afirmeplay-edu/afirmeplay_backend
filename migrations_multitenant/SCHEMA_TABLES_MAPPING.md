# Mapeamento de Tabelas por Schema — Multi-Tenant

Referência definitiva para migração **afirmeplay_dev → afirmeplay_prod**: quais tabelas ficam no `public` e quais em cada `city_xxx`.  
**Nenhum dado deve ser removido de afirmeplay_dev.**

---

## 1. Tabelas no schema `public` (globais)

Estas tabelas ficam **somente** no `public` em produção:

| Tabela                  |
| ----------------------- |
| `alembic_version`       |
| `users`                 |
| `user_settings`         |
| `user_quick_links`      |
| `manager`               |
| `city`                  |
| `education_stage`       |
| `grade`                 |
| `subject`               |
| `skills`                |
| `games`                 |
| `game_classes`          |
| `competition_templates` |
| `competition_rewards`   |
| `certificate_templates` |
| `play_tv_videos`        |

---

## 2. Tabela `question` — duas tabelas (public + city_xxx)

- **`public.question`**
    - Apenas admin pode salvar questões.
    - Fica no schema `public`.

- **`city_xxx.question`**
    - Apenas usuários do município podem salvar.
    - Existe uma tabela `question` em cada schema `city_<id>`.

- **Listagem para o usuário:**
    - Na hora de listar questões, o usuário recebe dados **das duas fontes**: `public.question` + `city_xxx.question` (do município dele).

Ou seja: são **duas tabelas distintas** (não a mesma tabela compartilhada); a aplicação deve unir os resultados na listagem.

---

## 3. Tabelas em cada schema `city_xxx` (por município)

Em cada schema `city_<id>` devem existir **somente** estas tabelas:

### Escola / turmas / professores / alunos

| Tabela                 |
| ---------------------- |
| `school`               |
| `school_course`        |
| `school_teacher`       |
| `class`                |
| `class_subject`        |
| `class_test`           |
| `teacher`              |
| `teacher_class`        |
| `student`              |
| `student_password_log` |

### Provas / avaliações

| Tabela                   |
| ------------------------ |
| `test`                   |
| `test_questions`         |
| `test_sessions`          |
| `evaluation_results`     |
| `answer_sheet_gabaritos` |
| `answer_sheet_results`   |
| `student_answers`        |
| `student_test_olimpics`  |

### Formulários

| Tabela              |
| ------------------- |
| `forms`             |
| `form_questions`    |
| `form_coordinates`  |
| `form_recipients`   |
| `form_responses`    |
| `form_result_cache` |

### Competições

| Tabela                        |
| ----------------------------- |
| `competitions`                |
| `competition_enrollments`     |
| `competition_results`         |
| `competition_ranking_payouts` |

### Calendário

| Tabela                   |
| ------------------------ |
| `calendar_events`        |
| `calendar_event_users`   |
| `calendar_event_targets` |

### Moedas

| Tabela              |
| ------------------- |
| `coin_transactions` |
| `student_coins`     |

### Físico / plantão / play TV / relatórios

| Tabela                  |
| ----------------------- |
| `physical_test_forms`   |
| `physical_test_answers` |
| `plantao_online`        |
| `plantao_schools`       |
| `play_tv_video_classes` |
| `play_tv_video_schools` |
| `report_aggregates`     |

### Questões (por cidade)

| Tabela     |
| ---------- |
| `question` |

---

## 4. Resumo rápido

- **Public:** 16 tabelas listadas na seção 1 + `question` (admin).
- **Por cidade (`city_xxx`):** 37 tabelas listadas na seção 3, incluindo `question` (usuários do município).
- **Regra de listagem:** `question` do usuário = união de `public.question` + `city_xxx.question`.

Use este mapeamento ao executar manualmente o plano de migração (backup, estrutura em prod, dados globais, 0001 em prod, migração de dados por city_id).
