from flask import Flask, send_from_directory, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate

from .config import Config
from dotenv import load_dotenv
import os
import logging
import traceback

# Importar configuração de logging e alertas Telegram
from .utils.logging_config import setup_logging
from .utils.telegram_alert import send_telegram_alert

db = SQLAlchemy()
jwt = JWTManager()
migrate = Migrate()

# Configuração da documentação OpenAPI
OPENAPI_SPEC_URL = '/swagger.yaml'  # Caminho onde o arquivo OpenAPI será servido

def create_app():
    # Carregar variáveis de ambiente do arquivo .env da pasta app/
    load_dotenv('app/.env')
    
    app = Flask(__name__)
    
    # Configurar logging estruturado
    setup_logging(app)
    
    # Configuração para não redirecionar requisições OPTIONS
    app.url_map.strict_slashes = False

    # Configuração do CORS
    CORS(app, resources={
        r"/*": {
            "origins": [os.getenv('FRONTEND_URL'), "http://localhost:8080",],
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
    migrate.init_app(app, db)
    
    # Inicializar Celery (para processamento assíncrono de relatórios)
    try:
        from app.report_analysis.celery_app import init_celery
        init_celery(app)
        app.logger.info("Celery inicializado com sucesso")
    except Exception as e:
        app.logger.warning(f"Celery não pôde ser inicializado: {str(e)}. Processamento assíncrono desabilitado.")
    
    # Importar rotas
    from .routes import school_routes, test_routes, question_routes, login, logout, admin_route, educationStage_routes, grades_routes, persistUser_routes, city_routes, student_routes, user_routes, class_routes, schoolTeacher, teacherClass, professor_route, subject_routes, skill_routes,student_answer_routes, userQuickLinks_routes, evaluation_results_routes, basic_endpoints, evaluation_routes, game_routes, manager_routes, report_routes, physical_test_routes, student_grades_routes, calendar_routes, dashboard_routes, answer_sheet_routes
    from app.socioeconomic_forms.routes import socioeconomic_form_routes
    from app.socioeconomic_forms.routes import filter_routes
    from .play_tv import routes as playtv_routes
    from .competicoes import routes as competicoes_routes
    # Importar rotas de report_analysis (processamento assíncrono)
    from app.report_analysis import routes as report_analysis_routes
    
    app.register_blueprint(school_routes.bp)
    app.register_blueprint(test_routes.bp)
    app.register_blueprint(evaluation_routes.bp)  # Novo blueprint separado para /evaluations/
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
    app.register_blueprint(report_routes.bp)
    # Registrar blueprint de report_analysis (sobrescreve algumas rotas com versão assíncrona)
    app.register_blueprint(report_analysis_routes.bp)
    app.register_blueprint(basic_endpoints.bp)
    app.register_blueprint(game_routes.bp)
    app.register_blueprint(manager_routes.bp)
    app.register_blueprint(physical_test_routes.bp)
    app.register_blueprint(student_grades_routes.bp)
    app.register_blueprint(calendar_routes.bp)
    app.register_blueprint(dashboard_routes.bp)
    app.register_blueprint(answer_sheet_routes.bp)
    app.register_blueprint(socioeconomic_form_routes.bp)
    app.register_blueprint(filter_routes.bp)
    app.register_blueprint(playtv_routes.bp)
    app.register_blueprint(competicoes_routes.bp)
    # Importar modelos para garantir que as tabelas sejam criadas
    from .models import City, School, SchoolTeacher, Teacher, Student, Subject, Class, ClassSubject, ClassTest, Test, EducationStage, Grade, Skill, Question, StudentAnswer, UserQuickLinks, TeacherClass, User, Manager
    from .competicoes.models import Competition, CompetitionEnrollment, CompetitionResult

    # Rota para servir o arquivo swagger.yaml a partir do diretório raiz do projeto
    @app.route('/swagger.yaml')
    def serve_swagger_yaml():
        return send_from_directory(os.path.dirname(app.root_path), 'swagger.yaml')
    
    # Rota para disponibilizar a documentação via Redoc
    @app.route('/')
    def root():
        return '''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8" />
            <title>Backend Innovaplay API Documentation</title>
            <style>
                html, body { margin: 0; padding: 0; height: 100%; }
                body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; overflow-y: auto; }
                .redoc-wrap { min-height: 100vh; }
            </style>
        </head>
        <body>
            <div class="redoc-wrap" id="redoc-container"></div>
            <script src="https://cdn.jsdelivr.net/npm/redoc@2.1.3/bundles/redoc.standalone.js"></script>
            <script>
                (async function() {
                    const container = document.getElementById('redoc-container');
                    const candidates = ['/api/swagger.yaml', '/swagger.yaml'];
                    let specUrl = null;

                    for (const url of candidates) {
                        try {
                            const resp = await fetch(url, { method: 'HEAD' });
                            if (resp.ok) {
                                specUrl = url;
                                break;
                            }
                        } catch (err) {
                            console.warn('Tentativa de carregar spec falhou para', url, err);
                        }
                    }

                    if (!specUrl) {
                        container.innerHTML = '<p style="padding:16px;font-family:sans-serif;">Não foi possível localizar o arquivo swagger.yaml. Verifique se o backend está servindo o endpoint correto.</p>';
                        return;
                    }

                    Redoc.init(specUrl, {}, container);
                })();
            </script>
        </body>
        </html>
        '''
    
    # Error handler global para capturar exceções não tratadas
    @app.errorhandler(Exception)
    def handle_exception(e):
        """
        Handler global de exceções.
        Registra o erro com detalhes completos e envia alerta para Telegram.
        """
        print(f"=== DEBUG handle_exception: ERRO CAPTURADO PELO HANDLER GLOBAL ===")
        print(f"Erro: {str(e)}")
        print(f"Tipo do erro: {type(e).__name__}")
        
        # Obter informações do contexto da requisição
        route = request.path if request else None
        method = request.method if request else None
        print(f"DEBUG: Rota: {route}, Método: {method}")
        
        # Tentar obter informações do usuário autenticado
        user_id = None
        user_email = None
        try:
            from app.decorators.role_required import get_current_user_from_token
            user_info = get_current_user_from_token()
            if user_info:
                user_id = user_info.get('id')
                user_email = user_info.get('email')
        except Exception:
            # Se falhar ao obter user_id, continua sem ele
            pass
        print(f"DEBUG: Usuário - ID: {user_id}, Email: {user_email}")
        
        # Obter stack trace completo
        stack_trace = traceback.format_exc()
        print(f"DEBUG: Stack Trace completo:\n{stack_trace}")
        
        # Informações adicionais do contexto
        additional_info = {}
        if request:
            additional_info['URL Completa'] = request.url
            additional_info['IP'] = request.remote_addr
            additional_info['User-Agent'] = request.headers.get('User-Agent', 'N/A')
            if request.is_json:
                try:
                    json_data = request.get_json(silent=True)
                    if json_data:
                        json_str = str(json_data)[:300]
                        additional_info['Body JSON'] = json_str
                except Exception:
                    pass
            print(f"DEBUG: Query params: {request.args.to_dict()}")
        
        # Logar erro completo com stack trace
        app.logger.exception(
            f"Erro não tratado na rota {method} {route}: {str(e)}\n"
            f"Usuário ID: {user_id}, Email: {user_email}\n"
            f"Stack Trace:\n{stack_trace}"
        )
        
        # Enviar alerta para Telegram (apenas para erros críticos)
        # Verificar se é um erro 500 ou outro erro crítico
        if isinstance(e, Exception):
            send_telegram_alert(
                error_message=str(e),
                route=route,
                method=method,
                user_id=user_id,
                stack_trace=stack_trace,
                additional_info=additional_info if additional_info else None
            )
        
        # Retornar resposta genérica (não expor detalhes internos)
        print(f"=== DEBUG handle_exception: RETORNANDO ERRO 500 ===")
        return jsonify({
            "error": "Erro interno no servidor",
            "message": "Ocorreu um erro inesperado. Os administradores foram notificados.",
            "details": str(e)  # Adicionar detalhes para debug
        }), 500
    
    def _get_user_info():
        """Helper para obter informações do usuário autenticado"""
        user_id = None
        user_email = None
        try:
            from app.decorators.role_required import get_current_user_from_token
            user_info = get_current_user_from_token()
            if user_info:
                user_id = user_info.get('id')
                user_email = user_info.get('email')
        except Exception:
            pass
        return user_id, user_email
    
    def _get_request_context():
        """Helper para obter contexto da requisição"""
        route = request.path if request else None
        method = request.method if request else None
        
        additional_info = {}
        if request:
            additional_info['URL Completa'] = request.url
            additional_info['IP'] = request.remote_addr
            additional_info['User-Agent'] = request.headers.get('User-Agent', 'N/A')
            if request.is_json:
                try:
                    json_data = request.get_json(silent=True)
                    if json_data:
                        json_str = str(json_data)[:300]
                        additional_info['Body JSON'] = json_str
                except Exception:
                    pass
        
        return route, method, additional_info
    
    def _send_error_alert(status_code, error_message, route, method, user_id, additional_info):
        """Helper para enviar alerta Telegram para erros"""
        send_telegram_alert(
            error_message=error_message,
            route=route,
            method=method,
            user_id=user_id,
            stack_trace=None,
            additional_info=additional_info if additional_info else None
        )
    
    # Error handler para 400 (Bad Request)
    @app.errorhandler(400)
    def handle_400(e):
        """Handler para erros 400 (Bad Request)"""
        route, method, additional_info = _get_request_context()
        user_id, user_email = _get_user_info()
        
        error_msg = str(e) if e else "Bad Request"
        app.logger.warning(
            f"400 Bad Request: {method} {route} - "
            f"Usuário: {user_email or 'N/A'} ({user_id or 'N/A'}) - "
            f"Erro: {error_msg}"
        )
        
        _send_error_alert(400, f"Bad Request: {error_msg}", route, method, user_id, additional_info)
        return jsonify({"error": "Bad Request", "message": error_msg}), 400
    
    # Error handler para 401 (Unauthorized)
    @app.errorhandler(401)
    def handle_401(e):
        """Handler para erros 401 (Unauthorized)"""
        route, method, additional_info = _get_request_context()
        user_id, user_email = _get_user_info()
        
        error_msg = str(e) if e else "Unauthorized"
        app.logger.warning(
            f"401 Unauthorized: {method} {route} - "
            f"Usuário: {user_email or 'N/A'} ({user_id or 'N/A'}) - "
            f"IP: {request.remote_addr if request else 'N/A'}"
        )
        
        _send_error_alert(401, f"Unauthorized: {error_msg}", route, method, user_id, additional_info)
        return jsonify({"error": "Unauthorized", "message": error_msg}), 401
    
    # Error handler para 403 (Forbidden)
    @app.errorhandler(403)
    def handle_403(e):
        """Handler para erros 403 (Forbidden)"""
        route, method, additional_info = _get_request_context()
        user_id, user_email = _get_user_info()
        
        error_msg = str(e) if e else "Forbidden"
        app.logger.warning(
            f"403 Forbidden: {method} {route} - "
            f"Usuário: {user_email or 'N/A'} ({user_id or 'N/A'}) - "
            f"IP: {request.remote_addr if request else 'N/A'}"
        )
        
        _send_error_alert(403, f"Forbidden: {error_msg}", route, method, user_id, additional_info)
        return jsonify({"error": "Forbidden", "message": error_msg}), 403
    
    # Error handler para 404 (Not Found)
    @app.errorhandler(404)
    def handle_404(e):
        """Handler para erros 404 (Not Found)"""
        route, method, additional_info = _get_request_context()
        user_id, user_email = _get_user_info()
        
        error_msg = str(e) if e else "Recurso não encontrado"
        app.logger.warning(
            f"404 Not Found: {method} {route} - "
            f"Usuário: {user_email or 'N/A'} ({user_id or 'N/A'}) - "
            f"IP: {request.remote_addr if request else 'N/A'}"
        )
        
        _send_error_alert(404, f"Recurso não encontrado: {route}", route, method, user_id, additional_info)
        return jsonify({"error": "Recurso não encontrado"}), 404
    
    # Error handler para 504 (Gateway Timeout)
    @app.errorhandler(504)
    def handle_504(e):
        """Handler para erros 504 (Gateway Timeout)"""
        route, method, additional_info = _get_request_context()
        user_id, user_email = _get_user_info()
        
        error_msg = str(e) if e else "Gateway Timeout"
        app.logger.error(
            f"504 Gateway Timeout: {method} {route} - "
            f"Usuário: {user_email or 'N/A'} ({user_id or 'N/A'}) - "
            f"IP: {request.remote_addr if request else 'N/A'}"
        )
        
        _send_error_alert(504, f"Gateway Timeout: {error_msg}", route, method, user_id, additional_info)
        return jsonify({"error": "Gateway Timeout", "message": error_msg}), 504
    
    # Error handler específico para 500
    @app.errorhandler(500)
    def handle_500(e):
        """Handler específico para erros 500 (já coberto pelo handler genérico, mas mantido para compatibilidade)"""
        return handle_exception(e)

    return app
