"""Watch scrollhouse.in until it is live (owner 18 Nov: .IN KYC under review, up to 24 h). Hourly, tells Mehul on Telegram
once per step: (1) registry hold lifted -> "edit DNS now" with the exact records, (2) DNS points to GitHub, (3) the site
answers over HTTPS. State in ~/studio-out/domainwatch.json; the timer can stay, it goes quiet when everything is done.
  python engine/domainwatch.py [--print]"""
import json, os, socket, sys, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import OUT, log, load, save, telegram

DOMAIN = "scrollhouse.in"
GH = {"185.199.108.153", "185.199.109.153", "185.199.110.153", "185.199.111.153"}
STATE = os.path.join(OUT, "domainwatch.json")


def status():
    try:
        d = json.load(urllib.request.urlopen(urllib.request.Request(f"https://rdap.nixiregistry.in/rdap/domain/{DOMAIN}",
                                                                    headers={"User-Agent": "studio"}), timeout=20))
        return [s.lower() for s in d.get("status", [])]
    except Exception as e:
        return ["unknown: " + str(e)[:60]]


def ips():
    try:
        return set(socket.gethostbyname_ex(DOMAIN)[2])
    except Exception:
        return set()


def https_ok():
    try:
        r = urllib.request.urlopen(urllib.request.Request(f"https://{DOMAIN}/", headers={"User-Agent": "studio"}), timeout=20)
        return r.status == 200 and b"Scroll House" in r.read(20000)
    except Exception:
        return False


def main():
    s = load(STATE, {}) or {}
    if s.get("live"):
        return
    st = status()
    held = any("hold" in x for x in st)
    a = ips()
    pr = "--print" in sys.argv
    if pr:
        print("status:", st, "| ips:", sorted(a), "| https:", https_ok())
    if not held and not s.get("released") and not any(x.startswith("unknown") for x in st):
        s["released"] = True
        telegram("✅ scrollhouse.in KYC approved, the hold is lifted. Edit DNS in GoDaddy now:\n"
                 "• A @ (the 'Parked' row) -> 185.199.108.153\n• add A @ 185.199.109.153, 185.199.110.153, 185.199.111.153\n"
                 "• CNAME www -> offhours-lab.github.io\nThen GitHub > Settings > Pages > custom domain scrollhouse.in")
        log("domainwatch: hold lifted")
    if a and a <= GH and not s.get("dns"):
        s["dns"] = True
        telegram("🌐 scrollhouse.in now points to GitHub. Tick 'Enforce HTTPS' in GitHub > Settings > Pages when it allows.")
        log("domainwatch: dns ok")
    if s.get("dns") and https_ok():
        s["live"] = True
        telegram("🚀 https://scrollhouse.in is live.")
        log("domainwatch: live")
    save(STATE, s)


if __name__ == "__main__":
    main()
