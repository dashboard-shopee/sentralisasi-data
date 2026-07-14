"""modules/voucher.py — AUTO daftar VOUCHER toko (upsell, TIDAK ubah harga).
Jelang-expire = BUAT BARU (keputusan owner 13 Jul, konsisten paket; fungsi perpanjang dihapus).

Endpoint terverifikasi via DevTools (3 Jul 2026):
  POST marketing/v3/voucher/               -> BUAT voucher -> data.voucher_id
  PUT  marketing/v3/voucher/               -> EDIT (body + voucher_id; dipakai edit rule.items)
  GET  marketing/v3/voucher/?voucher_id=X  -> detail 1 voucher
  GET  marketing/v3/voucher/list/          -> list voucher
  POST marketing/v3/voucher/validate_items/-> validasi item (voucher produk)

Semua via requests biasa (voucher TIDAK kena anti-bot). discount = persen (2 = 2%).
max_value = batas maksimal diskon Rp (null = "Tidak Terbatas"). min_price = min belanja,
Shopee batasi <= 2x AOV toko. rule.items = [{itemid}] utk voucher PRODUK (kosong = semua produk).

⚠️ ATURAN KODE (verified live 13 Jul): voucher_code WAJIB diawali PREFIX KODE TOKO
(4 char, mis. "KIMM") + maks 5 char custom (total 9). Tanpa prefix -> 201600001 ERROR_PARAM
(dan invalid_data cuma nampilin streamer_ids null — red herring, bukan field-nya).

TIPE (dibedakan param):
  - toko        : ✅ VERIFIED LIVE create 13 Jul (KIMMUP194 kimmioshop). Voucher toko
                  reguler (usecase 1), SHOP-WIDE (rule.items kosong = semua produk),
                  tanpa targeting user. Dipakai provisioning UPSELL.
  - ikuti toko / pembeli baru: keluarga WELCOME voucher (usecase 3) — Shopee batasi
                  1 AKTIF per toko (1400101033 "create a new shop welcome voucher
                  after the existing one is expired"). JANGAN dipakai buat upsell.
  - produk      : rule.items terisi; dibagi 3+ BAND harga (per 20rb) via bands_harga()
"""
import time
import requests
import config
from modules.log_siklus import log

_BASE = "https://seller.shopee.co.id/api/marketing/v3/voucher/"
URL_VOUCHER = _BASE
URL_LIST = _BASE + "list/"
URL_VALIDATE = _BASE + "validate_items/"

# Preset param per TIPE voucher (`usecase` di respon GET: 1=toko reguler, 2=produk, 3=welcome;
# usecase TIDAK dikirim di body create — server nentuin sendiri dari kombinasi param).
TIPE = {
    # ✅ Voucher TOKO reguler — SHOP-WIDE (items kosong = semua produk), tanpa targeting.
    #    VERIFIED LIVE create 13 Jul (tiru skema voucher KIMMBLJ35 existing).
    "toko":         {"landing_page": 1, "display_voucher_early": False,
                     "choose_users": {"shop_order_count": 0, "shop_order_count_period": 0}},
    # ⚠️ WELCOME family (shop_order_count:1) — maks 1 AKTIF per toko (1400101033).
    "ikuti_toko":   {"landing_page": 1, "display_voucher_early": False,
                     "choose_users": {"shop_order_count": 1, "shop_order_count_period": 0}},
    "pembeli_baru": {"landing_page": 0, "display_voucher_early": True,
                     "choose_users": {"shop_order_count": 1, "shop_order_count_period": 0}},
    # Voucher Produk — pakai item_ids (per band harga), tanpa targeting user.
    # Param disamain sama skema voucher produk ASLI di toko (KIMMV1, usecase 2).
    "produk":       {"landing_page": 1, "display_voucher_early": True,
                     "choose_users": {"shop_order_count": 0, "shop_order_count_period": 0}},
}


def prefix_kode_toko(vouchers, username):
    """PREFIX kode voucher toko (4 char, aturan Shopee: kode wajib diawali prefix ini).
    Diambil dari voucher existing (paling sering, skip kode sistem 'SFP-');
    fallback: 4 alnum pertama username (kimmioshop -> KIMM)."""
    import re as _re
    from collections import Counter
    c = Counter(str(v.get("voucher_code") or "")[:4].upper() for v in (vouchers or [])
                if v.get("voucher_code") and not str(v.get("voucher_code")).upper().startswith("SFP"))
    if c:
        return c.most_common(1)[0][0]
    return (_re.sub(r"[^A-Za-z0-9]", "", str(username)).upper() + "XXXX")[:4]


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


