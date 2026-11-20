# Businesses: reels from a business's own media library

Studio makes reels for any business from ITS OWN photos and clips. One engine (`engine/biz.py`), one settings file per
business (`businesses/<id>/business.json`). Nothing about a business is written in the code.
Example: `businesses/vajra/business.json` (VAJRA Formwork, first business, live since 20 Nov 2026).

## What happens for each reel
1. **Library update**: `library.update` command (e.g. `git pull`) in the library folder.
2. **Index**: every clip/photo once. Vision looks at 4 frames of each clip: what it shows, burned-in text (left out),
   black bars (cropped), AI or real. Cached in `~/studio-out/biz/<id>/index.json`.
3. **Plan**: script of 6-9 scenes, every scene uses one real media item (fresh first, `cooldown_days` per item).
   Business rules, `never` regexes and the optional python text filter are applied; a breaking plan is re-asked or held.
4. **Voice**: Gemini (Studio keys), free Edge voice when Gemini is out. Whisper times every word.
5. **Frame check before render**: each scene's real frame vs its line; wrong footage is swapped (2 rounds), else held.
6. **Edit + render**: Studio captions/cards/end card + music from the business library + SFX, -14 LUFS.
   Rendered on the laptop when it is on, else on the server.
7. **Final QC**: format, loudness, voice match, rules, frames (one repair round). Fail = held, never delivered.
8. **Deliver**: first usable target in `deliver` (git drop, command, or folder).

Dashboard: **Channels > Businesses** (library size, auto status, last reels, "Make one reel now").

## Add a new business (checklist)
1. **Media library** on the server: `~/libraries/<id>/` with folders, e.g. `clips/`, `photos/`, `music/`
   (mp4/mov/jpg/png/mp3). Optional `library.json` per folder: `{"file.mp4": {"note": "what it shows", "ok": true}}`.
   No index file is fine: vision describes everything.
   Ways to fill it: a Telegram group per business, a Google Drive folder (rclone), or a git repo (like VAJRA).
   Disk: server has ~155 GB free (Oracle 200 GB, 20 Nov).
2. **Settings**: copy `businesses/vajra/business.json` to `businesses/<id>/business.json` and change:
   - `name`, `handle`, `about` (what they sell, where), `audience`, `language`
   - `library.roots` (where the folder is on laptop / server), `library.sources` (folder, kind clip|photo, index file)
   - `media.ban` (regex of file names/descriptions never to use), `cooldown_days`
   - `rules` (plain sentences the writer must obey), `never` (regexes that hold a reel), optional `text_filter` (python hook)
   - `voice` (Gemini voice + style, Edge fallback voice), `edit` (words, scenes, min clips), `theme` (colours), `cta`,
     `caption_rule`, `hashtags`
   - `auto` (min_pending, max_per_day, hours, where the business's queue file is) or leave out for manual only
   - `deliver`: `{"type": "folder", "dir": "~/studio-out/biz/<id>/ready"}` is the simplest; `git_drop` / `command` for automation
3. **Test**: `python engine/biz.py <id> index` then `python engine/biz.py <id> make --no-deliver` and watch the reel.
4. **Timer** (auto): add one line to `engine/units.sh` like `studio-biz-vajra`, then `sudo bash engine/units.sh`.
5. **Posting**: for a business with its own Instagram/Facebook, deliver into Studio posting (publish.py with that page's
   account) or the business's own pipeline. Comment-to-DM works for any page given to the Planstalk Connect token.

## Commands
- `python engine/biz.py <id> status`: library size, fresh clips, last reels
- `python engine/biz.py <id> make [--angle "idea"] [--no-deliver] [--job ID] [--from plan|voice|assets|compose|render]`
- `python engine/biz.py <id> auto`: makes a reel only if the business needs one (timer uses this)

## VAJRA specifics (example)
- Library: git repo mdeshlahra123/vajra-automation (sparse clone on server `~/libraries/vajra`: assets/clips, photos, music,
  social/engine for claims.py + brand.md).
- Deliver: `git_drop` into offhours-lab/vajra-gen `studio/vajra-<job>/`; GitHub `studio-intake.yml` (every 30 min) imports it
  into the VAJRA queue + FYI on Telegram ("hatao reel-studio-<job>" removes it).
- Timer `studio-biz-vajra` 07:20-21:20 every 2 h; makes a reel when fewer than 3 reels are waiting (max 2/day).
