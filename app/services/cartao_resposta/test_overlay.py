# -*- coding: utf-8 -*-
"""
Script de teste para validar o sistema de overlay dos cartões resposta.

USO:
    python -m app.services.cartao_resposta.test_overlay

IMPORTANTE: Execute este script APENAS em ambiente de desenvolvimento/teste!
"""

import sys
import os

# Adicionar diretório raiz ao path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

def test_overlay_generation():
    """
    Testa a geração de overlay PDF com dados fictícios.
    NÃO requer banco de dados.
    """
    print("\n" + "="*80)
    print("TESTE: Geração de Overlay PDF (sem banco de dados)")
    print("="*80 + "\n")
    
    from app.services.cartao_resposta.answer_sheet_generator import AnswerSheetGenerator
    
    # Dados fictícios de teste
    test_student = {
        'id': 'test-student-uuid-123',
        'name': 'João da Silva Santos',
        'school_name': 'Escola Municipal Teste',
        'class_name': 'A',
        'grade_name': '5º Ano'
    }
    
    test_data = {
        'id': 'test-test-uuid-456',
        'title': 'Prova de Matemática - Teste',
        'grade_name': '5º Ano',
        'municipality': 'São Paulo',
        'state': 'SP'
    }
    
    gabarito_id = 'test-gabarito-uuid-789'
    
    # Criar gerador
    generator = AnswerSheetGenerator()
    
    print("📝 Gerando overlay PDF...")
    print(f"   Aluno: {test_student['name']}")
    print(f"   Escola: {test_student['school_name']}")
    print(f"   Turma: {test_student['grade_name']} - {test_student['class_name']}")
    print(f"   Gabarito ID: {gabarito_id}")
    
    # Gerar overlay
    overlay_bytes = generator._generate_student_overlay_pdf(
        student=test_student,
        test_data=test_data,
        gabarito_id=gabarito_id
    )
    
    if overlay_bytes:
        print(f"\n✅ Overlay gerado com sucesso!")
        print(f"   Tamanho: {len(overlay_bytes)} bytes")
        
        # Salvar em arquivo de teste
        output_path = '/tmp/test_overlay_cartao_resposta.pdf'
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'wb') as f:
            f.write(overlay_bytes)
        
        print(f"   Salvo em: {output_path}")
        print(f"\n📋 Abra o arquivo para verificar:")
        print(f"   - Textos estão visíveis?")
        print(f"   - QR code foi gerado?")
        print(f"   - Coordenadas parecem corretas?")
        
        return True
    else:
        print(f"\n❌ Falha ao gerar overlay!")
        return False


def test_placeholder_qr():
    """
    Testa a geração de QR code placeholder.
    """
    print("\n" + "="*80)
    print("TESTE: Geração de QR Code Placeholder")
    print("="*80 + "\n")
    
    from app.services.cartao_resposta.answer_sheet_generator import AnswerSheetGenerator
    
    generator = AnswerSheetGenerator()
    
    print("📝 Gerando QR code placeholder...")
    qr_base64 = generator._get_placeholder_qr_base64()
    
    if qr_base64:
        print(f"✅ QR placeholder gerado com sucesso!")
        print(f"   Tamanho: {len(qr_base64)} caracteres (base64)")
        print(f"   Primeiros 50 chars: {qr_base64[:50]}...")
        return True
    else:
        print(f"❌ Falha ao gerar QR placeholder!")
        return False


def test_coordinates_documentation():
    """
    Verifica se a documentação de coordenadas existe.
    """
    print("\n" + "="*80)
    print("TESTE: Documentação de Coordenadas")
    print("="*80 + "\n")
    
    coords_file = os.path.join(
        os.path.dirname(__file__), 
        'COORDENADAS_OVERLAY.md'
    )
    
    if os.path.exists(coords_file):
        print(f"✅ Documentação encontrada: {coords_file}")
        
        with open(coords_file, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.split('\n')
            print(f"   Linhas: {len(lines)}")
            print(f"   Tamanho: {len(content)} caracteres")
        
        return True
    else:
        print(f"❌ Documentação não encontrada: {coords_file}")
        return False


def main():
    """
    Executa todos os testes.
    """
    print("\n" + "="*80)
    print("🧪 TESTES DO SISTEMA DE OVERLAY - CARTÕES RESPOSTA")
    print("="*80)
    
    results = []
    
    # Teste 1: Documentação
    results.append(("Documentação", test_coordinates_documentation()))
    
    # Teste 2: QR Placeholder
    results.append(("QR Placeholder", test_placeholder_qr()))
    
    # Teste 3: Overlay Generation
    results.append(("Overlay PDF", test_overlay_generation()))
    
    # Resumo
    print("\n" + "="*80)
    print("📊 RESUMO DOS TESTES")
    print("="*80 + "\n")
    
    passed = 0
    failed = 0
    
    for test_name, result in results:
        status = "✅ PASSOU" if result else "❌ FALHOU"
        print(f"   {test_name:20s} {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\n   Total: {passed + failed} testes")
    print(f"   Passou: {passed}")
    print(f"   Falhou: {failed}")
    
    if failed == 0:
        print(f"\n🎉 Todos os testes passaram!")
        print(f"\n📋 PRÓXIMOS PASSOS:")
        print(f"   1. Validar visualmente o overlay gerado em /tmp/test_overlay_cartao_resposta.pdf")
        print(f"   2. Testar com banco de dados real (gerar cartão completo)")
        print(f"   3. Verificar alinhamento dos textos e QR code")
        print(f"   4. Ajustar coordenadas se necessário")
        return 0
    else:
        print(f"\n⚠️  Alguns testes falharam. Verifique os erros acima.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
