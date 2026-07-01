"""
config.py — Pusat konfigurasi (Layer 0) untuk BOT RUBAH HARGA SHOPEE.

Semua kredensial, URL Sheet, daftar toko, pemetaan kolom, endpoint API, dan
template header dikumpulkan di sini supaya tidak diduplikasi di tiap modul.
Rahasia dibaca dari file .env (lihat .env.example).

Pola & arsitektur mengikuti project "Otomatisasi Iklan Shopee":
  Layer 0 config -> Layer 1 session (browser harvest) -> Layer 2 grab ->
  Layer 4 aksi (rubah harga) -> orkestrator (run.py).
"""

import os
from dotenv import load_dotenv

load_dotenv()


# ============================================================
#  KREDENSIAL (dari .env)
# ============================================================
SHOPEE_PASSWORD = os.getenv("SHOPEE_PASSWORD", "")

# ── SAKLAR KEAMANAN FASE 2 (rubah harga) ──
# DRY_RUN True  = SIMULASI: hitung perubahan + catat alasan, TIDAK kirim ke Shopee.
# DRY_RUN False = LIVE: beneran ubah harga promo / harga dasar. Set env HARGA_LIVE=1.
DRY_RUN = os.getenv("HARGA_LIVE", "0") != "1"


def google_service_account():
    """Rekonstruksi dict service-account untuk gspread.service_account_from_dict()."""
    client_email = os.getenv("GOOGLE_CLIENT_EMAIL", "")
    return {
        "type": "service_account",
        "project_id": os.getenv("GOOGLE_PROJECT_ID", ""),
        "private_key_id": os.getenv("GOOGLE_PRIVATE_KEY_ID", ""),
        "private_key": os.getenv("GOOGLE_PRIVATE_KEY", "").replace("\\n", "\n"),
        "client_email": client_email,
        "client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/"
        + client_email.replace("@", "%40"),
        "universe_domain": "googleapis.com",
    }


# ============================================================
#  BROWSER (dipakai session.py untuk login & panen sesi)
# ============================================================
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
# Port HARUS beda dari project lain biar gak nempel ke browsernya:
#   - 9222 dipakai Lenovo Vantage
#   - 9555 dipakai project "Otomatisasi Iklan Shopee"
#   - 9556 -> project ini (Rubah Harga), browser & login sendiri
CHROME_PORT = 9556
CHROME_USER_DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "__chrome_profile")


# ============================================================
#  GOOGLE SHEET
# ============================================================
SHEET_ID = "1DQpoWjbeGMuM5MNOucN9g35CYEJQo5QX8B_iaLeyS3s"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit"

# Nama tab tujuan. Kosongkan ("" / None) -> pakai sheet pertama.
# TODO: isi nama tab yang benar bila bukan sheet pertama.
TAB_HARGA = "Olah Data"

# Data mulai baris ke-3 (baris 1-2 = judul/header manual).
BARIS_AWAL = 3

# ── SINKRON SKU -> tab "ALL PRODUK" ──────────────────────────
# Daftar master SKU. SKU yang sudah ada di Olah Data!E tapi BELUM terdaftar di
# ALL PRODUK!B akan di-append ke bawah: kolom A = tanggal ditambahkan, B = SKU.
# Struktur ALL PRODUK: baris 1 = header (A=timestamp, B="SKU", C="SKU Induk",
# D="Nama Produk"), baris 2 = "Update SKU", DATA mulai baris 3.
TAB_ALL_PRODUK = "ALL PRODUK"
BARIS_AWAL_ALL_PRODUK = 3
SINKRON_SKU_AKTIF = True               # False = lewati sinkron SKU & timestamp
# Format tanggal kolom A ALL PRODUK (mengikuti baris lama, mis. "06/03/26").
FMT_TANGGAL_SKU = "%d/%m/%y"
# Teks timestamp di A1 (Olah Data & ALL PRODUK), mis. "Terakhir diupdate: 18/06/2026 15:56:58".
FMT_TIMESTAMP = "Terakhir diupdate: %d/%m/%Y %H:%M:%S"

