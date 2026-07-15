"""modules/flash_sale_daftar.py — AUTO daftar SEMUA produk ke FLASH SALE Toko (upsell mingguan).

✅ TERBUKTI API-able via requests (3 Jul; set_items 2 item masuk). Semua `marketing/v4/shop_flash_sale/*`:
  GET  get_time_slot_id {start_time,end_time}        -> data=LIST slot [{timeslot_id,start,end}]
  GET  get_shop_flash_sale_list {offset,limit,type}  -> sesi existing
  GET  get_product_selector (scene=shop_flash_sale)  -> produk eligible (images=STRING, price/stock item-level)
  POST set_shop_flash_sale {time_slot_id}            -> BIKIN sesi -> {flash_sale_id}
  POST set_shop_flash_sale {flash_sale_id,time_slot_id,status:2} -> STOP sesi
  POST set_shop_flash_sale_items {flash_sale_id, items:[...], use_global_category:true}  <- WAJIB field itu!
       item: {item_id, model_id, status(1=masuk/0=keluar), input_promo_price, stock, item_display_image, purchase_limit}
  POST set_item_sequence {flash_sale_id, display_sequence_list:[{item_id, display_sequence}]}  -> urutan

Requirement user: SEMUA produk masuk; harga flash = harga_diskon − 10; maks 50 produk/sesi; bergilir antar
sesi (chunk[i%n]); urut KATEGORI lalu PENJUALAN tertinggi; 1 minggu sekali; model_id dari SQL, image dari selector.
Aturan Shopee: stok promo maks 350, diskon 1-99%. Hormatin config.DRY_RUN.
"""
import time
from modules.log_siklus import log
import requests
import config

_B = "https://seller.shopee.co.id/api/marketing/v4/shop_flash_sale/"
URL_SLOT = _B + "get_time_slot_id/"
URL_LIST = _B + "get_shop_flash_sale_list/"
URL_SET = _B + "set_shop_flash_sale/"
URL_SET_ITEMS = _B + "set_shop_flash_sale_items/"
URL_SEQ = _B + "set_item_sequence/"
URL_SELECTOR = "https://seller.shopee.co.id/api/marketing/v4/public/get_product_selector/"

STATUS_MASUK = 1
STATUS_KELUAR = 0
# KPI pasang flash — SATU sumber di config (jangan hardcode di sini).
MAKS_PRODUK_PER_SESI = config.KPI_FLASH_MAKS_PRODUK_PER_SESI
MAKS_STOK = config.KPI_FLASH_MAKS_STOK
POTONG_HARGA = config.KPI_FLASH_POTONG_HARGA   # harga flash = harga_diskon - ini
_TO = (15, 60)


def _req(method, session, url, payload=None, extra_params=None):
    """requests + cek code==0. Balikin data (bisa list/dict). Anti-hang (tuple timeout)."""
    headers = config.grab_headers(session)
    params = dict(session["params"])
    if extra_params:
        params.update(extra_params)
    r = requests.request(method, url, headers=headers, params=params, json=payload, timeout=_TO)
    d = r.json()
    if not (isinstance(d, dict) and d.get("code") == 0):
        raise RuntimeError(f"[flash] {url.split('/api/')[-1]}: code={d.get('code')} {d.get('message') or d.get('msg')}")
    return d.get("data")


def _chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


# ── SLOT & SESI ──
def slot_waktu(session, hari=config.KPI_FLASH_SLOT_HARI):
    """Slot flash sale yang tersedia `hari` ke depan -> list {timeslot_id, start_time, end_time}."""
    now = int(time.time())
    return _req("GET", session, URL_SLOT, extra_params={"start_time": now, "end_time": now + hari * 86400}) or []


def list_sesi(session):
    # get_shop_flash_sale_list = GET (query params), sama seperti modules/flash_sale.py (takedown).
    return (_req("GET", session, URL_LIST,
                 extra_params={"offset": 0, "limit": 50, "type": 0}) or {}).get("flash_sale_list") or []


def bikin_sesi(session, time_slot_id):
    """Bikin sesi flash di 1 slot -> flash_sale_id."""
    if getattr(config, "DRY_RUN", False):
        log(f"(DRY) bikin sesi slot {time_slot_id}", level="warning", modul="flash"); return None
    fsid = (_req("POST", session, URL_SET, {"time_slot_id": time_slot_id}) or {}).get("flash_sale_id")
    log(f"sesi dibikin: {fsid} (slot {time_slot_id})", level="live", modul="flash")
    return fsid


