"""
config.py — Pusat konfigurasi Syntra Monitoring Harga.

┌──────────────────────────────────────────────────────────────────┐
│  YANG SERING DIEDIT ada di blok "PENGATURAN UTAMA" paling ATAS.    │
│  Sisanya (teknis: endpoint, header, dll) di bawah — jarang disentuh│
└──────────────────────────────────────────────────────────────────┘
Rahasia (password) dibaca dari file .env.
"""

import os
from dotenv import load_dotenv

load_dotenv()


# ╔══════════════════════════════════════════════════════════════════╗
# ║                    PENGATURAN UTAMA — EDIT DI SINI                 ║
# ╚══════════════════════════════════════════════════════════════════╝

# 1) 🔴 SAKLAR LIVE — SATU-SATUNYA switch simulasi vs beneran. SEMUA modul & fase ikut ini.
#    False = DRY-RUN (SIMULASI, AMAN): ngitung + catat rencana, TIDAK ngubah Shopee.
#    True  = LIVE: SEMUA modul (harga poin 1-4 + provisioning poin 5) BENERAN ubah Shopee.
MODE_LIVE = True    # 🔴 M4 LIVE (14 Jul): scope kimmioshop, full send (owner ACC full incl 23 sesi flash). Balikin False abis verif.

# 2) FASE yang dijalankan (arsitektur 3 FASE, orkestrasi `siklus_terpadu` 1-sesi/toko):
#      1 = FAKTA          (grab data, READ-ONLY)
#      2 = MASALAH+SOLUSI (benerin harga poin 1-4 + pasang/cabut promo poin 5)
#      3 = LAPORAN        (grab-ulang abis aksi, rangkum ke dashboard)  → dibikin bertahap
#    Contoh: [1]=grab doang · [1,2]=grab+aksi · [1,2,3]=full. Live/DRY ikut MODE_LIVE.
FASE_AKTIF = [1,2,3]   # 🔴 M4 LIVE: full 3 fase — Fase 3 grab-ulang abis aksi = bukti hidup otomatis

# 3) TOKO yang diproses.  [] = SEMUA 10 toko.  ["kimmioshop"] = 1 toko (buat tes bertahap).
TOKO_AKTIF = ["kimmioshop"]   # ⚠️ M4: scope 1 toko kelinci-percobaan. Balikin [] cuma pas udah full-verified.
# TOKO_AKTIF = []

# 4) MODUL yang aktif (di-grab & diproses). Buang dari list = modul itu di-SKIP.
#    (produk/harga/stok = base, SELALU jalan, ga bisa dimatiin.)
# M4: full modul buat verif DRY semua provisioning. Kecilin lagi kalau mau fokus 1 modul.
MODUL_AKTIF = ["komisi", "promo_toko", "garansi", "paket", "voucher", "campaign", "flash", "kategori"]
# MODUL_AKTIF = ["promo_toko", "paket", "voucher", "kategori"]

# 5) Setelan lain:
STOK_MINIMAL        = 1            # grab hanya variasi stok >= ini (0 dilewati)
NAMA_PROMO          = "PROMO TOKO" # nama campaign Diskon Toko yang dikelola bot
NAMA_UPSELL         = "UPSELL"     # prefix nama paket/voucher yg dikelola bot (idempotent)
JELANG_EXPIRE_HARI  = 1            # promo dianggap "mau abis" bila sisa <= ini (hari)
DURASI_PROMO_HARI   = 180          # durasi promo baru (maks 180 sesuai Shopee)
BUAT_PROMO_DARI_NOL = True         # bikin promo toko baru kalau toko belum punya

# ── DRY_RUN turunan dari MODE_LIVE (semua modul BACA config.DRY_RUN). ──
DRY_RUN = not MODE_LIVE

