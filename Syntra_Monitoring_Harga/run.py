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
  python run.py kategori       # isi KATEGORI Shopee semua produk (incremental, aman diulang)
  python run.py fase2          # FASE 2 modul Harga: grab fresh -> diagnosa -> eksekusi (DRY-RUN paksa)
  python run.py komisi_cek     # VERIF READ komisi Shopee via requests (kena anti-bot 403) — read-only
  python run.py komisi_grab    # GRAB komisi Shopee via BROWSER (tangkap gql ber-SDK) -> harga_fakta_komisi
  python run.py komisi_inspect # EKSPLORASI DOM halaman komisi (buat desain set/takedown bagian C)
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
                _aman(nama, "promo_toko", lambda: fakta.fakta_promo_toko(username, nama, session))
            # ── TIER MINGGUAN ──
            if due_mingguan:
                _aman(nama, "flash", lambda: fakta.fakta_flash(nama, session))
                _aman(nama, "voucher", lambda: fakta.fakta_voucher(nama, session))
                _aman(nama, "paket", lambda: fakta.fakta_paket(nama, session))
                _aman(nama, "kategori", lambda: fakta.fakta_kategori(nama, session))  # incremental (capped)
            print(colorama.Fore.CYAN + f"[{_t()}] [{nama}] --- SELESAI ---" + colorama.Style.RESET_ALL)
        except Exception as e:
            T["gagal"] += 1
            print(colorama.Fore.RED + f"[{_t()}] [{nama}] GAGAL: {e}" + colorama.Style.RESET_ALL)
    close_session()

    # ── TIER HARIAN: GRAB KOMISI Shopee via BROWSER (bypass anti-bot). Jalan SETELAH loop +
    #    close_session() (port 9556 bebas). unattended -> interaktif=False (no input()).
    if due_harian:
        _aman("-", "komisi (browser)", lambda: grab_komisi_browser(interaktif=False))

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
#  FASE 2 (MASALAH+SOLUSI) modul HARGA — per-toko: grab FRESH -> diagnosa -> eksekusi.
#  ⚠️ v1 DRY-RUN DIPAKSA (belum diverifikasi live). Hapus paksa kalau udah yakin.
# ══════════════════════════════════════════════════════════════════
def jalankan_fase2():
    config.DRY_RUN = True   # PAKSA simulasi — v1 belum diverifikasi live (config MODE_LIVE bisa True)
    from modules import fase2_harga as F2
    jam_siklus.kunci()
    toko = config.daftar_toko_aktif()
    print(colorama.Fore.LIGHTCYAN_EX + f"\n[{_t()}] === FASE 2 (HARGA) — {len(toko)} toko — DRY-RUN (paksa) ===" + colorama.Style.RESET_ALL)
    for username, info in toko.items():
        nama = info["name"]
        try:
            session = grab_session(shop=username, i=info["i"])
            fakta.fakta_produk(username, nama, session)          # grab FRESH (wajib sebelum diagnosa)
            d = F2.diagnosa_toko(nama)
            kasus, aksi = F2.ringkas(d)
            print(colorama.Fore.WHITE + f"[{_t()}] [{nama}] diagnosa: {kasus} | aksi {aksi}" + colorama.Style.RESET_ALL)
            _aman(nama, "eksekusi promo toko", lambda: F2.eksekusi_promo_toko(username, nama, session, d))
            _aman(nama, "eksekusi harga dasar", lambda: F2.eksekusi_harga_dasar(username, nama, session, d))
            _aman(nama, "takedown flash", lambda: F2.eksekusi_takedown_flash(username, nama, session, d))
            _aman(nama, "takedown campaign", lambda: F2.eksekusi_takedown_campaign(username, nama, session, d))
        except Exception as e:
            print(colorama.Fore.RED + f"[{_t()}] [{nama}] GAGAL: {e}" + colorama.Style.RESET_ALL)
        close_session()
    catat_fase("rubah_harga", keterangan="Fase 2 v1 (promo toko + harga dasar + takedown flash/campaign, DRY-RUN paksa)")
    print(colorama.Fore.LIGHTCYAN_EX + f"[{_t()}] === FASE 2 SELESAI (DRY-RUN) ===" + colorama.Style.RESET_ALL)


