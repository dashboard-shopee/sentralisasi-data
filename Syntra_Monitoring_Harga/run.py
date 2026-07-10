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
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # cegah UnicodeEncodeError (emoji) di konsol Windows
except Exception: pass
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
            import json as J
            html = page.html or ""
            out = f"__komisi_dom_{username}.html"
            with open(out, "w", encoding="utf-8") as f:
                f.write(html)
            # DUMP elemen CLICKABLE via JS (jauh lebih kebaca dari HTML mentah): button/a/[role=button]/
            # elemen ber-onclick / cursor pointer. Simpan text + tag + class + id.
            probe = r"""
            try {
              var res = [];
              var els = document.querySelectorAll('button, a, [role=button], [class*=btn], [class*=Button], svg[class*=icon], [class*=action], [class*=Action]');
              for (var i=0;i<els.length && res.length<200;i++){
                var e = els[i];
                var t = (e.innerText||e.textContent||'').trim().replace(/\s+/g,' ').slice(0,40);
                var cls = (e.getAttribute('class')||'').slice(0,60);
                var r = e.getBoundingClientRect();
                if (r.width===0 && r.height===0) continue;   // skip hidden
                res.push({tag:e.tagName.toLowerCase(), text:t, cls:cls, id:(e.id||'').slice(0,30),
                          x:Math.round(r.x), y:Math.round(r.y)});
              }
              var inps = [];
              document.querySelectorAll('input,textarea').forEach(function(e){
                var r=e.getBoundingClientRect(); if(r.width===0&&r.height===0)return;
                inps.push({type:e.type||e.tagName.toLowerCase(), ph:(e.placeholder||'').slice(0,40), cls:(e.getAttribute('class')||'').slice(0,50)});
              });
              return JSON.stringify({clickable:res, inputs:inps});
            } catch(e){ return JSON.stringify({error:String(e)}); }
            """
            raw = page.run_js(probe)
            data = J.loads(raw) if isinstance(raw, str) else (raw or {})
            outj = f"__komisi_dom_{username}.json"
            with open(outj, "w", encoding="utf-8") as f:
                J.dump(data, f, ensure_ascii=False, indent=2)
            cl = data.get("clickable", [])
            print(colorama.Fore.LIGHTGREEN_EX + f"[inspect] [{nama}] HTML -> {out} | clickable -> {outj} ({len(cl)} elemen)" + colorama.Style.RESET_ALL)
            for e in cl[:35]:
                if e.get("text") or "action" in (e.get("cls", "").lower()):
                    print(f"    <{e['tag']}> '{e.get('text','')}' cls={e.get('cls','')[:35]}")
        except Exception as e:
            print(colorama.Fore.RED + f"[inspect] [{nama}] GAGAL: {type(e).__name__}: {e}" + colorama.Style.RESET_ALL)
        finally:
            S.tutup_page()
    print(colorama.Fore.LIGHTCYAN_EX + f"[{_t()}] === INSPECT DOM SELESAI ===" + colorama.Style.RESET_ALL)


