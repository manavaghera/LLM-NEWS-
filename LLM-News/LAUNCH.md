# NewsSense launch runbook

## Environments

Use separate `.env.staging` and `.env.production` files, Compose project names and news directories. Never copy production API keys into staging. The deployment scripts store generated data under `/opt/newssense/data/staging/static` and `/opt/newssense/data/production/static`, outside the Git checkout. The first free deployment target is documented in [deployment/oracle-cloud/README.md](deployment/oracle-cloud/README.md).

```bash
cd apps
APP_ENV_FILE=../.env.staging docker compose -p newssense-staging --env-file ../.env.staging -f docker-compose.yml -f docker-compose.staging.yml --profile updates up -d --build
APP_ENV_FILE=../.env.production docker compose -p newssense-production --env-file ../.env.production -f docker-compose.yml -f docker-compose.prod.yml --profile updates up -d --build
```

Both stacks run the frontend, backend and hourly updater without a personal computer. Caddy obtains HTTPS certificates. Production Compose restricts browser origins and host headers to `DOMAIN`.

Before promotion, check `/api/health/ready`. It returns HTTP 503 when news is stale or HTTPS, CORS, host allow-list or the admin secret is unsafe. Check the owner dashboard for the last successful update, feed failures, held stories, API errors, slow routes and remaining daily/monthly generation allowance.

## Required secrets

Set one paid AI provider key, `DOMAIN`, `PUBLIC_BASE_URL`, a random `ADMIN_TOKEN` of at least 24 characters, a random `POSTGRES_PASSWORD` of at least 24 characters, `CONTACT_EMAIL`, `CONTACT_ADDRESS`, and provider-side currency limits. Set `ALERT_WEBHOOK_URL` to receive updater failure alerts. Keep `.env.production` off Git and store it in the hosting provider's secret manager.

## Promotion

1. Deploy the candidate to staging and run backend, frontend and Playwright checks.
2. Run one updater cycle and confirm the timestamp, evidence, images, audio and held-story queue.
3. Test admin login, correction publication and logout.
4. Back up production, deploy the same image revisions, then check `/api/health/ready` and the home page.
5. Keep the previous image revision available for rollback.

## Backups and recovery

Run `apps/scripts/backup.sh` nightly. It creates a PostgreSQL custom-format dump plus news and generated-cache archives, validates every article and legacy SQLite file, validates the database dump with `pg_restore`, writes SHA-256 checksums and can upload to S3 or Cloudflare R2. Set `BACKUP_ENCRYPTION_PASSPHRASE` so off-site files are encrypted, then set `BACKUP_S3_URI` and optionally `BACKUP_S3_ENDPOINT`. Once per month, restore into a new staging Compose project and open several archived editions. `apps/scripts/verify-backup.sh` performs the same non-destructive checks manually.

Docker deployments use PostgreSQL for reports, corrections, generation usage, aggregate analytics and updater coordination. On its first start, the backend imports missing records from the previous SQLite files in the cache volume before it becomes healthy. Local development without `DATABASE_URL` continues to use SQLite. The import can also be run explicitly with `python apps/scripts/migrate_sqlite_to_postgres.py --cache-dir apps/cache`.

For server-replacement-safe editions and media, configure `OBJECT_STORAGE_BUCKET` plus the access key and secret in each environment. Set `OBJECT_STORAGE_ENDPOINT` for Cloudflare R2 and use a different `OBJECT_STORAGE_PREFIX` for staging and production. The updater uploads changed content before publishing the manifest; `storage-init` verifies and restores that manifest before the backend and frontend start.

## Launch gates

- CI, dependency scans, bundle budget and browser tests pass.
- The update timestamp is fresh and the alert webhook has been test-fired.
- Daily and monthly generation caps are lower than the provider's currency cap.
- Legal contact details and policies match the operator and jurisdiction.
- A keyboard, screen reader and two real mobile devices complete the core reading and reporting flows.
- A backup has been restored successfully in the last 30 days.
