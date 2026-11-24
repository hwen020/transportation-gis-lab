FROM node:22-bookworm-slim AS frontend-build
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run typecheck && npm run build

FROM python:3.12-slim-bookworm
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PORT=10000 LAB_DB=/tmp/lab.sqlite3
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY lab/ ./lab/
COPY prototype/ ./prototype/
COPY --from=frontend-build /build/dist ./frontend/dist
USER 10001
CMD ["sh", "-c", "exec uvicorn lab.api:app --host 0.0.0.0 --port \"$PORT\""]
