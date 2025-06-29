import os
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv('app/.env')

class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_key")
    
    # Configurações do SendGrid
    SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
    SENDGRID_FROM_EMAIL = os.getenv("SENDGRID_FROM_EMAIL", "noreply@innovaplay.com")
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
    
    # Configurações de reset de senha
    PASSWORD_RESET_TOKEN_EXPIRY = 3600  # 1 hora em segundos
    