# Planejamento: sincronização mobile offline-first (revisado — decisões fechadas)

Documento de arquitetura para execução por desenvolvimento. Todas as decisões abaixo são **normativas**; escopo exclui alteração do sistema web legado e inclusão de tecnologias não listadas.

---

## 1. Registro de decisões absolutas

| Regra | Enunciado |
|--------|-----------|
| **Legado intocado** | Não alterar autenticação existente, fluxo de login atual (`app/routes/login.py` e correlatos), nem estratégia de hash atual. |
| **Werkzeug obrigatório** | Manter `generate_password_hash` / `check_password_hash` como única forma de hash no domínio afetado por este módulo. **Não** implementar bcrypt, **não** migrar hashes existentes, **não** criar estratégia híbrida. |
| **Módulo isolado** | Novos endpoints **exclusivamente** sob o prefixo `/mobile/v1/`. Novas regras de negócio e de segurança **não** devem impactar rotas, decorators ou fluxos da web. |
| **JWT mobile** | Autenticação **online** dos consumidores mobile (aplicador/admin) usa **Flask-JWT-Extended**, em fluxo **próprio** ao módulo mobile. **Não** unificar nem substituir o JWT atual da web. |
| **Conflito online × offline** | Regra de negócio: um aluno **não** realiza a mesma prova online e offline em paralelo. **Não** implementar detecção de conflito, merge nem priorização entre modos. |

---

## 2. Objetivo do módulo

Permitir que **aplicador ou perfil autorizado** no tenant:

1. Autentique-se **online** via API mobile (JWT emitido com Flask-JWT-Extended).
2. **Baixe** um pacote versionado e paginável/incremental com alunos (incluindo `password_hash` Werkzeug), provas, questões, **vínculos explícitos** `aluno_id` + `prova_id`, metadados de versão e validade.
3. Opere **offline** no dispositivo (validação de senha com o mesmo algoritmo que o backend; armazenamento local **fora do escopo do backend**, exceto decisão registrada: banco local cifrado com **SQLCipher**).
4. **Envie** submissões com `submission_id` (UUID), respostas, metadados e `device_id`, com **idempotência** e aceitação de envios tardios.

### 2.1 Pré-condição: ordem de sincronização no cliente

O backend assume o seguinte ciclo **contratual** entre aplicador/dispositivo e servidor:

1. **Download completo** — obter e consolidar o pacote para o `school_id` (e escopo) acordado: todas as páginas necessárias e, quando usado incremental, o **snapshot completo** descrito em §10, até o cliente possuir um estado local coerente com o `sync_bundle_version` vigente.
2. **Uso offline** — login dos alunos, provas e coleta de respostas apenas contra esse estado local.
3. **Upload** — envio das submissões quando houver conectividade.

O servidor **não** define fluxo de correção para “upload antes de download” ou pacote parcial tratado como definitivo: validações de vínculo, `test_content_version` e `bundle_valid_until` podem falhar de forma previsível se essa ordem for violada. A responsabilidade de respeitar **download completo → offline → upload** é **do cliente**.

---

## 3. Contextualização do repositório (somente leitura)

Esta seção **descreve** o existente; **nenhuma** mudança aqui é planejada.

- **Web:** login continua como está; validação de senha via Werkzeug em `app/utils/auth.py` e modelos de usuário.
- **Domínio:** provas (`Test`), questões, `TestQuestion`, turmas/`ClassTest`, alunos (`Student` + `User.password_hash`), respostas (`StudentAnswer`), sessões (`TestSession`).
- **Multitenancy:** manter o mesmo isolamento por município/schema que o restante da API; rotas `/mobile/v1/*` devem resolver tenant **da mesma forma** que as demais rotas seguras (middleware/headers já adotados pelo projeto).
- **Auditoria:** `student_password_logs` e dados sensíveis continuam regidos pelas políticas já existentes; o pacote mobile **inclui** `password_hash` conforme decisão de produto (ver §5).

---

## 4. Autenticação mobile (isolada)

### 4.1 Responsabilidades

