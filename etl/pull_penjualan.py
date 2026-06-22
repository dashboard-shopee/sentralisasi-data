"""
etl/pull_penjualan.py — puller MANDIRI product performance -> fact_penjualan.

Pakai modul shopee/ sendiri (TIDAK menyentuh folder bot 01/02/03).
Ambil metrik lengkap termasuk PESANAN (confirmed_orders) & PEMBELI (confirmed_buyers).
Dipakai untuk re-backfill DAN update harian (lihat scripts/update_harian.py nanti).

CLI:
    python -m etl.pull_penjualan bulanan  all
    python -m etl.pull_penjualan mingguan all
    python -m etl.pull_penjualan harian   all
    python -m etl.pull_penjualan harian   beverra      # 1 toko
    python -m etl.pull_penjualan harian   all 3        # harian 3 hari terakhir saja

Resumable: lewati (toko,periode,tanggal) yang barisnya sudah punya 'pesanan'.
"""

import calendar  # noqa: F401
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
from etl.load import simpan_penjualan

WIB = timezone(timedelta(hours=7))
URL = "https://seller.shopee.co.id/api/mydata/v4/product/performance/"
HARI = 90


def _ts(dt):
    return int(dt.timestamp())


def list_bulanan():
    now = datetime.now(WIB); out = []; y, m = 2025, 1
    while (y, m) < (now.year, now.month):
        start = datetime(y, m, 1, tzinfo=WIB)
        nxt = datetime(y + 1, 1, 1, tzinfo=WIB) if m == 12 else datetime(y, m + 1, 1, tzinfo=WIB)
        out.append((start, _ts(start), _ts(nxt), "month"))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def list_mingguan():
    awal = datetime(2025, 1, 1, tzinfo=WIB); senin = awal - timedelta(days=awal.weekday())
    if senin < awal:
        senin += timedelta(days=7)
    now = datetime.now(WIB)
    senin_ini = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    out = []
    while senin < senin_ini:
        out.append((senin, _ts(senin), _ts(senin + timedelta(days=7)), "week"))
        senin += timedelta(days=7)
    return out


def list_harian(n=HARI):
    now = datetime.now(WIB)
    kemarin = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    out = []
    for i in range(n):
        d = kemarin - timedelta(days=i)
        out.append((d, _ts(d), _ts(d + timedelta(days=1)), "day"))
    return list(reversed(out))


PERIODE = {"bulanan": list_bulanan, "mingguan": list_mingguan, "harian": list_harian}


def _params(session, page, start, end, period):
    return {
        "SPC_CDS": session["params"]["SPC_CDS"],
        "SPC_CDS_VER": session["params"]["SPC_CDS_VER"],
        "start_time": start, "end_time": end, "period": period,
        "keyword": "", "category_type": "shopee", "category_id": -1,
        "page_size": 50, "page_num": page, "order_type": "confirmed",
        "order_by": "confirmed_sales.desc",
    }


def _int(x):
    try:
        return int(x or 0)
    except (TypeError, ValueError):
        return 0


def tarik(username, session, start, end, period, gran, mulai):
    page = 1; total = 0; out = []
    while True:
        result = None
        for _ in range(3):
            try:
                result = api_get(URL, scfg.grab_headers(session),
                                 _params(session, page, start, end, period))["result"]
                break
            except SesiKedaluwarsa:
                session["refresh"]()
            except Exception as ex:
                s = str(ex).lower()
                # data periode ini belum siap di Shopee / di luar batas -> skip cepat (jangan loop)
                if "ready" in s or "60001" in s or "month" in s:
                    return out
                try:
                    session["refresh"]()
                except Exception:
                    pass
        if result is None:
            break
        items = result.get("items", [])
        total = int(result.get("total", 0)) or total
        if not items:
            break
        aktif = 0
        for it in items:
            penj = _int(it.get("confirmed_sales")); peng = _int(it.get("uv"))
            if penj == 0 and peng == 0:
                continue
            aktif += 1
            out.append({
                "toko": username, "produk_id": int(it["id"]),
                "nama_produk": str(it.get("name", "")) or None,
                "sku_induk": str(it.get("sku", "")) or None,
                "periode": gran, "periode_mulai": mulai,
                "pengunjung": peng, "keranjang": _int(it.get("add_to_cart_buyers")),
                "unit_pesanan": _int(it.get("confirmed_units")), "penjualan": penj,
                "pesanan": _int(it.get("confirmed_orders")), "pembeli": _int(it.get("confirmed_buyers")),
                "extra": {"ctr": it.get("ctr"), "pv": it.get("pv"),
                          "conv": it.get("confirmed_order_conversion_rate"), "sumber": "pull"},
            })
        if aktif == 0:
            break
        if total and page * 50 >= total:
            break
        page += 1
        time.sleep(random.uniform(0.3, 0.8))
    return out


def main():
    if len(sys.argv) < 3 or sys.argv[1] not in PERIODE:
        print("Pakai: python -m etl.pull_penjualan [bulanan|mingguan|harian] [all|username] [n_hari?]")
        return
    gran, target = sys.argv[1], sys.argv[2]
    plist = PERIODE[gran]() if not (gran == "harian" and len(sys.argv) >= 4) else list_harian(int(sys.argv[3]))
    toko = (scfg.SHOP_DATABASE if target == "all" else {target: scfg.SHOP_DATABASE[target]})

    eng = get_engine()
    with eng.connect() as c:
        peta = {u: i for u, i in c.execute(text("select username, toko_id from dim_toko")).fetchall()}

    print(colorama.Fore.LIGHTCYAN_EX +
          f"\nPULL PENJUALAN {gran.upper()} — {len(toko)} toko x {len(plist)} periode\n" +
          colorama.Style.RESET_ALL)
    grand = 0
    for username, info in toko.items():
        nama = info["name"]; tid = peta.get(username)
        try:
            session = grab_session(shop=username, i=info["i"])
        except Exception as ex:
            print(colorama.Fore.RED + f"[{nama}] gagal sesi: {ex} — skip" + colorama.Style.RESET_ALL); continue
        ditarik = dilewati = baris = 0
        for mulai, s, e, per in plist:
            with eng.connect() as c:
                ada = c.execute(text("""select 1 from fact_penjualan
                    where toko_id=:t and periode=:p and periode_mulai=:m and pesanan is not null limit 1"""),
                    {"t": tid, "p": gran, "m": mulai}).first()
            if ada:
                dilewati += 1; continue
            try:
                rows = tarik(username, session, s, e, per, gran, mulai)
                n = simpan_penjualan(rows) if rows else 0
                ditarik += 1; baris += n
                print(f"  [{nama}] {mulai:%Y-%m-%d} -> {n} baris")
            except Exception as ex:
                print(colorama.Fore.RED + f"  [{nama}] {mulai:%Y-%m-%d} ERROR: {ex}" + colorama.Style.RESET_ALL)
            time.sleep(random.uniform(0.5, 1.2))
        grand += baris
        print(colorama.Fore.LIGHTGREEN_EX +
              f"[{nama}] selesai: {baris} baris ({ditarik} ditarik, {dilewati} dilewati)\n" +
              colorama.Style.RESET_ALL)
    close_session()
    print(colorama.Fore.LIGHTCYAN_EX + f"PULL PENJUALAN {gran.upper()} SELESAI — total {grand} baris." +
          colorama.Style.RESET_ALL)


if __name__ == "__main__":
    main()
