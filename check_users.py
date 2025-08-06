from app import create_app, db
from app.models.user import User, RoleEnum

app = create_app()

with app.app_context():
    print("🔍 Verificando usuários no banco de dados...")
    
    # Buscar todos os usuários
    users = User.query.all()
    
    if not users:
        print("❌ Nenhum usuário encontrado no banco de dados")
    else:
        print(f"✅ Encontrados {len(users)} usuários:")
        
        for user in users:
            print(f"  - ID: {user.id}")
            print(f"    Nome: {user.name}")
            print(f"    Email: {user.email}")
            print(f"    Matrícula: {user.registration}")
            print(f"    Role: {user.role.value if user.role else 'N/A'}")
            print(f"    City ID: {user.city_id}")
            print("    ---")
    
    # Buscar especificamente usuários admin
    admin_users = User.query.filter_by(role=RoleEnum('admin')).all()
    
    if admin_users:
        print(f"\n👑 Usuários admin encontrados: {len(admin_users)}")
        for admin in admin_users:
            print(f"  - {admin.name} ({admin.email}) - Matrícula: {admin.registration}")
    else:
        print("\n❌ Nenhum usuário admin encontrado") 