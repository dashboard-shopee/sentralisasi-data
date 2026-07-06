"""modules/paket_diskon.py — AUTO-ENROLL semua produk ke PAKET DISKON (bundle deal).

Tujuan bisnis: UPSELL — beli lebih banyak, diskon lebih gede (beli 2 diskon 1%,
beli 3 diskon 2%, beli 7 diskon 3%). Idealnya SEMUA produk toko masuk 1 paket.

Endpoint terverifikasi via DevTools/sniff (3 Jul 2026):
  GET  marketing/v3/bundle_deal/               -> list paket
  POST marketing/v3/bundle_deal/               -> CREATE paket (tier rule) -> data.bundle_deal_id
  POST marketing/v3/bundle_deal/item/validate/ -> validasi item boleh masuk
       body {bundle_deal_id?, start_time, end_time, item_id_list:[...]} -> data.succ_main_items[]
  PUT  marketing/v3/bundle_deal/item/          -> ATTACH/HAPUS item (INI yg nyimpen!)
       body {bundle_deal_id, items:[{item_id, status}]}  status 1=masuk, 2=keluar/hapus
       (TERVERIFIKASI DevTools: hapus produk = kirim status 2, bukan 0)
  POST marketing/v3/bundle_deal/operation/     -> {bundle_deal_id, action:"stop"} hentikan paket

CATATAN PENTING:
  - bundle_deal TIDAK kena anti-bot Shopee (beda dgn komisi affiliate) -> cukup sesi
    login via `requests` biasa (pakai config.grab_headers(session) + session["params"]).
  - rule_type 2 = %DISKON (discount_percentage). start_time/end_time = unix detik.
  - DRY_RUN (config): kalau True, semua aksi ubah HANYA disimulasi (tidak dikirim).
"""
import time
import colorama; colorama.init()
import requests
import config

_BASE = "https://seller.shopee.co.id/api/marketing/v3/bundle_deal/"
URL_LIST = _BASE
URL_CREATE = _BASE
URL_VALIDATE = _BASE + "item/validate/"
URL_ITEM = _BASE + "item/"
URL_OP = _BASE + "operation/"

# Tier upsell DEFAULT: (min_amount, discount_percentage). Elemen [0] = tier dasar,
# sisanya jadi additional_tiers. (beli >=2 -> 1%, >=3 -> 2%, >=7 -> 3%)
TIER_DEFAULT = [(2, 1), (3, 2), (7, 3)]

STATUS_MASUK = 1
STATUS_KELUAR = 2      # TERVERIFIKASI: hapus produk dari paket = status 2 (bukan 0)


def _call(method, url, session, payload=None, attempts=3):
    """requests + retry ringan. Sukses = HTTP JSON dgn code==0. Return dict json."""
    TO = (15, 60)   # (connect, read) — anti-hang SSL Windows
    headers = config.grab_headers(session)
    params = session["params"]
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
    raise RuntimeError(f"[paket diskon] gagal {method} {url.split('/api/')[-1]}: {last}")


def _chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


# ── BACA ──
def list_deals(session):
    """List semua paket diskon toko (raw list dari data). Field umum tiap item:
    bundle_deal_id, name, status, start_time, end_time."""
    data = _call("GET", URL_LIST, session).get("data") or {}
    if isinstance(data, list):
        return data
    return data.get("bundle_deal_list") or data.get("list") or []


# ── CREATE ──
def buat_deal(session, name, start_time, end_time, tiers=TIER_DEFAULT, usage_limit=100000):
    """Buat paket diskon (aturan tier saja, belum ada produk). Return bundle_deal_id.
    tiers = list (min_amount, discount_percentage); [0]=dasar, sisanya additional_tiers."""
    m0, p0 = tiers[0]
    payload = {
        "min_amount": m0, "discount_percentage": p0, "discount_value": 0, "fix_price": 0,
        "name": name, "rule_type": 2, "usage_limit": usage_limit,
        "start_time": int(start_time), "end_time": int(end_time),
        "additional_tiers": [
            {"min_amount": m, "discount_percentage": p, "discount_value": 0, "fix_price": 0}
            for m, p in tiers[1:]
        ],
    }
    if getattr(config, "DRY_RUN", False):
        print(colorama.Fore.YELLOW + f"[paket diskon] (DRY) buat '{name}' tier={tiers}" + colorama.Style.RESET_ALL)
        return None
    bid = _call("POST", URL_CREATE, session, payload).get("data", {}).get("bundle_deal_id")
    print(colorama.Fore.CYAN + f"[paket diskon] paket '{name}' dibuat -> id {bid}" + colorama.Style.RESET_ALL)
    return bid