# ╔══════════════════════════════════════════════════════════════════╗
# ║   JADWAL TRIGGER SCHEDULER (Fase 1). Bot nyala terus, detak 3 dtk, ║
# ║   nembak 1×/jam di menit MENIT_RUNNING. (Tier BULANAN dihapus.)    ║
# ╚══════════════════════════════════════════════════════════════════╝
MENIT_RUNNING       = "5"        # scheduler nembak tiap jam di menit ini (:05)
JAM_FAKTA_HARIAN    = "8"        # tier HARIAN jalan sekali sehari jam ini (08:00)
HARI_FAKTA_MINGGUAN = "SENIN"    # tier MINGGUAN: hari
JAM_FAKTA_MINGGUAN  = "9"        # tier MINGGUAN: jam (09:00 di hari itu)
# (Buat TES tier harian/mingguan pakai tes_harga.bat — JAM_TES harus SAMA dgn
#  JAM_FAKTA_HARIAN (harian) atau JAM_FAKTA_MINGGUAN + HARI_TES (mingguan).)

# ╔══════════════════════════════════════════════════════════════════╗
# ║           KPI PER-MODUL — PASANG & TAKEDOWN (EDIT DI SINI)         ║
# ║  SATU-SATUNYA sumber ambang bisnis Fase 2. Tiap modul BACA dari    ║
# ║  sini (jangan hardcode di modul). "target" = Harga Diskon/pancing  ║
# ║  per-SKU. "pjh" = penjualan/hari (rata2 30 hr). Ref: RENCANA_FASE2.║
# ╚══════════════════════════════════════════════════════════════════╝

# ── REM PENGAMAN HARGA (poin 1–4) — jaring kalau data ngaco, biar ga kebakaran massal ──
#    Dicek SEBELUM eksekusi. Kelewat ambang → SKIP + warning (jangan eksekusi).
KPI_HARGA_MAKS_UBAH_PCT  = 0.30   # maks fraksi produk 1 TOKO yg boleh keubah harganya per siklus jam.
                                  #   >30% mau keubah sekaligus = curiga data salah → SKIP TOKO + warning.
                                  #   Contoh: toko 900 produk, >270 mau keubah → skip toko itu.
KPI_HARGA_MAKS_TURUN_PCT = 0.40   # maks fraksi penurunan 1 PRODUK vs HARGA DISKON (acuan manual owner).
                                  #   target < Harga_Diskon × (1−0.40) = di bawah 60% Harga Diskon → curiga
                                  #   pancing/komisi salah input → SKIP PRODUK + warning.
                                  #   (FYI: Harga Komisi ≥ Harga Diskon, jadi komisi ga bakal salah-trigger.)

# ── HARGA / poin 1–4 — ambang TAKEDOWN per-jam (fase2_harga._cek_koreksi_turun) ──
KPI_GARANSI_SELISIH    = 500     # takedown garansi bila best  < target − ini (rupiah)
KPI_GARANSI_MARGIN_MIN = 0.07    # takedown/jangan-pasang garansi bila margin@best < ini (7%)
KPI_FLASH_SELISIH      = 10      # takedown flash bila flash    < target − ini (rupiah)
KPI_CAMPAIGN_FAKTOR    = 0.985   # takedown campaign bila harga < target × ini (di bawah 98,5%)
KPI_CAMPAIGN_STOK_MIN  = 30      # takedown campaign bila stok  < ini
# (campaign JUGA di-takedown bila stok < pjh — tanpa konstanta, murni banding)

# ── PASANG GARANSI (provisioning harian) — kebalikan ambang takedown di atas:
#    pasang HANYA jika best ≥ target−KPI_GARANSI_SELISIH DAN margin@best ≥ KPI_GARANSI_MARGIN_MIN.

# ── PASANG CAMPAIGN (provisioning mingguan) ──
KPI_CAMPAIGN_PASANG_FAKTOR     = 0.985  # harga potongan campaign MAKS target × ini
KPI_CAMPAIGN_PASANG_STOK_MIN   = 50     # syarat pasang: stok > ini
KPI_CAMPAIGN_PASANG_STOK_X_PJH = 10     # DAN stok > ini × pjh

