#!/bin/sh
# Back up what can't be rebuilt: the news archive (static/) and the "cache" volume, which holds the reader
# reports database (and translations, digests and audio, which would cost AI calls to make again).
#
#   cd LLM-News/apps && ./scripts/backup.sh /var/backups/newssense
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
keep_days="${KEEP_DAYS:-14}"
stamp=$(date +%Y-%m-%d-%H%M)
mkdir -p "$dest"
dest=$(cd "$dest" && pwd)

tar -czf "$dest/static-$stamp.tar.gz" static
echo "news archive -> $dest/static-$stamp.tar.gz"

backend=$(docker compose ps -q backend)
if [ -z "$backend" ]; then
  echo "The backend isn't running, so the cache volume was not backed up." >&2
  exit 1
fi
# A consistent copy of the reports database, even if a report is being saved right now
docker compose exec -T backend python -c "
import pathlib, sqlite3
db = pathlib.Path('cache/reports.db')
if db.exists():
    with sqlite3.connect(db) as source, sqlite3.connect('cache/reports-backup.db') as copy:
        source.backup(copy)
"
docker run --rm --volumes-from "$backend" -v "$dest:/backup" alpine \
  tar -czf "/backup/cache-$stamp.tar.gz" -C /app cache
echo "cache volume -> $dest/cache-$stamp.tar.gz"

find "$dest" -name '*.tar.gz' -mtime +"$keep_days" -delete