- **Emitir** access token (e, se o time definir na implementação, refresh token) **somente** para rotas sob `/mobile/v1/`.
- **Validar** credenciais com a **mesma** lógica de verificação de senha que o sistema já usa (Werkzeug), **sem** duplicar tabelas nem alterar o modelo `User`.
- **Não** reutilizar o endpoint `POST /login/` para o app mobile como contrato oficial: o contrato mobile será **explicitamente** documentado (ex.: `POST /mobile/v1/auth/login`), ainda que internamente possa chamar funções compartilhadas de verificação (apenas helpers, sem mudar comportamento da web).

### 4.2 Claims e tempo de vida

- Definir claims mínimos no JWT mobile: identidade do usuário aplicador, `tenant_id` / contexto de cidade compatível com o middleware atual, `role`, expiração curta (**valor exato** fixado na implementação e na OpenAPI).
- O token **não** substitui login offline do aluno; serve apenas a chamadas **online** (download, upload, eventual registro de dispositivo, mídia).

### 4.3 Conferência de dispositivo

Toda requisição autenticada à API mobile deve transportar **`device_id`** (ver §6). O backend **registra** o par `(tenant, usuário autenticado, device_id)` e rejeita ou audita desvios conforme política definida na implementação (ex.: dispositivo não registrado tentando sincronizar).

---

## 5. Senhas e conteúdo do pacote offline

### 5.1 Regra fechada

- O **download** inclui, para cada aluno elegível ao pacote, o campo **`password_hash` atual** persistido no servidor (formato Werkzeug, compatível com `check_password_hash` no cliente, usando a mesma função/parametrização que o servidor utiliza na criação/atualização de senha).
- **Não** implementar derivação adicional de credenciais no backend para este fluxo.
- O aplicativo **valida offline** comparando entrada do aluno com esse hash usando verificação **compatível** com `check_password_hash`; o contrato de formato está em **§5.3**.

### 5.2 Segurança complementar (fora do código backend, obrigatória no produto)

- **SQLCipher** no armazenamento local (responsabilidade do app).
- **Validade curta do pacote** (ver §11): o backend expõe no pacote datas/versão que permitem ao app invalidar dados expirados.
- Risco residual (exposição do hash no pacote) é **aceito** com as mitigações acima; não abrir alternativas de protocolo neste documento.

### 5.3 Formato do `password_hash` (Werkzeug) — contrato com o mobile

A validação offline **só é possível** se o app reproduzir a mesma semântica de `werkzeug.security.check_password_hash(hash, plaintext)` sobre a **string exata** enviada no download. O planejamento **fixa** os requisitos de documentação e compatibilidade:

| Item | Definição |
|------|-----------|
| **Origem** | O valor no pacote é **byte-a-byte** igual ao `password_hash` persistido no servidor (modelo `User`), produzido por `generate_password_hash` e verificado por `check_password_hash` no backend. |
| **Algoritmo** | **`pbkdf2:sha256`** — método padrão do Werkzeug para geração de hash neste contexto (não usar suposições de formato genérico; validar contra a versão **Werkzeug** fixada em `requirements.txt`). |
| **Estrutura da string** | String única em que **salt** e **parâmetros** (incluindo **iterations** do PBKDF2) estão **embutidos** na própria codificação Werkzeug (esquema `method:variant:iterations$<salt_b64>$<hash_b64>` ou equivalente **exato** da versão em uso — copiar formato literal da documentação Werkzeug correspondente à dependência do projeto). |
| **React Native** | **Sem** suporte nativo a esse formato; o time mobile **deve** integrar verificação via biblioteca ou bridge que implemente verificação **compatível** com a string Werkzeug recebida (equivalente a `check_password_hash`). |
| **Entregável backend** | Na **OpenAPI / guia de integração mobile**, incluir: (a) versão **Werkzeug** do servidor; (b) exemplo **anonimizado** de string `password_hash` (apenas estrutura/prefixo); (c) confirmação explícita de que o método é **`pbkdf2:sha256`** e o valor de **iterations** efetivo em produção (lido do código/config, sem alterar geração legada). |

**Não** delegar ao app “o mesmo algoritmo” sem esse anexo: sem o detalhe acima, o login offline **não** é implementável de forma confiável.

