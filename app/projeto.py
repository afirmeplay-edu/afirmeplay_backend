import numpy as np
import cv2
import tkinter as tk
from tkinter import filedialog
import smtplib
from email.message import EmailMessage
from email.mime.image import MIMEImage
import os
import sys
# Adicionar o diretório pai ao path para encontrar o módulo app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Imports do nosso sistema
from app import create_app
from app.models.question import Question
from app.models.testQuestion import TestQuestion
from app.models.testSession import TestSession
from app.models.formCoordinates import FormCoordinates

def atualizar_nota(id_aluno, nota):
    with open('alunos.txt', 'r', encoding='utf-8') as f:
        linhas = f.readlines()

    nova_lista = []
    for linha in linhas:
        partes = linha.strip().split(',')
        if partes[0] == 'id':
            nova_lista.append('id,nome,email,nota\n')
        elif partes[0] == id_aluno:
            nova_lista.append(f"{partes[0]},{partes[1]},{partes[2]},{nota}\n")
        else:
            nova_lista.append(','.join(partes) + '\n')

    with open('alunos.txt', 'w', encoding='utf-8') as f:
        f.writelines(nova_lista)
    print(f"Nota adicionada")


def enviar_email(destinatario, nome_aluno, nota, questoes, imagem_com_nota, gabarito):
    remetente = "corretordegabaritos@gmail.com"
    senha_app = "popnicbwvshlseoi"

    assunto = "Resultado da sua prova"
    corpo = f"""
    Olá {nome_aluno},

    Sua prova foi corrigida automaticamente pelo sistema.
    Sua nota foi: {nota}/{questoes}

    Obrigado por participar!

    Att,
    Sistema de Correção Automática
    """

    msg = EmailMessage()
    msg["Subject"] = assunto
    msg["From"] = remetente
    msg["To"] = destinatario
    msg.set_content(corpo)

    try:
        _, buffer = cv2.imencode('.jpg', imagem_com_nota)
        image_bytes = buffer.tobytes()
        _, buffer1 = cv2.imencode('.jpg', gabarito)
        image_bytes1 = buffer1.tobytes()

        msg.add_attachment(image_bytes, maintype='image', subtype='jpeg', filename=f"{nome_aluno}_resultado.jpg")
        msg.add_attachment(image_bytes1, maintype='image', subtype='jpeg', filename=f"gabarito.jpg")

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(remetente, senha_app)
            smtp.send_message(msg)
        print(f"E-mail enviado para {destinatario}")
    except Exception as e:
        print(f"Erro ao enviar e-mail: {e}")

def carregar_dados_alunos(caminho_arquivo="alunos.txt"):
    alunos = {}
    with open(caminho_arquivo, "r", encoding="utf-8") as arquivo:
        next(arquivo)  # pula o cabeçalho
        for linha in arquivo:
            partes = linha.strip().split(",")
            if len(partes) == 3:  # se não tiver nota
                partes.append("")  # adiciona nota vazia
            id_aluno, nome, email, nota = partes
            alunos[id_aluno] = {"nome": nome, "email": email, "nota": nota}
    return alunos


def ordenar_pontos(pontos):
    pontos = pontos.reshape((4, 2))
    soma = pontos.sum(axis=1)
    diff = np.diff(pontos, axis=1)

    topo_esq = pontos[np.argmin(soma)]
    baixo_dir = pontos[np.argmax(soma)]
    topo_dir = pontos[np.argmin(diff)]
    baixo_esq = pontos[np.argmax(diff)]

    return np.array([topo_esq, topo_dir, baixo_dir, baixo_esq], dtype="float32")

def aplicar_transformacao_perspectiva(img, contorno, largura=688, altura=301):
    epsilon = 0.02 * cv2.arcLength(contorno, True)
    aproximado = cv2.approxPolyDP(contorno, epsilon, True)

    if len(aproximado) == 4:
        pontos_ordenados = ordenar_pontos(aproximado)

        destino = np.array([
            [0, 0],
            [largura - 1, 0],
            [largura - 1, altura - 1],
            [0, altura - 1]
        ], dtype="float32")

        matriz = cv2.getPerspectiveTransform(pontos_ordenados, destino)
        corrigido = cv2.warpPerspective(img, matriz, (largura, altura))
        return corrigido
    else:
        return img



