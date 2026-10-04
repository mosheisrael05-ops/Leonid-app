# TEMP: what is t.me/sidorim?
import json, requests
from bs4 import BeautifulSoup
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
out = []
for url in ["https://t.me/sidorim", "https://t.me/s/sidorim"]:
    r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
    s = BeautifulSoup(r.text, "html.parser")
    out.append({"url": url, "final": r.url, "status": r.status_code, "title": s.title.string if s.title else None,
                "meta": {m.get("property") or m.get("name"): m.get("content") for m in s.find_all("meta") if m.get("content")},
                "extra": [d.get_text(" ", strip=True) for d in s.select(".tgme_page_extra, .tgme_page_title, .tgme_page_description, .tgme_action_button_new, .tgme_channel_info_header_title")],
                "n_msgs": len(s.select("div.tgme_widget_message"))})
open("data/sidorim-raw.json", "w").write(json.dumps(out, ensure_ascii=False, indent=1))
