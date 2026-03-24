# ⚡ Solução Rápida - Erro nos Pré-requisitos

## 🎯 Seu Problema Atual

Você está tentando executar de dentro da pasta `migrations_multitenant/`, mas precisa executar da **raiz do projeto**.

---

## ✅ Solução em 3 Passos

### Passo 1: Voltar para Raiz do Projeto

```powershell
# Você está aqui (ERRADO):
PS C:\Users\Artur Calderon\Documents\Programming\innovaplay_backend\migrations_multitenant>

# Execute:
cd ..

# Agora você está aqui (CORRETO):
PS C:\Users\Artur Calderon\Documents\Programming\innovaplay_backend>
```

### Passo 2: Verificar que .env existe

```powershell
# Verificar
Test-Path app\.env
# Deve retornar: True

# Ver DATABASE_URL
Select-String -Path app\.env -Pattern "DATABASE_URL"
# Deve mostrar: DATABASE_URL=postgresql://...
```

### Passo 3: Executar Verificação

```powershell
# Execute da RAIZ do projeto
python migrations_multitenant\check_prerequisites.py
```

---

## 🔧 Se ainda der erro de pg_dump

O `pg_dump` é **OPCIONAL** para a migração inicial. Você pode:

### Opção A: Pular backup por enquanto

```powershell
# Execute apenas a migração
python migrations_multitenant\0001_init_city_schemas.py --dry-run
python migrations_multitenant\0001_init_city_schemas.py
python migrations_multitenant\validate_migration.py
```

### Opção B: Instalar pg_dump (5 minutos)

1. **Download rápido:**
    - https://www.postgresql.org/download/windows/
    - "Download the installer"
    - Na instalação, marque apenas "Command Line Tools"

2. **Reiniciar PowerShell**

3. **Verificar:**
    ```powershell
    pg_dump --version
    ```

---

## 🚀 Executar Migração Agora (SEM backup)

Se quiser executar sem instalar pg_dump:

```powershell
# 1. Voltar para raiz
cd "C:\Users\Artur Calderon\Documents\Programming\innovaplay_backend"

# 2. Ativar venv
.\venv\Scripts\Activate.ps1

# 3. DRY RUN (teste)
python migrations_multitenant\0001_init_city_schemas.py --dry-run

# 4. Se passou OK, executar:
python migrations_multitenant\0001_init_city_schemas.py

# 5. Validar
python migrations_multitenant\validate_migration.py
```

---

## 📝 Comandos Prontos (Copy & Paste)

### Para DEV (banco atual):

```powershell
cd "C:\Users\Artur Calderon\Documents\Programming\innovaplay_backend"
.\venv\Scripts\Activate.ps1
python migrations_multitenant\0001_init_city_schemas.py --dry-run
```

Se dry run passar:

```powershell
python migrations_multitenant\0001_init_city_schemas.py
# Digite: CONFIRMO
```

Depois validar:

```powershell
python migrations_multitenant\validate_migration.py
```

---

## 🆘 Se Continuar com Problemas

### Verificar DATABASE_URL manualmente:

```powershell
# Ver conteúdo do .env
Get-Content app\.env | Select-String "DATABASE_URL"

# Testar conexão
python -c "import psycopg2; import os; from dotenv import load_dotenv; load_dotenv('app/.env'); print('DATABASE_URL:', os.getenv('DATABASE_URL')); conn = psycopg2.connect(os.getenv('DATABASE_URL')); print('✅ Conectado!'); conn.close()"
```

### DATABASE_URL deve estar assim:

```
DATABASE_URL=postgresql://postgres:devpass@147.79.87.213:5432/afirmeplay_dev
```

**Não:**

- ❌ `postgresql://localhost:5432/...` (seria banco local)
- ❌ `postgresql://...devdb` (nome antigo)

**Sim:**

- ✅ `postgresql://postgres:devpass@147.79.87.213:5432/afirmeplay_dev`
- ✅ `postgresql://postgres:prodpass@147.79.87.213:5432/afirmeplay_prod`

---

## 💡 Dica: Usar o Script PowerShell

Criamos um script que faz tudo automaticamente:

```powershell
# Da raiz do projeto:
.\migrations_multitenant\run_migration.ps1 -SkipBackup

# Com backup (se tiver pg_dump):
.\migrations_multitenant\run_migration.ps1

# Apenas dry run:
.\migrations_multitenant\run_migration.ps1 -DryRun -SkipBackup
```

---

**TL;DR:**

```powershell
cd "C:\Users\Artur Calderon\Documents\Programming\innovaplay_backend"
.\venv\Scripts\Activate.ps1
python migrations_multitenant\0001_init_city_schemas.py --dry-run
```

Se funcionar, executar para valer:

```powershell
python migrations_multitenant\0001_init_city_schemas.py
```
