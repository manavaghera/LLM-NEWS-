# Free Oracle Cloud deployment

This is the deployment target for the first public NewsSense release. It keeps the frontend, backend,
hourly updater and writable news directory on the same host, matching the application's current storage
model.

## Free layout

- **Production VM:** OCI `VM.Standard.A1.Flex`, 1 OCPU, 6 GB RAM, Ubuntu 24.04, 50 GB boot volume.
- **Staging VM:** the same shape and size.
- **DNS:** two existing domain records, or two free DuckDNS subdomains, pointed at the VM public IPs.
- **HTTPS:** Caddy obtains and renews certificates automatically.
- **Updates:** the Compose updater starts immediately and repeats every 60 minutes.

This uses the current Always Free total of 2 A1 OCPUs and 12 GB RAM. Oracle can reclaim an Always Free
instance it considers idle, so this is suitable for a first hobby launch rather than a guaranteed-SLA
commercial service.

## 1. Create the VMs

Create both VMs in the account's home region and select only resources labelled **Always Free eligible**.
Download each SSH private key. In the VCN/subnet security list, allow inbound TCP 22, 80 and 443. Do not
open ports 3000 or 8000.

## 2. Prepare each server

Copy `bootstrap.sh` to the VM and run:

```bash
chmod +x bootstrap.sh
sudo ./bootstrap.sh https://github.com/manavaghera/LLM-NEWS-.git feature/newssense-rebuild production
```

Use `staging` as the third argument on the staging VM.

The script installs Docker, clones the repository, creates an unprivileged `newssense` account and adds a
nightly backup. Generated news is stored outside Git in an environment-specific directory, so a deploy or
checkout cannot erase it.

## 3. Add secrets

On production, create `/opt/newssense/repo/LLM-News/.env.production`. On staging, create `.env.staging`.
Use `.env.example` as the field list. At minimum set:

```dotenv
LLM_PUBLISHER=NVIDIA
NVIDIA_API_KEY=replace-me
ADMIN_TOKEN=replace-with-at-least-24-random-characters
POSTGRES_PASSWORD=replace-with-at-least-24-random-characters
DOMAIN=newssense-example.duckdns.org
PUBLIC_BASE_URL=https://newssense-example.duckdns.org
ALLOWED_ORIGINS=https://newssense-example.duckdns.org
ALLOWED_HOSTS=newssense-example.duckdns.org,backend,localhost
CONTACT_EMAIL=you@example.com
CONTACT_ADDRESS=your-real-business-or-contact-address
UPDATE_MINUTES=60
STALE_AFTER_MINUTES=120
UPDATE_LOCK_SECONDS=7200
PIPELINE_DAILY_CALL_LIMIT=200
PIPELINE_MONTHLY_CALL_LIMIT=4000
OBJECT_STORAGE_BUCKET=your-news-bucket
OBJECT_STORAGE_PREFIX=production/news
OBJECT_STORAGE_REGION=auto
OBJECT_STORAGE_ENDPOINT=https://ACCOUNT_ID.r2.cloudflarestorage.com
OBJECT_STORAGE_ACCESS_KEY_ID=replace-me
OBJECT_STORAGE_SECRET_ACCESS_KEY=replace-me
```

Use `STAGING_DOMAIN` instead of `DOMAIN` in staging. Keep these files readable only by the deployment
account:

```bash
sudo chown newssense:newssense /opt/newssense/repo/LLM-News/.env.*
sudo chmod 600 /opt/newssense/repo/LLM-News/.env.*
```

## 4. Deploy

```bash
sudo -u newssense newssense-deploy staging
sudo -u newssense newssense-deploy production
```

The command validates Compose configuration, builds all images, starts the hourly updater and fails if the
public HTTPS readiness endpoint does not become healthy. Readiness includes news freshness, so a new empty
server becomes ready only after its first successful edition is published.

Production news lives in `/opt/newssense/data/production/static`; staging uses
`/opt/newssense/data/staging/static`. The Compose backend and frontend mount that directory read-only, while
only the updater can write it. The deploy script grants the updater the host directory's numeric group, so
publishing remains non-root even when the host `newssense` account is not UID 1000. On the first upgraded
deployment, an existing archive under `apps/static` is copied into the new durable directory automatically.

## 5. Verify backups

The nightly job validates article JSON, generated cache and the PostgreSQL dump before it reports success. Test a backup set without
changing the live site:

```bash
cd /opt/newssense/repo/LLM-News/apps
BACKUP_ENCRYPTION_PASSPHRASE='the-backup-secret' sh scripts/verify-backup.sh \
  /opt/newssense/backups/static-DATE.tar.gz.enc \
  /opt/newssense/backups/cache-DATE.tar.gz.enc \
  /opt/newssense/backups/database-DATE.dump.enc
```

Copy `deployment/oracle-cloud/backup.env.example` to `/opt/newssense/backup.env`. Put
`BACKUP_ENCRYPTION_PASSPHRASE`, `BACKUP_S3_URI`, standard `AWS_*` credentials and, for R2,
`BACKUP_S3_ENDPOINT` in `/opt/newssense/backup.env`. Use quoted shell `KEY=value` lines and keep the file
owned by `newssense` with mode `0600`. The backup job confirms each remote object exists after upload.

## 6. Optional GitHub deployments

The repository workflow `deploy.yml` can deploy an exact commit manually. Create GitHub environments named
`staging` and `production`, then add these secrets to each environment:

- `SSH_HOST`: VM public IP or hostname
- `SSH_USER`: `newssense`
- `SSH_PRIVATE_KEY`: the VM private key
- `SSH_KNOWN_HOSTS`: one `ssh-keyscan -H VM_IP` line, verified against the VM host-key fingerprint

Run **Actions → Deploy → Run workflow**, select the environment, and enter the commit SHA that passed CI.
Protect the production GitHub environment with manual approval before allowing collaborators to deploy.
