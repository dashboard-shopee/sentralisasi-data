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

# 1) MODE — simulasi atau beneran?
#    False = DRY-RUN (SIMULASI, AMAN): hitung + catat rencana, TIDAK ubah Shopee.
#    True  = LIVE: beneran ubah harga / bikin promo di Shopee.
MODE_LIVE = True

# 2) FASE yang dijalankan saat dobel-klik RUN.bat (python run.py tanpa argumen).
#    Boleh gabung, dijalankan berurutan.
#      1 = GRAB produk + konteks promo + HPP Jubelio
#      2 = RUBAH HARGA ke Harga Diskon (butuh MODE_LIVE=True biar beneran)
#      3 = VERIFIKASI (re-grab + banding harga real vs target)
#      4 = PERPANJANG / buat Promo Toko
#    Contoh: [1] · [2,3] · [1,2,3] full · [4]
FASE_AKTIF = [1,2,3]

# 3) TOKO yang diproses.  [] = SEMUA 10 toko.  ["kimmioshop"] = 1 toko.
TOKO_AKTIF = []
# TOKO_AKTIF = ["kimmioshop"]

# 4) Setelan yang kadang diubah:
STOK_MINIMAL = 1                 # grab hanya variasi stok >= ini (0 dilewati)
NAMA_PROMO = "PROMO TOKO"        # nama campaign Diskon Toko yang dikelola bot
JELANG_EXPIRE_HARI = 1           # perpanjang promo bila sisa <= ini (hari)
DURASI_PROMO_HARI = 180          # durasi promo baru (maks 180 sesuai Shopee)
BUAT_PROMO_DARI_NOL = True       # bikin promo baru kalau toko belum punya promo toko
JEDA_VERIFIKASI_DETIK = 30        # jeda sebelum Fase 3 re-grab (beri waktu Shopee propagasi harga)

# ── (turunan otomatis dari MODE_LIVE; env HARGA_LIVE=1 juga memaksa LIVE) ──
DRY_RUN = not (MODE_LIVE or os.getenv("HARGA_LIVE", "0") == "1")


# ╔══════════════════════════════════════════════════════════════════╗
# ║        SCHEDULER 24 JAM — FASE 1 (pola sama Syntra_Iklan)          ║
# ║  Bot nyala terus, detak tiap 3 detik (tanpa log), nembak 1×/jam    ║
# ║  di menit MENIT_RUNNING. Tiap tier fakta dipicu by JAM/HARI/TGL.   ║
# ║  Semua bisa di-custom di sini.                                     ║
# ╚══════════════════════════════════════════════════════════════════╝
MENIT_RUNNING         = "5"       # nembak tiap jam di menit ini (:05)
# TIER HARIAN (Garansi + Campaign) — jalan sekali sehari di jam ini.
JAM_FAKTA_HARIAN      = "2"       # 02:00
# TIER MINGGUAN (Flash Sale + Voucher + Paket Diskon) — sekali seminggu.
HARI_FAKTA_MINGGUAN   = "SENIN"   # hari grab mingguan
JAM_FAKTA_MINGGUAN    = "3"       # 03:00 (di hari mingguan)
# TIER BULANAN (housekeeping: prune fakta yatim) — sekali sebulan.
TANGGAL_FAKTA_BULANAN = "1"       # tanggal grab bulanan
JAM_FAKTA_BULANAN     = "4"       # 04:00 (di tanggal bulanan)

# Map weekday Inggris -> Indonesia (buat banding dgn HARI_FAKTA_MINGGUAN).
HARI_ID = {
    "Monday": "SENIN", "Tuesday": "SELASA", "Wednesday": "RABU", "Thursday": "KAMIS",
    "Friday": "JUMAT", "Saturday": "SABTU", "Sunday": "MINGGU",
}

# Umur maksimum baris fakta sebelum dianggap yatim & di-prune housekeeping (hari).
FAKTA_MAKS_UMUR_HARI = 35


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
# ⚠️ SKIP takedown FLASH SALE sementara (PR flash sale besok). Endpoint per-item
# `set_shop_flash_sale_items` DITOLAK Shopee (code 1001 "spex common error") 100% -> tak ada
# yg ke-takedown, cuma buang waktu (Yarra ratusan sesi × retry 2s). True = lewati Fase 2A/2B flash.
# Perbaikan: re-sniff endpoint remove item flash sale yg benar (yg verified baru `set_shop_flash_sale`
# level-SESI: body {flash_sale_id, time_slot_id, status}). Balikin False setelah endpoint benar.
SKIP_FLASH_TAKEDOWN = True
MAKS_PRODUK_PER_PROMO = 999      # > ini -> dipecah jadi beberapa promo
PROMO_IMAGES = []                # thumbnail promo (boleh kosong; Shopee isi otomatis)
DUPLIKAT_PROMO_SIMULASI = False  # (dilewati kalau DRY_RUN sudah True)
EDIT_HARGA_DASAR_AKTIF = True    # izinkan ubah harga dasar saat target >= harga awal
UPDATE_HARGA_TERVERIFIKASI = True  # kunci pengaman Fase 2 (sudah diverifikasi -> True)

# ── Endpoint API Shopee (terverifikasi DevTools/sniff) ──
URL_GRAB_PRODUK = "https://seller.shopee.co.id/api/v3/opt/mpsku/list/v2/search_product_list"
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


# ╔══════════════════════════════════════════════════════════════════╗
# ║   LEGACY — Google Sheet (warisan bot 02, dipakai modul lama saja)  ║
# ║   Sudah migrasi ke SQL; JANGAN dipakai lagi. Disimpan agar modul    ║
# ║   warisan (sku_sync/update_campaign/verifikasi_harga) tidak error.  ║
# ╚══════════════════════════════════════════════════════════════════╝
SHEET_ID = "1DQpoWjbeGMuM5MNOucN9g35CYEJQo5QX8B_iaLeyS3s"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit"
TAB_HARGA = "Olah Data"
BARIS_AWAL = 3
TAB_ALL_PRODUK = "ALL PRODUK"
BARIS_AWAL_ALL_PRODUK = 3
SINKRON_SKU_AKTIF = True
FMT_TANGGAL_SKU = "%d/%m/%y"
FMT_TIMESTAMP = "Terakhir diupdate: %d/%m/%Y %H:%M:%S"
# Pemetaan kolom sheet lama (kol 'alasan'/'harga_diskon'/'keterangan' masih dirujuk modul warisan).
KOL = {
    "toko": "A", "item": "B", "model": "C", "sku": "E", "nama_variasi": "F",
    "nama_produk": "G", "harga_awal": "H", "harga_akhir": "K", "harga_diskon": "L",
    "keterangan": "N", "alasan": "O",
}


def google_service_account():
    """Rekonstruksi dict service-account gspread (warisan; SQL tak memakainya)."""
    client_email = os.getenv("GOOGLE_CLIENT_EMAIL", "")
    return {
        "type": "service_account",
        "project_id": os.getenv("GOOGLE_PROJECT_ID", ""),
        "private_key_id": os.getenv("GOOGLE_PRIVATE_KEY_ID", ""),
        "private_key": os.getenv("GOOGLE_PRIVATE_KEY", "").replace("\n", "\n"),
        "client_email": client_email,
        "client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/"
        + client_email.replace("@", "%40"),
        "universe_domain": "googleapis.com",
    }
