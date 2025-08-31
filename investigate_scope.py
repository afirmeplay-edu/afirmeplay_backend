#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from app import create_app, db
from app.models.city import City
from app.models.school import School
from app.models.classTest import ClassTest
from app.models.studentClass import Class

app = create_app()
app.app_context().push()

municipio_id = '9a2f95ed-9f70-4863-a5f1-1b6c6c262b0d'
avaliacao_id = '31ad4ada-6f68-406e-95ff-0ee1bbf26d8a'

print("=== INVESTIGAÇÃO DO ESCOPO ===")

# 1. Verificar município
city = City.query.get(municipio_id)
print(f"Município: {city.name if city else 'N/A'}")
if city:
    print(f"  - ID: {city.id}")
    print(f"  - Estado: {city.state}")

# 2. Verificar ClassTests para a avaliação
class_tests = ClassTest.query.filter_by(test_id=avaliacao_id).all()
print(f"\nClassTests para avaliação: {len(class_tests)}")

if class_tests:
    class_ids = [ct.class_id for ct in class_tests]
    print(f"  - Class IDs: {class_ids}")
    
    # 3. Verificar classes
    classes = Class.query.filter(Class.id.in_(class_ids)).all()
    print(f"\nClasses encontradas: {len(classes)}")
    
    for classe in classes:
        school = School.query.get(classe.school_id)
        print(f"  - Class: {classe.name or 'N/A'}")
        print(f"    School ID: {classe.school_id}")
        print(f"    School: {school.name if school else 'N/A'}")
        if school and school.city:
            print(f"    City: {school.city.name}")
            print(f"    City ID: {school.city.id}")
            print(f"    Pertence ao município buscado: {school.city.id == municipio_id}")
        print()

# 4. Verificar escolas do município
schools_in_city = School.query.filter_by(city_id=municipio_id).all()
print(f"Escolas no município {city.name if city else 'N/A'}: {len(schools_in_city)}")
for school in schools_in_city:
    print(f"  - {school.name} (ID: {school.id})")

print("\n=== FIM DA INVESTIGAÇÃO ===")
