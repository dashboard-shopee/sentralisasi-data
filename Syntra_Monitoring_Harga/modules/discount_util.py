"""
discount_util.py — cari campaign Diskon Toko (Layer 2, penunjang Langkah 2 & 4).

grab_promotion_id: ambil promo toko yang SUDAH ADA — BERJALAN (time_status 2)
diutamakan; bila termasuk_mendatang=True dan tidak ada yang berjalan, pakai yang
MENDATANG (time_status 1). Dipilih berdasarkan nama (config.NAMA_PROMO).
"""
import config
from modules.api_util import api_post
from modules.log_siklus import log


# GRAB PAYLOAD (daftar diskon toko). limit API maksimal 10.
# time_status: 0=semua, 1=mendatang, 2=berjalan, 3=berakhir.
def grab_payload(offset=0, limit=10, time_status=0):
    return {"discount_type": 1, "time_status": time_status, "offset": offset, "limit": limit}


# Ambil seluruh seller discount untuk satu time_status (paginate sampai habis).
def _list_diskon(session, time_status):
    hasil = []
    offset = 0
    while True:
        data = api_post(
            config.URL_LIST_DISKON, config.grab_headers(session), session["params"],
            grab_payload(offset=offset, time_status=time_status), kunci="data",
        )["data"]
        diskon = data.get("discounts", []) or []
        for d in diskon:
            sd = d.get("seller_discount") if isinstance(d, dict) else None
            if isinstance(sd, dict) and sd.get("discount_id"):
                hasil.append({
                    "promotion_id": sd["discount_id"],
                    "name": str(sd.get("name", "")).strip(),
                    "time_status": sd.get("time_status"),
                })
        if len(diskon) < 10 or offset > 990:
            break
        offset += 10
    return hasil


# GRAB SEMUA PROMO TOKO — seller discount BERJALAN (2) + MENDATANG (1).
# Query per-status terpisah supaya tidak keseret ratusan diskon BERAKHIR.
# Dedup per promotion_id, BERJALAN diurutkan dulu.
def grab_semua_promo(shop, session):
    gabung = {}
    for ts in (2, 1):                       # 2=berjalan dulu, 1=mendatang
        for p in _list_diskon(session, ts):
            # hanya yang benar2 berjalan/mendatang (jaga2 server abaikan filter)
            if p["time_status"] in (1, 2):
                gabung.setdefault(p["promotion_id"], p)
    hasil = sorted(gabung.values(), key=lambda x: 0 if x["time_status"] == 2 else 1)
    log(f"{len(hasil)} promo toko ditemukan: "
        + (", ".join(f"{p['name']}({'jalan' if p['time_status']==2 else 'datang'})" for p in hasil) or "TIDAK ADA"),
        level="detail" if hasil else "warning", toko=shop, modul="promo_toko")
    return hasil


# GRAB PROMOTION ID — campaign Diskon Toko yang sudah ada.
#   Prioritas: BERJALAN (time_status 2) dulu; kalau tidak ada & termasuk_mendatang=True,
#   pakai yang MENDATANG (time_status 1). Dalam tiap status, cocok-nama diutamakan.
#   None hanya bila benar-benar tidak ada promo toko (berjalan maupun mendatang).
def grab_promotion_id(shop, session, nama_promo, termasuk_mendatang=False):
    target = (nama_promo or "").strip().lower()
    ong_cocok = ong_first = up_cocok = up_first = None

    offset = 0
    while True:
        data = api_post(
            config.URL_LIST_DISKON,
            config.grab_headers(session),
            session["params"],
            grab_payload(offset=offset),
            kunci="data",
        )["data"]
        diskon = data.get("discounts", []) or []

        for d in diskon:
            sd = d.get("seller_discount") if isinstance(d, dict) else None
            if not isinstance(sd, dict):
                continue
            ts = sd.get("time_status")
            nama = str(sd.get("name", "")).strip()
            pid = sd.get("discount_id")
            cocok_nama = bool(target and target in nama.lower())
            if ts == 2:        # BERJALAN
                if ong_first is None: ong_first = (pid, nama, "berjalan")
                if cocok_nama and ong_cocok is None: ong_cocok = (pid, nama, "berjalan")
            elif ts == 1:      # MENDATANG
                if up_first is None: up_first = (pid, nama, "mendatang")
                if cocok_nama and up_cocok is None: up_cocok = (pid, nama, "mendatang")

        if ong_cocok or len(diskon) < 10 or offset > 200:
            break
        offset += 10

    pilih = ong_cocok or ong_first
    if pilih is None and termasuk_mendatang:
        pilih = up_cocok or up_first
    if not pilih:
        log("tidak ada promo toko (berjalan/mendatang).", level="warning", toko=shop, modul="promo_toko")
        return None
    pid, nama, stat = pilih
    log(f"promo toko '{nama}' (id={pid}) [{stat}]", level="detail", toko=shop, modul="promo_toko")
    return pid


