#!/bin/bash
# Studio engine timers on the Oracle server: studio-make (every 2 h, makes at most one video) + studio-inbox (every minute).
set -e
for u in make inbox; do
  case $u in make) CMD="engine/daily.py"; ON="*-*-* 00/2:15:00"; NICE=15;; inbox) CMD="engine/inbox.py"; ON="*:*:00"; NICE=5;; esac
  sudo tee /etc/systemd/system/studio-$u.service >/dev/null <<U
[Unit]
Description=Studio engine: $u
[Service]
Type=oneshot
User=ubuntu
WorkingDirectory=/home/ubuntu/studio
Environment=PATH=/home/ubuntu/studio-venv/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=/home/ubuntu/studio-venv/bin/python /home/ubuntu/studio/$CMD
Nice=$NICE
CPUWeight=30
TimeoutStartSec=5h
U
  sudo tee /etc/systemd/system/studio-$u.timer >/dev/null <<U
[Unit]
Description=Studio engine timer: $u
[Timer]
OnCalendar=$ON
Persistent=false
[Install]
WantedBy=timers.target
U
done
sudo systemctl daemon-reload
sudo systemctl enable --now studio-make.timer studio-inbox.timer
systemctl list-timers 'studio-*' --no-pager
