from app import create_app, db
from flask_cors import CORS

app = create_app()

# para permitir somente o backend CORS(app, resources={r"/*": {"origins": "http://localhost:5173"}}, supports_credentials=True)
# resources={r"/*": {"origins": "https://innovplay.vercel.app"}}
CORS(app,  supports_credentials=True)

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)
