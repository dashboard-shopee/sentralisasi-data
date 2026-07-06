"""modules/garansi.py — GARANSI HARGA TERBAIK = program REALTIME BIDDING Shopee (mkt/bidding/*).

✅ TERBUKTI API-able via `requests` (TIDAK kena anti-bot, capture DevTools 3 Jul). Semua `mkt/bidding/*`:
  LIST ongoing (produk yg lagi ikut Garansi + bid_id):
    POST get_ongoing_list {pagination:{page_num,page_size}, filter:{req_source:1}, sorting:{field:3,is_asc:true}}
      -> data.list[{product_info:{item_id,model_id,current_price,...}, bidding_info:{bid_id,bid_price,...}, cspu_info:{cspu_id,...}}]
  OPT-OUT (withdraw 1 produk dari Garansi):
    POST seller_withdraw {bid_id}
  DAFTAR (enroll produk ke Garansi):
    POST submit_bidding_online {cspu_product:[{cspu_id,item_id,model_id,bid_price,floor_price,ceiling_price,
      bid_stock,bid_source,accept_rebate}], tracker_source:8}   (harga = rupiah × 100000)

Dipakai HARGA bot: opt-out Garansi (yg auto-nurunin harga) sebelum kontrol harga -> §9 #4.
Hormatin config.DRY_RUN.
"""
import time
import colorama; colorama.init()
import config
from modules.api_util import api_post

_B = "https://seller.shopee.co.id/api/mkt/bidding/"
URL_ONGOING = _B + "get_ongoing_list"
URL_WITHDRAW = _B + "seller_withdraw"
URL_SUBMIT = _B + "submit_bidding_online"

FAKTOR = 100000   # harga bidding = rupiah × 100000


def _chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


# ── LIST: produk yang lagi ikut Garansi (ongoing) + bid_id ──
def list_ongoing(session, page_size=100, maks_halaman=50):
    """Return {(item_id, model_id): {bid_id, cspu_id, current_price, bid_price, stok}}."""
    H = config.grab_headers(session); P = session["params"]
    hasil = {}; page = 1
    while page <= maks_halaman:
        try:
            r = api_post(URL_ONGOING, H, P,
                {"pagination": {"page_num": page, "page_size": page_size},
                 "filter": {"req_source": 1}, "sorting": {"field": 3, "is_asc": True}}, kunci="data")
        except Exception as e:
            print(colorama.Fore.RED + f"[garansi] get_ongoing_list hal {page} gagal: {type(e).__name__}" + colorama.Style.RESET_ALL)
            break
        lst = (r.get("data") or {}).get("list") or []
        for it in lst:
            pi = it.get("product_info") or {}; bi = it.get("bidding_info") or {}; ci = it.get("cspu_info") or {}
            try:
                key = (int(pi.get("item_id")), int(pi.get("model_id")))
            except (TypeError, ValueError):
                continue
            hasil[key] = {
                "bid_id": str(bi.get("bid_id", "")),
                "cspu_id": str(ci.get("cspu_id", "")),
                "current_price": int(pi.get("current_price") or 0) // FAKTOR,
                "bid_price": int(bi.get("bid_price") or 0) // FAKTOR,
                "stok": int(pi.get("normal_stock") or 0),
            }
        if len(lst) < page_size:
            break
        page += 1
    print(colorama.Fore.WHITE + f"[garansi] {len(hasil)} variasi lagi ikut Garansi (ongoing)" + colorama.Style.RESET_ALL)
    return hasil


# ── OPT-OUT: withdraw pakai bid_id ──
def withdraw(session, bid_ids):
    """Keluarkan (opt-out) dari Garansi. bid_ids = list bid_id. Return (ok, gagal)."""
    H = config.grab_headers(session); P = session["params"]
    ids = [str(b) for b in bid_ids if b]
    if getattr(config, "DRY_RUN", False):
        print(colorama.Fore.YELLOW + f"[garansi] (DRY) withdraw {len(ids)} bid" + colorama.Style.RESET_ALL)
        return len(ids), 0
    ok = gagal = 0
    for b in ids:
        try:
            api_post(URL_WITHDRAW, H, P, {"bid_id": b}, kunci="data", attempts=2)
            ok += 1
        except Exception as e:
            gagal += 1
            print(colorama.Fore.RED + f"[garansi] withdraw {b} gagal: {type(e).__name__}" + colorama.Style.RESET_ALL)
    print(colorama.Fore.MAGENTA + f"[garansi] opt-out: {ok} berhasil, {gagal} gagal" + colorama.Style.RESET_ALL)
    return ok, gagal


# ── OPT-OUT by (item_id, model_id): cari bid_id dari ongoing lalu withdraw ──
def withdraw_produk(session, kunci_set, ongoing=None):
    """kunci_set = set (item_id, model_id). Return jumlah ter-opt-out."""
    if not kunci_set:
        return 0
    ong = ongoing if ongoing is not None else list_ongoing(session)
    bids = [ong[k]["bid_id"] for k in kunci_set if k in ong and ong[k].get("bid_id")]
    if not bids:
        print(colorama.Fore.WHITE + "[garansi] tidak ada variasi target yang lagi ikut Garansi" + colorama.Style.RESET_ALL)
        return 0
    ok, _ = withdraw(session, bids)
    return ok


# ── DAFTAR (enroll) produk ke Garansi ──
def enroll(session, cspu_product, tracker_source=8, chunk=50):
    """cspu_product = list dict {cspu_id, item_id, model_id, bid_price, floor_price, ceiling_price,
    bid_stock, bid_source, accept_rebate} (harga sudah ×FAKTOR/string). Return (ok, gagal)."""
    if not cspu_product:
        return 0, 0
    H = config.grab_headers(session); P = session["params"]
    if getattr(config, "DRY_RUN", False):
        print(colorama.Fore.YELLOW + f"[garansi] (DRY) enroll {len(cspu_product)} produk" + colorama.Style.RESET_ALL)
        return len(cspu_product), 0
    ok = gagal = 0
    for c in _chunks(cspu_product, chunk):
        try:
            api_post(URL_SUBMIT, H, P, {"cspu_product": list(c), "tracker_source": tracker_source}, kunci="data")
            ok += len(c)
        except Exception as e:
            gagal += len(c)
            print(colorama.Fore.RED + f"[garansi] enroll chunk gagal ({len(c)}): {type(e).__name__}" + colorama.Style.RESET_ALL)
    print(colorama.Fore.MAGENTA + f"[garansi] daftar: {ok} berhasil, {gagal} gagal" + colorama.Style.RESET_ALL)
    return ok, gagal
