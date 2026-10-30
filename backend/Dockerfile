FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.lock.txt .
COPY wheelhouse /tmp/wheelhouse
RUN if find /tmp/wheelhouse -name '*.whl' | grep -q .; then \
      pip install --no-index --find-links=/tmp/wheelhouse --require-hashes -r requirements.lock.txt; \
    else pip install --no-cache-dir --require-hashes -r requirements.lock.txt; fi

RUN groupadd --system caregap && useradd --system --gid caregap caregap
COPY --chown=caregap:caregap . .
RUN mkdir -p /app/storage/documents && chown -R caregap:caregap /app/storage
USER caregap

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]

