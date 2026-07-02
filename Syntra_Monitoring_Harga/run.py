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
from modules.sql_harga import (simpan_olah_data, simpan_konteks, baca_baris_rubah,
                                tulis_alasan, baca_proteksi_komisi, baca_stok_habis,
                                isi_harga_diskon_kosong, verifikasi_toko)
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
    total_konteks = 0
    n_gagal = 0
    for username, info in toko.items():
        try:
            session = grab_session(shop=username, i=info["i"])
            rows, konteks = grab_produk(shop=username, nama_toko=info["name"], session=session)
            n = simpan_olah_data(rows)
            nk = simpan_konteks(info["name"], konteks)
            total += n
            total_konteks += nk
            print(colorama.Fore.LIGHTGREEN_EX
                  + f"[{_t()}] [{info['name']}] {n} variasi -> harga_olah_data, {nk} promo -> konteks"
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
               keterangan=f"{total} variasi, {total_konteks} keikutsertaan promo, {len(toko)} toko"
                          + (f", {n_gagal} toko gagal" if n_gagal else ""))

    # Isi Harga Diskon (per-SKU) utk SKU yg masih kosong tapi harga real sudah ada (mode).
    try:
        n_diskon = isi_harga_diskon_kosong()
        if n_diskon:
            print(colorama.Fore.LIGHTGREEN_EX
                  + f"[{_t()}] {n_diskon} SKU: Harga Diskon diisi dari mode (yg tadinya kosong)"
                  + colorama.Style.RESET_ALL)
    except Exception as e:
        print(colorama.Fore.RED + f"[{_t()}] isi Harga Diskon GAGAL: {e}" + colorama.Style.RESET_ALL)

    # (HPP Jubelio DIPINDAH ke Syntra_Iklan/etl/pull_erp.py — ikut alur ambil data ERP,
    #  supaya tidak ke-truncate & selalu segar. Syntra Harga tidak mengurus HPP lagi.)
    print(colorama.Fore.LIGHTCYAN_EX
          + f"[{_t()}] === SELESAI — total {total} variasi tersimpan ke SQL ==="
          + colorama.Style.RESET_ALL)


def _takedown_stok_campaign_flash(username, nama, i, session):
    """Keluarkan variasi STOK 0 dari CAMPAIGN & FLASH SALE (yg menahan stok terpisah,
    bisa kejual di harga campaign walau stok utama 0). Promo Toko TIDAK disentuh.
    Return jumlah variasi ter-takedown."""
    n = 0
    # Flash Sale — hanya kalau toko punya flash sale aktif (hemat: skip kalau ga ada).
    try:
        from modules import flash_sale as FS
        if FS.list_flash_sale(session):
            stok0 = baca_stok_habis(nama, None)          # semua stok-0 (jenis apa pun)
            n += FS.takedown_items(session, username, stok0)   # hanya yg beneran di flash sale
    except Exception as e:
        print(colorama.Fore.RED + f"[{_t()}] [{nama}] takedown stok flash sale gagal: {type(e).__name__}" + colorama.Style.RESET_ALL)
    # Campaign — variasi stok-0 yang konteksnya Campaign.
    try:
        camp = baca_stok_habis(nama, "Campaign")
        if camp:
            from modules.takedown_campaign import takedown_dari_campaign
            n += takedown_dari_campaign(session, username, i, camp)
    except Exception as e:
        print(colorama.Fore.RED + f"[{_t()}] [{nama}] takedown stok campaign gagal: {type(e).__name__}" + colorama.Style.RESET_ALL)
    return n


def jalankan_rubah_harga():
    """FASE 2: baca target (K) dari harga_olah_data -> rubah harga Shopee (promo/harga dasar).
    Proteksi komisi: produk yang ada di harga_komisi_toko TIDAK diubah.
    DEFAULT DRY-RUN (config.DRY_RUN) -> cuma simulasi sampai env HARGA_LIVE=1."""
    toko = config.daftar_toko_aktif()
    mode = "DRY-RUN (simulasi)" if config.DRY_RUN else "LIVE (ubah Shopee beneran)"
    print(colorama.Fore.LIGHTCYAN_EX
          + f"\n[{_t()}] === FASE 2: RUBAH HARGA ({len(toko)} toko) — MODE: {mode} ==="
          + colorama.Style.RESET_ALL)
    total_proses = total_komisi = total_stok0 = 0
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
            alasan.update(update_harga(username, session, proses, nama_toko=nama))
            n = tulis_alasan(nama, alasan)
            total_proses += len(proses)

            # STOK HABIS: variasi stok 0 yang masih di CAMPAIGN / FLASH SALE -> keluarkan
            # (mereka menahan stok terpisah, bisa kejual di harga campaign walau stok utama 0).
            # Promo Toko SENGAJA TIDAK dikeluarkan (biar tetap ikut promo saat restock).
            total_stok0 += _takedown_stok_campaign_flash(username, nama, info["i"], session)

            print(colorama.Fore.LIGHTGREEN_EX
                  + f"[{_t()}] [{nama}] {len(proses)} diproses, {len(baris)-len(proses)} komisi-skip, {n} alasan ditulis"
                  + colorama.Style.RESET_ALL)
        except Exception as e:
            print(colorama.Fore.RED + f"[{_t()}] [{nama}] GAGAL: {e}" + colorama.Style.RESET_ALL)
    close_session()
    catat_fase("rubah_harga",
               keterangan=f"{total_proses} diproses, {total_komisi} komisi-skip, "
                          f"{total_stok0} stok0-takedown campaign/flash | {mode}")
    print(colorama.Fore.LIGHTCYAN_EX + f"[{_t()}] === FASE 2 SELESAI ({mode}) ===" + colorama.Style.RESET_ALL)


