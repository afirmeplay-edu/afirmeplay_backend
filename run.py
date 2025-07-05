from app import create_app, db

# from . import create_app, db
from flask_cors import CORS
import requests
import os
import threading


app = create_app()


PING_INTERVAL = 14 * 60
SELF_URL = os.environ.get("SELF_URL", "https://innovaplay-backend.onrender.com")


def keep_alive():
    while True:
        try:
            res = requests.get(SELF_URL)
            print(f"[KEEPALIVE] Status: {res.status_code}")
        except Exception as e:
            print(f"[KEEPALIVE ERROR] {e}")


def start_keep_alive():
    thread = threading.Thread(target=keep_alive, daemon=True)
    thread.start()


@app.route("/ping")
def ping():
    return "pong", 200


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

print("Tentando criar tabelas do banco de dados...")
with app.app_context():
    try:
        db.create_all()
        print("Tabelas criadas com sucesso!")
    except Exception as e:
        print(f"Erro ao criar tabelas: {str(e)}")

if __name__ == "__main__":
    # start_keep_alive()
    app.run(debug=True, host="0.0.0.0", port=os.getenv("PORT"))
