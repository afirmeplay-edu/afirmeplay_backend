from app import db
from app.models import (
    City, School, SchoolTeacher, Teacher, Student, Subject, 
    Class, ClassSubject, ClassTest, Test, EducationStage, 
    Grade, Skill, Question, StudentAnswer, UserQuickLinks, 
    TeacherClass, User, TestSession, Game
)

def check_and_init_database():
    """
    Verifica se o banco precisa ser inicializado e cria as tabelas se necessário.
    Esta função é chamada antes de iniciar o servidor.
    """
    try:
        print("🔍 Verificando estado do banco de dados...")
        # Verificar se já existe alguma tabela
        inspector = db.inspect(db.engine)
        existing_tables = inspector.get_table_names()
        
        if not existing_tables:
            print("📊 Banco vazio detectado, criando tabelas...")
            db.create_all()
            print("✅ Tabelas criadas com sucesso!")
        else:
            print(f"📊 Banco já possui {len(existing_tables)} tabelas:")
            for table in existing_tables:
                print(f"   - {table}")
            print("✅ Banco de dados está pronto!")
            
    except Exception as e:
        print(f"❌ Erro ao verificar/inicializar banco de dados: {str(e)}")
        print("💡 Verifique se:")
        print("   - O banco de dados está acessível")
        print("   - As credenciais estão corretas")
        print("   - O banco existe")
        raise e

def reset_database():
    """
    Função para resetar completamente o banco (CUIDADO: apaga todos os dados!)
    """
    try:
        print("⚠️  ATENÇÃO: Resetando banco de dados...")
        print("   Todos os dados serão perdidos!")
        
        # Drop todas as tabelas
        db.drop_all()
        print("🗑️  Tabelas removidas")
        
        # Recriar tabelas
        db.create_all()
        print("✅ Tabelas recriadas com sucesso!")
        
    except Exception as e:
        print(f"❌ Erro ao resetar banco: {str(e)}")
        raise e

if __name__ == "__main__":
    # Se executar diretamente, importar app
    from app import create_app
    
    app = create_app()
    with app.app_context():
        check_and_init_database()
