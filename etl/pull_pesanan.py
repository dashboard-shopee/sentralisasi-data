"""
etl/pull_pesanan.py — puller PESANAN per TOKO (order unik) -> fact_pesanan.

CATATAN PENTING: API dashboard Shopee untuk order unik per-toko hanya menyediakan
jendela ROLLING (past30days dengan rincian harian via `points`), TIDAK menerima
rentang tanggal historis bebas. Jadi:
  - HARIAN  : diambil dari past30days `points` (30 hari terakhir) per toko.
  - MINGGUAN/BULANAN/TAHUNAN: di-ROLLUP dari harian (akurat — 1 order = 1 hari,
    jadi penjumlahan hari TIDAK double-count, beda dari produk).
  - Histori >30 hari TIDAK tersedia dari Shopee; bertambah maju lewat update harian.

Sumber: key-metrics (confirmed_orders/gmv/paid_orders) + order-performance (cancelled).

CLI:
    python -m etl.pull_pesanan probe          # cek 1 toko
    python -m etl.pull_pesanan all            # tarik 30 hari semua toko + rollup
"""

import random
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import colorama; colorama.init()
from sqlalchemy import text

from config.db import get_engine
from shopee import config as scfg
from shopee.session import grab_session, close_session
from shopee.api import api_get, SesiKedaluwarsa
from etl.load import simpan_pesanan

WIB = timezone(timedelta(hours=7))
URL_KM = "https://seller.shopee.co.id/api/mydata/v3/dashboard/key-metrics/"
URL_OP = "https://seller.shopee.co.id/api/mydata/dashboard/order-performance/"


def _get(session, url):
    now = datetime.now(WIB)
    params = {"SPC_CDS": session["params"]["SPC_CDS"], "SPC_CDS_VER": session["params"]["SPC_CDS_VER"],
              "start_time": int((now - timedelta(days=30)).timestamp()), "end_time": int(now.timestamp()),
              "period": "past30days", "order_type": "confirmed"}
    for _ in range(3):
        try:
            return api_get(url, scfg.grab_headers(session), params, attempts=2)["result"]
        except SesiKedaluwarsa:
            session["refresh"]()
        except Exception:
            try:
                session["refresh"]()
            except Exception:
                pass
    return None


def _peta(metric):
    out = {}
    for x in (metric or {}).get("points", []):
        d = datetime.fromtimestamp(x["timestamp"], WIB).date()
        out[d] = x.get("value")
    return out


def tarik_toko(username, session):
    km = _get(session, URL_KM)
    op = _get(session, URL_OP)
    if not km:
        return []
    co, gmv = _peta(km.get("confirmed_orders")), _peta(km.get("confirmed_gmv"))
    paid = _peta(km.get("paid_orders"))
    canc = _peta((op or {}).get("cancelled_orders"))
    rows = []
    for d in sorted(co):
        mulai = datetime(d.year, d.month, d.day, tzinfo=WIB)
        rows.append({
            "toko": username, "periode": "harian", "periode_mulai": mulai,
            "jumlah_pesanan": co.get(d), "omzet_pesanan": gmv.get(d),
            "pesanan_siap": paid.get(d), "pesanan_batal": canc.get(d),
            "extra": {"sumber": "pull"},
        })
    return rows


# Rollup harian -> mingguan/bulanan/tahunan (akurat utk order: 1 order = 1 hari)
_ROLLUP = text("""
    insert into fact_pesanan
        (toko_id, periode, periode_mulai, jumlah_pesanan, pesanan_siap, pesanan_batal, omzet_pesanan, extra)
    select toko_id, :gran,
           (date_trunc(:trunc, periode_mulai at time zone 'Asia/Jakarta') at time zone 'Asia/Jakarta'),
           sum(jumlah_pesanan), sum(pesanan_siap), sum(pesanan_batal), sum(omzet_pesanan),
           '{"sumber":"rollup_harian"}'::jsonb
    from fact_pesanan
    where periode='harian'
    group by toko_id, date_trunc(:trunc, periode_mulai at time zone 'Asia/Jakarta')
    on conflict (toko_id, periode, periode_mulai) do update set
        jumlah_pesanan=excluded.jumlah_pesanan, pesanan_siap=excluded.pesanan_siap,
        pesanan_batal=excluded.pesanan_batal, omzet_pesanan=excluded.omzet_pesanan,
        extra=excluded.extra, dimuat_pada=now()
""")


def rollup():
    with get_engine().begin() as c:
        for gran, trunc in [("mingguan", "week"), ("bulanan", "month"), ("tahunan", "year")]:
            c.execute(_ROLLUP, {"gran": gran, "trunc": trunc})
    print("Rollup pesanan (mingguan/bulanan/tahunan) dari harian: selesai.")


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else "all"
    toko = ({"kimmioshop": scfg.SHOP_DATABASE["kimmioshop"]} if arg == "probe" else scfg.SHOP_DATABASE)
    print(colorama.Fore.LIGHTCYAN_EX + f"\nPULL PESANAN (30 hari, points harian) — {len(toko)} toko\n" +
          colorama.Style.RESET_ALL)
    total = 0
    for username, info in toko.items():
        nama = info["name"]
        try:
            session = grab_session(shop=username, i=info["i"])
        except Exception as ex:
            print(colorama.Fore.RED + f"[{nama}] gagal sesi: {ex}" + colorama.Style.RESET_ALL); continue
        try:
            rows = tarik_toko(username, session)
            n = simpan_pesanan(rows)
            total += n
            tot_order = sum(r["jumlah_pesanan"] or 0 for r in rows)
            print(f"  [{nama}] {n} hari -> total {tot_order} pesanan (30hr)")
        except Exception as ex:
            print(colorama.Fore.RED + f"  [{nama}] ERROR: {ex}" + colorama.Style.RESET_ALL)
        time.sleep(random.uniform(0.5, 1.2))
    close_session()
    if arg != "probe":
        rollup()
    print(colorama.Fore.LIGHTCYAN_EX + f"SELESAI — {total} baris harian pesanan." + colorama.Style.RESET_ALL)


if __name__ == "__main__":
    main()