def sniff_komisi_write():
    """SNIFF set/takedown komisi via API: buka halaman komisi (profil bot, udah login) → listen
    `affiliateplatform/gql` → REKAM request HEADERS (x-sap-sec / af-ac-enc / x-sz-sdk dll) + body +
    response tiap aksi. USER lakuin SET + TAKEDOWN komisi MANUAL sampai notif berhasil (semua kerekam,
    ke-BUFFER selama proses). Dump __komisi_sniff_<toko>.json buat analisa apakah signature bisa
    direplikasi via requests. ⚠️ INI BENERAN NGUBAH KOMISI (user yg klik) — pilih produk yg reversible."""
    import json as J
    from modules import session as S
    from modules.sql_harga import baca_komisi_patokan
    URL = "https://seller.shopee.co.id/portal/web-seller-affiliate/open_campaign"
    toko = config.daftar_toko_aktif()
    for username, info in toko.items():
        if not baca_komisi_patokan(username):
            continue
        nama = info["name"]
        print(colorama.Fore.LIGHTCYAN_EX + f"\n[{_t()}] === SNIFF SET/TAKEDOWN KOMISI — {nama} ({username}) ===" + colorama.Style.RESET_ALL)
        rec = []
        try:
            page = S.buka_page_toko(shop=username, i=info["i"])
            page.listen.start("affiliateplatform/gql")   # start SEBELUM navigate biar ketangkep semua
            page.get(URL); page.wait(3)
            print(colorama.Fore.LIGHTYELLOW_EX + """
================================================================
  DI CHROME INI, lakukan MANUAL (sampai notif BERHASIL):
    [1] SET komisi 1 produk (yg belum komisi) -> isi rate -> Simpan/Ajukan
    [2] TAKEDOWN/hapus komisi 1 produk yg aktif
  Semua request API kerekam LENGKAP (header + body + response).
  ⚠️ pilih produk yg AMAN (bisa lo balikin). Kelar -> ENTER di sini.
================================================================""" + colorama.Style.RESET_ALL)
            try:
                input(colorama.Fore.LIGHTYELLOW_EX + "[sniff komisi] >>> ENTER kalau SET + TAKEDOWN udah selesai... " + colorama.Style.RESET_ALL)
            except EOFError:
                page.wait(120)
            for p in page.listen.steps(timeout=8):
                postdata = getattr(getattr(p, "request", None), "postData", None)
                op, body = "", postdata
                try:
                    rj = J.loads(postdata) if isinstance(postdata, str) else postdata
                    if isinstance(rj, dict):
                        op = rj.get("operationName", ""); body = rj
                except Exception:
                    pass
                rec.append({
                    "url": p.url, "op": op, "method": getattr(p, "method", ""),
                    "request_headers": dict(getattr(getattr(p, "request", None), "headers", {}) or {}),
                    "request_body": body,
                    "response": getattr(getattr(p, "response", None), "body", None),
                })
            out = f"__komisi_sniff_{username}.json"
            with open(out, "w", encoding="utf-8") as f:
                J.dump(rec, f, ensure_ascii=False, indent=2, default=str)
            print(colorama.Fore.LIGHTGREEN_EX + f"[sniff komisi] [{nama}] {len(rec)} request gql direkam -> {out}" + colorama.Style.RESET_ALL)
            for r in rec:
                if any(w in (r["op"] or "") for w in ("Set", "Remove", "AutoAdd")):
                    hdr = r["request_headers"]
                    sig = [k for k in hdr if any(s in k.lower() for s in ("sap", "af-ac", "sz-", "x-sz", "risk"))]
                    print(colorama.Fore.MAGENTA + f"  WRITE {r['op']}: sig-headers={sig} | resp={str(r['response'])[:70]}" + colorama.Style.RESET_ALL)
        except Exception as e:
            print(colorama.Fore.RED + f"[sniff komisi] [{nama}] GAGAL: {type(e).__name__}: {e}" + colorama.Style.RESET_ALL)
        finally:
            S.tutup_page()
    print(colorama.Fore.LIGHTCYAN_EX + f"[{_t()}] === SNIFF KOMISI SELESAI ===" + colorama.Style.RESET_ALL)


