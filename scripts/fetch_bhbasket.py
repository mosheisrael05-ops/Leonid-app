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
COMPETITIONS = [  # (text found on page, clean name)
    ("Winner", "ליגת ווינר"), ("ווינר", "ליגת ווינר"),
    ("צ'מפיונס", "ליגת האלופות"), ("ליגת האלופות", "ליגת האלופות"),
    ("גביע", "גביע המדינה"), ("פיינל פור", "פיינל פור"), ("ידידות", "משחק ידידות"),
]
HE_MONTHS = {"ינואר": 1, "פברואר": 2, "מרץ": 3, "מרס": 3, "אפריל": 4, "מאי": 5, "יוני": 6,
             "יולי": 7, "אוגוסט": 8, "ספטמבר": 9, "אוקטובר": 10, "נובמבר": 11, "דצמבר": 12}
HE_DATE_RE = re.compile(r"\b(\d{1,2})\s+ב?(" + "|".join(HE_MONTHS) + r")")
TEAM = "בני הרצליה"


def season_start_year():
    today = datetime.date.today()
    return today.year if today.month >= 8 else today.year - 1


def to_iso(day, month):
    """Season runs Aug-Jul: Aug-Dec in start year, Jan-Jul in the next year."""
    start = season_start_year()
    year = start if month >= 8 else start + 1
    try:
        return datetime.date(year, month, day).isoformat()
    except ValueError:
        return ""


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
    he_m = HE_DATE_RE.search(text)
    date_iso = to_iso(int(he_m.group(1)), HE_MONTHS[he_m.group(2)]) if he_m else ""
    date_text = f"{he_m.group(1)} ב{he_m.group(2)}" if he_m else (date_m.group(0) if date_m else "")
    competition = next((clean for key, clean in COMPETITIONS if key in text), "")
    home_away = "בית" if "בית" in text else ("חוץ" if "חוץ" in text else "")
    broadcast_m = re.search(r"(שידור טרם נקבע|שידור[^|•]{0,15}|ספורט\s?5\+?|ערוץ\s?\d+|כאן\s?11)", text)
    return {
        "date": date_iso,
        "date_text": date_text,
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
        info = parse(text)
        comp_words = [k for k, _ in COMPETITIONS]
        opponent = next((t for t in teams if TEAM not in t and not any(w in t for w in comp_words)), "")
        played = bool(info["score"]) and info["score"] not in ("0:0", "00:00")
        game = {"game_id": gid, **info, "opponent": opponent, "played": played,
                "teams": teams, "raw_text": text}
        games.append(game)

    if not games:
        print("no games parsed")
        return

    # Keep previously scraped played games the site no longer lists, so the last result
    # stays available until a newer game gets a final score.
    try:
        old = json.loads(OUT.read_text(encoding="utf-8")).get("games", [])
    except Exception:
        old = []
    current_ids = {g["game_id"] for g in games}
    games += [g for g in old if g.get("played") and g.get("game_id") not in current_ids]
    games.sort(key=lambda g: g.get("date") or "9999")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    data ={"updated": datetime.datetime.now(datetime.timezone.utc).isoformat(), "source": URL, "games": games}
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved {len(games)} games")


if __name__ == "__main__":
    main()
