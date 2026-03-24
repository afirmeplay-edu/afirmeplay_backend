# Relatório de Análise: Performance na Geração de PDFs das Provas

**Data:** 2025-03-16  
**Escopo:** `app/physical_tests/` e fluxo de geração de PDFs com WeasyPrint/Celery.  
**Objetivo:** Investigar se o HTML completo da prova é renderizado e se imagens do MinIO são baixadas novamente para cada aluno.  
**Regra:** Nenhum código foi alterado; apenas análise.

---

## 1. Resumo executivo

- **Não existe uma task Celery por aluno.** Existe uma única task que processa todos os alunos em sequência.
- **O fluxo atual usa Architecture 4 (arch4):** a prova base (capa + questões) é renderizada **uma vez**; por aluno só é renderizada **uma página OMR** (cartão-resposta), depois é feito o merge com o PDF base.
- **O HTML completo da prova (capa + questões) não é renderizado novamente para cada aluno.** Só é renderizado uma vez antes do loop de alunos.
- **As imagens do MinIO são usadas uma vez** (na fase de preparação, ao montar as questões e fazer o inline em base64). Existe cache por instância do gerador (`_image_data_uri_cache`). No fluxo arch4 não há chamadas que baixem imagens dentro do loop por aluno.
- O tempo alto por aluno (~80 s) e os logs do WeasyPrint (“Ignored clip-path…”) e do MinIO (“Arquivo baixado…”) são coerentes com: **(1)** uma única renderização pesada do PDF base (muitas questões/imagens) no início; **(2)** N renderizações WeasyPrint da página OMR (uma por aluno); **(3)** downloads do MinIO concentrados na fase única de inline das imagens. A ordem dos logs pode dar a impressão de “por aluno” se muitas imagens forem baixadas nessa fase única.

---

## 2. Tasks Celery relacionadas à geração de provas/cartões/kits

### 2.1 Tasks encontradas

| Task | Arquivo | Função | Uso |
|------|---------|--------|-----|
| `physical_test_tasks.generate_physical_forms_async` | `app/physical_tests/tasks.py` | `generate_physical_forms_async` | Geração de formulários físicos (prova + cartão) para todos os alunos da prova. |
| `physical_test_tasks.upload_physical_test_zip_async` | `app/physical_tests/tasks.py` | `upload_physical_test_zip_async` | Apenas upload do ZIP para o MinIO; não gera PDF. |

Não há tasks separadas para “geração de cartões” ou “kits” além da geração de formulários físicos acima. Não existe task que crie **subtasks por aluno**.

### 2.2 Onde a task é disparada

- **`app/physical_tests/routes.py`** (por volta da linha 492):  
  `task = generate_physical_forms_async.delay(test_id, city_id, force_regenerate=..., blocks_config=..., school_ids=..., grade_ids=..., class_ids=...)`
- **`app/physical_tests/tasks.py`** (linha 153): apenas referência em docstring (exemplo de uso).

Nenhum outro ponto no código analisado chama `.delay()` ou `.apply_async` para criar uma task **por aluno**.

---

## 3. Fluxo real: da task ao gerador WeasyPrint

### 3.1 Cadeia de chamadas

1. **Task** `generate_physical_forms_async` (única task por geração):
   - Configura multitenant (`search_path`), carrega prova, turmas, alunos, questões.
   - Monta `test_data` (com `correction_data`, `blocks_config`, etc.) e `students_data`.
   - Chama **uma vez** `PhysicalTestFormService().generate_physical_forms(test_id, test_data=test_data)`.

2. **Serviço** `PhysicalTestFormService.generate_physical_forms()` (`app/physical_tests/form_service.py`):
   - Valida prova, turmas, alunos; monta `questions_data` e `students_data`.
   - Instancia **uma vez** `InstitutionalTestWeasyPrintGenerator()` e chama **uma vez**:
     - `institutional_generator.generate_institutional_test_pdf_arch4(test_data, students_data, questions_data, class_test_id, output_dir=...)`.
   - Depois persiste resultados com `_save_physical_forms_to_db(...)`.

3. **Gerador** `InstitutionalTestWeasyPrintGenerator.generate_institutional_test_pdf_arch4()` (`app/services/institutional_test_weasyprint_generator.py`):
   - Implementa a “Architecture 4” (ver seção 4).
   - **Não** cria novas tasks; faz um **loop sequencial** sobre `students_data` dentro da mesma execução.

Conclusão: **não há “task por aluno”**. Uma única task Celery chama o form service uma vez, e o form service chama o gerador uma vez; o loop de alunos é interno ao gerador.

---

## 4. Onde o loop de alunos acontece e o que cada etapa faz

O loop de alunos está **apenas** em:

