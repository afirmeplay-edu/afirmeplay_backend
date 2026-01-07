#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para gerar formulários no formato do sistema antigo
Usa os dados do banco atual (SQLAlchemy) mas gera no formato antigo
"""

import os
import sys
import cv2
import numpy as np
try:
    from fpdf import FPDF
except ImportError:
    from fpdf2 import FPDF
from PIL import ImageFont, ImageDraw, Image
import matplotlib.font_manager as fm
from datetime import datetime
import hashlib

# Adicionar o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Importar Flask app e modelos
from app import create_app, db
from app.models.test import Test
from app.models.student import Student
from app.models.testQuestion import TestQuestion
from app.models.question import Question
from app.models.classTest import ClassTest
from app.models.studentClass import Class
from app.models.user import User

# Importar funções do sistema antigo
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app', 'test_correction'))
from libQr import formataQr, escreveQr
from util import desenhaCabecalho


def uuid_to_numeric(uuid_str: str, max_digits: int = 15) -> str:
    """Converte UUID para número usando hash (para compatibilidade com sistema antigo)"""
    hash_obj = hashlib.md5(uuid_str.encode())
    hash_hex = hash_obj.hexdigest()
    hash_int = int(hash_hex[:max_digits], 16)
    return str(hash_int % (10 ** max_digits)).zfill(max_digits)


def get_test_data_from_db(test_id: str):
    """
    Busca dados da prova do banco atual (SQLAlchemy)
    Retorna no formato esperado pelo sistema antigo
    """
    app = create_app()
    with app.app_context():
        # Buscar prova
        test = Test.query.get(test_id)
        if not test:
            raise ValueError(f"Prova {test_id} não encontrada")
        
        # Buscar questões ordenadas
        test_questions = TestQuestion.query.filter_by(test_id=test_id).order_by(TestQuestion.order).all()
        questions = []
        for tq in test_questions:
            question = db.session.get(Question, tq.question_id)
            if question:
                questions.append(question)
        
        if not questions:
            raise ValueError(f"Nenhuma questão encontrada para a prova {test_id}")
        
        # Contar alternativas (assumindo que todas têm 4 alternativas A, B, C, D)
        num_alternatives = 4
        
        # Buscar professor (criador da prova)
        professor_name = "Não informado"
        if test.created_by:
            try:
                professor = db.session.get(User, test.created_by)
                if professor:
                    professor_name = professor.name
            except Exception:
                pass
        
        # Buscar turmas que aplicaram a prova
        class_tests = ClassTest.query.filter_by(test_id=test_id).all()
        if not class_tests:
            raise ValueError(f"A prova {test_id} não foi aplicada em nenhuma turma")
        
        # Buscar alunos das turmas
        class_ids = [ct.class_id for ct in class_tests]
        students = Student.query.filter(Student.class_id.in_(class_ids)).all()
        
        if not students:
            raise ValueError(f"Nenhum aluno encontrado nas turmas que aplicaram a prova")
        
        # Buscar nome da turma (usar primeira turma)
        if class_ids:
            first_class = db.session.get(Class, class_ids[0])
            class_name = first_class.name if first_class else "Não informado"
        else:
            class_name = "Não informado"
        
        # Calcular nota total (soma dos valores das questões)
        total_score = sum(q.value if q.value else 1.0 for q in questions)
        
        # Data de hoje
        data = datetime.now().strftime("%Y-%m-%d")
        
        # Preparar dados no formato antigo
        nome_prova = test.title or "Prova"
        nome_professor = professor_name
        nome_turma = class_name
        qtd_quadrado_v = len(questions)  # Número de questões
        qtd_quadrado_h = num_alternatives  # Número de alternativas (A, B, C, D)
        nota_prova = total_score
        nome_alunos = [s.name for s in students]
        
        # Converter IDs de alunos para formato numérico (para QR code)
        id_alunos_numeric = []
        for student in students:
            numeric_id = uuid_to_numeric(student.id, max_digits=15)
            id_alunos_numeric.append(numeric_id)
        
        # ID da prova em formato numérico
        id_prova_numeric = uuid_to_numeric(test_id, max_digits=15)
        
        return {
            'nome_prova': nome_prova,
            'nome_professor': nome_professor,
            'nome_turma': nome_turma,
            'data': data,
            'qtd_quadrado_v': qtd_quadrado_v,
            'qtd_quadrado_h': qtd_quadrado_h,
            'nota_prova': nota_prova,
            'nome_alunos': nome_alunos,
            'id_alunos_numeric': id_alunos_numeric,
            'id_prova_numeric': id_prova_numeric,
            'id_usuario': test.created_by or "0"
        }


def gerar_prova_formato_antigo(test_id: str, output_dir: str = 'formularios_antigo'):
    """
    Gera formulários no formato do sistema antigo
    """
    # Criar diretório de saída
    if not os.path.isdir(output_dir):
        os.makedirs(output_dir)
    
    # Buscar dados do banco
    print(f"📋 Buscando dados da prova {test_id}...")
    dados = get_test_data_from_db(test_id)
    
    nome_prova = dados['nome_prova']
    prof = dados['nome_professor']
    turma = dados['nome_turma']
    data = dados['data']
    qtd_quadrado_v = dados['qtd_quadrado_v']
    qtd_quadrado_h = dados['qtd_quadrado_h']
    nota_prova = dados['nota_prova']
    aluno = dados['nome_alunos']
    id_aluno_numeric = dados['id_alunos_numeric']
    id_prova_numeric = dados['id_prova_numeric']
    id_usuario = dados['id_usuario']
    
    print(f"✅ Dados encontrados:")
    print(f"   Prova: {nome_prova}")
    print(f"   Professor: {prof}")
    print(f"   Turma: {turma}")
    print(f"   Questões: {qtd_quadrado_v}")
    print(f"   Alternativas: {qtd_quadrado_h}")
    print(f"   Alunos: {len(aluno)}")
    
    # Criar PDF
    pdf = FPDF(format=(int(1240/2.7), int(1754/2.7)))
    
    for m in range(len(aluno)):
        print(f"📄 Gerando formulário para {aluno[m]}...")
        
        # Criar imagem 1754x1240
        img = np.ones((1754, 1240, 3), np.uint8) * 255
        
        altura = img.shape[0]
        largura = img.shape[1]
        
        fonte = cv2.FONT_HERSHEY_SIMPLEX
        escala = 0.7
        espessura = 2
        
        # Desenha linhas
        img = cv2.line(img, (160, 270), (largura-160, 270), (0, 0, 0), 1)
        img = cv2.line(img, (80, 560), (largura-80, 560), (0, 0, 0), 2)
        
        # Desenha retângulos das notas
        cv2.rectangle(img, (330, 320), (580, 470), (0, 0, 0), 2)
        cv2.rectangle(img, (largura-330, 320), (largura-580, 470), (0, 0, 0), 2)
        
        # Desenha cabeçalho
        img = desenhaCabecalho(img, largura, altura, aluno[m], prof, nome_prova, turma, data, nota_prova)
        
        # Gera QR code no formato antigo
        try:
            msg = formataQr(f'{id_prova_numeric}.{id_aluno_numeric[m]}')
            qr_code = escreveQr(msg)
            
            # Coloca QR code no canto superior direito
            if qr_code is not None and hasattr(qr_code, 'shape'):
                qr_h, qr_w = qr_code.shape[:2]
                img[0:qr_h, largura-qr_w:largura] = qr_code
            else:
                print(f"   ⚠️ Aviso: QR code não foi gerado para {aluno[m]}")
        except Exception as e:
            print(f"   ⚠️ Aviso: Erro ao gerar QR code para {aluno[m]}: {str(e)}")
            # Continuar sem QR code se houver erro
        
        # Apaga arquivo temporário do QR code
        if os.path.exists('qr.png'):
            try:
                os.unlink('qr.png')
            except:
                pass
        
        # Cria triângulos de orientação
        t1 = np.array([[40, 640], [70, 640], [40, 610]], np.int32)
        t2 = np.array([[largura-70, 640], [largura-40, 640], [largura-70, 610]], np.int32)
        t3 = np.array([[40, altura-60], [70, altura-60], [40, altura-90]], np.int32)
        t4 = np.array([[largura-70, altura-60], [largura-40, altura-60], [largura-70, altura-90]], np.int32)
        t = [t1, t2, t3, t4]
        for i in range(len(t)):
            cv2.fillPoly(img, [t[i]], (0, 0, 0))
        
        # Coloca marcadores quadrados na vertical (questões)
        espaco = int(0)
        cinza = (210, 210, 210)
        for i in range(qtd_quadrado_v):
            cv2.rectangle(img, (120, 700 + espaco), (140, 720 + espaco), (0, 0, 0), -1)
            cv2.putText(img, f'{i+1}', (150, 720 + espaco), fonte, escala, cinza, espessura)
            espaco += 45
        
        # Coloca marcadores quadrados na horizontal (alternativas)
        espaco = 0
        for i in range(qtd_quadrado_h):
            cv2.rectangle(img, (260 + espaco, 650), (280 + espaco, 670), (0, 0, 0), -1)
            espaco += 120
        
        # Coloca círculos e letras
        letras = ['A', 'B', 'C', 'D', 'E', 'F', 'G']
        espaco_x = espaco_y = 0
        for i in range(qtd_quadrado_v):
            for j in range(qtd_quadrado_h):
                cv2.circle(img, (270 + espaco_x, 710 + espaco_y), 14, cinza, 2)
                cv2.putText(img, f'{letras[j]}', (263 + espaco_x, 717 + espaco_y), fonte, escala, cinza, espessura)
                espaco_x += 120
            espaco_x = 0
            espaco_y += 45
        
        # Salvar imagem temporária
        img_path = f'{output_dir}/prova{m}.png'
        cv2.imwrite(img_path, img)
        
        # Adicionar ao PDF
        pdf.add_page()
        pdf.set_auto_page_break(0)
        pdf.image(img_path)
        
        # Apagar imagem temporária
        os.unlink(img_path)
    
    # Salvar PDF
    pdf_path = f'{output_dir}/prova_{id_usuario}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
    pdf.output(pdf_path)
    
    abs_path = os.path.abspath(pdf_path)
    print(f"\n✅ Formulários gerados com sucesso!")
    print(f"📁 Arquivo salvo em: {abs_path}")
    
    return abs_path.replace("\\", "/")


if __name__ == "__main__":
    # ID da prova
    test_id = "6968d6e7-3a37-43f7-a418-6455a833a61b"
    
    # Diretório de saída
    output_dir = "formularios_antigo"
    
    try:
        path = gerar_prova_formato_antigo(test_id, output_dir)
        print(f"\n🎉 Sucesso! PDF gerado: {path}")
    except Exception as e:
        print(f"\n❌ Erro ao gerar formulários: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