def stop_sesi(session, flash_sale_id, time_slot_id):
    if getattr(config, "DRY_RUN", False):
        log(f"(DRY) stop sesi {flash_sale_id} (slot {time_slot_id})", level="warning", modul="flash")
        return
    _req("POST", session, URL_SET, {"flash_sale_id": flash_sale_id, "time_slot_id": time_slot_id, "status": 2})
    log(f"sesi {flash_sale_id} distop", level="live", modul="flash")


def _as_cat(v):
    """Kategori jadi int comparable (buat sort). global_cat / cat_path[0] bisa int ATAU
    dict {catid/id/global_cat_id:...} → ekstrak id-nya. Gagal → 0."""
    if isinstance(v, dict):
        for k in ("catid", "cat_id", "id", "global_cat_id", "category_id"):
            if v.get(k) is not None:
                v = v[k]; break
        else:
            return 0
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return 0


# ── DATA PRODUK (image+kategori dari selector, model+harga+stok+sales dari SQL) ──
def _peta_selector(session):
    """{item_id: {img, kategori, harga}} produk eligible flash. Endpoint CURSOR-based:
    pakai next_offset/cursor dari respons, dan STOP kalau 1 halaman ga nambah item baru
    (dulu naikin offset manual → Shopee balikin halaman sama → loop ~1000x = 16 menit)."""
    peta = {}; cursor = ""; offset = 0; guard = 0
    while guard < 200:                                    # hard cap: 200 halaman (20rb produk) cukup
        guard += 1
        data = _req("GET", session, URL_SELECTOR, extra_params={
            "cursor": cursor, "limit": 100, "offset": offset, "is_ads": 0,
            "need_brand": 0, "need_item_model": 0, "scene": "shop_flash_sale"}) or {}
        items = data.get("item_list") or []
        sebelum = len(peta)
        for it in items:
            imgs = it.get("images") or ""
            cat_path = it.get("category_path") or []
            kategori = it.get("global_cat") or (cat_path[0] if cat_path else 0) or 0
            peta[int(it["itemid"])] = {
                "img": imgs.split(",")[0] if imgs else "",
                "kategori": _as_cat(kategori),
                "harga": int(it.get("price") or 0),
            }
        # STOP: halaman ga penuh, ATAU ga ada item BARU (endpoint ngulang halaman sama).
        if len(items) < 100 or len(peta) == sebelum:
            break
        cursor = str(data.get("cursor") or data.get("next_cursor") or "")
        offset += 100
    return peta


def siapkan_produk(session, nama_toko):
    """Return list produk SIAP flash, URUT kategori lalu penjualan tertinggi:
    [{item_id, models:[model_id], harga_diskon, stok, img, kategori, sales}]."""
    from sqlalchemy import text
    from modules.db import get_engine
    from modules import sql_harga as SQL
    sel = _peta_selector(session)
    log(f"selector: {len(sel)} produk eligible flash", level="detail", toko=nama_toko, modul="flash")
    # Query produk TANPA subquery-korelasi sales (dulu: sum fact_penjualan per baris x 1391 produk
    # ke tabel raksasa 789MB tanpa filter periode = hang 10+ menit). Sales via 1 query batch.
    with get_engine().connect() as c:
        rows = c.execute(text("""
            select o.item_id,
                   array_agg(distinct o.model_id) mids,
                   max(o.stok) stok,
                   max(coalesce(nullif(a.harga_diskon,0), o.harga_tampil)) harga_diskon
            from harga_olah_data o left join harga_all_produk a on upper(a.sku)=upper(o.sku)
            where o.toko=:t and o.stok>0
            group by o.item_id"""), {"t": nama_toko}).fetchall()
    sales = SQL.baca_penjualan_per_hari([int(r.item_id) for r in rows])   # {item_id: unit/hari} 1 query
    hasil = []
    for r in rows:
        iid = int(r.item_id)
        if iid not in sel or not sel[iid]["img"]:
            continue   # tak eligible flash / tanpa image
        hasil.append({
            "item_id": iid, "models": [int(m) for m in r.mids],
            "harga_diskon": int(r.harga_diskon or 0), "stok": int(r.stok or 0),
            "img": sel[iid]["img"], "kategori": sel[iid]["kategori"], "sales": sales.get(iid, 0.0),
        })
    # URUT: kategori (grup) lalu penjualan tertinggi
    hasil.sort(key=lambda p: (p["kategori"], -p["sales"]))
    log(f"{len(hasil)} produk siap, urut kategori+penjualan", level="detail", toko=nama_toko, modul="flash")
    return hasil


