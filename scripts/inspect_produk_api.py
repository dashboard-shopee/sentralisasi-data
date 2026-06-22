"""
scripts/inspect_produk_api.py — INTIP semua field API product/performance.

Tujuan: cari apakah ada field "jumlah pesanan/order" per produk (mis.
confirmed_orders) yang belum kita pakai. Tidak menulis apa-apa ke SQL.

Prasyarat: sudah login modul sentralisasi -> `python -m shopee.session`
Jalankan: python scripts/inspect_produk_api.py
"""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shopee import config
from shopee.session import grab_session, close_session
from shopee.api import api_get

WIB = timezone(timedelta(hours=7))
URL = "https://seller.shopee.co.id/api/mydata/v4/product/performance/"
TOKO = "beverra"


def params(session, start, end):
    return {
        "SPC_CDS": session["params"]["SPC_CDS"],
        "SPC_CDS_VER": session["params"]["SPC_CDS_VER"],
        "start_time": start, "end_time": end, "period": "month",
        "keyword": "", "category_type": "shopee", "category_id": -1,
        "page_size": 10, "page_num": 1, "order_type": "confirmed",
        "order_by": "confirmed_sales.desc",
    }


def main():
    # bulan penuh terakhir
    now = datetime.now(WIB)
    first_this = datetime(now.year, now.month, 1, tzinfo=WIB)
    last_month_end = first_this
    last_month_start = (first_this - timedelta(days=1)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    start, end = int(last_month_start.timestamp()), int(last_month_end.timestamp())

    info = config.SHOP_DATABASE[TOKO]
    session = grab_session(shop=TOKO, i=info["i"])
    try:
        result = api_get(URL, config.grab_headers(session), params(session, start, end))["result"]
        items = result.get("items", [])
        print(f"\nTotal produk: {result.get('total')}  | contoh {len(items)} item\n")
        if items:
            print("=== SEMUA FIELD 1 PRODUK (cari yang artinya 'pesanan/order') ===")
            print(json.dumps(items[0], indent=2, ensure_ascii=False))
    finally:
        close_session()


if __name__ == "__main__":
    main()
