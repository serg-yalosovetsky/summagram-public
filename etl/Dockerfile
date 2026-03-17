# ETL Service Dockerfile
FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install runtime libs
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY etl/requirements.txt requirements.txt

# Install dependencies
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip --default-timeout=300 && \
    pip install --default-timeout=300 -r requirements.txt

# Copy application code into /app/etl (package structure)
COPY *.py /app/
COPY services/ /app/services/
COPY shared/ /app/shared/
COPY etl/ /app/etl/

ENV PYTHONPATH=/app:/app/etl

# Expose Port
EXPOSE 8000

# Healthcheck
HEALTHCHECK CMD curl --fail http://localhost:8000/health || exit 1

# Run FastAPI
CMD ["uvicorn", "etl.main:app", "--host", "0.0.0.0", "--port", "8000"]
