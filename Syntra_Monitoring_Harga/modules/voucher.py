"""modules/voucher.py — AUTO daftar/perpanjang VOUCHER toko (upsell, TIDAK ubah harga).

Endpoint terverifikasi via DevTools (3 Jul 2026):
  POST marketing/v3/voucher/               -> BUAT voucher -> data.voucher_id
  PUT  marketing/v3/voucher/               -> EDIT/PERPANJANG (body + voucher_id, ganti end_time)
  GET  marketing/v3/voucher/?voucher_id=X  -> detail 1 voucher
  GET  marketing/v3/voucher/list/          -> list voucher
  POST marketing/v3/voucher/validate_items/-> validasi item (voucher produk)

Semua via requests biasa (voucher TIDAK kena anti-bot). discount = persen (2 = 2%).
max_value = batas maksimal diskon Rp (null = "Tidak Terbatas"). min_price = min belanja,
Shopee batasi <= 2x AOV toko. rule.items = [{itemid}] utk voucher PRODUK (kosong = semua produk).

3 TIPE (dibedakan param — sebagian masih perlu konfirmasi/capture bersih):
  - ikuti toko  : shop-wide, voucher_landing_page 1
  - pembeli baru: shop-wide, choose_users targeting (param persis: TODO konfirmasi)
  - produk      : rule.items terisi; dibagi 3+ BAND harga (per 20rb) via bands_harga()
"""
import time
import colorama; colorama.init()
import requests
import config

_BASE = "https://seller.shopee.co.id/api/marketing/v3/voucher/"
URL_VOUCHER = _BASE
URL_LIST = _BASE + "list/"
URL_VALIDATE = _BASE + "validate_items/"

SATU_HARI = 86400

# Preset param per TIPE voucher (dari capture DevTools; `usecase` = param URL saat bikin di UI,
# TIDAK dikirim di body). ⚠️ ikuti_toko vs pembeli_baru payload-nya NYARIS SAMA (dua-duanya
# shop_order_count:1) — pembeda pasti belum 100% jelas; verifikasi saat create live.
TIPE = {
    # Voucher Ikuti Toko (follow) — shop-wide, tampil di semua halaman.
    "ikuti_toko":   {"landing_page": 1, "display_voucher_early": False,
                     "choose_users": {"shop_order_count": 1, "shop_order_count_period": 0}},
    # Voucher Pembeli Baru (usecase=3) — shop-wide, display early.
    "pembeli_baru": {"landing_page": 0, "display_voucher_early": True,
                     "choose_users": {"shop_order_count": 1, "shop_order_count_period": 0}},
    # Voucher Produk — pakai item_ids (per band harga). Tanpa targeting user.
    "produk":       {"landing_page": 0, "display_voucher_early": True,
                     "choose_users": {"shop_order_count": 0, "shop_order_count_period": 0}},
}


def _call(method, url, session, payload=None, extra_params=None, attempts=3):
    """requests + retry ringan. Sukses = code==0. Return dict json."""
    TO = (15, 60)
    headers = config.grab_headers(session)
    params = dict(session["params"])
    if extra_params:
        params.update(extra_params)
    delay, last = 2, ""
    for i in range(attempts):
        try:
            r = requests.request(method, url, headers=headers, params=params,
                                 json=payload, timeout=TO)
            data = r.json()
            if isinstance(data, dict) and data.get("code") == 0:
                return data
            last = (f"code={data.get('code')} {data.get('message') or data.get('msg') or ''}"
                    if isinstance(data, dict) else str(data)[:160])
        except Exception as e:
            last = f"{type(e).__name__}: {e}"
        if i < attempts - 1:
            time.sleep(delay); delay = min(delay * 2, 8)
    raise RuntimeError(f"[voucher] gagal {method} {url.split('/api/')[-1]}: {last}")


def _chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


# ── BAND HARGA: band pertama 1-14.999, sisanya per 20.000, band terakhir mentok di harga termahal ──
def bands_harga(max_price):
    """Return list (low, high) inklusif. Contoh max 50rb -> [(1,14999),(15000,34999),(35000,50000)]."""
    max_price = int(max_price)
    bands = [(1, 14999)]
    start = 15000
    while start <= max_price:
        bands.append((start, min(start + 19999, max_price)))
        start += 20000
    return bands


def bagi_produk_per_band(produk_harga):
    """produk_harga = {item_id: harga}. Return list of (low, high, [item_id,...]) sesuai band."""
    if not produk_harga:
        return []
    max_price = max(produk_harga.values())
    hasil = []
    for low, high in bands_harga(max_price):
        ids = [iid for iid, h in produk_harga.items() if low <= h <= high]
        hasil.append((low, high, ids))
    return hasil


# ── BACA ──
def list_vouchers(session):
    # ⚠️ ENDPOINT LIST BELUM TERVERIFIKASI: GET marketing/v3/voucher/list/ balik `201600001
    #    ERROR_PARAM` utk SEMUA kombinasi param yg dicoba (15+ varian live, 6 Jul). Params asli
    #    perlu di-CAPTURE DevTools: buka Seller Center > Voucher Saya > Network > cari request
    #    'voucher/list' -> copy URL query + method + body, ganti URL_LIST/param di sini.
    #    Sementara: gagal-anggun (return []) biar Fase 1 (tier mingguan) tak error-spam.
    try:
        data = _call("GET", URL_LIST, session).get("data") or {}
    except Exception as e:
        print(colorama.Fore.YELLOW + f"[voucher] list belum jalan (perlu capture endpoint): {type(e).__name__}"
              + colorama.Style.RESET_ALL)
        return []
    if isinstance(data, list):
        return data
    return data.get("voucher_list") or data.get("list") or []


