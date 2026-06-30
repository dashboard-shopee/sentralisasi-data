"""
verifikasi_harga.py — Layer 2+5 (LANGKAH 3).

Ambil ULANG produk terkini dari Shopee, lalu perbarui:
  - kolom L = harga yang dimunculkan (promotion_price / origin),
  - kolom N = sumber harga (Promo Toko / Garansi Harga Terbaik / Paket Diskon /
              Harga Awal / dll).
Perbandingan K vs L cukup dilihat dari kolom M (SELISIH, rumus user).
Produk tak ketemu -> kolom N "TIDAK DITEMUKAN".

Penulisan ke Sheet dikumpulkan lalu ditulis SEKALI oleh orkestrator (run.py).
"""
import colorama; colorama.init()
import config
from modules.sheet_util import ambil_worksheet_harga, _retry


# Bangun peta {(item_id, model_id): {"harga":.., "sumber":..}} dari hasil grab_produk.
def peta_dari_baris(rows):
    peta = {}
    for r in rows:   # [toko,item,model,sku,nama_variasi,nama_produk,harga_awal,harga_tampil,sumber]
        peta[(int(r[1]), int(r[2]))] = {
            "harga": int(r[7]),
            "sumber": r[8] if len(r) > 8 else "",
        }
    return peta


# BANDINGKAN — hasilkan list update {range, values} untuk kolom L & N satu toko.
#   peta_diskon    : {(item,model): {harga, sumber}} dari search_product_list (bisa telat update)
#   peta_promo_toko: {(item,model): harga_rupiah} harga promo toko AKTIF (update seketika)
# Kalau produk aktif di promo toko & harganya <= harga tampil dari grab (atau grab telat),
# pakai data promo toko -> tahan terhadap jeda propagasi daftar produk.
def bandingkan(shop, baris_sheet, peta_diskon, peta_promo_toko=None):
    peta_promo_toko = peta_promo_toko or {}
    kol_l = config.KOL["harga_diskon"]
    kol_n = config.KOL["keterangan"]
    updates = []
    n = 0
    for b in baris_sheet:
        n += 1
        row = b["row"]
        key = (int(b["item_id"]), int(b["model_id"]))
        info = peta_diskon.get(key)
        p_toko = peta_promo_toko.get(key)        # harga promo toko aktif (rupiah) / None
        l_grab = info["harga"] if info else None
        src_grab = info["sumber"] if info else ""

        # Tentukan L & sumber final (utamakan data promo toko bila menang / grab telat).
        if p_toko is not None and (l_grab is None or p_toko <= l_grab):
            harga, sumber = p_toko, "Promo Toko"
        elif l_grab is not None:
            harga, sumber = l_grab, src_grab
        else:
            updates.append({"range": f"{kol_n}{row}", "values": [["TIDAK DITEMUKAN"]]})
            print(colorama.Fore.RED
                  + f"[verifikasi] [{shop}] [{n}] - {key[0]}/{key[1]} TIDAK DITEMUKAN"
                  + colorama.Style.RESET_ALL)
            continue

        updates.append({"range": f"{kol_l}{row}", "values": [[harga]]})
        updates.append({"range": f"{kol_n}{row}", "values": [[sumber]]})

        K = b["harga_akhir"]
        cocok = (K is not None and harga == K)
        warna = colorama.Fore.GREEN if cocok else colorama.Fore.YELLOW
        print(warna
              + f"[verifikasi] [{shop}] [{n}] - {key[0]}/{key[1]} L={config.fmt_angka(harga)} "
              + f"({sumber})" + ("" if cocok else " [K beda]")
              + colorama.Style.RESET_ALL)
    return updates


# TULIS VERIFIKASI — tulis semua update L & N dalam 1 request.
def tulis_verifikasi(updates):
    if not updates:
        print(colorama.Fore.YELLOW + "[verifikasi] - tidak ada update." + colorama.Style.RESET_ALL)
        return
    ws = ambil_worksheet_harga()
    _retry(ws.batch_update, updates)
    print(colorama.Fore.GREEN
          + f"[verifikasi] - {len(updates)} sel diperbarui (L & N)."
          + colorama.Style.RESET_ALL)
