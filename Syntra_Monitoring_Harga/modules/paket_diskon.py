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
import requests
import config
from modules.log_siklus import log

_BASE = "https://seller.shopee.co.id/api/marketing/v3/bundle_deal/"
URL_LIST = _BASE + "list/"    # LIST pakai /list/ (base '/' = detail, minta bundle_deal_id) — verified live
URL_CREATE = _BASE
URL_VALIDATE = _BASE + "item/validate/"
URL_ITEM = _BASE + "item/"
URL_OP = _BASE + "operation/"

# Tier upsell DEFAULT: (min_amount, discount_percentage). Elemen [0] = tier dasar,
# sisanya jadi additional_tiers. KPI dari config (jangan hardcode).
TIER_DEFAULT = config.KPI_PAKET_TIER

STATUS_MASUK = 1
STATUS_KELUAR = 2      # TERVERIFIKASI: hapus produk dari paket = status 2 (bukan 0)


def _call(method, url, session, payload=None, attempts=3, extra_params=None):
    """requests + retry ringan. Sukses = HTTP JSON dgn code==0. Return dict json.
    extra_params: query-param tambahan (mis. offset/limit/time_status utk list)."""
    TO = (15, 60)   # (connect, read) — anti-hang SSL Windows
    headers = config.grab_headers(session)
    params = {**session["params"], **(extra_params or {})}
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
# time_status: 0=semua, 1=mendatang, 2=berjalan, 3=berakhir (verified sniff 11 Jul).
def _list_status(session, time_status, limit=10):
    """1 time_status, paginate sampai habis. Return list deal mentah."""
    hasil, offset = [], 0
    while True:
        data = _call("GET", URL_LIST, session,
                     extra_params={"offset": offset, "limit": limit, "time_status": time_status}).get("data") or {}
        if isinstance(data, list):
            lst = data
        else:
            lst = data.get("bundle_deal_list") or data.get("list") or []
        hasil.extend(lst)
        if len(lst) < limit or offset > 990:
            break
        offset += limit
    return hasil


def _buang_berakhir(deals):
    """Buang deal yg udah BERAKHIR (end_time < sekarang). Shopee KADANG tetap balikin deal ended
    walau filter time_status 2/1 — jadi saring tegas pakai end_time. end_time=0/kosong -> disimpen."""
    now = int(time.time())
    out = []
    for d in deals:
        if not isinstance(d, dict):
            continue
        et = int(d.get("end_time") or 0)
        if et == 0 or et > now:          # berjalan/akan datang (atau ga ada info) -> keep
            out.append(d)
    return out


def list_deals(session, time_status=None):
    """List paket diskon toko. Default: BERJALAN(2)+AKAN DATANG(1) — yg BERAKHIR dibuang (via end_time).
    Kirim time_status eksplisit (0=semua/1/2/3) kalau mau spesifik.
    NOTE: endpoint WAJIB param offset/limit/time_status — tanpa itu balik KOSONG (verified 11 Jul)."""
    if time_status is not None:
        return _buang_berakhir(_list_status(session, time_status))
    gabung = {}
    for ts in (2, 1):
        for d in _buang_berakhir(_list_status(session, ts)):
            bid = (d.get("bundle_deal_id") or d.get("id")) if isinstance(d, dict) else None
            if bid:
                gabung.setdefault(bid, d)
    return list(gabung.values())


def baca_item_deal(session, bundle_deal_id, limit=100):
    """Item_id yang ADA di dalam 1 paket (keanggotaan produk). Paginate.
    Endpoint verified 11 Jul: GET bundle_deal/item/ {bundle_deal_id,offset,limit}
    -> data.items[{itemid,status}] + total_count. Return list int item_id (status masuk)."""
    ids, offset = [], 0
    while True:
        data = _call("GET", URL_ITEM, session,
                     extra_params={"bundle_deal_id": bundle_deal_id, "offset": offset, "limit": limit}).get("data") or {}
        items = (data.get("items") if isinstance(data, dict) else None) or []
        for it in items:
            iid = it.get("itemid") or it.get("item_id")
            # status 2 = keluar/hapus -> skip; sisanya dianggap masuk
            if iid and it.get("status") != STATUS_KELUAR:
                ids.append(int(iid))
        total = data.get("total_count") if isinstance(data, dict) else None
        offset += limit
        if len(items) < limit or (total is not None and offset >= total) or offset > 5000:
            break
    return ids


