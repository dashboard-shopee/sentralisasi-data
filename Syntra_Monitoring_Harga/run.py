"""run.py — Syntra_Monitoring_Harga | Orkestrator (loop PER-TOKO).

Migrasi bot 02 (Monitoring Harga) dari Google Sheet -> SQL (Supabase).
Browser/CMD/login SENDIRI (Chrome port 9556) -> tidak bentrok dgn Syntra_Iklan.

OPSI A (percepat): tiap toko di-HARVEST SESI SEKALI, lalu SEMUA fase (grab/rubah/
verifikasi/perpanjang) dijalankan utk toko itu pakai sesi yg sama, baru pindah toko
berikutnya. Hemat 2-3x harvest browser dibanding model lama (fase-major).

Fase (config.FASE_AKTIF): 1=grab · 2=rubah harga · 3=verifikasi · 4=perpanjang promo.

Pemakaian:
  python run.py login          # login Shopee sekali
  python run.py                # ikuti config.FASE_AKTIF (loop per-toko)
  python run.py grab|rubah|verifikasi|fase4   # 1 fase saja (semua toko)
"""
import sys
import time
from datetime import datetime
import colorama; colorama.init()
import config
from modules.session import grab_session, close_session, buka_login
from modules.grab_produk import grab_produk
from modules.sql_harga import (simpan_olah_data, simpan_konteks, baca_baris_rubah,
                                tulis_alasan, baca_proteksi_komisi, baca_stok_habis,
                                isi_harga_diskon_kosong, verifikasi_toko)
from modules.update_harga import update_harga
from modules.log_siklus import catat_fase

# Jeda sebelum re-grab Fase 3 (beri waktu Shopee propagasi harga sesudah Fase 2 ubah).
JEDA_VERIF = int(getattr(config, "JEDA_VERIFIKASI_DETIK", 30))


def _t():
    return datetime.now().strftime("%H:%M:%S")


# ── LANGKAH PER-TOKO (pakai sesi yg SUDAH dipanen) ──
def _grab_toko(username, info, session):
    rows, konteks = grab_produk(shop=username, nama_toko=info["name"], session=session)
    n = simpan_olah_data(rows)
    nk = simpan_konteks(info["name"], konteks)
    return n, nk


def _takedown_stok_campaign_flash(username, nama, i, session):
    """Keluarkan variasi STOK 0 dari CAMPAIGN & FLASH SALE (menahan stok terpisah).
    Promo Toko SENGAJA TIDAK disentuh. Return jumlah ter-takedown."""
    n = 0
    try:
        from modules import flash_sale as FS
        if FS.list_flash_sale(session):
            n += FS.takedown_items(session, username, baca_stok_habis(nama, None))
    except Exception as e:
        print(colorama.Fore.RED + f"[{_t()}] [{nama}] takedown stok flash sale gagal: {type(e).__name__}" + colorama.Style.RESET_ALL)
    try:
        camp = baca_stok_habis(nama, "Campaign")
        if camp:
            from modules.takedown_campaign import takedown_dari_campaign
            n += takedown_dari_campaign(session, username, i, camp)
    except Exception as e:
        print(colorama.Fore.RED + f"[{_t()}] [{nama}] takedown stok campaign gagal: {type(e).__name__}" + colorama.Style.RESET_ALL)
    return n


def _rubah_toko(username, info, session):
    nama = info["name"]
    baris = baca_baris_rubah(nama)
    komisi = baca_proteksi_komisi(username)      # komisi AKTIF (harga_jual>0) -> dilindungi
    alasan = {}
    proses = []
    for b in baris:
        if b["sku"] and b["sku"].strip().upper() in komisi:
            alasan[b["row"]] = "Komisi Aktif - harga tidak diubah"
        else:
            proses.append(b)
    alasan.update(update_harga(username, session, proses, nama_toko=nama))
    tulis_alasan(nama, alasan)
    stok0 = _takedown_stok_campaign_flash(username, nama, info["i"], session)
    return len(proses), len(baris) - len(proses), stok0


def _verifikasi_toko_step(username, info, session):
    nama = info["name"]
    if JEDA_VERIF > 0:
        time.sleep(JEDA_VERIF)                   # beri waktu propagasi harga
    rows, konteks = grab_produk(shop=username, nama_toko=nama, session=session)
    simpan_olah_data(rows)
    simpan_konteks(nama, konteks)
    return verifikasi_toko(nama)


def _perpanjang_toko(username, info, session):
    from modules.duplikat_promo import proses_duplikat_promo
    proses_duplikat_promo(username, session, baca_baris_rubah(info["name"]))


