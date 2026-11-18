# Laptop render worker (18 Nov)

Mehul's laptop (Lenovo 81SY, i5-9300HF 4c/8t, 16 GB, GTX 1650 4 GB) renders Studio videos when it is on.
Measured on tech 1117-0729: server 464 s, laptop 146 s (3.2x), frames identical (SSIM 0.987, grain only).
`--gpu` and `--experimental-fast-capture` gave no gain (encode is not the bottleneck; fast capture falls back on the
lab look's mix-blend-mode). The job bot stays on the server (owner).

## How it works
- Server `engine/make.py` step 7 asks `engine/laptop.py`: if the laptop checked in < 60 s ago, is plugged in and not
  "off", the render folder goes to `~/studio-out/laptop/queue/`. Not claimed in 75 s, failed, wrong length, or > 25 min
  -> the server renders it as before. Nothing ever waits on the laptop for long.
- Laptop `tools/laptop_worker.py` (Task Scheduler "StudioRenderWorker", hidden, at logon, restarts on crash) checks in
  every 15 s over ssh (no open port), claims a job with an atomic `mv`, renders, uploads the mp4.
- Files on the laptop: `C:\Users\mehul\studio-render\` (mode.txt, worker.log, jobs\).

## The toggle (Desktop shortcut "Studio render mode")
- auto (default): full speed (normal priority, 6 workers) after 3 min without keyboard/mouse, gentle (below-normal
  priority, 3 workers) while Mehul works.
- fast / quiet / off. On battery it never takes a job.
- Plugged-in sleep is off (powercfg standby/hibernate AC = 0), owner OK 18 Nov.

## Check
- Server: `python engine/laptop.py` (status), STATE.md "Laptop render worker", engine.log "laptop: rendered in".
- Laptop: `Get-Content C:\Users\mehul\studio-render\worker.log -Tail 20`; `Get-ScheduledTask StudioRenderWorker`.
