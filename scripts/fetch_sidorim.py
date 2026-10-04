#!/usr/bin/env python3
"""Broadcast channel for Bnei Herzliya from Telegram @sidorim.

League sites block datacenter bots, and the club site often says
"שידור טרם נקבע". The public channel https://t.me/sidorim posts the
daily sports lineup (channel + time + match). This script reads the
public web preview, with TGStat as a fallback, and:

- writes data/sidorim-herzliya.json
- fills broadcast on matching games in data/bhbasket-games.json
- refreshes the spoken card in data/bnei-herzliya.json

On total failure it exits 0 and does not wipe existing files.
"""
import datetime
import html
import json
import pathlib
import re

import requests

OUT = pathlib.Path("data/sidorim-herzliya.json")
GAMES = pathlib.Path("data/bhbasket-games.json")
CARD = pathlib.Path("data/bnei-herzliya.json")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
SOURCES = [
    "https://t.me/s/sidorim",
    "https://tgstat.com/channel/@sidorim",
    "https://syndication.twitter.com/srv/timeline-profile/screen-name/BHerzliya",
]
TEAM_RE = re.compile(r"הרצליה")
DATE_RE = re.compile(r"(\d{1,2})[./](\d{1,2})[./](\d{2,4})")
TIME_RE = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")
CHANNEL_RE = re.compile(
    r"(ספורט\s*5\s*\+|ספורט\s*5\s*לייב|ספורט\s*5\s*מקס|5\s*סטארס|"
    r"ספורט\s*[1-5]|וואן|ONE|ערוץ\s*הספורט|ספורט\s*1\s*HD|"
    r"ערוץ\s*56|5\s*Plus|5Plus)",
    re.I,
)
MSG_RE = re.compile(
    r'class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>',
    re.S,
)
TAG_RE = re.compile(r"<[^>]+>")


def season_year(month, day_year_hint):
    today = datetime.date.today()
    start = today.year if today.month >= 8 else today.year - 1
    return start if month >= 8 else start + 1


def clean(raw):
    text = TAG_RE.sub(" ", raw)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def fetch_texts():
    texts = []
    for url in SOURCES:
        try:
            r = requests.get(url, headers={"User-Agent": UA, "Accept-Language": "he-IL,he;q=0.9"}, timeout=30)
            r.raise_for_status()
        except Exception as e:
            print(f"source failed {url}: {e}")
            continue
        r.encoding = r.apparent_encoding or "utf-8"
        blocks = MSG_RE.findall(r.text)
        if blocks:
            texts.extend(clean(b) for b in blocks)
        else:
            # aggregator pages: keep the raw visible-ish text
            texts.append(clean(r.text)[:20000])
        print(f"{url}: {len(texts)} text blocks")
    return texts


def parse_hits(texts):
    hits = []
    for text in texts:
        if not TEAM_RE.search(text):
            continue
        date_m = DATE_RE.search(text)
        date_iso = ""
        if date_m:
            day, month, year = int(date_m.group(1)), int(date_m.group(2)), int(date_m.group(3))
            if year < 100:
                year += 2000
            if year < 2020:
                year = season_year(month, year)
            try:
                date_iso = datetime.date(year, month, day).isoformat()
            except ValueError:
                date_iso = ""
        # a line-ish window around the team name
        for m in TEAM_RE.finditer(text):
            window = text[max(0, m.start() - 80): m.end() + 40]
            ch = CHANNEL_RE.search(window) or CHANNEL_RE.search(text[max(0, m.start() - 160): m.end()])
            tm = TIME_RE.search(window)
            channel = re.sub(r"\s+", " ", ch.group(0)).strip() if ch else ""
            clock = tm.group(0) if tm else ""
            hits.append({
                "date": date_iso,
                "time": clock,
                "channel": channel,
                "snippet": window.strip(),
            })
    # unique
    seen, out = set(), []
    for h in hits:
        key = (h["date"], h["time"], h["channel"], h["snippet"])
        if key in seen:
            continue
        seen.add(key)
        out.append(h)
    return out


def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def apply(hits):
    games_doc = load_json(GAMES, {"games": []})
    games = games_doc.get("games") or []
    attached = 0
    for g in games:
        match = None
        for h in hits:
            if h["date"] and h["date"] == g.get("date"):
                match = h
                break
            opp = g.get("opponent") or ""
            if h["channel"] and opp and (opp.split()[0] in h["snippet"] or any(w in h["snippet"] for w in opp.split() if len(w) > 3)):
                match = h
        if not match or not match["channel"]:
            continue
        label = match["channel"]
        if match["time"]:
            label = f"{match['channel']} {match['time']}"
        if g.get("broadcast") in ("", "שידור טרם נקבע", None) or "sidorim" not in (g.get("broadcast_source") or ""):
            g["broadcast"] = label
            g["broadcast_source"] = "https://t.me/sidorim"
            attached += 1
    if games_doc.get("games"):
        games_doc["broadcast_updated"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        GAMES.write_text(json.dumps(games_doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return attached


def refresh_card():
    games_doc = load_json(GAMES, {"games": []})
    games = [g for g in (games_doc.get("games") or []) if g.get("date")]
    games.sort(key=lambda g: g["date"])
    today = datetime.date.today().isoformat()
    nxt = next((g for g in games if not g.get("played") and g["date"] >= today), None)
    last = next((g for g in reversed(games) if g.get("played") and g["date"] <= today and g.get("score") not in ("", "0:0")), None)
    card = load_json(CARD, {})

    def line(g, played=False):
        if not g:
            return None
        home = "בבית" if g.get("home_away") == "בית" else "בחוץ"
        tv = g.get("broadcast") or ""
        tv_bit = f" | ערוץ: {tv}" if tv and tv != "שידור טרם נקבע" else " | ערוץ: טרם פורסם בלוח השידורים"
        score = f" | תוצאה {g.get('score')}" if played and g.get("score") else ""
        return f"{g.get('date_text') or g.get('date')} {g.get('time') or ''} — {home} נגד {g.get('opponent') or ''} ({g.get('competition') or ''}){score}{tv_bit}".strip()

    if nxt:
        card["nextGame"] = line(nxt)
        card["nextGameRu"] = f"{nxt.get('date')} {nxt.get('time') or ''} — {'дома' if nxt.get('home_away') == 'בית' else 'в гостях'} против {nxt.get('opponent') or ''}"
        if nxt.get("broadcast") and nxt.get("broadcast") != "שידור טרם נקבע":
            card["nextGameRu"] += f" | канал: {nxt['broadcast']}"
    # league table is not in the telegram channel; keep a honest status until standings exist
    if not card.get("position") or "רבע גמר" in str(card.get("position")) or datetime.date.today() < datetime.date(2026, 10, 12):
        card["position"] = "ליגת ווינר 2026/27 עוד לא התחילה (מחזור 1 ב-12.10)"
        card["positionRu"] = "Лига Виннер 2026/27 ещё не началась (тур 1 — 12.10)"
    if last:
        card["lastGame"] = line(last, played=True)
    card["updatedAt"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    card["broadcastSource"] = "https://t.me/sidorim"
    CARD.parent.mkdir(parents=True, exist_ok=True)
    CARD.write_text(json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    texts = fetch_texts()
    hits = parse_hits(texts) if texts else []
    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source": "https://t.me/sidorim",
        "hits": hits,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"sidorim hits: {len(hits)}")
    attached = apply(hits)
    print(f"broadcasts attached: {attached}")
    refresh_card()
    print("card refreshed")


if __name__ == "__main__":
    main()