# ── ROTASI: bagi produk ke sesi (bergilir, maks 50/sesi, tak dobel dalam 1 sesi) ──
def bagi_rotasi(produk, jumlah_sesi, per_sesi=MAKS_PRODUK_PER_SESI):
    """Return list-of-list: produk per sesi. chunk[i % n_chunk] -> kalau sesi > jumlah chunk, ulang dari awal."""
    if not produk or jumlah_sesi <= 0:
        return []
    chunks = list(_chunks(produk, per_sesi))
    return [chunks[i % len(chunks)] for i in range(jumlah_sesi)]


def _entri(produk_item):
    """Bangun entri set_items per model dari 1 produk. harga flash = harga_diskon - POTONG_HARGA."""
    harga = max(produk_item["harga_diskon"] - POTONG_HARGA, 1)
    stok = min(produk_item["stok"], MAKS_STOK)
    return [{
        "item_id": produk_item["item_id"], "model_id": m, "status": STATUS_MASUK,
        "input_promo_price": harga, "stock": stok,
        "item_display_image": produk_item["img"], "purchase_limit": 0,
    } for m in produk_item["models"]]


def daftar_ke_sesi(session, flash_sale_id, produk_sesi):
    """Masukkan daftar produk (list item) ke 1 sesi: set_items (chunked) + set urutan."""
    entri = [e for p in produk_sesi for e in _entri(p)]
    if not entri:
        return {"masuk": 0, "gagal": 0}
    if getattr(config, "DRY_RUN", False):
        log(f"(DRY) daftar {len(produk_sesi)} produk ({len(entri)} model) → sesi {flash_sale_id}", level="warning", modul="flash")
        return {"masuk": len(entri), "gagal": 0}
    masuk = gagal = 0
    for c in _chunks(entri, 50):
        try:
            res = _req("POST", session, URL_SET_ITEMS,
                       {"flash_sale_id": flash_sale_id, "items": list(c), "use_global_category": True})
            fail = res.get("failed_items") or []
            masuk += len(c) - len(fail); gagal += len(fail)
        except Exception as e:
            gagal += len(c)
            log(f"set_items chunk gagal ({len(c)}): {type(e).__name__}", level="error", modul="flash")
    # urutan tampil = urutan produk_sesi (udah ke-sort kategori+penjualan)
    try:
        seq = [{"item_id": p["item_id"], "display_sequence": i + 1} for i, p in enumerate(produk_sesi)]
        _req("POST", session, URL_SEQ, {"flash_sale_id": flash_sale_id, "display_sequence_list": seq})
    except Exception as e:
        log(f"set_item_sequence gagal (non-fatal): {type(e).__name__}", level="warning", modul="flash")
    log(f"sesi {flash_sale_id}: {masuk} model masuk, {gagal} gagal", level="live", modul="flash")
    return {"masuk": masuk, "gagal": gagal}


# ── ORKESTRATOR mingguan: grab slot seminggu -> bikin sesi -> daftar produk bergilir ──
def daftar_mingguan(session, nama_toko, maks_sesi=None):
    """Grab slot seminggu, bikin sesi tiap slot, daftarin SEMUA produk bergilir (maks 50/sesi).
    maks_sesi = batasi jumlah sesi (None = semua slot). Return ringkasan."""
    produk = siapkan_produk(session, nama_toko)
    slots = slot_waktu(session)   # hari ke depan = config.KPI_FLASH_SLOT_HARI
    if maks_sesi:
        slots = slots[:maks_sesi]
    if not produk or not slots:
        log(f"produk={len(produk)} slot={len(slots)} — skip", level="warning", toko=nama_toko, modul="flash")
        return {"sesi": 0, "masuk": 0}
    rotasi = bagi_rotasi(produk, len(slots))
    total_masuk = sesi_ok = 0
    for slot, produk_sesi in zip(slots, rotasi):
        try:
            fsid = bikin_sesi(session, slot["timeslot_id"])
            if not fsid and not getattr(config, "DRY_RUN", False):
                continue
            r = daftar_ke_sesi(session, fsid, produk_sesi)
            total_masuk += r["masuk"]; sesi_ok += 1
        except Exception as e:
            log(f"sesi slot {slot['timeslot_id']} gagal: {type(e).__name__}", level="error", toko=nama_toko, modul="flash")
    log(f"selesai: {sesi_ok} sesi, {total_masuk} model masuk", level="ok", toko=nama_toko, modul="flash")
    return {"sesi": sesi_ok, "masuk": total_masuk, "produk": len(produk), "slot": len(slots)}
