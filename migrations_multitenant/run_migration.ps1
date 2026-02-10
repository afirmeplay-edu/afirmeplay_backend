# Script PowerShell para executar migração no Windows
# Execute da RAIZ do projeto!

param(
    [switch]$SkipBackup,
    [switch]$DryRun,
    [switch]$SkipValidation
)

$ErrorActionPreference = "Stop"

# Verificar se está na raiz do projeto
if (-not (Test-Path "app\.env")) {
    Write-Host "❌ ERRO: Execute este script da raiz do projeto!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Você está em: $PWD" -ForegroundColor Yellow
    Write-Host "Deveria estar em: C:\Users\Artur Calderon\Documents\Programming\innovaplay_backend" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Para corrigir:" -ForegroundColor Cyan
    Write-Host '  cd "C:\Users\Artur Calderon\Documents\Programming\innovaplay_backend"' -ForegroundColor White
    Write-Host '  .\migrations_multitenant\run_migration.ps1' -ForegroundColor White
    exit 1
}

Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "🚀 MIGRAÇÃO MULTI-TENANT - INNOVAPLAY" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host ""

# ETAPA 1: Verificar pré-requisitos
Write-Host "1️⃣  Verificando pré-requisitos..." -ForegroundColor Blue
Write-Host ""
python migrations_multitenant\check_prerequisites.py

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "❌ Pré-requisitos falharam!" -ForegroundColor Red
    Write-Host ""
    Write-Host "💡 Dicas:" -ForegroundColor Yellow
    Write-Host "   - Verifique se app\.env existe" -ForegroundColor White
    Write-Host "   - Verifique DATABASE_URL em app\.env" -ForegroundColor White
    Write-Host "   - Para instalar pg_dump: migrations_multitenant\SETUP_WINDOWS.md" -ForegroundColor White
    Write-Host ""
    exit 1
}

# ETAPA 2: Backup (opcional se pg_dump não instalado)
if (-not $SkipBackup) {
    Write-Host ""
    Write-Host "=" * 80 -ForegroundColor Cyan
    Write-Host "2️⃣  Criando backup do banco..." -ForegroundColor Blue
    Write-Host ""
    
    try {
        python migrations_multitenant\backup_database.py
        
        if ($LASTEXITCODE -ne 0) {
            Write-Host ""
            Write-Host "⚠️  Backup falhou (pg_dump não instalado?)" -ForegroundColor Yellow
            Write-Host ""
            $response = Read-Host "Continuar sem backup? (digite 'SIM' para continuar)"
            
            if ($response -ne "SIM") {
                Write-Host "❌ Migração cancelada" -ForegroundColor Red
                exit 1
            }
            
            Write-Host "⚠️  Continuando sem backup..." -ForegroundColor Yellow
        }
    } catch {
        Write-Host ""
        Write-Host "⚠️  Erro ao criar backup: $_" -ForegroundColor Yellow
        Write-Host ""
        $response = Read-Host "Continuar sem backup? (digite 'SIM' para continuar)"
        
        if ($response -ne "SIM") {
            Write-Host "❌ Migração cancelada" -ForegroundColor Red
            exit 1
        }
    }
}

# ETAPA 3: Migração
Write-Host ""
Write-Host "=" * 80 -ForegroundColor Cyan

if ($DryRun) {
    Write-Host "3️⃣  Executando DRY RUN (simulação)..." -ForegroundColor Blue
    Write-Host ""
    python migrations_multitenant\0001_init_city_schemas.py --dry-run
} else {
    Write-Host "3️⃣  Executando MIGRAÇÃO REAL..." -ForegroundColor Blue
    Write-Host ""
    Write-Host "⚠️  ATENÇÃO: Isso vai ALTERAR o banco de dados!" -ForegroundColor Yellow
    Write-Host ""
    python migrations_multitenant\0001_init_city_schemas.py
}

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "❌ Migração falhou!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Verifique o log em: migration_0001_*.log" -ForegroundColor Yellow
    exit 1
}

# ETAPA 4: Validação
if (-not $SkipValidation -and -not $DryRun) {
    Write-Host ""
    Write-Host "=" * 80 -ForegroundColor Cyan
    Write-Host "4️⃣  Validando migração..." -ForegroundColor Blue
    Write-Host ""
    python migrations_multitenant\validate_migration.py
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "⚠️  Validação encontrou problemas" -ForegroundColor Yellow
        Write-Host "Revise os erros acima" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "✅ PROCESSO CONCLUÍDO!" -ForegroundColor Green
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host ""
