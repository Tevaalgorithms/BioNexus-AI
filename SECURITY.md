# Security

## Reporting a vulnerability

Please do not open a public issue for a security problem. Use GitHub's **private vulnerability reporting**
(Security tab → Report a vulnerability) on this repository. Include what you found, how to reproduce it, and
the version or commit. Say if the report involves real credentials, so they can be rotated first.

## Secrets: what is and is not in this repository

- No credentials are committed. Local settings live in a git-ignored `.env` (create it with
  `scripts/init-env.sh`, which generates random values). Production reads every setting and secret from
  AWS SSM Parameter Store. `tests/test_no_secrets_in_repo.py` and gitleaks (in CI) fail a change that adds a
  credential-shaped string.
- The `.env.example` files list names only, with empty values.
- Terraform state (`*.tfstate`), `*.tfvars`, key files and the host's `secrets/` folder are git-ignored.
  Terraform state would contain generated secrets: store it in an encrypted remote backend, never in Git.
- If a secret is ever committed, treat it as exposed: rotate it first ([`docs/runbooks/secrets.md`](docs/runbooks/secrets.md)),
  then remove it from history.

## Checks that run on every change

Ruff (with a complexity limit), the test suite on in-memory and PostgreSQL stores, Bandit (static security
analysis of the Python code), `pip-audit` and `npm audit` (known-vulnerable dependencies), gitleaks (secret
scan), and `terraform validate`.

## Known limits

See "Limits and honest caveats" in the [README](README.md). In short: not yet run against a real Cognito
pool or deployed; the API has no rate limiting yet; the web app's Content-Security-Policy allows inline scripts
(needed for the theme setting and Next.js); sessions are held in server memory.