# ── VALIDATE ──
def validate_items(session, item_ids, start_time, end_time, bundle_deal_id=None, chunk=50):
    """Validasi item mana yang BOLEH masuk paket. Return list item_id yg lolos."""
    valid = []
    for c in _chunks([int(i) for i in dict.fromkeys(item_ids)], chunk):
        payload = {"start_time": int(start_time), "end_time": int(end_time), "item_id_list": list(c)}
        if bundle_deal_id:
            payload["bundle_deal_id"] = bundle_deal_id
        try:
            data = _call("POST", URL_VALIDATE, session, payload).get("data") or {}
            for it in (data.get("succ_main_items") or []):
                if it.get("err_code") in (None, 0) and it.get("item_id"):
                    valid.append(int(it["item_id"]))
        except Exception as e:
            print(colorama.Fore.RED + f"[paket diskon] validate chunk gagal ({len(c)}): {type(e).__name__}" + colorama.Style.RESET_ALL)
    return valid


# ── ATTACH (SAVE) ──
def attach_items(session, bundle_deal_id, item_ids, status=STATUS_MASUK, chunk=50):
    """Masukkan/keluarkan item ke/dari paket (PUT). status 1=masuk, 2=keluar/hapus.
    Return (jumlah_ok, jumlah_gagal). Per-chunk: 1 chunk gagal tak menggugurkan sisa."""
    ok = fail = 0
    label = "MASUK" if status == STATUS_MASUK else "KELUAR/HAPUS"
    ids = [int(i) for i in dict.fromkeys(item_ids)]
    for c in _chunks(ids, chunk):
        if getattr(config, "DRY_RUN", False):
            ok += len(c); continue
        payload = {"bundle_deal_id": bundle_deal_id,
                   "items": [{"item_id": i, "status": status} for i in c]}
        try:
            _call("PUT", URL_ITEM, session, payload)
            ok += len(c)
            print(colorama.Fore.MAGENTA + f"[paket diskon] {len(c)} item -> {label} paket {bundle_deal_id}" + colorama.Style.RESET_ALL)
        except Exception as e:
            fail += len(c)
            print(colorama.Fore.RED + f"[paket diskon] attach chunk gagal ({len(c)}): {type(e).__name__} - lanjut" + colorama.Style.RESET_ALL)
    return ok, fail


# ── STOP ──
def stop_deal(session, bundle_deal_id):
    if getattr(config, "DRY_RUN", False):
        print(colorama.Fore.YELLOW + f"[paket diskon] (DRY) stop {bundle_deal_id}" + colorama.Style.RESET_ALL); return
    _call("POST", URL_OP, session, {"bundle_deal_id": bundle_deal_id, "action": "stop"})
    print(colorama.Fore.CYAN + f"[paket diskon] paket {bundle_deal_id} DIHENTIKAN" + colorama.Style.RESET_ALL)


# ── ORKESTRATOR: masukin SEMUA produk ke 1 paket ──
def enroll_semua(session, item_ids, bundle_deal_id, start_time, end_time):
    """Validasi lalu attach SEMUA item_ids ke paket bundle_deal_id.
    Return ringkasan dict."""
    print(colorama.Fore.WHITE + f"[paket diskon] enroll {len(item_ids)} produk -> paket {bundle_deal_id}..." + colorama.Style.RESET_ALL)
    valid = validate_items(session, item_ids, start_time, end_time, bundle_deal_id)
    ok, fail = attach_items(session, bundle_deal_id, valid)
    hasil = {"total": len(set(item_ids)), "lolos_validasi": len(valid), "masuk": ok, "gagal": fail}
    print(colorama.Fore.GREEN + f"[paket diskon] SELESAI: {hasil}" + colorama.Style.RESET_ALL)
    return hasil


# ── Sumber item_id: SEMUA produk toko dari harga_olah_data (hasil grab Fase 1) ──
def item_ids_toko(nama_toko):
    """Distinct item_id 1 toko dari harga_olah_data (produk berstok hasil grab)."""
    from sqlalchemy import text
    from modules.db import get_engine
    with get_engine().connect() as c:
        rows = c.execute(text("select distinct item_id from harga_olah_data where toko=:t"),
                         {"t": nama_toko}).fetchall()
    return [int(r.item_id) for r in rows]
