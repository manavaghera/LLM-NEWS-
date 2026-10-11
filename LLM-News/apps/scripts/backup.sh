#!/bin/sh
# Back up what can't be rebuilt: the news archive (static/) and the "cache" volume, which holds the reader
# reports database (and translations, digests and audio, which would cost AI calls to make again).
#
#   cd LLM-News/apps && ./scripts/backup.sh /var/backups/newssense [production|staging]
#
# Nightly from cron (crontab -e), keeping the last 14 days (KEEP_DAYS changes that):
#   15 3 * * * cd /srv/LLM-NEWS-/LLM-News/apps && ./scripts/backup.sh /var/backups/newssense >> /var/log/newssense-backup.log 2>&1
#
# Restore (stack stopped, from LLM-News/apps):
#   tar -xzf /var/backups/newssense/static-DATE.tar.gz
#   docker compose run --rm --no-deps --user root -v /var/backups/newssense:/backup backend \
#     sh -c "cd /app && tar -xzf /backup/cache-DATE.tar.gz"
# If cache/reports.db is damaged, rename cache/reports-backup.db (a consistent copy) to reports.db.
# Copy the backups to another machine too: a backup on the same disk doesn't survive losing the server.
set -eu

dest="${1:-./backups}"
environment="${2:-development}"
keep_days="${KEEP_DAYS:-14}"
stamp=$(date +%Y-%m-%d-%H%M)
mkdir -p "$dest"
dest=$(cd "$dest" && pwd)

case "$environment" in
  production)
    export APP_ENV_FILE=../.env.production
    set -- -p newssense-production --env-file ../.env.production \
      -f docker-compose.yml -f docker-compose.prod.yml
    ;;
  staging)
    export APP_ENV_FILE=../.env.staging
    set -- -p newssense-staging --env-file ../.env.staging \
      -f docker-compose.yml -f docker-compose.staging.yml
    ;;
  development)
    set --
    ;;
  *)
    echo "Environment must be production, staging or omitted for development." >&2
    exit 2
    ;;
esac

tar -czf "$dest/static-$stamp.tar.gz" static
echo "news archive -> $dest/static-$stamp.tar.gz"

backend=$(docker compose "$@" ps -q backend)
if [ -z "$backend" ]; then
  echo "The backend isn't running, so the cache volume was not backed up." >&2
  exit 1
fi
# Make consistent copies of every SQLite database, even while reports, usage or metrics are being saved.
docker compose "$@" exec -T backend python -c "
import pathlib, sqlite3
for db in pathlib.Path('cache').glob('*.db'):
    backup = db.with_name(db.stem + '-backup.db')
    if '-backup' not in db.stem:
        with sqlite3.connect(db) as source, sqlite3.connect(backup) as copy:
            source.backup(copy)
"
docker run --rm --volumes-from "$backend" -v "$dest:/backup" alpine \
  tar -czf "/backup/cache-$stamp.tar.gz" -C /app cache
echo "cache volume -> $dest/cache-$stamp.tar.gz"

# Refuse to report success for an unreadable archive.
tar -tzf "$dest/static-$stamp.tar.gz" >/dev/null
tar -tzf "$dest/cache-$stamp.tar.gz" >/dev/null
echo "verified both backup archives"

find "$dest" -name '*.tar.gz' -mtime +"$keep_days" -delete
