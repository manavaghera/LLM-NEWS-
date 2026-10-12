FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (see .dockerignore: no frontend, tests, local venv or generated news)
COPY . .

# Create non-root user; cache/ holds generated translations, digests and audio
RUN adduser --disabled-password --gecos '' appuser && \
    mkdir -p /app/cache && \
    chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Run the application
# Import any operational data left by a pre-PostgreSQL deployment before accepting traffic.
# The migration is idempotent and exits immediately when there are no legacy SQLite files.
CMD ["sh", "-c", "python scripts/migrate_sqlite_to_postgres.py --cache-dir /app/cache --if-present && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
