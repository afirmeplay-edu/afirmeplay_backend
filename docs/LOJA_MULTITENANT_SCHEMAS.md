# Loja e schemas multi-tenant

## Onde cada tabela fica

| Tabela             | Schema      | Observação |
|--------------------|------------|------------|
| **store_items**    | **public**  | Catálogo único para todos os municípios. Criada pela migration `add_store_tables`. |
| **student_purchases** | **public** + **cada city_xxx** | Migration cria em `public`. Novas cidades (provisionadas pelo `city_schema_service`) também recebem `student_purchases` no schema da cidade. |

## Comportamento em runtime

- O middleware define `search_path = "city_xxx", "public"` quando o request tem contexto de um município.
- **StoreItem**: não tem schema fixo no modelo → o primeiro que tiver `store_items` no search_path é usado. Só existe em `public` → sempre lê/grava em **public.store_items**.
- **StudentPurchase**: não tem schema fixo → o primeiro que tiver `student_purchases` é usado.
  - Se a cidade foi provisionada **depois** da inclusão da loja no `city_schema_service`: existe `city_xxx.student_purchases` → compras ficam no schema da cidade (isolamento por tenant).
  - Se a cidade foi provisionada **antes**: não existe `student_purchases` no schema da cidade → usa **public.student_purchases** (comportamento antigo).

## Resumo

- **Catálogo (store_items)**: só em **public** (um catálogo para todos).
- **Compras (student_purchases)**: em **public** (criado pela migration) e, para **novas** cidades, também no schema **city_xxx** (criado pelo `city_schema_service`). Em requests com tenant, o PostgreSQL usa primeiro o schema do tenant; se existir `student_purchases` lá, as compras ficam isoladas por município.

## Cidades já existentes

Para que **todas** as cidades tenham compras no próprio schema (e não em public), é preciso criar a tabela `student_purchases` em cada schema `city_xxx` já existente. Exemplo de script (rodar com cuidado, em ambiente controlado):

```sql
-- Para cada schema city_xxx existente (listar com: SELECT schema_name FROM information_schema.schemata WHERE schema_name LIKE 'city_%');)
-- Substituir {schema} pelo nome do schema, ex: city_9a2f95ed_9f70_4863_a5f1_1b6c6c262b0d

CREATE TABLE IF NOT EXISTS "{schema}".student_purchases (
    id VARCHAR PRIMARY KEY,
    student_id VARCHAR REFERENCES "{schema}".student(id) ON DELETE CASCADE NOT NULL,
    store_item_id VARCHAR REFERENCES public.store_items(id) ON DELETE CASCADE NOT NULL,
    price_paid INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_student_purchases_student_id ON "{schema}".student_purchases(student_id);
CREATE INDEX IF NOT EXISTS idx_student_purchases_store_item_id ON "{schema}".student_purchases(store_item_id);
CREATE INDEX IF NOT EXISTS idx_student_purchases_created_at ON "{schema}".student_purchases(created_at);
```

Assim, após rodar esse SQL para cada cidade, todas as compras passam a ficar no schema do tenant.