- **Arquivo:** `app/services/institutional_test_weasyprint_generator.py`  
- **Função:** `generate_institutional_test_pdf_arch4()`  
- **Trecho:** `for idx, student in enumerate(students_data, 1):` (por volta da linha 246).

### 4.1 Antes do loop (uma vez por prova)

- `_organize_questions_by_subject(questions_data, test_data)` → `questions_by_subject`.  
  - Dentro, cada questão é processada com `_process_question_for_template(question)`, que chama `_inline_question_images_html(...)` e portanto **pode baixar do MinIO** e preencher o cache `_image_data_uri_cache`.
- Se `use_blocks`: `_organize_questions_by_blocks(questions_data, test_data)` → `questions_by_block`.  
  - Em um dos ramos, chama `_process_question_for_template` por questão (novamente inlining e possível download; cache evita repetição para a mesma imagem).
- Numeração das questões e construção de `questions_map`.
- **Inline explícito** de imagens nas questões (linhas 191–215): percorre `questions_by_block` ou `questions_by_subject` e chama `_inline_question_images_html` em `content`, `prompt` e alternativas. Downloads do MinIO ocorrem aqui quando a imagem ainda não está em cache; após isso, o HTML já vai com `data:...;base64,...`.
- **Uma única** renderização do template com:
  - `include_cover=True`, `include_questions=True`, `include_answer_sheet=False`  
  → HTML da **capa + questões** (prova completa).
- **Uma única** chamada WeasyPrint sobre esse HTML → `base_pdf_bytes` / `base_reader`.

Ou seja: **o HTML completo da prova (capa + questões) é renderizado uma vez e convertido em PDF uma vez.** Todas as imagens usadas nessa etapa já foram resolvidas para base64 na fase de preparação (com cache).

### 4.2 Dentro do loop (por aluno)

Para cada `student` em `students_data`:

- Geração do QR do aluno (student_id + test_id).
- Montagem de `student_template_data` com:
  - `include_cover=False`, `include_questions=False`, `include_answer_sheet=True`.
- **Uma** renderização do **mesmo** template `institutional_test_hybrid.html` com esses flags → só a parte do **cartão-resposta (OMR)** é incluída no HTML.
- **Uma** chamada WeasyPrint sobre esse HTML (página OMR) → `student_pdf_bytes`.
- Merge com pypdf: todas as páginas do `base_reader` + primeira página do PDF do aluno (OMR).
- Gravação do PDF final em disco e acréscimo em `generated_files`.

Ou seja: **por aluno não há nova renderização da capa nem das questões.** Só há renderização da **página OMR** e merge. O template recebe os mesmos `questions_by_subject` / `questions_by_block` (já com conteúdo inlined), mas com `include_questions=False` a seção de questões não é emitida; a seção OMR não reutiliza imagens das questões, apenas estrutura (número de questões, blocos, etc.).

### 4.3 Onde `InstitutionalTestWeasyPrintGenerator` é chamado

- **Único ponto no fluxo de provas físicas:**  
  `app/physical_tests/form_service.py`, por volta das linhas 244–254, dentro de `generate_physical_forms()`:
  - Cria uma instância de `InstitutionalTestWeasyPrintGenerator`.
  - Chama **uma vez** `generate_institutional_test_pdf_arch4(...)` com a lista completa de alunos.

Não há chamada ao gerador por aluno (nem por task separada nem por outro serviço) no fluxo analisado.

---

## 5. Download de imagens do MinIO e construção de `questions_data`

### 5.1 Onde ocorre download do MinIO

- **Serviço de armazenamento:** `app/services/storage/minio_service.py`, método `download_file()`, que emite o log `"Arquivo baixado do MinIO: {bucket_name}/{object_name}"`.
- **Uso no gerador:** apenas no método `_inline_question_images_html()` (`app/services/institutional_test_weasyprint_generator.py`), que:
  - É chamado em `_process_question_for_template()` (ao processar cada questão para o template).
  - É chamado no bloco de “inline base64 nas questões (uma vez)” (linhas 191–215) em `generate_institutional_test_pdf_arch4()`.

Ambos os usos ocorrem **antes** do loop de alunos (na preparação das estruturas de questões). O gerador mantém `_image_data_uri_cache` por instância; após a primeira resolução de uma imagem (bucket + object_name), as próximas referências usam o cache e **não** disparam novo download.

### 5.2 Construção de `questions_data`

- **Quem monta:** `PhysicalTestFormService.generate_physical_forms()` em `form_service.py`:  
  `questions_data = [self._format_question_data(q) for q in questions]` (por volta da linha 235).  
  Isso é feito **uma vez** antes de chamar o gerador.
