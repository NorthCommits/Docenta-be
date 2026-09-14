# Docenta backend
FROM python:3.10-slim

# Cleaner, more predictable Python behaviour inside containers
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies first so this layer is cached until requirements change
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy the application code
COPY app ./app

# Run as a non-root user for safety
RUN useradd --create-home appuser
USER appuser

# Render provides $PORT at runtime; default to 8000 for local runs
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]