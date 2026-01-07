import cv2
import numpy as np
import pyzbar.pyzbar as pyzbar
try:
    import pyqrcode
except ImportError:
    pyqrcode = None  # pyqrcode só é necessário para escreveQr, não para leQr
try:
    import qrcode
    from PIL import Image
except ImportError:
    qrcode = None
import os

def leQr(img) -> dict:
    """
    Dada uma imagem, a função retorna:
        *A informação contida no QRcode

    @parâmetro img Arquivo de imagem no qual está inserido o QRcode

    """
    print(f"🔍 [DEBUG leQr] Iniciando leQr...")
    print(f"🔍 [DEBUG leQr] Dimensões da imagem: {img.shape if img is not None else 'None'}")

    im_gray = cv2.split(cv2.cvtColor(img, cv2.COLOR_BGR2HSV))[2]
    _, im_bw = cv2.threshold(im_gray, 0, 255, cv2.THRESH_OTSU | cv2.THRESH_BINARY)
    print(f"🔍 [DEBUG leQr] Imagem processada: grayscale e threshold aplicados")

    final = {}

    try:
        qr_info = pyzbar.decode(im_bw)
        print(f"🔍 [DEBUG leQr] pyzbar.decode encontrou {len(qr_info)} QR code(s)")

        text = None
        for obj in qr_info:
            text = obj.data
            print(f"🔍 [DEBUG leQr] QR code encontrado: tipo={type(text)}, dados brutos={text}")
            break  # Pegar apenas o primeiro QR code encontrado

        # Verificar se encontrou algum QR code
        if text is None:
            print("⚠️ [DEBUG leQr] Nenhum QR code encontrado por pyzbar")
            return final

        # Texto com formatação
        new_text = text.decode('utf-8')
        print(f"🔍 [DEBUG leQr] Texto decodificado: '{new_text}' (tamanho: {len(new_text)})")
        
        if len(new_text) != 40:
            print(f"❌ [DEBUG leQr] Tamanho do texto ({len(new_text)}) diferente de 40 caracteres esperados")
            new_text = None
        else:
            print(f"✅ [DEBUG leQr] Tamanho correto (40 caracteres)")
            new_text_original = new_text
            new_text = new_text.replace('#', '') # Substitui os "#" por null
            print(f"🔍 [DEBUG leQr] Texto após remover '#': '{new_text}' (tamanho: {len(new_text)})")
            
            if '.' not in new_text:
                print(f"❌ [DEBUG leQr] Texto não contém '.' para separar id_prova e id_aluno")
                return final
                
            id_prova = new_text.split('.')[0]
            id_aluno = new_text.split('.')[1]
            print(f"🔍 [DEBUG leQr] id_prova='{id_prova}', id_aluno='{id_aluno}'")

            # Esse if verifica se o primeiro número e o segundo número podem
            # ser convetidos para numeral
            if ((id_prova.isdigit()) and (id_aluno.isdigit())):
                final = {
                    'id_prova': int(id_prova),
                    'id_aluno': int(id_aluno)
                }
                print(f"✅ [DEBUG leQr] QR code válido detectado: {final}")
            else:
                print(f"❌ [DEBUG leQr] id_prova ou id_aluno não são numéricos (id_prova.isdigit()={id_prova.isdigit()}, id_aluno.isdigit()={id_aluno.isdigit()})")
    except Exception as error:
        print(f'❌ [DEBUG leQr] Something went wrong!\n{error}')
        import traceback
        traceback.print_exc()
        
    #retorna apenas o texto contido
    print(f"🔍 [DEBUG leQr] Retornando: {final}")
    return final

def escreveQr(texto):
    """
    Codifica um texto em QRcode e retorna-o como imagem:

    @parâmetro texto Texto que vai ser codificado em QRcode

    """
    # Tentar usar qrcode (biblioteca padrão) primeiro, depois pyqrcode
    if qrcode is not None:
        # Usar biblioteca qrcode (já instalada)
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=6,
            border=2,
        )
        qr.add_data(texto)
        qr.make(fit=True)
        
        # Criar imagem do QR code
        qr_img = qr.make_image(fill_color="black", back_color="white")
        
        # Converter PIL Image para numpy array (OpenCV)
        img_array = np.array(qr_img.convert('RGB'))
        img = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        
    elif pyqrcode is not None:
        # Usar pyqrcode (fallback)
        code = pyqrcode.create(texto)
        qr_temp_path = 'qr.png'
        try:
            code.png(qr_temp_path, scale=6)
        except Exception as e:
            raise ValueError(f"Erro ao gerar arquivo PNG do QR code: {str(e)}")
        
        img = cv2.imread(qr_temp_path)
        if img is None:
            if not os.path.exists(qr_temp_path):
                raise ValueError(f"Erro ao gerar QR code: arquivo {qr_temp_path} não foi criado")
            else:
                raise ValueError(f"Erro ao carregar QR code: não foi possível ler {qr_temp_path}")
    else:
        raise ImportError("Nenhuma biblioteca de QR code disponível. Instale 'qrcode' ou 'pyqrcode'")
    
    CURRENT_FOLDER = os.path.dirname(__file__)
    logo_path = f'{CURRENT_FOLDER}/../assets/logo_qr.jpg'
    
    # Tentar carregar logo, se não existir, retornar QR code sem logo
    logo_img = cv2.imread(logo_path)
    if logo_img is None:
        # Logo não encontrado, retornar QR code simples sem logo
        return img
    
    # Se logo existe, adicionar ao QR code
    logo_qr = cv2.cvtColor(logo_img, cv2.COLOR_BGR2RGB)
    logo_h, logo_w, _ = logo_qr.shape
    
    img_h, img_w, _ = img.shape
    # Mudando o tamanho da logo pra 20% do tamanho do qr code
    prop = logo_w/logo_h
    logo_qr = cv2.resize(logo_qr, (int(img_w*20/100), int((img_w*20/100)  *prop)))
    
    logo_h, logo_w, _ = logo_qr.shape

    img[int(img_h/2-logo_h/2):int(img_h/2+logo_h/2), int(img_w/2-logo_w/2):int(img_w/2+logo_w/2)] = logo_qr

    return img



def formataQr(msg):
    """
    Dada uma string, prenche essa string até atingir o tamanho 20 e retorna essa
    nova string.

    @parâmetro msg String que será prenchida

    """
    txt_msg = str(msg)
    zeros = ''
    if len(txt_msg) < 9999999999999999999999999999999999999999:
        for i in range(40-len(txt_msg)):
            zeros += '#'
        txt_msg = zeros + txt_msg
    return txt_msg