# ── ORKESTRATOR: loop per-toko, harvest 1x, jalankan fase yg diminta ──
def jalankan_semua(fases):
    fases = [int(f) for f in fases if int(f) in (1, 2, 3, 4)] or [1]
    toko = config.daftar_toko_aktif()
    mode = "DRY-RUN (simulasi)" if config.DRY_RUN else "LIVE (ubah Shopee beneran)"
    label = " + ".join({1: "Grab", 2: "Rubah", 3: "Verifikasi", 4: "Perpanjang"}[f] for f in fases)
    print(colorama.Fore.LIGHTCYAN_EX
          + f"\n[{_t()}] === MULAI [{label}] — {len(toko)} toko (loop per-toko) — MODE: {mode} ==="
          + colorama.Style.RESET_ALL)
    T = dict(grab=0, konteks=0, proses=0, komisi=0, stok0=0, sesuai=0, belum=0, perpanjang=0, gagal=0)
    for username, info in toko.items():
        nama = info["name"]
        try:
            session = grab_session(shop=username, i=info["i"])     # HARVEST SESI 1x utk semua fase
            if 1 in fases:
                n, nk = _grab_toko(username, info, session)
                T["grab"] += n; T["konteks"] += nk
                print(colorama.Fore.LIGHTGREEN_EX + f"[{_t()}] [{nama}] Grab: {n} variasi, {nk} promo->konteks" + colorama.Style.RESET_ALL)
            if 2 in fases:
                p, k, s = _rubah_toko(username, info, session)
                T["proses"] += p; T["komisi"] += k; T["stok0"] += s
                print(colorama.Fore.LIGHTGREEN_EX + f"[{_t()}] [{nama}] Rubah: {p} diproses, {k} komisi-skip, {s} stok0-takedown" + colorama.Style.RESET_ALL)
            if 3 in fases:
                se, be, ta = _verifikasi_toko_step(username, info, session)
                T["sesuai"] += se; T["belum"] += be
                print((colorama.Fore.LIGHTGREEN_EX if be == 0 else colorama.Fore.YELLOW)
                      + f"[{_t()}] [{nama}] Verifikasi: {se} sesuai, {be} belum, {ta} tanpa-target" + colorama.Style.RESET_ALL)
            if 4 in fases:
                _perpanjang_toko(username, info, session)
                T["perpanjang"] += 1
                print(colorama.Fore.LIGHTGREEN_EX + f"[{_t()}] [{nama}] Perpanjang promo: dicek" + colorama.Style.RESET_ALL)
            print(colorama.Fore.CYAN + f"[{_t()}] [{nama}] --- SELESAI ({label}) ---" + colorama.Style.RESET_ALL)
        except Exception as e:
            T["gagal"] += 1
            print(colorama.Fore.RED + f"[{_t()}] [{nama}] GAGAL: {e}" + colorama.Style.RESET_ALL)
    close_session()

    # Pass akhir: isi Harga Diskon utk SKU baru yg kosong (butuh data semua toko).
    if 1 in fases:
        try:
            nd = isi_harga_diskon_kosong()
            if nd:
                print(colorama.Fore.LIGHTGREEN_EX + f"[{_t()}] {nd} SKU: Harga Diskon diisi dari mode" + colorama.Style.RESET_ALL)
        except Exception as e:
            print(colorama.Fore.RED + f"[{_t()}] isi Harga Diskon GAGAL: {e}" + colorama.Style.RESET_ALL)

    # Catat jejak tiap fase yg dijalankan -> dashboard (menu Log).
    g = f", {T['gagal']} toko gagal" if T["gagal"] else ""
    if 1 in fases:
        catat_fase("grab", status="gagal" if (T["grab"] == 0 and T["gagal"]) else "ok",
                   keterangan=f"{T['grab']} variasi, {T['konteks']} promo, {len(toko)} toko{g}")
    if 2 in fases:
        catat_fase("rubah_harga", keterangan=f"{T['proses']} diproses, {T['komisi']} komisi-skip, {T['stok0']} stok0-takedown | {mode}")
    if 3 in fases:
        catat_fase("verifikasi", keterangan=f"{T['sesuai']} sesuai, {T['belum']} belum sesuai")
    if 4 in fases:
        catat_fase("duplikat_promo", keterangan=f"{T['perpanjang']} toko diproses | {mode}")
    print(colorama.Fore.LIGHTCYAN_EX + f"[{_t()}] === SELESAI [{label}] ({mode}) ===" + colorama.Style.RESET_ALL)


if __name__ == "__main__":
    arg = sys.argv[1].lower() if len(sys.argv) > 1 else ""
    if arg == "login":
        buka_login()
    elif arg in ("rubah", "rubah_harga", "2"):
        jalankan_semua([2])
    elif arg in ("verifikasi", "verif", "3"):
        jalankan_semua([3])
    elif arg in ("fase4", "perpanjang", "4"):
        jalankan_semua([4])
    elif arg in ("grab", "1"):
        jalankan_semua([1])
    else:
        jalankan_semua(getattr(config, "FASE_AKTIF", [1]) or [1])
