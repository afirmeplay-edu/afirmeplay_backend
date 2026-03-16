# Relatório de Análise: Arquitetura de Alta Performance para Geração de PDFs Institucionais

**Escopo:** Análise do código existente em `app/physical_tests/` e componentes relacionados.  
**Objetivo:** Avaliar a viabilidade de uma estratégia **base exam PDF + folha de respostas por aluno + merge com pypdf**, sem alterar o layout do cartão-resposta (OMR).  
**Regra:** Nenhum código foi modificado; apenas análise.

---

## 1. Fluxo Atual de Geração de PDF

### 1.1 Cadeia de Chamadas

| Etapa | Componente | Arquivo | Responsabilidade |
|-------|------------|---------|------------------|
| 1 | Task Celery | `app/physical_tests/tasks.py` | `generate_physical_forms_async` — configura schema (multitenant), valida prova/turmas, monta `test_data` com `correction_data` e `blocks_config`, chama o serviço. |
| 2 | Serviço | `app/physical_tests/form_service.py` | `PhysicalTestFormService.generate_physical_forms()` — carrega prova, questões, alunos, extrai `correction_data` do `test_data`, monta `test_data` final, chama o gerador WeasyPrint e depois `_save_physical_forms_to_db`. |
| 3 | Gerador | `app/services/institutional_test_weasyprint_generator.py` | `InstitutionalTestWeasyPrintGenerator.generate_institutional_test_pdf_arch4()` — implementa a “Architecture 4”: gera 1 PDF de questões, 1 PDF por aluno (capa + OMR), mescla com pypdf e persiste em disco. |

A geração em produção é acionada pela task Celery; o serviço não recebe `output_dir` na chamada atual, então o gerador usa o diretório padrão `/tmp/celery_pdfs/physical_tests`.

### 1.2 Fluxo Detalhado (Um Aluno) — Architecture 4 (Atual)

1. **Uma vez por prova (antes do loop de alunos):**
   - Organização de questões: `_organize_questions_by_subject`, opcionalmente `_organize_questions_by_blocks`.
   - Numeração sequencial das questões e construção de `questions_map`.
   - Inline de imagens nas questões (base64 via MinIO).
   - Renderização do template `institutional_test_hybrid.html` com:
     - `include_cover=False`, `include_questions=True`, `include_answer_sheet=False`.
   - Conversão do HTML em PDF com WeasyPrint → `questions_pdf_bytes` → `PdfReader(questions_reader)`.

2. **Por aluno (loop):**
   - Geração do QR code (student_id + test_id) em base64.
   - `student_template_data` com `include_cover=True`, `include_questions=False`, `include_answer_sheet=True`.
   - Renderização do mesmo template → HTML (capa institucional + cartão OMR).
   - WeasyPrint → `student_pdf_bytes` → `PdfReader(student_reader)`.
   - Merge com pypdf (`PdfWriter`):
     - Páginas da capa do aluno: `student_reader.pages[:-1]`.
     - Todas as páginas do PDF de questões: `questions_reader.pages`.
     - Última página do aluno (OMR): `student_reader.pages[-1]`.
   - Gravação do PDF final em disco e acréscimo em `generated_files`.

3. **Após o loop:** o serviço persiste cada arquivo no banco (e envia para MinIO).

**Conclusão:** O fluxo já utiliza “1 PDF de questões + 1 PDF por aluno (capa + OMR) + merge”. A proposta em análise é evoluir para “1 PDF base (capa + blocos + questões, sem dados do aluno) + 1 PDF por aluno (apenas OMR) + merge”, eliminando a renderização da capa por aluno.

---

## 2. Onde as Páginas de Questões São Renderizadas

- **Onde:** Em `InstitutionalTestWeasyPrintGenerator.generate_institutional_test_pdf_arch4()`, na primeira parte (antes do loop de alunos).
- **Template:** `institutional_test_hybrid.html` com `include_questions=True` e `include_cover=False`, `include_answer_sheet=False`.
- **Variáveis usadas na parte de questões:**  
  `test_data`, `questions_by_subject`, `questions_by_block`, `blocks_config`, `questions_map`, `total_questions`, `generated_date`, `default_logo`. O template recebe `student: {}` nesse passo e não usa aluno na seção de questões.
- **Dependência de aluno:** Nenhuma. As páginas de questões (capas de bloco + listagem de questões) são **idênticas para todos os alunos**.

As questões já são renderizadas uma única vez no fluxo atual (Architecture 4).

---

## 3. Onde o Cartão-Resposta (Answer Sheet / OMR) É Renderizado

