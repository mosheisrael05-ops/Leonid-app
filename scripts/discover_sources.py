# TEMP: find a key-free source for the league table and results.
import json, re, requests
from bs4 import BeautifulSoup
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
urls = [
    "https://bhbasket.co.il/", "https://bhbasket.co.il/games.asp",
    "https://bhbasket.co.il/game.asp?GameId=26650",
    "https://ibasketball.co.il/", "https://ibasketball.co.il/league/2026-2/",
    "https://basket.co.il/", "https://www.basket.co.il/",
    "https://www.sport5.co.il/liga.aspx?FolderID=407", "https://www.one.co.il/Basketball/",
    "https://www.flashscore.co.il/basketball/israel/super-league/standings/",
    "https://www.sofascore.com/api/v1/team/3466/events/last/0",
]
out = []
for u in urls:
    rec = {"url": u}
    try:
        r = requests.get(u, headers={"User-Agent": UA, "Accept-Language": "he-IL,he;q=0.9"}, timeout=25)
        r.encoding = r.apparent_encoding or "utf-8"
        rec.update(status=r.status_code, final=r.url, len=len(r.text))
        s = BeautifulSoup(r.text, "html.parser")
        rec["title"] = s.title.get_text(strip=True) if s.title else None
        rec["links"] = sorted({(a.get_text(" ", strip=True)[:40], a["href"]) for a in s.find_all("a", href=True)
                               if re.search(r"טבל|table|stand|תוצא|result|league|ליג|game", a["href"] + a.get_text(), re.I)})[:80]
        txt = " ".join(s.get_text(" ", strip=True).split())
        i = txt.find("הרצליה")
        rec["herzliya"] = txt[max(0, i - 300):i + 500] if i >= 0 else None
        rec["tables"] = len(s.find_all("table"))
        if "game.asp" in u or "sofascore" in u:
            rec["text"] = txt[:3000]
    except Exception as e:
        rec["error"] = str(e)[:200]
    out.append(rec)
open("data/discovery.json", "w", encoding="utf-8").write(json.dumps(out, ensure_ascii=False, indent=1))
