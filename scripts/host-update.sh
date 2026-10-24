#!/usr/bin/env bash
# Weekly unattended host patching; the app stays up because containers restart automatically.
set -euo pipefail
apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get -y -qq upgrade
[ -f /var/run/reboot-required ] && systemctl reboot || true
