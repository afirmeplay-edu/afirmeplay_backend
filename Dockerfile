FROM python:3.13.5-slim

# Configurar timezone
ENV TZ=UTC
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Instalar dependências do sistema necessárias para opencv e outros pacotes
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /code

# Copiar arquivos antes do pip install (melhor cache)
COPY requirements.txt .

# Instalar dependências Python
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# Copiar resto do código
COPY . .

EXPOSE 5000

CMD ["python", "run.py"]
