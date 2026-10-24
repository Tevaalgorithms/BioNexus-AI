# Contributing

Thanks for helping. This project is small on purpose: keep changes easy to read.

## Before you start
- Run `scripts/init-env.sh` once to create your local `.env`, then `scripts/install-hooks.sh` to turn on the
  commit-time secret scan. See the [README](README.md#run-it-locally) for the full setup.
- **Never commit a secret, a `.env`, a Terraform state or plan file, or a key.** The commit hook and CI both
  scan for them. If one slips through, rotate it first, then remove it.

## Make a change
1. Branch from `main` and keep the change focused: one concern per pull request.
2. Match the surrounding code: names, comment density, and file layout (see
   [`services/api/README.md`](services/api/README.md) and [`apps/web/README.md`](apps/web/README.md)).
3. Add or update a test with the behaviour you changed.
4. Run the checks for the side you touched:
   - Backend (`services/api`): `ruff check .`, `ruff format --check .`, `python -m pytest`.
   - Frontend (`apps/web`): `npm run typecheck`, `npm test`, `npm run build`.
5. Open a pull request. CI runs the same checks plus the secret scan and the Terraform checks.

## Standards
- **Simple code.** The complexity limit (McCabe 5) is enforced; split a function instead of raising it.
- **Accurate claims.** The product reports evidence and its limits. It must not claim a disease is caused
  by a target and must not give treatment advice. Keep that true in code, copy and docs.
- **No invented numbers.** Prices, limits and security claims must be checked against a source or the
  running system before they go in the docs.

## Releases
Pushing a tag like `v0.1.9` runs the checks, builds the images and deploys (see
[`docs/runbooks/deploy.md`](docs/runbooks/deploy.md)). Only maintainers tag releases.

Security issues: see [SECURITY.md](SECURITY.md).
