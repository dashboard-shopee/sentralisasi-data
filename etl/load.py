"""
etl/load.py — penulis data bersih ke SQL (Supabase).

Ini "pintu masuk" data ke database. Dipakai oleh:
  - ETL migrasi (baca Sheet -> sini), dan
  - program otomasi (Fase 2: API Shopee -> sini, tanpa lewat Sheet).

API utama (semua menerima list of dict, idempotent / upsert):
    simpan_penjualan(records)
    simpan_iklan(records)
    simpan_harga(records)
    simpan_kompetitor(records)

Contoh 1 record penjualan:
    {
        "toko": "kimmioshop",            # username (wajib) -> dipetakan ke toko_id
        "produk_id": 51209166018,        # item_id Shopee (wajib utk penjualan/iklan)
        "nama_produk": "Penjepit Bulu Mata ...",
        "sku_induk": None,
        "periode": "harian",             # realtime|harian|mingguan|bulanan|tahunan
        "periode_mulai": datetime(2026, 6, 19),
        "periode_selesai": datetime(2026, 6, 20),
        "pengunjung": 122, "keranjang": 59,
        "unit_pesanan": 77, "penjualan": 663569,
        "extra": {"sumber": "api"},      # opsional, variabel laporan baru
    }
"""

from __future__ import annotations

import json
from typing import Any, Iterable

from sqlalchemy import text

from config.db import get_engine

_engine = None


def _eng():
    global _engine
    if _engine is None:
        _engine = get_engine()
    return _engine


def _peta_toko(conn) -> dict[str, int]:
    rows = conn.execute(text("select username, toko_id from dim_toko")).fetchall()
    return {u: i for u, i in rows}


def _toko_id(peta: dict[str, int], rec: dict) -> int:
    uname = rec.get("toko")
    if uname not in peta:
        raise ValueError(
            f"Toko '{uname}' tidak ada di dim_toko. "
            f"Toko valid: {sorted(peta)}"
        )
    return peta[uname]


def _extra(rec: dict) -> str:
    return json.dumps(rec.get("extra") or {})


_SQL_PRODUK = text(
    """
    insert into dim_produk (produk_id, toko_id, nama_produk, sku_induk)
    values (:pid, :tid, :nama, :sku)
    on conflict (produk_id) do update set
        toko_id = excluded.toko_id,
        nama_produk = coalesce(excluded.nama_produk, dim_produk.nama_produk),
        sku_induk = coalesce(excluded.sku_induk, dim_produk.sku_induk),
        diperbarui_pada = now()
    """
)


def _batch_produk(conn, produk: dict):
    """produk = {produk_id: (toko_id, nama, sku)} -> sekali executemany."""
    if not produk:
        return
    conn.execute(_SQL_PRODUK, [
        {"pid": pid, "tid": v[0], "nama": v[1], "sku": v[2]}
        for pid, v in produk.items()
    ])


def _dedup(params: list[dict], kunci) -> list[dict]:
    """Buang duplikat dalam 1 batch (ON CONFLICT tak boleh kena baris sama 2x).
    Yang terakhir menang."""
    seen = {}
    for p in params:
        seen[kunci(p)] = p
    return list(seen.values())


# ---------------------------------------------------------------------------
#  PENJUALAN
# ---------------------------------------------------------------------------
_SQL_PENJUALAN = text(
    """
    insert into fact_penjualan
        (toko_id, produk_id, periode, periode_mulai, periode_selesai,
         pengunjung, keranjang, unit_pesanan, penjualan, pesanan, pembeli, extra)
    values
        (:toko_id, :produk_id, :periode, :periode_mulai, :periode_selesai,
         :pengunjung, :keranjang, :unit_pesanan, :penjualan, :pesanan, :pembeli, cast(:extra as jsonb))
    on conflict (produk_id, periode, periode_mulai) do update set
        toko_id = excluded.toko_id,
        periode_selesai = excluded.periode_selesai,
        pengunjung = excluded.pengunjung,
        keranjang = excluded.keranjang,
        unit_pesanan = excluded.unit_pesanan,
        penjualan = excluded.penjualan,
        pesanan = excluded.pesanan,
        pembeli = excluded.pembeli,
        extra = excluded.extra,
        dimuat_pada = now()
    """
)


