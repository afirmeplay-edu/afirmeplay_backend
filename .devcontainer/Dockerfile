FROM mcr.microsoft.com/devcontainers/python:1-3.11-bookworm

ENV TZ=UTC \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

USER root

RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Libs nativas que no Windows costumam falhar: WeasyPrint, OpenCV, pyzbar, pdf2image
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    git \
    curl \
    poppler-utils \
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
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libzbar0 \
    fonts-dejavu-core \
    librsvg2-common \
    shared-mime-info \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspaces/afirmeplay_backend

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

USER vscode
