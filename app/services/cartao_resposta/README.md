# Cartão Resposta — Documentação do Módulo

Este documento descreve o funcionamento do sistema de **cartões resposta** (answer sheets): geração de PDFs, correção por imagem e integração com rotas, Celery e MinIO.

---

## Índice

1. [Visão geral](#1-visão-geral)
2. [Estrutura do pacote](#2-estrutura-do-pacote)
3. [Dependências](#3-dependências)
4. [Componentes principais](#4-componentes-principais)
5. [Fluxo de geração de PDFs](#5-fluxo-de-geração-de-pdfs)
6. [Template e dados](#6-template-e-dados)
7. [Correção de cartões](#7-correção-de-cartões)
8. [Tasks Celery](#8-tasks-celery)
9. [Rotas que usam o módulo](#9-rotas-que-usam-o-módulo)
10. [Modelos de dados](#10-modelos-de-dados)
11. [Multitenancy e variáveis de ambiente](#11-multitenancy-e-variáveis-de-ambiente)
12. [Download (URL pré-assinada)](#12-download-url-pré-assinada)

---

## 1. Visão geral

O sistema permite:

- **Criar gabaritos** (configuração de prova: número de questões, blocos, disciplinas, respostas corretas).
- **Gerar PDFs** de cartões resposta (um por aluno), com QR Code, blocos de questões e alternativas configuráveis.
- **Corrigir** cartões a partir de foto/scan: detecção de QR Code, alinhamento, leitura de bolhas e gravação do resultado.
- **Download** do ZIP de cartões via URL pré-assinada (MinIO público: `files.afirmeplay.com.br`).

**Stack de geração:** Jinja2 (template HTML) → WeasyPrint (HTML → PDF). Um PDF por aluno; turmas processadas em paralelo via Celery (group + chord).

---

## 2. Estrutura do pacote

```
app/services/cartao_resposta/
├── __init__.py                    # Exporta AnswerSheetGenerator, AnswerSheetCorrectionService
├── README.md                      # Este arquivo
├── answer_sheet_generator.py     # Geração de PDFs (WeasyPrint + Jinja2 + QR)
├── answer_sheet_correction.py     # Correção legada (AnswerSheetGabarito + AnswerSheetResult)
├── answer_sheet_correction_service.py  # Serviço de correção (QR, bolhas, resultado)
├── correction_new_grid.py         # Corretor principal (nova grade; usado em physical_test e answer_sheet)
├── correction_n.py                # Corretor com template digital e _generate_individual_answer_sheet
├── coordinate_generator.py        # Geração de coordenadas (ROIs) das bolhas para correção
├── hierarchical_generator.py      # Escopo hierárquico (cidade → escola → série → turma)
├── block_01_coordinates_adjustment.json
├── block_02_coordinates_adjustment.json
├── block_03_coordinates_adjustment.json
└── block_04_coordinates_adjustment.json
```

**Template usado na geração:** `app/templates/answer_sheet.html` (carregado pelo `AnswerSheetGenerator` a partir de `app/templates/`).

---

## 3. Dependências

| Dependência    | Uso |
|----------------|-----|
| **WeasyPrint** | HTML → PDF |
| **Jinja2**     | Renderização do template `answer_sheet.html` |
| **qrcode**     | QR Code no cartão (student_id, gabarito_id/test_id) |
| **Celery**     | Geração assíncrona (group + chord) e upload |
| **MinIO** (S3) | Armazenamento do ZIP; URL pré-assinada para download |
| **OpenCV (cv2)** / **numpy** | Correção: detecção de QR, triângulos, bolhas |
| **Redis**      | Progresso gradual do job (progress_current, progress_percentage) |

---

## 4. Componentes principais

### 4.1 `answer_sheet_generator.py`

- **`AnswerSheetGenerator`**
  - **`generate_answer_sheets(...)`**  
    Fluxo legado: uma turma → um PDF multi-página (uma página por aluno). Concatena HTMLs, uma chamada WeasyPrint, salva um arquivo por turma. Mantido por compatibilidade.
  - **`generate_class_answer_sheets(...)`**  
    Fluxo atual: uma turma → um PDF por aluno. Usa `_generate_individual_answer_sheet` para cada aluno e salva em pasta por nome (município, escola, série, turma).
  - **`_generate_individual_answer_sheet(student, test_data, num_questions, use_blocks, blocks_config, questions_by_block, gabarito_id, questions_map)`**  
    Gera o PDF de um único aluno: dados do aluno, QR, renderiza `answer_sheet.html`, WeasyPrint → bytes. Também usado em `correction_n.py` para gerar template PDF.
  - **`_organize_questions_by_blocks(num_questions, blocks_config, questions_map)`**  
    Organiza questões em blocos (com ou sem disciplinas); usado pelo template.
  - **`_build_questions_map(num_questions, questions_options)`**  
    Monta o mapa de alternativas por questão (para o template).
  - **`_build_class_folder_path(base_output_dir, class_obj)`**  
    Cria e retorna o path da turma usando **nomes** (não IDs):  
    `municipio_{nome}/escola_{nome}/serie_{nome}/turma_{nome}/`.
  - **`_get_complete_student_data(student)`**  
    Retorna dict com id, name, class_name, grade_name, school_name, etc. Aceita objeto `Student` ou dict.
  - **`_generate_qr_code(student_id, test_id, gabarito_id)`**  
    Gera QR em base64 com `{"student_id": "...", "gabarito_id": "..."}` (ou test_id).

- **`sanitize_filename(name, max_length=80)`**  
  Função de módulo: normaliza string para nome de arquivo (acentos, caracteres inválidos, lowercase).

### 4.2 `coordinate_generator.py`

- **`CoordinateGenerator`**
  - **`generate_coordinates(num_questions, use_blocks, blocks_config, questions_options, warped_dimensions)`**  
    Gera coordenadas fixas (ROIs) das bolhas de resposta em pixels, para uso na correção. Usado na rota de criação de gabarito (coordenadas salvas no gabarito).

### 4.3 `answer_sheet_correction_service.py`

- **`AnswerSheetCorrectionService`**
  - **`corrigir_cartao_resposta(image_data: bytes)`**  
    Fluxo: decodifica imagem → detecta QR (student_id, gabarito_id) → valida aluno e gabarito → detecta triângulos e corrige perspectiva → detecta bolhas → compara com `correct_answers` do gabarito → calcula nota/proficiência → persiste em `AnswerSheetResult`.

### 4.4 `correction_new_grid.py`

- **`AnswerSheetCorrectionNewGrid`**
  - Corretor principal usado em rotas de correção (answer_sheet e physical_test). Método principal: **`corrigir_cartao_resposta(image_path=None, image_data=bytes, ...)`**. Usa constantes calibradas para o layout de `answer_sheet.html`.

### 4.5 `correction_n.py`

- Corretor que usa **template digital** (imagens de referência por bloco) e chama **`AnswerSheetGenerator()._generate_individual_answer_sheet`** para gerar PDF de template quando necessário. Não alterar a assinatura de `_generate_individual_answer_sheet`, pois é usada aqui.

### 4.6 `hierarchical_generator.py`

- **`HierarchicalAnswerSheetSheetGenerator`**
  - **`determine_generation_scope(state, city, school_id, grade_id, class_id, user)`**  
    Determina escopo (class | grade | school | city) e lista de turmas/escolas para validação. Usado em rota que valida escopo hierárquico.

---

## 5. Fluxo de geração de PDFs

### 5.1 Rota de geração

- **POST `/answer-sheets/generate`** (com contexto de cidade).
- Resolve escopo (município, escola, série ou turma) e monta a lista `classes_to_generate`.
- Cria diretório base: **`/app/tmp/answer_sheets/{job_id}`** (ou `ANSWER_SHEETS_TMP_BASE` no `.env`).
- Dispara um **Celery group** (uma task por turma) + **chord** (callback que monta o ZIP, faz upload e atualiza o job).

### 5.2 Task por turma: `generate_answer_sheets_single_class_async`

- Configura **`search_path`** do PostgreSQL para o schema da cidade (multitenancy).
- Chama **`AnswerSheetGenerator().generate_class_answer_sheets(class_id, base_output_dir, test_data, num_questions, use_blocks, blocks_config, correct_answers, gabarito_id, questions_options)`**.
- Atualiza progresso gradual: **`increment_answer_sheet_progress(batch_id, total_classes)`** (Redis) + **`update_answer_sheet_job(batch_id, {...})`**.
- Retorna apenas **`{class_id, total_students}`** (sem lista de paths).

### 5.3 Por turma: `generate_class_answer_sheets`

- Busca turma e alunos.
- Monta `questions_map` e `questions_by_block` (mesma lógica de `generate_answer_sheets`).
- Cria pasta da turma com **`_build_class_folder_path`** (nomes: municipio_*, escola_*, serie_*, turma_*).
- Para cada aluno:
  - **`_generate_individual_answer_sheet(...)`** → bytes do PDF.
  - Nome do arquivo: **`{sanitize_filename(nome)}_{serie}_{turma}.pdf`**.
  - Salva na pasta da turma.

### 5.4 Chord: `build_zip_and_upload_answer_sheets`

- Recebe os resultados do group (lista de `{class_id, total_students}`).
- Percorre **`base_output_dir`** e cria um **ZIP** mantendo a estrutura de pastas.
- Faz **upload** do ZIP para o MinIO (bucket `answer-sheets`, objeto `gabaritos/batch/{batch_id}/cartoes.zip`).
- Atualiza o **job** no banco e os **gabaritos** (minio_url, minio_object_name, scope, totais, etc.).
- Remove **`base_output_dir`** após sucesso.

### 5.5 Estrutura de pastas no ZIP

```
/app/tmp/answer_sheets/{job_id}/
  municipio_{nome_cidade}/
    escola_{nome_escola}/
      serie_{nome_serie}/
        turma_{nome_turma}/
          {nome_aluno}_{serie}_{turma}.pdf
```

Exemplo: `municipio_jaru/escola_em_joao_silva/serie_5_ano/turma_a/joao_silva_5_ano_turma_a.pdf`.

---

## 6. Template e dados

### 6.1 Template

- **Arquivo:** `app/templates/answer_sheet.html`.
- **Carregado por:** `AnswerSheetGenerator` (Jinja2 `FileSystemLoader` em `app/templates/`).

### 6.2 Dados enviados ao template

- **`test_data`**: `title`, `municipality`, `state`, `grade_name`, `department`, `institution`, `id`, etc.
- **`student`**: dados do aluno + **`qr_code`** (base64 do PNG do QR).
- **`questions_by_block`**: lista de blocos; cada bloco tem `block_number`, `subject_name`, `questions` (lista de `{question_number, options}`), `start_question_num`, `end_question_num`.
- **`questions_map`**: `{num_questao: [alternativas]}` (ex.: `{1: ['A','B','C','D'], 2: ['A','B','C']}`).
- **`blocks_config`**: configuração de blocos (topology, num_blocks, questions_per_block, etc.).
- **`total_questions`**: número total de questões.
- **`generated_date`**: string de data/hora.

Não alterar a estrutura desses dados nem a lógica de blocos/QR no gerador; o template e a correção dependem deles.

---

## 7. Correção de cartões

- **QR Code:** contém `student_id` e `gabarito_id` (ou `test_id`). A correção usa o `gabarito_id` para buscar `AnswerSheetGabarito` e suas `correct_answers` e coordenadas.
- **Coordenadas:** geradas por `CoordinateGenerator` e salvas no gabarito; usadas para localizar as bolhas na imagem corrigida.
- **Arquivos de ajuste:** `block_01_coordinates_adjustment.json` … `block_04_...` podem ser usados para fine-tuning por bloco.
- **Serviços de correção:**
  - **AnswerSheetCorrectionService** e **AnswerSheetCorrectionNewGrid** são usados nas rotas de correção (answer_sheet e physical_test).
  - **correction_n.py** usa template digital e **`_generate_individual_answer_sheet`** para gerar PDF de referência; não alterar a assinatura desse método.

---

## 8. Tasks Celery

| Task | Descrição |
|------|------------|
| **`generate_answer_sheets_single_class_async`** | Uma turma: gera 1 PDF por aluno, salva em `base_output_dir`, atualiza progresso (Redis + job), retorna `{class_id, total_students}`. |
| **`build_zip_and_upload_answer_sheets`** | Chord: monta ZIP a partir de `base_output_dir`, upload MinIO, atualiza job e gabaritos, remove diretório. |
| **`generate_answer_sheets_batch_async`** | Fluxo legado: uma task processa todas as turmas em sequência, um PDF multi-página por turma; ainda disponível, mas a rota principal usa group + chord. |
| **`upload_answer_sheets_zip_async`** | Upload isolado de ZIP (usado em outros fluxos se necessário). |

**App Celery:** `app.report_analysis.celery_app.celery_app`.  
**Progresso:** `app.services.progress_store.increment_answer_sheet_progress` e `update_answer_sheet_job` (Redis + DB).

---

## 9. Rotas que usam o módulo

- **`app/routes/answer_sheet_routes.py`**
  - Blueprint: **`answer_sheets`**, prefixo **`/answer-sheets`**.
  - Geração: **POST `/generate`** (group + chord, `generate_class_answer_sheets`).
  - Listagem de gabaritos: **GET** (retorna `download_url` para link de download com redirect para presigned).
  - Download: **GET `/gabarito/<id>/download`** (gera URL pré-assinada; com `?redirect=1` faz 302 para essa URL).
  - Criação de gabarito: **POST** (usa `CoordinateGenerator` para coordenadas).
  - Correção: usa **AnswerSheetCorrectionService** e **AnswerSheetCorrectionNewGrid**.
  - Status do job: **GET `/jobs/<job_id>/status`** (progresso gradual via Redis/DB).
- **`app/routes/physical_test_routes.py`**
  - Usa **AnswerSheetCorrectionNewGrid** para correção de cartão em provas físicas.
- **HierarchicalAnswerSheetGenerator** é usado em rota de validação de escopo (answer_sheet_routes).

---

## 10. Modelos de dados

- **AnswerSheetGabarito**  
  Gabarito da prova: `num_questions`, `correct_answers`, `use_blocks`, `blocks_config`, `questions_options`, coordenadas, `minio_url`, `minio_object_name`, `minio_bucket`, `scope_type`, etc.
- **AnswerSheetResult**  
  Resultado da correção por aluno: vínculo com gabarito e aluno, respostas marcadas, nota, etc.
- **AnswerSheetGenerationJob**  
  Job de geração: `job_id`, `task_ids`, `total`, `progress_current`, `progress_percentage`, `status`, `gabarito_id`, `city_id`, etc. (tabela em `public`).
- **Student**, **Class**, **School**, **Grade**, **City**  
  Usados pelo gerador e pela correção (dados do aluno, turma, escola, série, cidade).

---

## 11. Multitenancy e variáveis de ambiente

- **PostgreSQL:** antes de gerar PDFs por turma, a task configura **`search_path`** para o schema da cidade: `city_{city_id_sem_hífens}`.
- **Diretório de saída:** base **`/app/tmp/answer_sheets/{job_id}`**. Opcional: **`ANSWER_SHEETS_TMP_BASE`** no `.env` (ex.: em dev, outro path).
- **MinIO:** endpoint interno (upload) e client público (presigned) em `app/services/storage/minio_service.py`. URL pré-assinada usa host **`files.afirmeplay.com.br`** (configurável no serviço se necessário).

---

## 12. Download (URL pré-assinada)

- **Listagem de gabaritos:** cada item pode ter **`download_url`**: link para a API com `?redirect=1` (ex.: `https://api.../answer-sheets/gabarito/<id>/download?redirect=1`). O front deve usar **`download_url`** (e não `minio_url`) para o botão de baixar.
- **GET `/answer-sheets/gabarito/<id>/download`:**  
  - Gera URL pré-assinada (MinIO, host público) com **`MinIOService.get_presigned_url()`**.  
  - Com **`?redirect=1`**: responde com **302** para a URL pré-assinada (o navegador baixa do MinIO público).  
  - Sem `redirect=1`: responde JSON com **`download_url`** (presigned) e demais metadados.
- **`minio_url`** no banco pode ser a URL interna do MinIO; não deve ser usada como link direto no navegador. O link correto para o usuário é sempre via **`download_url`** da listagem ou da rota de download.

---

*Documento gerado para referência do sistema de cartão resposta em uso no projeto.*
