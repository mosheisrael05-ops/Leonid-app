#!/usr/bin/env python3
"""Fetch TV broadcasts of Bnei Herzliya games from the @Shiddurim and @sidorim Telegram channels
-> data/shiddurim-broadcasts.json, matched to games in data/bhbasket-games.json.
Entries are kept between runs (posts scroll off the channel); entries older than
30 days are dropped. On failure exits 0 without touching the file."""
import datetime
import json
import os
import pathlib
import re

import requests
from bs4 import BeautifulSoup

URL = "https://t.me/s/Shiddurim"
SIDORIM = "https://t.me/sidorim"  # preview disabled: posts are read one by one by number
SIDORIM_POSTS = 30  # ~10 days
GAMES = pathlib.Path("data/bhbasket-games.json")
OUT = pathlib.Path("data/shiddurim-broadcasts.json")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
PAGES = 2  # each page is ~20 posts (about 10 days)
TEAM_RE = re.compile(r"(?:בני|ב\.)\s*הרצליה")  # not "מכבי הרצליה" (football)
TV_RE = re.compile(r"📺\s*([^·|\n]+?)\s*(?:[·|].*)?$")  # channel name after 📺, up to "·" or "|"
TIME_RE = re.compile(r"\b(?:[01]?\d|2[0-3]):[0-5]\d\b")
# post header date: "להיום (31/8)" (@Shiddurim), "יום ראשון • 04/10/26" (@sidorim)
DATE_RE = re.compile(r"\((\d{1,2})[./](\d{1,2})\)|\b(\d{1,2})[./](\d{1,2})[./](\d{2}|\d{4})\b")
IL_TZ = datetime.timezone(datetime.timedelta(hours=3))  # close enough for picking the day


def get(url, **params):
    r = requests.get(url, params=params or None, headers={"User-Agent": UA}, timeout=30)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")


def fetch_posts():
    """Recent posts with their text. Newer posts are a type the channel preview page
    doesn't render ("Please open Telegram to view this post"); for those the text is
    read from the post's own page (og:description)."""
    posts, before = [], None
    for _ in range(PAGES):
        soup = get(URL, **({"before": before} if before else {}))
        msgs = soup.select("div.tgme_widget_message[data-post]")
        if not msgs:
            break
        for m in msgs:
            t = m.select_one("time[datetime]")
            if not t:
                continue
            body = m.select_one("div.tgme_widget_message_text")
            if body:
                for br in body.find_all("br"):
                    br.replace_with("\n")
                text = body.get_text()
            else:
                meta = get(f"https://t.me/{m['data-post']}").select_one('meta[property="og:description"]')
                text = meta["content"] if meta else ""
            posted = datetime.datetime.fromisoformat(t["datetime"]).astimezone(IL_TZ).date()
            posts.append({"id": m["data-post"], "date": posted, "text": text})
        ids = [int(m["data-post"].split("/")[-1]) for m in msgs]
        before = min(ids)
    return posts


def sidorim_exists(n):
    return get(f"{SIDORIM}/{n}", embed=1).select_one("time[datetime]")


def sidorim_latest(start):
    """Latest post number: walk forward from the last known one, tolerating gaps of
    deleted posts. Without a starting point, search exponentially from post 3000."""
    gap = 8
    alive = lambda n: any(sidorim_exists(k) for k in range(n, n + gap))
    if not start:
        lo, hi, step = 3000, 3200, 200
        while alive(hi):
            lo, hi, step = hi, hi + step * 2, step * 2
        while hi - lo > gap:
            mid = (lo + hi) // 2
            lo, hi = (mid, hi) if alive(mid) else (lo, mid)
        start = lo
    n, misses = start, 0
    while misses < gap:
        n += 1
        misses = 0 if sidorim_exists(n) else misses + 1
    return n - gap


def fetch_sidorim(last_id):
    latest = sidorim_latest(last_id)
    posts = []
    for n in range(latest - SIDORIM_POSTS + 1, latest + 1):
        t = sidorim_exists(n)
        if not t:
            continue
        meta = get(f"{SIDORIM}/{n}").select_one('meta[property="og:description"]')
        posted = datetime.datetime.fromisoformat(t["datetime"]).astimezone(IL_TZ).date()
        posts.append({"id": f"sidorim/{n}", "date": posted, "text": meta["content"] if meta else ""})
    return latest, posts


