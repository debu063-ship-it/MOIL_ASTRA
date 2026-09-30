# MOIL ASTRA — single-service image: FastAPI serves both the REST API and the
# built React dashboard (multi-stage so the heavy frontend build doesn't
# bloat the runtime image).
FROM node:20-bookworm-slim AS frontend
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app

# matplotlib needs a libGL runtime even headless; curl is for healthchecks.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend ./backend
COPY data ./data
COPY outputs/models_v3 ./outputs/models_v3
COPY --from=frontend /app/dist ./frontend/dist

ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
