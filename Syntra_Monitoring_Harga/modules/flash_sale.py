"""modules/flash_sale.py — kelola Flash Sale Toko (Fase 2B takedown + Fase 4 daftar).

Endpoint terverifikasi (sniff __sniff_promo.json), berbasis `requests` (pakai sesi grab):
  - list  : URL_FLASH_LIST  -> flash sale aktif/mendatang (flash_sale_id, status, timeslot).
  - items : URL_FLASH_ITEMS -> item dalam 1 flash sale (status, harga, stok, gambar).
  - set   : URL_FLASH_SET_ITEMS -> ubah status item (0=keluar/takedown, 1=ikut).

status flash sale (data.status): umumnya 1=berjalan/mendatang, 2=berakhir/stop.
"""
import colorama; colorama.init()
import config
from modules.api_util import api_get, api_post


# STATUS flash sale yang masih relevan (item bisa di-takedown/daftar).
_FS_AKTIF = {1}


def list_flash_sale(session, hanya_aktif=True):
    """List flash sale toko. Return list dict (flash_sale_id, status, timeslot_id,
    start_time, end_time, item_count)."""
    hasil = []
    offset = 0
    while True:
        data = api_get(config.URL_FLASH_LIST, config.grab_headers(session),
                       {**session["params"], "offset": offset, "limit": 50, "type": 0},
                       kunci="data")["data"]
        lst = data.get("flash_sale_list") or []
        for f in lst:
            if (not hanya_aktif) or f.get("status") in _FS_AKTIF:
                hasil.append({
                    "flash_sale_id": f.get("flash_sale_id"),
                    "status": f.get("status"),
                    "timeslot_id": f.get("timeslot_id"),
                    "start_time": f.get("start_time"),
                    "end_time": f.get("end_time"),
                    "item_count": f.get("item_count", 0),
                })
        if len(lst) < 50 or offset > 5000:
            break
        offset += 50
    return hasil


def items_flash_sale(session, flash_sale_id):
    """Item dalam 1 flash sale -> list dict (item_id, model_id, status, promotion_price,
    input_promotion_price, stock, item_display_image, purchase_limit)."""
    hasil = []
    offset = 0
    while True:
        data = api_get(config.URL_FLASH_ITEMS, config.grab_headers(session),
                       {**session["params"], "flash_sale_id": flash_sale_id, "offset": offset, "limit": 100},
                       kunci="data")["data"]
        items = data.get("items") or []
        hasil.extend(i for i in items if isinstance(i, dict))
        if len(items) < 100 or offset > 100000:
            break
        offset += 100
    return hasil


def _entry(it, status):
    """Bangun 1 entri set_shop_flash_sale_items dari item existing (pertahankan field)."""
    return {
        "item_id": it.get("item_id"),
        "model_id": it.get("model_id"),
        "status": status,
        "input_promo_price": it.get("input_promotion_price") or it.get("promotion_price") or 0,
        "stock": it.get("stock", 0),
        "purchase_limit": it.get("purchase_limit", 0),
        "item_display_image": it.get("item_display_image", ""),
    }


def peta_item(session):
    """{(item_id, model_id): [flash_sale_id,...]} utk SEMUA flash sale aktif +
    cache item per flash sale -> dipakai takedown by (item,model)."""
    peta = {}
    cache = {}
    for f in list_flash_sale(session, hanya_aktif=True):
        fsid = f["flash_sale_id"]
        items = items_flash_sale(session, fsid)
        cache[fsid] = items
        for it in items:
            key = (int(it.get("item_id") or 0), int(it.get("model_id") or 0))
            peta.setdefault(key, []).append(fsid)
    return peta, cache


def set_items(session, flash_sale_id, entries, chunk=50):
    """Kirim perubahan item ke 1 flash sale, DI-CHUNK (default 50) biar payload tak
    besar & 1 chunk error/hang tidak menggugurkan sisanya. Return (sukses_bool, failed_items)."""
    if not entries:
        return True, []
    if config.DRY_RUN:
        return True, []      # simulasi: tidak kirim
    failed = []
    for i in range(0, len(entries), chunk):
        batch = entries[i:i + chunk]
        try:
            data = api_post(config.URL_FLASH_SET_ITEMS, config.grab_headers(session), session["params"],
                            {"flash_sale_id": flash_sale_id, "items": batch},
                            kunci="data", attempts=2)["data"]   # attempts=2: gagal cepat, jangan hang lama
            failed += data.get("failed_items") or []
        except Exception as e:
            failed += batch   # chunk ini gagal (mis. timeout) -> tandai, LANJUT chunk berikut
            print(colorama.Fore.RED + f"[flash sale] set_items chunk gagal ({len(batch)} item): {type(e).__name__} - lanjut" + colorama.Style.RESET_ALL)
    return (len(failed) == 0), failed


def takedown_items(session, shop, kunci_set):
    """Keluarkan variasi (set status 0) dari SEMUA flash sale aktif yang memuatnya.
    kunci_set = set (item_id, model_id). Return jumlah variasi ter-takedown."""
    if not kunci_set:
        return 0
    peta, cache = peta_item(session)
    n = 0
    for fsid, items in cache.items():
        entries = [_entry(it, config.STATUS_FLASH_KELUAR)
                   for it in items
                   if (int(it.get("item_id") or 0), int(it.get("model_id") or 0)) in kunci_set
                   and it.get("status") != config.STATUS_FLASH_KELUAR]
        if not entries:
            continue
        ok, failed = set_items(session, fsid, entries)
        n += len(entries) - len(failed)
        warna = colorama.Fore.YELLOW if config.DRY_RUN else colorama.Fore.MAGENTA
        print(warna + f"[flash sale] [{shop}] - {len(entries)} variasi -> keluar dari FS {fsid}"
              + (" (DRY)" if config.DRY_RUN else f", {len(failed)} gagal")
              + colorama.Style.RESET_ALL)
    return n
