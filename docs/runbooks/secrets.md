# Secrets

All configuration and secrets live in **AWS SSM Parameter Store** under `/bionexus/prod/` (SecureString for
secrets); see [../configuration.md](../configuration.md). Nothing is in images, Git, Compose or logs.

| Secret | Rotate how |
| --- | --- |
| `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` | Create a new key at the provider, `aws ssm put-parameter --overwrite --type SecureString`, wait up to 5 minutes (no restart), revoke the old key. |
| Cognito client secrets | Rotate on the app client, update the SSM parameter, `docker compose up -d --force-recreate web`, revoke the old one. |
| `SESSION_SECRET` | Update the parameter and recreate `web` (signs everyone out). |
| `POSTGRES_PASSWORD` / `BIONEXUS_DATABASE_URL` | `ALTER USER` in the db, update both SSM parameters and `secrets/postgres_password`, recreate `db api worker migrate`. |
| Bootstrap AWS access key | `aws iam create-access-key` for the runtime user, replace `secrets/aws_credentials`, recreate containers, delete the old key. Rotate at least every 90 days. |

Rotate immediately after any suspected exposure. The admin UI shows only "configured / missing" per credential.
