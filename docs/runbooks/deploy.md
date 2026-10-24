# Deploy, rollback, patching

## Automatic deploys (GitHub Actions, no SSH key)

A release is a git tag: `git tag v0.1.0 && git push origin v0.1.0`.

1. **checks**: the same tests, audits, secret scan and image builds as CI. Any failure stops the release.
2. **approval**: the job waits for a reviewer on the GitHub `production` environment.
3. **deploy** (`.github/workflows/deploy.yml`):
   - signs in to AWS with a short-lived OIDC role (no AWS keys stored in GitHub);
   - `scripts/ci-deploy.sh` builds the two images and pushes them to a private registry (ECR);
   - it then sends one command to the server through AWS Systems Manager (SSM). The command unpacks the small
     deploy bundle (compose files and scripts) and runs `scripts/deploy.sh`;
   - `deploy.sh` pulls the images, takes a backup, runs migrations, starts the release, and **rolls back by itself**
     if the API or worker is not healthy within about 2.5 minutes;
   - a smoke test fetches the public home page.

Port 22 stays closed to the internet the whole time. A failed deploy or smoke test fails the workflow run, so you get
GitHub's normal failure email.

### One-time setup

1. Set `github_repo` in your tfvars and run `terraform apply`. Note the outputs `deploy_role_arn`, `ecr_registry`, `ssm_activation_id`.
2. The new server registers itself with SSM on first boot (cloud-init uses a one-time code that expires after 7 days).
   Check: `aws ssm describe-instance-information` lists it as Online. If it is not listed within a few minutes of first boot, or the 7-day code expired, run `terraform apply -replace=aws_ssm_activation.host` for a new code and register by hand in the Lightsail browser terminal: `sudo snap stop amazon-ssm-agent && sudo amazon-ssm-agent -register -code <code> -id <id> -region <region> && sudo snap start amazon-ssm-agent`.
3. First-time server secrets need no manual step: the deploy copies `POSTGRES_PASSWORD` and `bootstrap/aws_credentials` from SSM onto the server (mode 600) using the server's own SSM identity (`scripts/fetch-bootstrap-secrets.sh`). Only `/etc/bionexus/backup.env` (daily backups) is set up separately, see `secrets.md`.
4. In GitHub: Settings, Environments, create **production** and add yourself as a required reviewer. In it add these
   variables (none are secret): `DEPLOY_ROLE_ARN`, `ECR_REGISTRY`, `SSM_ACTIVATION_ID`, `AWS_REGION`, `PUBLIC_HOST`.
5. Push a tag.

### Trade-offs to know

- The GitHub role can push to the two image repositories and run one shell command on the registered server, which is
  effectively root there. It only works for jobs in the `production` environment of your repository, after approval.
- Images are kept immutable, five per repository. ECR storage costs about $0.10 per GB per month, so well under $1.
- The registered server counts as an SSM "hybrid" machine; the standard tier used here has no charge.
- Everything runs on the server through AWS, so there is no SSH key to lose or rotate. For emergencies use the Lightsail browser terminal.

## Manual deploy (fallback)

From a laptop signed in to AWS with Docker: set `REGISTRY`, `AWS_REGION`, `MANAGED_INSTANCE_ID`, then run `scripts/ci-deploy.sh v0.1.0`.
On the host only: `sudo scripts/deploy.sh <tag>` when the images are already loaded.

## Rollback

- Automatic during a deploy, as above. The first ever deploy has nothing to roll back to and just fails.
- Later: deploy an older tag again (re-run the workflow on it). Migrations are forward-only, so a destructive migration needs a separate, reviewed release and a tested restore point (`restore.md`).

## Patching

`scripts/host-update.sh` weekly (cron or systemd timer); containers restart themselves.

Configuration rollback (models, prompts) is in the admin UI: Releases, then Roll back to this. It is independent of code deploys; historical runs always keep their original release.