- **Onde é usado no gerador:** em `generate_institutional_test_pdf_arch4()` apenas na fase inicial (organização por disciplina/blocos, numeração, inline de imagens). O loop de alunos **não** reconstrói `questions_data`; reutiliza as estruturas já preparadas (`questions_by_subject`, `questions_by_block`).

Conclusão: **não há nova construção de `questions_data` nem novos downloads do MinIO dentro do loop por aluno.** Os downloads estão concentrados na fase única de preparação e inlining.

---

## 6. Confirmação do fluxo (sem subtasks por aluno)

O fluxo atual é:

```
generate_physical_forms_async (uma task)
  → PhysicalTestFormService.generate_physical_forms()
      → InstitutionalTestWeasyPrintGenerator.generate_institutional_test_pdf_arch4()
          [uma vez] organizar questões, inline imagens (MinIO aqui), renderizar base (capa+questões), WeasyPrint → base PDF
          [para cada aluno] renderizar só OMR, WeasyPrint → PDF OMR → merge base + OMR → salvar PDF
  → _save_physical_forms_to_db() / ZIP / upload do ZIP (opcional)
```

Não existe:

- `task_aluno_1`, `task_aluno_2`, … criadas pela task principal.
- Cada “task_aluno” montando HTML da prova, baixando imagens e rodando WeasyPrint para a prova completa.

Ou seja: **não** é “uma task por aluno que gera o PDF completo da prova”. É uma única task que gera um PDF base uma vez e, por aluno, só gera a página OMR e faz o merge.

---

## 7. Responsáveis por etapa (arquivos e funções)

| O quê | Onde (arquivo e função) |
|-------|--------------------------|
| Disparo da geração assíncrona | `app/physical_tests/routes.py` (chamada a `generate_physical_forms_async.delay`) |
| Task Celery única | `app/physical_tests/tasks.py`: `generate_physical_forms_async` |
| Loop de alunos e preparação de dados | `app/physical_tests/tasks.py`: mesmo corpo da task (alunos, questões, `test_data`) |
| Orquestração e chamada ao gerador | `app/physical_tests/form_service.py`: `PhysicalTestFormService.generate_physical_forms()` |
| Geração do PDF base + loop por aluno (OMR + merge) | `app/services/institutional_test_weasyprint_generator.py`: `generate_institutional_test_pdf_arch4()` |
| Inline de imagens (e downloads MinIO) | `app/services/institutional_test_weasyprint_generator.py`: `_inline_question_images_html()`, usado em `_process_question_for_template()` e no bloco de “inline base64” em `generate_institutional_test_pdf_arch4()` |
| Log “Arquivo baixado do MinIO” | `app/services/storage/minio_service.py`: `download_file()` |

---

## 8. Sobre os sintomas observados (~80 s por aluno, logs WeasyPrint e MinIO)

- **~80 s por aluno:** no arch4, por aluno só se faz: renderização WeasyPrint de **uma** página (OMR), merge em memória e escrita em disco. O custo é dominado pelo WeasyPrint (layout, fontes, etc.). 80 s por página é alto mas possível em máquina carregada ou com muitos elementos/CSS no OMR (ex.: “Ignored clip-path” indica que o WeasyPrint está a processar CSS complexo em cada render).
- **“Ignored clip-path: polygon(...)”:** esperado em cada chamada ao WeasyPrint (base e cada OMR); não indica que a prova completa está a ser renderizada de novo por aluno.
- **“Arquivo baixado do MinIO: question-images/...”:** no código atual esses downloads ocorrem na fase única de inlining (e em `_process_question_for_template` nessa mesma fase). Se nos logs eles parecem “entre alunos”, as causas plausíveis são: **(1)** ordem de logs (muitas imagens na prova → muitos logs concentrados no início, que podem aparecer misturados com logs do WeasyPrint da base); **(2)** ambiente ou versão de código diferente (ex. fluxo antigo que gera PDF completo por aluno). No fluxo arch4 analisado, **não** há nova chamada a MinIO dentro do loop por aluno.

---

## 9. Conclusão

- **Não existe arquitetura “uma task por aluno” que regenere a prova inteira.** Existe uma única task que chama o gerador uma vez; o gerador gera o PDF base uma vez e, no loop, só gera a página OMR por aluno e faz o merge.
- **O HTML completo da prova (capa + questões) não é renderizado novamente para cada aluno;** é renderizado uma vez antes do loop.
- **As imagens do MinIO são usadas na fase única de preparação (inline em base64), com cache por instância;** no loop por aluno não há código que volte a baixar imagens.
- Os atrasos e logs observados são compatíveis com: uma renderização pesada do PDF base no início, N renderizações WeasyPrint da página OMR (uma por aluno) e os downloads do MinIO concentrados na fase de inlining. Nenhuma alteração de código foi feita; este relatório limita-se a descrever o comportamento atual do código analisado.
