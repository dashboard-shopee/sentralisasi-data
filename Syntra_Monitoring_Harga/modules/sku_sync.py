"""
sku_sync.py — Sinkronisasi SKU dari 'Olah Data' -> 'ALL PRODUK'.

Tujuan:
  - SKU yang sudah ada di Olah Data!E (mulai BARIS_AWAL) tapi BELUM terdaftar di
    ALL PRODUK!B akan di-APPEND ke bawah daftar ALL PRODUK:
        kolom A = tanggal ditambahkan (FMT_TANGGAL_SKU, mis. "20/06/26")
        kolom B = SKU
    (kolom C "SKU Induk" & D "Nama Produk" sengaja dibiarkan kosong untuk baris baru.)
  - Tulis timestamp "Terakhir diupdate: ..." ke:
        ALL PRODUK!A1  (refresh, tab ini baru diubah)
        Olah Data!A1   (diminta)

READ/WRITE Sheet seminimal mungkin: 1x baca kolom E, 1x baca kolom B,
1x batch_update untuk append, 2x set A1. Semua via _retry (tahan 429/5xx).
"""
from datetime import datetime
import colorama; colorama.init()
import config
from modules.sheet_util import ambil_worksheet, _retry


def _timestamp():
    return datetime.now().strftime(config.FMT_TIMESTAMP)


def _tanggal():
    return datetime.now().strftime(config.FMT_TANGGAL_SKU)


def _bersih(v):
    """Sel Sheet -> SKU bersih (string, tanpa spasi pinggir)."""
    return str(v).strip() if v is not None else ""


def _kunci(v):
    """Kunci PEMBANDING SKU: case-insensitive + tanpa spasi pinggir.
    Mencegah duplikat gara-gara beda huruf besar/kecil
    (mis. ALL PRODUK 'KLI-1' vs Olah Data 'KLi-1' -> dianggap SAMA)."""
    return _bersih(v).lower()


# SINKRON SKU — kembalikan jumlah SKU baru yang ditambahkan.
def sinkron_sku():
    ws_olah = ambil_worksheet(config.TAB_HARGA)         # "Olah Data"
    ws_all = ambil_worksheet(config.TAB_ALL_PRODUK)     # "ALL PRODUK"

    # 1) SKU sumber dari Olah Data!E (urut, dedup case-insensitive, buang kosong).
    kol_e = _retry(ws_olah.get_values, f"E{config.BARIS_AWAL}:E")
    sumber, seen = [], set()
    for r in kol_e:
        sku = _bersih(r[0]) if r else ""
        if sku and _kunci(sku) not in seen:
            seen.add(_kunci(sku))
            sumber.append(sku)

    # 2) SKU yang SUDAH terdaftar di ALL PRODUK!B (mulai baris data).
    kol_b = _retry(ws_all.get_values, f"B{config.BARIS_AWAL_ALL_PRODUK}:B")
    terdaftar = {_kunci(r[0]) for r in kol_b if r and _bersih(r[0])}

    # 3) SKU baru = ada di sumber, belum di ALL PRODUK (banding case-insensitive).
    baru = [s for s in sumber if _kunci(s) not in terdaftar]

    # get_values memangkas baris kosong di ekor -> baris append berikutnya:
    baris_mulai = config.BARIS_AWAL_ALL_PRODUK + len(kol_b)

    print(colorama.Fore.LIGHTCYAN_EX
          + f" [sinkron SKU] Olah Data: {len(sumber)} SKU unik | "
            f"ALL PRODUK: {len(terdaftar)} terdaftar | BARU: {len(baru)}"
          + colorama.Style.RESET_ALL)

    # 4) Append SKU baru (kolom A = tanggal, B = SKU) dalam 1 batch.
    if baru:
        tanggal = _tanggal()
        body = [[tanggal, s] for s in baru]
        akhir = baris_mulai + len(baru) - 1
        _retry(ws_all.batch_update, [
            {"range": f"A{baris_mulai}:B{akhir}", "values": body},
        ])
        contoh = ", ".join(baru[:5]) + (" ..." if len(baru) > 5 else "")
        print(colorama.Fore.LIGHTGREEN_EX
              + f" [sinkron SKU] +{len(baru)} SKU ke ALL PRODUK baris "
                f"{baris_mulai}-{akhir} (tgl {tanggal}): {contoh}"
              + colorama.Style.RESET_ALL)

    # 5) Timestamp "Terakhir diupdate" di A1 kedua tab.
    ts = _timestamp()
    _retry(ws_all.update_acell, "A1", ts)    # refresh ALL PRODUK!A1
    _retry(ws_olah.update_acell, "A1", ts)   # Olah Data!A1 (diminta)
    print(colorama.Fore.LIGHTCYAN_EX
          + f" [sinkron SKU] A1 di-set: '{ts}' (Olah Data & ALL PRODUK)"
          + colorama.Style.RESET_ALL)

    return len(baru)
