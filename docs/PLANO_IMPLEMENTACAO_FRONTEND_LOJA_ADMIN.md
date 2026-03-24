# Plano de Implementação - Frontend: Gestão da Loja (Admin / Tec Admin / Diretor / Coordenador / Professor)

Plano para implementar no frontend a **adição, edição e remoção de itens da loja** pelos perfis admin, tec admin, diretor, coordenador e professor, com **escopo por perfil** (sistema, município, escola, turma).

---

## Índice

1. [Quem pode o quê (escopo por perfil)](#1-quem-pode-o-quê-escopo-por-perfil)
2. [API de gestão da loja](#2-api-de-gestão-da-loja)
3. [Contexto de tenant (admin)](#3-contexto-de-tenant-admin)
4. [Etapa 1: Tipos e serviço](#4-etapa-1-tipos-e-serviço)
5. [Etapa 2: Página de listagem (admin)](#5-etapa-2-página-de-listagem-admin)
6. [Etapa 3: Formulário criar/editar item](#6-etapa-3-formulário-criareditar-item)
7. [Etapa 4: Escopo e carregamento de opções](#7-etapa-4-escopo-e-carregamento-de-opções)
8. [Etapa 5: Excluir item](#8-etapa-5-excluir-item)
9. [Etapa 6: Navegação e permissão](#9-etapa-6-navegação-e-permissão)
10. [Checklist final](#10-checklist-final)

---

## 1. Quem pode o quê (escopo por perfil)

| Perfil | Escopos permitidos | Comportamento |
|--------|--------------------|---------------|
| **Admin** | system, city, school, class | Pode criar itens para todo o sistema ou para cidade/escola/turma específica. Em cidade/escola/turma precisa **contexto de tenant** (X-City-ID ou município selecionado). |
| **Tec Admin** | system, city | Pode criar para todo o sistema ou **apenas para o município** dele. Ao escolher "city", o backend usa o city_id do token/tenant. |
| **Diretor / Coordenador** | system, city, school | Pode criar para sistema, cidade ou **apenas para a escola** dele. Ao escolher "school", usa a escola vinculada ao perfil. |
| **Professor** | system, city, school, class | Pode criar para sistema, cidade, escola ou **apenas para turmas em que leciona**. Ao escolher "class", o backend valida que as turmas são as dele. |

- **system**: item visível para todos os alunos (todo o sistema).
- **city**: item visível só para alunos do(s) município(s) em `scope_filter.city_ids`.
- **school**: item visível só para alunos da(s) escola(s) em `scope_filter.school_ids`.
- **class**: item visível só para alunos da(s) turma(s) em `scope_filter.class_ids`.

Na **listagem** de itens no admin, cada perfil vê apenas os itens que **pode gerenciar** (editar/excluir).

---

## 2. API de gestão da loja

Base URL: mesma do backend (ex.: `/api` ou como estiver configurado).

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/store/admin/items` | Lista itens que o usuário pode gerenciar. Query: `active_only` (true/false, opcional). |
| GET | `/store/admin/allowed-scopes` | Retorna `{ allowed_scopes: string[] }` para montar o select de "Para quem este item?" (system, city, school, class). |
| POST | `/store/admin/items` | Cria item. Body em JSON (ver abaixo). |
| PUT | `/store/admin/items/<item_id>` | Atualiza item (apenas itens que o usuário pode gerenciar). |
| DELETE | `/store/admin/items/<item_id>` | Remove item (apenas itens que o usuário pode gerenciar). |

### Cabeçalhos

- **Authorization**: `Bearer <token>` (obrigatório).
- **X-City-ID** (opcional): para **admin** que está atuando em um município específico (criar item para uma cidade). Se o admin não envia, pode estar “sem contexto” e aí só poderá criar itens com escopo **system**.

### Body de criação (POST) e edição (PUT)

```json
{
  "name": "Moldura Ouro",
  "description": "Moldura especial para avatar",
  "price": 50,
  "category": "frame",
  "reward_type": "frame",
  "reward_data": "{\"frame_id\":\"gold\"}",
  "is_physical": false,
  "scope_type": "system",
  "scope_filter": null,
  "is_active": true,
  "sort_order": 0
}
```

- **Obrigatórios**: `name`, `price`, `category`.
- **scope_type**: um de `system`, `city`, `school`, `class` (dentro dos `allowed_scopes` do usuário).
- **scope_filter**: obrigatório quando scope_type não é `system`.
  - **city**: `{ "city_ids": ["uuid-da-cidade"] }` (tec adm usa só a cidade dele; admin pode enviar com X-City-ID).
  - **school**: `{ "school_ids": ["uuid-da-escola"] }` (pode ser array com uma ou mais escolas, dentro do permitido).
  - **class**: `{ "class_ids": ["uuid-turma1", "uuid-turma2"] }` (professor: só turmas em que leciona).
- **reward_type**: em geral igual a `category` para digitais; **reward_data**: string (JSON ou identificador).

### Respostas de erro

- **400**: validação (ex.: "Tec adm só pode definir itens para o seu município", "Professor só pode definir itens para turmas em que você leciona").
- **401**: não autenticado.
- **403**: sem permissão para editar/excluir aquele item.

---

## 3. Contexto de tenant (admin)

- **Admin** pode atuar “sem cidade” (só itens **system**) ou “numa cidade” (header **X-City-ID** ou seleção de município no front).
- Ao criar item com escopo **city** ou **school/class** de uma cidade, o frontend deve enviar **X-City-ID** com o UUID da cidade escolhida, para o backend resolver o tenant e validar escola/turma.
- **Tec admin, diretor, coordenador e professor** já têm cidade/tenant no token; não precisam enviar X-City-ID para a própria atuação.

Sugestão de UI para admin: se houver **seletor de município** no layout (dropdown ou página “Atuar em: Município X”), ao chamar POST/PUT/GET da loja admin, enviar **X-City-ID** quando um município estiver selecionado.

---

## 4. Etapa 1: Tipos e serviço

### 4.1 Tipos TypeScript (estender ou criar)

**Arquivo**: `src/types/store.ts` (ou equivalente)

```typescript
export type StoreScopeType = 'system' | 'city' | 'school' | 'class';

export interface StoreScopeFilter {
  city_ids?: string[];
  school_ids?: string[];
  class_ids?: string[];
}

export interface StoreItemAdmin {
  id: string;
  name: string;
  description: string | null;
  price: number;
  category: string;
  reward_type: string;
  reward_data: string | null;
  is_physical: boolean;
  scope_type: string;
  scope_filter: StoreScopeFilter | null;
  is_active: boolean;
  sort_order: number;
  created_at: string | null;
}

export interface StoreItemCreatePayload {
  name: string;
  description?: string | null;
  price: number;
  category: string;
  reward_type?: string;
  reward_data?: string | null;
  is_physical?: boolean;
  scope_type: StoreScopeType;
  scope_filter?: StoreScopeFilter | null;
  is_active?: boolean;
  sort_order?: number;
}
```

### 4.2 Serviço API (admin)

**Arquivo**: `src/services/storeAdminService.ts` (ou dentro de `storeService.ts`)

- `getAdminItems(activeOnly?: boolean)` → GET `/store/admin/items`, retorna `{ items: StoreItemAdmin[] }`.
- `getAllowedScopes()` → GET `/store/admin/allowed-scopes`, retorna `{ allowed_scopes: string[] }`.
- `createItem(payload: StoreItemCreatePayload)` → POST `/store/admin/items`, body JSON, retorna item criado.
- `updateItem(itemId: string, payload: Partial<StoreItemCreatePayload>)` → PUT `/store/admin/items/:id`.
- `deleteItem(itemId: string)` → DELETE `/store/admin/items/:id`.

Em todas as chamadas, usar o **mesmo cliente HTTP** que já envia o token (e, se existir, o header **X-City-ID** quando o admin tiver município selecionado).

---

## 5. Etapa 2: Página de listagem (admin)

### 5.1 Rota e acesso

- **Rota sugerida**: `/admin/store/items` ou `/loja/gerenciar` (conforme padrão do projeto).
- **Acesso**: apenas usuários com role **admin**, **tecadm**, **diretor**, **coordenador** ou **professor** (redirect ou 403 para outros).

### 5.2 Layout

- **Título**: "Gerenciar itens da loja" (ou "Itens da loja").
- **Botão**: "Adicionar item" → leva ao formulário de criação.
- **Filtro opcional**: toggle ou select "Mostrar apenas ativos" (chamar `getAdminItems(true)` ou `getAdminItems(false)`).
- **Tabela ou cards** com itens retornados por `getAdminItems()`:
  - Nome, categoria, preço (afirmecoins), escopo (system / cidade / escola / turma), ativo (sim/não), ordem.
  - Ações: **Editar**, **Excluir** (excluir só se o backend permitir; 403 indica que não pode gerenciar aquele item).

### 5.3 Comportamento

- Ao montar a página, chamar `getAdminItems()` (e, se houver filtro, `getAdminItems(activeOnly)`).
- Tratar 401 (redirecionar para login) e 403 (mensagem de permissão).
- Lista vazia: mensagem “Nenhum item para gerenciar” ou “Adicione o primeiro item”.

---

## 6. Etapa 3: Formulário criar/editar item

### 6.1 Rota

- **Criar**: `/admin/store/items/new` (ou modal/drawer na mesma página da listagem).
- **Editar**: `/admin/store/items/:id/edit`.

### 6.2 Campos do formulário

| Campo | Tipo | Obrigatório | Observação |
|-------|------|-------------|------------|
| Nome | text | Sim | Nome do item na loja. |
| Descrição | textarea | Não | Texto explicativo. |
| Preço (afirmecoins) | number | Sim | Inteiro ≥ 0. |
| Categoria | select | Sim | Opções: frame, stamp, sidebar_theme, physical (conforme backend). |
| Tipo de recompensa | text | Não | Default: igual à categoria. Ex.: frame, stamp, sidebar_theme. |
| Dados da recompensa | text | Não | JSON ou ID (ex.: `{"frame_id":"gold"}`). |
| Item físico? | checkbox | Não | Default false. |
| **Para quem este item?** | select | Sim | Opções vindas de **allowed_scopes** (system, city, school, class). |
| **Filtro de escopo** | dinâmico | Conforme escopo | Ver Etapa 4. |
| Ativo? | checkbox | Não | Default true. |
| Ordem | number | Não | sort_order, default 0. |

### 6.3 Validação no frontend

- Nome não vazio; preço numérico ≥ 0; categoria preenchida.
- Se **scope_type** for city, school ou class, preencher **scope_filter** com os IDs selecionados (city_ids, school_ids ou class_ids).
- Ao editar, enviar no PUT apenas os campos alterados (ou todos, conforme convenção do backend).

### 6.4 Envio e feedback

- **Criar**: POST com payload completo; em sucesso (201), toast de sucesso e redirecionar para a listagem (ou fechar modal e atualizar lista).
- **Editar**: PUT com payload; em sucesso (200), toast e voltar/atualizar.
- **Erro 400**: exibir mensagem do backend (ex.: "Professor só pode definir itens para turmas em que você leciona").
- **Erro 403**: "Você não tem permissão para editar este item."

---

## 7. Etapa 4: Escopo e carregamento de opções

### 7.1 Select "Para quem este item?"

- Ao abrir o formulário (criar ou editar), chamar **GET /store/admin/allowed-scopes**.
- Montar um **select** com as opções retornadas em `allowed_scopes`.
- Labels sugeridas:
  - **system** → "Todo o sistema"
  - **city** → "Município"
  - **school** → "Escola"
  - **class** → "Turma"

### 7.2 Filtro de escopo (conforme scope_type)

Quando o usuário escolher um escopo diferente de **system**, exibir um bloco adicional para escolher **para qual** cidade/escola/turma.

- **scope_type = city**
  - **Admin**: exibir select de **cidades** (listar cidades disponíveis; ao selecionar, enviar X-City-ID nas requisições e `scope_filter: { city_ids: [selectedCityId] }`).
  - **Tec admin**: não precisa de select; o backend usa a cidade do token. Enviar `scope_filter: { city_ids: [cityIdDoUsuario] }`. O front pode obter o city_id do usuário (perfil ou contexto) e enviar fixo.
- **scope_type = school**
  - Exibir select de **escolas**. Diretor/coordenador: apenas a escola dele (pode ser select com uma opção ou fixo). Admin/tec adm: listar escolas (do município selecionado, se houver). Payload: `scope_filter: { school_ids: [id] }`.
- **scope_type = class**
  - Exibir select múltiplo de **turmas**. Professor: apenas turmas em que leciona (endpoint existente de “minhas turmas” ou equivalente). Diretor/admin: turmas da escola selecionada. Payload: `scope_filter: { class_ids: [...] }`.

### 7.3 Endpoints auxiliares (já existentes no projeto)

- Listagem de **cidades**: usar endpoint existente (ex.: lista de municípios).
- Listagem de **escolas**: por cidade (ex.: escolas do município selecionado ou do tenant).
- Listagem de **turmas**: por escola ou “turmas do professor” (conforme rotas já existentes).

Garantir que, ao escolher escola ou turma, os IDs enviados em **scope_filter** sejam os que o backend espera (UUIDs em string).

---

## 8. Etapa 5: Excluir item

- Na listagem, botão **Excluir** por item.
- **Confirmação**: modal “Excluir item [nome]? Esta ação não pode ser desfeita.”
- Ao confirmar: **DELETE** `/store/admin/items/:id`.
  - **200**: toast de sucesso, remover o item da lista ou recarregar.
  - **403**: toast de erro “Você não tem permissão para remover este item.”
  - **404**: “Item não encontrado.”

---

## 9. Etapa 6: Navegação e permissão

### 9.1 Menu

- No menu ou sidebar de **admin / tec admin / diretor / coordenador / professor**, adicionar entrada **“Loja”** ou **“Itens da loja”** que leva à listagem de itens (`/admin/store/items` ou equivalente).
- Ocultar essa entrada para perfis que não tenham uma das roles permitidas.

### 9.2 Permissão na rota

- Na rota da listagem e do formulário, verificar se o usuário está logado e se a role está em `['admin', 'tecadm', 'diretor', 'coordenador', 'professor']`; caso contrário, redirecionar ou exibir 403.

---

## 10. Checklist final

- [ ] Tipos: `StoreItemAdmin`, `StoreScopeFilter`, `StoreItemCreatePayload`, `StoreScopeType`.
- [ ] Serviço: `getAdminItems`, `getAllowedScopes`, `createItem`, `updateItem`, `deleteItem` (com token e X-City-ID quando aplicável).
- [ ] Página de listagem: rota protegida, tabela/cards, botão “Adicionar item”, filtro ativo/inativo, ações Editar e Excluir.
- [ ] Formulário criar: campos nome, descrição, preço, categoria, reward_type, reward_data, is_physical, scope_type, scope_filter, is_active, sort_order; select de escopo baseado em `allowed_scopes`.
- [ ] Formulário editar: mesmo layout; carregar item por ID; PUT com alterações.
- [ ] Escopo dinâmico: quando scope_type = city, school ou class, exibir select(s) de cidade/escola/turma e preencher `scope_filter` corretamente; admin com X-City-ID quando atuar em um município.
- [ ] Excluir: confirmação em modal; DELETE; tratamento 403/404 e atualização da lista.
- [ ] Navegação: entrada “Loja” / “Itens da loja” no menu para os perfis permitidos; proteção de rota por role.
- [ ] Tratamento de erros 400 (mensagens do backend) e 403 (permissão) em todas as ações.

---

## Ordem sugerida de implementação

1. **Tipos e serviço** (allowed-scopes, admin items, create, update, delete).
2. **Listagem** (página, tabela, botão adicionar, editar/excluir chamando API).
3. **Formulário de criação** com escopo **system** primeiro (sem scope_filter), para validar fluxo.
4. **Select de escopo** e **bloco dinâmico** para city/school/class (carregar cidades, escolas, turmas e preencher scope_filter).
5. **Formulário de edição** (reutilizar mesmo formulário, carregar item por ID).
6. **Excluir com confirmação** e **navegação/menu** por perfil.

Com isso, o frontend cobre a adição, edição e exclusão de itens na loja por admin, tec admin, diretor, coordenador e professor, alinhado ao backend já implementado.