# Cek apakah sudah ada promo toko yang BELUM MULAI (time_status==1) -> tanda
# sudah pernah diduplikat, jangan bikin lagi.
def ada_promo_belum_mulai(session, nama_promo):
    data = api_post(
        config.URL_LIST_DISKON, config.grab_headers(session), session["params"],
        grab_payload(), kunci="data",
    )["data"]
    target = (nama_promo or "").strip().lower()
    for d in data.get("discounts", []) or []:
        sd = d.get("seller_discount") if isinstance(d, dict) else None
        if isinstance(sd, dict) and sd.get("time_status") == 1:
            if (not target) or (target in str(sd.get("name", "")).lower()):
                return True
    return False


# Cari promotion_id promo toko APA PUN (status apa saja) di toko ini -> untuk
# menyalin gambar banner saat BUAT PROMO DARI 0. None bila toko belum pernah punya promo.
def grab_promo_apapun_id(session):
    offset = 0
    while True:
        data = api_post(
            config.URL_LIST_DISKON, config.grab_headers(session), session["params"],
            grab_payload(offset=offset), kunci="data",
        )["data"]
        diskon = data.get("discounts", []) or []
        for d in diskon:
            sd = d.get("seller_discount") if isinstance(d, dict) else None
            if isinstance(sd, dict) and sd.get("discount_id"):
                return sd["discount_id"]
        if len(diskon) < 10 or offset > 200:
            return None
        offset += 10


# GRAB DETAIL PROMO — judul, gambar, start/end, total produk (untuk duplikat).
def grab_promo_detail(session, promotion_id):
    data = api_post(
        config.URL_GET_PROMO_DETAIL,
        config.grab_headers(session),
        session["params"],
        {"promotion_id_list": [promotion_id], "need_image": True, "need_count": True, "offset": 0, "limit": 1},
        kunci="data",
    )["data"]
    lst = data.get("discount_list") or []
    return lst[0] if lst else None


# GRAB ITEM PROMO — semua (item_id, model_id, promotion_price, status) dalam promo.
#
# ⚠️ PENTING: endpoint get_discount_items_AGGREGATED memakai offset/limit per ITEM
#    (produk induk), TAPI discount_item_list dibalikin per MODEL (variasi).
#    Jadi offset HARUS maju per-item (+= page_size), BUKAN per jumlah baris model.
#    (dulu offset += len(items) -> lompat kejauhan -> item di tengah ke-skip ->
#     produk dianggap "belum di promo" -> gagal dirubah.)
#    total_count = jumlah ITEM -> dipakai sebagai batas berhenti.
def grab_item_promo(shop, session, promotion_id, page_size=100):
    hasil = []
    offset = 0
    total = None
    while True:
        data = api_post(
            config.URL_GET_PROMO_ITEMS,
            config.grab_headers(session),
            session["params"],
            {"promotion_id": promotion_id, "offset": offset, "limit": page_size},
            kunci="data",
        )["data"]
        items = data.get("discount_item_list") or []
        if total is None:
            total = int(data.get("total_count", 0))
        for it in items:
            if not isinstance(it, dict):
                continue
            hasil.append({
                "item_id": it.get("item_id"),
                "model_id": it.get("model_id"),
                "promotion_price": it.get("promotion_price", 0),   # micro-unit
                "status": it.get("status", 1),
            })
        # Maju per ITEM (jumlah item unik di halaman ini, biasanya = page_size).
        n_item = len({it.get("item_id") for it in items if isinstance(it, dict)})
        offset += n_item
        if (not items) or n_item == 0 or (total and offset >= total) or offset > 100000:
            break
    log(f"{len(hasil)} variasi (dari {total} item) terdaftar di promo {promotion_id}", level="detail", toko=shop, modul="promo_toko")
    return hasil
