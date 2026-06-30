"""
grab_produk.py — Layer 2 (LANGKAH 1).

Ambil SEMUA produk + variasi (model) dari satu toko Shopee lewat API internal,
kembalikan list baris siap-tulis ke Sheet. Penulisan ke Sheet dilakukan SEKALI
oleh orkestrator (run.py).

Tiap baris = satu MODEL (variasi):
  [toko, item_id, model_id, sku, nama_variasi, nama_produk, harga_awal, harga_diskon]

──────────────────────────────────────────────────────────────────────────────
✅ Endpoint & struktur TERVERIFIKASI dari DevTools:
   GET /api/v3/opt/mpsku/list/v2/search_product_list  (pagination = cursor)
   data.products[]                 -> id (item_id), name (nama produk), parent_sku
     .model_list[]                 -> id (model_id), name (nama variasi), sku
       .price_detail.origin_price      "20000.00"  (harga awal)
       .price_detail.promotion_price   "5800.00" / "0.00"  (0 = promo mati)
──────────────────────────────────────────────────────────────────────────────
"""
import colorama; colorama.init()
import config
from modules.api_util import api_get


# Harga di list-API berbentuk string rupiah "20000.00" / "0.00".
def _rupiah(v):
    if v in (None, "", "None"):
        return 0
    try:
        return int(round(float(v)))
    except (ValueError, TypeError):
        return 0


# Label sumber promo dari campaign_type.
def _label_promo(ct):
    return config.PROMO_LABEL.get(ct, config.LABEL_PROMO_LAIN)


# Tentukan SUMBER harga yang dimunculkan (kolom N).
#   promo_tampil = harga promo terkini (rupiah, 0 = tidak ada promo)
#   kandidat     = list (campaign_type, harga_rupiah) campaign ongoing utk variasi ini
def _sumber_harga(promo_tampil, kandidat):
    if promo_tampil <= 0:
        return config.LABEL_HARGA_AWAL
    cocok = [ct for ct, p in kandidat if p == promo_tampil]
    return _label_promo(cocok[0]) if cocok else config.LABEL_PROMO_LAIN


# Petakan promotion_detail.ongoing_campaigns -> {model_id: [(campaign_type, harga_rupiah)]}
def _peta_promo(prod):
    peta = {}
    pdet = prod.get("promotion_detail") or {}
    for c in (pdet.get("ongoing_campaigns") or []):
        if isinstance(c, dict):
            mid = c.get("model_id", 0)
            peta.setdefault(mid, []).append((c.get("campaign_type"), _rupiah(c.get("promotion_price"))))
    return peta


# Ambil nilai stok dari objek (model/produk) sesuai config.STOK_FIELD.
def _stok(obj):
    sd = obj.get("stock_detail", {}) or {}
    try:
        return int(sd.get(config.STOK_FIELD, 0) or 0)
    except (ValueError, TypeError):
        return 0


# GRAB PARAMS (daftar produk, cursor-based)
def grab_params(session, cursor="", page_size=48):
    return {
        "SPC_CDS": session["params"].get("SPC_CDS"),
        "SPC_CDS_VER": session["params"].get("SPC_CDS_VER", 2),
        "page_size": page_size,
        "list_type": "all",
        "request_attribute": "",
        "operation_sort_by": "recommend_v4",
        "need_ads": "true",
        "cursor": cursor,
    }


# GRAB PRODUK — kumpulkan semua model dari satu toko (HANYA yang stoknya > 0)
def grab_produk(shop, nama_toko, session):
    baris = []
    cursor = ""
    total = 0
    collected = 0
    halaman = 0
    dilewati = 0   # jumlah model dilewati karena stok 0
    while True:
        halaman += 1
        data = api_get(
            config.URL_GRAB_PRODUK,
            config.grab_headers(session),
            grab_params(session=session, cursor=cursor),
            kunci="data",
        )["data"]

        produk_list = data.get("products", [])
        page_info = data.get("page_info", {})
        total = int(page_info.get("total", 0)) or total

        for prod in produk_list:
            if not isinstance(prod, dict):
                continue
            item_id = prod.get("id")
            nama_produk = str(prod.get("name", ""))
            models = [m for m in (prod.get("model_list") or []) if isinstance(m, dict)]
            promo_map = _peta_promo(prod)   # {model_id: [(campaign_type, harga)]}

            if not models:
                # Produk tanpa variasi -> satu baris, model_id 0
                if _stok(prod) < config.STOK_MINIMAL:
                    dilewati += 1
                    continue
                pd = prod.get("price_detail", {})
                origin = _rupiah(pd.get("price_min"))
                promo = _rupiah(pd.get("selling_price_min")) if pd.get("has_discount") else 0
                tampil = promo if promo > 0 else origin   # harga yang dimunculkan
                sumber = _sumber_harga(promo, promo_map.get(0, []))
                baris.append([nama_toko, item_id, 0, prod.get("parent_sku", ""),
                              "", nama_produk, origin, tampil, sumber])
                _log(shop, len(baris), item_id, tampil, sumber)
                continue

            for m in models:
                # FILTER STOK: lewati variasi yang stoknya 0
                if _stok(m) < config.STOK_MINIMAL:
                    dilewati += 1
                    continue
                mp = m.get("price_detail", {})
                origin = _rupiah(mp.get("origin_price"))
                promo = _rupiah(mp.get("promotion_price"))
                tampil = promo if promo > 0 else origin   # harga yang dimunculkan ke pembeli
                # kandidat campaign utk variasi ini (+ campaign level-produk model_id 0)
                kandidat = promo_map.get(m.get("id"), []) + promo_map.get(0, [])
                sumber = _sumber_harga(promo, kandidat)
                baris.append([nama_toko, item_id, m.get("id"), str(m.get("sku", "") or ""),
                              str(m.get("name", "")), nama_produk, origin, tampil, sumber])
                _log(shop, len(baris), f"{item_id}/{m.get('id')}", tampil, sumber)

        collected += len(produk_list)
        cursor = page_info.get("cursor", "")
        if (not produk_list) or (total and collected >= total) or (not cursor) or (halaman > 500):
            break
    print(colorama.Fore.LIGHTGREEN_EX
          + f"[grab produk] [{shop}] - SELESAI: {len(baris)} variasi berstok, {dilewati} dilewati (stok 0)"
          + colorama.Style.RESET_ALL)
    return baris


def _log(shop, n, kode, harga, sumber=""):
    print(colorama.Fore.WHITE
          + f"[grab produk] [{shop}] [{n}] - {kode} [{config.fmt_angka(harga)}] ({sumber})"
          + colorama.Style.RESET_ALL)

# (tulis_produk ke Google Sheet DIHAPUS — penyimpanan sekarang lewat
#  modules/sql_harga.simpan_olah_data ke tabel harga_olah_data.)
