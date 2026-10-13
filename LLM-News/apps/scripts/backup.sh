#!/bin/sh
# Create verified news and application-state archives. Production and staging use separate data roots.
# Optional client-side encryption and S3-compatible uploads use standard AWS credential variables.
set -eu

if [ -n "${BACKUP_ENV_FILE:-}" ]; then
  if [ ! -r "$BACKUP_ENV_FILE" ]; then
    echo "Backup environment file is not readable: $BACKUP_ENV_FILE" >&2
    exit 1
  fi
  set -a
  # This operator-owned file must use shell KEY=value syntax and mode 0600.
  . "$BACKUP_ENV_FILE"
  set +a
fi

if [ -n "${BACKUP_S3_URI:-}" ] && [ -z "${BACKUP_ENCRYPTION_PASSPHRASE:-}" ]; then
  echo "BACKUP_ENCRYPTION_PASSPHRASE is required for off-site uploads." >&2
  exit 1
fi

dest="${1:-./backups}"
environment="${2:-development}"
keep_days="${KEEP_DAYS:-14}"
stamp=$(date +%Y-%m-%d-%H%M)
mkdir -p "$dest"
dest=$(cd "$dest" && pwd)

case "$environment" in
  production)
    export APP_ENV_FILE=../.env.production
    export NEWS_DATA_DIR="${NEWS_DATA_DIR:-/opt/newssense/data/production/static}"
    set -- -p newssense-production --env-file ../.env.production \
      -f docker-compose.yml -f docker-compose.prod.yml
    ;;
  staging)
    export APP_ENV_FILE=../.env.staging
    export NEWS_DATA_DIR="${NEWS_DATA_DIR:-/opt/newssense/data/staging/static}"
    set -- -p newssense-staging --env-file ../.env.staging \
      -f docker-compose.yml -f docker-compose.staging.yml
    ;;
  development)
    export NEWS_DATA_DIR="${NEWS_DATA_DIR:-./static}"
    set --
    ;;
  *)
    echo "Environment must be production, staging or omitted for development." >&2
    exit 2
    ;;
esac

if [ ! -d "$NEWS_DATA_DIR" ]; then
  echo "News data directory does not exist: $NEWS_DATA_DIR" >&2
  exit 1
fi

static_archive="$dest/static-$stamp.tar.gz"
cache_archive="$dest/cache-$stamp.tar.gz"
database_dump="$dest/database-$stamp.dump"
tar -czf "$static_archive" -C "$NEWS_DATA_DIR" .
echo "news archive -> $static_archive"

backend=$(docker compose "$@" ps -q backend)
if [ -z "$backend" ]; then
  echo "The backend isn't running, so the cache volume was not backed up." >&2
  exit 1
fi

# Snapshot generated cache files in a container-local temporary directory. SQLite's backup API
# replaces copied database/WAL files with consistent databases under their original names.
docker compose "$@" exec -T backend python -c "
import pathlib, shutil, sqlite3, sys, tarfile, tempfile
from contextlib import closing
source_root = pathlib.Path('cache')
with tempfile.TemporaryDirectory(prefix='newssense-cache-') as temporary:
    snapshot = pathlib.Path(temporary) / 'cache'
    shutil.copytree(source_root, snapshot)
    for pattern in ('*.db', '*.db-wal', '*.db-shm'):
        for copied in snapshot.glob(pattern):
            copied.unlink()
    for database in source_root.glob('*.db'):
        with closing(sqlite3.connect(database)) as source, closing(sqlite3.connect(snapshot / database.name)) as target:
            source.backup(target)
    with tarfile.open(fileobj=sys.stdout.buffer, mode='w|gz') as bundle:
        for path in snapshot.rglob('*'):
            bundle.add(path, arcname=path.relative_to(snapshot), recursive=False)
" > "$cache_archive"
echo "cache volume -> $cache_archive"

database=$(docker compose "$@" ps -q database)
if [ -z "$database" ]; then
  echo "The PostgreSQL service isn't running, so no consistent database backup can be made." >&2
  exit 1
fi
docker compose "$@" exec -T database sh -c \
  'exec pg_dump --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --format=custom' > "$database_dump"
if [ ! -s "$database_dump" ]; then
  echo "PostgreSQL produced an empty backup." >&2
  exit 1
fi
docker compose "$@" exec -T database pg_restore --list < "$database_dump" >/dev/null
echo "PostgreSQL database -> $database_dump"

if [ -n "${BACKUP_ENCRYPTION_PASSPHRASE:-}" ]; then
  command -v openssl >/dev/null 2>&1 || {
    echo "BACKUP_ENCRYPTION_PASSPHRASE is set but openssl is unavailable." >&2
    exit 1
  }
  for archive in "$static_archive" "$cache_archive" "$database_dump"; do
    openssl enc -aes-256-cbc -salt -pbkdf2 -iter 200000 \
      -pass env:BACKUP_ENCRYPTION_PASSPHRASE -in "$archive" -out "$archive.enc"
    rm -f "$archive"
  done
  static_archive="$static_archive.enc"
  cache_archive="$cache_archive.enc"
  database_dump="$database_dump.enc"
  echo "encrypted all backup files"
fi

manifest="$dest/manifest-$stamp.sha256"
(
  cd "$dest"
  sha256sum "$(basename "$static_archive")" "$(basename "$cache_archive")" \
    "$(basename "$database_dump")" > "$(basename "$manifest")"
  sha256sum -c "$(basename "$manifest")" >/dev/null
)

sh "$(dirname "$0")/verify-backup.sh" "$static_archive" "$cache_archive" "$database_dump"
echo "verified news, cache and PostgreSQL restore inputs"

aws_command() {
  if [ -n "${BACKUP_S3_ENDPOINT:-}" ]; then
    aws --endpoint-url "$BACKUP_S3_ENDPOINT" "$@"
  else
    aws "$@"
  fi
}

upload_file() {
  file="$1"
  remote="${BACKUP_S3_URI%/}/$(basename "$file")"
  aws_command s3 cp "$file" "$remote" --only-show-errors
  aws_command s3 ls "$remote" >/dev/null
  echo "off-site backup -> $remote"
}

if [ -n "${BACKUP_S3_URI:-}" ]; then
  command -v aws >/dev/null 2>&1 || {
    echo "BACKUP_S3_URI is set but the AWS CLI is unavailable." >&2
    exit 1
  }
  upload_file "$static_archive"
  upload_file "$cache_archive"
  upload_file "$database_dump"
  upload_file "$manifest"
fi

# Delete only files produced by this script, never unrelated files in the destination.
find "$dest" -type f \( -name 'static-*.tar.gz' -o -name 'static-*.tar.gz.enc' \
  -o -name 'cache-*.tar.gz' -o -name 'cache-*.tar.gz.enc' \
  -o -name 'database-*.dump' -o -name 'database-*.dump.enc' \
  -o -name 'manifest-*.sha256' \) -mtime +"$keep_days" -delete