# ══════════════════════════════════════════════════════════════════
#  KATEGORI — isi awal SEMUA produk yg belum punya kategori (bulk, incremental).
#  Aman diulang (cuma yg belum). Per toko harvest 1x lalu grab kategori sampai habis.
# ══════════════════════════════════════════════════════════════════
def jalankan_kategori():
    jam_siklus.kunci()
    toko = config.daftar_toko_aktif()
    print(colorama.Fore.LIGHTCYAN_EX + f"\n[{_t()}] === ISI KATEGORI — {len(toko)} toko (incremental) ===" + colorama.Style.RESET_ALL)
    total = 0
    for username, info in toko.items():
        nama = info["name"]
        try:
            session = grab_session(shop=username, i=info["i"])
            n = fakta.fakta_kategori(nama, session, limit=100000)   # semua yg belum, 1 pass
            total += n
            print(colorama.Fore.CYAN + f"[{_t()}] [{nama}] kategori terisi +{n}" + colorama.Style.RESET_ALL)
        except Exception as e:
            print(colorama.Fore.RED + f"[{_t()}] [{nama}] GAGAL: {e}" + colorama.Style.RESET_ALL)
        close_session()
    catat_fase("kategori", keterangan=f"{total} produk diproses, {len(toko)} toko")
    print(colorama.Fore.LIGHTCYAN_EX + f"[{_t()}] === KATEGORI SELESAI ({total} produk) ===" + colorama.Style.RESET_ALL)


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


def cek_komisi_shopee():
    """VERIFIKASI READ komisi Shopee (Komisi bagian B). Grab sesi toko komisi-aktif → coba
    `komisi_api.baca_komisi_aktif`. Laporin JALAN (berapa item) atau kena ANTI-BOT (403/90309999).
    READ-ONLY, TIDAK ubah apa pun. Hasilnya nentuin #9 bisa auto-grab via requests atau perlu
    browser-session ber-SDK. Cuma proses toko yg komisinya aktif di `harga_komisi_toko` (skrg Yarra)."""
    from modules import komisi_api
    from modules.sql_harga import baca_komisi_patokan
    toko = config.daftar_toko_aktif()
    ada = False
    for username, info in toko.items():
        nama = info["name"]
        if not baca_komisi_patokan(username):
            continue   # skip toko tanpa komisi aktif (Syntra)
        ada = True
        print(colorama.Fore.LIGHTCYAN_EX + f"\n[{_t()}] === CEK READ KOMISI SHOPEE — {nama} ({username}) ===" + colorama.Style.RESET_ALL)
        try:
            session = grab_session(shop=username, i=info["i"])
            try:
                akun = komisi_api.grab_akun(session)
                print(f"[komisi cek] [{nama}] akun: operator={akun.get('operator')} shop_id={akun.get('shop_id')}")
            except Exception as e:
                print(colorama.Fore.YELLOW + f"[komisi cek] [{nama}] grab_akun gagal: {type(e).__name__}: {e}" + colorama.Style.RESET_ALL)
            try:
                aktif = komisi_api.baca_komisi_aktif(session)
                print(colorama.Fore.LIGHTGREEN_EX + f"[komisi cek] [{nama}] ✅ baca_komisi_aktif JALAN: {len(aktif)} item komisi aktif di Shopee" + colorama.Style.RESET_ALL)
                for it in aktif[:5]:
                    print(f"    item {it['item_id']} rate {it['persen']}% status {it['status']}")
            except Exception as e:
                print(colorama.Fore.RED + f"[komisi cek] [{nama}] ❌ baca_komisi_aktif GAGAL (kemungkinan anti-bot): {type(e).__name__}: {e}" + colorama.Style.RESET_ALL)
        except Exception as e:
            print(colorama.Fore.RED + f"[komisi cek] [{nama}] GAGAL grab sesi: {e}" + colorama.Style.RESET_ALL)
        close_session()
    if not ada:
        print(colorama.Fore.YELLOW + "[komisi cek] tak ada toko dgn komisi aktif di harga_komisi_toko." + colorama.Style.RESET_ALL)
    print(colorama.Fore.LIGHTCYAN_EX + f"[{_t()}] === CEK KOMISI SELESAI ===" + colorama.Style.RESET_ALL)


