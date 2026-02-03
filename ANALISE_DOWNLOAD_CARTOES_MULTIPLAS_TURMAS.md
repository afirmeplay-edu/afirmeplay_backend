# Análise: Download de cartões para várias turmas (escola)

## Comportamento esperado

- **1 PDF por turma**, com **1 página por aluno**.
- Ex.: Escola com 1 série, Turma A (3 alunos) e Turma B (1 aluno) → 2 PDFs (um de 3 páginas, outro de 1 página). O download do gabarito deve entregar **um único artefato** (ex.: ZIP) contendo esses 2 PDFs.

## O que o código faz hoje

### 1. Geração (POST `/generate` com `school_id`)

- Cria **1 gabarito** (scope_type = `school`, `class_id` = None).
- Dispara **1 task Celery por turma** (no seu caso: 2 tasks — Turma A e Turma B).
- Cada task gera **1 PDF por turma** (N páginas = N alunos), como desejado.

### 2. Upload por task (`answer_sheet_tasks.py`)

- Cada task faz upload do PDF em:  
  `gabaritos/{gabarito_id}/{class_id}/cartoes.pdf`
- Em seguida atualiza o **mesmo** registro de gabarito:
    - **Só a primeira task** que termina preenche `minio_url` e `minio_object_name` (trecho `if not gabarito.minio_url`).
    - Ou seja: o link de download do gabarito passa a apontar para **um único PDF** (o da turma cuja task terminou primeiro), e não para um ZIP com todas as turmas.

### 3. Consolidação (`consolidate_answer_sheets_to_zip`)

- **Cada** task que termina agenda **uma** consolidação com `countdown=30`.
- A consolidação lista objetos em `gabaritos/{gabarito_id}/` (todos os `.../cartoes.pdf`), baixa os PDFs, monta um ZIP e atualiza o gabarito com `minio_object_name` = `gabaritos/{gabarito_id}/cartoes.zip`.
- Problemas:
    - Se a consolidação rodar **antes** da outra task terminar, ela vê só 1 PDF e gera um ZIP com 1 arquivo; o usuário que baixar nesse momento recebe só uma turma.
    - Duas tasks → duas consolidações agendadas; a segunda pode rodar com 2 PDFs e “corrigir” o ZIP, mas isso é condicionado ao tempo e à ordem de execução (race).

### 4. Download (GET `/gabarito/<gabarito_id>/download`)

- Retorna URL pré-assinada para **um único objeto**: `gabarito.minio_object_name`.
- Para escopo escola/série:
    - Até a primeira consolidação rodar, esse objeto é o **PDF de uma turma só** (a que atualizou o gabarito primeiro).
    - Depois da consolidação, passa a ser o **ZIP** (se a consolidação tiver visto todos os PDFs).

## Por que no seu caso “os cartões vêm separados” / só uma turma

1. **Download apontando para um único PDF**  
   O gabarito fica com `minio_object_name` = path de um PDF de turma (ex.: `.../957e3216-.../cartoes.pdf`). Quem usa o link de download recebe só esse PDF (no log, Turma B).

2. **Possível execução de uma task só**  
   No log do Celery que você colou aparece **apenas** a Turma B. Pode ser que:
    - só uma task tenha sido disparada (ex.: `Class.query.filter_by(school_id=school_id)` retornou só uma turma), ou
    - a Turma A tenha rodado em outro worker/outro momento e não entrou no trecho de log.

3. **Consolidação com apenas 1 PDF**  
   Se a consolidação rodar quando só existir o PDF da Turma B no MinIO, o ZIP gerado terá só 1 arquivo; o download do gabarito continuará “separado” (uma turma só).

## Resumo dos pontos a corrigir (sem alterar código ainda)

| #   | Ponto                                                                                                                                                                                                    | Onde                                                                         |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| 1   | Para escopo `school`/`grade`, **não** atualizar o gabarito com o PDF de uma turma específica; deixar `minio_url`/`minio_object_name` apenas para o ZIP gerado na consolidação.                           | `answer_sheet_tasks.py` (trecho que faz upload e atualiza o gabarito)        |
| 2   | Consolidar **uma única vez** quando **todas** as tasks do job tiverem terminado (ex.: checando job/tasks no `progress_store` ou número esperado de turmas), em vez de agendar uma consolidação por task. | `answer_sheet_tasks.py` (agendamento da consolidação)                        |
| 3   | Garantir que, ao selecionar escola, **todas** as turmas da escola sejam listadas e que uma task seja disparada para cada uma.                                                                            | `answer_sheet_routes.py` (montagem de `classes_to_generate` e loop de tasks) |
| 4   | (Opcional) Na consolidação, validar que o número de PDFs encontrados no MinIO bate com o número de turmas do gabarito/job; se faltar PDF, re-agendar consolidação com delay.                             | `consolidate_answer_sheets_to_zip`                                           |

## Arquivos envolvidos

- `app/routes/answer_sheet_routes.py` — escopo (school/grade/class), criação do gabarito, disparo das tasks.
- `app/services/celery_tasks/answer_sheet_tasks.py` — geração por turma, upload do PDF, atualização do gabarito, agendamento da consolidação; task `consolidate_answer_sheets_to_zip`.
- `app/services/cartao_resposta/answer_sheet_generator.py` — geração do PDF (1 PDF por turma, 1 página por aluno); esse comportamento está correto.
- `app/models/answerSheetGabarito.py` — modelo com `minio_url`, `minio_object_name`, etc.

Nada foi alterado no código; esta análise serve de base para as correções quando você quiser implementá-las.
