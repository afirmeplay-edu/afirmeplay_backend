#!/usr/bin/env python3
"""
Script para resetar cronômetros de avaliações com problemas
"""

import sys
import os
from datetime import datetime, timedelta

# Adicionar o diretório do projeto ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models.testSession import TestSession
from app.models.student import Student
from app.models.test import Test

def reset_evaluation_timers():
    """
    Reseta cronômetros de avaliações com problemas:
    1. Sessões com tempo restante = 0 mas status em_andamento
    2. Sessões onde actual_start_time é None mas started_at existe
    3. Sessões criadas recentemente mas com tempo esgotado
    """
    
    app = create_app()
    
    with app.app_context():
        print("🔍 Analisando sessões de teste...")
        
        # Buscar todas as sessões em andamento
        sessions = TestSession.query.filter_by(status='em_andamento').all()
        
        print(f"📊 Encontradas {len(sessions)} sessões em andamento")
        
        sessions_to_reset = []
        sessions_to_expire = []
        
        for session in sessions:
            print(f"\n🔍 Analisando sessão {session.id}:")
            print(f"   👤 Aluno: {session.student.name if session.student else 'N/A'}")
            print(f"   📝 Teste: {session.test.title if session.test else 'N/A'}")
            print(f"   ⏰ Tempo limite: {session.time_limit_minutes} min")
            print(f"   🕐 started_at: {session.started_at}")
            print(f"   🕐 actual_start_time: {session.actual_start_time}")
            print(f"   ⏱️  Tempo restante: {session.remaining_time_minutes} min")
            print(f"   📅 Criado em: {session.created_at}")
            
            # Verificar se a sessão tem problemas
            problems = []
            
            # Problema 1: Tempo restante é 0 ou negativo
            if session.remaining_time_minutes is not None and session.remaining_time_minutes <= 0:
                problems.append("Tempo esgotado")
            
            # Problema 2: actual_start_time é None mas started_at existe
            if session.started_at and not session.actual_start_time:
                problems.append("Cronômetro iniciado automaticamente")
            
            # Problema 3: Sessão criada há muito tempo mas ainda em andamento
            if session.created_at:
                hours_since_created = (datetime.utcnow() - session.created_at).total_seconds() / 3600
                if hours_since_created > 24:  # Mais de 24 horas
                    problems.append(f"Sessão antiga ({hours_since_created:.1f}h)")
            
            if problems:
                print(f"   ❌ Problemas encontrados: {', '.join(problems)}")
                
                # Decidir ação baseada nos problemas
                if "Tempo esgotado" in problems and "Cronômetro iniciado automaticamente" not in problems:
                    # Se o tempo realmente esgotou legitimamente, expirar
                    sessions_to_expire.append(session)
                else:
                    # Caso contrário, resetar
                    sessions_to_reset.append(session)
            else:
                print(f"   ✅ Sessão OK")
        
        print(f"\n📋 RESUMO:")
        print(f"   🔄 Sessões para resetar: {len(sessions_to_reset)}")
        print(f"   ⏰ Sessões para expirar: {len(sessions_to_expire)}")
        
        if not sessions_to_reset and not sessions_to_expire:
            print("✅ Nenhuma sessão precisa de correção!")
            return
        
        # Confirmar ação
        print(f"\n⚠️  ATENÇÃO: Esta operação irá:")
        if sessions_to_reset:
            print(f"   - Resetar {len(sessions_to_reset)} sessões (limpar started_at e actual_start_time)")
        if sessions_to_expire:
            print(f"   - Expirar {len(sessions_to_expire)} sessões (marcar como expiradas)")
        
        confirm = input("\nDeseja continuar? (s/N): ").lower().strip()
        if confirm != 's':
            print("❌ Operação cancelada.")
            return
        
        # Resetar sessões
        reset_count = 0
        for session in sessions_to_reset:
            try:
                print(f"🔄 Resetando sessão {session.id}...")
                
                # Limpar campos de tempo
                session.started_at = None
                session.actual_start_time = None
                
                # Manter status em_andamento para permitir início normal
                # session.status permanece 'em_andamento'
                
                db.session.add(session)
                reset_count += 1
                
                print(f"   ✅ Sessão {session.id} resetada")
                
            except Exception as e:
                print(f"   ❌ Erro ao resetar sessão {session.id}: {e}")
        
        # Expirar sessões
        expired_count = 0
        for session in sessions_to_expire:
            try:
                print(f"⏰ Expirando sessão {session.id}...")
                
                session.status = 'expirada'
                session.submitted_at = datetime.utcnow()
                
                db.session.add(session)
                expired_count += 1
                
                print(f"   ✅ Sessão {session.id} expirada")
                
            except Exception as e:
                print(f"   ❌ Erro ao expirar sessão {session.id}: {e}")
        
        # Salvar mudanças
        try:
            db.session.commit()
            print(f"\n✅ SUCESSO!")
            print(f"   🔄 {reset_count} sessões resetadas")
            print(f"   ⏰ {expired_count} sessões expiradas")
            print(f"\n💡 As sessões resetadas agora podem ser iniciadas normalmente pelos alunos.")
            
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ ERRO ao salvar mudanças: {e}")
            return
        
        # Mostrar estatísticas finais
        print(f"\n📊 ESTATÍSTICAS FINAIS:")
        total_sessions = TestSession.query.count()
        active_sessions = TestSession.query.filter_by(status='em_andamento').count()
        expired_sessions = TestSession.query.filter_by(status='expirada').count()
        completed_sessions = TestSession.query.filter_by(status='finalizada').count()
        
        print(f"   📈 Total de sessões: {total_sessions}")
        print(f"   🟢 Em andamento: {active_sessions}")
        print(f"   🔴 Expiradas: {expired_sessions}")
        print(f"   ✅ Finalizadas: {completed_sessions}")

def create_migration_for_new_field():
    """
    Cria uma migração para adicionar o campo actual_start_time
    """
    print("\n🔧 Criando migração para o campo actual_start_time...")
    
    try:
        import subprocess
        result = subprocess.run([
            'python', '-m', 'flask', 'db', 'migrate', 
            '-m', 'add_actual_start_time_to_test_sessions'
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Migração criada com sucesso!")
            print("💡 Execute 'python -m flask db upgrade' para aplicar a migração.")
        else:
            print(f"❌ Erro ao criar migração: {result.stderr}")
            
    except Exception as e:
        print(f"❌ Erro ao executar comando de migração: {e}")

if __name__ == "__main__":
    print("🚀 SCRIPT DE CORREÇÃO DE CRONÔMETROS DE AVALIAÇÕES")
    print("=" * 60)
    
    # Verificar se deve criar migração
    if len(sys.argv) > 1 and sys.argv[1] == "--create-migration":
        create_migration_for_new_field()
    else:
        reset_evaluation_timers()
    
    print("\n🎯 Script finalizado!") 