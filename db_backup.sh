#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/home/eee/flexx-app"
BACKUP_DIR="/home/eee/flexx-app/backups"
DB_CONTAINER="postgres"
DB_NAME="flexx"
DB_USER="flexx"
DB_PASSWORD="flexx_passwd"
MEDIA_VOLUME_PRIMARY="flexx-app_media_data"
MEDIA_VOLUME_FALLBACK="media_data"
RETENTION_DAYS=7

mkdir -p "$BACKUP_DIR"
cd "$PROJECT_DIR"
umask 077

timestamp="$(date +%Y-%m-%d_%H-%M-%S)"
db_out_file="${BACKUP_DIR}/${DB_NAME}_${timestamp}.sql.gz"
db_tmp_file="${db_out_file}.tmp"
media_out_file="${BACKUP_DIR}/media_${timestamp}.tar.gz"
media_tmp_file="${media_out_file}.tmp"

echo "[db-backup] start db: ${db_out_file}"

docker exec -e PGPASSWORD="$DB_PASSWORD" "$DB_CONTAINER" \
  pg_dump -U "$DB_USER" -d "$DB_NAME" --clean --if-exists --no-owner --no-privileges \
  | gzip -9 > "$db_tmp_file"

mv "$db_tmp_file" "$db_out_file"
echo "[db-backup] done db: ${db_out_file}"

MEDIA_VOLUME="$MEDIA_VOLUME_PRIMARY"
if ! docker volume inspect "$MEDIA_VOLUME" >/dev/null 2>&1; then
  MEDIA_VOLUME="$MEDIA_VOLUME_FALLBACK"
fi
if ! docker volume inspect "$MEDIA_VOLUME" >/dev/null 2>&1; then
  echo "[db-backup] media volume not found: ${MEDIA_VOLUME_PRIMARY} or ${MEDIA_VOLUME_FALLBACK}" >&2
  exit 1
fi

echo "[db-backup] start media: ${media_out_file}"
docker run --rm \
  -v "${MEDIA_VOLUME}:/from:ro" \
  -v "${BACKUP_DIR}:/to" \
  busybox:1.36 \
  sh -c "tar -czf /to/$(basename "$media_tmp_file") -C /from ."

mv "$media_tmp_file" "$media_out_file"
echo "[db-backup] done media: ${media_out_file}"

# Храним только последние 7 дней.
find "$BACKUP_DIR" -type f -name "${DB_NAME}_*.sql.gz" -mtime +"$((RETENTION_DAYS - 1))" -delete
find "$BACKUP_DIR" -type f -name "media_*.tar.gz" -mtime +"$((RETENTION_DAYS - 1))" -delete

echo "[db-backup] rotation done: keep ${RETENTION_DAYS} days"
