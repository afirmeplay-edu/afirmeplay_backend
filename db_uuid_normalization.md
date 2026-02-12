## Padronização de tipos UUID x VARCHAR

Este arquivo documenta **inconsistências atuais de tipos** entre colunas que representam IDs (muitas vezes UUID), e os **ajustes temporários de cast explícito** feitos nas queries. A ideia é servir de guia para uma futura migração de schema.

---

### 1. Situação atual (inferida pelo código/erros)

- **Tabela `school`**
    - **Coluna**: `school.id`
    - **Uso no código**: tratada várias vezes como texto (comparações diretas com `Student.school_id`, conversões `uuid_to_str` para comparar com `School.id`).
    - **Tipo real provável**: `VARCHAR` / `TEXT`.
    - **Tipo desejado na padronização**: `UUID` (PK).

- **Tabela `class` (studentClass)**
    - **Coluna**: `class.id`
    - **Uso no código**: sempre convertida com `ensure_uuid(class_id)` para filtros.
    - **Tipo desejado**: `UUID` (PK).
    - **Coluna**: `class.school_id`
        - **Erros atuais**:
            - `operator does not exist: character varying = uuid`
            - Queries geradas com `class.school_id = CAST(school.id AS UUID)` ou `class.school_id = :school_id::UUID`.
        - **Conclusão**: `class.school_id` hoje é `VARCHAR` armazenando UUID em formato texto.
        - **Tipo desejado**: `UUID` (FK para `school(id)`).

- **Tabela `manager`**
    - **Coluna**: `manager.school_id`
    - **Uso no código**:
        - Convertida com `uuid_to_str(manager.school_id)` para comparar com `School.id` (comentário no código indica: _"School.id é VARCHAR"_).
    - **Tipo real provável**: `UUID` (FK para escola).
    - **Impacto da futura migração**:
        - Quando `school.id` virar `UUID`, essa coluna já estará coerente.

- **Tabela `school_teacher`**
    - **Coluna**: `school_teacher.school_id`
    - **Uso no código**:
        - Comparada diretamente com `School.id` como string (listas de `school_ids` vindas do request).
    - **Tipo real provável**: `VARCHAR` armazenando UUID como texto.
    - **Tipo desejado**: `UUID` (FK para `school(id)`).

- **Tabela `student`**
    - **Coluna**: `student.school_id`
    - **Uso no código**:
        - Joins como `School.id == Student.school_id` sem cast.
    - **Tipo real provável**: mesmo tipo de `school.id` (atualmente `VARCHAR`).
    - **Tipo desejado**: `UUID` (FK para `school(id)`).

---

### 2. Ajustes temporários já feitos (casts explícitos)

Nestes pontos, o código foi ajustado para **eliminar erros de `UUID` x `VARCHAR`** sem mudar o schema.

- **Arquivo**: `app/routes/school_routes.py`
    - **Joins `School` ↔ `Class`**:
        - Antes: `Class, cast(School.id, PostgresUUID) == Class.school_id`
        - Agora: **`Class, School.id == cast(Class.school_id, String)`**
    - Rotas afetadas:
        - `GET /school` (`listar_escolas`)
        - `GET /school/<escola_id>` (`buscar_escola`)
        - `GET /school/city/<city_id>` (`buscar_escolas_por_cidade`)
        - `GET /school/by-grade/<grade_id>` (`buscar_escolas_por_serie`)

- **Arquivo**: `app/routes/class_routes.py`
    - Import:
        - Antes: `from sqlalchemy import cast`
        - Agora: **`from sqlalchemy import cast, String`**
    - **Joins `Class` ↔ `School`**:
        - Antes: `School, Class.school_id == cast(School.id, PostgresUUID)`
        - Agora: **`School, School.id == cast(Class.school_id, String)`**
    - Rotas afetadas:
        - `GET /classes/filtered`
        - `GET /classes/school/<school_id>` (`get_classes_by_school`)
        - `GET /classes` (`get_classes`)
        - `GET /classes/<class_id>` (`get_class`)
    - **Filtros por `school_id` em `Class`**:
        - Antes (exemplos):
            - `Class.school_id == ensure_uuid(school_id)`
        - Agora:
            - **`Class.school_id == str(ensure_uuid(school_id))`**
        - Objetivo: comparar **texto com texto** (`VARCHAR` = `VARCHAR`), mantendo validação de formato UUID via `ensure_uuid`.

- **Arquivo**: `app/routes/educationStage_routes.py`
    - **Join `EducationStage` / `Grade` / `Class` / `School`** para `/education_stages`:
        - Antes:
            - Base: `School, Class.school_id == cast(School.id, PostgresUUID)`
            - Filtros por escola/manager/professor usando `cast(School.id, PostgresUUID)` e listas de UUID.
            - Erro observado:
                - `operator does not exist: character varying = uuid` em:
                    - `JOIN school ON class.school_id = CAST(school.id AS UUID)`
        - Agora:
            - Join:
                - **`School, School.id == cast(Class.school_id, String)`**
            - Filtro por escola de diretor/coordenador:
                - **`School.id == str(manager_school_id_uuid)`**
            - Filtro por escolas do professor:
                - **`School.id.in_([str(sid) for sid in school_ids_uuids])`**
        - Objetivo: manter `School.id` como texto e apenas converter os UUIDs (do código ou de `Class.school_id`) para `str`, evitando comparações `UUID` x `VARCHAR`.

