"""run.py — Syntra_Monitoring_Harga | Orkestrator + Scheduler.

Arsitektur BARU 4 fase: 1.Fakta -> 2.Masalah -> 3.Solusi -> 4.Laporan.
Sekarang yang aktif: FASE 1 (Pengumpul Fakta, READ-ONLY) + scheduler 24 jam.

Scheduler (pola sama Syntra_Iklan): nyala terus, detak tiap 3 detik (tanpa log),
nembak 1x/jam di menit config.MENIT_RUNNING. Tiap tier fakta dipicu by JAM/HARI/TGL
(config): JAM = grab produk (harga+stok+konteks); harian = Garansi+Campaign;
mingguan = Flash+Voucher+Paket; bulanan = housekeeping.

Browser/CMD/login SENDIRI (Chrome port 9556) -> tidak bentrok dgn Syntra_Iklan.

Pemakaian:
  python run.py login          # login Shopee sekali
  python run.py                # SCHEDULER 24 jam (Fase 1) — produksi
  python run.py grab           # tes 1 siklus Fase 1 SEKARANG (tier ikut jam saat ini)
  python run.py grab full      # tes 1 siklus Fase 1 + PAKSA semua tier (harian+mingguan+bulanan)
  python run.py rubah|verifikasi|fase4   # LEGACY Fase 2-4 lama (akan di-port ke model baru)
"""
import sys
import time
from datetime import datetime
import colorama; colorama.init()
import config
from modules.session import grab_session, close_session, buka_login
from modules import jam_siklus
from modules import fakta
from modules.sql_harga import isi_harga_diskon_kosong
from modules.log_siklus import catat_fase


def _t():
    return datetime.now().strftime("%H:%M:%S")


def _aman(nama, label, fn):
    """Jalankan collector, tangkap error biar 1 collector gagal tak matiin sisanya."""
    try:
        return fn()
    except Exception as e:
        print(colorama.Fore.RED + f"[{_t()}] [{nama}] fakta {label} GAGAL: {type(e).__name__}: {e}"
              + colorama.Style.RESET_ALL)
        return None


