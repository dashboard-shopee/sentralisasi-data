"""
komisi_util.py — BACA tab 'Komisi' -> mapping harga jual + persen komisi per toko.

Struktur tab 'Komisi':
  Baris 1 : nama toko di kolom AWAL tiap blok (mis. F='Alialia Store', AD='YARRA STORE').
            A='SKU', B='Parent SKU', C='Category', D='Total Sales', E='Net Price'.
  Baris 2 : sub-header per blok 3 kolom -> ['Harga Saat Ini', '<persen>%', 'Harga Jual'].
            Persen komisi DIBACA dari header kolom TENGAH ('10%' -> 10; bisa '8%' dst).
  Baris 3+: data per SKU (kolom A = SKU).

Toko dianggap "komisi aktif" bila kolom 'Harga Jual'-nya TERISI (> 0). Saat ini
otomatis hanya YARRA (toko lain kolom Harga Jual-nya kosong).

Hasil hasil_komisi():
  { username: {"nama": <display>, "persen": <float>, "harga": { SKU: <int rupiah> }} }
"""
import colorama; colorama.init()
import config
from modules.sheet_util import buka_workbook, _retry

TAB_KOMISI = "Komisi"
BARIS_DATA = 3            # data SKU mulai baris 3 (1=nama toko, 2=sub-header)


def _rupiah(v):
    """'Rp34.041' / '34041' / 'Rp0' / '' -> int rupiah atau None (kalau 0/kosong)."""
    if v is None:
        return None
    s = str(v).strip().replace("Rp", "").replace(".", "").replace(" ", "").replace(",", "")
    if not s:
        return None
    try:
        n = int(float(s))
    except (ValueError, TypeError):
        return None
    return n if n > 0 else None


def _persen(v):
    """'10%' / '8' / '10,5%' -> float (10.0 / 8.0 / 10.5) atau None."""
    if v is None:
        return None
    s = str(v).strip().replace("%", "").replace(",", ".").replace(" ", "")
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def _peta_nama_ke_user():
    """{nama tampilan toko -> username} dari config.SHOP_DATABASE (banding strip)."""
    return {info["name"].strip(): user for user, info in config.SHOP_DATABASE.items()}


# BACA KOMISI — return mapping per toko (lihat docstring modul).
def hasil_komisi():
    ws = buka_workbook().worksheet(TAB_KOMISI)
    nilai = _retry(ws.get_all_values)
    if len(nilai) < BARIS_DATA:
        return {}

    baris_toko = nilai[0]    # baris 1: nama toko di awal blok
    baris_sub = nilai[1]     # baris 2: ['Harga Saat Ini','<persen>%','Harga Jual']
    nama2user = _peta_nama_ke_user()

    # 1) Temukan blok tiap toko: kolom awal (Harga Saat Ini), +1 (%), +2 (Harga Jual).
    blok = []   # list of (username, nama, col_jual, persen)
    for col, sel in enumerate(baris_toko):
        nama = str(sel).strip()
        if nama in nama2user:
            persen = _persen(baris_sub[col + 1]) if col + 1 < len(baris_sub) else None
            blok.append({
                "user": nama2user[nama],
                "nama": nama,
                "col_jual": col + 2,     # kolom 'Harga Jual'
                "persen": persen,
            })

    # 2) Kumpulkan SKU -> harga jual untuk tiap blok (hanya yang terisi > 0).
    hasil = {}
    for b in blok:
        harga = {}
        for row in nilai[BARIS_DATA - 1:]:
            sku = str(row[0]).strip() if row else ""
            if not sku:
                continue
            hj = _rupiah(row[b["col_jual"]]) if b["col_jual"] < len(row) else None
            if hj is not None:
                harga[sku] = hj
        if harga:   # toko "komisi aktif" = ada minimal 1 Harga Jual terisi
            hasil[b["user"]] = {"nama": b["nama"], "persen": b["persen"], "harga": harga}
    return hasil


# Daftar username toko yang punya komisi aktif (untuk dipakai orkestrator).
def toko_komisi_aktif():
    return list(hasil_komisi().keys())


# PROTEKSI HARGA — produk yang harganya TIDAK boleh diubah bot karena dikelola komisi.
# Return { NAMA_TOKO_DISPLAY: {"persen": float|None, "skus": set(SKU UPPER)} } untuk
# toko yang kolom "Harga Jual"-nya terisi. Key = nama tampilan (cocok kolom A Olah Data);
# SKU di-UPPER agar banding case-insensitive (mis. 'zb8' == 'ZB8').
def proteksi_komisi():
    out = {}
    for info in hasil_komisi().values():
        out[info["nama"]] = {
            "persen": info["persen"],
            "skus": {str(s).strip().upper() for s in info["harga"].keys()},
        }
    return out
