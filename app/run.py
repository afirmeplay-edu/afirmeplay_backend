from app import create_app, db
from flask_cors import CORS
import requests
import os

app = create_app()

PING_INTERVAL = 14 * 60
SELF_URL = os.environ.get("SELF_URL", )

# para permitir somente o backend CORS(app, resources={r"/*": {"origins": "http://localhost:5173"}}, supports_credentials=True)
# resources={r"/*": {"origins": "https://innovplay.vercel.app"}}
CORS(app,  supports_credentials=True)

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)
