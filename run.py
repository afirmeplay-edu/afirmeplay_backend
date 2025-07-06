from app import create_app, db

# from . import create_app, db
from flask_cors import CORS
import requests
import os
import threading

# Importar o script de inicialização do banco
from init_db import check_and_init_database

app = create_app()


# Configuração do CORS
CORS(
    app,
    resources={
        r"/*": {
            "origins": ["http://localhost:8080", "https://innovplay.vercel.app"],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization", "Accept"],
            "expose_headers": ["Content-Type", "Authorization"],
            "supports_credentials": False,
            "max_age": 3600,
        }
    },
    supports_credentials=False,
)

# print("Tentando criar tabelas do banco de dados...")
# with app.app_context():
#     try:
#         db.create_all()
#         print("Tabelas criadas com sucesso!")
#     except Exception as e:
#         print(f"Erro ao criar tabelas: {str(e)}")

if __name__ == "__main__":
    # Verificar e inicializar o banco antes de rodar o servidor
    with app.app_context():
        check_and_init_database()
    
    app.run(debug=True, host="0.0.0.0", port=os.getenv("PORT"))