def _parse_komisi_list(body, acc):
    """Ekstrak item komisi (yg ada `commissionRate`) dari response gql `GetOpenCampaignProducts`/
    `QueryItemsOpenCampaign` (data.<Op>.itemList atau .list). acc keyed by item_id ->
    {item_id, commission_id, persen, status, item_name}. rate 10000 -> 10%. Buang noise
    (AutoAddProducts/orderTarget dll yg ga punya commissionRate)."""
    if not isinstance(body, dict):
        return
    data = body.get("data")
    if not isinstance(data, dict):
        return
    for blk in data.values():
        if not isinstance(blk, dict):
            continue
        lst = blk.get("itemList") or blk.get("list")
        if not isinstance(lst, list):
            continue
        for it in lst:
            if not (isinstance(it, dict) and it.get("itemId") and "commissionRate" in it):
                continue
            commid = str(it.get("commissionId") or "")
            if commid in ("", "0"):
                continue   # commId 0 = daftar REKOMENDASI (belum aktif), bukan komisi aktif -> skip
            iid = str(it["itemId"])
            rate = it.get("commissionRate") or 0
            acc[iid] = {
                "item_id": int(iid),
                "commission_id": str(it.get("commissionId") or ""),
                "persen": round(rate / 1000, 3),      # 10000 -> 10.0 (FAKTOR_KOMISI=1000)
                "status": it.get("commissionStatus"),  # str "CommissionStatusOngoing" / int 2
                "item_name": it.get("itemName", ""),
            }


