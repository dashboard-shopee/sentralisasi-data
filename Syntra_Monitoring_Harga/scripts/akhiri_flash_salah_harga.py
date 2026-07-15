"""scripts/akhiri_flash_salah_harga.py — ONE-OFF: akhiri SEMUA sesi flash Kimmioshop yang
dibikin SEBELUM fix per-model (M4, 15 Jul) — harganya salah (model murah ikut harga model
mahal dalam 1 item, mis. Rp29.800 ke-flash-in Rp35.790). Provisioning mingguan ga bisa
ngebenerin sendiri karena semua slot 7 hari udah kepenuhan sesi lama ini.

Pakai stop_sesi (POST set_shop_flash_sale {flash_sale_id,time_slot_id,status:2}) — sama
persis endpoint yang dipakai bot buat takedown flash biasa (M4). Hormat config.DRY_RUN.

Jalanin: python scripts/akhiri_flash_salah_harga.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from modules.db import get_engine
from modules.session import grab_session, close_session
from modules import flash_sale_daftar as FSD
import config

TOKO = "kimmioshop"
NAMA_TOKO = "Kimmioshop"


def sesi_aktif_upcoming():
    with get_engine().connect() as c:
        rows = c.execute(text("""
            select flash_sale_id, timeslot_id
            from harga_fakta_flash_sesi
            where toko=:t and end_time >= now()
            order by start_time
        """), {"t": NAMA_TOKO}).fetchall()
    return [(int(r.flash_sale_id), int(r.timeslot_id)) for r in rows]


def main():
    sesi = sesi_aktif_upcoming()
    print(f"[akhiri-flash] {len(sesi)} sesi aktif/upcoming ditemukan di DB (toko={NAMA_TOKO})")
    if not sesi:
        print("[akhiri-flash] Tidak ada sesi — selesai.")
        return
    if config.DRY_RUN:
        print("[akhiri-flash] ⚠️ MODE_LIVE=False (DRY) — SIMULASI doang, ga nyentuh Shopee.")
    else:
        print("[akhiri-flash] 🔴 MODE_LIVE=True — LIVE, beneran akhirin sesi di Shopee.")

    info = config.SHOP_DATABASE[TOKO]
    session = grab_session(shop=TOKO, i=info["i"])
    ok = gagal = 0
    for fsid, tslot in sesi:
        try:
            FSD.stop_sesi(session, fsid, tslot)
            ok += 1
        except Exception as e:
            gagal += 1
            print(f"[akhiri-flash] GAGAL sesi {fsid}: {type(e).__name__}: {e}")
    close_session()
    print(f"[akhiri-flash] SELESAI — {ok} sesi diakhirin, {gagal} gagal")


if __name__ == "__main__":
    main()
