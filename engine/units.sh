#!/bin/bash
# Studio timers added 17 Nov (same shape as studio-radar). Run once with sudo: bash engine/units.sh
# The doctor keeps them enabled afterwards. Times are IST (server clock).
set -e
mk() {   # name  description  OnCalendar  script-and-args  timeout-seconds
cat > /etc/systemd/system/$1.service <<EOF
[Unit]
Description=$2
[Service]
Type=oneshot
User=ubuntu
WorkingDirectory=/home/ubuntu/studio
Environment=HOME=/home/ubuntu
ExecStart=/home/ubuntu/studio-venv/bin/python /home/ubuntu/studio/engine/$4
CPUWeight=20
Nice=15
TimeoutStartSec=$5
EOF
cat > /etc/systemd/system/$1.timer <<EOF
[Unit]
Description=$2
[Timer]
OnCalendar=$3
Persistent=true
[Install]
WantedBy=timers.target
EOF
mkdir -p /etc/systemd/system/$1.service.d          # 18 Nov: same memory fence as every Studio unit (server froze twice)
[ -f /etc/systemd/system/$1.service.d/memory.conf ] || printf '[Service]\nMemoryHigh=2600M\nMemoryMax=3400M\nIOWeight=20\n' > /etc/systemd/system/$1.service.d/memory.conf
systemctl daemon-reload; systemctl enable --now $1.timer
}
mk studio-trends   "Studio trending topics scout (daily)"     "*-*-* 06:00:00"      trends.py    1800
# 18 Nov: self-healing (engine/healer.py) every 15 min + daily OmniRoute model map (engine/omnimap.py)
[ -f /home/ubuntu/studio/engine/healer.py ]  && mk studio-healer  "Studio healer (fixes what the doctor cannot)" "*-*-* *:07,22,37,52:00" healer.py 3000
[ -f /home/ubuntu/studio/engine/omnimap.py ] && mk studio-omnimap "Studio OmniRoute model map (daily)" "*-*-* 04:40:00" omnimap.py 1800
mk studio-hooks    "Studio hook study of top Shorts (weekly)" "Mon *-*-* 05:30:00"  hookstudy.py 5400
[ -f /home/ubuntu/studio/engine/weekly.py ]   && mk studio-weekly   "Studio weekly report (Sunday)"        "Sun *-*-* 20:00:00" weekly.py   900
[ -f /home/ubuntu/studio/engine/comments.py ] && mk studio-comments "Studio pinned question + comment replies" "*-*-* *:25:00" comments.py 900
# 18 Nov: comment-to-DM + keyword DM replies (engine/dm.py), every 10 min
[ -f /home/ubuntu/studio/engine/dm.py ] && mk studio-dm "Studio comment-to-DM (every 10 min)" "*-*-* *:03/10:00" dm.py 240
[ -f /home/ubuntu/studio/engine/mehul.py ] && mk studio-mehul "Studio Mehul agent (acts for the owner, daily)" "*-*-* 22:30:00" mehul.py 3600
# 18 Nov: competitors + brands (engine/rivals.py): daily track, Sunday brand scan + weekly strategy read
mk studio-rivals "Studio competitor + brand tracker (daily)" "*-*-* 05:10:00" rivals.py 5400
mk studio-domainwatch "Studio scrollhouse.in go-live watcher (hourly)" "*-*-* *:15:00" domainwatch.py 120
mk studio-site "Studio scrollhouse.in site rebuild (daily)" "*-*-* 09:05:00" site.py 300
mk studio-money "Studio money milestones (daily)" "*-*-* 08:50:00" money.py 600
# 19 Nov: brand kit (engine/brand.py)
mk studio-brand "Studio brand kit: real IG DPs -> FB DP/cover, banners, highlight covers (daily)" "*-*-* 06:20:00" brand.py 900
mk studio-janitor "Studio cleanup: duplicates, rejected files, dead builds, serial gaps (daily)" "*-*-* 03:30:00" janitor.py 900
# 18 Nov: whole-repo reading (engine/learn.py deep), 70 chunks a run, 3 runs a day through the repos in ~/studio-out/learn-deep-list.json
mk studio-learn-deep "Studio deep repo reader (3x a day)" "*-*-* 01,09,15:30:00" "learn.py deep --max 70" 14400
[ -f /home/ubuntu/studio/engine/stories.py ] && mk studio-stories "Studio daily Stories (IG + FB, every page)" "*-*-* 11,19:00:00" stories.py 1800
systemctl list-timers 'studio-*' --no-pager | head -30
