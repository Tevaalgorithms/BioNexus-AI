# Restore from backup (target RTO 8 h, RPO 24 h)

Backups: `bionexus-backup.timer` runs `scripts/backup.sh` daily at 02:15 UTC: `pg_dump` -> `age`
encryption -> private Lightsail bucket, 30-day retention. Lightsail snapshots are an extra layer, not
a replacement. Local writes after the last backup are lost; this is accepted for the pilot.

1. Provision a clean host (`terraform apply`, cloud-init) and copy `/opt/bionexus`, secrets and `.env`.
2. `BACKUP_BUCKET=... scripts/restore.sh db/db-<timestamp>.dump.age /path/to/age-identity.txt`
3. Verify: sign in (both entry points), open investigation history, open an approved report, and check
   the manifest's configuration release exists under Admin -> Releases.
4. Record elapsed time in the DR log. Re-run this drill before go-live and quarterly.
The `age` private key is stored offline by two named people, never on the host.
