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
import config
from modules.api_util import api_post
from modules.log_siklus import log

_B = "https://seller.shopee.co.id/api/mkt/bidding/"
URL_ONGOING = _B + "get_ongoing_list"
URL_WITHDRAW = _B + "seller_withdraw"
URL_SUBMIT = _B + "submit_bidding_online"
# ── Endpoint provisioning (sniff 11 Jul, halaman Nominasi Produk) ──
URL_MATCH = _B + "get_item_match_list"        # produk REKOMENDASI (belum-didaftar)
URL_ITEM_ONGOING = _B + "get_item_ongoing_list"  # dinominasi + bid_status per model
URL_STATS = _B + "get_ongoing_statistics"     # count per tab

FAKTOR = 100000   # harga bidding = rupiah × 100000
# bid_status (get_item_ongoing_list): 30 = Terbaik (winning, muncul ke customer),
#                                     40 = Perlu Ditinjau Ulang (belum kompetitif / stok rendah).
BID_STATUS_TERBAIK = 30
BID_STATUS_PERLU_TINJAU = 40


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
            log(f"get_ongoing_list hal {page} gagal: {type(e).__name__}", level="error", modul="garansi")
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
                # 3 harga (semua rupiah × FAKTOR):
                "current_price": int(pi.get("current_price") or 0) // FAKTOR,   # Harga Kini (tampil Shopee)
                "bid_price": int(bi.get("bid_price") or 0) // FAKTOR,            # Harga Program (garansi yg diset)
                # Harga Terbaik (rekomendasi terendah). Field pasti belum dikonfirmasi ke UI ->
                # pakai suggest_final_price (cspu) dulu, fallback default_bid_price/prefill_floor_price.
                "best_price": int(ci.get("suggest_final_price")
                                  or bi.get("default_bid_price")
                                  or bi.get("prefill_floor_price") or 0) // FAKTOR,
                "stok": int(pi.get("normal_stock") or 0),
            }
        if len(lst) < page_size:
            break
        page += 1
    log(f"{len(hasil)} variasi lagi ikut Garansi (ongoing)", level="detail", modul="garansi")
    return hasil


# ── REKOMENDASI (belum-didaftar) — get_item_match_list ──
def list_rekomendasi(session, page_size=100, maks_halaman=50):
    """Produk REKOMENDASI garansi (belum-didaftar) → list {item_id, item_name, floor, ceiling, stok,
    models:[{model_id, model_name, cspu_id}]}. floor=best/Harga Terbaik, ceiling=Harga Program (rupiah).
    floor & ceiling per-ITEM (item_floor_price/item_ceiling_price)."""
    H = config.grab_headers(session); P = session["params"]
    hasil = {}; page = 1   # dedup by item_id
    while page <= maks_halaman:
        try:
            r = api_post(URL_MATCH, H, P,
                {"filter": {}, "page_info": {"page_num": page, "page_size": page_size},
                 "option": {"with_performance": True}}, kunci="data")
        except Exception as e:
            log(f"get_item_match_list hal {page} gagal: {type(e).__name__}", level="error", modul="garansi")
            break
        lst = (r.get("data") or {}).get("list") or []
        before = len(hasil)
        for it in lst:
            floor = int((it.get("item_floor_price") or {}).get("lower_value") or 0) // FAKTOR
            ceil = int((it.get("item_ceiling_price") or {}).get("lower_value") or 0) // FAKTOR
            models = []
            for m in (it.get("model_list") or []):
                pi = m.get("product_info") or {}; ci = m.get("cspu_info") or {}
                if ci.get("cspu_id"):
                    models.append({"model_id": str(pi.get("model_id", "")),
                                   "model_name": pi.get("model_name", ""),
                                   "cspu_id": str(ci.get("cspu_id", ""))})
            hasil[int(it.get("item_id") or 0)] = {
                "item_id": int(it.get("item_id") or 0), "item_name": it.get("item_name", ""),
                "floor": floor, "ceiling": ceil,
                "stok": int(it.get("item_current_stock") or 0), "models": models}
        if not lst or len(hasil) == before:   # halaman kosong ATAU ga ada yg baru -> stop
            break
        page += 1
    log(f"{len(hasil)} produk rekomendasi (belum-didaftar)", level="detail", modul="garansi")
    return list(hasil.values())


