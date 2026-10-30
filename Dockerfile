FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/
COPY avaliacao/ ./avaliacao/

RUN pip install --no-cache-dir . && rm -rf /app/build

RUN useradd -m -u 10001 app && mkdir -p /app/data && chown -R app:app /app
ENV ESTOQUE_DB_PATH=/app/data/estoque.db
ENV PYTHONUNBUFFERED=1

RUN python -m estoque_ia.seed --db /app/data/estoque.db --force
RUN chown -R app:app /app/data

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/saude', timeout=5).read()"

CMD ["uvicorn", "estoque_ia.api:app", "--host", "0.0.0.0", "--port", "8000"]
