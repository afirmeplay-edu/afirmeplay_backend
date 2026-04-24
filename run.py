from app import create_app
import logging

# Importar o script de inicialização do banco
from init_db import check_and_init_database

# Importar o scheduler de tarefas agendadas
from app.services.scheduled_tasks import start_scheduler, stop_scheduler

app = create_app()


if __name__ == "__main__":
    # Verificar e inicializar o banco antes de rodar o servidor
    with app.app_context():
        check_and_init_database()
        
        # Iniciar scheduler de tarefas agendadas (passar app)
        try:
            # Em debug com reloader, evitar iniciar duas vezes (processo pai + filho).
            # Em produção (gunicorn), o scheduler deve ser habilitado via ENABLE_SCHEDULER=1
            # e é inicializado em create_app() com advisory lock no Postgres.
            import os

            if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
                start_scheduler(app)
        except Exception as e:
            logging.error("Erro ao iniciar scheduler", exc_info=True)
    
    try:
        # Executar servidor Flask padrão (sem Socket.IO)
        app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=True)
    except KeyboardInterrupt:
        logging.info("Aplicação interrompida")
    finally:
        # Parar scheduler quando a aplicação for encerrada
        try:
            stop_scheduler()
        except Exception:
            logging.error("Erro ao parar scheduler", exc_info=True)
