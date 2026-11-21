"""21 Nov owner: "everything must run on the server too, the laptop can be off any time".
Runs a laptop-worker job (clip / transcribe / info / fetch / words / whop) HERE, with the same code as the laptop
(tools/laptop_worker.py), so nothing waits for the laptop:
  - ssh / scp to the server become local shell / copy (we ARE the server)
  - YouTube blocks this server's IP ("Sign in to confirm you're not a bot"): yt-dlp and ffmpeg go through Cloudflare
    WARP's local proxy (warp-cli proxy mode, http://127.0.0.1:40000, free). Only this job process uses the proxy.
  python engine/localjob.py <jid>     (laptop.job starts it; the job file is in ~/studio-out/laptop/claimed/)
Result: ~/studio-out/laptop/done/<jid>.tgz (or .err), exactly what the laptop would send."""
import json, os, shutil, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROXY = "http://127.0.0.1:40000"


def main(jid):
    os.environ.update(HTTP_PROXY=PROXY, HTTPS_PROXY=PROXY, http_proxy=PROXY, https_proxy=PROXY,
                      NO_PROXY="127.0.0.1,localhost", no_proxy="127.0.0.1,localhost")
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import laptop_worker as W
    W.NOWIN = 0                                          # Windows-only process flag
    W.HOME = os.path.expanduser("~/studio-render-local")
    W.CACHE = os.path.join(W.HOME, "yt-cache")
    os.makedirs(os.path.join(W.HOME, "jobs"), exist_ok=True)
    W.SSH, W.SCP = ["SSHLOCAL"], ["SCPLOCAL"]
    real = subprocess.run

    def run(cmd, timeout=120, **kw):
        kw.pop("creationflags", None)
        if cmd[0] == "SSHLOCAL":
            return real(["bash", "-c", cmd[-1]], capture_output=True, text=True, timeout=timeout)
        if cmd[0] == "SCPLOCAL":
            src, dst = [c.split(":", 1)[1] if c.startswith(W.HOST + ":") else c for c in cmd[-2:]]
            shutil.copy(src, dst)
            return subprocess.CompletedProcess(cmd, 0, "", "")
        return real(cmd, capture_output=True, text=True, timeout=timeout, **kw)
    W.run = run
    _Popen = subprocess.Popen.__init__

    def popen(self, *a, **kw):                           # clipcore / gdown call subprocess directly with creationflags
        if kw.get("creationflags"):
            kw["creationflags"] = 0
        _Popen(self, *a, **kw)
    subprocess.Popen.__init__ = popen
    spec = json.load(open(os.path.join(W.R, "claimed", jid + ".json")))
    W.log("server job", jid, spec.get("kind"), spec.get("label", ""))
    fn = {"fetch": W.fetch, "info": W.info_job, "clip": W.clip_job, "whop": W.whop_job, "transcribe": W.transcribe_job,
          "words": W.words_job}[spec["kind"]]
    fn(jid, spec)


if __name__ == "__main__":
    main(sys.argv[1])