def simpan_penjualan(records: Iterable[dict]) -> int:
    records = list(records)
    if not records:
        return 0
    with _eng().begin() as conn:
        peta = _peta_toko(conn)
        produk: dict = {}
        params: list[dict] = []
        for r in records:
            tid = _toko_id(peta, r)
            pid = r.get("produk_id")
            if pid is not None:
                produk[pid] = (tid, r.get("nama_produk"), r.get("sku_induk"))
            params.append({
                "toko_id": tid,
                "produk_id": pid,
                "periode": r["periode"],
                "periode_mulai": r["periode_mulai"],
                "periode_selesai": r.get("periode_selesai"),
                "pengunjung": r.get("pengunjung"),
                "keranjang": r.get("keranjang"),
                "unit_pesanan": r.get("unit_pesanan"),
                "penjualan": r.get("penjualan"),
                "pesanan": r.get("pesanan"),
                "pembeli": r.get("pembeli"),
                "extra": _extra(r),
            })
        _batch_produk(conn, produk)
        params = _dedup(params, lambda p: (p["produk_id"], p["periode"], p["periode_mulai"]))
        conn.execute(_SQL_PENJUALAN, params)
    return len(params)


# ---------------------------------------------------------------------------
#  IKLAN
# ---------------------------------------------------------------------------
_SQL_IKLAN = text(
    """
    insert into fact_iklan
        (toko_id, produk_id, periode, periode_mulai, periode_selesai,
         dilihat, klik, konversi, omzet_iklan, biaya_iklan, roas, extra)
    values
        (:toko_id, :produk_id, :periode, :periode_mulai, :periode_selesai,
         :dilihat, :klik, :konversi, :omzet_iklan, :biaya_iklan, :roas, cast(:extra as jsonb))
    on conflict (produk_id, periode, periode_mulai) do update set
        toko_id = excluded.toko_id,
        periode_selesai = excluded.periode_selesai,
        dilihat = excluded.dilihat,
        klik = excluded.klik,
        konversi = excluded.konversi,
        omzet_iklan = excluded.omzet_iklan,
        biaya_iklan = excluded.biaya_iklan,
        roas = excluded.roas,
        extra = excluded.extra,
        dimuat_pada = now()
    """
)


def simpan_iklan(records: Iterable[dict]) -> int:
    records = list(records)
    if not records:
        return 0
    with _eng().begin() as conn:
        peta = _peta_toko(conn)
        produk: dict = {}
        params: list[dict] = []
        for r in records:
            tid = _toko_id(peta, r)
            pid = r.get("produk_id")
            if pid is not None:
                produk[pid] = (tid, r.get("nama_produk"), r.get("sku_induk"))
            omzet = r.get("omzet_iklan")
            biaya = r.get("biaya_iklan")
            roas = r.get("roas")
            if roas is None and omzet is not None and biaya:
                roas = round(float(omzet) / float(biaya), 4)
            params.append({
                "toko_id": tid,
                "produk_id": pid,
                "periode": r["periode"],
                "periode_mulai": r["periode_mulai"],
                "periode_selesai": r.get("periode_selesai"),
                "dilihat": r.get("dilihat"),
                "klik": r.get("klik"),
                "konversi": r.get("konversi"),
                "omzet_iklan": omzet,
                "biaya_iklan": biaya,
                "roas": roas,
                "extra": _extra(r),
            })
        _batch_produk(conn, produk)
        params = _dedup(params, lambda p: (p["produk_id"], p["periode"], p["periode_mulai"]))
        conn.execute(_SQL_IKLAN, params)
    return len(params)


# ---------------------------------------------------------------------------
#  HARGA (snapshot)
# ---------------------------------------------------------------------------
_SQL_HARGA = text(
    """
    insert into fact_harga
        (toko_id, item_id, model_id, sku, nama_produk, nama_variasi,
         harga_awal, harga_target, harga_tampil, sumber_harga, extra)
    values
        (:toko_id, :item_id, :model_id, :sku, :nama_produk, :nama_variasi,
         :harga_awal, :harga_target, :harga_tampil, :sumber_harga, cast(:extra as jsonb))
    """
)


