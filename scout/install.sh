#!/bin/bash
# Installs the scout as a systemd timer on the Oracle server (05:00 and 17:00 IST). Run once: bash scout/install.sh
set -e
sudo tee /etc/systemd/system/studio-scout.service >/dev/null <<EOF
[Unit]
Description=Studio scout (what works now + AI/tech news radar)
After=network-online.target

[Service]
Type=oneshot
User=ubuntu
WorkingDirectory=/home/ubuntu/studio
Nice=15
TimeoutStartSec=3h
ExecStartPre=/usr/bin/git -C /home/ubuntu/studio pull -q --rebase
ExecStart=/bin/bash -c 'python3 scout/scout.py >> /home/ubuntu/scout.log 2>&1'
EOF
sudo tee /etc/systemd/system/studio-scout.timer >/dev/null <<EOF
[Unit]
Description=Studio scout twice a day

[Timer]
OnCalendar=*-*-* 23:30:00 UTC
OnCalendar=*-*-* 11:30:00 UTC
Persistent=true
RandomizedDelaySec=300

[Install]
WantedBy=timers.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now studio-scout.timer
systemctl list-timers studio-scout.timer --no-pager | head -n 3
