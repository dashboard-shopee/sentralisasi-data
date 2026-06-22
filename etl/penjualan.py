"""
etl/penjualan.py — Bagian A: sync Penjualan (Sheet "Input Produk" -> fact_penjualan).

READ-ONLY terhadap Sheet. Tidak menyentuh bot / program lain.

Struktur sumber ("Input Produk"): 6 blok x 8 kolom mendatar —
MINGGU 1..5 (mingguan) + "1 BULAN" (bulanan). Tiap blok punya timestamp
capture di baris 2, dipakai sebagai periode_mulai (kunci snapshot).
Kolom per blok: Nama Toko, Kode Produk, Produk, SKU Induk, Pengunjung(Kunjungan),
Pengunjung(Keranjang), Produk(Pesanan Siap Dikirim), Penjualan(IDR).

Jalankan:  python -m etl.penjualan
"""

from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import text  # noqa: E402

from config.db import get_engine  # noqa: E402
from config.sheets import SHEET_IKLAN, get_client  # noqa: E402
from etl.load import simpan_penjualan  # noqa: E402

TAB = "Input Produk - TESTING"
BLOK_LEBAR = 8
BARIS_DATA_MULAI = 3  # index 0-based -> baris ke-4 di sheet


def _peta_nama_toko() -> dict[str, str]:
    """{nama_normalisasi: username} dari dim_toko."""
    with get_engine().connect() as c:
        rows = c.execute(text("select nama, username from dim_toko")).fetchall()
    return {nama.strip().casefold(): uname for nama, uname in rows}


def _angka(x):
    """Teks sel -> int/float/None. Tahan pemisah ribuan & 'Rp'."""
    if x is None:
        return None
    s = str(x).strip().replace("Rp", "").replace(".", "").replace(",", "").replace(" ", "")
    if s in ("", "-"):
        return None
    try:
        return int(s)
    except ValueError:
        try:
            return float(s)
        except ValueError:
            return None


def _parse_label(label: str):
    """'MINGGU 1\\n(09/06/2026 16:59)' -> ('mingguan', datetime, 'MINGGU 1')."""
    m = re.search(r"\((\d{2})/(\d{2})/(\d{4})\s+(\d{1,2}):(\d{2})", label)
    cap = None
    if m:
        d, mo, y, h, mi = map(int, m.groups())
        cap = datetime(y, mo, d, h, mi)
    low = label.lower()
    if "minggu" in low:
        per = "mingguan"
    elif "bulan" in low:
        per = "bulanan"
    elif "hari" in low:
        per = "harian"
    elif "tahun" in low:
        per = "tahunan"
    else:
        per = None
    judul = label.split("\n")[0].strip()
    return per, cap, judul


def sync_penjualan(verbose: bool = True) -> int:
    gc = get_client()
    ws = gc.open_by_key(SHEET_IKLAN).worksheet(TAB)
    data = ws.get_all_values()
    if len(data) < BARIS_DATA_MULAI + 1:
        print("Sheet kosong / format tak terduga.")
        return 0

    baris_label = data[1]  # baris 2
    peta = _peta_nama_toko()
    ncol = len(baris_label)

    records: list[dict] = []
    toko_tak_dikenal: set[str] = set()
    ringkas_blok: list[str] = []

    for start in range(1, ncol, BLOK_LEBAR):
        label = baris_label[start] if start < len(baris_label) else ""
        per, cap, judul = _parse_label(label)
        if not per or not cap:
            continue
        n_blok = 0
        for row in data[BARIS_DATA_MULAI:]:
            def cell(off: int) -> str:
                idx = start + off
                return row[idx].strip() if idx < len(row) and row[idx] else ""

            kode = cell(1)
            if not kode.isdigit():
                continue
            nama_toko = cell(0)
            uname = peta.get(nama_toko.casefold())
            if not uname:
                if nama_toko:
                    toko_tak_dikenal.add(nama_toko)
                continue
            records.append({
                "toko": uname,
                "produk_id": int(kode),
                "nama_produk": cell(2) or None,
                "sku_induk": cell(3) or None,
                "periode": per,
                "periode_mulai": cap,
                "pengunjung": _angka(cell(4)),
                "keranjang": _angka(cell(5)),
                "unit_pesanan": _angka(cell(6)),
                "penjualan": _angka(cell(7)),
                "extra": {"label": judul, "sumber": "sheet:input_produk"},
            })
            n_blok += 1
        ringkas_blok.append(f"{judul} [{per}] @ {cap:%d/%m/%Y %H:%M} -> {n_blok} baris")

    if verbose:
        print(f"Blok terbaca dari '{TAB}':")
        for b in ringkas_blok:
            print("  -", b)
        if toko_tak_dikenal:
            print("  ! Nama toko tak dikenal (dilewati):", sorted(toko_tak_dikenal))

    n = simpan_penjualan(records)
    if verbose:
        print(f"\n{n} baris penjualan disimpan/diperbarui ke fact_penjualan.")
    return n


if __name__ == "__main__":
    sync_penjualan()
