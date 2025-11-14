from app import create_app, db

# from . import create_app, db
import requests
import os
import threading
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
        
        # Iniciar scheduler de tarefas agendadas
        try:
            start_scheduler()
        except Exception as e:
            logging.error(f"Erro ao iniciar scheduler: {str(e)}", exc_info=True)
    
    try:
        app.run(debug=True, host="0.0.0.0", port=5000)
    except KeyboardInterrupt:
        logging.info("Aplicação interrompida pelo usuário")
    finally:
        # Parar scheduler quando a aplicação for encerrada
        try:
            stop_scheduler()
        except Exception as e:
            logging.error(f"Erro ao parar scheduler: {str(e)}", exc_info=True)