---

## 6. Identificação de dispositivo (`device_id`)

### 6.1 Formato e transporte

- **`device_id`:** **UUID versão 4** (RFC 4122), gerado **uma vez** na primeira execução da aplicação (ou na primeira chamada mobile), **persistido** em armazenamento local do app e **imutável** durante o ciclo de vida da instalação (**não** regenerar nem permitir troca de identidade silenciosa). Isso evita colisão de auditoria e fraude de identidade de dispositivo nas tráfegos `/mobile/v1/*`.
- **Transporte obrigatório:** em **todas** as requisições HTTP aos endpoints `/mobile/v1/*`, via header canônico (ex.: `X-Device-Id`) **ou** parâmetro acordado **único** por método; a escolha final é **uma** convenção documentada na OpenAPI (não duplicar formas opcionais conflitantes).

### 6.2 Registro no backend

- Persistir entidade lógica **`mobile_device`** (nome de tabela a definir na migration) com, no mínimo: `device_id`, `user_id` (aplicador que autenticou), `tenant`/`city` scope, `first_seen_at`, `last_seen_at`, opcional `label`/`platform`.
- Operações de sync (download/upload) **atualizam** `last_seen_at` e validam que o dispositivo está vinculado ao usuário/tenant esperado.

---

## 7. Vínculo aluno–prova (obrigatório e explícito)

### 7.1 Regra normativa

- O corpo do pacote de download **deve** incluir uma coleção **`student_test_links`** (nome de campo na API a fixar na OpenAPI), onde **cada elemento** contém **obrigatoriamente**:
  - `student_id` (id servidor),
  - `test_id` (id servidor).
- O aplicativo **não** infere vínculo a partir de turma, série ou listas desacopladas.
- O backend **garante consistência:** apenas pares **explicitamente autorizados** pela regra de negócio do tenant (ex.: agregação a partir de `ClassTest` e matrícula do aluno **no servidor**, antes de serializar o pacote). A implementação traduz o modelo relacional existente **nesta** estrutura canônica.

### 7.2 Upload

- Cada submissão referencia `student_id` e `test_id`. O backend **valida** que o par constitui vínculo permitido **no estado atual do servidor** no momento do processamento (não confiar apenas no cliente).  
- Se o vínculo deixar de existir após o download, a política de recusa/aceitação com mensagem de erro **contratual** deve ser definida na OpenAPI (sem lógica de merge entre modos).

---

## 8. Versionamento

### 8.1 `sync_bundle_version`

- Valor inteiro **estritamente monotônico crescente** por **`school_id`** (no âmbito do tenant corrente): cada nova geração de snapshot para **aquela escola** incrementa o contador **somente** daquela escola. **Não** usar sequência única agregada por tenant sem particionar por `school_id` — evita versões inconsistentes e quebra do incremental quando há várias escolas no mesmo município.
- Todas as páginas de uma mesma geração de download para aquele `school_id` compartilham o **mesmo** `sync_bundle_version` até o servidor publicar uma nova geração (novo incremento para aquela escola).
- Respostas de upload carregam o **`sync_bundle_version` referenciado** pelo app (último bundle **completo** aplicado localmente para aquela escola) para auditoria e suporte.

### 8.2 Versão de prova — `test_content_version` (fonte: hash de conteúdo)

- Para cada `test_id` no pacote, o download inclui **`test_content_version`**: **hash criptográfico** do conteúdo da prova, normativamente **SHA-256** em **hexadecimal minúsculo**, calculado no servidor sobre um **canone estável** (ordenação e campos exatos — lista fechada na OpenAPI / implementação: questões, enunciados, alternativas, identificadores, e demais campos que afetem a prova no offline).
- **Motivo:** automático, integridade real, sem contador sujeito a erro humano.
- **Upload:** o cliente envia o `test_content_version` recebido no bundle; o servidor **recalcula** o hash com o **mesmo canone** sobre o estado **atual** da prova e **rejeita** se divergir (conteúdo alterado após o download — exige novo sync).
- **Distinção:** `sync_bundle_version` pode avançar sem mudar o conteúdo de uma prova (hash igual); edição de prova gera novo hash e novo download para uso offline.

