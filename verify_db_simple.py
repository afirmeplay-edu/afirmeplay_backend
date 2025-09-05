#!/usr/bin/env python3
"""
Script simples para verificar o status do banco de dados.
"""

import subprocess
import sys
import os

def run_command(command):
    """Executa um comando e retorna o resultado"""
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, cwd=os.path.dirname(__file__))
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return -1, "", str(e)

def main():
    """Função principal"""
    print("=" * 60)
    print("VERIFICAÇÃO SIMPLES DO BANCO DE DADOS")
    print("=" * 60)
    
    # Verificar se estamos no diretório correto
    if not os.path.exists('app'):
        print("❌ Execute este script no diretório raiz do projeto")
        return
    
    # 1. Verificar status das migrações
    print("\n1. Verificando status das migrações...")
    returncode, stdout, stderr = run_command("flask db current")
    
    if returncode == 0:
        print(f"✅ Status atual: {stdout.strip()}")
    else:
        print(f"❌ Erro ao verificar status: {stderr}")
    
    # 2. Verificar se há migrações pendentes
    print("\n2. Verificando migrações pendentes...")
    returncode, stdout, stderr = run_command("flask db heads")
    
    if returncode == 0:
        print(f"✅ Última migração: {stdout.strip()}")
    else:
        print(f"❌ Erro ao verificar última migração: {stderr}")
    
    # 3. Tentar gerar uma migração automática (sem salvar)
    print("\n3. Verificando se há diferenças no schema...")
    returncode, stdout, stderr = run_command("flask db revision --autogenerate --message 'temp_check' --dry-run")
    
    if returncode == 0:
        if "No changes in schema detected" in stdout:
            print("✅ Schema está sincronizado!")
        else:
            print("⚠️  Há diferenças no schema detectadas:")
            print(stdout)
    else:
        print(f"❌ Erro ao verificar schema: {stderr}")
    
    # 4. Mostrar histórico de migrações
    print("\n4. Histórico de migrações:")
    returncode, stdout, stderr = run_command("flask db history")
    
    if returncode == 0:
        print(stdout)
    else:
        print(f"❌ Erro ao mostrar histórico: {stderr}")
    
    print("\n" + "=" * 60)
    print("COMANDOS ÚTEIS:")
    print("=" * 60)
    print("• Ver status atual: flask db current")
    print("• Ver última migração: flask db heads")
    print("• Aplicar migrações: flask db upgrade")
    print("• Gerar nova migração: flask db revision --autogenerate -m 'descrição'")
    print("• Ver histórico: flask db history")
    print("• Reverter migração: flask db downgrade")

if __name__ == "__main__":
    main()