# ── PEMETAAN KOLOM SHEET ─────────────────────────────────────
# Bot HANYA menulis: A,B,C,E,F,G,H (Langkah 1) + L (Langkah 1 & 3) + N (Langkah 3).
# A: nama toko          B: kode produk (item_id)   C: kode variasi (model_id)
# E: sku                F: nama variasi            G: nama produk
# H: harga awal         L: harga diskon / Harga Real (promotion_price)
# N: keterangan (hasil banding K vs L)
# TIDAK disentuh bot (punya user / rumus):
#   D=PTAG  I=HARGA DISKON(db sendiri)  J=Harga Pancing  K=HARGA AKHIR(rumus, dibaca saja)  M=SELISIH(rumus)
KOL = {
    "toko": "A",
    "item": "B",
    "model": "C",
    "sku": "E",
    "nama_variasi": "F",
    "nama_produk": "G",
    "harga_awal": "H",
    "harga_akhir": "K",     # rumus user — bot HANYA membaca (target Langkah 2 & 3)
    "harga_diskon": "L",    # promotion_price terkini (ditulis Langkah 1 & 3)
    "keterangan": "N",      # sumber harga yang dimunculkan (ditulis Langkah 1 & 3)
    "alasan": "O",          # alasan kenapa harga tidak/ belum dirubah (ditulis Langkah 2)
}

# ── SUMBER HARGA (kolom N, Langkah 1 & 3) ────────────────────
# campaign_type dari promotion_detail.ongoing_campaigns -> label sumber harga tampil.
# Terverifikasi: 3=Paket Diskon, 8=Promo Toko, 11=Garansi Harga Terbaik.
# Tambah di sini bila ketemu tipe baru (Flash Sale / Campaign / Voucher / dll).
PROMO_LABEL = {
    0: "Campaign",
    3: "Paket Diskon",
    8: "Promo Toko",
    11: "Garansi Harga Terbaik",
}
LABEL_HARGA_AWAL = "Harga Awal"   # harga tampil = origin_price (tidak ada promo)
LABEL_PROMO_LAIN = "Promosi Lain" # ada promo tapi tipe belum dikenali

# Fase 2 mengoreksi harga bila sumber (kolom N) ada di daftar ini.
# "Garansi Harga Terbaik" = BADGE harga terjamin termurah (bukan promo yg menyetel
# harga) -> harga tetap milik toko, JADI boleh dikoreksi ke Harga Diskon.
SUMBER_BOLEH_RUBAH = ["Promo Toko", "Harga Awal", "Garansi Harga Terbaik"]

# Sumber yang harganya DIKUNCI promo penindih & PUNYA handler takedown otomatis:
# takedown dulu (di jalur promo toko / base), lalu koreksi ke Harga Diskon.
SUMBER_TAKEDOWN_OTOMATIS = ["Campaign"]      # Flash Sale ditangani via konteks (base-edit)
# Sumber dikunci promo TANPA handler takedown (endpoint belum ada) -> ditandai jelas.
SUMBER_BLOKIR_MANUAL = ["Paket Diskon", "Promosi Lain"]


# ── FILTER STOK (Langkah 1) ──────────────────────────────────
# Hanya tulis produk yang stoknya >= STOK_MINIMAL. Produk stok 0 dilewati
# (biar baris Sheet tidak kebanyakan). Stok TIDAK ditulis ke Sheet.
# Field stok yang dipakai (ganti bila perlu):
#   "total_available_stock" (default) / "total_seller_stock" / "total_shopee_stock"
STOK_FIELD = "total_available_stock"
STOK_MINIMAL = 1


# ============================================================
#  DAFTAR TOKO  (urutan = posisi tombol "Detail" di shop switcher)
# ============================================================
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


# ============================================================
#  KONFIG JALANKAN (custom: semua / sebagian / satu toko + langkah)
# ============================================================
# Toko yang diproses:
#   []                                     -> SEMUA toko
#   ["alialiastore"]                       -> 1 toko saja
#   ["alialiastore", "ravellashop", ...]   -> sebagian toko
TOKO_AKTIF = []
# TOKO_AKTIF = ["beverra"]
# TOKO_AKTIF = ["kimmioshop","lolly0310","ravellashop","topikece2023","alialiastore","oliolio.id","nomidestore","zioscarf","beverra"]