# Inicializar aplicação Flask
app = create_app()

# Variáveis globais
test_id = None
num_questoes = 0
gabarito = {}
coordenadas_db = []
coordenadas_para_uso = []

with app.app_context():
    while True:
        try:
            test_id = input("Digite o ID do teste: ")
            if test_id:
                break
            else:
                print("Por favor, digite um ID válido.")
        except ValueError:
            print("Entrada inválida! Digite um ID válido.")

    # Buscar questões do teste no banco de dados
    test_questions = TestQuestion.query.filter_by(test_id=test_id).all()
    num_questoes = len(test_questions)
    
    if num_questoes == 0:
        print(f"Nenhuma questão encontrada para o teste {test_id}")
        exit()
    
    print(f"Encontradas {num_questoes} questões no teste {test_id}")

    alternativas_validas = {"A", "B", "C", "D", "E"}
    opcoes = {"A": 0, "B": 1, "C": 2, "D": 3, "E": 4}
    respostas_marcadas = []

    # Buscar respostas corretas do banco de dados
    for tq in test_questions:
        question = Question.query.get(tq.question_id)
        if question and question.correct_answer:
            gabarito[tq.order] = question.correct_answer

    print("\nGabarito carregado do banco de dados:")

    for questao, resposta in gabarito.items():
        print(f"Questão {questao}: {resposta}")

    # Buscar coordenadas do banco de dados
    form_coords = FormCoordinates.query.filter_by(test_id=test_id).first()
    if form_coords and form_coords.coordinates:
        coordenadas_db = form_coords.coordinates
        # Converter para lista se for dicionário
        if isinstance(coordenadas_db, dict):
            coordenadas_db = list(coordenadas_db.values())
        elif isinstance(coordenadas_db, list):
            # Já é lista, usar diretamente
            pass
        else:
            print(f"Tipo de coordenadas inesperado: {type(coordenadas_db)}")
            coordenadas_db = coordenadas
        print(f"Coordenadas carregadas do banco: {len(coordenadas_db)} círculos")
        print(f"Tipo: {type(coordenadas_db)}")
        print(f"Primeiras 3 coordenadas: {coordenadas_db[:3] if len(coordenadas_db) >= 3 else coordenadas_db}")
    else:
        print("Usando coordenadas fixas (coordenadas não encontradas no banco)")
        coordenadas_db = coordenadas

# Coordenadas fixas (fallback)
coordenadas = [
    (198, 14, 20, 20), (238, 14, 20, 20), (278, 14, 20, 20), (318, 14, 20, 20), (358, 14, 20, 20),
    (198, 42, 20, 20), (238, 42, 20, 20), (278, 42, 20, 20), (318, 42, 20, 20), (358, 42, 20, 20),
    (198, 70, 20, 20), (238, 70, 20, 20), (278, 70, 20, 20), (318, 70, 20, 20), (358, 70, 20, 20),
    (198, 98, 20, 20), (238, 98, 20, 20), (278, 98, 20, 20), (318, 98, 20, 20), (358, 98, 20, 20),
    (198, 126, 20, 20), (238, 126, 20, 20), (278, 126, 20, 20), (318, 126, 20, 20), (358, 126, 20, 20),
    (198, 154, 20, 20), (238, 154, 20, 20), (278, 154, 20, 20), (318, 154, 20, 20), (358, 154, 20, 20),
    (198, 182, 20, 20), (238, 182, 20, 20), (278, 182, 20, 20), (318, 182, 20, 20), (358, 182, 20, 20),
    (198, 210, 20, 20), (238, 210, 20, 20), (278, 210, 20, 20), (318, 210, 20, 20), (358, 210, 20, 20),
    (198, 238, 20, 20), (238, 238, 20, 20), (278, 238, 20, 20), (318, 238, 20, 20), (358, 238, 20, 20),
    (198, 266, 20, 20), (238, 266, 20, 20), (278, 266, 20, 20), (318, 266, 20, 20), (358, 266, 20, 20),
    (479, 14, 20, 20), (519, 14, 20, 20), (559, 14, 20, 20), (599, 14, 20, 20), (639, 14, 20, 20),
    (479, 42, 20, 20), (519, 42, 20, 20), (559, 42, 20, 20), (599, 42, 20, 20), (639, 42, 20, 20),
    (479, 70, 20, 20), (519, 70, 20, 20), (559, 70, 20, 20), (599, 70, 20, 20), (639, 70, 20, 20),
    (479, 98, 20, 20), (519, 98, 20, 20), (559, 98, 20, 20), (599, 98, 20, 20), (639, 98, 20, 20),
    (479, 126, 20, 20), (519, 126, 20, 20), (559, 126, 20, 20), (599, 126, 20, 20), (639, 126, 20, 20),
    (479, 154, 20, 20), (519, 154, 20, 20), (559, 154, 20, 20), (599, 154, 20, 20), (639, 154, 20, 20),
    (479, 182, 20, 20), (519, 182, 20, 20), (559, 182, 20, 20), (599, 182, 20, 20), (639, 182, 20, 20),
    (479, 210, 20, 20), (519, 210, 20, 20), (559, 210, 20, 20), (599, 210, 20, 20), (639, 210, 20, 20),
    (479, 238, 20, 20), (519, 238, 20, 20), (278, 238, 20, 20), (318, 238, 20, 20), (358, 238, 20, 20),
    (479, 266, 20, 20), (519, 266, 20, 20), (559, 266, 20, 20), (599, 266, 20, 20), (639, 266, 20, 20)
]

