# Ideia: Página administrativa – Dar e remover moedas

Roteiro para montar a tela em que admin, coordenador, diretor ou tecadm **filtra** até achar o aluno e depois **credita** ou **debita** moedas.

---

## 1. Dinâmica de roles

O backend já define assim:

| Role          | Consultar saldo/transações de outro aluno | Dar ou remover moedas | Listagem GET `/students` (escopo) |
|---------------|-------------------------------------------|------------------------|------------------------------------|
| **admin**     | Sim (`?student_id=xxx`)                    | Sim                    | Todos os alunos                    |
| **coordenador** | Sim                                    | Sim                    | Só alunos da **sua escola**        |
| **diretor**   | Sim                                      | Sim                    | Só alunos da **sua escola**        |
| **professor** | Sim                                      | Não                    | Alunos das **escolas onde leciona** |
| **tecadm**    | Sim                                      | Sim                    | Alunos do **município** (city_id)  |
| **aluno**     | Não (só próprio)                         | Não                    | Não acessa lista de outros          |

- **Consultar** = GET `/coins/balance?student_id=xxx` e GET `/coins/transactions?student_id=xxx`. Quem não pode passar `student_id` só vê próprio saldo (aluno).
- **Dar/remover** = POST `/coins/admin/credit` e POST `/coins/admin/debit` → no backend **todos exceto aluno e professor** (`@role_required('admin', 'coordenador', 'diretor', 'tecadm')`).

### O que mostrar na UI por role

| Role          | Mostrar página “Administração de moedas”? | Mostrar filtros + lista de alunos? | Mostrar botões “Dar moedas” / “Remover moedas”? |
|---------------|-------------------------------------------|-------------------------------------|-------------------------------------------------|
| **admin**     | Sim                                      | Sim (todos os alunos)               | Sim                                             |
| **coordenador** | Sim                                    | Sim (alunos da escola dele)         | Sim                                             |
| **diretor**   | Sim                                      | Sim (alunos da escola dele)         | Sim                                             |
| **professor** | Sim (como “Consulta de saldos”)          | Sim (alunos das escolas dele)       | Não                                             |
| **tecadm**    | Sim (como “Consulta de saldos”)          | Sim (alunos do município)           | Sim                                             |
| **aluno**     | Não (ou redirecionar para “Meu saldo”)   | —                                   | Não                                             |

- Para **admin**, **coordenador**, **diretor** e **tecadm**: página completa com filtros, lista, seleção de aluno e ações de dar/remover.
- Para **professor**: mesma página (como “Consulta de saldos”) — filtros e lista, **sem** botões de dar/remover.
- Para **aluno**: não exibir esta página; mostrar só “Meu saldo” e “Minhas transações” (sem `student_id` na query).

Assim a dinâmica de roles fica alinhada ao backend: quem pode consultar outro aluno vê lista e saldos; quem pode alterar (admin, coordenador, diretor, tecadm) vê também os botões de dar/remover.

---

## 2. Fluxo geral

1. **Filtrar** (cidade → escola → turma e/ou nome) até reduzir a lista de alunos.
2. **Selecionar** um aluno da lista (obter o `student_id`).
3. **Ver saldo** atual (opcional).
4. **Executar ação**: dar moedas (crédito) ou remover moedas (débito) — admin, coordenador, diretor e tecadm.

---

## 3. Estrutura da página (wireframe em texto)

