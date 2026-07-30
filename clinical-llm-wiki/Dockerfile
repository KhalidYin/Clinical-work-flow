FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml alembic.ini ./
COPY service/__init__.py ./service/__init__.py
RUN python -m pip install --no-cache-dir .

COPY service ./service
COPY schemas ./schemas
RUN python -m pip install --no-deps .

CMD ["python", "-m", "service.platform_api.main"]