# ══════════════════════════════════════════════════════════════════
#  FASE 1 — PENGUMPUL FAKTA (READ-ONLY). Loop per-toko, harvest sesi 1x.
# ══════════════════════════════════════════════════════════════════
def siklus_fase1(paksa_semua=False):
    """paksa_semua=True -> semua tier (harian/mingguan/bulanan) dipaksa nyala.
    Buat TES manual (`python run.py grab full`) tanpa nunggu jam-nya pas."""
    jam_siklus.kunci()
    skr = jam_siklus.now()
    jam = skr.hour
    hari = config.HARI_ID.get(skr.strftime("%A"), "")
    tgl = skr.day

    due_harian = paksa_semua or (jam == int(config.JAM_FAKTA_HARIAN))
    due_mingguan = paksa_semua or (hari == config.HARI_FAKTA_MINGGUAN and jam == int(config.JAM_FAKTA_MINGGUAN))
    due_bulanan = paksa_semua or (tgl == int(config.TANGGAL_FAKTA_BULANAN) and jam == int(config.JAM_FAKTA_BULANAN))

    toko = config.daftar_toko_aktif()
    tier = "JAM" + (" +HARIAN" if due_harian else "") + (" +MINGGUAN" if due_mingguan else "") + (" +BULANAN" if due_bulanan else "")
    print(colorama.Fore.LIGHTCYAN_EX
          + f"\n[{_t()}] === FASE 1 (FAKTA) — {len(toko)} toko — tier: {tier} ==="
          + colorama.Style.RESET_ALL)

    T = {"grab": 0, "konteks": 0, "gagal": 0}
    for username, info in toko.items():
        nama = info["name"]
        try:
            session = grab_session(shop=username, i=info["i"])     # HARVEST SESI 1x utk semua tier
            # ── TIER JAM (selalu) ──
            n, nk = fakta.fakta_produk(username, nama, session)
            T["grab"] += n; T["konteks"] += nk
            print(colorama.Fore.LIGHTGREEN_EX
                  + f"[{_t()}] [{nama}] Produk: {n} variasi, {nk} promo->konteks"
                  + colorama.Style.RESET_ALL)
            # ── TIER HARIAN ──
            if due_harian:
                _aman(nama, "garansi", lambda: fakta.fakta_garansi(nama, session))
                _aman(nama, "campaign", lambda: fakta.fakta_campaign(nama, session))
            # ── TIER MINGGUAN ──
            if due_mingguan:
                _aman(nama, "flash", lambda: fakta.fakta_flash(nama, session))
                _aman(nama, "voucher", lambda: fakta.fakta_voucher(nama, session))
                _aman(nama, "paket", lambda: fakta.fakta_paket(nama, session))
            print(colorama.Fore.CYAN + f"[{_t()}] [{nama}] --- SELESAI ---" + colorama.Style.RESET_ALL)
        except Exception as e:
            T["gagal"] += 1
            print(colorama.Fore.RED + f"[{_t()}] [{nama}] GAGAL: {e}" + colorama.Style.RESET_ALL)
    close_session()

    # Pass akhir (butuh data semua toko): isi Harga Diskon utk SKU baru yg kosong.
    try:
        nd = isi_harga_diskon_kosong()
        if nd:
            print(colorama.Fore.LIGHTGREEN_EX + f"[{_t()}] {nd} SKU: Harga Diskon diisi dari mode" + colorama.Style.RESET_ALL)
    except Exception as e:
        print(colorama.Fore.RED + f"[{_t()}] isi Harga Diskon GAGAL: {e}" + colorama.Style.RESET_ALL)

    # ── TIER BULANAN: housekeeping (global, sekali) ──
    if due_bulanan:
        _aman("-", "housekeeping", fakta.housekeeping)

    # ── CATAT JEJAK tiap tier -> dashboard (menu Log) ──
    g = f", {T['gagal']} toko gagal" if T["gagal"] else ""
    # Tier jam = grab produk -> pakai pemicu 'grab' yg SUDAH terdaftar di Log (reuse, bukan bikin baru).
    catat_fase("grab", status="gagal" if (T["grab"] == 0 and T["gagal"]) else "ok",
               keterangan=f"{T['grab']} variasi, {T['konteks']} promo, {len(toko)} toko{g}")
    if due_harian:
        catat_fase("fakta_harian", keterangan=f"{len(toko)} toko | Garansi + Campaign")
    if due_mingguan:
        catat_fase("fakta_mingguan", keterangan=f"{len(toko)} toko | Flash + Voucher + Paket")
    if due_bulanan:
        catat_fase("fakta_bulanan", keterangan="housekeeping (prune fakta yatim)")

    print(colorama.Fore.LIGHTCYAN_EX + f"[{_t()}] === FASE 1 (FAKTA) SELESAI — tier: {tier} ===" + colorama.Style.RESET_ALL)


# ══════════════════════════════════════════════════════════════════
#  SCHEDULER 24 JAM (detak 3 detik tanpa log, nembak 1x/jam di menit :MM)
# ══════════════════════════════════════════════════════════════════
def scheduler():
    menit = int(config.MENIT_RUNNING)
    print(colorama.Fore.LIGHTMAGENTA_EX
          + f"[{_t()}] Scheduler HARGA aktif — Fase 1 (Fakta). Nembak tiap jam di menit {menit:02d}. "
          + f"Harian@{config.JAM_FAKTA_HARIAN}:00 · Mingguan {config.HARI_FAKTA_MINGGUAN}@{config.JAM_FAKTA_MINGGUAN}:00 · "
          + f"Bulanan tgl-{config.TANGGAL_FAKTA_BULANAN}@{config.JAM_FAKTA_BULANAN}:00"
          + colorama.Style.RESET_ALL)
    jam_terakhir = None
    while True:
        time.sleep(3)                                  # DETAK (tanpa log biar terminal bersih)
        now = datetime.now()
        if now.minute == menit and now.hour != jam_terakhir:
            jam_terakhir = now.hour
            try:
                siklus_fase1()
            except Exception as e:
                print(colorama.Fore.RED + f"[{_t()}] SIKLUS GAGAL (di-skip, lanjut jam berikutnya): {e}"
                      + colorama.Style.RESET_ALL)