# ── BAND HARGA: GRID FIX — band pertama 1..BAND1_MAKS, sisanya per BAND_LEBAR. Batas band
#    SENGAJA ga mentok harga termahal: min belanja voucher BERJALAN ga bisa diedit (Shopee
#    ERROR_VOUCHER_NO_EDIT_PERMISSION, verif 13 Jul) — grid fix bikin min ga pernah geser
#    walau harga termahal berubah. Intent tetap: min belanja > harga tiap produk di band. ──
def bands_harga(max_price):
    """Return list (low, high) inklusif s/d band yg memuat max_price. Contoh (band1=14999,
    lebar=20000) max 50rb -> [(1,14999),(15000,34999),(35000,54999)]. Min belanja = high+1."""
    max_price = int(max_price)
    b1 = int(config.KPI_VOUCHER_BAND1_MAKS)
    lebar = int(config.KPI_VOUCHER_BAND_LEBAR)
    bands = [(1, b1)]
    start = b1 + 1
    while start <= max_price:
        bands.append((start, start + lebar - 1))
        start += lebar
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
def list_vouchers(session, promotion_type=0, page_size=50):
    """List voucher toko. Endpoint VERIFIED via sniff (6 Jul): GET marketing/v3/voucher/list/
    params {offset, limit, promotion_type}. promotion_type 0=SEMUA (1=akan datang, 2=berlangsung).
    Paginate offset s/d total_count. Return list voucher (data.voucher_list). Gagal-anggun -> []."""
    hasil = []
    offset = 0
    while True:
        try:
            data = _call("GET", URL_LIST, session,
                         extra_params={"offset": offset, "limit": page_size,
                                       "promotion_type": promotion_type}).get("data") or {}
        except Exception as e:
            log(f"list gagal: {type(e).__name__}", level="warning", modul="voucher")
            break
        lst = (data.get("voucher_list") or data.get("list") or []) if isinstance(data, dict) else (data or [])
        hasil.extend(x for x in lst if isinstance(x, dict))
        total = int(data.get("total_count") or 0) if isinstance(data, dict) else 0
        offset += page_size
        if len(lst) < page_size or (total and offset >= total) or offset > 5000:
            break
    return hasil


def get_voucher(session, voucher_id):
    return _call("GET", URL_VOUCHER, session, extra_params={"voucher_id": voucher_id}).get("data") or {}


# ── BUAT ──
# ⚠️ value & max_value WAJIB angka 0 (kaya voucher buatan UI, "0.00") — verified live 13 Jul
#    (ZTES A/B fe_status 2 = Berlangsung). Jangan kirim None.
def _payload_voucher(name, code, start_time, end_time, discount=config.KPI_VOUCHER_DISKON_PCT,
                     min_price=0, max_value=0, usage_quantity=config.KPI_VOUCHER_USAGE_QTY,
                     limit_per_user=1, item_ids=None, choose_users=None, landing_page=1,
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
        "voucher_code": code, "value": 0, "max_value": int(max_value or 0),
        "discount": discount, "min_price": int(min_price),
        "usage_quantity": usage_quantity, "rule": rule,
    }


def buat_voucher(session, name, code, start_time, end_time, **kw):
    """Buat voucher. Return voucher_id. kw: discount, min_price, max_value, usage_quantity,
    limit_per_user, item_ids(=voucher produk), choose_users, landing_page."""
    payload = _payload_voucher(name, code, start_time, end_time, **kw)
    if getattr(config, "DRY_RUN", False):
        log(f"(DRY) buat '{name}' ({code}) diskon {payload['discount']}%", level="warning", modul="voucher")
        return None
    vid = _call("POST", URL_VOUCHER, session, payload).get("data", {}).get("voucher_id")
    log(f"'{name}' ({code}) dibuat → id {vid}", level="live", modul="voucher")
    return vid


# ── BODY buat PUT voucher/ — WAJIB bentuk payload CREATE yang bersih + voucher_id.
#    (kirim respon GET apa adanya = ERROR_PARAM: field server kaya signature/fe_status ditolak.
#    Verif live 13 Jul: edit rule.items voucher BERJALAN -> BOLEH (propagasi ~10 dtk);
#    edit min_price / mempersingkat end_time voucher berjalan -> DITOLAK
#    ERROR_VOUCHER_NO_EDIT_PERMISSION / ERROR_PARAM.) ──
def _body_edit(detail, items_override=None, **override):
    """Susun body PUT dari detail GET: bentuk create-bersih, nilai apa adanya, bisa dioverride."""
    r = detail.get("rule") or {}
    items = items_override
    if items is None:
        items = [int(x.get("itemid")) for x in (r.get("items") or [])
                 if isinstance(x, dict) and x.get("itemid")]
    rule = {
        "usage_limit_per_user": r.get("usage_limit_per_user", 1),
        "coin_cashback_voucher": {"coin_percentage_real": None, "max_coin": None},
        "voucher_landing_page": r.get("voucher_landing_page", 1),
        "display_from": r.get("display_from"),
        "exclusive_channel_type": None, "hide": 0, "reward_type": 0, "backend_created": 0,
        "display_voucher_early": r.get("display_voucher_early", False),
        "choose_users": r.get("choose_users") or {"shop_order_count": 0, "shop_order_count_period": 0},
    }
    if items:
        rule["items"] = [{"itemid": int(i)} for i in sorted(items)]
    body = {
        "voucher_id": detail.get("voucher_id"), "name": detail.get("name"),
        "start_time": int(detail.get("start_time") or 0), "end_time": int(detail.get("end_time") or 0),
        "voucher_code": detail.get("voucher_code"),
        "value": int(float(detail.get("value") or 0)), "max_value": int(float(detail.get("max_value") or 0)),
        "discount": detail.get("discount"), "min_price": int(float(detail.get("min_price") or 0)),
        "usage_quantity": detail.get("usage_quantity"), "rule": rule,
    }
    body.update(override)
    return body


