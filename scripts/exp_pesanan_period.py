"""Eksperimen: cari nilai 'period' di key-metrics yang menghargai start/end (per-hari)."""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shopee import config as scfg
from shopee.session import grab_session, close_session
from shopee.api import api_get

WIB = timezone(timedelta(hours=7))
URL = "https://seller.shopee.co.id/api/mydata/v3/dashboard/key-metrics/"
CAND = ["", "real_time", "realtime", "today", "yesterday", "day", "daily",
        "custom", "self_defined", "past7days", "past30days", "month"]


def hari(d):
    s = datetime(d.year, d.month, d.day, tzinfo=WIB)
    return int(s.timestamp()), int((s + timedelta(days=1) - timedelta(seconds=1)).timestamp())


def main():
    info = scfg.SHOP_DATABASE["kimmioshop"]
    sess = grab_session(shop="kimmioshop", i=info["i"])
    try:
        d1 = (datetime.now(WIB) - timedelta(days=3)).date()      # 3 hari lalu
        d2 = (datetime.now(WIB) - timedelta(days=10)).date()     # 10 hari lalu
        for label, d in [("H-3", d1), ("H-10", d2)]:
            s, e = hari(d)
            print(f"\n=== {label} ({d}) ===")
            for p in CAND:
                params = {"SPC_CDS": sess["params"]["SPC_CDS"], "SPC_CDS_VER": sess["params"]["SPC_CDS_VER"],
                          "start_time": s, "end_time": e, "order_type": "confirmed"}
                if p:
                    params["period"] = p
                try:
                    r = api_get(URL, scfg.grab_headers(sess), params, attempts=1)["result"]
                    co = (r.get("confirmed_orders") or {}).get("value")
                    print(f"  period={p or '(kosong)':<12} confirmed_orders={co}")
                except Exception as ex:
                    print(f"  period={p or '(kosong)':<12} ERR: {str(ex)[:70]}")
    finally:
        close_session()


if __name__ == "__main__":
    main()
