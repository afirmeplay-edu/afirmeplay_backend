from app import create_app
import logging

# Importar o script de inicialização do banco
from init_db import check_and_init_database

# Importar o scheduler de tarefas agendadas
from app.services.scheduled_tasks import start_scheduler, stop_scheduler

app = create_app()

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
        
        # Iniciar scheduler de tarefas agendadas (passar app)
        try:
            start_scheduler(app)
        except Exception as e:
            logging.error("Erro ao iniciar scheduler", exc_info=True)
    
    try:
        # Tentar usar SocketIO se disponível, senão usar app.run normal
        try:
            from app.socketio import socketio
            socketio.run(app, host="0.0.0.0", port=5000, debug=True, use_reloader=True)
        except ImportError:
            # SocketIO não disponível, usar Flask normal
            app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=True)
    except KeyboardInterrupt:
        logging.info("Aplicação interrompida")
    finally:
        # Parar scheduler quando a aplicação for encerrada
        try:
            stop_scheduler()
        except Exception:
            logging.error("Erro ao parar scheduler", exc_info=True)