---

## 9. Sincronização — download

### 9.1 Conteúdo obrigatório (agregado ou particionado)

Em uma ou mais respostas paginadas/incrementais (ver §10), o conjunto entregue para um `sync_bundle_version` deve permitir ao cliente montar localmente:

- **Alunos** elegíveis: identificadores, nome, `registration`/login conforme necessário, **`password_hash`** (Werkzeug).
- **Provas** (`test`): campos necessários para renderização offline acordados na OpenAPI.
- **Questões** vinculadas a essas provas: ordem, enunciado, alternativas, metadados acordados, referências a mídia.
- **`student_test_links`:** apenas pares explícitos `(student_id, test_id)`.
- **Metadados de pacote:** `sync_bundle_version`, `bundle_valid_until` (ISO 8601), e por prova o `test_content_version`.
- **Manifest de mídia** (pode ser endpoint auxiliar): lista de assets com URLs ou identificadores para download autenticado **mobile**.

### 9.2 Autorização

- Apenas perfis permitidos (roles) acordados com o produto — mapear para `RoleEnum` existente **sem** alterar permissões da web; aplicar **novos** decorators/checagens **somente** nas rotas `/mobile/v1/`.

### 9.3 Mídia

- Evitar corpo JSON gigante: mídia via rotas dedicadas (ex.: `GET /mobile/v1/sync/media/...`) com o mesmo JWT mobile + `device_id`.

---

## 10. Paginação e sync incremental (obrigatório na primeira entrega útil)

Pelo menos **uma** das estratégias abaixo deve estar implementada **antes** de considerar o download “completo” em produção; **combinar ambas** quando o volume exigir.

### 10.1 Semântica do incremental — **snapshot completo (substituição), NÃO patch parcial**

Para um dado `school_id`, quando o cliente informa `since_bundle_version` **menor** que a versão atual da escola, o servidor responde com o **estado atual completo** do escopo solicitado para aquela escola **na nova** `sync_bundle_version` (ou seja: conjunto **integral** de alunos, provas, questões, `student_test_links` e metadados necessários àquele snapshot), possivelmente **espalhado em várias páginas**.

- O app, após concluir **todas** as páginas dessa geração, **substitui localmente** o cache daquela escola pelo novo estado (**não** aplicar semântica de patch/diff por entidade).
- **Não** especificar nem implementar delta parcial tipo “só criados” / “só alterados” no MVP: reduz complexidade e ambiguidade no cliente; o ganho de rede fica na **paginação** e no uso de `since_bundle_version` apenas como **atalho** (“já estou na versão N, não preciso baixarde novo” quando N já é a atual — resposta 304 ou corpo vazio com versão confirmada, conforme OpenAPI).

**Primeira carga:** omitir `since_bundle_version` ou enviar `0` (contrato único na OpenAPI); o servidor devolve o snapshot completo atual em páginas.

### 10.2 Paginação

- Parâmetros explícitos (`cursor` ou `page` + `page_size`) para fatiar listas grandes, **sem** alterar a regra de §10.1: todas as páginas pertencem à **mesma** geração (`sync_bundle_version`) daquele `school_id`.

**Requisito:** nenhum fluxo de download “sem limite” em escola de grande porte.

---

## 11. Validade do pacote e limpeza de dados

### 11.1 Política de expiração (backend)

- Cada resposta de download inclui **`bundle_valid_until`** calculada pelo servidor com base em política configurável (ex.: variável de ambiente `MOBILE_BUNDLE_TTL_HOURS`, valor padrão sugerido **48 h** — **fixar na implementação**).
- **Comportamento fechado:** se o horário do servidor for **posterior** a `bundle_valid_until` associado ao pacote referenciado no upload, o backend **rejeita** o envio com erro contratual (ex.: HTTP **422** ou **403** com código `BUNDLE_EXPIRED`). **Não** aceitar upload expirado com mero aviso. Garante consistência e evita ingestão de dados contra snapshot inválido; o cliente deve fazer **novo download** antes de reenviar.

### 11.2 Recomendações para o app (não implementadas no backend)

