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

Set one paid AI provider key, `DOMAIN`, `PUBLIC_BASE_URL`, a random `ADMIN_TOKEN` of at least 24 characters, `CONTACT_EMAIL`, `CONTACT_ADDRESS`, and provider-side currency limits. Set `ALERT_WEBHOOK_URL` to receive updater failure alerts. Keep `.env.production` off Git and store it in the hosting provider's secret manager.

## Promotion

1. Deploy the candidate to staging and run backend, frontend and Playwright checks.
2. Run one updater cycle and confirm the timestamp, evidence, images, audio and held-story queue.
3. Test admin login, correction publication and logout.
4. Back up production, deploy the same image revisions, then check `/api/health/ready` and the home page.
5. Keep the previous image revision available for rollback.

## Backups and recovery

Run `apps/scripts/backup.sh` nightly. The script creates transactionally consistent copies of all SQLite databases, validates every article, runs `PRAGMA integrity_check`, writes SHA-256 checksums and can upload to S3 or Cloudflare R2. Set `BACKUP_ENCRYPTION_PASSPHRASE` so off-site archives are encrypted, then set `BACKUP_S3_URI` and optionally `BACKUP_S3_ENDPOINT`. Once per month, restore into a new staging Compose project and open several archived editions. `apps/scripts/verify-backup.sh` performs the same non-destructive archive checks manually.

This repository currently uses SQLite databases in the persistent cache volume for reports, generation usage and aggregate analytics. That is safe for one application host with tested backups. A multi-host deployment still requires migrating those stores to PostgreSQL before launch; do not run multiple backend writers against copied cache volumes.

## Launch gates

- CI, dependency scans, bundle budget and browser tests pass.
- The update timestamp is fresh and the alert webhook has been test-fired.
- Daily and monthly generation caps are lower than the provider's currency cap.
- Legal contact details and policies match the operator and jurisdiction.
- A keyboard, screen reader and two real mobile devices complete the core reading and reporting flows.
- A backup has been restored successfully in the last 30 days.
