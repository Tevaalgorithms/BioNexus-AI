# Runbooks

Pilot operator procedures. The host is a single Lightsail instance (one failure domain, no SLA).
Targets: RPO <= 24 h, RTO <= 8 h. Assign a named operator per alert before go-live (OPS-04).

| Situation | Go to |
| --- | --- |
| Invite / change / disable a user | [users.md](users.md) |
| Deploy, roll back, patch the host | [deploy.md](deploy.md) |
| Restore from backup | [restore.md](restore.md) |
| Rotate a secret | [secrets.md](secrets.md) |
| Provider outage, runaway spend | [incidents.md#provider-outage-or-runaway-spend](incidents.md) |
| Compromised account / tenant data exposure | [incidents.md#compromised-account](incidents.md) |
| Source retraction or licence withdrawal | [incidents.md#source-retraction](incidents.md) |
