# Cloud Run Job image for FMI validator

FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ../shared /app/validators/shared
COPY . /app/validators/fmi

WORKDIR /app/validators/fmi
CMD ["python", "main.py"]
