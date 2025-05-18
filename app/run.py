from app import create_app, db
from flask_cors import CORS
import requests
import os
import threading

app = create_app()

PING_INTERVAL = 14 * 60
SELF_URL = os.environ.get("SELF_URL","https://innovaplay-backend.onrender.com")

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
    return "pong",200
     
            
# para permitir somente o backend CORS(app, resources={r"/*": {"origins": "http://localhost:5173"}}, supports_credentials=True)
# resources={r"/*": {"origins": "https://innovplay.vercel.app"}}
CORS(app,  supports_credentials=True)

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    start_keep_alive()
    app.run(debug=True)
