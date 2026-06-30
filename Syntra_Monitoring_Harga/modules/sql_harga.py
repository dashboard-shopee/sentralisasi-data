"""modules/sql_harga.py — pengganti sheet_data/sheet_util: baca/tulis SQL (harga_olah_data).

FASE 1: simpan hasil grab produk Shopee ke harga_olah_data (upsert).
Kolom yang diisi grab: toko, item_id, model_id, sku, nama_variasi, nama_produk,
harga_awal, harga_tampil, sumber_harga. Kolom lain (ptag, harga_diskon_db,
harga_pancing, harga_akhir_target, selisih, alasan) = milik dashboard/user ->
TIDAK ditimpa (dipertahankan saat upsert).
"""
from sqlalchemy import text
from modules.db import get_engine

_SQL_UPSERT = text("""
    insert into harga_olah_data
        (toko, item_id, model_id, sku, nama_variasi, nama_produk,
         harga_awal, harga_tampil, sumber_harga, diperbarui_pada)
    values
        (:toko, :item_id, :model_id, :sku, :nama_variasi, :nama_produk,
         :harga_awal, :harga_tampil, :sumber, now())
    on conflict (toko, item_id, model_id) do update set
        sku = excluded.sku,
        nama_variasi = excluded.nama_variasi,
        nama_produk = excluded.nama_produk,
        harga_awal = excluded.harga_awal,
        harga_tampil = excluded.harga_tampil,
        sumber_harga = excluded.sumber_harga,
        diperbarui_pada = now()
""")


def _baris_ke_param(r):
    # r = [toko, item_id, model_id, sku, nama_variasi, nama_produk, harga_awal, harga_tampil, sumber]
    return {
        "toko": r[0],
        "item_id": int(r[1]),
        "model_id": int(r[2] or 0),
        "sku": (str(r[3]).strip() or None) if r[3] is not None else None,
        "nama_variasi": (r[4] or None),
        "nama_produk": (r[5] or None),
        "harga_awal": r[6] or 0,
        "harga_tampil": r[7] or 0,
        "sumber": (r[8] or None),
    }


def simpan_olah_data(rows):
    """Upsert list baris hasil grab_produk ke harga_olah_data. Return jumlah baris."""
    if not rows:
        return 0
    params = [_baris_ke_param(r) for r in rows]
    # dedup dalam 1 batch (ON CONFLICT tak boleh kena baris sama 2x)
    seen = {}
    for p in params:
        seen[(p["toko"], p["item_id"], p["model_id"])] = p
    params = list(seen.values())
    with get_engine().begin() as c:
        c.execute(_SQL_UPSERT, params)
    return len(params)