```
┌─────────────────────────────────────────────────────────────────┐
│  Administração de moedas                                         │
├─────────────────────────────────────────────────────────────────┤
│  FILTROS                                                         │
│  [Cidade ▼]  [Escola ▼]  [Turma ▼]  [Nome do aluno ____] [Buscar]│
├─────────────────────────────────────────────────────────────────┤
│  ALUNOS (clique para selecionar)                                 │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ Nome           │ Turma   │ Escola    │ Saldo  │ ✓            │ │
│  │ Maria Silva   │ 5º A   │ EMEF X    │ 120    │ (selecionado) │ │
│  │ João Santos   │ 5º A   │ EMEF X    │  80    │               │ │
│  └─────────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│  ALUNO SELECIONADO: Maria Silva (ID: xxx)  │  Saldo atual: 120    │
│                                                                  │
│  AÇÃO                                                             │
│  ( ) Dar moedas    ( ) Remover moedas                            │
│                                                                  │
│  Quantidade: [____]   Motivo: [admin_credit ▼]   Descrição: [___] │
│                                                                  │
│  [ Executar ]                                                     │
├─────────────────────────────────────────────────────────────────┤
│  Últimas transações (opcional)                                   │
│  - +50  admin_credit  02/03/2026  Saldo: 120                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Filtros (em cascata)

| Ordem | Filtro   | Fonte de dados | Comportamento |
|-------|----------|----------------|----------------|
| 1     | Cidade   | GET `/cities` ou equivalente | Ao escolher, carrega escolas da cidade. |
| 2     | Escola   | GET `/schools?city_id=xxx` (ou listagem por cidade) | Ao escolher, carrega turmas da escola. |
| 3     | Turma    | GET `/classes` ou por escola | Opcional; reduz a lista de alunos. |
| 4     | Nome     | Campo de texto | Filtra na lista já carregada ou dispara busca no backend. |

- **Carregar alunos:** usar o mesmo critério de listagem que o backend já usa (ex.: GET `/students` conforme permissão do usuário: admin, coordenador, diretor, tecadm). Se a API aceitar `city_id`, `school_id`, `class_id`, use esses query params para já vir filtrado; senão, carregue a lista e filtre no front (por escola/turma/nome).
- Objetivo: reduzir a lista até achar o aluno e pegar o **id do aluno** (`student.id` = `student_id` usado nas APIs de moedas).

---

## 5. Listagem de alunos

- **Fonte:** lista retornada por GET `/students` (ou endpoint que já retorne alunos com escola/turma conforme permissão).
- Exibir pelo menos: **nome**, **turma**, **escola**, e **saldo atual** (GET `/coins/balance?student_id=<id>` para cada linha, ou em lote se houver endpoint).
- **Seleção:** clique na linha (ou radio) → guardar `student_id` e, se quiser, nome e saldo para o painel “Aluno selecionado”.

---

## 6. Painel “Aluno selecionado”

- Mostrar: **Nome**, **ID** (para conferência) e **Saldo atual** (GET `/coins/balance?student_id=<id>`).
- Só habilitar os controles de “Dar moedas” / “Remover moedas” quando houver um aluno selecionado.

---

## 7. Ação: dar ou remover moedas

- **Dar moedas:**  
  POST `/coins/admin/credit`  
  Body: `{ "student_id": "<id>", "amount": <número>, "reason": "admin_credit", "description": "opcional" }`

- **Remover moedas:**  
  POST `/coins/admin/debit`  
  Body: `{ "student_id": "<id>", "amount": <número>, "reason": "admin_debit", "description": "opcional" }`

Campos na tela:
- **Quantidade:** número inteiro, obrigatório; para débito, validar no front que não excede o saldo (e o backend já retorna 400 se for insuficiente).
- **Motivo:** pode ser fixo (ex. `admin_credit` / `admin_debit`) ou um dropdown com outros motivos, se no futuro a API aceitar mais valores.
- **Descrição:** texto livre (opcional).

Após sucesso: atualizar o saldo exibido e, se houver, a lista de “Últimas transações” (GET `/coins/transactions?student_id=<id>&limit=5`).

---

## 8. APIs utilizadas (resumo)

| Ação na página        | Método e endpoint |
|----------------------|-------------------|
| Cidades              | GET conforme rotas de cidades/escolas do projeto |
| Escolas (por cidade) | GET escolas (com city_id se existir) |
| Turmas (por escola)  | GET classes (com school_id se existir) |
| Listar alunos       | GET `/students` (com filtros se a API suportar) |
| Saldo do aluno       | GET `/coins/balance?student_id=<id>` |
| Dar moedas           | POST `/coins/admin/credit` |
| Remover moedas       | POST `/coins/admin/debit` |
| Histórico (opcional) | GET `/coins/transactions?student_id=<id>&limit=5` |

Todas as chamadas com o token JWT do usuário logado (admin, coordenador, diretor ou tecadm para dar/remover).

---

## 9. Detalhes de UX

- **Permissão:** exibir a página de administração de moedas (com botões dar/remover) para roles que podem alterar no backend: `admin`, `coordenador`, `diretor`, `tecadm`; professor só consulta.
- **Feedback:** mensagem de sucesso após crédito/débito; em caso de 400 (ex.: saldo insuficiente), exibir a mensagem retornada pela API.
- **Validação:** quantidade > 0; no débito, avisar ou desabilitar se quantidade > saldo atual.
- **Mobile:** filtros em coluna ou accordion; tabela de alunos scrollável horizontal se necessário.

Com isso você consegue montar a página administrativa que usa filtros até chegar no aluno (e no `student_id`) e então dar ou remover moedas usando as rotas atuais do backend.
