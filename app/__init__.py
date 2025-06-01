from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_jwt_extended import JWTManager

from .config import Config
from dotenv import load_dotenv
import os

db = SQLAlchemy()
jwt = JWTManager()

def create_app():
    load_dotenv()
    
    app = Flask(__name__)
    
   

    # Configuração do JWT
    app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY')
    app.config['JWT_TOKEN_LOCATION'] = ['headers']
    app.config['JWT_HEADER_NAME'] = 'Authorization'
    app.config['JWT_HEADER_TYPE'] = 'Bearer'
    
    # Configuração do banco de dados
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Inicialização das extensões
    db.init_app(app)
    jwt.init_app(app)

    # Importar rotas
    from .routes import school_routes, test_routes, question_routes, login,logout,admin_route,educationStage_routes,grades_routes,persistUser_routes,city_routes,student_routes, user_routes, class_routes
    
    app.register_blueprint(school_routes.bp)
    app.register_blueprint(test_routes.bp)
    app.register_blueprint(question_routes.bp)
    app.register_blueprint(login.bp)
    app.register_blueprint(logout.bp)
    app.register_blueprint(admin_route.bp)
    app.register_blueprint(educationStage_routes.bp)
    app.register_blueprint(grades_routes.bp)
    app.register_blueprint(persistUser_routes.bp)
    app.register_blueprint(city_routes.bp)
    app.register_blueprint(student_routes.bp)
    app.register_blueprint(user_routes.bp)
    app.register_blueprint(class_routes.bp)

    return app
