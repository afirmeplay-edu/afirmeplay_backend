from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from .config import Config
from dotenv import load_dotenv

import os

db = SQLAlchemy()
jwt = JWTManager()

def create_app():
    load_dotenv()
    
    app = Flask(__name__)
    app.config.from_object(Config)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['JWT_SECRET_KEY'] = os.getenv("JWT_SECRET_KEY")
    
      # Configurações para JWT via Cookie:
    app.config['JWT_TOKEN_LOCATION'] = ['cookies']
    app.config['JWT_ACCESS_COOKIE_NAME'] = 'access_token'
    app.config['JWT_COOKIE_SECURE'] = False  # True em produção com HTTPS
    app.config['JWT_COOKIE_SAMESITE'] = 'Strict'
    app.config['JWT_COOKIE_CSRF_PROTECT'] = False  # Ative se quiser proteção extra

    db.init_app(app)
    jwt.init_app(app)

    # Importar rotas
    from .routes import escola_routes, aluno_routes, avaliacao_routes, questao_routes,login,logout,admin_route
    
    app.register_blueprint(escola_routes.bp)
    app.register_blueprint(aluno_routes.bp)
    app.register_blueprint(avaliacao_routes.bp)
    app.register_blueprint(questao_routes.bp)
    app.register_blueprint(login.bp)
    app.register_blueprint(logout.bp)
    app.register_blueprint(admin_route.bp)

    return app