# ── AKHIRI voucher (end_time = sekarang) ──
def akhiri_voucher(session, voucher_id, detail=None):
    """Coba akhiri voucher: PUT end_time = sebentar lagi. ⚠️ Verif 13 Jul: voucher BERJALAN
    GA BISA diakhiri via API (ERROR_PARAM) — cuma yg BELUM mulai yg mungkin bisa.
    Gagal-anggun -> return False + warning (akhiri MANUAL di Seller Center)."""
    if getattr(config, "DRY_RUN", False):
        log(f"(DRY) akhiri {voucher_id}", level="warning", modul="voucher")
        return True
    try:
        detail = detail or get_voucher(session, voucher_id)
        _call("PUT", URL_VOUCHER, session, _body_edit(detail, end_time=int(time.time()) + 60), attempts=1)
    except Exception:
        log(f"⚠️ '{detail.get('name')}' (kode {detail.get('voucher_code')}) ga bisa diakhiri via API → AKHIRI MANUAL di Seller Center", level="warning", modul="voucher")
        return False
    log(f"{voucher_id} diakhiri (end_time=sekarang)", level="live", modul="voucher")
    return True


# ── FASE 2 kasus 4 + reconcile band: edit daftar item voucher PRODUK ──
#    ✅ VERIFIED LIVE 13 Jul: rule.items voucher BERJALAN boleh diedit (tambah & keluar);
#    perubahan kebaca di GET setelah ~10 detik (jangan verif kecepetan).
def _set_item_voucher(session, voucher_id, item_ids, tambah, detail=None):
    """Ubah rule.items voucher: tambah=True -> tambahin item, False -> keluarin. Return bool."""
    ids = {int(i) for i in item_ids if i}
    if not ids:
        return False
    detail = detail or get_voucher(session, voucher_id)
    sekarang = {int(x.get("itemid")) for x in ((detail.get("rule") or {}).get("items") or [])
                if isinstance(x, dict) and x.get("itemid")}
    baru = (sekarang | ids) if tambah else (sekarang - ids)
    aksi = "tambah" if tambah else "keluarkan"
    if not baru:
        # items kosong bisa ngerubah makna voucher (kosong = semua produk) -> jangan!
        log(f"⚠️ {aksi} batal: voucher {voucher_id} bakal 0 item (kosong = semua produk). Akhiri manual kalau emang mau dimatiin.", level="warning", modul="voucher")
        return False
    if getattr(config, "DRY_RUN", False):
        log(f"(DRY) {aksi} {len(ids)} item @ voucher {voucher_id} ({len(sekarang)}→{len(baru)})", level="warning", modul="voucher")
        return True
    _call("PUT", URL_VOUCHER, session, _body_edit(detail, items_override=sorted(baru)))
    log(f"{aksi} {len(ids)} item @ voucher {voucher_id} ({len(sekarang)}→{len(baru)})", level="live", modul="voucher")
    return True


def keluarkan_item(session, voucher_id, item_ids, detail=None):
    """Keluarin item dari 1 voucher produk (rule.items minus item)."""
    return _set_item_voucher(session, voucher_id, item_ids, tambah=False, detail=detail)


def masukkan_item(session, voucher_id, item_ids, detail=None):
    """Masukin lagi item ke 1 voucher produk (rule.items plus item)."""
    return _set_item_voucher(session, voucher_id, item_ids, tambah=True, detail=detail)


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
            log(f"validate chunk gagal ({len(c)}): {type(e).__name__}", level="error", modul="voucher")
    return valid


# ── AOV per toko (fact_pesanan) -> min_price voucher (aturan Shopee: <= 2x AOV) ──
def aov_toko(toko, window_hari=config.KPI_VOUCHER_AOV_WINDOW_HARI):
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


def min_price_toko(toko, faktor=config.KPI_VOUCHER_MINPRICE_FAKTOR,
                   buffer=config.KPI_VOUCHER_MINPRICE_BUFFER,
                   window_hari=config.KPI_VOUCHER_AOV_WINDOW_HARI):
    """min_price voucher = faktor x AOV x buffer. buffer<1 biar aman DI BAWAH batas
    Shopee (2x AOV) walau AOV kita beda tipis dari hitungan Shopee. Return int rupiah."""
    return int(aov_toko(toko, window_hari) * faktor * buffer)


