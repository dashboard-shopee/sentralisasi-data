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
from modules.sql_harga import simpan_olah_data, baca_baris_rubah, tulis_alasan, baca_proteksi_komisi
from modules.update_harga import update_harga
from modules.log_siklus import catat_fase


def _t():
    return datetime.now().strftime("%H:%M:%S")


def jalankan():
    toko = config.daftar_toko_aktif()
    nama = ", ".join(info["name"] for info in toko.values())
    print(colorama.Fore.LIGHTCYAN_EX
          + f"\n[{_t()}] === FASE 1: GRAB PRODUK -> SQL ({len(toko)} toko: {nama}) ==="
          + colorama.Style.RESET_ALL)
    total = 0
    n_gagal = 0
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
            n_gagal += 1
            print(colorama.Fore.RED
                  + f"[{_t()}] [{info['name']}] GAGAL: {e}"
                  + colorama.Style.RESET_ALL)
    close_session()
    # Catat jejak fase grab -> dashboard (halaman Harga + menu Log)
    catat_fase("grab",
               status="gagal" if (total == 0 and n_gagal) else "ok",
               keterangan=f"{total} variasi, {len(toko)} toko" + (f", {n_gagal} toko gagal" if n_gagal else ""))

    # ── AMBIL HPP dari Jubelio -> erp_sku_list.hpp (token cache, browser cuma kalau expired) ──
    try:
        from modules.jubelio import sync_hpp
        ditarik, terupdate = sync_hpp()
        catat_fase("hpp", keterangan=f"{terupdate} sku HPP di-update (dari {ditarik} Jubelio)")
    except Exception as e:
        print(colorama.Fore.RED + f"[{_t()}] HPP Jubelio GAGAL: {e}" + colorama.Style.RESET_ALL)
        catat_fase("hpp", status="gagal", keterangan=str(e)[:120])
    print(colorama.Fore.LIGHTCYAN_EX
          + f"[{_t()}] === SELESAI — total {total} variasi tersimpan ke SQL ==="
          + colorama.Style.RESET_ALL)


def jalankan_rubah_harga():
    """FASE 2: baca target (K) dari harga_olah_data -> rubah harga Shopee (promo/harga dasar).
    Proteksi komisi: produk yang ada di harga_komisi_toko TIDAK diubah.
    DEFAULT DRY-RUN (config.DRY_RUN) -> cuma simulasi sampai env HARGA_LIVE=1."""
    toko = config.daftar_toko_aktif()
    mode = "DRY-RUN (simulasi)" if config.DRY_RUN else "LIVE (ubah Shopee beneran)"
    print(colorama.Fore.LIGHTCYAN_EX
          + f"\n[{_t()}] === FASE 2: RUBAH HARGA ({len(toko)} toko) — MODE: {mode} ==="
          + colorama.Style.RESET_ALL)
    total_proses = total_komisi = 0
    for username, info in toko.items():
        nama = info["name"]
        try:
            session = grab_session(shop=username, i=info["i"])
            baris = baca_baris_rubah(nama)
            komisi = baca_proteksi_komisi(username)
            # pisahkan produk komisi (jangan diubah) -> tandai alasan
            alasan = {}
            proses = []
            for b in baris:
                if b["sku"] and b["sku"].strip().upper() in komisi:
                    alasan[b["row"]] = "Komisi Aktif - harga tidak diubah"
                else:
                    proses.append(b)
            total_komisi += len(baris) - len(proses)
            # rubah harga (DRY/LIVE) -> dapat alasan per (item,model)
            alasan.update(update_harga(username, session, proses))
            n = tulis_alasan(nama, alasan)
            total_proses += len(proses)
            print(colorama.Fore.LIGHTGREEN_EX
                  + f"[{_t()}] [{nama}] {len(proses)} diproses, {len(baris)-len(proses)} komisi-skip, {n} alasan ditulis"
                  + colorama.Style.RESET_ALL)
        except Exception as e:
            print(colorama.Fore.RED + f"[{_t()}] [{nama}] GAGAL: {e}" + colorama.Style.RESET_ALL)
    close_session()
    catat_fase("rubah_harga",
               keterangan=f"{total_proses} variasi diproses, {total_komisi} komisi-skip | {mode}")
    print(colorama.Fore.LIGHTCYAN_EX + f"[{_t()}] === FASE 2 SELESAI ({mode}) ===" + colorama.Style.RESET_ALL)


if __name__ == "__main__":
    arg = sys.argv[1].lower() if len(sys.argv) > 1 else ""
    if arg == "login":
        buka_login()
    elif arg in ("rubah", "rubah_harga", "2"):
        jalankan_rubah_harga()
    else:
        jalankan()
