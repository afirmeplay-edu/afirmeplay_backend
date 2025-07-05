FROM python:3.13.5-slim

WORKDIR /code
COPY . .

RUN pip install --no-cache-dir --upgrade -r requirements.txt

EXPOSE 5000

CMD ["python", "run.py"]
