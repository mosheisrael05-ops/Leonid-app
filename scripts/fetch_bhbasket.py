#!/usr/bin/env python3
"""Fetch Bnei Herzliya games from bhbasket.co.il -> data/bhbasket-games.json.
On failure (network error or zero games) exits 0 without touching the file."""
import datetime
import json
import pathlib
import re

import requests
from bs4 import BeautifulSoup

URL = "https://bhbasket.co.il/games.asp"
OUT = pathlib.Path("data/bhbasket-games.json")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
ID_RE = re.compile(r"GameId=(\d+)", re.I)
TIME_RE = re.compile(r"\b(?:[01]?\d|2[0-3]):[0-5]\d\b")
SCORE_RE = re.compile(r"\b\d{1,3}\s?:\s?\d{1,3}\b")
DATE_RE = re.compile(r"\b\d{1,2}[./]\d{1,2}(?:[./]\d{2,4})?\b")
COMPETITIONS = ["ליגת ווינר", "ווינר", "צ'מפיונס", "ליגת האלופות", "גביע", "פיינל פור", "ידידות"]


def ids_in(el):
    found = set()
    for a in el.find_all("a", href=True):
        m = ID_RE.search(a["href"])
        if m:
            found.add(m.group(1))
    return found


def game_box(a):
    """Climb from the link to the largest container holding only this one game."""
    box = a
    while (box.parent is not None
           and box.parent.name not in ("body", "html", "[document]")
           and len(ids_in(box.parent)) <= 1):
        box = box.parent
    return box


def parse(text):
    time_m = TIME_RE.search(text)
    time = time_m.group(0) if time_m else ""
    scores = [s.replace(" ", "") for s in SCORE_RE.findall(text) if s.replace(" ", "") != time]
    date_m = DATE_RE.search(text)
    competition = next((c for c in COMPETITIONS if c in text), "")
    home_away = "בית" if "בית" in text else ("חוץ" if "חוץ" in text else "")
    broadcast_m = re.search(r"(שידור טרם נקבע|שידור[^|•]{0,15}|ספורט\s?5\+?|ערוץ\s?\d+|כאן\s?11)", text)
    return {
        "date_text": date_m.group(0) if date_m else "",
        "time": time,
        "competition": competition,
        "home_away": home_away,
        "score": scores[-1] if scores else "",
        "broadcast": broadcast_m.group(0).strip() if broadcast_m else "",
    }


def main():
    try:
        r = requests.get(URL, headers={"User-Agent": UA, "Accept-Language": "he-IL,he;q=0.9"}, timeout=30)
        r.raise_for_status()
    except Exception as e:
        print(f"fetch failed: {e}")
        return
    r.encoding = r.apparent_encoding or "utf-8"
    soup = BeautifulSoup(r.text, "html.parser")

    games, seen = [], set()
    for a in soup.find_all("a", href=ID_RE):
        gid = ID_RE.search(a["href"]).group(1)
        if gid in seen:
            continue
        seen.add(gid)
        box = game_box(a)
        text = " ".join(box.get_text(" ", strip=True).split())
        teams = [img.get("alt", "").strip() for img in box.find_all("img") if img.get("alt", "").strip()]
        game = {"game_id": gid, **parse(text), "teams": teams, "raw_text": text}
        games.append(game)

    if not games:
        print("no games parsed")
        return

    OUT.parent.mkdir(parents=True, exist_ok=True)
    data = {"updated": datetime.datetime.now(datetime.timezone.utc).isoformat(), "source": URL, "games": games}
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved {len(games)} games")


if __name__ == "__main__":
    main()