# Langkah yang dijalankan (boleh pilih sebagian):
#   1 = AMBIL produk berstok -> tulis Sheet (A,B,C,E,F,G,H,L)
#   2 = RUBAH harga (promo K<H / harga dasar K>=H). Kalau toko belum punya promo toko -> BIKIN dari 0
#   3 = AMBIL ulang -> tulis L (harga tampil) + N (sumber harga)
#   4 = PERPANJANG promo toko: duplikat kalau <1 hari sebelum expiry (jalankan berkala)
#   5 = KAMPANYE BULANAN (daftar & takedown kampanye bulanan Shopee)
# Contoh: [1] ambil; [2,3] rubah+verifikasi; [1,2,3] full; [4] perpanjang promo; [5] kampanye bulanan.
LANGKAH_AKTIF = [1]
# LANGKAH_AKTIF = [5]


def daftar_toko_aktif():
    """SHOP_DATABASE yang difilter sesuai TOKO_AKTIF (urutan & 'i' dipertahankan)."""
    if not TOKO_AKTIF:
        return SHOP_DATABASE
    return {u: info for u, info in SHOP_DATABASE.items() if u in TOKO_AKTIF}


# ── ALLOWLIST 10 TOKO RESMI (pengaman: kecualikan/skip toko sub-akun lain) ──
# Semua operasi (grab, tulis DB, hitung Harga Diskon) DIBATASI ke toko ini saja.
# username -> untuk verifikasi shop_switcher; nama tampilan -> untuk filter tabel harga_*.
def username_toko_resmi():
    """Set username 10 toko resmi (dari SHOP_DATABASE)."""
    return set(SHOP_DATABASE.keys())


def nama_toko_resmi():
    """Set NAMA TAMPILAN 10 toko resmi (kolom `toko` di tabel harga_*)."""
    return {info["name"] for info in SHOP_DATABASE.values()}


def is_toko_resmi(nama_tampilan):
    """True kalau nama tampilan toko termasuk 10 toko resmi."""
    return nama_tampilan in nama_toko_resmi()


# ============================================================
#  ENDPOINT API SHOPEE  (Layer 2 & 4)
#  ⚠️ VERIFIKASI dari DevTools (tab Network) saat buka halaman terkait.
#     URL & struktur payload/response bisa berbeda — lihat catatan di
#     modules/grab_produk.py & modules/update_harga.py.
# ============================================================
# ✅ TERVERIFIKASI — daftar produk + variasi + harga (cursor-based).
URL_GRAB_PRODUK = "https://seller.shopee.co.id/api/v3/opt/mpsku/list/v2/search_product_list"
# ✅ TERVERIFIKASI (sniff) — flag RESMI apakah item keblok utk ubah promo/harga.
#    POST body {"item_id_list":[...]} -> data.campaign_info[item_id].is_blocked_for_promotion
URL_CEK_BLOKIR = "https://seller.shopee.co.id/api/v3/opt/product/get_campaign_info_by_item_list/"

# ✅ TERVERIFIKASI (sniff) — FLASH SALE TOKO (daftar/takedown item).
#   list: GET  ?offset&limit&type=0 -> data.flash_sale_list[] (flash_sale_id, status, timeslot_id)
#   item: GET  ?flash_sale_id&offset&limit -> data.items[] (item_id, model_id, status, promotion_price, stock, item_display_image, purchase_limit)
#   set : POST {flash_sale_id, items:[{item_id, model_id, status(0=keluar/1=ikut), input_promo_price, stock, item_display_image, purchase_limit}]}
URL_FLASH_LIST = "https://seller.shopee.co.id/api/marketing/v4/shop_flash_sale/get_shop_flash_sale_list/"
URL_FLASH_ITEMS = "https://seller.shopee.co.id/api/marketing/v4/shop_flash_sale/get_shop_flash_sale_item/"
URL_FLASH_SET_ITEMS = "https://seller.shopee.co.id/api/marketing/v4/shop_flash_sale/set_shop_flash_sale_items/"
# ✅ TERVERIFIKASI — cari campaign Diskon Toko (ambil promotion_id).
URL_LIST_DISKON = "https://seller.shopee.co.id/api/marketing/v3/public/discount/list/"
# ✅ TERVERIFIKASI — simpan/ubah harga item di campaign Diskon Toko.
URL_UPDATE_HARGA = "https://seller.shopee.co.id/api/marketing/v4/discount/update_seller_discount_items/"
# ✅ TERVERIFIKASI — edit HARGA DASAR produk (quick edit). Harga = STRING rupiah, TANPA ×100000.
URL_EDIT_HARGA_DASAR = "https://seller.shopee.co.id/api/v3/product/update_product_info_for_quick_edit"
# ✅ TERVERIFIKASI — buat promo baru (Langkah 5) & stop/hapus promo.
URL_CREATE_PROMO = "https://seller.shopee.co.id/api/marketing/v4/discount/create_discount/"
URL_STOP_PROMO = "https://seller.shopee.co.id/api/marketing/v4/discount/delete_stop_discount/"
# ✅ TERVERIFIKASI — detail promo (judul/gambar/tanggal) & daftar item dalam promo.
URL_GET_PROMO_DETAIL = "https://seller.shopee.co.id/api/marketing/v4/discount/get_discount_list/"
URL_GET_PROMO_ITEMS = "https://seller.shopee.co.id/api/marketing/v4/discount/get_discount_items_aggregated/"

