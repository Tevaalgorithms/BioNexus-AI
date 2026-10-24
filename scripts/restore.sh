#!/usr/bin/env bash
# Restore a backup onto a clean host (OPS-07). Usage: restore.sh <s3-key> <age-identity-file>
set -euo pipefail
KEY="${1:?s3 key, e.g. db/db-20261023T020000Z.dump.age}"; IDENTITY="${2:?age identity file}"
: "${BACKUP_BUCKET:?set BACKUP_BUCKET}"
COMPOSE_DIR="${COMPOSE_DIR:-/opt/bionexus/infra/lightsail}"
cd "$COMPOSE_DIR"

docker compose up -d db
until docker compose exec -T db pg_isready -U bionexus >/dev/null 2>&1; do sleep 2; done

aws s3 cp "s3://$BACKUP_BUCKET/$KEY" - | age -d -i "$IDENTITY" \
  | docker compose exec -T db pg_restore -U bionexus -d bionexus --clean --if-exists --no-owner

docker compose up -d migrate api worker web proxy
echo "restore complete; verify login, history and a reviewed report (docs/runbooks/restore.md)"
