# Contrato da API mobile — pacote offline (`api_contract_version` **1.1**)

Documento normativo para o **app** consumir **estritamente** o JSON devolvido pelo backend.  
Prefixo HTTP: **`/mobile/v1`**.

---

## 1. `POST /offline-pack/redeem`

### 1.1 Headers obrigatórios

| Header         | Valor                                            |
| -------------- | ------------------------------------------------ |
| `Content-Type` | `application/json`                               |
| `X-Device-Id`  | UUID v4 (mesmo em todas as chamadas do aparelho) |

Não é obrigatório `X-City-ID` quando o código existe em `public.mobile_offline_pack_registry`.

### 1.2 Corpo (todas as páginas)

```json
{
	"code": "<12 caracteres normalizados, com ou sem hífens>",
	"page": 1,
	"page_size": 50,
	"offline_pack_id": "<uuid retornado na página 1; opcional na pág. 1, recomendado nas seguintes>"
}
```

- **`code`**: obrigatório em **todas** as páginas.
- **`offline_pack_id`**: na página 1 pode ser omitido; nas páginas `> 1` deve ser o mesmo da página 1 (validação de consistência).

### 1.3 Objeto raiz da resposta (200)

Campos **sempre presentes** em todas as páginas:

| Campo                           | Tipo               | Descrição                                                                                                                                                                                                                                       |
| ------------------------------- | ------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `api_contract_version`          | `string`           | `"1.1"` inclui `aplicadores`; `"1.0"` sem esse campo.                                                                                                                                                                                           |
| `city_id`                       | `string`           | UUID do município (`public.city.id`).                                                                                                                                                                                                           |
| `offline_pack_id`               | `string`           | UUID do registro no tenant (`mobile_offline_pack_code.id`).                                                                                                                                                                                     |
| `bundle_valid_until`            | `string`           | ISO 8601 com sufixo `Z` (validade mínima do snapshot para upload).                                                                                                                                                                              |
| `sync_bundle_version_by_school` | `object`           | Mapa **`school_id` (string) → `number` inteiro**. Versão do bundle **por escola**; usar no **`POST /sync/upload`** conforme a escola da submissão.                                                                                              |
| `sync_bundle_version`           | `number` \| `null` | Se **exatamente uma** escola em `sync_bundle_version_by_school`, repete esse inteiro; caso contrário **`null`**. O app **deve** usar `sync_bundle_version_by_school[student.school_id]` quando houver várias escolas ou quando este for `null`. |
| `page`                          | `number`           | Página atual (≥ 1).                                                                                                                                                                                                                             |
| `page_size`                     | `number`           | Tamanho da página.                                                                                                                                                                                                                              |
| `total_students`                | `number`           | Total de alunos elegíveis no pacote.                                                                                                                                                                                                            |
| `total_pages`                   | `number`           | Total de páginas de alunos (≥ 1).                                                                                                                                                                                                               |
| `unchanged`                     | `boolean`          | No offline pack costuma ser `false`.                                                                                                                                                                                                            |
| `students`                      | `array`            | Lista de **StudentPayload** (ver §2).                                                                                                                                                                                                           |

**Página 1** (`page === 1`): payload completo de provas e aplicadores do município.

| Campo                  | Tipo     | Descrição                                                                                  |
| ---------------------- | -------- | ------------------------------------------------------------------------------------------ |
| `aplicadores`          | `array`  | **AplicadorPayload** (§2.1) — todos os `users` com `role=aplicador` e `city_id` do pacote. |
| `student_test_links`   | `array`  | Lista de `{ "student_id", "test_id" }`.                                                    |
| `tests`                | `object` | Mapa **`test_id` → objeto metadados da prova** (igual espírito ao `sync/bundle`).          |
| `questions_by_test`    | `object` | Mapa **`test_id` → array de questões** canónicas (com `order`).                            |
| `test_content_version` | `object` | Mapa **`test_id` → string** (hash de conteúdo; enviar no upload).                          |

#### Identidade das questões (`questions_by_test`)

Cada item do array usa:

| Campo         | Tipo     | Descrição |
| ------------- | -------- | --------- |
| `id`          | `string` | UUID global em `public.question.id` (banco de questões). |
| `question_id` | `string` | Alias de `id` (desde contrato 1.1+); valor enviado no **`POST /sync/upload`** como `answers[].question_id`. |
| `order`       | `number` | Posição da questão na prova (`tenant.test_questions.order`). |

**Importante para clientes offline:** o mesmo `id` / `question_id` **pode aparecer em provas diferentes** quando a instituição reutiliza itens do banco. O app deve indexar questões localmente pelo par **`(test_id, question_id)`**, nunca só por `question_id`. Não alterar o backend para IDs únicos por prova — o upload valida contra `public.question.id`.

**Página > 1**:

| Campo                   | Tipo      | Descrição           |
| ----------------------- | --------- | ------------------- |
| `aplicadores`           | `array`   | Sempre `[]`.        |
| `student_test_links`    | `array`   | Sempre `[]`.        |
| `tests`                 | `object`  | Sempre `{}`.        |
| `questions_by_test`     | `object`  | Sempre `{}`.        |
| `test_content_version`  | `object`  | Sempre `{}`.        |
| `includes_full_payload` | `boolean` | Presente e `false`. |

---