def item_ids_terdaftar(session, deals):
    """Gabungan item_id yang UDAH masuk paket manapun (dari list deals). Return set int.
    Buat Fase 2: produk 'belum masuk paket' = semua produk toko − set ini."""
    out = set()
    for d in deals:
        bid = (d.get("bundle_deal_id") or d.get("id")) if isinstance(d, dict) else None
        if bid:
            out.update(baca_item_deal(session, bid))
    return out


def baca_kapasitas(session):
    """Info kapasitas paket AKTIF dari Shopee (1 call). Buat logika Fase 2 'usahain 1 paket,
    kalau kelebihan buat ke-2'. Return {total_count, max_active_count, is_exceed}."""
    data = _call("GET", URL_LIST, session,
                 extra_params={"offset": 0, "limit": 10, "time_status": 2}).get("data") or {}
    if not isinstance(data, dict):
        data = {}
    return {
        "total_count": data.get("total_count"),
        "max_active_count": data.get("max_active_count"),
        "is_exceed": data.get("is_exceed_max_active_count"),
    }


# ── CREATE ──
def buat_deal(session, name, start_time, end_time, tiers=TIER_DEFAULT, usage_limit=config.KPI_PAKET_USAGE_LIMIT):
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
        log(f"(DRY) buat '{name}' tier={tiers}", level="warning", modul="paket")
        return None
    bid = _call("POST", URL_CREATE, session, payload).get("data", {}).get("bundle_deal_id")
    log(f"paket '{name}' dibuat → id {bid}", level="live", modul="paket")
    return bid


# ── VALIDATE ──
def validate_items(session, item_ids, start_time, end_time, bundle_deal_id=None, chunk=50):
    """Validasi item mana yang BOLEH masuk paket. Return list item_id yg lolos.
    Item yg DITOLAK Shopee dikelompokin per (err_code, err_msg) lalu diringkas — biar
    ketahuan KENAPA ke-reject (mis. udah di deal lain / harga / stok)."""
    valid = []
    tolak = {}   # (err_code, err_msg) -> jumlah
    for c in _chunks([int(i) for i in dict.fromkeys(item_ids)], chunk):
        payload = {"start_time": int(start_time), "end_time": int(end_time), "item_id_list": list(c)}
        if bundle_deal_id:
            payload["bundle_deal_id"] = bundle_deal_id
        try:
            data = _call("POST", URL_VALIDATE, session, payload).get("data") or {}
            # item ditolak bisa nyangkut di succ_main_items (err_code != 0) ATAU fail_main_items
            kandidat = list(data.get("succ_main_items") or []) + list(data.get("fail_main_items") or [])
            for it in kandidat:
                if it.get("err_code") in (None, 0) and it.get("item_id"):
                    valid.append(int(it["item_id"]))
                else:
                    key = (it.get("err_code"), str(it.get("err_msg") or it.get("msg") or "")[:80])
                    tolak[key] = tolak.get(key, 0) + 1
        except Exception as e:
            log(f"validate chunk gagal ({len(c)}): {type(e).__name__}", level="error", modul="paket")
    if tolak:
        log(f"{sum(tolak.values())} item DITOLAK validasi — alasan:", level="warning", modul="paket")
        for (code, msg), n in sorted(tolak.items(), key=lambda x: -x[1]):
            log(f"  • {n:>4}× err_code={code}  {msg}", level="warning", modul="paket")
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
            log(f"{len(c)} item → {label} paket {bundle_deal_id}", level="live", modul="paket")
        except Exception as e:
            fail += len(c)
            log(f"attach chunk gagal ({len(c)}): {type(e).__name__} — lanjut", level="error", modul="paket")
    return ok, fail


# ── STOP ──
def stop_deal(session, bundle_deal_id):
    if getattr(config, "DRY_RUN", False):
        log(f"(DRY) stop {bundle_deal_id}", level="warning", modul="paket"); return
    _call("POST", URL_OP, session, {"bundle_deal_id": bundle_deal_id, "action": "stop"})
    log(f"paket {bundle_deal_id} DIHENTIKAN", level="live", modul="paket")


