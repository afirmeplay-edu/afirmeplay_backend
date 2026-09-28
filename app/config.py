import os
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv('app/.env')

class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Cada processo (worker do Gunicorn ou do Celery) tem o próprio pool.
    # O Gunicorn síncrono atende 1 request por worker, então o pool não precisa
    # ser grande: 4 workers da API + 4 do Celery, com pool 2 + overflow 2,
    # ficam em ~16 conexões paradas e no máximo ~32 num pico por ambiente.
    # O servidor está em max_connections=100 e dev/prod compartilham esse teto.
    # pool_size 20 + overflow 40 (até 60 por processo) lotava o Postgres sozinho.
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 2,
        'pool_recycle': 3600,  # Reciclar conexões a cada 1 hora (evitar timeout)
        'pool_pre_ping': True,  # Verificar conexões antes de usar
        'max_overflow': 2,
    }
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_key")

    # Postgres: proteções contra "idle in transaction" e queries eternas.
    #
    # Esses timeouts são aplicados por conexão (via event listener no create_app),
    # então também protegem jobs/scheduler/celery que usem o mesmo pool.
    #
    # Valores hardcoded (sem env):
    # - idle_in_transaction_session_timeout: 10min
    #     Antes era 60s. Era agressivo demais para tasks Celery longas (geração de
    #     PDFs, formulários físicos, recálculos) que mantêm sessão aberta entre
    #     operações de SQL. O Postgres derrubava a conexão e a próxima query
    #     estourava com "server closed the connection unexpectedly".
    #     10min cobre o uso real de Celery e ainda mantém proteção contra
    #     transações "perdidas". Para HTTP, o teardown do request já fecha a
    #     sessão muito antes desse limite.
    # - statement_timeout: 5min
    # - idle_session_timeout: 10min
    #     Encerra sessão parada fora de transação (pool ocioso, psql esquecido,
    #     cliente que caiu sem fechar). Diferente do timeout de "idle in
    #     transaction", que não cobre o estado "idle" do pool.
    #     Tasks longas fazem commit antes do trabalho de CPU e devolvem a
    #     conexão ao pool; o pool_pre_ping abre outra se o Postgres já a encerrou.
    PG_IDLE_IN_TX_SESSION_TIMEOUT_MS = 600_000
    PG_IDLE_SESSION_TIMEOUT_MS = 600_000
    PG_STATEMENT_TIMEOUT_MS = 300_000
    
    # Configurações do SendGrid
    SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
    SENDGRID_FROM_EMAIL = os.getenv("SENDGRID_FROM_EMAIL", "noreply@innovaplay.com")
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
    
    # Configurações de reset de senha
    PASSWORD_RESET_TOKEN_EXPIRY = 3600  # 1 hora em segundos

    # OMR / cartão-resposta: salva imagens em debug_corrections_new/ quando True
    # export OMR_DEBUG=1  (ou true, yes, on)
    OMR_DEBUG = os.getenv("OMR_DEBUG", "").strip().lower() in ("1", "true", "yes", "on")