def _komisi_gql_via_page(page, operation, query, variables, qparam, timeout=30):
    """Panggil gql affiliateplatform via window.fetch DARI konteks halaman → SDK (__sap_hook_fetch)
    auto-nandatangan. Hasil disimpen ke localStorage (TAHAN navigasi same-origin, jadi ga ilang
    walau halaman ke-redirect). Poll localStorage. Return {status, body} / {error}. TANPA klik."""
    import json as J, time as T
    url = f"https://seller.shopee.co.id/api/v3/affiliateplatform/gql?q={qparam}"
    url_js = J.dumps(url)
    body_js = J.dumps(J.dumps({"operationName": operation, "query": query, "variables": variables}))

    def _js(s):
        for _ in range(15):
            try:
                return page.run_js(s)
            except Exception as ex:
                if "ContextLost" in type(ex).__name__ or "refresh" in str(ex).lower():
                    page.wait(1); continue
                raise
        return None

    for _ in range(24):
        try:
            if page.run_js("return document.readyState;") == "complete":
                break
        except Exception:
            pass
        page.wait(0.5)
    page.wait(2)

    kick = f"""
    try {{
      localStorage.setItem('__komres', 'PENDING');
      fetch({url_js}, {{method:'POST', headers:{{'content-type':'application/json'}}, body:{body_js}, credentials:'include'}})
        .then(function(r){{ return r.text().then(function(t){{ localStorage.setItem('__komres', JSON.stringify({{status:r.status, body:t}})); }}); }})
        .catch(function(e){{ localStorage.setItem('__komres', JSON.stringify({{error:String(e)}})); }});
      return 'kicked|ls=' + localStorage.getItem('__komres');
    }} catch(e) {{ return 'kickerr:' + String(e); }}
    """
    kicked = _js(kick)   # diagnosa: harus 'kicked|ls=PENDING' kalau eksekusi + localStorage OK
    page.wait(0.5)
    after = _js("return localStorage.getItem('__komres');")
    hook = _js("return (typeof window.__sap_hook_fetch) + '|native=' + /native/.test(window.fetch.toString());")
    t0 = T.time()
    while T.time() - t0 < timeout:
        v = _js("return localStorage.getItem('__komres');")
        if v and v != "PENDING":
            try:
                o = J.loads(v)
                if isinstance(o, dict) and isinstance(o.get("body"), str):
                    try:
                        o["body"] = J.loads(o["body"])
                    except Exception:
                        pass
                return o
            except Exception:
                return {"raw": str(v)[:500]}
        page.wait(0.5)
    return {"error": "timeout", "kicked": kicked, "after_kick": after, "fetch_hook": hook}


def sniff_set_komisi_produk():
    """SNIFF set komisi dari HALAMAN PRODUK (Produk Saya, filter komisi) — bukan halaman affiliate.
    Listen SEMUA /api (broad). User SET komisi 1 produk manual (sampai notif berhasil). Rekam req
    header+body+response. Analisa: endpoint-nya BEDA (mungkin signable) atau tetap affiliateplatform
    /gql (anti-bot)? Dump __komisi_sniff_produk_<toko>.json + highlight op write."""
    import json as J
    from modules import session as S
    from modules.sql_harga import baca_komisi_patokan
    URL = "https://seller.shopee.co.id/portal/product/list/all?productType=ams_commission"
    toko = config.daftar_toko_aktif()
    for username, info in toko.items():
        if not baca_komisi_patokan(username):
            continue
        nama = info["name"]
        print(colorama.Fore.LIGHTCYAN_EX + f"\n[{_t()}] === SNIFF SET KOMISI (HALAMAN PRODUK) — {nama} ===" + colorama.Style.RESET_ALL)
        rec = []
        try:
            page = S.buka_page_toko(shop=username, i=info["i"])
            page.listen.start("seller.shopee.co.id/api")   # BROAD: semua /api
            page.get(URL); page.wait(4)
            print(colorama.Fore.LIGHTYELLOW_EX + """
================================================================
  DI HALAMAN PRODUK ini: SET komisi 1 produk (Atur Komisi -> isi rate -> Simpan)
  sampai notif BERHASIL. Semua /api kerekam. Kelar -> ENTER.
  (kalau halaman produk ga kebuka, navigate ke Produk Saya + filter komisi)
================================================================""" + colorama.Style.RESET_ALL)
            try:
                input(colorama.Fore.LIGHTYELLOW_EX + "[sniff produk] >>> ENTER kalau SET komisi udah berhasil... " + colorama.Style.RESET_ALL)
            except EOFError:
                page.wait(120)
            for p in page.listen.steps(timeout=8):
                url = getattr(p, "url", "")
                method = getattr(p, "method", "")
                postdata = getattr(getattr(p, "request", None), "postData", None)
                # cuma simpen yg POST/PUT (aksi write) + endpoint menarik
                if method not in ("POST", "PUT"):
                    continue
                body = postdata
                try:
                    body = J.loads(postdata) if isinstance(postdata, str) else postdata
                except Exception:
                    pass
                hdr = dict(getattr(getattr(p, "request", None), "headers", {}) or {})
                sig = [k for k in hdr if any(s in k.lower() for s in ("sap", "af-ac", "sz-", "x-sz"))]
                rec.append({"url": url, "method": method, "sig_headers": sig,
                            "request_body": body,
                            "response": getattr(getattr(p, "response", None), "body", None)})
            out = f"__komisi_sniff_produk_{username}.json"
            with open(out, "w", encoding="utf-8") as f:
                J.dump(rec, f, ensure_ascii=False, indent=2, default=str)
            print(colorama.Fore.LIGHTGREEN_EX + f"[sniff produk] {len(rec)} req POST/PUT direkam -> {out}" + colorama.Style.RESET_ALL)
            for r in rec:
                u = r["url"].split("?")[0].split("/api/")[-1]
                if any(k in (r["url"] + J.dumps(r.get("request_body") or "")).lower() for k in ("commission", "komisi", "campaign", "ams")):
                    print(colorama.Fore.MAGENTA + f"  WRITE? {r['method']} /{u} | sig={r['sig_headers']}" + colorama.Style.RESET_ALL)
        except Exception as e:
            print(colorama.Fore.RED + f"[sniff produk] [{nama}] GAGAL: {type(e).__name__}: {e}" + colorama.Style.RESET_ALL)
        finally:
            S.tutup_page()
    print(colorama.Fore.LIGHTCYAN_EX + f"[{_t()}] === SNIFF SET KOMISI PRODUK SELESAI ===" + colorama.Style.RESET_ALL)


