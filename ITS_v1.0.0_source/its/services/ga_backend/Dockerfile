FROM python:3.12-slim

ENV POETRY_VERSION=2.1.4 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

RUN pip install --no-cache-dir "poetry==${POETRY_VERSION}"

COPY pyproject.toml poetry.lock poetry.toml ./
RUN poetry config virtualenvs.create false \
    && poetry install --only main --no-interaction --no-ansi --no-root

COPY its ./its

EXPOSE 8000

CMD ["uvicorn", "its.services.ga_backend.app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]

