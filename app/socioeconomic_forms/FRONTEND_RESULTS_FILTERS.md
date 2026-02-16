# Filtros para tela de resultados de formulários

## Nova rota: opções em cascata (com formulário)

**GET** `/forms/results/filter-options`

Retorna as opções dos próximos filtros conforme a seleção anterior. Hierarquia:

**Estado → Município → Formulário → Escola → Série → Turma**

### Query parameters (cascata)

| Parâmetro    | Obrigatório após | Descrição              |
| ------------ | ---------------- | ---------------------- |
| `estado`     | —                | Estado (ex: `SP`)      |
| `municipio`  | `estado`         | ID (UUID) do município |
| `formulario` | `municipio`      | ID do formulário       |
| `escola`     | `formulario`     | ID da escola           |
| `serie`      | `escola`         | ID da série            |
| `turma`      | `serie`          | ID da turma            |

### Exemplos de chamada

- `GET /forms/results/filter-options`  
  → `{ "estados": [...] }`
- `GET /forms/results/filter-options?estado=SP`  
  → `{ "estados": [...], "municipios": [...] }`
- `GET /forms/results/filter-options?estado=SP&municipio=<uuid>`  
  → `{ "estados": [...], "municipios": [...], "formularios": [...] }`
- `GET /forms/results/filter-options?estado=SP&municipio=<uuid>&formulario=<uuid>`  
  → `{ ..., "escolas": [...] }`
- Com `escola` e `serie` → resposta inclui também `series` e `turmas`.

### Formato da resposta

- **estados**: `[{ "id", "nome", "name" }]`
- **municipios**: `[{ "id", "nome", "name", "estado_id" }]`
- **formularios**: `[{ "id", "titulo", "name", "nome", "formType" }]`
- **escolas**: `[{ "id", "nome", "name", "city_id", "municipio_id" }]`
- **series**: `[{ "id", "nome", "name", "education_stage_id", "educationStageId" }]`
- **turmas**: `[{ "id", "nome", "name", "grade_id", "school_id" }]`

Sempre vêm apenas os níveis preenchidos até o último parâmetro enviado (e os anteriores da cascata).

---

## Rotas de resultados (inalteradas)

- **Resultados de um formulário** (mantidas):
    - `GET /forms/<form_id>/results/indices?state=&municipio=&escola=&serie=&turma=`
    - `GET /forms/<form_id>/results/profiles?state=&municipio=&escola=&serie=&turma=`
- **Resultados agregados (todos os formulários do escopo)** (mantidas):
    - `GET /forms/aggregated/results/indices?state=&municipio=&escola=&serie=&turma=`
    - `GET /forms/aggregated/results/profiles?...`
    - `GET /forms/aggregated/results/summary?...`

Os parâmetros de filtro das rotas de resultados continuam: `state`, `municipio`, `escola`, `serie`, `turma`. Para resultados de **um** formulário, o `form_id` vai na URL; para agregados, não se passa formulário (considera todos do escopo).

---

## Rota antiga de filtros (criação/edição)

**GET** `/forms/filter-options`  
Hierarquia: **Estado → Município → Escola → Série → Turma** (sem formulário).  
Continue usando para telas de criação/edição de formulários; para a tela de **resultados**, use `/forms/results/filter-options`.
