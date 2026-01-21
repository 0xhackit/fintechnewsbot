# Multi-stage build for FastAPI backend
FROM python:3.12-slim as backend

WORKDIR /app

# Copy backend requirements and install
COPY api/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY api/ ./api/
COPY out/ ./out/
COPY config.json ./

# Expose backend port
EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