coordenada_qr = (10, 100, 100, 100)

alternativas = ['1A', '1B', '1C', '1D', '1E', '2A', '2B', '2C', '2D', '2E', '3A', '3B', '3C', '3D', '3E', '4A',
                '4B', '4C', '4D', '4E', '5A', '5B', '5C', '5D', '5E']

def ler_qrcode_em_rgb(imagem_gray):
    imagem_colorida = cv2.cvtColor(imagem_gray, cv2.COLOR_GRAY2BGR)
    detector = cv2.QRCodeDetector()
    dados, _, _ = detector.detectAndDecode(imagem_colorida)
    return dados

while True:
    print("Escolha a origem da imagem:")
    print("1 - Fazer captura")
    print("2 - Selecionar imagem do computador")
    print("3 - Webcam")
    escolha = input("Digite 1, 2 ou 3: ")

    if escolha in ["1", "2", "3"]:
        break
    else:
        print("Opção inválida!")

# Usar coordenadas do banco se disponíveis
coordenadas_para_uso = coordenadas_db if coordenadas_db else coordenadas

# Variáveis de controle
id_aluno = None
corrigindo = True
teste = 0

# Criar gabarito visual simples
recorte1 = np.ones((301, 688, 3), dtype=np.uint8) * 255  # Imagem branca 688x301

if escolha == "3":
    video = cv2.VideoCapture(1)