# ── DINOMINASI + bid_status — get_item_ongoing_list (semua page_tab, dedup bid_id) ──
def list_ongoing_status(session, page_size=100, maks_halaman=50):
    """Produk DINOMINASI per MODEL → list {item_id, item_name, model_id, model_name, bid_id,
    bid_status, stok, floor, ceiling, cspu_id}. floor=best/Harga Terbaik, ceiling=Harga Program
    (rupiah, per-ITEM). bid_status 30=Terbaik / 40=Perlu-Ditinjau. Iterasi page_tab 1-3 + dedup bid_id."""
    H = config.grab_headers(session); P = session["params"]
    hasil = {}
    for page_tab in (1, 2, 3):
        page = 1
        while page <= maks_halaman:
            try:
                r = api_post(URL_ITEM_ONGOING, H, P,
                    {"filter": {"page_tab": page_tab}, "page_info": {"page_num": page, "page_size": page_size},
                     "option": {"with_performance": True}}, kunci="data")
            except Exception:
                break
            lst = (r.get("data") or {}).get("list") or []
            before = len(hasil)
            for it in lst:
                iid = int(it.get("item_id") or 0); stok = int(it.get("item_current_stock") or 0)
                iname = it.get("item_name", "")
                for m in (it.get("model_list") or []):
                    bi = m.get("bidding_info") or {}; pi = m.get("product_info") or {}; ci = m.get("cspu_info") or {}
                    bid_id = str(bi.get("bid_id", ""))
                    if not bid_id:
                        continue
                    # floor/ceiling PER-MODEL dari bidding_info (verified 12 Jul, produk CREAM Alialia):
                    #   floor_price = "Harga Terbaik Saya" · ceiling_price = "Harga Program Saya".
                    #   (item_floor/ceiling_price = rentang IZIN per-item, BUKAN nilai nominasi → dulu salah)
                    floor = int(bi.get("floor_price") or 0) // FAKTOR
                    ceil = int(bi.get("ceiling_price") or 0) // FAKTOR
                    hasil[bid_id] = {"item_id": iid, "item_name": iname,
                                     "model_id": str(pi.get("model_id", "")), "model_name": pi.get("model_name", ""),
                                     "bid_id": bid_id, "bid_status": bi.get("bid_status"), "stok": stok,
                                     "floor": floor, "ceiling": ceil, "cspu_id": str(ci.get("cspu_id", ""))}
            if not lst or len(hasil) == before:   # halaman kosong ATAU ga ada yg baru -> stop tab ini
                break
            page += 1
    log(f"{len(hasil)} model dinominasi (ongoing)", level="detail", modul="garansi")
    return list(hasil.values())


def entri_enroll(item_id, item_name, model_id, model_name, cspu_id, floor_rp, ceiling_rp, bid_stock=0, bid_rp=None):
    """Bangun 1 entri cspu_product utk submit_bidding_online. floor/ceiling = rentang IZIN.
    bid_price (harga yg di-commit) = `bid_rp` kalau diisi, else DEFAULT ceiling (Harga Program).
    Dipakai owner 13 Jul: rekomendasi/enroll baru → bid @ Program (default); re-submit dari
    'perlu ditinjau' → bid @ Harga Terbaik (bid_rp=floor) biar kompetitif. Harga ×FAKTOR (string)."""
    bid = int(bid_rp) if bid_rp else int(ceiling_rp)
    return {
        "cspu_id": str(cspu_id), "item_id": str(item_id), "item_name": item_name,
        "model_id": str(model_id), "model_name": model_name,
        "bid_price": str(bid * FAKTOR), "floor_price": str(int(floor_rp) * FAKTOR),
        "ceiling_price": str(int(ceiling_rp) * FAKTOR), "bid_stock": str(bid_stock),
        "bid_source": 0, "accept_rebate": 1,
    }


# ── OPT-OUT: withdraw pakai bid_id ──
def withdraw(session, bid_ids):
    """Keluarkan (opt-out) dari Garansi. bid_ids = list bid_id. Return (ok, gagal)."""
    H = config.grab_headers(session); P = session["params"]
    ids = [str(b) for b in bid_ids if b]
    if getattr(config, "DRY_RUN", False):
        log(f"(DRY) withdraw {len(ids)} bid", level="warning", modul="garansi")
        return len(ids), 0
    ok = gagal = 0
    for b in ids:
        try:
            api_post(URL_WITHDRAW, H, P, {"bid_id": b}, kunci="data", attempts=2)
            ok += 1
        except Exception as e:
            gagal += 1
            log(f"withdraw {b} gagal: {type(e).__name__}", level="error", modul="garansi")
    log(f"opt-out: {ok} berhasil, {gagal} gagal", level="live", modul="garansi")
    return ok, gagal


# ── OPT-OUT by (item_id, model_id): cari bid_id dari ongoing lalu withdraw ──
def withdraw_produk(session, kunci_set, ongoing=None):
    """kunci_set = set (item_id, model_id). Return jumlah ter-opt-out."""
    if not kunci_set:
        return 0
    ong = ongoing if ongoing is not None else list_ongoing(session)
    bids = [ong[k]["bid_id"] for k in kunci_set if k in ong and ong[k].get("bid_id")]
    if not bids:
        log("tidak ada variasi target yang lagi ikut Garansi", level="detail", modul="garansi")
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
        log(f"(DRY) enroll {len(cspu_product)} produk", level="warning", modul="garansi")
        return len(cspu_product), 0
    ok = gagal = 0
    for c in _chunks(cspu_product, chunk):
        try:
            api_post(URL_SUBMIT, H, P, {"cspu_product": list(c), "tracker_source": tracker_source}, kunci="data")
            ok += len(c)
        except Exception as e:
            gagal += len(c)
            log(f"enroll chunk gagal ({len(c)}): {type(e).__name__}", level="error", modul="garansi")
    log(f"daftar: {ok} berhasil, {gagal} gagal", level="live", modul="garansi")
    return ok, gagal