- **Onde no template:** Bloco `{% if include_answer_sheet %}` (aprox. linhas 717–906 em `institutional_test_hybrid.html`), dentro da div `.answer-sheet`.
- **CSS:** Toda a regra do cartão está no mesmo arquivo: `@page answer-sheet-omr` (margem 0), `.answer-sheet` (21cm×29.7cm, padding fixo), âncoras A4, triângulos fiduciais, cabeçalho, instruções, grade de bolhas. Nenhum CSS externo adicional é necessário para o OMR.
- **Dados passados:**  
  `student` (nome, escola, turma, `qr_code`), `test_data`, `questions_by_subject` / `questions_by_block`, `blocks_config`, `questions_map`, `total_questions`. O layout (tamanho, coordenadas, QR, bolhas) é controlado por esse HTML/CSS; a variável `answer_sheet_image` (gerada por `_generate_answer_sheet_base64`) é passada ao template mas **não é referenciada** no HTML — o OMR é 100% o markup da div `.answer-sheet`.

**Conclusão:** O cartão-resposta pode ser renderizado sozinho com o mesmo template, usando `include_cover=False`, `include_questions=False`, `include_answer_sheet=True` e o mesmo HTML/CSS, preservando layout idêntico ao atual (incluindo QR e coordenadas OMR).

---

## 4. Análise da Estrutura do Template

### 4.1 Partes do Template

| Bloco | Condição | Conteúdo | Dados do aluno? |
|-------|----------|----------|-----------------|
| Capa institucional | `include_cover` | Logo, título, disciplinas, rodapé (ESCOLA, SÉRIE, TURMA) | Sim: `student.school_name`, `student.class_name` no rodapé. |
| Capas de bloco + questões | `include_questions` | Blocos, disciplinas, enunciados e alternativas | Não. |
| Cartão-resposta OMR | `include_answer_sheet` | Cabeçalho (nome da prova, nome do aluno, escola, turma), QR, instruções, grade de bolhas | Sim: `student` (nome, escola, turma, `qr_code`). |

### 4.2 Divisão Lógica (Sem Mudar Layout)

- **Compartilhado entre todos os alunos:**  
  Capa institucional (exceto rodapé), capas de bloco e todas as páginas de questões.  
  O rodapé da capa hoje usa escola/turma do aluno; para um “PDF base” único, seria necessário tratar a capa como genérica (sem aluno) ou omitir a capa do base.
- **Específico por aluno:**  
  Rodapé da capa (se mantido por aluno) e todo o bloco do cartão-resposta (OMR).

O template já permite controle fino via:

- `questions_template.html` conceptual: mesmo arquivo com `include_cover=False`, `include_questions=True`, `include_answer_sheet=False`.
- `answer_sheet_template.html` conceptual: mesmo arquivo com `include_cover=False`, `include_questions=False`, `include_answer_sheet=True`.

Não é obrigatório fatiar em dois arquivos; a divisão lógica já existe com as três flags. Uma eventual separação em dois templates só exigiria copiar as seções correspondentes e o CSS necessário, sem alterar layout.

---

## 5. Viabilidade do PDF Base (Questões Únicas)

**Pergunta:** É possível gerar um único `questions_base.pdf` contendo capa institucional, capas de bloco e páginas de questões, **sem** conteúdo por aluno?

- **Sim.** O gerador já gera um PDF “só de questões” (sem capa, sem OMR). Para obter um “base” que inclua também a capa e os blocos:
  - Renderizar com `include_cover=True`, `include_questions=True`, `include_answer_sheet=False`.
  - Passar um objeto `student` vazio ou com valores genéricos **apenas para a capa** (ou ajustar o template para que o rodapé da capa seja opcional quando não houver aluno).

**Atenção:** Na capa atual, o rodapé usa `student.school_name` e `student.class_name`. Para um PDF base realmente compartilhado (sem dados de aluno), é necessário:

- Ou usar texto genérico no rodapé da capa (ex.: “Escola: —”, “Turma: —”) quando `student` estiver vazio, ou
- Não incluir a capa no base e manter a lógica atual (capa por aluno).

Se a regra de negócio permitir uma capa genérica no base, a implementação é apenas garantir que o template não quebre com `student` vazio e que o rodapé tenha um fallback. Nenhuma mudança no layout do OMR é necessária.

---

## 6. Viabilidade da Renderização da Folha de Respostas Por Aluno

- **Sim.** Basta chamar o mesmo template com `include_cover=False`, `include_questions=False`, `include_answer_sheet=True` e o `student` completo (incluindo `qr_code`). O WeasyPrint gera um PDF de uma página (a `@page answer-sheet-omr`).
- O HTML e o CSS do OMR permanecem os mesmos; portanto o layout (tamanho, margens, posição do QR, bolhas, fiduciais) permanece **idêntico** ao atual. O sistema de correção continua válido.

---

## 7. Viabilidade do Merge com pypdf

