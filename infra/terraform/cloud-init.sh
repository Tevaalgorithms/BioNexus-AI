#!/usr/bin/env bash
# First-boot provisioning: Docker, unattended upgrades, deploy directory, daily backup timer.
set -eu   # Lightsail runs this with sh, which has no pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq ca-certificates curl unattended-upgrades age unzip
snap install aws-cli --classic
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
echo "deb [signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" > /etc/apt/sources.list.d/docker.list
apt-get update -qq && apt-get install -y -qq docker-ce docker-ce-cli docker-compose-plugin
systemctl enable --now docker
# A 2 GB host needs headroom for spikes: 1 GB of swap keeps the database from being killed.
if [ ! -f /swapfile ]; then
  fallocate -l 1G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi
mkdir -p /opt/bionexus /var/lib/bionexus /etc/bionexus
chmod 700 /etc/bionexus

# Keyless deploys: register this server with AWS Systems Manager so the CI/CD workflow can run
# the deploy script here (no SSH key, no open SSH port). The one-time code expires after 7 days.
snap install amazon-ssm-agent --classic
snap stop amazon-ssm-agent
/snap/amazon-ssm-agent/current/amazon-ssm-agent -register -code '${activation_code}' -id '${activation_id}' -region '${region}'
snap start amazon-ssm-agent

cat > /etc/systemd/system/bionexus-backup.service <<'UNIT'
[Unit]
Description=BioNexus encrypted database backup
[Service]
Type=oneshot
EnvironmentFile=/etc/bionexus/backup.env
ExecStart=/opt/bionexus/scripts/backup.sh
UNIT
cat > /etc/systemd/system/bionexus-backup.timer <<'UNIT'
[Unit]
Description=Daily BioNexus backup
[Timer]
OnCalendar=*-*-* 02:15:00 UTC
Persistent=true
[Install]
WantedBy=timers.target
UNIT
systemctl daemon-reload && systemctl enable bionexus-backup.timer
