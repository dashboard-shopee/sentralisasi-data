"""scripts/hapus_semua_flash.py — ONE-OFF: hapus (status=0) SEMUA sesi flash Kimmioshop
(baik yang masih aktif/mendatang maupun yang udah berakhir) buat ngosongin semua slot
sebelum tes ulang tes_harga.bat (verifikasi endpoint hapus_sesi hasil sniff 15 Jul, sekalian
mastiin slot beneran kebuka lagi abis dihapus).

Sesi status=1 (aktif/mendatang) -> stop (status 2) dulu baru hapus (status 0), sesuai alur
Shopee (cuma bisa hapus dari sesi yg udah berakhir). Sesi status=2 (udah berakhir) -> hapus
langsung. Hormat config.DRY_RUN.

Jalanin: python scripts/hapus_semua_flash.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.session import grab_session, close_session
from modules import flash_sale as FS
from modules import flash_sale_daftar as FSD
import config

TOKO = "kimmioshop"


def main():
    info = config.SHOP_DATABASE[TOKO]
    session = grab_session(shop=TOKO, i=info["i"])
    sesi = FS.list_flash_sale(session, hanya_aktif=True)
    print(f"[hapus-flash] {len(sesi)} sesi aktif/upcoming/berakhir ditemukan (toko={TOKO})")
    if not sesi:
        print("[hapus-flash] Tidak ada sesi — selesai.")
        close_session()
        return
    if config.DRY_RUN:
        print("[hapus-flash] MODE_LIVE=False (DRY) — SIMULASI doang, ga nyentuh Shopee.")
    else:
        print("[hapus-flash] MODE_LIVE=True — LIVE, beneran hapus semua sesi di Shopee.")

    ok = gagal = 0
    for s in sesi:
        fsid, tslot, status = s["flash_sale_id"], s["timeslot_id"], s["status"]
        try:
            if status == 1:
                FSD.stop_sesi(session, fsid, tslot)
            FSD.hapus_sesi(session, fsid, tslot)
            ok += 1
        except Exception as e:
            gagal += 1
            print(f"[hapus-flash] GAGAL sesi {fsid} (status={status}): {type(e).__name__}: {e}")
    close_session()
    print(f"[hapus-flash] SELESAI — {ok} sesi dihapus, {gagal} gagal")


if __name__ == "__main__":
    main()
