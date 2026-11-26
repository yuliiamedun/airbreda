FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ingest_air.py log_utils.py health.py ./

CMD ["python", "ingest_air.py"]