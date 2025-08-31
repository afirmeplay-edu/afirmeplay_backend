#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from app import create_app, db
from app.models.city import City
from app.models.school import School
from app.models.classTest import ClassTest
from app.models.studentClass import Class
from app.models.test import Test
from app.models.evaluationResult import EvaluationResult
from app.models.student import Student
from app.models.grades import Grade
from app.models.schoolTeacher import SchoolTeacher

app = create_app()
app.app_context().push()

# Simular usuário (você precisa ajustar isso baseado no usuário real que está fazendo a requisição)
# Vou simular diferentes tipos de usuário para identificar o problema

def test_user_permissions(user_role, user_city_id=None, user_school_id=None, user_id=None):
    print(f"\n=== TESTANDO USUÁRIO: {user_role.upper()} ===")
    
    # Parâmetros da requisição
    estado = "Rondônia"
    municipio = "9a2f95ed-9f70-4863-a5f1-1b6c6c262b0d"
    avaliacao = "31ad4ada-6f68-406e-95ff-0ee1bbf26d8a"
    escola = "all"
    serie = "all"
    turma = "all"
    
    print(f"Parâmetros: estado={estado}, municipio={municipio}, avaliacao={avaliacao}")
    
    # Simular usuário
    user = {
        'role': user_role,
        'city_id': user_city_id,
        'school_id': user_school_id,
        'id': user_id
    }
    
    print(f"Usuário simulado: {user}")
    
    # 1. Verificar município
    city = City.query.get(municipio)
    if not city:
        print("❌ Município não encontrado")
        return
    
    print(f"✅ Município: {city.name} ({city.id})")
    
    # 2. Verificar avaliação
    test = Test.query.get(avaliacao)
    if not test:
        print("❌ Avaliação não encontrada")
        return
    
    print(f"✅ Avaliação: {test.title} ({test.id})")
    
    # 3. Verificar onde a avaliação foi aplicada
    class_tests = ClassTest.query.filter_by(test_id=avaliacao).all()
    if not class_tests:
        print("❌ Avaliação não foi aplicada em nenhuma turma")
        return
    
    print(f"✅ Avaliação aplicada em {len(class_tests)} turma(s)")
    class_ids = [ct.class_id for ct in class_tests]
    
    # 4. Verificar turmas e escolas
    classes = Class.query.filter(Class.id.in_(class_ids)).all()
    escolas_avaliacao = []
    for classe in classes:
        school = School.query.get(classe.school_id)
        if school:
            escolas_avaliacao.append(school)
            print(f"  - Turma: {classe.name or 'N/A'} -> Escola: {school.name} -> Município: {school.city.name if school.city else 'N/A'}")
    
    # 5. Verificar se as escolas pertencem ao município
    escolas_filtradas = []
    for escola_obj in escolas_avaliacao:
        if escola_obj.city_id == municipio:
            escolas_filtradas.append(escola_obj)
            print(f"  ✅ Escola {escola_obj.name} pertence ao município {city.name}")
        else:
            print(f"  ❌ Escola {escola_obj.name} NÃO pertence ao município {city.name}")
    
    print(f"\n📊 Resumo:")
    print(f"  - Total de escolas onde avaliação foi aplicada: {len(escolas_avaliacao)}")
    print(f"  - Escolas no município correto: {len(escolas_filtradas)}")
    
    # 6. Simular lógica de permissões
    print(f"\n🔐 Simulando permissões...")
    
    if user_role == 'admin':
        print("  - Admin vê todas as escolas")
        escola_ids = [escola.id for escola in escolas_filtradas]
    elif user_role == 'tecadm':
        print(f"  - Tecadm vê apenas escolas do seu município (city_id: {user_city_id})")
        if user_city_id == municipio:
            escola_ids = [escola.id for escola in escolas_filtradas if escola.city_id == user_city_id]
            print(f"    ✅ Usuário tem acesso ao município")
        else:
            escola_ids = []
            print(f"    ❌ Usuário NÃO tem acesso ao município")
    elif user_role == 'diretor':
        print(f"  - Diretor vê apenas sua escola (school_id: {user_school_id})")
        escola_ids = [escola.id for escola in escolas_filtradas if escola.id == user_school_id]
    elif user_role == 'coordenador':
        print(f"  - Coordenador vê apenas sua escola (school_id: {user_school_id})")
        escola_ids = [escola.id for escola in escolas_filtradas if escola.id == user_school_id]
    elif user_role == 'professor':
        print(f"  - Professor vê escolas onde está vinculado (user_id: {user_id})")
        if user_id:
            teacher_schools = SchoolTeacher.query.filter_by(teacher_id=user_id).all()
            school_ids = [ts.school_id for ts in teacher_schools]
            print(f"    - Escolas vinculadas: {school_ids}")
            escola_ids = [escola.id for escola in escolas_filtradas if escola.id in school_ids]
        else:
            escola_ids = []
    else:
        print(f"  - Papel desconhecido: {user_role}")
        escola_ids = []
    
    print(f"  - Escolas permitidas para o usuário: {len(escola_ids)}")
    if escola_ids:
        for escola_id in escola_ids:
            escola_obj = School.query.get(escola_id)
            print(f"    - {escola_obj.name if escola_obj else 'N/A'} ({escola_id})")
    
    # 7. Verificar se a query retornaria dados
    if escola_ids:
        print(f"\n🔍 Testando query com escolas permitidas...")
        try:
            query_base = ClassTest.query.join(Test, ClassTest.test_id == Test.id)\
                                       .join(Class, ClassTest.class_id == Class.id)\
                                       .join(Grade, Class.grade_id == Grade.id)\
                                       .join(School, Class.school_id == School.id)\
                                       .join(City, School.city_id == City.id)\
                                       .filter(City.id == municipio)\
                                       .filter(Test.id == avaliacao)\
                                       .filter(School.id.in_(escola_ids))
            
            todas_avaliacoes_escopo = query_base.all()
            print(f"  ✅ Query executada: {len(todas_avaliacoes_escopo)} avaliações encontradas")
            
            if todas_avaliacoes_escopo:
                for ct in todas_avaliacoes_escopo:
                    print(f"    - ClassTest ID: {ct.id}, Class: {ct.class_id}, Test: {ct.test_id}")
        except Exception as e:
            print(f"  ❌ Erro na query: {str(e)}")
    else:
        print(f"\n❌ Usuário não tem acesso a nenhuma escola - query não executada")
    
    return escola_ids

