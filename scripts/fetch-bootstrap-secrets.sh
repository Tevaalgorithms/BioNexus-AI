#!/usr/bin/env bash
# Copies the two first-time secrets from SSM Parameter Store onto the server (mode 600).
# Uses the server's own SSM identity: nothing is typed, pasted, logged or stored in Git.
set -euo pipefail
export PATH=$PATH:/snap/bin
PREFIX="${SSM_PREFIX:-/bionexus/prod}"
REGION="${AWS_REGION:-us-west-2}"
DEST="${1:-secrets}"

fetch() {
  local parameter="$1" file="$2" value
  [ -s "$DEST/$file" ] && return 0
  # Captured in a variable, not redirected: the snap-packaged CLI writes nothing to a file redirect.
  value="$(aws ssm get-parameter --region "$REGION" --name "$PREFIX/$parameter" --with-decryption \
    --query Parameter.Value --output text)"
  [ -n "$value" ] || { echo "parameter $parameter is empty" >&2; return 1; }
  printf '%s\n' "$value" > "$DEST/$file.tmp"
  chmod 600 "$DEST/$file.tmp" && mv "$DEST/$file.tmp" "$DEST/$file"
}

mkdir -p "$DEST" && chmod 700 "$DEST"
fetch POSTGRES_PASSWORD postgres_password
fetch bootstrap/aws_credentials aws_credentials