while corrigindo:
    respostas_marcadas = []

    if escolha == "1" and teste==0:
        video = cv2.VideoCapture(1)
        while True:
            ret, img = video.read()
            if not ret:
                cv2.namedWindow("Pré-visualização (Pressione ESPAÇO para capturar)", cv2.WINDOW_NORMAL)
                cv2.setWindowProperty("Pré-visualização (Pressione ESPAÇO para capturar)", cv2.WND_PROP_TOPMOST, 1)
                cv2.imshow("Pré-visualização (Pressione ESPAÇO para capturar)", img)
                continue
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            img = cv2.resize(img, (720, 320))
            binario2 = cv2.adaptiveThreshold(img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)
            contornos2, _ = cv2.findContours(binario2, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contornos2:
                continue
            maior_contorno2 = max(contornos2, key=cv2.contourArea)
            recorte_corrigido2 = aplicar_transformacao_perspectiva(img, maior_contorno2)

            if recorte_corrigido2 is None:
                continue

            recorte3 = recorte_corrigido2.copy()
            recorte2 = cv2.cvtColor(recorte_corrigido2, cv2.COLOR_GRAY2BGR)

            _, pontos1 = cv2.QRCodeDetector().detect(recorte3)
            if pontos1 is not None:
                id_aluno = ler_qrcode_em_rgb(recorte3)
                pontos1 = pontos1[0].astype(int)
                cv2.polylines(recorte2, [pontos1], isClosed=True, color=(0, 255, 255), thickness=2)

            cv2.namedWindow("Pré-visualização (Pressione ESPAÇO para capturar)", cv2.WINDOW_NORMAL)
            cv2.setWindowProperty("Pré-visualização (Pressione ESPAÇO para capturar)", cv2.WND_PROP_TOPMOST, 1)
            cv2.imshow("Pré-visualização (Pressione ESPAÇO para capturar)", recorte2)

            if (cv2.waitKey(1) & 0xFF) == 32 and pontos1 is not None and id_aluno is not None:
                print("ID do aluno:", id_aluno)
                imagem_gray = img.copy()
                break
        video.release()
        cv2.destroyAllWindows()
        teste = 1

    elif escolha == "2" and teste==0:
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        caminho_imagem = filedialog.askopenfilename(
            title="Selecione a imagem da resposta do aluno",
            filetypes=[("Imagens", "*.png *.jpg *.jpeg *.bmp *.tiff")]
        )

        img = cv2.imread(caminho_imagem, cv2.IMREAD_GRAYSCALE)
        img = cv2.resize(img, (720, 320))
        binario = cv2.adaptiveThreshold(img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)
        contornos, _ = cv2.findContours(binario, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        maior_contorno = max(contornos, key=cv2.contourArea)
        recorte_corrigido = aplicar_transformacao_perspectiva(img, maior_contorno)

        id_aluno = ler_qrcode_em_rgb(recorte_corrigido)

        if id_aluno:
            print("ID do aluno:", id_aluno)
        else:
            print("QR Code não detectado.")

        if not caminho_imagem:
            print("Nenhuma imagem selecionada.")
            exit()
        teste = 1

    elif escolha == "3":
        ret, img = video.read()
        if not ret:
            cv2.namedWindow("Resposta", cv2.WINDOW_NORMAL)
            cv2.setWindowProperty("Resposta", cv2.WND_PROP_TOPMOST, 1)
            cv2.imshow("Resposta", img)
            continue
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        img = cv2.resize(img, (720, 320))

    borrada = cv2.GaussianBlur(img, (5, 5), 0)
    binario = cv2.adaptiveThreshold(borrada, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)
    kernel = np.ones((3, 3), np.uint8)
    opening = cv2.morphologyEx(binario, cv2.MORPH_OPEN, kernel)
    contornos, _ = cv2.findContours(binario, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contornos:
        continue
    maior_contorno = max(contornos, key=cv2.contourArea)
    recorte_corrigido = aplicar_transformacao_perspectiva(img, maior_contorno)
    binario_corrigido = aplicar_transformacao_perspectiva(opening, maior_contorno)

    if recorte_corrigido is None or binario_corrigido is None:
        continue

    recorte = cv2.cvtColor(recorte_corrigido, cv2.COLOR_GRAY2BGR)
    imagem_gray = cv2.cvtColor(recorte, cv2.COLOR_BGR2GRAY)
    binario = binario_corrigido

    # Usar coordenadas do banco de dados se disponíveis
    coordenadas_para_uso = coordenadas_db if coordenadas_db else coordenadas
    
    print(f"🔍 Usando {len(coordenadas_para_uso)} coordenadas para {num_questoes} questões")
    
    for questao, resposta in gabarito.items():
        # Ajustar para 4 alternativas se usando coordenadas do banco
        if len(coordenadas_para_uso) == num_questoes * 4:  # 4 alternativas
            indice = (questao - 1) * 4 + opcoes[resposta]
        else:  # 5 alternativas (coordenadas fixas)
            indice = (questao - 1) * 5 + opcoes[resposta]
        
        if indice < len(coordenadas_para_uso):
            x, y, w, h = coordenadas_para_uso[indice]
            centro_x = x + w // 2
            centro_y = y + h // 2
            raio = min(w, h) // 2
            cv2.circle(recorte1, (centro_x, centro_y), raio, (0, 255, 0), 2)

    for i, coord in enumerate(coordenadas_para_uso):
        if not coord or len(coord) != 4:
            continue
            
        x, y, w, h = coord
        
        # Verificar se as coordenadas estão dentro da imagem
        if x < 0 or y < 0 or x + w > binario.shape[1] or y + h > binario.shape[0]:
            continue
            
        interesse = binario[y:y + h, x:x + w]
        mascara = np.zeros((h, w), dtype=np.uint8)
        centro_x = w // 2
        centro_y = h // 2
        raio = min(w, h) // 2
        cv2.circle(mascara, (centro_x, centro_y), raio, 255, -1)
        interesse_mascarado = cv2.bitwise_and(interesse, interesse, mask=mascara)
        total_pixels = cv2.countNonZero(mascara)
        pixels_brancos = cv2.countNonZero(interesse_mascarado)
        porcentagem_branco = (pixels_brancos / total_pixels) * 100

        if porcentagem_branco >= 70:
            respostas_marcadas.append(i)

    acertos = 0

    # Determinar número de alternativas por questão
    alternativas_por_questao = 4 if len(coordenadas_para_uso) == num_questoes * 4 else 5
    
    for i in range(num_questoes):
        alternativas_questao = [(i * alternativas_por_questao) + j for j in range(alternativas_por_questao)]

        for j in alternativas_questao:
            if j in respostas_marcadas:
                marcada = j
                resposta_marcada = j % alternativas_por_questao
                resposta_correta = opcoes[gabarito[i + 1]]
                x, y, w, h = coordenadas_para_uso[marcada]
                if resposta_marcada == resposta_correta:
                    cor = (0, 255, 0)
                    acertos += 1
                else:
                    cor = (0, 0, 255)
                centro_x = x + w // 2
                centro_y = y + h // 2
                raio = min(w, h) // 2
                cv2.circle(recorte, (centro_x, centro_y), raio, cor, 2)
                break


    imagem_com_nota = np.ones((recorte.shape[0] + 50, recorte.shape[1], 3), dtype=np.uint8) * 255
    imagem_com_nota[:recorte.shape[0], :] = recorte
    nota = f"Nota: {acertos}/{num_questoes}"
    cv2.putText(imagem_com_nota, nota, (50, recorte.shape[0] + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 0), 2)

    _, pontos = cv2.QRCodeDetector().detect(imagem_com_nota)
    if pontos is not None:
        pontos = pontos[0].astype(int)
        cv2.polylines(imagem_com_nota, [pontos], isClosed=True, color=(0, 255, 255), thickness=2)



    cv2.namedWindow("Gabarito", cv2.WINDOW_NORMAL)
    cv2.setWindowProperty("Gabarito", cv2.WND_PROP_TOPMOST, 1)
    cv2.imshow("Gabarito", recorte1)

    cv2.namedWindow("Resposta", cv2.WINDOW_NORMAL)
    cv2.setWindowProperty("Resposta", cv2.WND_PROP_TOPMOST, 1)
    cv2.imshow("Resposta", imagem_com_nota)

    tecla = cv2.waitKey(1) & 0xFF
    if tecla == 13:
        if escolha =='3':
            id_aluno = ler_qrcode_em_rgb(imagem_gray)
            print("ID do aluno:", id_aluno)
        alunos = carregar_dados_alunos()
        nota1 = f"{acertos}/{num_questoes}"
        pasta_destino = "provas_corrigidas"
        os.makedirs(pasta_destino, exist_ok=True)

        if id_aluno in alunos:
            nome = alunos[id_aluno]["nome"]
            email = alunos[id_aluno]["email"]

            nome_arquivo = f"{nome.replace(' ', '_')}.jpg"
            caminho_salvar = os.path.join(pasta_destino, nome_arquivo)
            try:
                cv2.imwrite(caminho_salvar, imagem_com_nota)
                print(f"Imagem corrigida salva em: {caminho_salvar}")
            except Exception as e:
                print(f"Erro ao salvar a imagem {caminho_salvar}: {e}")
            atualizar_nota(id_aluno, nota1)
            enviar_email(email, nome, acertos, num_questoes, imagem_com_nota, recorte1)
        else:
            print(f"ID {id_aluno} não encontrado na lista de alunos. Imagem e nota não foram salvas e e-mail não foi enviado.")

        cv2.destroyAllWindows()
        teste = 0
    if tecla == 27:
        corrigindo = False
        cv2.destroyAllWindows()
        cv2.waitKey(1)
        break




print("Correções finalizadas.")