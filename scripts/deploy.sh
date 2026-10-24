#!/usr/bin/env bash
# Safe deploy with rollback to the previously running release (AWS-15).
# Usage: deploy.sh <release-tag>
# Images bionexus-api:<tag> and bionexus-web:<tag> must exist locally, or set REGISTRY (and PROJECT_NAME) and
# this script pulls <REGISTRY>/<PROJECT_NAME>-api:<tag> and -web:<tag> using the server's AWS user.
set -euo pipefail
NEW="${1:?release tag}"
COMPOSE_DIR="${COMPOSE_DIR:-/opt/bionexus/infra/lightsail}"
cd "$COMPOSE_DIR"
export PATH="$PATH:/snap/bin"
touch .env
PREVIOUS="$(grep -E '^RELEASE=' .env | cut -d= -f2 || true)"; PREVIOUS="${PREVIOUS:-none}"
grep -q '^RELEASE=' .env || echo "RELEASE=$PREVIOUS" >> .env
# The 2 GB MVP plan uses the memory-limited override; remove this line on a bigger server.
grep -q '^COMPOSE_FILE=' .env || echo "COMPOSE_FILE=docker-compose.yml:docker-compose.mvp.yml" >> .env

# Compose reads these from .env; the workflow passes them in, so they are never hand-edited on the server.
set_env() { grep -q "^$1=" .env && sed -i.bak "s|^$1=.*|$1=$2|" .env && rm -f .env.bak || echo "$1=$2" >> .env; }
[ -z "${AWS_REGION:-}" ] || set_env AWS_REGION "$AWS_REGION"
[ -z "${PUBLIC_HOST:-}" ] || set_env PUBLIC_HOST "$PUBLIC_HOST"

set_release() { sed -i.bak "s/^RELEASE=.*/RELEASE=$1/" .env && rm -f .env.bak; }
healthy() {
  for _ in $(seq 1 30); do
    [ "$(docker compose ps api --format '{{.Health}}')" = "healthy" ] && \
    [ "$(docker compose ps worker --format '{{.Health}}')" = "healthy" ] && return 0
    sleep 5
  done
  return 1
}

fetch_secrets() { "$(dirname "$0")/fetch-bootstrap-secrets.sh" secrets; }
fetch_secrets

pull_images() {
  [ -n "${REGISTRY:-}" ] || return 0
  local region; region="$(echo "$REGISTRY" | cut -d. -f4)"
  AWS_SHARED_CREDENTIALS_FILE="$PWD/secrets/aws_credentials" aws ecr get-login-password --region "$region" \
    | docker login --username AWS --password-stdin "$REGISTRY"
  for part in api web; do
    docker pull "$REGISTRY/${PROJECT_NAME:-bionexus-pilot}-$part:$NEW"
    docker tag "$REGISTRY/${PROJECT_NAME:-bionexus-pilot}-$part:$NEW" "bionexus-$part:$NEW"
  done
}
pull_images

# Always take a fresh restore point first, except on the very first deploy when there is no database yet.
# Once backups are configured (/etc/bionexus/backup.env) this step is mandatory; until then it is skipped loudly.
if [ -n "$(docker compose ps -q db 2>/dev/null)" ]; then
  if [ -f /etc/bionexus/backup.env ]; then
    set -a; . /etc/bionexus/backup.env; set +a
    "$(dirname "$0")/backup.sh"
  else
    echo "WARNING: backups are not configured, so no restore point was taken (see docs/runbooks/secrets.md)" >&2
  fi
fi
set_release "$NEW"
docker compose up -d migrate                # migrations run before the new API starts
docker compose up -d --remove-orphans

if healthy; then echo "deployed $NEW"; exit 0; fi

if [ "$PREVIOUS" = none ]; then echo "release $NEW unhealthy and there is no earlier release to roll back to" >&2; exit 1; fi
echo "release $NEW unhealthy; rolling back to $PREVIOUS" >&2
set_release "$PREVIOUS"
docker compose up -d --remove-orphans
exit 1
