import os
import time
import json
from datetime import date, timedelta

import requests

BASE = "https://world-switch.com/kaitoriouji/ext"
AUTH = os.environ["WASABI_AUTH"]
HEADERS = {"Authorization": f"Bearer {AUTH}"}
SHOP_IDS = [1, 4, 5, 6, 8, 11, 20, 22, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34]
WINDOW_DAYS = 4


def daterange():
    today = date.today()
    return [(today - timedelta(days=i)).isoformat() for i in range(WINDOW_DAYS)][::-1]


def fetch_totals(endpoint, start, end):
    r = requests.get(
        f"{BASE}/api/total/{endpoint}",
        headers=HEADERS,
        params={"start_date": start, "end_date": end},
        timeout=30,
    )
    r.raise_for_status()
    return {row["date"]: row for row in r.json()}


def fetch_qty(d):
    qty_by_shop = {}
    total_qty = 0
    page = 1
    while True:
        r = requests.post(
            f"{BASE}/api/orders/search",
            headers=HEADERS,
            json={
                "limit": 1000,
                "page": page,
                "query": {"order_date": {"gte": f"{d} 00:00:00", "lte": f"{d} 23:59:59"}},
            },
            timeout=60,
        )
        r.raise_for_status()
        payload = r.json()
        for o in payload["data"]:
            shop = int(o["shop_id"])
            for od in o.get("order_details", []):
                q = int(float(od.get("quantity", 0)))
                qty_by_shop[shop] = qty_by_shop.get(shop, 0) + q
                total_qty += q
        if len(payload["data"]) < 1000:
            break
        page += 1
        time.sleep(0.4)
    return total_qty, qty_by_shop


def main():
    dates = daterange()
    ordered = fetch_totals("ordered", dates[0], dates[-1])
    shipped = fetch_totals("shipped", dates[0], dates[-1])

    docs = {}
    for d in dates:
        o = ordered.get(d)
        s = shipped.get(d)
        if not o or not s:
            continue
        total_qty, qty_by_shop = fetch_qty(d)
        o_shop = {x["shop_id"]: int(x["total"]) for x in o["shops"]}
        s_shop = {x["shop_id"]: int(x["total"]) for x in s["shops"]}
        shops = [
            {
                "id": sid,
                "ordered": o_shop.get(sid, 0),
                "shipped": s_shop.get(sid, 0),
                "qty": qty_by_shop.get(sid, 0),
            }
            for sid in SHOP_IDS
        ]
        docs[d] = {
            "date": d,
            "ordered_total": int(o["total"]),
            "ordered_count": int(o["total_order"]),
            "ordered_qty": total_qty,
            "shipped_total": int(s["total"]),
            "shipped_count": int(s["total_order"]),
            "shops": shops,
        }

    out = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "docs": docs,
    }
    os.makedirs("data", exist_ok=True)
    with open("data/latest_sales.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"Wrote {len(docs)} day(s) to data/latest_sales.json")


if __name__ == "__main__":
    main()