- Apagar ou rotacionar chaves SQLCipher após sincronização bem-sucedida das submissões pendentes, quando o aplicador confirmar “fim do ciclo” da aplicação.
- Remover pacote local após expiração ou após upload completo, conforme UX do produto.

---

## 12. Sincronização — upload

### 12.1 Formato do corpo — **lote (batch) em array**

- `POST /mobile/v1/sync/upload` recebe um **JSON** com um campo **`submissions`** (array ordenado de objetos), cada objeto sendo **uma** submissão independente.
- **Não** usar NDJSON neste contrato; **não** deixar formato aberto entre alternativas.

### 12.2 Campos por item do array (cada submissão)

- **`submission_id`:** UUID v4, gerado no cliente **uma vez** por submissão lógica.
- **`device_id`:** conforme §6 (também no header da requisição; deve coincidir).
- **`student_id`**, **`test_id`**, **`test_content_version`** e **`sync_bundle_version`** de referência.
- **Respostas:** estrutura alinhada ao modelo `StudentAnswer` (campos exatos na OpenAPI).
- **Metadados obrigatórios mínimos:** timestamps de início/fim no cliente, identificador de tentativa se aplicável, tempo efetivo se coletado, flag `offline_origin: true` (recomendado para auditoria).

### 12.3 Processamento e resposta — **por item, sem atomicidade de lote**

- O backend processa cada elemento do array **individualmente** (ordem preservada recomendada para logs).
- **Não** garantir transação única sobre o lote inteiro: um item pode ser aplicado e outro falhar no mesmo POST.
- Corpo de resposta **obrigatório:** objeto com **`results`**, array na **mesma ordem** que `submissions`, cada entrada contendo no mínimo: `submission_id`, `status` (`applied` | `duplicate_ignored` | `error`), `http_equivalent` opcional por item, `message` ou código de erro, identificadores persistidos quando `applied` / `duplicate_ignored`.
- **HTTP do POST:** resposta **200** quando autenticação e parse do corpo forem válidos e o servidor tiver **terminado** o processamento de todos os itens (cada um com desfecho em `results`). Erros **por item** não alteram o código HTTP global: ficam em `status: error` no elemento correspondente. **400** para JSON inválido ou ausência de `submissions`; **401** / **403** para falha de auth ou dispositivo; **413** se limite de tamanho do lote for excedido (limite documentado na OpenAPI).
- **Retry:** o app pode reenviar apenas itens com `error` não idempotente; itens `applied` / `duplicate_ignored` **não** devem ser reprocessados de novo com o mesmo `submission_id`.

### 12.4 Regras por item

- **Aceitar dados atrasados:** processar cada item enquanto regras de negócio e **`bundle_valid_until`** permitirem (ver §11 — expirado **rejeita** o item).
- **Idempotência:** se `submission_id` já existir, marcar item como **`duplicate_ignored`** com `already_processed: true` e ids existentes, **sem** duplicar respostas persistidas.
- **Integridade:** validar `question_id` ∈ `test_id`, vínculo `student_id`+`test_id` e `test_content_version` conforme §7 e §8.

### 12.5 Persistência

- Mapping para `TestSession` / `StudentAnswer` (e tabelas auxiliares de idempotência) **sem** alterar comportamento das rotas web existentes — serviços novos ou camadas dedicadas ao namespace mobile.

---

## 13. Idempotência e unicidade

- Tabela (ou índice único) **`mobile_sync_submission`** (nome a definir) com pelo menos: `submission_id` **UNIQUE**, `device_id`, `received_at`, payload resumido ou referência, `user_id` aplicador, status `applied`/`duplicate_ignored`.
- Duplicata = mesmo `submission_id`; ignorar e retornar no **item** correspondente do batch, conforme §12.4.

---

## 14. Esboço de superfície HTTP (para OpenAPI)

Prefixo fixo: **`/mobile/v1/`**.

