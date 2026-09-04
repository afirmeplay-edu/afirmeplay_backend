# -*- coding: utf-8 -*-
"""
Script de teste simples para validar coordenadas do overlay.
Não requer banco de dados nem Flask.
"""

import io
import json
import base64
import qrcode
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.lib.colors import HexColor


def test_overlay_coordinates():
    """
    Gera um PDF de teste com as coordenadas do overlay.
    """
    print("\n" + "="*80)
    print("TESTE: Coordenadas do Overlay - Cartão Resposta")
    print("="*80 + "\n")
    
    # Coordenadas (mesmas do código)
    X_TEXT = 135.44
    Y_PDF_NAME = 775.62
    Y_PDF_SCHOOL = 731.37
    Y_PDF_TURMA = 716.62
    QR_X = 434.39
    QR_Y = 672.17
    QR_SIZE = 90
    
    # Dados de teste
    student_name = "JOÃO DA SILVA SANTOS"
    school_name = "ESCOLA MUNICIPAL TESTE"
    turma_display = "5º ANO - A"
    
    print("📐 Coordenadas:")
    print(f"   X_TEXT: {X_TEXT}")
    print(f"   Y_PDF_NAME: {Y_PDF_NAME}")
    print(f"   Y_PDF_SCHOOL: {Y_PDF_SCHOOL}")
    print(f"   Y_PDF_TURMA: {Y_PDF_TURMA}")
    print(f"   QR_X: {QR_X}, QR_Y: {QR_Y}, QR_SIZE: {QR_SIZE}")
    
    print("\n📝 Dados de teste:")
    print(f"   Nome: {student_name}")
    print(f"   Escola: {school_name}")
    print(f"   Turma: {turma_display}")
    
    # Criar PDF
    buffer = io.BytesIO()
    c = Canvas(buffer, pagesize=A4)
    c.setPageSize(A4)
    
    # Desenhar textos
    c.setFont('Helvetica', 7)
    c.setFillColor(HexColor('#374151'))
    c.drawString(X_TEXT, Y_PDF_NAME, student_name)
    c.drawString(X_TEXT, Y_PDF_SCHOOL, school_name)
    c.drawString(X_TEXT, Y_PDF_TURMA, turma_display)
    
    # Gerar QR code
    qr_metadata = {
        "student_id": "test-123",
        "gabarito_id": "gabarito-456"
    }
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=1,
    )
    qr.add_data(json.dumps(qr_metadata))
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    
    qr_buffer = io.BytesIO()
    qr_img.save(qr_buffer, format="PNG")
    qr_buffer.seek(0)
    qr_image_reader = ImageReader(qr_buffer)
    
    # Desenhar QR code
    c.drawImage(qr_image_reader, QR_X, QR_Y, width=QR_SIZE, height=QR_SIZE)
    
    # Adicionar linhas de referência (para validação visual)
    c.setStrokeColorRGB(1, 0, 0)  # Vermelho
    c.setLineWidth(0.5)
    
    # Linha horizontal no Y do nome
    c.line(0, Y_PDF_NAME, 595, Y_PDF_NAME)
    
    # Linha vertical no X do texto
    c.line(X_TEXT, 0, X_TEXT, 842)
    
    # Retângulo ao redor do QR
    c.rect(QR_X, QR_Y, QR_SIZE, QR_SIZE)
    
    c.save()
    buffer.seek(0)
    
    # Salvar arquivo
    output_path = 'C:/Users/Artur Calderon/Documents/Programming/innovaplay_backend/test_overlay_coordenadas.pdf'
    
    with open(output_path, 'wb') as f:
        f.write(buffer.read())
    
    print(f"\n✅ PDF de teste gerado!")
    print(f"   Arquivo: {output_path}")
    print(f"\n📋 Validação visual:")
    print(f"   1. Abra o PDF gerado")
    print(f"   2. Verifique se os textos estão nas posições corretas")
    print(f"   3. Verifique se o QR code está no canto superior direito")
    print(f"   4. As linhas vermelhas são referências (remover em produção)")
    
    return True


if __name__ == '__main__':
    try:
        test_overlay_coordinates()
        print("\n🎉 Teste concluído com sucesso!")
    except Exception as e:
        print(f"\n❌ Erro no teste: {str(e)}")
        import traceback
        traceback.print_exc()
