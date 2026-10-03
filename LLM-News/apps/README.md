# NewsSense web app

FastAPI backend (`app/`) and React frontend (`web/`). It shows the articles in `static/articles/`, written
by `../pipeline/quick_news.py` (or the full pipeline via `../migrate.py`).

## Run it

**Docker** (from this folder): `docker compose up --build`, then open http://localhost:3000.
nginx serves the frontend and forwards `/api`, `/static`, `/share` and `/feed.xml` to the backend.

**Without Docker** (Python 3.11, Node 22), two terminals:

```bash
# backend
python -m venv .venv
.venv/bin/pip install -r requirements.txt        # Windows: .venv\Scripts\pip
.venv/bin/python -m uvicorn app.main:app --port 8000

# frontend
cd web && npm ci && npm run dev                   # http://localhost:5173 (proxies to port 8000)
```

Settings come from `../.env` (template: `../.env.example`): an AI key (`OPENROUTER_API_KEY`, `NVIDIA_API_KEY`,
`OPENAI_API_KEY`, ...), optional model overrides, `AI_RATE_LIMIT`, `AI_DAILY_CALL_LIMIT`,
`PUBLIC_BASE_URL` (for share previews and RSS when public), `ALLOWED_ORIGINS` and `ADMIN_TOKEN`.

## Structure

```
app/
├── main.py                  # app, CORS, static files (path-traversal safe), error handlers
├── core/
│   ├── config.py            # settings from ../.env
│   ├── providers.py         # AI providers and models (shared with ../llm_client.py)
│   └── limits.py            # per-visitor rate limit and daily AI-call cap
├── api/endpoints/           # news, chat, digest, translate, audio, trends, reports, config, health,
│                            # public (share previews, RSS)
└── services/                # news, archive (search, earlier coverage), chat, llm, digest,
                             # translation, audio, trends, topics, reports
web/src/
├── pages/                   # Home, Article, Digest, Trends, Search, Saved
├── components/              # article, chat, news, trends, layout, ui
├── api/                     # typed API client, queries, chat stream reader
└── lib/                     # formatting, safe citation/markdown parsing, saved stories
tests/                       # backend tests
```

Generated translations, digests, audio and reader reports are written to `cache/` (a Docker volume),
because `static/` is mounted read-only in Docker.

## Tests

```bash
.venv/bin/python -m pytest tests                  # backend
cd web && npm run lint && npm test && npm run build
```

Browser tests (Playwright) start the backend on the fixed news in `web/e2e/fixtures/` with no AI key,
start the frontend, and click through the site in Chromium:

```bash
cd web
npx playwright install chromium                   # once
PYTHON=../.venv/bin/python npm run test:e2e       # Windows: $env:PYTHON='../.venv/Scripts/python'
```

## Put it online

`docker-compose.prod.yml` adds [Caddy](https://caddyserver.com) in front of the site. It gets a free
HTTPS certificate from Let's Encrypt, renews it, and redirects http to https.

1. A Linux server with Docker, ports 80 and 443 open, and a DNS `A` record pointing your domain at it.
2. In `../.env`: `DOMAIN=news.example.com`, an AI key, and `ADMIN_TOKEN` if you want to read reader
   reports. `PUBLIC_BASE_URL` is set to `https://$DOMAIN` for you.
3. Copy the news (`static/`) to the server, or run the news script there.
4. Start it:

   ```bash
   docker compose --env-file ../.env -f docker-compose.yml -f docker-compose.prod.yml up -d --build
   ```

Only Caddy is reachable from outside; the backend counts visitors (for rate limits) from the address
Caddy saw (`PROXY_COUNT=2`). Keep `AI_DAILY_CALL_LIMIT` set so a busy day can't run up the AI bill.
To try it on your own computer first, use `DOMAIN=localhost` (Caddy then uses its own local certificate,
which browsers warn about).

## Reader reports

Reports from the article page's "Report a problem" button are stored in `cache/reports.db`, without any
personal data. Set `ADMIN_TOKEN` in `../.env` and read them with:

```bash
curl -H "X-Admin-Token: <your token>" http://localhost:3000/api/reports
```
