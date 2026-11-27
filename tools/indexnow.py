#!/usr/bin/env python3
"""Tell Bing (and the other IndexNow search engines) which pages changed.

After a publish, this compares sitemap.xml with an earlier version and sends
the addresses of new or changed pages to IndexNow, so those search engines
see them within minutes instead of days. Google does not use IndexNow; it
reads the sitemap on its own schedule.

    python3 tools/indexnow.py <earlier git commit>     # only what changed
    python3 tools/indexnow.py                          # every page

The key is the file <key>.txt at the root of the site (it proves the site is
ours). Python 3 standard library only.
"""
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOST = "rojanshrestha.com"
ENDPOINT = "https://api.indexnow.org/indexnow"


def pages(sitemap_text):
    """{address: last-changed date} from a sitemap."""
    return dict(re.findall(r"<loc>([^<]+)</loc>\s*<lastmod>([^<]+)</lastmod>", sitemap_text))


def main():
    keys = [f for f in ROOT.glob("*.txt") if re.fullmatch(r"[0-9a-f]{32}", f.stem)]
    if not keys:
        sys.exit("no IndexNow key file found")
    key = keys[0].stem
    now = pages((ROOT / "sitemap.xml").read_text(encoding="utf-8"))
    before = {}
    if len(sys.argv) > 1 and not set(sys.argv[1]) <= {"0"}:
        try:
            old = subprocess.run(["git", "show", f"{sys.argv[1]}:sitemap.xml"], cwd=ROOT,
                                 capture_output=True, text=True, check=True).stdout
            before = pages(old)
        except subprocess.CalledProcessError:
            before = {}
    changed = [u for u, d in now.items() if before.get(u) != d]
    if not changed:
        print("IndexNow: no changed pages")
        return
    body = json.dumps({"host": HOST, "key": key, "keyLocation": f"https://{HOST}/{key}.txt",
                       "urlList": changed}).encode()
    req = urllib.request.Request(ENDPOINT, data=body, method="POST",
                                 headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            print(f"IndexNow: sent {len(changed)} page(s), answer {res.status}")
    except urllib.error.HTTPError as err:
        # 202 = accepted, 422/403 = key not reachable yet; never fail the publish over this
        print(f"IndexNow: answer {err.code} {err.reason}")
    for u in changed:
        print("  ", u)


if __name__ == "__main__":
    main()
