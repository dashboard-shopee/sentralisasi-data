"""run.py — Syntra_Monitoring_Harga | Orkestrator.

Migrasi bot 02 (Monitoring Harga) dari Google Sheet -> SQL (Supabase).
Browser/CMD/login SENDIRI (Chrome port 9556) -> tidak bentrok dgn Syntra_Iklan.

FASE 1 (aktif sekarang): ambil produk berstok dari Shopee -> tulis harga_olah_data.
  Cuma BACA dari Shopee + tulis SQL. TIDAK mengubah harga apa pun.

Pemakaian:
  python run.py login   # login Shopee sekali (buka browser profil bot)
  python run.py         # grab semua toko aktif -> SQL
  python run.py test    # alias (sama dgn tanpa argumen)
"""
import sys
from datetime import datetime
import colorama; colorama.init()
import config
from modules.session import grab_session, close_session, buka_login
from modules.grab_produk import grab_produk
from modules.sql_harga import simpan_olah_data


def _t():
    return datetime.now().strftime("%H:%M:%S")


def jalankan():
    toko = config.daftar_toko_aktif()
    nama = ", ".join(info["name"] for info in toko.values())
    print(colorama.Fore.LIGHTCYAN_EX
          + f"\n[{_t()}] === FASE 1: GRAB PRODUK -> SQL ({len(toko)} toko: {nama}) ==="
          + colorama.Style.RESET_ALL)
    total = 0
    for username, info in toko.items():
        try:
            session = grab_session(shop=username, i=info["i"])
            rows = grab_produk(shop=username, nama_toko=info["name"], session=session)
            n = simpan_olah_data(rows)
            total += n
            print(colorama.Fore.LIGHTGREEN_EX
                  + f"[{_t()}] [{info['name']}] {n} variasi -> harga_olah_data"
                  + colorama.Style.RESET_ALL)
        except Exception as e:
            print(colorama.Fore.RED
                  + f"[{_t()}] [{info['name']}] GAGAL: {e}"
                  + colorama.Style.RESET_ALL)
    close_session()
    print(colorama.Fore.LIGHTCYAN_EX
          + f"[{_t()}] === SELESAI — total {total} variasi tersimpan ke SQL ==="
          + colorama.Style.RESET_ALL)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1].lower() == "login":
        buka_login()
    else:
        jalankan()