# ── PASANG PAKET DISKON (provisioning harian) ──
KPI_PAKET_TIER        = [(2, 1), (3, 2), (7, 3)]  # (min_qty, diskon%): beli 2→1%, 3→2%, 7→3%
KPI_PAKET_USAGE_LIMIT = 100000                    # kuota pemakaian paket
KPI_PAKET_MAKS_ITEM   = 100000                    # maks produk per-paket → EFEKTIF 1 paket (ga overflow).
                                                  # Batas item asli Shopee GA di-ekspos API (cek 12 Jul); paket
                                                  # #5 lama muat 227 produk lancar. Kalau nanti attach gagal
                                                  # massal (deal penuh), turunkan ke angka asli yg ketauan.

# ── PASANG VOUCHER (provisioning harian) — voucher PRODUK per BAND harga (spec owner 13 Jul):
#    band 1..BAND1_MAKS lalu per BAND_LEBAR (grid fix); MIN BELANJA = batas atas band + 1
#    (maksa pembeli ambil >1 pcs). CAP: band yg min-nya > 2×AOV dibuang (aturan Shopee,
#    keputusan owner) → produk mahal TANPA voucher. ──
KPI_VOUCHER_DISKON_PCT      = 2       # diskon voucher default (%)
KPI_VOUCHER_BAND_LEBAR      = 20000   # lebar band harga voucher produk (per 20rb)
KPI_VOUCHER_BAND1_MAKS      = 14999   # band pertama: 1 .. ini (min belanja 15000)
KPI_VOUCHER_USAGE_QTY       = 100000  # kuota pemakaian voucher
KPI_VOUCHER_DURASI_HARI     = 90      # durasi voucher baru (90 verified live 13 Jul; >90 belum dites)
KPI_VOUCHER_MAKS_ITEM       = 500     # maks produk per voucher — Shopee TOLAK (ERROR_PARAM) kalau >~570
                                      # (verified 13 Jul: 570 lolos, 575 gagal). Band >ini dipecah jadi
                                      # >1 voucher (min belanja & diskon sama). 500 = aman (553 kebukti jalan).
KPI_VOUCHER_MINPRICE_FAKTOR = 2.0     # CAP band = faktor × AOV (aturan Shopee: min order ≤ 2×AOV)
KPI_VOUCHER_MINPRICE_BUFFER = 0.97    # buffer < 1 biar cap aman DI BAWAH batas Shopee
KPI_VOUCHER_AOV_WINDOW_HARI = 30      # jendela hari hitung AOV (fact_pesanan)

# ── PASANG FLASH SALE (provisioning mingguan) ──
KPI_FLASH_MAKS_PRODUK_PER_SESI = 50   # maks produk per sesi flash
KPI_FLASH_MAKS_STOK            = 350  # stok promo maks per item (aturan Shopee)
KPI_FLASH_POTONG_HARGA         = 10   # harga flash = harga_diskon − ini
KPI_FLASH_SLOT_HARI            = 7    # ambil slot s/d berapa hari ke depan
KPI_FLASH_PASANG_STOK_MIN      = 50   # syarat pasang: stok > ini
KPI_FLASH_PASANG_STOK_X_PJH    = 10   # ATAU stok > ini × pjh

# Map weekday Inggris -> Indonesia (buat banding dgn HARI_FAKTA_MINGGUAN).
HARI_ID = {
    "Monday": "SENIN", "Tuesday": "SELASA", "Wednesday": "RABU", "Thursday": "KAMIS",
    "Friday": "JUMAT", "Saturday": "SABTU", "Sunday": "MINGGU",
}

# Umur maksimum baris fakta sebelum dianggap yatim & di-prune housekeeping (hari).
FAKTA_MAKS_UMUR_HARI = 35

