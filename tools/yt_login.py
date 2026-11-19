"""ONE-TIME YouTube login for a Studio page (run on the laptop, 20 seconds per page).
  python tools/yt_login.py tech      (or katha / raaz)
A browser opens. Pick the Google account that owns that YouTube channel, choose the CHANNEL (brand account) on the next
screen, press Allow. The refresh token is copied to the server (~/.studio-accounts/<page>.json -> "yt") and the engine
starts uploading Shorts to that channel after every Instagram/Facebook post.
It re-uses the VAJRA Uploader OAuth app (already in production, API audit passed 28 Oct): the file
C:\\Users\\mehul\\Desktop\\vajra-automation\\yt-client.json (gitignored). Needs: pip install google-auth-oauthlib"""
import json, os, subprocess, sys, tempfile
from google_auth_oauthlib.flow import InstalledAppFlow

KEY = r"C:\Users\mehul\Desktop\job\oracle.key"
HOST = "ubuntu@137.23.60.164"
CLIENT = r"C:\Users\mehul\Desktop\vajra-automation\yt-client.json"
SCOPES = ["https://www.googleapis.com/auth/youtube", "https://www.googleapis.com/auth/youtube.force-ssl",
          "https://www.googleapis.com/auth/youtube.upload"]

page = (sys.argv[1] if len(sys.argv) > 1 else "").strip()
PAGES = sorted(d for d in os.listdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "channels"))
               if os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "channels", d, "channel.json")))
if page not in PAGES:                                   # 19 Nov: every page (was tech / katha / raaz only)
    sys.exit("usage: python tools/yt_login.py " + "|".join(PAGES))
flow = InstalledAppFlow.from_client_secrets_file(CLIENT, SCOPES)
# 19 Nov: the owner opens the link himself (Edge): print it and do not launch the default browser
creds = flow.run_local_server(port=0, prompt="consent", access_type="offline", open_browser="--open" in sys.argv,
                              authorization_prompt_message=f"Open this link, choose the {page.upper()} YouTube channel, then Allow:\n{{url}}")
if not creds.refresh_token:
    sys.exit("No refresh token came back. Run again and press Allow on every screen.")
c = json.load(open(CLIENT))["installed"]
yt = {"client_id": c["client_id"], "client_secret": c["client_secret"], "refresh_token": creds.refresh_token}
tmp = os.path.join(tempfile.gettempdir(), f"yt-{page}.json")
json.dump(yt, open(tmp, "w"))
script = ("import json,os,sys; p=os.path.expanduser('~/.studio-accounts/%s.json'); a=json.load(open(p)); "
          "a['yt']=json.load(open('/tmp/yt-%s.json')); json.dump(a,open(p,'w'),indent=1); os.remove('/tmp/yt-%s.json'); print('saved yt for %s')") % (page, page, page, page)
subprocess.check_call(["scp", "-q", "-i", KEY, tmp, f"{HOST}:/tmp/yt-{page}.json"])
subprocess.check_call(["ssh", "-i", KEY, HOST, f'python3 -c "{script}"; chmod 600 ~/.studio-accounts/{page}.json'])
os.remove(tmp)
print(f"Done: {page} is connected. Check: the next approved video will also go to YouTube.")