- **Uso atual:** No próprio gerador, dentro do loop por aluno: `PdfReader` (questões e aluno), `PdfWriter`, depois `writer.add_page(...)` na ordem desejada e `writer.write(out)`.
- **Proposta:**  
  `questions_base.pdf` (todas as páginas) + `answer_sheet_student.pdf` (1 página) → `complete_exam_student.pdf`.
- **Onde colocar o merge:** Mantê-lo no gerador (`InstitutionalTestWeasyPrintGenerator`) é coerente: o gerador já conhece a estrutura dos PDFs (base vs. OMR). O serviço continuaria apenas orquestrando (chamar gerador, receber lista de arquivos, persistir no banco/MinIO). Não é necessário subir o merge para a camada de serviço.

---

## 8. Impacto de Performance

### 8.1 Situação Atual (Architecture 4)

- 1× render WeasyPrint: “só questões” (várias páginas).
- N× renders WeasyPrint: por aluno, “capa + OMR” (2 páginas cada).
- Total: 1 + N chamadas WeasyPrint; N merges pypdf.

### 8.2 Proposta (Base + OMR por Aluno)

- 1× render WeasyPrint: “base” (capa genérica + blocos + questões; ex.: ~15 páginas).
- N× renders WeasyPrint: por aluno, “só OMR” (1 página cada).
- N merges: base + OMR_aluno.

### 8.3 Comparação

- **Antes da Arch4 (referência):** N × (capa + questões + OMR) = N × ~16 páginas.
- **Arch4 atual:** 1 × (questões) + N × (capa + OMR) → menos trabalho que N provas completas.
- **Proposta:** 1 × (base com capa + questões) + N × (1 página OMR) → elimina N renders da capa (cada um com logo, texto e rodapé). Redução de trabalho do WeasyPrint e, em geral, menor tempo total e menor uso de memória por aluno.

Estimativa de ganho adicional em relação à Arch4: da ordem de N páginas a menos renderizadas (uma capa por aluno) e PDFs por aluno menores na etapa de render (1 página em vez de 2). Para 1000 alunos, isso representa 1000 renders de capa a menos.

---

## 9. Riscos e Limitações

1. **Capa no PDF base:** Se a capa for incluída no base com rodapé genérico (sem escola/turma por aluno), o usuário deixa de ver escola/turma na primeira página. Se isso for inaceitável, o base pode continuar “só questões” (como hoje) e manter capa por aluno; o ganho seria só padronizar o merge “base + OMR” em vez de “capa_aluno + questões + OMR”.
2. **Compatibilidade do OMR:** Qualquer alteração no HTML/CSS do bloco `.answer-sheet` ou na `@page answer-sheet-omr` pode afetar a correção. Na proposta, esse bloco não é alterado; apenas se renderiza sozinho.
3. **Ordem das páginas no merge:** O merge deve manter a ordem: todas as páginas do base, depois a página do OMR. O código atual já faz esse tipo de ordenação; basta replicar para “base + answer_sheet_student”.
4. **Cache do PDF base:** Em cenários com muitos alunos, manter o `questions_base.pdf` (ou o `PdfReader` correspondente) em memória ou em disco temporário evita regenerá-lo. O fluxo atual já mantém um único `questions_reader` no loop; o mesmo vale para um base que inclua capa.
5. **Testes:** Validar que o PDF final (base + OMR) tem o mesmo número de páginas e a mesma página final (OMR) que o fluxo atual, e que a correção OMR continua funcionando com o novo PDF.

---

## 10. Resumo das Conclusões

| Tópico | Conclusão |
|--------|-----------|
| Fluxo atual | Celery → PhysicalTestFormService → InstitutionalTestWeasyPrintGenerator; Arch4 já usa “1 PDF questões + N PDFs (capa+OMR) + merge”. |
| Páginas de questões | Renderizadas uma vez; não dependem de aluno; já compartilhadas. |
| Cartão-resposta (OMR) | Pode ser renderizado sozinho com o mesmo template/CSS; layout preservado. |
| Template | Divisão lógica já existe via `include_cover` / `include_questions` / `include_answer_sheet`; possível separar em dois arquivos sem mudar layout. |
| PDF base | Viável; capa no base exige capa genérica (rodapé sem aluno) ou manter capa por aluno. |
| OMR por aluno | Viável; mesmo template, 1 página por aluno. |
| Merge pypdf | Viável; manter no gerador; ordem: base + OMR. |
| Performance | Redução de N renders de capa e de tamanho do PDF por aluno na etapa de render. |

Implementar a arquitetura “base exam PDF + folha de respostas por aluno + merge” é **viável e seguro** desde que o bloco do cartão-resposta (OMR) não seja alterado e que a decisão sobre a capa (genérica no base ou por aluno) seja tomada conforme a regra de negócio.
