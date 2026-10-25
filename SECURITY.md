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

See [`docs/limits.md`](docs/limits.md). In short: it runs on a single host with no
high availability; the API has no general rate limiting (only a daily cap on user invitations); the web app's Content-Security-Policy allows inline scripts
(needed for the theme setting and Next.js); sessions are held in server memory.

## Stopping secrets from reaching GitHub

GitHub's own secret scanning and push protection are not available for a private repository on a personal account
(the API answers "not available for this repository"). They are free if the repository is public or on a plan with
GitHub Advanced Security. Until then, three layers apply:

1. **Commit hook (per clone).** Run `scripts/install-hooks.sh` once. Every commit is scanned with gitleaks and blocked if it
   contains a secret or a file such as `.env`, `terraform.tfvars`, `*.tfstate`, `tfplan`, `*.pem` or `*.key`.
2. **CI.** Every push and pull request runs gitleaks over the whole history (`.github/workflows/ci.yml`).
3. **`.gitignore`.** Local settings, Terraform state and plans, and server secret files are ignored.

Hooks can be skipped with `--no-verify`, so treat layer 2 as the real guarantee: set a branch protection rule requiring
the `secrets-and-infra` check before merging. If a secret is ever pushed, rotate it first, then clean the history.