# ── PARAMETER LANGKAH 5 (auto-duplikat promo toko) ───────────
DURASI_PROMO_HARI = 180          # durasi promo baru (maks 180 sesuai Shopee)
JELANG_EXPIRE_HARI = 1           # buat promo baru bila sisa <= ini (hari) sebelum berakhir
MAKS_PRODUK_PER_PROMO = 999      # batas produk per promo; > ini -> pecah jadi beberapa promo
# Mode aman: True = SIMULASI (cuma log, tidak benar-benar bikin promo). Ubah False utk eksekusi.
# BUAT PROMO DARI 0 (kalau toko belum punya promo toko aktif sama sekali) — bagian Langkah 4.
#   - produk diambil dari Sheet (baris yang K terisi & K < harga awal).
# PROMO_IMAGES = thumbnail preview promo (gambar cover produk), BUKAN banner upload — sama
# seperti buat manual yang tidak perlu upload gambar, jadi boleh DIBIARKAN KOSONG.
# (kalau diisi/ada promo lama, dipakai sebagai preview; kalau kosong, Shopee isi sendiri.)
# Nama campaign Diskon Toko yang dikelola (cocok-sebagian, tidak peka huruf besar).
# Harga diskon (kolom L) = harga item di dalam campaign ini.
DUPLIKAT_PROMO_SIMULASI = False
BUAT_PROMO_DARI_NOL = True
PROMO_IMAGES = []
NAMA_PROMO = "PROMO TOKO"

# Uang di API promo memakai micro-unit (×100000). 12.900 -> 1290000000.
FAKTOR_HARGA = 100000

# status item di campaign: 1 = AKTIF (ikut promo), 2 = dimatikan/keluar promo.
STATUS_AKTIF = 1
STATUS_NONAKTIF = 2

# status item di FLASH SALE (beda skala dgn promo toko): 0 = keluar, 1 = ikut.
STATUS_FLASH_KELUAR = 0
STATUS_FLASH_IKUT = 1

# Langkah 4b: kalau K >= harga awal (promo mustahil), ubah HARGA DASAR langsung ke K
# (keluarin dari promo dulu kalau lagi ikut). True = jalan, False = cuma ditandai.
EDIT_HARGA_DASAR_AKTIF = True

# ⚠️ KUNCI PENGAMAN — Langkah 2 (rubah harga) TIDAK jalan selama ini False.
# Sudah diverifikasi dari DevTools -> boleh True. Tetap tes 1 toko dulu.
UPDATE_HARGA_TERVERIFIKASI = True


# ============================================================
#  FORMAT ANGKA (untuk log)
# ============================================================
def fmt_angka(n):
    """Pemisah ribuan titik gaya Indonesia. 100000 -> '100.000'."""
    try:
        return f"{int(n):,}".replace(",", ".")
    except (ValueError, TypeError):
        return str(n)


# ============================================================
#  TEMPLATE HEADER API SHOPEE
# ============================================================
SC_FE_VER = "21.142872"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
)
REFERER = "https://seller.shopee.co.id/portal/product/list/all"


def grab_headers(session):
    """Header standar untuk request API Shopee, memakai cookie & sesi dari login."""
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


# ============================================================
#  KAMPANYE BULANAN SHOPEE (LANGKAH 4)
# ============================================================
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
CAMPAIGN_DISCOUNT_TOLERANCE = 0.02  # maks 2% diskon dari K

