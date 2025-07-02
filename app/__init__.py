from flask import Flask, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_swagger_ui import get_swaggerui_blueprint

from .config import Config
from dotenv import load_dotenv
import os

db = SQLAlchemy()
jwt = JWTManager()

SWAGGER_URL = '/api'  # URL for Swagger UI
API_URL = '/swagger.yaml' # URL where our Swagger spec will be served

# Call factory function to create our blueprint
swaggerui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={
        'app_name': "InvaPlay Backend API Documentation"
    }
)

def create_app():
    # Carregar variáveis de ambiente do arquivo .env da pasta app/
    load_dotenv('app/.env')
    
    app = Flask(__name__)
    
    # Configuração para não redirecionar requisições OPTIONS
    app.url_map.strict_slashes = False

    # Configuração do CORS
    CORS(app, resources={
        r"/*": {
            "origins": ["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173", 
                       "http://localhost:8080", "http://127.0.0.1:8080"],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"],
            "expose_headers": ["Authorization"],
            "supports_credentials": True
        }
    })

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
    from .routes import school_routes, test_routes, question_routes, login, logout, admin_route, educationStage_routes, grades_routes, persistUser_routes, city_routes, student_routes, user_routes, class_routes, schoolTeacher, teacherClass, professor_route, subject_routes, skill_routes,student_answer_routes, userQuickLinks_routes, evaluation_results_routes, basic_endpoints
    
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
    app.register_blueprint(schoolTeacher.school_teacher_bp)
    app.register_blueprint(teacherClass.teacher_class_bp)
    app.register_blueprint(professor_route.bp)
    app.register_blueprint(subject_routes.bp)
    app.register_blueprint(skill_routes.skill_bp)
    app.register_blueprint(student_answer_routes.bp)
    app.register_blueprint(userQuickLinks_routes.bp)
    app.register_blueprint(evaluation_results_routes.bp)
    app.register_blueprint(basic_endpoints.bp)
    # Registrar blueprint do Swagger UI
    app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)

    # Importar modelos para garantir que as tabelas sejam criadas
    from .models import City, School, SchoolTeacher, Teacher, Student, Subject, Class, ClassSubject, ClassTest, Test, EducationStage, Grade, Skill, Question, StudentAnswer, UserQuickLinks, TeacherClass, User

    # Rota para servir o arquivo swagger.yaml a partir do diretório raiz do projeto
    @app.route('/swagger.yaml')
    def serve_swagger_yaml():
        return send_from_directory(os.path.dirname(app.root_path), 'swagger.yaml')

    return app
