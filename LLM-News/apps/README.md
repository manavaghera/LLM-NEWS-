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
`PIPELINE_DAILY_CALL_LIMIT`, `PIPELINE_MONTHLY_CALL_LIMIT`, `PUBLIC_BASE_URL` (for share previews and RSS when public),
`ALLOWED_ORIGINS` and `ADMIN_TOKEN`.

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

Generated translations, digests and audio are written to `cache/` (a Docker volume), because `static/`
is mounted read-only in Docker. Docker stores reports, corrections, analytics, budgets and updater leases
in PostgreSQL; local development keeps those records in SQLite unless `DATABASE_URL` is set.

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

## News updates every hour

`../pipeline/daily_update.py --interval 60` keeps the site current: the first run of a day writes the
edition, then every hour it adds up to 2 stories per category about events the edition doesn't cover
yet (follow-ups to covered stories are skipped). The front page shows "Updated 2:05 PM · next update
in 34 min", marks the new stories, puts a story more outlets cover at the top, and reloads by itself.

```bash
cd .. && python pipeline/daily_update.py --interval 60                  # keep running in a terminal
cd .. && python pipeline/daily_update.py --interval 60 --print-task     # or a Windows scheduled task
docker compose --profile updates up -d --build                          # or Docker: the "updater" service
```

The default desks are AI Models, World & Society, Technology, Science, Business, Startups,
Cybersecurity, Health, Climate, Space, Sports, Gaming and Entertainment. Each update makes about
1 AI call per category plus 2 per new story (fact-check and comparison), so a run where every desk
publishes two stories can reach ~65 calls. Pass `--categories ai_models,tech,cybersecurity` to the
updater to limit coverage and cost. `UPDATE_MINUTES` in `../.env` sets the Docker interval; set `TZ` (e.g.
`Asia/Kolkata`) so editions change at your midnight. NVIDIA's free key is for testing only: a public
site needs a paid provider.

## Put it online

`docker-compose.prod.yml` adds [Caddy](https://caddyserver.com) in front of the site. It gets a free
HTTPS certificate from Let's Encrypt, renews it, and redirects http to https.

1. A Linux server with Docker, ports 80 and 443 open, and a DNS `A` record pointing your domain at it.
2. In `../.env`: `DOMAIN=news.example.com`, an AI key, a random `POSTGRES_PASSWORD` and `ADMIN_TOKEN`
   of at least 24 characters. `PUBLIC_BASE_URL` is set to `https://$DOMAIN` for you.
3. Copy the news (`static/`) to the server, or run the news script there.
4. Start it, with hourly news updates (see below):

   ```bash
   docker compose --env-file ../.env -f docker-compose.yml -f docker-compose.prod.yml --profile updates up -d --build
   ```

Only Caddy is reachable from outside; the backend counts visitors (for rate limits) from the address
Caddy saw (`PROXY_COUNT=2`). Keep `AI_DAILY_CALL_LIMIT` and `AI_VISITOR_DAILY_LIMIT` set so a busy day,
or one visitor, can't run up the AI bill. `PIPELINE_DAILY_CALL_LIMIT` caps attempted news-generation calls
across processes and restarts (default 200/day); change it in the owner dashboard. Calls have different
prices, so set a currency spending limit with the AI provider too. Also set
`ALLOWED_ORIGINS=https://your.domain`, `ADMIN_TOKEN` and
`CONTACT_EMAIL` (shown on the About and Privacy pages), and keep only the keys you pay for: every key in
`.env` appears in the chat's model menu.
To try it on your own computer first, use `DOMAIN=localhost` (Caddy then uses its own local certificate,
which browsers warn about).

nginx serves article images and audio straight from `static/` and sends a strict Content-Security-Policy
(`web/security-headers.conf`); logs are capped at 3 × 10 MB per service. Back up nightly:

```bash
./scripts/backup.sh /var/backups/newssense production  # news, generated cache and PostgreSQL
```

The script's header has the cron line and how to restore. Copy the backups off the server as well.

## Owner dashboard and corrections

Set a random `ADMIN_TOKEN` of at least 24 characters in `../.env`, restart the backend and open `/admin`.
The token is exchanged for a signed, HTTP-only, same-site session that expires after eight hours. The
dashboard shows update failures, stale news, feed health, held-back drafts, recent runs, aggregate route
errors and model/token usage. Daily and monthly pipeline limits persist in PostgreSQL in Docker (SQLite
in local development) and are shared with the updater; 0 disables a limit. Website AI requests retain
their separate existing limits.

Review reader reports, save private resolutions, dismiss or reopen reports, and publish dated public
correction notes. Public article pages show correction history without exposing reader messages.

## Reader library and evidence

Article pages show literal source excerpts beside checked claims when the pipeline records them.
Older articles retain their original numbered citations. Excerpts are checked against the fetched
source text; AI verification can still make mistakes.

Readers can follow topics and individual stories to receive alerts in the site while it is open.
Saved stories and follows stay in browser storage. The Saved page exports and imports a validated
JSON library backup, merging duplicates so readers can move their library between browsers.

## Reader reports API

Reports from the article page's "Report a problem" button are stored in PostgreSQL in Docker and
`cache/reports.db` during local development, without personal data. Set `ADMIN_TOKEN` in `../.env` and read them with:

```bash
curl -H "X-Admin-Token: <your token>" http://localhost:3000/api/reports
```