# KATEGORI produk (Shopee) — di-grab per-produk (get_product_info), incremental (cuma yg
# belum punya kategori). Batas per toko per siklus mingguan biar gak marathon.
MAKS_KATEGORI_PER_RUN = 800


# ╔══════════════════════════════════════════════════════════════════╗
# ║                    DAFTAR 10 TOKO (urutan = tombol "Detail")       ║
# ╚══════════════════════════════════════════════════════════════════╝
SHOP_DATABASE = {
    "kimmioshop": {"name": "Kimmioshop", "i": 1},
    "lolly0310": {"name": "lollysweet", "i": 2},
    "ravellashop": {"name": "Ravella Shop", "i": 3},
    "topikece2023": {"name": "Topikece Store", "i": 4},
    "alialiastore": {"name": "Alialia Store", "i": 5},
    "oliolio.id": {"name": "OLIOLIO.ID", "i": 6},
    "nomidestore": {"name": "NOMIDE STORE", "i": 7},
    "yarrastore": {"name": "YARRA STORE", "i": 8},
    "zioscarf": {"name": "ZIOSCARF SUPPLIER HIJAB IMPORT", "i": 9},
    "beverra": {"name": "BEVERRA OFFICIAL STORE", "i": 10},
}


def daftar_toko_aktif():
    """SHOP_DATABASE yang difilter sesuai TOKO_AKTIF (urutan & 'i' dipertahankan)."""
    if not TOKO_AKTIF:
        return SHOP_DATABASE
    return {u: info for u, info in SHOP_DATABASE.items() if u in TOKO_AKTIF}


# Allowlist pengaman: semua operasi dibatasi ke 10 toko resmi di atas -> toko
# sub-akun lain otomatis di-skip (tidak ke-grab / tidak diubah).
def username_toko_resmi():
    return set(SHOP_DATABASE.keys())


def nama_toko_resmi():
    return {info["name"] for info in SHOP_DATABASE.values()}


def username_dari_nama(nama):
    """Nama tampilan toko -> username (kebalikan SHOP_DATABASE). None kalau tak ketemu.
    Dipakai mis. resolve komisi (harga_komisi_toko pakai username_toko, diagnosa pakai nama)."""
    for u, info in SHOP_DATABASE.items():
        if info["name"] == nama:
            return u
    return None


def is_toko_resmi(nama_tampilan):
    return nama_tampilan in nama_toko_resmi()


# ╔══════════════════════════════════════════════════════════════════╗
# ║       TEKNIS — JARANG DIUBAH (endpoint, header, konstanta)         ║
# ╚══════════════════════════════════════════════════════════════════╝

# ── Kredensial (dari .env) ──
SHOPEE_PASSWORD = os.getenv("SHOPEE_PASSWORD", "")

# ── Browser (session.py). Port HARUS beda project lain (iklan 9555/9560). ──
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
CHROME_PORT = 9556
CHROME_USER_DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "__chrome_profile")

# ── Filter stok & field stok Shopee ──
STOK_FIELD = "total_available_stock"   # / "total_seller_stock" / "total_shopee_stock"

# ── Label sumber harga (campaign_type dari ongoing_campaigns) ──
#    3=Paket Diskon, 8=Promo Toko, 11=Garansi Harga Terbaik, 0=Campaign.
PROMO_LABEL = {0: "Campaign", 3: "Paket Diskon", 8: "Promo Toko", 11: "Garansi Harga Terbaik"}
LABEL_HARGA_AWAL = "Harga Awal"    # tidak ada promo -> origin_price
LABEL_PROMO_LAIN = "Promosi Lain"  # ada promo tapi tipe belum dikenali