| Método | Rota (exemplo) | Uso |
|--------|----------------|-----|
| POST | `/mobile/v1/auth/login` | Credenciais aplicador → JWT Flask-JWT-Extended |
| POST | `/mobile/v1/devices/register` | Opcional: registro explícito do `device_id` (pode ser unificado com primeiro sync) |
| GET | `/mobile/v1/sync/bundle` | Download paginado/incremental do pacote (query: `school_id`, `since_bundle_version`, paginação) |
| GET | `/mobile/v1/sync/media/<asset_id>` | Download de mídia referenciada no manifest |
| POST | `/mobile/v1/sync/upload` | Corpo: `{ "submissions": [ ... ] }` — processamento **por item**, resposta com **`results`** alinhado à ordem do array |

**Headers comuns:** `Authorization: Bearer`, `X-Device-Id`, headers de tenant já usados pelo projeto para admins/aplicadores.

**Nota:** Nomes finais de rotas podem ser ajustados desde que permaneçam sob `/mobile/v1/`.

---

## 15. Modelagem sugerida (implementação)

Entidades **novas** (nomes indicativos):

- `mobile_device` — registro de dispositivos.
- `mobile_sync_submission` — idempotência por `submission_id`.
- `mobile_sync_bundle_generation` (opcional) — histórico de `sync_bundle_version` **por `school_id`** (dentro do tenant) com timestamp e hash opcional do conjunto.

Campos em tabelas existentes: **evitar** na medida do possível; preferir tabelas auxiliares para não tocar no legado. Se for **estritamente necessário** armazenar `test_content_version` em `Test`, avaliar migration dedicada **sem** alterar código das rotas web.

---

## 16. Testes e observabilidade

- Testes automatizados: idempotência por `submission_id` (dois POSTs com o mesmo item), **batch** com falha em um item e sucesso em outro (resposta **200** + `results` mistos), download paginado, incremental **snapshot** `since_bundle_version`, **rejeição** de item com pacote após `bundle_valid_until`, vínculo inválido no upload, `test_content_version` divergente.
- Logs estruturados: `device_id`, `submission_id`, `sync_bundle_version`, `test_content_version`, `school_id`, duração.
- Métricas: taxa de duplicatas ignoradas, downloads por dispositivo, erros de versão.

---

## 17. Fases de entrega (execução)

| Fase | Escopo |
|------|--------|
| **M1 — Fundações** | Blueprint `/mobile/v1/`, configuração Flask-JWT-Extended **somente** para este blueprint, `POST /auth/login` mobile, modelo `mobile_device`, middleware exigindo `device_id`, CORS/headers se necessário. |
| **M2 — Download v1** | `GET /sync/bundle` com **paginação ou incremental obrigatório**, emissão de `sync_bundle_version`, `test_content_version`, `student_test_links` explícitos, `bundle_valid_until`, alunos com `password_hash`, provas e questões + manifest de mídia mínimo. |
| **M3 — Mídia** | Endpoint(s) de mídia com mesma autenticação mobile; validação de `asset_id` pertencente ao bundle/manifest do tenant. |
| **M4 — Upload** | `POST /sync/upload`, persistência mapeada para domínio de respostas, idempotência, validação de vínculo e de versão de prova. |
| **M5 — Endurecimento** | Testes de carga em listas grandes, políticas de TTL configuráveis, documentação OpenAPI/publicada, revisão LGPD (auditoria de downloads por usuário/dispositivo). |

---

## 18. Itens explicitamente fora de escopo

- Alteração do login web, migração de hash, bcrypt, unificação global de JWT.
- Lógica de merge ou resolução de conflito entre sessão online e offline.
- Implementação de SQLCipher ou UX de limpeza no cliente (apenas recomendações em §11.2).
- Derivação de credenciais adicional no servidor para o fluxo offline.

---

## 19. Próximo passo operacional imediato

1. Redigir **fragmento OpenAPI** (`swagger.yaml` ou arquivo dedicado) com schemas de `student_test_links`, paginação/incremental, upload e códigos de erro de versão/expiração.
2. Especificar **exatamente** no código de serviço: (a) incremento de `sync_bundle_version` **por `school_id`**; (b) canone e função **SHA-256** para `test_content_version`; (c) schema de resposta do batch upload (`results[]`).
3. Iniciar **M1** sem modificar rotas ou modelos usados exclusivamente pela web.
