#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para gerar formulário preenchido com respostas específicas
Respostas: 1A, 2B, 3A, 4A
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.services.physical_test_pdf_generator import PhysicalTestPDFGenerator
from app.models.test import Test
from app.models.question import Question
from app.models.testQuestion import TestQuestion
from app.models.student import Student
from app import db

def gerar_formulario_preenchido():
    """Gera formulário preenchido com respostas específicas"""
    
    app = create_app()
    
    with app.app_context():
        try:
            # Buscar a prova existente
            test_id = "eafb4493-e47a-43e2-98ea-70f75bf6b103"
            test = Test.query.get(test_id)
            
            if not test:
                print(f"❌ Prova {test_id} não encontrada")
                return
            
            print(f"✅ Prova encontrada: {test.title}")
            
            # Buscar questões da prova
            test_question_ids = [tq.question_id for tq in TestQuestion.query.filter_by(test_id=test_id).order_by(TestQuestion.order).all()]
            questions = Question.query.filter(Question.id.in_(test_question_ids)).all()
            
            print(f"📋 Questões encontradas: {len(questions)}")
            
            # Usar aluno existente ou criar um simples
            student_id = "teste_formulario_preenchido"
            student = Student.query.get(student_id)
            if not student:
                # Buscar uma escola existente
                from app.models.school import School
                existing_school = School.query.first()
                if existing_school:
                    student = Student(
                        id=student_id,
                        name="Aluno Teste",
                        school_id=existing_school.id
                    )
                    db.session.add(student)
                    db.session.commit()
                    print(f"✅ Aluno de teste criado: {student.name}")
                else:
                    print(f"❌ Nenhuma escola encontrada no banco")
                    return
            
            # Respostas específicas: 1A, 2B, 3A, 4A
            respostas_especificas = {
                1: 'A',
                2: 'B', 
                3: 'A',
                4: 'A'
            }
            
            print(f"🎯 Respostas a serem preenchidas: {respostas_especificas}")
            
            # Gerar formulário preenchido
            pdf_generator = PhysicalTestPDFGenerator()
            
            # Gerar formulário individual preenchido
            result = pdf_generator.gerar_formulario_individual_preenchido(
                test_id=test_id,
                student_id=student_id,
                respostas_especificas=respostas_especificas,
                output_dir="formularios_preenchidos"
            )
            
            if result and result.get('success'):
                print(f"✅ Formulário preenchido gerado com sucesso!")
                print(f"📁 Arquivo: {result.get('file_path')}")
                print(f"🎯 Respostas preenchidas: {respostas_especificas}")
            else:
                print(f"❌ Erro ao gerar formulário: {result.get('error', 'Erro desconhecido')}")
                
        except Exception as e:
            print(f"❌ Erro: {str(e)}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    gerar_formulario_preenchido()
