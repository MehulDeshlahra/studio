"""Store what the engine made in the repo (no video files): plan, research, qc, timing per job + done.json +
lessons-auto.md, then push (deploy key alias github-studio). Video files stay in ~/studio-out."""
import os, shutil, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import ROOT, OUT, log

KEEP = ("plan.json", "research.json", "qc.json", "timing.json", "meta.json", "cues.json")


def main():
    for cid in os.listdir(os.path.join(ROOT, "channels")):
        src = os.path.join(OUT, cid)
        if not os.path.isdir(src):
            continue
        for job in os.listdir(src):
            jd = os.path.join(src, job)
            if not os.path.isdir(jd):
                continue
            dst = os.path.join(ROOT, "channels", cid, "videos", job)
            for f in KEEP:
                if os.path.exists(os.path.join(jd, f)):
                    os.makedirs(dst, exist_ok=True)
                    shutil.copy(os.path.join(jd, f), os.path.join(dst, f))
    g = lambda *a: subprocess.run(["git", "-C", ROOT] + list(a), capture_output=True, text=True)
    g("add", "channels")
    # 18 Nov: the server's own state + what it learned travel with the repo (a new session reads these, not old notes)
    for f in ("results.md", "STATE.md", "fixes.json", "build-queue.md", "mehul.md", "mehul-log.json"):
        if os.path.exists(os.path.join(ROOT, "knowledge", f)):
            g("add", "knowledge/" + f)
    if g("diff", "--cached", "--quiet").returncode:
        g("commit", "-qm", "engine: jobs + lessons")
        g("pull", "-q", "--rebase", "--autostash")
        r = g("push", "-q")
        log("sync pushed" if r.returncode == 0 else "sync push failed: " + r.stderr[-200:])


if __name__ == "__main__":
    main()