def simpan_harga(records: Iterable[dict]) -> int:
    records = list(records)
    if not records:
        return 0
    with _eng().begin() as conn:
        peta = _peta_toko(conn)
        params = [{
            "toko_id": _toko_id(peta, r),
            "item_id": r.get("item_id"),
            "model_id": r.get("model_id"),
            "sku": r.get("sku"),
            "nama_produk": r.get("nama_produk"),
            "nama_variasi": r.get("nama_variasi"),
            "harga_awal": r.get("harga_awal"),
            "harga_target": r.get("harga_target"),
            "harga_tampil": r.get("harga_tampil"),
            "sumber_harga": r.get("sumber_harga"),
            "extra": _extra(r),
        } for r in records]
        conn.execute(_SQL_HARGA, params)
    return len(records)


# ---------------------------------------------------------------------------
#  KOMPETITOR (snapshot)
# ---------------------------------------------------------------------------
_SQL_KOMPETITOR = text(
    """
    insert into fact_kompetitor
        (market, produk_acuan, toko_pesaing, nama_produk,
         harga, terjual, rating, url, extra)
    values
        (:market, :produk_acuan, :toko_pesaing, :nama_produk,
         :harga, :terjual, :rating, :url, cast(:extra as jsonb))
    """
)


_SQL_PESANAN = text(
    """
    insert into fact_pesanan
        (toko_id, periode, periode_mulai, periode_selesai,
         jumlah_pesanan, pesanan_siap, pesanan_batal, pembeli, omzet_pesanan, extra)
    values
        (:toko_id, :periode, :periode_mulai, :periode_selesai,
         :jumlah_pesanan, :pesanan_siap, :pesanan_batal, :pembeli, :omzet_pesanan, cast(:extra as jsonb))
    on conflict (toko_id, periode, periode_mulai) do update set
        periode_selesai = excluded.periode_selesai,
        jumlah_pesanan = excluded.jumlah_pesanan,
        pesanan_siap = excluded.pesanan_siap,
        pesanan_batal = excluded.pesanan_batal,
        pembeli = excluded.pembeli,
        omzet_pesanan = excluded.omzet_pesanan,
        extra = excluded.extra,
        dimuat_pada = now()
    """
)


def simpan_pesanan(records: Iterable[dict]) -> int:
    """fact_pesanan level-toko. records: {toko, periode, periode_mulai, jumlah_pesanan,
    pesanan_siap, pesanan_batal, pembeli, omzet_pesanan, extra}."""
    records = list(records)
    if not records:
        return 0
    with _eng().begin() as conn:
        peta = _peta_toko(conn)
        params = [{
            "toko_id": _toko_id(peta, r),
            "periode": r["periode"], "periode_mulai": r["periode_mulai"],
            "periode_selesai": r.get("periode_selesai"),
            "jumlah_pesanan": r.get("jumlah_pesanan"),
            "pesanan_siap": r.get("pesanan_siap"),
            "pesanan_batal": r.get("pesanan_batal"),
            "pembeli": r.get("pembeli"),
            "omzet_pesanan": r.get("omzet_pesanan"),
            "extra": _extra(r),
        } for r in records]
        params = _dedup(params, lambda p: (p["toko_id"], p["periode"], p["periode_mulai"]))
        conn.execute(_SQL_PESANAN, params)
    return len(params)


def simpan_kompetitor(records: Iterable[dict]) -> int:
    records = list(records)
    if not records:
        return 0
    with _eng().begin() as conn:
        params = [{
            "market": r.get("market"),
            "produk_acuan": r.get("produk_acuan"),
            "toko_pesaing": r.get("toko_pesaing"),
            "nama_produk": r.get("nama_produk"),
            "harga": r.get("harga"),
            "terjual": r.get("terjual"),
            "rating": r.get("rating"),
            "url": r.get("url"),
            "extra": _extra(r),
        } for r in records]
        conn.execute(_SQL_KOMPETITOR, params)
    return len(records)