def grab_komisi_browser(interaktif=True):
    """GRAB komisi Shopee lewat BROWSER (bypass anti-bot: JS halaman yg nandatangan gql).
    Buka halaman komisi → tangkap response `affiliateplatform/gql` (GetOpenCampaignProducts) →
    parse item komisi aktif → SIMPAN ke harga_fakta_komisi + dump __komisi_shopee_<toko>.json.
    READ-ONLY di Shopee (navigate + scroll). Cuma toko komisi-aktif (skrg Yarra).
    interaktif=True (CLI): kasih jeda ENTER buat navigate manual kalau auto-nav meleset.
    interaktif=False (SCHEDULER): TANPA input() — auto-nav + wait aja (biar gak ngeblok)."""
    import json as J
    from modules import session as S
    from modules.sql_harga import baca_komisi_patokan
    # URL halaman komisi (dikonfirmasi user 10 Jul). Page JS manggil gql GetOpenCampaignProducts
    # (itemList komisi aktif: itemId, commissionId, commissionRate 10000=10%, commissionStatus).
    KOMISI_URLS = [
        "https://seller.shopee.co.id/portal/web-seller-affiliate/open_campaign",
    ]
    toko = config.daftar_toko_aktif()
    ada = False
    for username, info in toko.items():
        if not baca_komisi_patokan(username):
            continue
        ada = True
        nama = info["name"]
        print(colorama.Fore.LIGHTCYAN_EX + f"\n[{_t()}] === GRAB KOMISI BROWSER — {nama} ({username}) ===" + colorama.Style.RESET_ALL)
        raw, items = [], {}
        try:
            page = S.buka_page_toko(shop=username, i=info["i"])
            page.listen.start("affiliateplatform/gql")
            for url in KOMISI_URLS:
                try:
                    print(colorama.Fore.WHITE + f"[komisi grab] navigate: {url.split('?')[0].split('/portal/')[-1]}" + colorama.Style.RESET_ALL)
                    page.get(url); page.wait(3)
                    for _ in range(12):     # scroll biar lazy-load / pagination kepanggil
                        try: page.scroll.to_bottom()
                        except Exception: pass
                        page.wait(1)
                except Exception as e:
                    print(colorama.Fore.YELLOW + f"[komisi grab] nav gagal: {type(e).__name__}" + colorama.Style.RESET_ALL)
            # JEDA MANUAL (CLI): kalau auto-nav meleset, buka halaman Komisi manual di Chrome +
            # scroll. Paket gql ke-BUFFER selama ini. SCHEDULER (interaktif=False): skip, wait aja.
            if interaktif:
                print(colorama.Fore.LIGHTYELLOW_EX + "\n[komisi grab] >>> Kalau tabel komisi BELUM kebuka: buka manual di Chrome ini "
                      "(menu Affiliate/Komisi), SCROLL sampai habis." + colorama.Style.RESET_ALL)
                try:
                    input(colorama.Fore.LIGHTYELLOW_EX + "[komisi grab] >>> Tekan ENTER kalau udah keliatan semua produk komisi... " + colorama.Style.RESET_ALL)
                except EOFError:
                    page.wait(5)
            else:
                page.wait(5)   # unattended: kasih waktu gql kepanggil
            # drain paket ke-capture (berhenti kalau 8s ga ada request baru)
            try:
                for p in page.listen.steps(timeout=8):
                    body = getattr(getattr(p, "response", None), "body", None)
                    postdata = getattr(getattr(p, "request", None), "postData", None)
                    op = ""
                    try:
                        rj = J.loads(postdata) if isinstance(postdata, str) else postdata
                        op = (rj or {}).get("operationName", "")
                    except Exception:
                        pass
                    raw.append({"url": p.url, "op": op,
                                "response": body if isinstance(body, (dict, list)) else str(body)[:3000]})
                    _parse_komisi_list(body, items)
            except Exception as e:
                print(colorama.Fore.YELLOW + f"[komisi grab] drain gagal: {type(e).__name__}: {e}" + colorama.Style.RESET_ALL)
            out = f"__komisi_shopee_{username}.json"
            with open(out, "w", encoding="utf-8") as f:
                J.dump({"raw": raw, "items": list(items.values())}, f, ensure_ascii=False, indent=2)
            warna = colorama.Fore.LIGHTGREEN_EX if items else colorama.Fore.YELLOW
            print(warna + f"[komisi grab] [{nama}] {len(raw)} respons gql ditangkap, {len(items)} item komisi terparse -> {out}" + colorama.Style.RESET_ALL)
            for it in list(items.values())[:8]:
                print(f"    item {it['item_id']} komisi {it['persen']}% status {it['status']} commId {it['commission_id']} | {it['item_name'][:35]}")
            # SIMPAN ke fakta HANYA kalau ada hasil (jangan ngosongin tabel kalau grab meleset).
            if items:
                from modules.sql_harga import simpan_fakta_komisi
                n = simpan_fakta_komisi(nama, list(items.values()))
                print(colorama.Fore.CYAN + f"[komisi grab] [{nama}] {n} item komisi disimpan ke harga_fakta_komisi" + colorama.Style.RESET_ALL)
            else:
                print(colorama.Fore.YELLOW + f"[komisi grab] [{nama}] 0 item -> TIDAK disimpan (tabel fakta dibiarin, cek URL/scroll)" + colorama.Style.RESET_ALL)
        except Exception as e:
            print(colorama.Fore.RED + f"[komisi grab] [{nama}] GAGAL: {type(e).__name__}: {e}" + colorama.Style.RESET_ALL)
        finally:
            S.tutup_page()
    if not ada:
        print(colorama.Fore.YELLOW + "[komisi grab] tak ada toko komisi aktif di harga_komisi_toko." + colorama.Style.RESET_ALL)
    print(colorama.Fore.LIGHTCYAN_EX + f"[{_t()}] === GRAB KOMISI BROWSER SELESAI ===" + colorama.Style.RESET_ALL)


