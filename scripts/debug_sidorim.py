# TEMP: can single @sidorim posts be read?
import json, requests
from bs4 import BeautifulSoup
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
out = {}
for n in [1, 10, 100, 300, 1000, 2000, 3000, 5000]:
    for url in [f"https://t.me/sidorim/{n}", f"https://t.me/sidorim/{n}?embed=1"]:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
        s = BeautifulSoup(r.text, "html.parser")
        d = s.select_one('meta[property="og:description"]')
        t = s.select_one("time[datetime]")
        body = s.select_one(".tgme_widget_message_text, .message_media_not_supported_label, .tgme_widget_message_error")
        out[url] = {"desc": (d["content"][:200] if d else None), "time": t["datetime"] if t else None,
                    "body": body.get_text(" ", strip=True)[:200] if body else None}
open("data/sidorim-raw.json", "w").write(json.dumps(out, ensure_ascii=False, indent=1))
