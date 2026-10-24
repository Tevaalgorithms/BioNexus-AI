#!/usr/bin/env bash
# Creates a local .env with freshly generated random values. Safe to re-run: never overwrites.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -e .env ] && { echo ".env already exists; leaving it untouched"; exit 0; }
rand() { openssl rand -hex $(( ${1:-40} / 2 )); }
PG_PASS="$(rand 24)"
cat > .env <<ENV
# Local development only (gitignored). Production reads the same names from AWS SSM Parameter Store.
BIONEXUS_RUN_BUDGET_USD=10
BIONEXUS_RUN_WARN_USD=5
BIONEXUS_RUN_MAX_CALLS=40
BIONEXUS_TENANT_MONTHLY_USD=200
BIONEXUS_SOURCES=fixture
BIONEXUS_INLINE_WORKER=1
# Throwaway local database: docker run -d -p 55432:5432 -e POSTGRES_PASSWORD=$PG_PASS -e POSTGRES_DB=bionexus pgvector/pgvector:pg16
BIONEXUS_TEST_DSN=postgresql://postgres:$PG_PASS@localhost:55432/bionexus
# Dev-mode sign-in tokens (random; only honoured when APP_ENV is not production)
DEV_ADMIN_TOKEN=$(rand 40)
DEV_SCIENTIST_TOKEN=$(rand 40)
SESSION_SECRET=$(rand 48)
# Optional, for real model calls:
# ANTHROPIC_API_KEY=
# OPENAI_API_KEY=
ENV
chmod 600 .env
echo "wrote .env (mode 600)"
