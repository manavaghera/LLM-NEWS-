# News updates for a hosted site: pipeline/daily_update.py --interval, as the "updater" service in
# apps/docker-compose.yml (profile "updates"). Build context: LLM-News/, limited by Dockerfile.dockerignore.
FROM python:3.11-slim

WORKDIR /app
# tzdata: editions are dated in TZ from .env (e.g. TZ=Asia/Kolkata), not always UTC
RUN apt-get update && apt-get install -y --no-install-recommends tzdata && rm -rf /var/lib/apt/lists/*

COPY requirements/quick_news.txt requirements/quick_news.txt
RUN pip install --no-cache-dir -r requirements/quick_news.txt

COPY llm_client.py ./
COPY apps/app/core/providers.py apps/app/core/providers.py
COPY pipeline/ pipeline/

# uid 1000 is usually the owner of the apps/static folder it writes into
RUN useradd --create-home --uid 1000 appuser && mkdir -p apps/static && chown appuser apps/static
USER appuser

ENV PYTHONUNBUFFERED=1 UPDATE_MINUTES=60
CMD ["sh", "-c", "exec python pipeline/daily_update.py --interval \"${UPDATE_MINUTES:-60}\""]