# ── FASE 2 kasus 4: takedown item dari paket (harga dasar mau diubah) + re-add ──
def keluarkan_item(session, bundle_deal_ids, item_ids):
    """Keluarkan item dari SEMUA deal aktif (PUT status=2). Konteks tak simpan deal-id per item,
    jadi coba keluarin dari tiap deal (Shopee no-op kalau item tak di deal itu). Return jumlah OK."""
    if not bundle_deal_ids or not item_ids:
        return 0
    total = 0
    for bid in bundle_deal_ids:
        ok, _ = attach_items(session, bid, item_ids, status=STATUS_KELUAR)
        total += ok
    return total


def masukkan_item(session, bundle_deal_id, item_ids, start_time, end_time):
    """Re-add item ke 1 deal (validate dulu, lalu PUT status=1). Buat 'pasang lagi' setelah
    harga dasar diubah (paket WAJIB selalu aktif). Return (ok, gagal)."""
    if not bundle_deal_id or not item_ids:
        return 0, 0
    valid = validate_items(session, item_ids, start_time, end_time, bundle_deal_id)
    if not valid:
        return 0, 0
    return attach_items(session, bundle_deal_id, valid, status=STATUS_MASUK)


# ── ORKESTRATOR: masukin SEMUA produk ke 1 paket ──
def enroll_semua(session, item_ids, bundle_deal_id, start_time, end_time):
    """Validasi lalu attach SEMUA item_ids ke paket bundle_deal_id.
    Return ringkasan dict."""
    log(f"enroll {len(item_ids)} produk → paket {bundle_deal_id}…", level="detail", modul="paket")
    valid = validate_items(session, item_ids, start_time, end_time, bundle_deal_id)
    ok, fail = attach_items(session, bundle_deal_id, valid)
    hasil = {"total": len(set(item_ids)), "lolos_validasi": len(valid), "masuk": ok, "gagal": fail}
    log(f"enroll selesai: {hasil}", level="ok", modul="paket")
    return hasil


def enroll_dengan_overflow(session, item_ids, bid, nama_toko, start, end, prefix, maks=None):
    """Enroll item ke paket `bid`; kalau isi paket lewat `maks` (cap per-paket), sisanya
    TUMPAH ke paket tambahan '<prefix> <toko> #N'. Return ringkasan gabungan.
    Idempotent: `item_ids` mestinya udah = produk 'belum masuk paket manapun'."""
    maks = maks or config.KPI_PAKET_MAKS_ITEM
    ids = [int(i) for i in dict.fromkeys(item_ids)]
    kini = 0 if getattr(config, "DRY_RUN", False) else len(baca_item_deal(session, bid))
    ringkas = {"belum_masuk": len(ids), "masuk": 0, "gagal": 0, "paket": [bid], "paket_tambahan": 0}

    ruang = max(0, maks - kini)
    batch = ids if ruang >= len(ids) else ids[:ruang]
    sisa = ids[len(batch):]
    if batch:
        r = enroll_semua(session, batch, bid, start, end)
        ringkas["masuk"] += r["masuk"]; ringkas["gagal"] += r["gagal"]

    n = 2
    while sisa:
        nbid = buat_deal(session, f"{prefix} {nama_toko} #{n}", start, end)
        if not nbid:      # DRY atau gagal buat
            log(f"overflow {len(sisa)} produk butuh paket tambahan (DRY/gagal buat, di-skip)", level="warning", modul="paket")
            break
        ringkas["paket"].append(nbid); ringkas["paket_tambahan"] += 1
        chunk = sisa[:maks]
        r = enroll_semua(session, chunk, nbid, start, end)
        ringkas["masuk"] += r["masuk"]; ringkas["gagal"] += r["gagal"]
        sisa = sisa[maks:]; n += 1
    return ringkas


# ── Sumber item_id: SEMUA produk toko dari harga_olah_data (hasil grab Fase 1) ──
def item_ids_toko(nama_toko):
    """Distinct item_id 1 toko dari harga_olah_data (produk berstok hasil grab)."""
    from sqlalchemy import text
    from modules.db import get_engine
    with get_engine().connect() as c:
        rows = c.execute(text("select distinct item_id from harga_olah_data where toko=:t"),
                         {"t": nama_toko}).fetchall()
    return [int(r.item_id) for r in rows]
