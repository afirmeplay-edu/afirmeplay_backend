FROM python:3.13.5-slim

# Configurar timezone para usar o timezone local do sistema
ENV TZ=UTC
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

WORKDIR /code
COPY . .

RUN pip install --no-cache-dir --upgrade -r requirements.txt

EXPOSE 5000

CMD ["python", "run.py"]