- **Arquivo**: `app/routes/evaluation_results_routes.py`
    - **Joins para obter avaliações por município em `/evaluation-results/opcoes-filtros`**:
        - Antes:
            - `JOIN school ON class.school_id = CAST(school.id AS UUID)`
            - Gerando erro:
                - `operator does not exist: character varying = uuid`
        - Agora:
            - `JOIN school ON school.id = CAST(class.school_id AS VARCHAR)` via SQLAlchemy:
                - **`test_query = test_query.join(School, School.id == cast(Class.school_id, String))`**
                - **`query_avaliacoes = ... .join(School, School.id == cast(Class.school_id, String))`**
        - Objetivo: alinhar com o padrão geral (`School.id` como texto, `Class.school_id` convertido para texto em runtime).

- **Arquivo**: `app/routes/basic_endpoints.py`
    - **Estatísticas completas do dashboard `/dashboard/comprehensive-stats` (escopo TecAdm)**:
        - Antes:
            - Filtros de turmas e subquery para `ClassTest` usando `ensure_uuid_list(school_ids)`:
                - `class_query = class_query.filter(Class.school_id.in_(ensure_uuid_list(school_ids)))`
                - `Class.query.filter(Class.school_id.in_(ensure_uuid_list(school_ids)))`
            - Gerando SQL do tipo:
                - `WHERE class.school_id IN (%(school_id_1_1)s::UUID, ...)` ⇒ conflito `VARCHAR = UUID`.
        - Agora:
            - Uso de cast explícito em `Class.school_id` para comparar com `School.id` (texto):
                - **`class_query = class_query.filter(cast(Class.school_id, String).in_(school_ids))`**
                - **`Class.query.filter(cast(Class.school_id, String).in_(school_ids))`** dentro da subquery de `ClassTest`.
        - Objetivo: garantir que as comparações sejam sempre `VARCHAR` x `VARCHAR` enquanto o schema não for migrado para `UUID` real.

- **Arquivo**: `app/socioeconomic_forms/services/form_service.py`
    - **Erro**: `operator does not exist: character varying = uuid` em `POST /forms` ao resolver escopo (só escolas / só séries / turmas). Query: `WHERE class.school_id = :school_id::UUID` (coluna `class.school_id` é `VARCHAR`).
    - **Ajustes**:
        - Em `_resolve_scope_and_warnings`: comparação por escola com **`Class.school_id == str(sid)`**; `Class.school_id.in_([str(s) for s in school_ids_uuids])`; `School.query.get(str(sid))`.
        - Em `_validate_selections`: **`Class.school_id.in_([str(s) for s in school_ids_uuids])`**; e **`School.id.in_(school_ids_str)`** com `school_ids_str = [str(s) for s in school_ids_uuids]` (coluna `school.id` é VARCHAR).
        - Em `_validate_filters` (série/turma na escola): **`Class.query.filter_by(school_id=str(school_id_uuid))`**; comparação **`turma.school_id != str(escola_id_uuid)`**.
    - Objetivo: comparar sempre `VARCHAR` com string, sem cast do parâmetro para UUID.

- **Arquivo**: `app/socioeconomic_forms/services/distribution_service.py`
    - **Erro**: mesmo `character varying = uuid` ao buscar turmas por `school_ids`; e **`WHERE school.id IN (...::UUID)`** em `get_diretor_recipients` (coluna `school.id` é VARCHAR).
    - **Ajustes**:
        - **`school_ids_str = [str(s) for s in school_ids_uuids]`** e filtros **`Class.school_id.in_(school_ids_str)`** ou **`Class.school_id == school_ids_str[0]`**.
        - Em **`get_diretor_recipients`**: **`School.id.in_([str(s) for s in school_ids])`**.
    - Objetivo: alinhar com o padrão `class.school_id` e `school.id` VARCHAR.

---

### 3. Plano sugerido de migração futura

Quando for possível mudar o schema do banco, os passos gerais sugeridos são:

1. **Converter chaves primárias de texto para UUID**:
    - `school.id`: `VARCHAR` → `UUID` (com migração que faça `USING id::uuid`).
2. **Converter FKs relacionadas para UUID**:
    - `class.school_id`: `VARCHAR` → `UUID USING school_id::uuid`.
    - `student.school_id`: idem.
    - `school_teacher.school_id`: idem.
3. **Remover casts temporários do código**:
    - Eliminar `cast(Class.school_id, String)` nos joins.
    - Passar a comparar `Class.school_id` diretamente como `UUID`.
4. **Revisar utilitários de UUID**:
    - Ver onde `uuid_to_str` e `ensure_uuid` ainda são necessários ou podem ser simplificados.

> Enquanto a migração completa não é feita, **todos os pontos de cast explícito listados aqui precisam ser mantidos**, pois evitam os erros `operator does not exist: character varying = uuid`.
