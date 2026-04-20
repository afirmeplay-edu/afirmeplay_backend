# -*- coding: utf-8 -*-
"""
Serviço de tarefas agendadas usando APScheduler
Verifica e atualiza automaticamente o status de avaliações expiradas
"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from app import db
from app.utils.tenant_middleware import city_id_to_schema_name, set_search_path
from app.models.test import Test
from app.models.classTest import ClassTest
from app.models.testSession import TestSession
from datetime import datetime
import dateutil.parser
import pytz
import logging

# Instância global do scheduler
scheduler = BackgroundScheduler()


def check_expired_evaluations(app=None):
    """
    Verifica todas as avaliações expiradas e atualiza seus status
    Executa a cada 5 minutos
    
    Args:
        app: Instância da aplicação Flask (opcional, tenta usar current_app se não fornecido)
    
    IMPORTANTE: Esta função deve ser chamada dentro do contexto da aplicação Flask
    """
    from flask import current_app
    from sqlalchemy.exc import ProgrammingError
    
    # Se app não foi fornecido, tentar usar current_app
    if app is None:
        try:
            app = current_app._get_current_object()
        except RuntimeError:
            # Se não há contexto, precisamos criar a app
            from app import create_app
            app = create_app()
    
    from app.models.city import City

    # Garantir que estamos dentro do contexto da aplicação
    with app.app_context():
        try:
            logging.info("Iniciando verificação de avaliações expiradas...")
            # class_test existe nos schemas city_xxx; iterar por cidade
            try:
                cities = City.query.with_entities(City.id).all()
            except ProgrammingError as e:
                logging.warning("Não foi possível listar cidades para verificação de expiração: %s", e)
                return
            if not cities:
                logging.info("✅ Verificação concluída: Nenhuma cidade cadastrada")
                return

            updated_count = 0
            expired_sessions_count = 0
            current_utc = datetime.utcnow()

            for (city_id,) in cities:
                city_updated = 0
                city_sessions_expired = 0
                try:
                    schema = city_id_to_schema_name(str(city_id))
                    set_search_path(schema)
                except Exception as e:
                    logging.warning("Schema %s: %s", city_id, e)
                    continue
                try:
                    class_tests = ClassTest.query.filter(
                        ClassTest.status.in_(['agendada', 'em_andamento']),
                        ClassTest.expiration.isnot(None)
                    ).all()
                except ProgrammingError as e:
                    if 'class_test' in str(e).lower() and 'does not exist' in str(e).lower():
                        continue
                    raise

                for class_test in class_tests:
                    try:
                        # Obter timezone da aplicação ou usar UTC como padrão
                        if class_test.timezone:
                            try:
                                target_tz = pytz.timezone(class_test.timezone)
                                current_time = datetime.now(target_tz)
                            except pytz.exceptions.UnknownTimeZoneError:
                                logging.warning(f"Timezone inválido: {class_test.timezone}, usando UTC")
                                current_time = current_utc
                        else:
                            current_time = current_utc

                        # Converter expiration para datetime
                        expiration_dt = dateutil.parser.parse(class_test.expiration)
                        if expiration_dt.tzinfo is None:
                            if class_test.timezone:
                                try:
                                    target_tz = pytz.timezone(class_test.timezone)
                                    expiration_dt = expiration_dt.replace(tzinfo=target_tz)
                                except pytz.exceptions.UnknownTimeZoneError:
                                    expiration_dt = expiration_dt.replace(tzinfo=current_time.tzinfo)
                            else:
                                expiration_dt = expiration_dt.replace(tzinfo=current_time.tzinfo)

                        # Verificar se expirou
                        if current_time > expiration_dt:
                            # Atualizar status do ClassTest
                            if class_test.status != 'concluida':
                                class_test.status = 'concluida'
                                class_test.updated_at = datetime.utcnow()
                                updated_count += 1
                                city_updated += 1

                                logging.info(
                                    f"Avaliação {class_test.test_id} (ClassTest {class_test.id}) expirada. "
                                    f"Data expiração: {expiration_dt}, Data atual: {current_time}"
                                )

                                # Expirar todas as sessões ativas desta avaliação
                                active_sessions = TestSession.query.filter_by(
                                    test_id=class_test.test_id,
                                    status='em_andamento'
                                ).all()

                                for session in active_sessions:
                                    session.status = 'expirada'
                                    session.submitted_at = datetime.utcnow()
                                    expired_sessions_count += 1
                                    city_sessions_expired += 1

                                if active_sessions:
                                    logging.info(
                                        f"Expiradas {len(active_sessions)} sessões ativas da avaliação {class_test.test_id}"
                                    )
                    except Exception as e:
                        logging.error(
                            f"Erro ao processar ClassTest {class_test.id} (test_id: {class_test.test_id}): {str(e)}",
                            exc_info=True
                        )
                        continue

                if city_updated > 0 or city_sessions_expired > 0:
                    try:
                        db.session.commit()
                    except Exception as commit_err:
                        logging.warning("Commit em %s: %s", schema, commit_err)
                        db.session.rollback()
                logging.info(
                    f"✅ Verificação concluída: {updated_count} avaliações expiradas atualizadas, "
                    f"{expired_sessions_count} sessões expiradas"
                )
            else:
                logging.info("✅ Verificação concluída: Nenhuma avaliação expirada encontrada")
                
        except Exception as e:
            logging.error(
                f"Erro na verificação de avaliações expiradas: {str(e)}",
                exc_info=True
            )
            db.session.rollback()


def start_scheduler(app=None):
    """
    Inicia o scheduler de tarefas agendadas
    
    Args:
        app: Instância da aplicação Flask (opcional, mas recomendado)
    """
    try:
        # Verificar se o scheduler já está rodando
        if scheduler.running:
            logging.warning("Scheduler já está em execução")
            return
        
        # Criar wrapper que passa a app para a função
        def job_wrapper():
            check_expired_evaluations(app)
        
        # Adicionar job para verificar avaliações expiradas a cada 5 minutos
        scheduler.add_job(
            job_wrapper,  # Usar wrapper ao invés da função diretamente
            trigger=CronTrigger(minute='*/5'),  # A cada 5 minutos
            id='check_expired_evaluations',
            name='Verificar avaliações expiradas',
            replace_existing=True,
            max_instances=1  # Garantir que apenas uma instância rode por vez
        )
        
        scheduler.start()
        logging.info("✅ Scheduler de tarefas agendadas iniciado com sucesso")
        logging.info("   - Verificação de avaliações expiradas: A cada 5 minutos")
        
    except Exception as e:
        logging.error(f"Erro ao iniciar scheduler: {str(e)}", exc_info=True)
        raise


def stop_scheduler():
    """Para o scheduler de tarefas agendadas"""
    try:
        if scheduler.running:
            scheduler.shutdown(wait=True)
            logging.info("✅ Scheduler de tarefas agendadas parado com sucesso")
        else:
            logging.info("Scheduler não está em execução")
    except Exception as e:
        logging.error(f"Erro ao parar scheduler: {str(e)}", exc_info=True)


def get_scheduler_status():
    """Retorna o status atual do scheduler"""
    return {
        "running": scheduler.running,
        "jobs": [
            {
                "id": job.id,
                "name": job.name,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None
            }
            for job in scheduler.get_jobs()
        ]
    }

