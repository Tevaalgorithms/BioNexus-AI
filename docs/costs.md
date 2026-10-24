# Cost of running the MVP on AWS Lightsail

Prices are US dollars per month, taken from the AWS pricing pages in October 2026. Confirm them before you commit.

| Item | Cost | Notes |
|---|---|---|
| Lightsail Linux server, 2 GB RAM, 2 vCPU, 60 GB disk, 3 TB transfer | **$12** | Runs Caddy, web, API, worker and PostgreSQL. Includes a static IP. |
| Weekly snapshot backup of that disk | about $3 | $0.05 per GB, 60 GB disk. Skip it and use `scripts/backup.sh` to S3 or a laptop for $0. |
| Cognito sign-in (invite-only, password) | $0 | First 10,000 monthly users are free, for all accounts. |
| SSM Parameter Store (standard parameters) | $0 | Storage is free. |
| KMS for SecureString parameters | under $1 | AWS-managed key, 20,000 free requests, then about $0.03 per 10,000. |
| AWS Budgets | $0 | The first two budgets are free. |
| Domain name (optional) | about $1 | Caddy gets the TLS certificate for free. |
| **AWS total** | **about $12 to $16** | Under the $20 limit. |

## AI-model charges are not on the AWS bill

The model provider (Anthropic or OpenAI) bills you directly. The AWS budget cannot see it.
This is the only cost that can exceed $20, so cap it in three places:

1. In the provider's console, set a monthly spend limit (about $5).
2. `run_budget_usd` (default $0.50): the product stops a single investigation at this amount.
3. `tenant_monthly_usd` (default $5): the product stops an organisation at this amount per month.

Both product caps are SSM parameters, so you can change them without a deploy.

## Why the 2 GB plan

Measured on this build: the API or worker process peaks near 130 MB, the web server near 80 MB,
and an idle PostgreSQL near 25 MB. With the OS and Caddy that is well under 1 GB, so 2 GB leaves room for
database cache and spikes. The 1 GB plan ($7) probably works but is tight; the 512 MB plan does not.
`infra/lightsail/docker-compose.mvp.yml` sets per-container memory limits and the server adds 1 GB of swap.

Do not choose the IPv6-only plans to save $2: most of your users, and some tools, still need IPv4.

## Cost controls already in place

- `monthly_budget_usd` defaults to 20. You get an email at 80% of actual spend and when AWS forecasts you will pass 100%.
- SSM settings refresh every 5 minutes (`BIONEXUS_PARAM_REFRESH_SECONDS`) to keep KMS requests near zero.
- Stop the server when idle? Lightsail still bills a stopped server. Delete it, or keep it on.

## Not measured

A real investigation with a live AI model has never been run, so its token cost is an estimate. In offline model mode, one
investigation used 15 model calls and about 6,800 input tokens. Multiply by your provider's current per-token price to
estimate a run, and use the caps above until you have real numbers.
