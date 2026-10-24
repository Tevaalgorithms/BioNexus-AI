#!/usr/bin/env bash
# Encrypted daily PostgreSQL backup + artifact sync to private Lightsail object storage (OPS-05).
# Requires: age (https://age-encryption.org) public key in $BACKUP_AGE_RECIPIENT, aws CLI, and
# access keys for the bucket in /etc/bionexus/backup-credentials (bucket-scoped, not account-wide).
set -euo pipefail

: "${BACKUP_BUCKET:?set BACKUP_BUCKET}" "${BACKUP_AGE_RECIPIENT:?set BACKUP_AGE_RECIPIENT}"
COMPOSE_DIR="${COMPOSE_DIR:-/opt/bionexus/infra/lightsail}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT

cd "$COMPOSE_DIR"
docker compose exec -T db pg_dump -U bionexus --format=custom bionexus \
  | age -r "$BACKUP_AGE_RECIPIENT" > "$WORK/db-$STAMP.dump.age"

# Refuse to upload an empty or suspiciously small dump.
[ "$(stat -c %s "$WORK/db-$STAMP.dump.age" 2>/dev/null || stat -f %z "$WORK/db-$STAMP.dump.age")" -gt 1024 ]

aws s3 cp "$WORK/db-$STAMP.dump.age" "s3://$BACKUP_BUCKET/db/db-$STAMP.dump.age" --only-show-errors

# Retention: delete dumps older than ${RETENTION_DAYS:-30} days.
CUTOFF="$(date -u -d "-${RETENTION_DAYS:-30} days" +%Y%m%d 2>/dev/null || date -u -v-"${RETENTION_DAYS:-30}"d +%Y%m%d)"
aws s3 ls "s3://$BACKUP_BUCKET/db/" | awk '{print $4}' | while read -r key; do
  day="${key#db-}"; day="${day:0:8}"
  [ -n "$day" ] && [ "$day" -lt "$CUTOFF" ] && aws s3 rm "s3://$BACKUP_BUCKET/db/$key" --only-show-errors || true
done

date -u +%s > /var/lib/bionexus/last-backup 2>/dev/null || true   # read by the freshness alert
echo "backup $STAMP ok"
