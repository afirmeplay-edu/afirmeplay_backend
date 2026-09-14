from app import db
from app.models import (
    City, School, SchoolTeacher, Teacher, Student, Subject,
    Class, ClassSubject, ClassTest, Test, EducationStage,
    Grade, Skill, Question, StudentAnswer, UserQuickLinks,
    TeacherClass, User, TestSession, Game
)


def _safe_print(msg: str) -> None:
    """Evita UnicodeEncodeError no console Windows (cp1252)."""
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "replace").decode("ascii"))


def check_and_init_database():
    """
    Verifica se o banco precisa ser inicializado e cria as tabelas se necessário.
    Esta função é chamada antes de iniciar o servidor.
    """
    try:
        _safe_print("Verificando estado do banco de dados...")
        inspector = db.inspect(db.engine)
        existing_tables = inspector.get_table_names()

        if not existing_tables:
            _safe_print("Banco vazio detectado, criando tabelas...")
            db.create_all()
            _safe_print("Tabelas criadas com sucesso!")
        else:
            _safe_print(f"Banco ja possui {len(existing_tables)} tabelas:")
            for table in existing_tables:
                _safe_print(f"   - {table}")
            _safe_print("Banco de dados esta pronto!")

    except Exception as e:
        _safe_print(f"Erro ao verificar/inicializar banco de dados: {str(e)}")
        _safe_print("Verifique se:")
        _safe_print("   - O banco de dados esta acessivel")
        _safe_print("   - As credenciais estao corretas")
        _safe_print("   - O banco existe")
        raise e


def reset_database():
    """
    Função para resetar completamente o banco (CUIDADO: apaga todos os dados!)
    """
    try:
        _safe_print("ATENCAO: Resetando banco de dados...")
        _safe_print("   Todos os dados serao perdidos!")

        db.drop_all()
        _safe_print("Tabelas removidas")

        db.create_all()
        _safe_print("Tabelas recriadas com sucesso!")

    except Exception as e:
        _safe_print(f"Erro ao resetar banco: {str(e)}")
        raise e


if __name__ == "__main__":
    from app import create_app

    app = create_app()
    with app.app_context():
        check_and_init_database()
