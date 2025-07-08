FROM python:3.11-slim

# Define o diretório de trabalho no container
WORKDIR /app

# Instala dependências do sistema
RUN apt-get update && apt-get install -y gcc

# Copia os arquivos de dependências
COPY app/requirements.txt .

# Instala as dependências do projeto
RUN pip install --no-cache-dir -r requirements.txt

# Copia o restante da aplicação
COPY app/ .

# Expõe a porta usada pelo Flask (ajuste conforme necessário)
EXPOSE 5000

# Define a variável de ambiente para o Flask
ENV FLASK_APP=run.py
ENV FLASK_RUN_HOST=0.0.0.0

# Comando para iniciar a aplicação
CMD ["flask", "run"]
