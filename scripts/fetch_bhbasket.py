 #!/usr/bin/env python3
"""Fetch Bnei Herzliya games from bhbasket.co.il -> data/bhbasket-games.json, the final
score of played games from each game's page, and the league table position ->
data/bnei-herzliya.json ("standing"). No API key needed.
On failure (network error or zero games) exits 0 without touching the files."""
import datetime
import json
import pathlib
import re

import requests
from bs4 import BeautifulSoup

SITE = "https://bhbasket.co.il/"
URL = SITE + "games.asp"
OUT = pathlib.Path("data/bhbasket-games.json")
CARD = pathlib.Path("data/bnei-herzliya.json")
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


def get_soup(url):
    r = requests.get(url, headers={"User-Agent": UA, "Accept-Language": "he-IL,he;q=0.9"}, timeout=30)
    r.raise_for_status()
    r.encoding = r.apparent_encoding or "utf-8"
    return BeautifulSoup(r.text, "html.parser")


def rows(soup):
    return [[" ".join(c.get_text(" ", strip=True).split()) for c in tr.find_all(["td", "th"])]
            for tr in soup.find_all("tr")]


def final_score(gid):
    """(ours, theirs) from the game page's "סיום רבע" table, or None before the game ends."""
    found, ours, theirs = False, None, None
    for row in rows(get_soup(f"{SITE}game-zone.asp?GameId={gid}")):
        if row and row[0] == "סיום רבע":
            found = True
            continue
        if found:
            nums = [int(c) for c in row[1:] if c.isdigit()]
            if not row or len(nums) < 4:  # all four quarters, or the game isn't over
                break
            if TEAM.split()[-1] in row[0]:
                ours = nums[-1]
            else:
                theirs = nums[-1]
            if ours is not None and theirs is not None:
                break
    if ours and theirs:
        return ours, theirs
    return None


def fetch_standing():
    """Bnei Herzliya's row in the Winner league table of the current season."""
    table = [r for r in rows(get_soup(f"{SITE}table.asp?cYear={season_start_year() + 1}"))
             if len(r) >= 6 and r[0].isdigit() and r[2].isdigit()]
    row = next((r for r in table if TEAM.split()[-1] in r[1]), None)
    if not row:
        return None
    games, wins, losses = int(row[3]), int(row[4]), int(row[5])
    if not games:
        return None  # season hasn't started
    return {"position": int(row[0]), "total": len(table), "wins": wins, "losses": losses,
            "source": f"{SITE}table.asp", "updated": datetime.datetime.now(datetime.timezone.utc).isoformat()}


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

    # Keep earlier games the site no longer lists. The site drops a game once it is played,
    # often before showing its score, so past games stay here (a score can then be filled
    # in by hand) and the last result stays available until a newer game gets a final score.
    try:
        old = json.loads(OUT.read_text(encoding="utf-8")).get("games", [])
    except Exception:
        old = []
    # The site often drops or never lists the TV channel; keep a channel set earlier
    # (by hand or by fetch_sidorim.py) when the fresh scrape has none.
    old_by_id = {g.get("game_id"): g for g in old}
    for g in games:
        prev = old_by_id.get(g["game_id"]) or {}
        if g.get("broadcast") in ("", "שידור טרם נקבע") and prev.get("broadcast") not in (None, "", "שידור טרם נקבע"):
            g["broadcast"] = prev["broadcast"]
            if prev.get("broadcast_source"):
                g["broadcast_source"] = prev["broadcast_source"]
    current_ids = {g["game_id"] for g in games}
    today = datetime.date.today().isoformat()
    games += [g for g in old if g.get("game_id") not in current_ids
              and (g.get("played") or (g.get("date") or "9999") <= today)]
    games.sort(key=lambda g: g.get("date") or "9999")

    # Final score and win/loss from the game's own page, once per game.
    for g in games:
        if g.get("result") or (g.get("date") or "9999") > today:
            continue
        if g["date"] == today and g.get("time"):
            # Israel time; the page shows running totals until the game ends
            now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3)))
            if now.strftime("%H:%M") < f"{int(g['time'][:2]) + 3:02d}{g['time'][2:]}":
                continue
        try:
            score = final_score(g["game_id"])
        except Exception as e:
            print(f"game {g['game_id']}: score fetch failed: {e}")
            continue
        if score:
            g["score"] = f"{score[0]}:{score[1]}"  # ours:theirs
            g["result"] = "win" if score[0] > score[1] else "loss"
            g["played"] = True
            print(f"{g['date']} {g.get('opponent')}: {g['result']} {g['score']}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    data ={"updated": datetime.datetime.now(datetime.timezone.utc).isoformat(), "source": URL, "games": games}
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved {len(games)} games")

    try:
        standing = fetch_standing()
    except Exception as e:
        print(f"standings fetch failed: {e}")
        standing = None
    if standing:
        try:
            card = json.loads(CARD.read_text(encoding="utf-8"))
        except Exception:
            card = {}
        card["standing"] = standing
        CARD.write_text(json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"standing: {standing['position']}/{standing['total']} ({standing['wins']}-{standing['losses']})")
    else:
        print("no standing for this season yet")


if __name__ == "__main__":
    main()