# ── Fase 2: sumber harga mana yang bot boleh koreksi / takedown ──
# HANYA Promo Toko & Harga Awal yg dikoreksi (SAMA dgn bot 02 acuan).
# Garansi Harga Terbaik SENGAJA TIDAK di sini: dia auto-nurunin harga ikut kompetitor
# (BUKAN badge) -> koreksi percuma ditarik balik. Ditangani PR terpisah (opt-out Garansi).
SUMBER_BOLEH_RUBAH = ["Promo Toko", "Harga Awal"]
# Dikunci promo penindih TAPI ada handler takedown otomatis -> takedown lalu koreksi.
SUMBER_TAKEDOWN_OTOMATIS = ["Campaign"]
# Dikunci promo TANPA handler takedown (endpoint belum ada) -> di-FLAG "perlu takedown".
SUMBER_BLOKIR_MANUAL = ["Paket Diskon", "Promosi Lain"]
# Sumber yg SENGAJA dilewati (ditangani PR terpisah): auto-lower / proteksi.
SUMBER_SKIP_PR = ["Garansi Harga Terbaik", "Komisi"]

# ── Konstanta harga/promo ──
FAKTOR_HARGA = 100000            # uang di API promo = rupiah × 100000
STATUS_AKTIF = 1                 # item campaign: 1=ikut promo, 2=keluar
STATUS_NONAKTIF = 2
STATUS_FLASH_KELUAR = 0          # item flash sale: 0=keluar, 1=ikut
STATUS_FLASH_IKUT = 1
# ✅ M4 (14 Jul): takedown FLASH = AKHIRI SESI (bukan per-item). Endpoint per-item
# `set_shop_flash_sale_items` ditolak Shopee (1001), jadi flash_sale.takedown_items sekarang
# panggil flash_sale_daftar.stop_sesi (POST set_shop_flash_sale {flash_sale_id,time_slot_id,status:2}).
# ✅ (15 Jul): sesi yg diakhirin LANGSUNG DIGANTI real-time — sesi baru dibikin di SLOT SAMA
# (reuse timeslot_id, ga ada endpoint "hapus" terpisah dari Shopee) lalu produk SEHAT (semua
# item di sesi lama MINUS yg bermasalah) didaftar ulang pake data fresh (flash_sale_daftar.ganti_sesi).
# True = emergency off-switch (skip stop+ganti semua). False = jalan (DRY-safe). ⚠️ tes DRY+scope dulu,
# lalu 1x live scoped test dulu buat pastiin Shopee ngizinin bikin sesi baru di slot yg baru distop.
SKIP_FLASH_TAKEDOWN = False
MAKS_PRODUK_PER_PROMO = 999      # > ini -> dipecah jadi beberapa promo
PROMO_IMAGES = []                # thumbnail promo (boleh kosong; Shopee isi otomatis)
DUPLIKAT_PROMO_SIMULASI = False  # (dilewati kalau DRY_RUN sudah True)
EDIT_HARGA_DASAR_AKTIF = True    # izinkan ubah harga dasar saat target >= harga awal
UPDATE_HARGA_TERVERIFIKASI = True  # kunci pengaman Fase 2 (sudah diverifikasi -> True)

# ── Endpoint API Shopee (terverifikasi DevTools/sniff) ──
URL_GRAB_PRODUK = "https://seller.shopee.co.id/api/v3/opt/mpsku/list/v2/search_product_list"
# Detail produk (buat KATEGORI). Param: product_id + is_draft=false. Response:
# data.product_info.category_path (ID) + category_path_name_list (nama). Verified 9 Jul.
URL_GET_PRODUCT_INFO = "https://seller.shopee.co.id/api/v3/product/get_product_info"
URL_CEK_BLOKIR = "https://seller.shopee.co.id/api/v3/opt/product/get_campaign_info_by_item_list/"
URL_FLASH_LIST = "https://seller.shopee.co.id/api/marketing/v4/shop_flash_sale/get_shop_flash_sale_list/"
URL_FLASH_ITEMS = "https://seller.shopee.co.id/api/marketing/v4/shop_flash_sale/get_shop_flash_sale_item/"
URL_FLASH_SET_ITEMS = "https://seller.shopee.co.id/api/marketing/v4/shop_flash_sale/set_shop_flash_sale_items/"
URL_LIST_DISKON = "https://seller.shopee.co.id/api/marketing/v3/public/discount/list/"
URL_UPDATE_HARGA = "https://seller.shopee.co.id/api/marketing/v4/discount/update_seller_discount_items/"
URL_EDIT_HARGA_DASAR = "https://seller.shopee.co.id/api/v3/product/update_product_info_for_quick_edit"
URL_CREATE_PROMO = "https://seller.shopee.co.id/api/marketing/v4/discount/create_discount/"
URL_STOP_PROMO = "https://seller.shopee.co.id/api/marketing/v4/discount/delete_stop_discount/"
URL_GET_PROMO_DETAIL = "https://seller.shopee.co.id/api/marketing/v4/discount/get_discount_list/"
URL_GET_PROMO_ITEMS = "https://seller.shopee.co.id/api/marketing/v4/discount/get_discount_items_aggregated/"