def inspect_komisi_dom():
    """EKSPLORASI DOM halaman komisi buat DESAIN set/takedown (bagian C) — GA HALU, ga klik apa-apa.
    Buka halaman komisi → JEDA (kamu navigate/atur tampilan yg mau di-inspect: produk aktif, tombol
    'Atur'/'Hapus', atau dialog set rate) → dump `page.html` ke __komisi_dom_<toko>.html + ringkasan
    TOMBOL & INPUT (label/placeholder) biar gua tau selektor asli. READ-ONLY."""
    from modules import session as S
    from modules.sql_harga import baca_komisi_patokan
    toko = config.daftar_toko_aktif()
    for username, info in toko.items():
        if not baca_komisi_patokan(username):
            continue
        nama = info["name"]
        print(colorama.Fore.LIGHTCYAN_EX + f"\n[{_t()}] === INSPECT DOM KOMISI — {nama} ({username}) ===" + colorama.Style.RESET_ALL)
        try:
            page = S.buka_page_toko(shop=username, i=info["i"])
            page.get("https://seller.shopee.co.id/portal/web-seller-affiliate/open_campaign")
            page.wait(4)
            print(colorama.Fore.LIGHTYELLOW_EX + "[inspect] >>> Di Chrome: arahin ke tampilan yg mau gua liat "
                  "(mis. list produk komisi + tombol Atur/Hapus, ATAU buka dialog set rate). Jangan di-SAVE." + colorama.Style.RESET_ALL)
            try:
                input(colorama.Fore.LIGHTYELLOW_EX + "[inspect] >>> Tekan ENTER kalau tampilan udah pas buat di-dump... " + colorama.Style.RESET_ALL)
            except EOFError:
                page.wait(3)
            html = page.html or ""
            out = f"__komisi_dom_{username}.html"
            with open(out, "w", encoding="utf-8") as f:
                f.write(html)
            btns, inps = [], []
            try:
                for b in page.eles("tag:button"):
                    t = (b.text or "").strip()
                    if t and t[:45] not in btns:
                        btns.append(t[:45])
            except Exception as e:
                print(f"[inspect] baca tombol gagal: {type(e).__name__}")
            try:
                for ip in page.eles("tag:input"):
                    ph = (ip.attr("placeholder") or "").strip()
                    ty = (ip.attr("type") or "").strip()
                    inps.append(f"{ty}:{ph}"[:40])
            except Exception:
                pass
            print(colorama.Fore.LIGHTGREEN_EX + f"[inspect] [{nama}] HTML -> {out} ({len(html):,} char)" + colorama.Style.RESET_ALL)
            print(colorama.Fore.WHITE + f"[inspect] TOMBOL ({len(btns)}): " + " | ".join(btns[:40]) + colorama.Style.RESET_ALL)
            print(colorama.Fore.WHITE + f"[inspect] INPUT ({len(inps)}): " + " | ".join(inps[:20]) + colorama.Style.RESET_ALL)
        except Exception as e:
            print(colorama.Fore.RED + f"[inspect] [{nama}] GAGAL: {type(e).__name__}: {e}" + colorama.Style.RESET_ALL)
        finally:
            S.tutup_page()
    print(colorama.Fore.LIGHTCYAN_EX + f"[{_t()}] === INSPECT DOM SELESAI ===" + colorama.Style.RESET_ALL)


if __name__ == "__main__":
    arg = sys.argv[1].lower() if len(sys.argv) > 1 else ""
    if arg == "login":
        buka_login()
    elif arg in ("komisi_cek", "cek_komisi", "komisicek"):
        cek_komisi_shopee()
    elif arg in ("komisi_grab", "grab_komisi", "komisigrab"):
        grab_komisi_browser()
    elif arg in ("komisi_inspect", "inspect_komisi", "komisidom"):
        inspect_komisi_dom()
    elif arg in ("grab", "fase1", "test", "1"):
        paksa = len(sys.argv) > 2 and sys.argv[2].lower() in ("full", "semua", "all")
        siklus_fase1(paksa_semua=paksa)
    elif arg in ("kategori", "category"):
        jalankan_kategori()
    elif arg in ("fase2", "rubah2"):
        jalankan_fase2()
    elif arg in ("rubah", "rubah_harga", "2"):
        _legacy_jalankan([2])
    elif arg in ("verifikasi", "verif", "3"):
        _legacy_jalankan([3])
    elif arg in ("fase4", "perpanjang", "4"):
        _legacy_jalankan([4])
    else:
        scheduler()
