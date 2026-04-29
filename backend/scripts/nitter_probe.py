"""
Quick CLI probe for Nitter — tests every instance in twitter_scraper.py
against a single handle and prints what came back.

Usage:
    python backend/scripts/nitter_probe.py BSF_India
    python backend/scripts/nitter_probe.py adgpi 10        # 10 tweets

Prints, for each Nitter instance:
  - HTTP reachability + response time
  - tweet count returned
  - first tweet preview (text + date + likes/retweets)

Use this to confirm whether your Twitter zero-hits issue is Nitter
instance death (very common as of 2023+) or something else.
"""

import sys
import time
from datetime import datetime

# Default instances mirror twitter_scraper.py
INSTANCES = [
    "https://nitter.net",
    "https://nitter.privacydev.net",
    "https://nitter.poast.org",
    "https://nitter.1d4.us",
    "https://nitter.kavin.rocks",
    "https://nitter.unixfox.eu",
]


def reachable(url: str, timeout: int = 5) -> tuple:
    """Return (ok: bool, status_code: int|None, ms: float)."""
    import urllib.request
    import urllib.error
    start = time.time()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return True, resp.status, (time.time() - start) * 1000
    except urllib.error.HTTPError as e:
        return False, e.code, (time.time() - start) * 1000
    except Exception:
        return False, None, (time.time() - start) * 1000


def probe(handle: str, n: int = 5) -> None:
    print(f"\n=== Nitter probe: @{handle} (requesting {n} tweets each) ===\n")

    # Step 1 — basic HTTP reachability
    print("[1] Basic reachability check (GET / on each instance):")
    print(f"    {'instance':<40} {'status':<10} {'time':<8}")
    alive = []
    for inst in INSTANCES:
        ok, code, ms = reachable(inst, timeout=4)
        marker = "OK " if ok else "DEAD"
        print(f"    {inst:<40} {marker} {str(code):<5} {ms:>6.0f} ms")
        if ok:
            alive.append(inst)
    print()

    if not alive:
        print("[!] All Nitter instances are unreachable. Twitter via Nitter is fully broken right now.")
        print("    Recommend either using the official X API (paid Basic+ tier) or")
        print("    self-hosting a Nitter instance with a Twitter session cookie.")
        return

    # Step 2 — try ntscraper end-to-end on each live instance
    print("[2] ntscraper.get_tweets() against each live instance:\n")
    try:
        from ntscraper import Nitter
    except ImportError:
        print("    ntscraper not installed — `pip install ntscraper`")
        return

    for inst in alive:
        print(f"--- {inst}")
        try:
            scraper = Nitter(instance=inst, log_level=1)
            results = scraper.get_tweets(handle, mode="user", number=n)

            tweets = (results or {}).get("tweets", [])
            print(f"    tweets returned: {len(tweets)}")
            if not tweets:
                print(f"    ⚠ no tweets — instance probably blocked / no guest accounts")
                continue

            # Show the first tweet
            t = tweets[0]
            text = (t.get("text") or "").replace("\n", " ")[:160]
            stats = t.get("stats", {}) or {}
            print(f"    first tweet:")
            print(f"      date:     {t.get('date', 'n/a')}")
            print(f"      text:     {text}")
            print(f"      likes:    {stats.get('likes', 0)}")
            print(f"      RTs:      {stats.get('retweets', 0)}")
            print(f"      link:     {t.get('link', 'n/a')}")
            print()
        except Exception as e:
            print(f"    ✗ failed: {type(e).__name__}: {e}")
            print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python backend/scripts/nitter_probe.py <handle> [num_tweets]")
        sys.exit(1)
    handle = sys.argv[1].lstrip("@")
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    probe(handle, n)
