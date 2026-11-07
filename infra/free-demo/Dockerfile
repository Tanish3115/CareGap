FROM node:22-bookworm-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
ENV NEXT_TELEMETRY_DISABLED=1 API_PROXY_TARGET=http://127.0.0.1:8000
RUN npm run build

FROM python:3.12-slim-bookworm AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends libstdc++6 tesseract-ocr tesseract-ocr-eng poppler-utils fonts-dejavu-core && rm -rf /var/lib/apt/lists/*
COPY --from=frontend /usr/local/bin/node /usr/local/bin/node
WORKDIR /opt/caregap/backend
COPY backend/requirements.lock.txt ./
RUN pip install --no-cache-dir --require-hashes -r requirements.lock.txt
COPY backend/app ./app
COPY backend/migrations ./migrations
COPY backend/alembic.ini ./
COPY --from=frontend /build/.next/standalone /opt/caregap/frontend/
COPY --from=frontend /build/.next/static /opt/caregap/frontend/.next/static/
COPY infra/free-demo/start.py /opt/caregap/start.py
RUN useradd --system --uid 10001 caregap-demo && chown -R caregap-demo /opt/caregap
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PYTHONUNBUFFERED=1 PORT=10000 MALLOC_ARENA_MAX=2
USER caregap-demo
EXPOSE 10000
CMD ["python", "/opt/caregap/start.py"]
