FROM python:3.11-bullseye

RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    g++ \
    libcairo2 \
    pango1.0-tools \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libpango1.0-dev \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    libfreetype6-dev \
    libjpeg-dev \
    zlib1g-dev \
    libpng-dev \
    liblcms2-dev \
    libwebp-dev \
    libtiff-dev \
    libopenjp2-7-dev \
    libharfbuzz-dev \
    libfribidi-dev \
    libxcb1-dev \
    libgl1 \
    libzbar0 \
    libglib2.0-0 \
    fonts-dejavu-core \
    librsvg2-common \
    shared-mime-info \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV TZ=UTC
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

WORKDIR /code
COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["gunicorn","--bind", "0.0.0.0:5000","--workers", "2","--threads", "2","--timeout", "120","--graceful-timeout", "30","--max-requests", "500","--max-requests-jitter", "50","--preload","run:app"]