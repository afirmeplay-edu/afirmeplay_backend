# 👋 COMECE AQUI - Migração Multi-Tenant

## 🎯 Você está aqui

Você precisa migrar o backend Innovaplay para arquitetura multi-tenant com schemas PostgreSQL separados por município.

**Este diretório contém tudo que você precisa.**

---

## 📚 O que há neste diretório?

```
migrations_multitenant/
├── 🟢 START_HERE.md              ← VOCÊ ESTÁ AQUI
├── 📖 INDEX.md                   ← Índice de todos os arquivos
├── 📘 README.md                  ← Documentação técnica completa
├── 🚀 QUICKSTART.md              ← Guia passo a passo (RECOMENDADO)
│
├── Scripts Python:
│   ├── check_prerequisites.py   ← 1️⃣ Execute primeiro
│   ├── backup_database.py       ← 2️⃣ Faça backup
│   ├── 0001_init_city_schemas.py ← 3️⃣ Migração principal
│   └── validate_migration.py    ← 4️⃣ Valide resultado
│
└── .gitignore                   ← Ignora logs e backups
```

---

## 🚦 Primeira Vez Aqui?

### Opção A: Rápido e Prático (Recomendado)

```bash
# 1. Abra o guia rápido
cat migrations_multitenant/QUICKSTART.md

# 2. Siga os passos
```

### Opção B: Entender Tudo Primeiro

```bash
# 1. Leia a documentação completa
cat migrations_multitenant/README.md

# 2. Veja o índice
cat migrations_multitenant/INDEX.md

# 3. Depois siga QUICKSTART.md
```

---

## ⚡ Execução Express (5 Minutos)

Se você já sabe o que está fazendo:

```bash
cd migrations_multitenant

# 1. Verificar pré-requisitos
python check_prerequisites.py

# 2. Backup
python backup_database.py

# 3. Dry run (simulação)
python 0001_init_city_schemas.py --dry-run

# 4. Migração real
python 0001_init_city_schemas.py
# Digite: CONFIRMO

# 5. Validação
python validate_migration.py
```

---

## 🎓 Primeira Migração? (30 Minutos)

### Passo 1: Entender (10 min)

1. Leia `QUICKSTART.md` seções:
    - "Pré-requisitos"
    - "Passo a Passo"

### Passo 2: Preparar (5 min)

```bash
# Instalar dependências
pip install psycopg2-binary python-dotenv

# Verificar ambiente
python check_prerequisites.py
```

### Passo 3: Backup (5 min)

```bash
python backup_database.py
```

### Passo 4: Testar (5 min)

```bash
# Executar em modo simulação
python 0001_init_city_schemas.py --dry-run
```

### Passo 5: Migrar (5 min)

```bash
# Executar para valer
python 0001_init_city_schemas.py
```

### Passo 6: Validar (2 min)

```bash
python validate_migration.py
```

---

## ❓ Dúvidas Frequentes

### P: Isso vai quebrar meu banco de dados?

**R:** Não! O script é seguro:

- ✅ NÃO remove tabelas existentes
- ✅ NÃO move dados
- ✅ Apenas CRIA nova estrutura
- ✅ Pode rodar múltiplas vezes (idempotente)
- ✅ Pede confirmação "CONFIRMO"

### P: E se algo der errado?

**R:** Você tem backup!

```bash
# Restaurar backup
pg_restore -d afirmeplay_dev backup_*.dump
```

### P: Preciso parar minha aplicação?

**R:** Para esta migração inicial, NÃO. Ela apenas cria estrutura nova, não mexe na antiga.

### P: Quanto tempo demora?

**R:**

- 1 município: ~2 minutos
- 10 municípios: ~10 minutos
- 100 municípios: ~1 hora

### P: Posso rodar em produção direto?

**R:** NÃO! Sempre:

1. Testar em DEV primeiro
2. Validar resultado
3. Planejar janela de manutenção para PROD

---

## 🆘 Precisa de Ajuda?

| Situação                  | Arquivo                              |
| ------------------------- | ------------------------------------ |
| Erro de Python            | check_prerequisites.py               |
| Erro de conexão com banco | README.md → Troubleshooting          |
| Erro durante migração     | Logs em migration*0001*\*.log        |
| Validação falhou          | validate_migration.py (mostra erros) |
| Não sei o que fazer       | QUICKSTART.md                        |
| Quero entender melhor     | README.md                            |

---

## ✅ Tudo Pronto?

**Checklist antes de começar:**

- [ ] Tenho backup do banco
- [ ] Testei em ambiente DEV
- [ ] Li o QUICKSTART.md
- [ ] check_prerequisites.py passou
- [ ] DATABASE_URL está configurado
- [ ] Sei como fazer rollback se necessário

**Tudo OK? Vá para:**

```bash
cat migrations_multitenant/QUICKSTART.md
```

---

## 🎉 Após a Migração

**Sucesso! E agora?**

1. **Validar:**

    ```bash
    python validate_migration.py
    ```

2. **Verificar logs:**

    ```bash
    cat migration_0001_*.log
    ```

3. **Próximas etapas:**
    - [ ] Script 0002: Migração de dados
    - [ ] Script 0003: Limpeza de tabelas antigas
    - [ ] Script 0004: Ajustes de application code

**Documentação futura:**

- Como usar schemas dinâmicos no Flask/SQLAlchemy
- Como fazer queries cross-schema
- Como implementar schema routing

---

## 📊 Resumo do que será criado

Após executar `0001_init_city_schemas.py`:

```
PostgreSQL Database
│
├── 🔵 SCHEMA: public (GLOBAL)
│   ├── users (sem alteração)
│   ├── manager (sem alteração)
│   ├── city (sem alteração)
│   ├── question ← MODIFICADO (+ colunas de escopo)
│   └── ... outras tabelas globais
│
└── 🟢 SCHEMAS: city_<uuid> (TENANT)
    ├── city_abc123_def4_5678_90ab_cdef12345678/
    │   ├── school (54 tabelas)
    │   ├── student
    │   ├── teacher
    │   ├── test
    │   ├── school_managers ← NOVA
    │   └── ... 50+ tabelas
    │
    ├── city_xyz789_abc1_2345_67cd_ef8901234567/
    │   └── ... (mesmas 54 tabelas)
    │
    └── ... (1 schema por município)
```

---

**Versão:** 1.0  
**Data:** 2026-02-10  
**Status:** ✅ Pronto para uso

**👉 Próximo passo:** Abra `QUICKSTART.md`