## 2.1 `AplicadorPayload` (cada elemento de `aplicadores`)

| Campo              | Tipo     | Descrição                                                                          |
| ------------------ | -------- | ---------------------------------------------------------------------------------- |
| `user_id`          | `string` | UUID em `public.users`.                                                            |
| `name`             | `string` | Nome exibido.                                                                      |
| `email`            | `string` | E-mail completo (cadastro web).                                                    |
| `login`            | `string` | Prefixo antes do `@` (ex. `joao` para `joao@afirmeplay.com.br`).                   |
| `role`             | `string` | Fixo `"aplicador"`.                                                                |
| `offline_password` | `string` | Senha em texto claro para login offline rápido (mesma senha definida no cadastro). |

**Login offline do aplicador:** `login` + `offline_password` (comparação literal, sem hash).  
**Login online (sync):** `POST /mobile/v1/auth/login` com `registration` = prefixo ou e-mail + `password` (hash web).

---

## 2.2 `StudentPayload` (cada elemento de `students`)

Ordem das chaves no JSON **não** é garantida; usar nomes exatos.

| Campo          | Tipo               | Obrigatório | Descrição                                                                                                               |
| -------------- | ------------------ | ----------- | ----------------------------------------------------------------------------------------------------------------------- |
| `id`           | `string`           | sim         | UUID do aluno (`student.id`).                                                                                           |
| `name`         | `string`           | sim         | Nome exibido (campo do aluno).                                                                                          |
| `registration` | `string` \| `null` | sim         | PIN de 4 dígitos (`student.registration`); gerado no cadastro do aluno. `null` se ainda não atribuído (rodar backfill). |
| `user_id`      | `string` \| `null` | sim         | UUID em `public.users`.                                                                                                 |
| `class_id`     | `string` \| `null` | sim         | UUID da turma.                                                                                                          |
| `grade_id`     | `string` \| `null` | sim         | UUID da série/nota.                                                                                                     |
| `school_id`    | `string`           | sim         | UUID da escola.                                                                                                         |
| `school_name`  | `string` \| `null` | sim\*       | Nome da escola (`tenant.school.name`). `null` se `school_id` ausente ou registro não encontrado.                        |
| `grade_name`   | `string` \| `null` | sim\*       | Nome da série (`public.grade.name`). `null` se `grade_id` for `null` ou registro não encontrado.                        |
| `class_name`   | `string` \| `null` | sim\*       | Nome da turma (`tenant.class.name`). `null` se `class_id` for `null` ou registro não encontrado.                        |

\*Presentes em todas as respostas a partir da versão **1.1**; apps **1.0** podem ignorar.

**Login offline do aluno:** usar **`registration`** como identificador e como senha (mesmo valor, 4 dígitos). Não enviar `email` nem `password_hash` no pacote.

---

## 3. Alinhamento com `GET /mobile/v1/sync/bundle`

O bundle por escola (`sync/bundle`) segue o **mesmo formato** de cada item em `students` e os mesmos conceitos de `tests`, `questions_by_test`, `test_content_version`, `student_test_links`.  
Diferenças:

- `sync/bundle` expõe `school_id` e **um** `sync_bundle_version` (escola única no pedido).
- `redeem` expõe `sync_bundle_version_by_school` e opcionalmente `sync_bundle_version` quando só há uma escola.

---

## 4. Upload (`POST /sync/upload`) — lembrete

Cada item de `submissions` deve incluir o **`sync_bundle_version`** inteiro correspondente à **escola** da submissão:  
`sync_bundle_version_by_school[school_id]` guardado no sync local após o download.

---

## 5. Painel web — listagem, edição e exclusão (`/mobile/v1/offline-pack*`)

Autenticação: JWT do login web + tenant (`X-City-Id` ou slug).

Cada item (`GET` lista/detalhe, resposta de `PATCH`) inclui:

| Campo                | Tipo               | Descrição                                                            |
| -------------------- | ------------------ | -------------------------------------------------------------------- |
| `created_by_user_id` | `string` \| `null` | Quem gerou o código (`POST /register`). `null` em registros antigos. |
| `can_edit`           | `boolean`          | Pode chamar `PATCH` neste pacote.                                    |
| `can_delete`         | `boolean`          | Pode chamar `DELETE` ou incluir o id no bulk.                        |

**Regras:**

- **admin** — edita/exclui qualquer código do município.
- **tecadm, diretor, coordenador, aplicador** — só códigos com `created_by_user_id ===` id do usuário logado.
- Códigos sem criador (legado) — só **admin**.

`PATCH` / `DELETE` sem permissão → **403**.  
`POST /offline-pack/bulk-delete` → corpo `{ "offline_pack_ids": [...] }`; resposta `{ "deleted", "not_found", "forbidden" }` (HTTP 200 mesmo com `forbidden` parcial).

---

## 6. Evolução de versão

| Versão  | Alteração                                                                                                                                          |
| ------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1.1** | Cada `StudentPayload` inclui `school_name`, `grade_name`, `class_name` (mesmo formato em `GET /sync/bundle`). Compatível com apps que só leem IDs. |
| **1.0** | Apenas IDs de escola, série e turma no aluno.                                                                                                      |

Alterações incompatíveis devem incrementar **`api_contract_version`** (ex.: `"2.0"`) e atualizar este ficheiro. O app pode negociar ou recusar versões desconhecidas.