def takedown_komisi_browser(dry=True, konfirmasi=True, limit=1):
    """TAKEDOWN komisi via DOM-click (satu-satunya jalan; API mati). Alur per produk: ketik di
    search 'Cari di sini' → sisa 1 baris → klik <div>'Hapus' → modal 'Yakin Hapus?' → klik confirm →
    verify network (RemoveOpenCampaigns isAllSuccess). dry=True: cuma search+temuin tombol, GA diklik
    (aman, ga ngubah). Target = produk komisi aktif Shopee (harga_fakta_komisi); nanti wiring Fase 2
    pakai verdict 'harusnya_dicabut'. limit=batasi jumlah (dry test)."""
    from sqlalchemy import text as _text
    from modules.db import get_engine
    from modules import session as S
    from modules.sql_harga import baca_komisi_patokan
    URL = "https://seller.shopee.co.id/portal/web-seller-affiliate/open_campaign"
    SRCH = 'x://input[@placeholder="Cari di sini"]'
    HAPUS = 'x://div[contains(@class,"actionBtn") and normalize-space()="Hapus"]'
    toko = config.daftar_toko_aktif()
    for username, info in toko.items():
        if not baca_komisi_patokan(username):
            continue
        nama = info["name"]
        with get_engine().connect() as c:
            rows = c.execute(_text("select item_id, item_name from harga_fakta_komisi where toko=:t limit :l"),
                             {"t": nama, "l": limit}).fetchall()
        targets = [(int(r.item_id), r.item_name or "") for r in rows]
        mode = "DRY" if dry else "LIVE"
        print(colorama.Fore.LIGHTCYAN_EX + f"\n[{_t()}] === TAKEDOWN KOMISI ({mode}) — {nama} — {len(targets)} target ===" + colorama.Style.RESET_ALL)
        try:
            page = S.buka_page_toko(shop=username, i=info["i"])
            page.listen.start("affiliateplatform/gql")
            page.get(URL); page.wait(6)
            # tungguin search box muncul (app Vue load lambat). Kalau tetep gak ada -> dump state.
            box = None
            for _ in range(12):
                box = page.ele(SRCH, timeout=2)
                if box:
                    break
                page.wait(1.5)
            if not box:
                print(colorama.Fore.RED + "  search box 'Cari di sini' TAK KETEMU — dump state halaman aktual" + colorama.Style.RESET_ALL)
                try:
                    import json as _J
                    st = page.run_js(r"""try{var b=[];document.querySelectorAll('button,a,[role=button],[class*=Tab],[class*=tab]').forEach(function(e){var t=(e.innerText||'').trim().replace(/\s+/g,' ').slice(0,35);if(t)b.push(e.tagName.toLowerCase()+':'+t);});var i=[];document.querySelectorAll('input').forEach(function(e){i.push((e.placeholder||e.type||''));});return JSON.stringify({btns:b.slice(0,50),inputs:i});}catch(e){return JSON.stringify({error:String(e)});}""")
                    _J.dump(_J.loads(st) if isinstance(st, str) else st, open(f"__komisi_takedown_state_{username}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
                    dd = _J.loads(st) if isinstance(st, str) else st
                    print("  INPUTS:", dd.get("inputs"))
                    print("  BTNS:", " | ".join(dd.get("btns", [])[:30]))
                except Exception as _e:
                    print("  dump state gagal:", type(_e).__name__)
                break
            # Ambil TEKS tiap baris (in-order sama kaya page.eles(HAPUS)) via JS — buat cocokin produk.
            import json as _J
            rowjs = r"""
            try {
              var out=[]; var hs=document.querySelectorAll('div[class*="actionBtn"]');
              hs.forEach(function(h){
                if ((h.innerText||'').trim()!=='Hapus') return;
                var row = h.closest('[class*="row"],[class*="Row"],[class*="listItem"],[class*="ListItem"],tr') || (h.parentElement&&h.parentElement.parentElement&&h.parentElement.parentElement.parentElement);
                out.push((row&&(row.innerText||'')||'').replace(/\s+/g,' ').slice(0,160));
              });
              return JSON.stringify(out);
            } catch(e){ return JSON.stringify({error:String(e)}); }
            """
            for iid, iname in targets:
                haps = page.eles(HAPUS)
                raw = page.run_js(rowjs)
                rowtexts = _J.loads(raw) if isinstance(raw, str) else raw
                if isinstance(rowtexts, dict):
                    rowtexts = []
                idx = -1
                key_name = (iname or "").strip()[:18].lower()
                for i, txt in enumerate(rowtexts):
                    tl = str(txt).lower()
                    if str(iid) in tl or (key_name and key_name in tl):
                        idx = i; break
                print(f"  item {iid} ({iname[:26]}): {len(haps)} baris, match idx={idx}")
                if dry:
                    print(colorama.Fore.YELLOW + f"    [DRY] ga diklik (rowtext contoh: {str(rowtexts[idx])[:70] if idx>=0 else 'N/A'})" + colorama.Style.RESET_ALL); continue
                if idx < 0 or idx >= len(haps):
                    print(colorama.Fore.RED + "    SKIP (produk ga ketemu di baris — mungkin perlu scroll/paginate)" + colorama.Style.RESET_ALL); continue
                haps[idx].click(); page.wait(2.5)
                # dump SEMUA tombol visible + elemen ber-teks konfirmasi (diagnosa selektor confirm)
                try:
                    mb = page.run_js(r"""try{
                      var b=[]; document.querySelectorAll('button').forEach(function(e){
                        var r=e.getBoundingClientRect(); if(r.width===0&&r.height===0)return;
                        var t=(e.innerText||'').trim().slice(0,22); if(t) b.push(t+'|'+(e.className||'').slice(0,40));
                      });
                      var konf=[]; document.querySelectorAll('*').forEach(function(e){
                        var t=(e.innerText||'').trim();
                        if(/Yakin|Menghapus|Ingin Menghapus/i.test(t) && t.length<120 && e.children.length<=3) konf.push(t.slice(0,80)+' :: '+(e.className||'').slice(0,40));
                      });
                      return JSON.stringify({buttons:b.slice(0,25), konfirmasi:konf.slice(0,4)});
                    }catch(e){return JSON.stringify({error:String(e)});}""")
                    print(f"    [MODAL] {mb}")
                except Exception:
                    pass
                if not konfirmasi:
                    cancel = page.ele('x://div[contains(@class,"modal") or contains(@class,"dialog")]//button[contains(@class,"eds-react-button--normal") or contains(@class,"default")]', timeout=4)
                    if cancel:
                        cancel.click()
                    print(colorama.Fore.YELLOW + "    [PROBE MODAL] di-CANCEL (ga jadi hapus)" + colorama.Style.RESET_ALL); continue
                # modal konfirmasi -> tombol primary
                confirm = page.ele('x://div[contains(@class,"modal") or contains(@class,"dialog") or contains(@class,"eds-modal")]//button[contains(@class,"primary")]', timeout=6)
                if not confirm:
                    print(colorama.Fore.RED + "    modal confirm TAK KETEMU" + colorama.Style.RESET_ALL); continue
                confirm.click(); page.wait(3)
                # verify via network
                ok = False
                for p in page.listen.steps(timeout=6):
                    body = getattr(getattr(p, "response", None), "body", None)
                    if isinstance(body, dict) and (((body.get("data") or {}).get("RemoveOpenCampaigns") or {}).get("isAllSuccess")):
                        ok = True; break
                print((colorama.Fore.MAGENTA if ok else colorama.Fore.RED) + f"    -> takedown {'BERHASIL (isAllSuccess)' if ok else 'gagal/ tak terverifikasi'}" + colorama.Style.RESET_ALL)
        except Exception as e:
            print(colorama.Fore.RED + f"[takedown] [{nama}] GAGAL: {type(e).__name__}: {e}" + colorama.Style.RESET_ALL)
        finally:
            S.tutup_page()
    print(colorama.Fore.LIGHTCYAN_EX + f"[{_t()}] === TAKEDOWN SELESAI ({mode}) ===" + colorama.Style.RESET_ALL)


def probe_komisi_apollo():
    """PROBE (read-only): cari instance Apollo Client / objek gql di window halaman komisi. Kalau
    ke-expose + punya .mutate/.query, kita bisa manggil mutation lewat jalur yg UDAH ditandatangani
    SDK (bukan fetch injeksi). Cuma ngintip window (ga manggil gql) → ga trigger 403/redirect."""
    import json as J
    from modules import session as S
    from modules.sql_harga import baca_komisi_patokan
    URL = "https://seller.shopee.co.id/portal/web-seller-affiliate/open_campaign"
    toko = config.daftar_toko_aktif()
    for username, info in toko.items():
        if not baca_komisi_patokan(username):
            continue
        nama = info["name"]
        print(colorama.Fore.LIGHTCYAN_EX + f"\n[{_t()}] === PROBE APOLLO KOMISI — {nama} ({username}) ===" + colorama.Style.RESET_ALL)
        try:
            page = S.buka_page_toko(shop=username, i=info["i"])
            page.get(URL)
            for _ in range(24):
                try:
                    if page.run_js("return document.readyState;") == "complete":
                        break
                except Exception:
                    pass
                page.wait(0.5)
            page.wait(4)
            probe = """
            try {
              var out = {relKeys:[], apollo:null, candidates:[], gqlFns:[]};
              var kk = Object.keys(window);
              out.relKeys = kk.filter(function(k){ return /apollo|client|graphql|gql|sap|sz|affiliate|__/i.test(k); }).slice(0,60);
              if (window.__APOLLO_CLIENT__) {
                var c = window.__APOLLO_CLIENT__;
                out.apollo = {global:'__APOLLO_CLIENT__', mutate: typeof c.mutate, query: typeof c.query};
              }
              for (var i=0;i<kk.length;i++){
                try {
                  var v = window[kk[i]];
                  if (v && typeof v==='object'){
                    if (typeof v.mutate==='function' && typeof v.query==='function') out.candidates.push(kk[i]);
                  }
                  if (typeof v==='function' && /gql|graphql/i.test(kk[i])) out.gqlFns.push(kk[i]);
                } catch(e){}
              }
              return JSON.stringify(out);
            } catch(e){ return JSON.stringify({error:String(e)}); }
            """
            raw = page.run_js(probe)
            res = J.loads(raw) if isinstance(raw, str) else raw
            with open(f"__komisi_apollo_{username}.json", "w", encoding="utf-8") as f:
                J.dump(res, f, ensure_ascii=False, indent=2, default=str)
            print(colorama.Fore.WHITE + f"[probe] key relevan: {res.get('relKeys')}" + colorama.Style.RESET_ALL)
            print(colorama.Fore.WHITE + f"[probe] __APOLLO_CLIENT__: {res.get('apollo')}" + colorama.Style.RESET_ALL)
            print(colorama.Fore.WHITE + f"[probe] kandidat (punya mutate+query): {res.get('candidates')} | gqlFns: {res.get('gqlFns')}" + colorama.Style.RESET_ALL)
            if res.get("apollo") or res.get("candidates"):
                print(colorama.Fore.LIGHTGREEN_EX + "[probe] ✅ ada kandidat apollo -> bisa dicoba mutate lewat jalur signed." + colorama.Style.RESET_ALL)
            else:
                print(colorama.Fore.YELLOW + "[probe] ⚠️ apollo client GAK ke-expose di window global." + colorama.Style.RESET_ALL)
        except Exception as e:
            print(colorama.Fore.RED + f"[probe] [{nama}] GAGAL: {type(e).__name__}: {e}" + colorama.Style.RESET_ALL)
        finally:
            S.tutup_page()
    print(colorama.Fore.LIGHTCYAN_EX + f"[{_t()}] === PROBE SELESAI ===" + colorama.Style.RESET_ALL)


def test_komisi_api_via_browser():
    """TES: bisa gak panggil gql komisi dari konteks halaman (SDK auto-sign) — TANPA klik tombol.
    Pakai READ aman (GetOpenCampaignProducts). status 200 + ada data = SDK nandatangan fetch kita
    → set/takedown via page-fetch BAKAL JALAN. status 403 = SDK gak sign fetch injeksi (mentok DOM)."""
    from modules import session as S
    from modules.sql_harga import baca_komisi_patokan
    from modules import komisi_api
    URL = "https://seller.shopee.co.id/portal/web-seller-affiliate/open_campaign"
    toko = config.daftar_toko_aktif()
    for username, info in toko.items():
        if not baca_komisi_patokan(username):
            continue
        nama = info["name"]
        print(colorama.Fore.LIGHTCYAN_EX + f"\n[{_t()}] === TES KOMISI API VIA BROWSER — {nama} ({username}) ===" + colorama.Style.RESET_ALL)
        try:
            page = S.buka_page_toko(shop=username, i=info["i"])
            page.get(URL); page.wait(7)   # biarin SDK load penuh + redirect SPA settle
            res = _komisi_gql_via_page(page, "GetOpenCampaignProductsQuery",
                                       komisi_api._Q_DAFTAR_AKTIF, {"cursor": "", "limit": 5},
                                       "GetOpenCampaignProducts")
            try:
                import json as _J
                with open(f"__komisi_apitest_{username}.json", "w", encoding="utf-8") as _f:
                    _J.dump(res, _f, ensure_ascii=False, indent=2, default=str)
            except Exception:
                pass
            status = res.get("status")
            b = res.get("body") or {}
            blok = ((b.get("data") or {}).get("GetOpenCampaignProducts") or {}) if isinstance(b, dict) else {}
            n = len(blok.get("itemList") or []) if isinstance(blok, dict) else 0
            err = (b.get("error") if isinstance(b, dict) else None) or res.get("error")
            if status == 200 and isinstance(b, dict) and b.get("data"):
                print(colorama.Fore.LIGHTGREEN_EX + f"[tes] ✅ BERHASIL via page-fetch! status={status}, {n} item. SDK NANDATANGAN fetch kita → set/takedown API BISA (tanpa klik)." + colorama.Style.RESET_ALL)
            else:
                print(colorama.Fore.RED + f"[tes] ❌ GAGAL status={status} err={err}. SDK gak sign fetch injeksi → mentok DOM-click." + colorama.Style.RESET_ALL)
        except Exception as e:
            print(colorama.Fore.RED + f"[tes] [{nama}] GAGAL: {type(e).__name__}: {e}" + colorama.Style.RESET_ALL)
        finally:
            S.tutup_page()
    print(colorama.Fore.LIGHTCYAN_EX + f"[{_t()}] === TES SELESAI ===" + colorama.Style.RESET_ALL)


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
    elif arg in ("komisi_sniff", "sniff_komisi", "komisisniff"):
        sniff_komisi_write()
    elif arg in ("komisi_sniff_produk", "sniff_produk", "komisisniffproduk"):
        sniff_set_komisi_produk()
    elif arg in ("komisi_apitest", "komisi_test", "komisiapitest"):
        test_komisi_api_via_browser()
    elif arg in ("komisi_apollo", "apollo_probe", "komisiapollo"):
        probe_komisi_apollo()
    elif arg in ("komisi_takedown_dry", "takedown_dry"):
        takedown_komisi_browser(dry=True, limit=2)
    elif arg in ("komisi_takedown_modal", "takedown_modal"):
        takedown_komisi_browser(dry=False, konfirmasi=False, limit=1)   # klik Hapus -> dump modal -> CANCEL
    elif arg in ("komisi_takedown_live", "takedown_live"):
        takedown_komisi_browser(dry=False, konfirmasi=True, limit=1)
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
