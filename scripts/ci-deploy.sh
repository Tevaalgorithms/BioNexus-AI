#!/usr/bin/env bash
# Ship one release without SSH: images go to a private registry (ECR), the deploy files and the "run deploy.sh"
# command go to the server through AWS Systems Manager. Used by the deploy workflow; works from a laptop that
# is signed in to AWS too.
# Usage: ci-deploy.sh <release-tag>
# Needs: REGISTRY (ECR host), AWS_REGION, MANAGED_INSTANCE_ID, and the image repositories <name>-api / <name>-web.
set -euo pipefail
RELEASE="${1:?release tag}"
: "${REGISTRY:?}" "${AWS_REGION:?}" "${MANAGED_INSTANCE_ID:?}"
NAME="${PROJECT_NAME:-bionexus-pilot}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

aws ecr get-login-password | docker login --username AWS --password-stdin "$REGISTRY"
for part in api web; do
  image="$REGISTRY/$NAME-$part:$RELEASE"
  if [ "$part" = api ]; then docker build -f "$ROOT/services/api/Dockerfile" -t "$image" "$ROOT"
  else docker build -t "$image" "$ROOT/apps/web"; fi
  docker push "$image"
done

# The deploy files (compose, Caddyfile, scripts) are small and hold no secrets, so they ride inside the command.
BUNDLE="$(tar -czf - --exclude=secrets --exclude=.env -C "$ROOT" scripts infra/lightsail | base64 | tr -d '\n')"
[ "${#BUNDLE}" -lt 90000 ] || { echo "deploy bundle too large for one SSM command" >&2; exit 1; }

COMMANDS="$(python3 - "$BUNDLE" "$RELEASE" "$REGISTRY" "$NAME" <<'PY'
import json, shlex, sys
bundle, release, registry, name = sys.argv[1:]
lines = [
    "set -eu",
    "export PATH=$PATH:/snap/bin",
    "install -d -m 0755 /opt/bionexus",
    f"echo {shlex.quote(bundle)} | base64 -d | tar -xzf - -C /opt/bionexus",
    f"REGISTRY={shlex.quote(registry)} PROJECT_NAME={shlex.quote(name)} "
    f"bash /opt/bionexus/scripts/deploy.sh {shlex.quote(release)}",
]
print(json.dumps({"commands": lines, "executionTimeout": ["900"]}))
PY
)"

COMMAND_ID="$(aws ssm send-command --instance-ids "$MANAGED_INSTANCE_ID" --document-name AWS-RunShellScript \
  --timeout-seconds 600 --parameters "$COMMANDS" --query Command.CommandId --output text)"
echo "SSM command $COMMAND_ID sent; waiting for the server"

for _ in $(seq 1 90); do
  STATUS="$(aws ssm get-command-invocation --command-id "$COMMAND_ID" --instance-id "$MANAGED_INSTANCE_ID" \
    --query Status --output text 2>/dev/null || echo Pending)"
  case "$STATUS" in
    Success) echo "release $RELEASE deployed; internal health checks passed"; exit 0 ;;
    Failed|Cancelled|TimedOut)
      aws ssm get-command-invocation --command-id "$COMMAND_ID" --instance-id "$MANAGED_INSTANCE_ID" \
        --query StandardErrorContent --output text | tail -n 30 >&2
      echo "deploy $STATUS (the server rolled back if it had started the new release)" >&2; exit 1 ;;
  esac
  sleep 10
done
echo "timed out waiting for SSM command $COMMAND_ID" >&2; exit 1