# Testar diferentes tipos de usuário
print("=== INVESTIGAÇÃO DE PERMISSÕES ===")

# 1. Admin (deve ver tudo)
test_user_permissions('admin')

# 2. Tecadm do município correto
test_user_permissions('tecadm', user_city_id='9a2f95ed-9f70-4863-a5f1-1b6c6c262b0d')

# 3. Tecadm de município diferente
test_user_permissions('tecadm', user_city_id='outro-municipio-id')

# 4. Diretor da escola onde a avaliação foi aplicada
test_user_permissions('diretor', user_school_id='56bfd6b8-8465-4331-a13b-06cb06a8516d')

# 5. Professor (precisa estar vinculado à escola)
# Primeiro, vamos ver se há algum professor vinculado à escola
print(f"\n=== VERIFICANDO PROFESSORES VINCULADOS ===")
school_id = '56bfd6b8-8465-4331-a13b-06cb06a8516d'
teacher_schools = SchoolTeacher.query.filter_by(school_id=school_id).all()
print(f"Professores vinculados à escola {school_id}: {len(teacher_schools)}")
for ts in teacher_schools:
    print(f"  - Teacher ID: {ts.teacher_id}")

if teacher_schools:
    # Testar com o primeiro professor encontrado
    first_teacher = teacher_schools[0]
    test_user_permissions('professor', user_id=first_teacher.teacher_id)
else:
    print("  - Nenhum professor vinculado à escola")

print("\n=== FIM DA INVESTIGAÇÃO ===")
