#!/usr/bin/env python3
"""Build wallart-feed.json for gravelandgum.com (IT, 14 Nov 2026, HO-GG-IT-022).

Reads the Cut Price Gadgets store's PUBLIC product feed (the same data any
shopper's browser can see), keeps only products tagged gg-site-only, and writes
a small JSON file the Wall art section reads. No keys, no secrets, no writes to
the store. Run by .github/workflows/wallart-feed.yml every 2 hours.

Safety: exits with an error (so nothing is committed) if any page fails, or if
the number of site-only products drops by more than half compared with the
file already in the repo (protects the live page from a bad read).
"""
import html, json, re, sys, time, urllib.request
from datetime import datetime, timezone

STORE = "https://www.cutpricegadgets.com"
TAG = "gg-site-only"
OUT = "wallart-feed.json"
UA = "gravelandgum.com wall-art feed (hello@gravelandgum.com)"


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except Exception as e:  # retry twice, then give up
            if attempt == 2:
                raise
            time.sleep(10)


def caption(body):
    text = html.unescape(re.sub(r"<[^>]+>", " ", body or ""))
    text = re.sub(r"\s+", " ", text).strip()
    first = re.split(r"(?<=[.!?])\s", text, maxsplit=1)[0] if text else ""
    return first[:220]


def main():
    found = []
    for page in range(1, 60):
        data = get(f"{STORE}/products.json?limit=250&page={page}")
        products = data.get("products", [])
        if not products:
            break
        for p in products:
            tags = p.get("tags", [])
            if TAG not in tags or "cpg-studio" in tags:  # studio line never on gravelandgum.com (55A)
                continue
            found.append({
                "id": str(p["id"]),
                "handle": p["handle"],
                "title": p["title"],
                "caption": caption(p.get("body_html")),
                # newest-first order, G&G's gg-feature-1..9 order tags and gg-opener (HO-GG-IT-028)
                "published": p.get("published_at") or p.get("created_at") or "",
                "rank": min([int(t[len("gg-feature-"):]) for t in tags
                             if re.fullmatch(r"gg-feature-[1-9]", t)] or [0]) or None,
                "opener": "gg-opener" in tags,
                "optionNames": [o["name"] for o in p.get("options", [])],
                "images": [i["src"] for i in p.get("images", [])][:6],
                "variants": [{
                    "id": str(v["id"]),
                    "options": [x for x in (v.get("option1"), v.get("option2"), v.get("option3")) if x],
                    "price": float(v["price"]),
                    "available": bool(v.get("available")),
                    "image": (v.get("featured_image") or {}).get("src"),
                } for v in p.get("variants", [])],
            })
        time.sleep(2)
    else:
        sys.exit("Too many pages; refusing to write.")

    try:
        old = json.load(open(OUT))
        old_n = len(old.get("products", []))
    except Exception:
        old_n = 0
    if old_n and len(found) < old_n / 2:
        sys.exit(f"Only {len(found)} site-only products found (was {old_n}); refusing to write.")

    found.sort(key=lambda p: p["handle"])
    new = {"source": STORE, "tag": TAG, "products": found}
    try:
        same = {k: v for k, v in old.items() if k != "generated"} == new
    except Exception:
        same = False
    if same:
        print(f"No change ({len(found)} products).")
        return
    new = {"generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), **new}
    with open(OUT, "w") as f:
        json.dump(new, f, ensure_ascii=False, indent=1)
    print(f"Wrote {OUT}: {len(found)} products.")


if __name__ == "__main__":
    main()