# ══════════════════════════════════════════════════════════════════
#  LEGACY — Fase 2-4 lama (dipertahankan sementara; akan di-port ke model baru).
#  Dipanggil hanya via argumen eksplisit rubah/verifikasi/fase4.
# ══════════════════════════════════════════════════════════════════
def _legacy_jalankan(fases):
    from modules.grab_produk import grab_produk
    from modules.sql_harga import (simpan_olah_data, simpan_konteks, baca_baris_rubah,
                                    tulis_alasan, baca_proteksi_komisi, baca_stok_habis, verifikasi_toko)
    from modules.update_harga import update_harga
    JEDA_VERIF = int(getattr(config, "JEDA_VERIFIKASI_DETIK", 30))
    toko = config.daftar_toko_aktif()
    mode = "DRY-RUN (simulasi)" if config.DRY_RUN else "LIVE (ubah Shopee beneran)"
    label = " + ".join({2: "Rubah", 3: "Verifikasi", 4: "Perpanjang"}[f] for f in fases)
    print(colorama.Fore.LIGHTCYAN_EX + f"\n[{_t()}] === LEGACY [{label}] — {len(toko)} toko — MODE: {mode} ===" + colorama.Style.RESET_ALL)
    for username, info in toko.items():
        nama = info["name"]
        try:
            session = grab_session(shop=username, i=info["i"])
            if 2 in fases:
                baris = baca_baris_rubah(nama)
                komisi = baca_proteksi_komisi(username)
                alasan, proses = {}, []
                for b in baris:
                    if b["sku"] and b["sku"].strip().upper() in komisi:
                        alasan[b["row"]] = "Komisi Aktif - harga tidak diubah"
                    else:
                        proses.append(b)
                alasan.update(update_harga(username, session, proses, nama_toko=nama))
                tulis_alasan(nama, alasan)
                print(colorama.Fore.LIGHTGREEN_EX + f"[{_t()}] [{nama}] Rubah: {len(proses)} diproses, {len(baris)-len(proses)} komisi-skip" + colorama.Style.RESET_ALL)
            if 3 in fases:
                if JEDA_VERIF > 0:
                    time.sleep(JEDA_VERIF)
                rows, konteks = grab_produk(shop=username, nama_toko=nama, session=session)
                simpan_olah_data(rows); simpan_konteks(nama, konteks)
                se, be, ta = verifikasi_toko(nama)
                print(colorama.Fore.LIGHTGREEN_EX + f"[{_t()}] [{nama}] Verifikasi: {se} sesuai, {be} belum, {ta} tanpa-target" + colorama.Style.RESET_ALL)
            if 4 in fases:
                from modules.duplikat_promo import proses_duplikat_promo
                proses_duplikat_promo(username, session, baca_baris_rubah(nama))
                print(colorama.Fore.LIGHTGREEN_EX + f"[{_t()}] [{nama}] Perpanjang promo: dicek" + colorama.Style.RESET_ALL)
        except Exception as e:
            print(colorama.Fore.RED + f"[{_t()}] [{nama}] GAGAL: {e}" + colorama.Style.RESET_ALL)
    close_session()
    print(colorama.Fore.LIGHTCYAN_EX + f"[{_t()}] === LEGACY [{label}] SELESAI ===" + colorama.Style.RESET_ALL)


if __name__ == "__main__":
    arg = sys.argv[1].lower() if len(sys.argv) > 1 else ""
    if arg == "login":
        buka_login()
    elif arg in ("grab", "fase1", "test", "1"):
        paksa = len(sys.argv) > 2 and sys.argv[2].lower() in ("full", "semua", "all")
        siklus_fase1(paksa_semua=paksa)
    elif arg in ("rubah", "rubah_harga", "2"):
        _legacy_jalankan([2])
    elif arg in ("verifikasi", "verif", "3"):
        _legacy_jalankan([3])
    elif arg in ("fase4", "perpanjang", "4"):
        _legacy_jalankan([4])
    else:
        scheduler()