# ── Endpoint campaign bulanan (cmt) — takedown/nominasi ──
URL_GET_LANDING_CAMPAIGN = "https://seller.shopee.co.id/api/mkt/cmt/get_landing_page_campaign_list"
URL_GET_SESSION_LIST = "https://seller.shopee.co.id/api/mkt/cmt/commonscene/get_session_list"
URL_GET_NOMINATED_LIST = "https://seller.shopee.co.id/api/mkt/cmt/nominated/nominated_entity_list"
URL_PREVIEW_ADD = "https://seller.shopee.co.id/api/mkt/cmt/preview/add"
URL_PREVIEW_LIST = "https://seller.shopee.co.id/api/mkt/cmt/preview/preview_list"
URL_SUBMIT_NOMINATION = "https://seller.shopee.co.id/api/mkt/cmt/preview/submit_entity_online"
URL_OPT_OUT_NOMINATION = "https://seller.shopee.co.id/api/mkt/cmt/nominated/opt_out"
URL_SESSION_NOMINATION_STATS = "https://seller.shopee.co.id/api/mkt/cmt/session/get_session_nomination_statistics"
URL_PRODUCT_SELECTOR_VERIFY = "https://seller.shopee.co.id/api/mkt/cmt/product/online/selector/verify"
CAMPAIGN_KEYWORDS = ["gajian", "double", "kembar", "6.6", "7.7", "8.8", "9.9", "10.10", "11.11", "12.12"]
CAMPAIGN_DISCOUNT_TOLERANCE = 0.02   # maks 2% diskon dari target

# ── Template header API Shopee ──
SC_FE_VER = "21.142872"
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36")
REFERER = "https://seller.shopee.co.id/portal/product/list/all"


def grab_headers(session):
    """Header standar request API Shopee (pakai cookie & sesi dari login)."""
    return {
        "accept": "application/json, text/plain, */*",
        "accept-encoding": "gzip, deflate, br, zstd",
        "accept-language": "en-US,en;q=0.9,id;q=0.8",
        "cookie": session["headers"]["cookie"],
        "priority": "u=1, i",
        "referer": REFERER,
        "sc-fe-session": session["headers"]["sc-fe-session"],
        "sc-fe-ver": SC_FE_VER,
        "sec-ch-ua": '"Chromium";v="146", "Not-A.Brand";v="24", "Google Chrome";v="146"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": USER_AGENT,
    }


def fmt_angka(n):
    """Pemisah ribuan titik gaya Indonesia. 100000 -> '100.000'."""
    try:
        return f"{int(n):,}".replace(",", ".")
    except (ValueError, TypeError):
        return str(n)


# ── Peta nama→huruf kolom (sisa era Google Sheet; masih dirujuk `update_harga.py` via config.KOL). ──
KOL = {
    "toko": "A", "item": "B", "model": "C", "sku": "E", "nama_variasi": "F",
    "nama_produk": "G", "harga_awal": "H", "harga_akhir": "K", "harga_diskon": "L",
    "keterangan": "N", "alasan": "O",
}
