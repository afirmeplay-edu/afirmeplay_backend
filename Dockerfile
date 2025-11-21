FROM python:3.12-slim

# Instalar dependências de sistema necessárias pro WeasyPrint
RUN apt-get update && apt-get install -y \
    build-essential \
    libcairo2 \
    pango1.0-tools \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libpango1.0-dev \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    libfreetype-dev \
    shared-mime-info \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependências do sistema necessárias para compilar pacotes Python
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    g++ \
    libffi-dev \
    libssl-dev \
    libjpeg-dev \
    zlib1g-dev \
    libpng-dev \
    libfreetype6-dev \
    liblcms2-dev \
    libwebp-dev \
    libtiff5-dev \
    libopenjp2-7-dev \
    libharfbuzz-dev \
    libfribidi-dev \
    libxcb1-dev \
    && rm -rf /var/lib/apt/lists/*

# Configurar timezone para usar o timezone local do sistema
ENV TZ=UTC
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

WORKDIR /code
COPY . .

# Instalar dependências Python
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --upgrade -r requirements.txt

EXPOSE 5000

CMD ["python", "run.py"]