def get_voucher(session, voucher_id):
    return _call("GET", URL_VOUCHER, session, extra_params={"voucher_id": voucher_id}).get("data") or {}


# ── BUAT ──
def _payload_voucher(name, code, start_time, end_time, discount=2, min_price=0,
                     max_value=None, usage_quantity=100000, limit_per_user=1,
                     item_ids=None, choose_users=None, landing_page=1,
                     display_voucher_early=False, display_from=None):
    rule = {
        "usage_limit_per_user": limit_per_user,
        "coin_cashback_voucher": {"coin_percentage_real": None, "max_coin": None},
        "voucher_landing_page": landing_page,
        "display_from": display_from, "exclusive_channel_type": None, "hide": 0,
        "reward_type": 0, "backend_created": 0,
        "display_voucher_early": display_voucher_early,
        "choose_users": choose_users or {"shop_order_count": 0, "shop_order_count_period": 0},
    }
    if item_ids:
        rule["items"] = [{"itemid": int(i)} for i in item_ids]
    return {
        "name": name, "start_time": int(start_time), "end_time": int(end_time),
        "voucher_code": code, "value": None, "max_value": max_value,
        "discount": discount, "min_price": int(min_price),
        "usage_quantity": usage_quantity, "rule": rule,
    }


def buat_voucher(session, name, code, start_time, end_time, **kw):
    """Buat voucher. Return voucher_id. kw: discount, min_price, max_value, usage_quantity,
    limit_per_user, item_ids(=voucher produk), choose_users, landing_page."""
    payload = _payload_voucher(name, code, start_time, end_time, **kw)
    if getattr(config, "DRY_RUN", False):
        print(colorama.Fore.YELLOW + f"[voucher] (DRY) buat '{name}' ({code}) diskon {payload['discount']}%" + colorama.Style.RESET_ALL)
        return None
    vid = _call("POST", URL_VOUCHER, session, payload).get("data", {}).get("voucher_id")
    print(colorama.Fore.CYAN + f"[voucher] '{name}' ({code}) dibuat -> id {vid}" + colorama.Style.RESET_ALL)
    return vid


# ── PERPANJANG (EDIT end_time) ──
def perpanjang_voucher(session, voucher_id, end_time_baru, voucher_detail=None):
    """Perpanjang voucher: PUT voucher/ dgn body voucher existing + end_time baru.
    voucher_detail = hasil get_voucher (biar field lain ikut apa adanya). Kalau None -> di-fetch."""
    detail = voucher_detail or get_voucher(session, voucher_id)
    body = dict(detail)
    body["voucher_id"] = voucher_id
    body["end_time"] = int(end_time_baru)
    if getattr(config, "DRY_RUN", False):
        print(colorama.Fore.YELLOW + f"[voucher] (DRY) perpanjang {voucher_id} -> end {end_time_baru}" + colorama.Style.RESET_ALL)
        return True
    _call("PUT", URL_VOUCHER, session, body)
    print(colorama.Fore.MAGENTA + f"[voucher] {voucher_id} diperpanjang -> end {end_time_baru}" + colorama.Style.RESET_ALL)
    return True


# ── VALIDATE item (voucher produk) ──
def validate_items(session, item_ids, chunk=50, **extra):
    valid = []
    for c in _chunks([int(i) for i in dict.fromkeys(item_ids)], chunk):
        payload = {"item_id_list": list(c), **extra}
        try:
            data = _call("POST", URL_VALIDATE, session, payload).get("data") or {}
            for it in (data.get("succ_main_items") or data.get("valid_items") or []):
                iid = it.get("item_id") if isinstance(it, dict) else it
                if iid:
                    valid.append(int(iid))
        except Exception as e:
            print(colorama.Fore.RED + f"[voucher] validate chunk gagal ({len(c)}): {type(e).__name__}" + colorama.Style.RESET_ALL)
    return valid


# ── AOV per toko (fact_pesanan) -> min_price voucher (aturan Shopee: <= 2x AOV) ──
def aov_toko(toko, window_hari=30):
    """Rata-rata Pembelian (omzet/pesanan) 1 toko dari fact_pesanan.
    toko = nama tampilan / username (dicocokkan ke dim_toko)."""
    from sqlalchemy import text
    from modules.db import get_engine
    sql = text("""
        select case when sum(fp.jumlah_pesanan) > 0
                    then sum(fp.omzet_pesanan)::float / sum(fp.jumlah_pesanan) else 0 end
        from fact_pesanan fp join dim_toko dt on dt.toko_id = fp.toko_id
        where fp.periode = 'harian'
          and fp.periode_mulai > now() - make_interval(days => :w)
          and (lower(dt.nama) = lower(:t) or lower(dt.username) = lower(:t))
    """)
    with get_engine().connect() as c:
        return float(c.execute(sql, {"t": toko, "w": window_hari}).scalar() or 0)


def min_price_toko(toko, faktor=2.0, buffer=0.97, window_hari=30):
    """min_price voucher = faktor x AOV x buffer. buffer<1 biar aman DI BAWAH batas
    Shopee (2x AOV) walau AOV kita beda tipis dari hitungan Shopee. Return int rupiah."""
    return int(aov_toko(toko, window_hari) * faktor * buffer)


# ── LOGIKA AUTO: perpanjang kalau <=1 hari sebelum mati, else bikin baru ──
def perlu_perpanjang(voucher, sekarang, ambang=SATU_HARI):
    """voucher dict punya end_time. True kalau sisa <= ambang (mau mati)."""
    end = int(voucher.get("end_time") or 0)
    return 0 < (end - sekarang) <= ambang
