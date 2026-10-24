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

set_release() { sed -i.bak "s/^RELEASE=.*/RELEASE=$1/" .env && rm -f .env.bak; }
healthy() {
  for _ in $(seq 1 30); do
    [ "$(docker compose ps api --format '{{.Health}}')" = "healthy" ] && \
    [ "$(docker compose ps worker --format '{{.Health}}')" = "healthy" ] && return 0
    sleep 5
  done
  return 1
}

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
if [ -n "$(docker compose ps -q db 2>/dev/null)" ]; then
  [ -f /etc/bionexus/backup.env ] && { set -a; . /etc/bionexus/backup.env; set +a; }
  "$(dirname "$0")/backup.sh"
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
