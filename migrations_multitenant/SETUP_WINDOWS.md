# 🪟 Setup no Windows - Guia Completo

## ⚠️ Você precisa executar os scripts da RAIZ do projeto!

### ❌ Errado (onde você está agora):

```powershell
PS C:\Users\Artur Calderon\Documents\Programming\innovaplay_backend\migrations_multitenant>
python check_prerequisites.py
```

### ✅ Correto:

```powershell
# Voltar para raiz do projeto
cd ..

# Agora você está em:
PS C:\Users\Artur Calderon\Documents\Programming\innovaplay_backend>

# Execute os scripts assim:
python migrations_multitenant\check_prerequisites.py
python migrations_multitenant\backup_database.py
python migrations_multitenant\0001_init_city_schemas.py
python migrations_multitenant\validate_migration.py
```

---

## 📦 Instalar PostgreSQL Client Tools (pg_dump)

### Opção 1: Via Instalador Oficial (Recomendado)

1. **Download:**
    - Acesse: https://www.postgresql.org/download/windows/
    - Clique em "Download the installer"
    - Baixe a versão mais recente (ex: PostgreSQL 16)

2. **Instalar:**
    - Execute o instalador
    - **IMPORTANTE:** Na tela "Select Components", marque:
        - ✅ Command Line Tools (necessário para pg_dump)
        - ⬜ PostgreSQL Server (OPCIONAL - só se quiser servidor local)
        - ⬜ pgAdmin (OPCIONAL - interface gráfica)
        - ⬜ Stack Builder (OPCIONAL)
3. **Adicionar ao PATH:**
    - O instalador geralmente adiciona automaticamente
    - Caso não tenha adicionado:
        - Caminho padrão: `C:\Program Files\PostgreSQL\16\bin`
        - Adicione manualmente ao PATH do Windows

4. **Verificar instalação:**
    ```powershell
    pg_dump --version
    # Deve mostrar: pg_dump (PostgreSQL) 16.x
    ```

### Opção 2: Via Chocolatey (Mais Rápido)

Se você tem Chocolatey instalado:

```powershell
# Instalar apenas client tools
choco install postgresql-client

# OU instalar PostgreSQL completo
choco install postgresql
```

### Opção 3: Download Direto (Portável)

1. **Download ZIP:**
    - Acesse: https://www.enterprisedb.com/download-postgresql-binaries
    - Baixe "PostgreSQL Binaries" para Windows
    - Extraia para: `C:\PostgreSQL\bin`

2. **Adicionar ao PATH:**

    ```powershell
    # PowerShell como Administrador
    $env:Path += ";C:\PostgreSQL\bin"

    # Permanente (adicionar no PATH do sistema)
    [Environment]::SetEnvironmentVariable("Path", $env:Path + ";C:\PostgreSQL\bin", "Machine")
    ```

3. **Verificar:**
    ```powershell
    pg_dump --version
    ```

---

## 🔧 Configurar Ambiente

### 1. Confirmar que .env existe:

```powershell
# Voltar para raiz do projeto
cd "C:\Users\Artur Calderon\Documents\Programming\innovaplay_backend"

# Verificar se .env existe
Test-Path app\.env
# Deve retornar: True

# Ver conteúdo (primeiras linhas)
Get-Content app\.env -Head 5
```

### 2. Confirmar DATABASE_URL:

```powershell
# Ler DATABASE_URL do .env
Select-String -Path app\.env -Pattern "DATABASE_URL"

# Deve mostrar algo como:
# DATABASE_URL=postgresql://postgres:devpass@147.79.87.213:5432/devdb
```

### 3. Para trocar entre DEV e PROD:

Você pode criar múltiplos arquivos .env:

```
app/
├── .env                  # Atual
├── .env.dev             # Desenvolvimento
└── .env.prod            # Produção
```

**Copiar para usar:**

```powershell
# Usar DEV
Copy-Item app\.env.dev app\.env

# Usar PROD
Copy-Item app\.env.prod app\.env
```

