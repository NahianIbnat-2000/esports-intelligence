FROM python:3.13-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends make && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend backend
COPY pipelines pipelines
COPY machine_learning machine_learning
COPY analytics analytics
COPY Makefile .
RUN mkdir -p data/raw data/intermediate data/processed data/reports
EXPOSE 8000
CMD ["sh", "-c", "cd backend && python -m alembic upgrade head && cd .. && uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
