#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from app import create_app, db
from app.models.user import User
from app.models.city import City
from app.models.school import School
from app.models.schoolTeacher import SchoolTeacher

app = create_app()
app.app_context().push()

print("=== VERIFICAÇÃO DE PERMISSÕES DO USUÁRIO ===")

# Importar a função corrigida da rota
from app.routes.evaluation_results_routes import verificar_permissao_filtros

# 1. Verificar todos os usuários no sistema
print("\n1. Verificando todos os usuários no sistema...")
users = User.query.all()
print(f"   Total de usuários: {len(users)}")

for user in users:
    print(f"\n   Usuário: {user.name} (ID: {user.id})")
    print(f"     - Email: {user.email}")
    print(f"     - Role: {user.role}")
    print(f"     - City ID: {getattr(user, 'city_id', 'N/A')}")
    
    # Verificar permissões usando a função corrigida da rota
    user_dict = {
        'role': str(user.role),  # Usar o role completo como está na rota
        'city_id': getattr(user, 'city_id', None),
        'id': user.id
    }
    
    permissao = verificar_permissao_filtros(user_dict)
    print(f"     - Permissão: {permissao['permitted']}")
    if not permissao['permitted']:
        print(f"     - Erro: {permissao['error']}")
    else:
        print(f"     - Scope: {permissao['scope']}")

# 2. Verificar usuários específicos por papel
print(f"\n2. Verificando usuários por papel...")
roles = ['ADMIN', 'TECADM', 'DIRETOR', 'COORDENADOR', 'PROFESSOR']
for role in roles:
    users_with_role = User.query.filter_by(role=role).all()
    print(f"   {role.title()}s: {len(users_with_role)}")
    
    for user in users_with_role:
        print(f"     - {user.name}: city_id={getattr(user, 'city_id', 'N/A')}")

# 3. Verificar vínculos de professores com escolas
print(f"\n3. Verificando vínculos de professores com escolas...")
teacher_schools = SchoolTeacher.query.all()
print(f"   Total de vínculos professor-escola: {len(teacher_schools)}")

for ts in teacher_schools:
    teacher = User.query.get(ts.teacher_id)
    school = School.query.get(ts.school_id)
    print(f"     - Professor: {teacher.name if teacher else 'N/A'} -> Escola: {school.name if school else 'N/A'}")

# 4. Verificar municípios e escolas
print(f"\n4. Verificando municípios e escolas...")
cities = City.query.all()
print(f"   Total de municípios: {len(cities)}")

for city in cities:
    schools = School.query.filter_by(city_id=city.id).all()
    print(f"     - {city.name} ({city.state}): {len(schools)} escolas")
    for school in schools:
        print(f"       * {school.name} (ID: {school.id})")

print("\n=== FIM DA VERIFICAÇÃO ===")
