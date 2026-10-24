# Incident procedures

## Provider outage or runaway spend
1. Admin -> Overview -> **Stop all model calls** (records a reason). New calls are blocked; affected runs
   end `incomplete` with the original manifest; nothing is silently re-routed to an unapproved model.
2. Check Admin -> Usage and the provider dashboard; reconcile with `bionexus_spend_usd_total` (`/admin/metrics`).
3. Fix or switch an agent to an approved fallback (Agents & models -> validate -> evaluate -> activate).
4. Resume model calls with a reason. Re-submit incomplete investigations as new runs.

## Compromised account
1. `admin_cli revoke-sessions` and `disable-user` for the subject; disable in Cognito.
2. Review Admin -> Audit history and `GET /investigations/{id}/messages` for runs the user touched.
3. Rotate secrets if an admin account was involved ([secrets.md](secrets.md)). Re-enrol MFA on re-enable.

## Tenant data exposure (suspected)
1. Stop model calls; take a backup; preserve logs (`docker compose logs`, structured JSON).
2. Identify scope from the append-only audit log and run events; notify the data owner and security lead.
3. Do not delete evidence of the incident. Record timeline, cause and fix in the post-incident note.

## Source retraction
1. Identify affected evidence ids. Scientists can exclude evidence (with a reason) on any run awaiting
   review; exclusion also removes it from project memory reuse.
2. For approved reports, create a corrected version by re-running the investigation (new run supersedes
   the old one); do not edit approved versions.
3. Record the decision and source/licence status in the source-rights register (SOURCE-10).

## Failed deployment
`scripts/deploy.sh` rolls back automatically; if it cannot, set `RELEASE=<previous>` in `.env` and
`docker compose up -d`. Restore the pre-deploy backup only if a migration damaged data.
