# Módulo Mobile (offline-first)

Documentação em **`app/mobile/`** (este diretório).

Planejamento **revisado e fechado** para integração do app mobile com o backend, em **`PLANEJAMENTO_SINCRONIZACAO.md`**.

## Princípios fixos

- **Legado intocado:** login web, fluxos e hashes existentes **não** são alterados; **Werkzeug** permanece o único esquema de hash neste escopo.
- **Isolamento:** toda API nova sob **`/mobile/v1/`**; JWT mobile via **Flask-JWT-Extended**, separado do JWT atual da web.
- **Pacote:** alunos com `password_hash` (**formato Werkzeug documentado** para o app, §5.3), provas, questões, **`student_test_links`** explícitos, `sync_bundle_version` **monotônico por `school_id`**, `test_content_version` por **SHA-256** do canone da prova, `bundle_valid_until`; incremental = **snapshot completo** + substituição local (§10).
- **Upload:** `{ "submissions": [...] }`, processamento **por item**, resposta `results[]`; pacote expirado **rejeita** (§11); **`device_id`** UUID v4 imutável; ciclo **download completo → offline → upload** (§2.1).

## Documentos

| Arquivo | Conteúdo |
|---------|----------|
| [PLANEJAMENTO_SINCRONIZACAO.md](./PLANEJAMENTO_SINCRONIZACAO.md) | Decisões absolutas, contratos, versão, dispositivo, download/upload, limpeza, fases M1–M5 |

## Referência ao repositório (inalterada pelo módulo mobile)

- Login web: `app/routes/login.py`.
- Hist de senha: `werkzeug.security` em `app/utils/auth.py` e criação de usuários existente.
- Domínio de provas/respostas: `app/models/` (`Test`, `StudentAnswer`, etc.).

Detalhes executivos estão apenas no planejamento principal.
