import os
import logging
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content, HtmlContent
from flask import current_app
from datetime import datetime, timedelta
import secrets
import string
from dotenv import load_dotenv

class EmailService:
    def __init__(self):
        # Carregar variáveis de ambiente diretamente
        load_dotenv('app/.env')
        
        # Tentar obter do Flask primeiro, depois do .env
        self.api_key = current_app.config.get('SENDGRID_API_KEY') or os.getenv('SENDGRID_API_KEY')
        self.from_email = current_app.config.get('SENDGRID_FROM_EMAIL') or os.getenv('SENDGRID_FROM_EMAIL')
        self.frontend_url = current_app.config.get('FRONTEND_URL') or os.getenv('FRONTEND_URL')
        
        if not self.api_key:
            logging.warning("SENDGRID_API_KEY não configurada")
            print("⚠️  SENDGRID_API_KEY não configurada no EmailService")
        
        if not self.from_email:
            logging.warning("SENDGRID_FROM_EMAIL não configurado")
            print("⚠️  SENDGRID_FROM_EMAIL não configurado no EmailService")
    
    def generate_reset_token(self):
        """Gera um token seguro para reset de senha"""
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(32))
    
    def send_password_reset_email(self, user_email, user_name, reset_token):
        """Envia email de reset de senha"""
        if not self.api_key:
            logging.error("SendGrid API key não configurada")
            return False
        
        try:
            reset_url = f"{self.frontend_url}/reset-password?token={reset_token}"
            
            # Template HTML do email
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>Redefinição de Senha - InnovaPlay</title>
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        line-height: 1.6;
                        color: #333;
                        max-width: 600px;
                        margin: 0 auto;
                        padding: 20px;
                    }}
                    .header {{
                        background-color: #4CAF50;
                        color: white;
                        padding: 20px;
                        text-align: center;
                        border-radius: 5px 5px 0 0;
                    }}
                    .content {{
                        background-color: #f9f9f9;
                        padding: 20px;
                        border-radius: 0 0 5px 5px;
                    }}
                    .button {{
                        display: inline-block;
                        background-color: #4CAF50;
                        color: white;
                        padding: 12px 24px;
                        text-decoration: none;
                        border-radius: 5px;
                        margin: 20px 0;
                    }}
                    .footer {{
                        margin-top: 20px;
                        padding-top: 20px;
                        border-top: 1px solid #ddd;
                        font-size: 12px;
                        color: #666;
                    }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>InnovaPlay</h1>
                    <h2>Redefinição de Senha</h2>
                </div>
                <div class="content">
                    <p>Olá <strong>{user_name}</strong>,</p>
                    <p>Recebemos uma solicitação para redefinir sua senha na plataforma InnovaPlay.</p>
                    <p>Clique no botão abaixo para criar uma nova senha:</p>
                    
                    <a href="{reset_url}" class="button">Redefinir Senha</a>
                    
                    <p>Se o botão não funcionar, copie e cole o link abaixo no seu navegador:</p>
                    <p style="word-break: break-all; color: #666;">{reset_url}</p>
                    
                    <p><strong>Importante:</strong></p>
                    <ul>
                        <li>Este link é válido por 1 hora</li>
                        <li>Se você não solicitou esta redefinição, ignore este email</li>
                        <li>Nunca compartilhe este link com outras pessoas</li>
                    </ul>
                </div>
                <div class="footer">
                    <p>Este é um email automático, não responda a esta mensagem.</p>
                    <p>Se tiver dúvidas, entre em contato com o suporte.</p>
                </div>
            </body>
            </html>
            """
            
            # Configurar email
            from_email = Email(self.from_email)
            to_email = To(user_email)
            subject = "Redefinição de Senha - InnovaPlay"
            html_content = HtmlContent(html_content)
            
            mail = Mail(from_email, to_email, subject, html_content)
            
            # Enviar email
            sg = SendGridAPIClient(api_key=self.api_key)
            response = sg.send(mail)
            
            if response.status_code == 202:
                logging.info(f"Email de reset enviado com sucesso para {user_email}")
                return True
            else:
                logging.error(f"Erro ao enviar email: {response.status_code} - {response.body}")
                return False
                
        except Exception as e:
            logging.error(f"Erro ao enviar email de reset: {str(e)}")
            return False
    
    def send_password_changed_email(self, user_email, user_name):
        """Envia email de confirmação de alteração de senha"""
        if not self.api_key:
            logging.error("SendGrid API key não configurada")
            return False
        
        try:
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>Senha Alterada - InnovaPlay</title>
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        line-height: 1.6;
                        color: #333;
                        max-width: 600px;
                        margin: 0 auto;
                        padding: 20px;
                    }}
                    .header {{
                        background-color: #4CAF50;
                        color: white;
                        padding: 20px;
                        text-align: center;
                        border-radius: 5px 5px 0 0;
                    }}
                    .content {{
                        background-color: #f9f9f9;
                        padding: 20px;
                        border-radius: 0 0 5px 5px;
                    }}
                    .footer {{
                        margin-top: 20px;
                        padding-top: 20px;
                        border-top: 1px solid #ddd;
                        font-size: 12px;
                        color: #666;
                    }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>InnovaPlay</h1>
                    <h2>Senha Alterada com Sucesso</h2>
                </div>
                <div class="content">
                    <p>Olá <strong>{user_name}</strong>,</p>
                    <p>Sua senha foi alterada com sucesso na plataforma InnovaPlay.</p>
                    <p>Se você não realizou esta alteração, entre em contato conosco imediatamente.</p>
                </div>
                <div class="footer">
                    <p>Este é um email automático, não responda a esta mensagem.</p>
                    <p>Se tiver dúvidas, entre em contato com o suporte.</p>
                </div>
            </body>
            </html>
            """
            
            from_email = Email(self.from_email)
            to_email = To(user_email)
            subject = "Senha Alterada - InnovaPlay"
            html_content = HtmlContent(html_content)
            
            mail = Mail(from_email, to_email, subject, html_content)
            
            sg = SendGridAPIClient(api_key=self.api_key)
            response = sg.send(mail)
            
            if response.status_code == 202:
                logging.info(f"Email de confirmação enviado com sucesso para {user_email}")
                return True
            else:
                logging.error(f"Erro ao enviar email de confirmação: {response.status_code}")
                return False
                
        except Exception as e:
            logging.error(f"Erro ao enviar email de confirmação: {str(e)}")
            return False 