---

## 🎯 Executar Verificação de Pré-requisitos

```powershell
# IMPORTANTE: Execute da RAIZ do projeto!
cd "C:\Users\Artur Calderon\Documents\Programming\innovaplay_backend"

# Ativar venv (se usar)
.\venv\Scripts\Activate.ps1

# Verificar pré-requisitos
python migrations_multitenant\check_prerequisites.py
```

**Resultado esperado:**

```
✅ TUDO OK! Pronto para executar migração.

Próximos passos:
  1. python migrations_multitenant\backup_database.py
  2. python migrations_multitenant\0001_init_city_schemas.py --dry-run
  3. python migrations_multitenant\0001_init_city_schemas.py
  4. python migrations_multitenant\validate_migration.py
```

---

## 🚀 Fluxo Completo no Windows

```powershell
# 1. Ir para raiz do projeto
cd "C:\Users\Artur Calderon\Documents\Programming\innovaplay_backend"

# 2. Ativar ambiente virtual
.\venv\Scripts\Activate.ps1

# 3. Verificar pré-requisitos
python migrations_multitenant\check_prerequisites.py

# 4. Fazer backup (OBRIGATÓRIO!)
python migrations_multitenant\backup_database.py

# 5. Testar migração (DRY RUN)
python migrations_multitenant\0001_init_city_schemas.py --dry-run

# 6. Executar migração (REAL)
python migrations_multitenant\0001_init_city_schemas.py
# Digite: CONFIRMO

# 7. Validar resultado
python migrations_multitenant\validate_migration.py
```

---

## 🐛 Troubleshooting

### Erro: "app/.env não encontrado"

**Causa:** Script executado de dentro de `migrations_multitenant/`  
**Solução:**

```powershell
cd ..  # Voltar para raiz
python migrations_multitenant\check_prerequisites.py
```

### Erro: "pg_dump não encontrado"

**Causa:** PostgreSQL client tools não instalado  
**Solução:** Siga "Instalar PostgreSQL Client Tools" acima

### Erro: "connection refused"

**Causa:** DATABASE_URL não carregado ou incorreto  
**Verificar:**

```powershell
# Ver DATABASE_URL
Select-String -Path app\.env -Pattern "DATABASE_URL"

# Testar conexão manual
python -c "import psycopg2; from dotenv import load_dotenv; import os; load_dotenv('app/.env'); psycopg2.connect(os.getenv('DATABASE_URL')); print('✅ Conexão OK')"
```

### Erro: "Permission denied"

**Causa:** Sem permissão no banco  
**Solução:** Verificar com DBA se usuário tem permissão CREATE

---

## 📝 Checklist Final

Antes de executar migração:

- [ ] Estou na **raiz** do projeto (não em migrations_multitenant/)
- [ ] `app\.env` existe e tem DATABASE_URL
- [ ] `pg_dump --version` funciona
- [ ] `check_prerequisites.py` passou todas as verificações
- [ ] Tenho backup do banco
- [ ] Testei em DEV antes de PROD

---

## 💡 Dicas Windows

### Atalho PowerShell (criar script):

Crie `migrate.ps1` na raiz:

```powershell
# migrate.ps1
$ErrorActionPreference = "Stop"

Write-Host "🔍 Verificando pré-requisitos..." -ForegroundColor Cyan
python migrations_multitenant\check_prerequisites.py

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Pré-requisitos falharam!" -ForegroundColor Red
    exit 1
}

Write-Host "`n💾 Criando backup..." -ForegroundColor Cyan
python migrations_multitenant\backup_database.py

Write-Host "`n🚀 Executando migração..." -ForegroundColor Cyan
python migrations_multitenant\0001_init_city_schemas.py

Write-Host "`n✅ Validando..." -ForegroundColor Cyan
python migrations_multitenant\validate_migration.py
```

**Usar:**

```powershell
.\migrate.ps1
```

---

**Versão:** 1.0  
**Sistema:** Windows 10/11  
**PowerShell:** 5.1+