def jalankan_verifikasi():
    """FASE 3: ambil ULANG harga terkini (re-grab) lalu banding Harga Real vs Target
    (pancing/Harga Diskon). Tulis verdict ke kolom `alasan` + selisih. Dipakai SETELAH
    Fase 2 utk memastikan perubahan harga benar-benar berlaku di Shopee."""
    toko = config.daftar_toko_aktif()
    print(colorama.Fore.LIGHTCYAN_EX
          + f"\n[{_t()}] === FASE 3: VERIFIKASI HARGA ({len(toko)} toko) ==="
          + colorama.Style.RESET_ALL)
    tot_sesuai = tot_belum = 0
    for username, info in toko.items():
        nama = info["name"]
        try:
            session = grab_session(shop=username, i=info["i"])
            # 1) ambil ulang harga terkini (refresh harga_tampil + sumber + konteks)
            rows, konteks = grab_produk(shop=username, nama_toko=nama, session=session)
            simpan_olah_data(rows)
            simpan_konteks(nama, konteks)
            # 2) banding real vs target -> tulis verdict
            sesuai, belum, tanpa = verifikasi_toko(nama)
            tot_sesuai += sesuai
            tot_belum += belum
            warna = colorama.Fore.LIGHTGREEN_EX if belum == 0 else colorama.Fore.YELLOW
            print(warna + f"[{_t()}] [{nama}] {sesuai} sesuai, {belum} belum, {tanpa} tanpa-target"
                  + colorama.Style.RESET_ALL)
        except Exception as e:
            print(colorama.Fore.RED + f"[{_t()}] [{nama}] GAGAL: {e}" + colorama.Style.RESET_ALL)
    close_session()
    catat_fase("verifikasi", keterangan=f"{tot_sesuai} sesuai, {tot_belum} belum sesuai")
    print(colorama.Fore.LIGHTCYAN_EX
          + f"[{_t()}] === FASE 3 SELESAI — {tot_sesuai} sesuai, {tot_belum} belum ==="
          + colorama.Style.RESET_ALL)


def jalankan_fase4():
    """FASE 4: PERPANJANG promo toko yang mau berakhir (duplikat) + BUAT DARI 0
    untuk toko yang belum punya promo toko. DEFAULT DRY-RUN (config.DRY_RUN)."""
    from modules.duplikat_promo import proses_duplikat_promo
    toko = config.daftar_toko_aktif()
    mode = "DRY-RUN (simulasi)" if config.DRY_RUN else "LIVE (bikin promo beneran)"
    print(colorama.Fore.LIGHTCYAN_EX
          + f"\n[{_t()}] === FASE 4: PERPANJANG/BUAT PROMO TOKO ({len(toko)} toko) — MODE: {mode} ==="
          + colorama.Style.RESET_ALL)
    n_ok = n_gagal = 0
    for username, info in toko.items():
        nama = info["name"]
        try:
            session = grab_session(shop=username, i=info["i"])
            baris = baca_baris_rubah(nama)
            proses_duplikat_promo(username, session, baris)
            n_ok += 1
        except Exception as e:
            n_gagal += 1
            print(colorama.Fore.RED + f"[{_t()}] [{nama}] GAGAL: {e}" + colorama.Style.RESET_ALL)
    close_session()
    catat_fase("duplikat_promo",
               status="gagal" if (n_ok == 0 and n_gagal) else "ok",
               keterangan=f"{n_ok} toko diproses" + (f", {n_gagal} gagal" if n_gagal else "") + f" | {mode}")
    print(colorama.Fore.LIGHTCYAN_EX + f"[{_t()}] === FASE 4 SELESAI ({mode}) ===" + colorama.Style.RESET_ALL)


_FASE = {1: jalankan, 2: jalankan_rubah_harga, 3: jalankan_verifikasi, 4: jalankan_fase4}


if __name__ == "__main__":
    arg = sys.argv[1].lower() if len(sys.argv) > 1 else ""
    if arg == "login":
        buka_login()
    elif arg in ("rubah", "rubah_harga", "2"):
        jalankan_rubah_harga()
    elif arg in ("verifikasi", "verif", "3"):
        jalankan_verifikasi()
    elif arg in ("fase4", "perpanjang", "4"):
        jalankan_fase4()
    elif arg in ("grab", "1"):
        jalankan()
    else:
        # Tanpa argumen -> ikuti config.FASE_AKTIF (bisa gabung, dijalankan berurutan).
        fase = getattr(config, "FASE_AKTIF", [1]) or [1]
        for f in fase:
            fn = _FASE.get(int(f))
            if fn:
                fn()
            else:
                print(colorama.Fore.RED + f"[run] FASE_AKTIF {f} tidak dikenal (pilih 1-4)" + colorama.Style.RESET_ALL)
