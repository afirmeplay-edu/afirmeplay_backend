"""Script para verificar o estado das questões no banco de dados"""
from app import create_app, db
from app.models.question import Question
from sqlalchemy import text

app = create_app()

with app.app_context():
    print("="*80)
    print("🔍 VERIFICANDO QUESTÕES NO BANCO DE DADOS")
    print("="*80)
    
    # Total de questões
    total = Question.query.count()
    print(f"\n📊 Total de questões: {total}")
    
    if total == 0:
        print("\n⚠️ NÃO HÁ QUESTÕES NO BANCO!")
    else:
        # Contar por scope_type
        print("\n📋 Distribuição por scope_type:")
        result = db.session.execute(text("""
            SELECT scope_type, COUNT(*) as total 
            FROM public.question 
            GROUP BY scope_type
        """))
        for row in result:
            print(f"   {row.scope_type or 'NULL'}: {row.total}")
        
        # Ver questões do usuário tecadm
        user_id = '2355cc7c-df7a-4773-90b1-ecf9265d18a5'
        print(f"\n👤 Questões criadas pelo usuário {user_id}:")
        user_questions = Question.query.filter_by(created_by=user_id).all()
        print(f"   Total: {len(user_questions)}")
        for q in user_questions[:5]:
            print(f"   - ID: {q.id}, scope_type: {q.scope_type}, owner_city_id: {q.owner_city_id}")
        
        # Ver questões do município
        city_id = '9a2f95ed-9f70-4863-a5f1-1b6c6c262b0d'
        print(f"\n🏙️ Questões do município {city_id}:")
        city_questions = Question.query.filter_by(owner_city_id=city_id).all()
        print(f"   Total: {len(city_questions)}")
        for q in city_questions[:5]:
            print(f"   - ID: {q.id}, scope_type: {q.scope_type}, created_by: {q.created_by}")
        
        # Ver questões GLOBAL
        print(f"\n🌐 Questões GLOBAL:")
        global_questions = Question.query.filter_by(scope_type='GLOBAL').all()
        print(f"   Total: {len(global_questions)}")
        for q in global_questions[:5]:
            print(f"   - ID: {q.id}, owner_city_id: {q.owner_city_id}, created_by: {q.created_by}")
        
        # Primeiras 10 questões (qualquer scope)
        print(f"\n📋 Primeiras 10 questões (qualquer scope):")
        first_questions = Question.query.limit(10).all()
        for i, q in enumerate(first_questions, 1):
            print(f"   {i}. ID: {q.id}")
            print(f"      scope_type: {q.scope_type}")
            print(f"      owner_city_id: {q.owner_city_id}")
            print(f"      created_by: {q.created_by}")
    
    print("\n" + "="*80)