def post_date(text, posted):
    """Date from the post header; posts without one continue that day's list."""
    m = DATE_RE.search("\n".join(text.split("\n")[:5]))
    if not m:
        return posted
    day, month = int(m.group(1) or m.group(3)), int(m.group(2) or m.group(4))
    year = posted.year + (1 if posted.month == 12 and month == 1 else 0)
    if m.group(5):
        year = int(m.group(5)) % 100 + 2000
    try:
        return datetime.date(year, month, day)
    except ValueError:
        return posted


def entries_from(post):
    """Yield (date, time, channel, line) for each item whose game mentions Bnei Herzliya.
    @sidorim items are one line; @Shiddurim items are two lines, a game line and a
    "📺 channel" line, in either order:
      "⏰ 19:00  |  📺 ספורט 5 מקס" / "בני הרצליה - מכבי רמת גן"
      "🏀 בני הרצליה - מכבי רמת גן" / "📺 ספורט 5 · החל ב-20:10"
    """
    date = post_date(post["text"], post["date"])
    lines = [l.strip() for l in post["text"].split("\n") if l.strip()]
    for i, line in enumerate(lines):
        if not TEAM_RE.search(line) or "📺" in line:
            continue
        # @sidorim: one line, "ספורט 5  19:00  כדורסל : בני הרצליה - מכבי רמת גן"
        t = TIME_RE.search(line)
        if t and line[:t.start()].strip():
            yield date, t.group(0), " ".join(line[:t.start()].split()), line
            continue
        # @Shiddurim: the slot line is above the game (older posts) or below it
        tv = lines[i - 1] if i and "⏰" in lines[i - 1] else (lines[i + 1] if i + 1 < len(lines) else "")
        m = TV_RE.search(tv)
        if m:
            t = TIME_RE.search(tv) or TIME_RE.search(line)
            yield date, t.group(0) if t else "", " ".join(m.group(1).split()), line


def match(games, posts):
    found = {}
    for post in posts:
        for date, time, channel, line in entries_from(post):
            for g in games:
                if g.get("played") or not g.get("date"):
                    continue
                if date.isoformat() != g["date"]:
                    continue
                # prefer an item whose time matches kick-off (another "בני הרצליה" sport the same day)
                prev = found.get(g["game_id"])
                if prev and prev["text_time"] == g.get("time") and time != g.get("time"):
                    continue
                found[g["game_id"]] = {"date": g["date"], "time": g.get("time", ""),
                                       "opponent": g.get("opponent", ""), "channel": channel,
                                       "text_time": time, "text": line,
                                       "post": f"https://t.me/{post['id']}"}
    return found


def main():
    try:
        games = json.loads(GAMES.read_text(encoding="utf-8")).get("games", [])
    except Exception as e:
        print(f"no games file: {e}")
        return
    try:
        saved = json.loads(OUT.read_text(encoding="utf-8"))
    except Exception:
        saved = {}
    posts = []
    try:
        posts += fetch_posts()
    except Exception as e:
        print(f"@Shiddurim fetch failed: {e}")
    sidorim_last = saved.get("sidorim_last_id")
    try:
        sidorim_last, more = fetch_sidorim(sidorim_last)
        posts += more
        print(f"@sidorim latest post {sidorim_last}")
    except Exception as e:
        print(f"@sidorim fetch failed: {e}")
    if not posts:
        return
    print(f"read {len(posts)} posts")
    dump = os.environ.get("SHIDDURIM_DUMP")
    if dump:  # debugging aid: save the raw posts to inspect the channel's format
        pathlib.Path(dump).write_text(json.dumps(
            [{**p, "date": p["date"].isoformat()} for p in posts], ensure_ascii=False, indent=2), encoding="utf-8")

    old = saved.get("broadcasts", {})
    cutoff = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()
    broadcasts = {k: v for k, v in old.items() if v.get("date", "") >= cutoff}
    new = match(games, posts)
    broadcasts.update(new)
    for gid, b in new.items():
        print(f"{b['date']} {b['opponent']}: {b['channel']}")

    if broadcasts == old and sidorim_last == saved.get("sidorim_last_id"):
        print("no changes")
        return
    OUT.parent.mkdir(parents=True, exist_ok=True)
    data = {"updated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "sources": [URL, SIDORIM], "sidorim_last_id": sidorim_last, "broadcasts": broadcasts}
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved {len(broadcasts)} broadcasts")


if __name__ == "__main__":
    main()
