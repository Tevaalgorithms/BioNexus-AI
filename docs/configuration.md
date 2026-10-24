# Configuration and secrets

**No secret, password, token or key is stored in the code, images, Compose files or Terraform inputs.**
(Enforced by `tests/test_no_secrets_in_repo.py` and gitleaks in CI.)

| Environment | Source | How |
| --- | --- | --- |
| Local development | repo-root `.env` (gitignored) | `scripts/init-env.sh` writes it with **random** values; real env vars override it |
| Production | **AWS SSM Parameter Store**, `/bionexus/prod/*` | API, worker and web read it with decryption at start-up; settings re-read every 5 minutes (`BIONEXUS_PARAM_REFRESH_SECONDS`) |

Selecting the source needs only bootstrap variables: `APP_ENV=production`, `SSM_PATH_PREFIX`, `AWS_REGION`
and the AWS credential chain. In production the process environment is *not* consulted for settings.

## Parameters (same names in `.env` and SSM; relative path `a/b` is read as `a_b`)

| Name | Type in SSM | Purpose | Live? |
| --- | --- | --- | --- |
| `BIONEXUS_DATABASE_URL`, `POSTGRES_PASSWORD` | SecureString | database access | restart |
| `COGNITO_REGION`, `COGNITO_USER_POOL_ID`, `COGNITO_DOMAIN`, `COGNITO_*_CLIENT_ID` | String | sign-in | restart |
| `COGNITO_ADMIN_CLIENT_SECRET`, `COGNITO_SCIENTIST_CLIENT_SECRET`, `SESSION_SECRET` | SecureString | BFF sign-in + sessions | restart |
| `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` (or any name a model references) | SecureString | provider keys | **yes** (rotate with no restart) |
| `BIONEXUS_RUN_BUDGET_USD`, `BIONEXUS_RUN_WARN_USD`, `BIONEXUS_RUN_MAX_CALLS`, `BIONEXUS_TENANT_MONTHLY_USD` | String | spend limits | **yes** (applies to the next submission) |
| `BIONEXUS_SOURCES` (`live`/`fixture`), `BIONEXUS_INLINE_WORKER`, `AUTH_MODE`, `PUBLIC_BASE_URL`, `BIONEXUS_API_URL` | String | behaviour | restart |
| `BIONEXUS_DEFAULT_MODEL`, `BIONEXUS_FALLBACK_MODEL`, `BIONEXUS_MODELS_JSON` | String | **first-start** model seed | seed only |
| `DEV_ADMIN_TOKEN`, `DEV_SCIENTIST_TOKEN` | local only | dev sign-in; ignored in production | n/a |

## Models are configured at runtime
`BIONEXUS_MODELS_JSON` only *seeds* the catalogue on first start (it never overwrites later admin changes).
After that, admins use **Admin → Model registry** (or `POST /admin/models`) to:
- **add** a model: provider must be `anthropic`/`openai` (endpoints are fixed in code), the key *name* must
  already exist in SSM, prices must be positive and dated, and it must pass a capped smoke test;
- **deprecate** (no new bindings; pinned runs keep working) or **disable** (runs use their approved fallback);
- **bind** it to any agent via validate → fixture evaluation → activate, with rollback.
Changes apply to new runs; running investigations stay pinned to their configuration release.

## The one bootstrap credential
Lightsail has no instance role, so something must authenticate to SSM. Terraform creates an IAM user limited to
read `/bionexus/prod*` (plus decrypt through SSM). An operator creates its access key by hand
(`aws iam create-access-key`), stores it on the host as `infra/lightsail/secrets/aws_credentials` (mode 600,
AWS credentials-file format), and it is mounted read-only into containers. It never enters Terraform state or
Git. The database container also needs `secrets/postgres_password` (a copy of SSM `POSTGRES_PASSWORD`).
