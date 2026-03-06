# Plano de Implementação - Frontend da Loja (Afirmecoins)

Plano para implementar no frontend a loja onde o aluno gasta afirmecoins e recebe **molduras**, **selos** e **temas da sidebar** (e no futuro itens físicos).

---

## Índice

1. [Visão geral e API](#1-visão-geral-e-api)
2. [Etapa 1: Serviços e tipos](#2-etapa-1-serviços-e-tipos)
3. [Etapa 2: Página da Loja](#3-etapa-2-página-da-loja)
4. [Etapa 3: Compra e feedback](#4-etapa-3-compra-e-feedback)
5. [Etapa 4: Minhas compras](#5-etapa-4-minhas-compras)
6. [Etapa 5: Aplicar recompensas (moldura, selo, tema)](#6-etapa-5-aplicar-recompensas)
7. [Etapa 6: Navegação e saldo](#7-etapa-6-navegação-e-saldo)
8. [Checklist final](#8-checklist-final)

---

## 1. Visão geral e API

### Endpoints (backend já implementado)

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/store/items` | Lista itens. Query: `category`, `physical_only`, `student_id` (admin). Retorna `already_purchased` por item se logado como aluno. |
| POST | `/store/purchase` | Compra. Body: `{ "store_item_id": "uuid" }`. Retorna `purchase`, `new_balance`, `reward_type`, `reward_data`. |
| GET | `/store/my-purchases` | Histórico de compras do aluno (limit/offset). |
| GET | `/coins/balance` | Saldo atual (já existente). |

### Categorias de itens

- **frame** – Moldura (avatar/perfil)
- **stamp** – Selo
- **sidebar_theme** – Tema da sidebar
- **physical** – Item físico (futuro)

### Respostas de erro relevantes

- **400** – Saldo insuficiente: `{ "erro": "Saldo insuficiente", "detalhes": "..." }`
- **404** – Item não encontrado ou inativo
- **401** – Não autenticado (para compra e my-purchases)

---

## 2. Etapa 1: Serviços e tipos

### 2.1 Tipos TypeScript

**Arquivo sugerido**: `src/types/store.ts` (ou dentro de `src/types/` existente)

```typescript
export type StoreCategory = 'frame' | 'stamp' | 'sidebar_theme' | 'physical';

export interface StoreItem {
  id: string;
  name: string;
  description: string | null;
  price: number;
  category: StoreCategory;
  reward_type: string;
  reward_data: string | null;
  is_physical: boolean;
  is_active: boolean;
  sort_order: number;
  created_at: string | null;
  already_purchased?: boolean;
}

export interface StorePurchaseResponse {
  message: string;
  purchase: {
    id: string;
    student_id: string;
    store_item_id: string;
    price_paid: number;
    created_at: string;
  };
  new_balance: number;
  reward_type: string;
  reward_data: string | null;
}

export interface StudentPurchase {
  id: string;
  student_id: string;
  store_item_id: string;
  price_paid: number;
  created_at: string;
  item_name: string | null;
  reward_type: string | null;
  reward_data: string | null;
}
```

### 2.2 Serviço / API da loja

**Arquivo sugerido**: `src/services/storeService.ts` (ou `src/api/store.ts`)

```typescript
import { apiClient } from '@/services/api'; // ou seu cliente HTTP

export const storeApi = {
  getItems(params?: { category?: string; physical_only?: boolean; student_id?: string }) {
    const query: Record<string, string> = {};
    if (params?.category) query.category = params.category;
    if (params?.physical_only !== undefined) query.physical_only = String(params.physical_only);
    if (params?.student_id) query.student_id = params.student_id;
    return apiClient.get<{ items: StoreItem[] }>('/store/items', { params: query });
  },

  purchase(storeItemId: string) {
    return apiClient.post<StorePurchaseResponse>('/store/purchase', { store_item_id: storeItemId });
  },

  getMyPurchases(params?: { limit?: number; offset?: number }) {
    return apiClient.get<{ purchases: StudentPurchase[]; limit: number; offset: number }>(
      '/store/my-purchases',
      { params: params ?? {} }
    );
  },
};
```

**Objetivo**: centralizar chamadas à API da loja e tipar respostas.

---

## 3. Etapa 2: Página da Loja

### 3.1 Rota

- **Rota sugerida**: `/student/store` ou `/loja` (conforme seu padrão de rotas do aluno).
- **Acesso**: apenas aluno (ou roles que tenham “student” vinculado). Redirecionar se não for aluno.

### 3.2 Layout da página

- **Header**: título “Loja” + saldo de moedas (reutilizar `CoinBalance` já planejado em `PLANO_IMPLEMENTACAO_FRONTEND.md`).
- **Abas ou filtros por categoria**:
  - Todas
  - Molduras (`category=frame`)
  - Selos (`category=stamp`)
  - Temas da sidebar (`category=sidebar_theme`)
  - (Opcional) Itens físicos (`physical_only=true`) para o futuro.
- **Lista de itens**: grid ou lista de cards.

### 3.3 Componente de card de item

**Arquivo sugerido**: `src/components/Store/StoreItemCard.tsx`

**Props**:

- `item: StoreItem`
- `balance: number` (saldo atual)
- `onPurchase: (itemId: string) => void` (callback de compra, pode abrir modal de confirmação)
- `loading?: boolean` (item sendo comprado)

**Exibir**:

- Nome, descrição (resumida), preço em moedas, imagem/ícone conforme categoria.
- Badge “Já comprado” se `item.already_purchased`.
- Botão “Comprar” desabilitado se `already_purchased` ou `balance < item.price`, com tooltip “Saldo insuficiente” quando aplicável.

### 3.4 Listagem

- Ao montar a página (e ao trocar aba/filtro), chamar `storeApi.getItems({ category })`.
- Passar saldo do aluno para os cards (buscar com `GET /coins/balance` ou contexto existente de moedas).
- Tratar loading e lista vazia (“Nenhum item nesta categoria”).

---

## 4. Etapa 3: Compra e feedback

### 4.1 Fluxo de compra

1. Usuário clica em “Comprar” no card.
2. (Recomendado) Modal de confirmação: “Comprar [nome] por [preço] afirmecoins?”
3. Ao confirmar: chamar `storeApi.purchase(item.id)`.
4. Em sucesso:
   - Fechar modal.
   - Toast de sucesso: “Compra realizada! Novo saldo: X moedas.”
   - Atualizar saldo global (contexto ou refetch de `GET /coins/balance`).
   - Atualizar lista de itens (refetch `GET /store/items`) para refletir `already_purchased` e evitar compra duplicada na mesma sessão.
   - Se a recompensa for aplicável na hora (ex.: tema da sidebar), aplicar conforme Etapa 5.
5. Em erro 400 (saldo insuficiente): toast de erro com `response.data.detalhes` ou mensagem amigável.
6. Em erro 404/500: toast genérico de erro.

### 4.2 Estado de loading

- Durante o POST, desabilitar o botão “Comprar” e mostrar loading no card ou no modal (evitar double submit).

---

## 5. Etapa 4: Minhas compras

### 5.1 Página ou seção

- **Rota sugerida**: `/student/store/purchases` ou aba “Minhas compras” dentro da loja.
- **Dados**: `GET /store/my-purchases` com paginação (limit/offset) se quiser.

### 5.2 Conteúdo

- Lista de compras (data, nome do item, preço pago).
- Opcional: filtro por categoria (frontend filtra pelo `reward_type` ou por um campo equivalente retornado).
- Para itens digitais: link ou botão “Usar” que leva à tela onde o aluno aplica moldura/selo/tema (ver Etapa 5).

---

## 6. Etapa 5: Aplicar recompensas (moldura, selo, tema)

O backend retorna `reward_type` e `reward_data` na compra e em “minhas compras”. O frontend é responsável por **aplicar** o prêmio.

### 6.1 Onde cada tipo é usado

| Categoria         | Onde aplicar na UI |
|-------------------|---------------------|
| **frame**         | Moldura em volta do avatar do aluno (perfil, header, ranking). |
| **stamp**         | Selo no perfil ou em cards (conquistas, certificados). |
| **sidebar_theme** | Tema visual da sidebar (cores, fundo). |

### 6.2 Persistência no frontend

- **Opção A (recomendada)**: o frontend chama um endpoint no backend para “salvar preferências do aluno” (ex.: `selected_frame_id`, `selected_sidebar_theme_id`). Assim, ao logar em outro dispositivo, as escolhas vêm do servidor.
- **Opção B**: só localStorage (dispositivo atual). Mais simples, menos consistente.

Se ainda não existir, criar no backend algo como:

- `GET/PUT /student/me/preferences` com `{ "frame_id": "...", "stamp_id": "...", "sidebar_theme_id": "..." }`.

O frontend, ao carregar a área do aluno, busca essas preferências e aplica moldura, selo e tema.

### 6.3 Lógica de aplicação

- **Moldura**: componente de avatar recebe `frameId` (vindo de `reward_data`, ex. `frame_id`). Se o aluno tem esse item em “minhas compras” e escolheu usar, desenha a moldura em volta do avatar.
- **Selos**: lista de selos desbloqueados vem das compras com `category === 'stamp'`; o aluno escolhe um para exibir no perfil (salvar em preferências).
- **Tema sidebar**: `reward_data` pode ser um id (ex. `"dark"`, `"blue"`). Ao aplicar, o frontend altera classes CSS ou variáveis de tema da sidebar e persiste em preferências.

### 6.4 Tela de “Escolher moldura/selo/tema”

- Em “Minhas compras” ou em “Perfil” → “Personalização”.
- Listar itens comprados por tipo (molduras, selos, temas).
- Botão “Usar” que chama PUT de preferências e atualiza a UI na hora.

---

## 7. Etapa 6: Navegação e saldo

### 7.1 Menu / Navbar do aluno

- Adicionar link “Loja” (ícone + texto) que leva à página da loja.
- Manter o componente de saldo (CoinBalance) visível no header/navbar do aluno, para o usuário sempre ver quantas moedas tem antes de comprar.

### 7.2 Atualização do saldo após compra

- Após `POST /store/purchase` bem-sucedido, o backend retorna `new_balance`.
- Atualizar imediatamente o estado global de saldo (contexto de moedas ou refetch de `GET /coins/balance`) para refletir o novo valor sem recarregar a página.

---

## 8. Checklist final

- [ ] **Tipos**: `StoreItem`, `StorePurchaseResponse`, `StudentPurchase`, `StoreCategory`.
- [ ] **API**: `storeApi.getItems`, `storeApi.purchase`, `storeApi.getMyPurchases` com tipagem.
- [ ] **Página Loja**: rota, header com CoinBalance, abas/filtros por categoria, lista de itens.
- [ ] **StoreItemCard**: nome, descrição, preço, “Já comprado”, botão Comprar (desabilitado quando saldo insuficiente ou já comprado).
- [ ] **Modal de confirmação** de compra e tratamento de erros (400 saldo insuficiente, 404, 500).
- [ ] **Atualização de saldo** e da lista de itens após compra.
- [ ] **Minhas compras**: página ou aba, lista com dados de `GET /store/my-purchases`.
- [ ] **Preferências no backend** (opcional mas recomendado): endpoint para salvar frame/selo/tema selecionados.
- [ ] **Aplicar moldura**: avatar com moldura conforme preferência e itens comprados.
- [ ] **Aplicar selo**: exibição do selo escolhido no perfil/cards.
- [ ] **Aplicar tema da sidebar**: troca de tema e persistência.
- [ ] **Link “Loja”** no menu do aluno e **CoinBalance** visível no header.

---

## Ordem sugerida de implementação

1. Tipos + `storeApi` + página da loja (listagem e filtro por categoria).
2. Card de item + modal de compra + tratamento de erro de saldo + atualização de saldo.
3. Página “Minhas compras”.
4. Backend de preferências (se ainda não existir) + UI para “Escolher moldura/selo/tema”.
5. Aplicar moldura, selo e tema na interface (avatar, perfil, sidebar).

Assim o aluno já pode ver a loja, comprar e ver o histórico; em seguida você entrega a “entrega” visual dos prêmios (moldura, selo, tema).
