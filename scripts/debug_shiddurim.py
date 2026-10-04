#!/usr/bin/env python3
"""TEMP: dump what t.me/s/Shiddurim returns, to see why recent posts are missing."""
import json, re, requests
from bs4 import BeautifulSoup
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
out, before = [], None
for url in ["https://t.me/s/Shiddurim", "https://t.me/Shiddurim/4610?embed=1&mode=tme", "https://t.me/Shiddurim/4610"]:
    r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
    soup = BeautifulSoup(r.text, "html.parser")
    msgs = []
    for m in soup.select("div.tgme_widget_message"):
        t = m.select_one("time[datetime]")
        body = m.select_one("div.tgme_widget_message_text")
        msgs.append({"post": m.get("data-post"), "time": t["datetime"] if t else None,
                     "classes": sorted({c for el in m.find_all(class_=True) for c in el["class"]
                                        if c.startswith("tgme_widget_message_")}),
                     "text": body.get_text("\n")[:300] if body else None,
                     "html": str(m)[:6000]})
    out.append({"url": r.url, "status": r.status_code, "len": len(r.text),
                "title": soup.title.string if soup.title else None,
                "links": sorted({a["href"] for a in soup.find_all("a", href=True) if "before=" in a["href"] or "after=" in a["href"]}),
                "messages": msgs, "head": r.text[:1500] if not msgs else ""})
open("data/shiddurim-raw.json", "w", encoding="utf-8").write(json.dumps(out, ensure_ascii=False, indent=1))
print(json.dumps([{k: v for k, v in o.items() if k != "messages"} | {"n": len(o["messages"])} for o in out], ensure_ascii=False)[:3000])
