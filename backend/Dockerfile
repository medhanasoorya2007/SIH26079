FROM python:3.11-slim
WORKDIR /app/backend
RUN pip install --no-cache-dir uv
COPY backend/pyproject.toml backend/uv.lock backend/.python-version ./
RUN uv sync --frozen --no-dev --extra full
COPY backend/ ./
COPY data/sample /app/data/sample
ENV BUSTGUARD_DATA_DIR=/app/data BUSTGUARD_CORS_ORIGINS=http://localhost:3000
EXPOSE 8000
CMD ["uv", "run", "--no-sync", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
