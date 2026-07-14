"""
duplikat_promo.py — Layer 4 (LANGKAH 5).

Promo Toko tidak bisa diperpanjang -> harus dibuat baru (duplikat). Modul ini:
  - baca promo toko yang berjalan (judul, gambar, tanggal berakhir),
  - kalau sisa <= JELANG_EXPIRE_HARI hari sebelum berakhir, buat promo BARU:
      start = waktu berakhir promo lama, durasi = DURASI_PROMO_HARI (maks 180),
      judul + gambar disalin dari promo lama,
  - produk yang didaftarkan = GABUNGAN: item promo lama + harga K terbaru dari Sheet,
  - kalau produk > MAKS_PRODUK_PER_PROMO -> dipecah jadi beberapa promo.

Mode aman: config.DUPLIKAT_PROMO_SIMULASI = True -> cuma log rencana, tidak eksekusi.

✅ Endpoint terverifikasi: create_discount + update_seller_discount_items.
"""
import time
from modules.log_siklus import log
import config
from modules.api_util import api_post
from modules.discount_util import (
    grab_promotion_id, grab_promo_detail, grab_item_promo, ada_promo_belum_mulai,
    grab_promo_apapun_id,
)


def _chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def _tgl(ts):
    return time.strftime("%d/%m/%Y %H:%M", time.localtime(int(ts))) if ts else "-"


# GABUNGAN: item promo lama + harga K terbaru dari Sheet (kalau ada).
def _gabung_item(item_promo, peta_k):
    daftar = []
    for it in item_promo:
        key = (it["item_id"], it["model_id"])
        K = peta_k.get(key)
        harga = (K * config.FAKTOR_HARGA) if (K and K > 0) else it["promotion_price"]
        daftar.append({
            "item_id": it["item_id"], "model_id": it["model_id"],
            "promotion_price": harga, "user_item_limit": 0,
            "status": config.STATUS_AKTIF, "promotion_stock": 0,
        })
    return daftar


# Buat 1 promo + daftarkan produknya (chunk 50). Kembalikan promotion_id baru.
def _buat_promo(session, judul, images, start_time, end_time, grup):
    resp = api_post(
        config.URL_CREATE_PROMO, config.grab_headers(session), session["params"],
        {"discount_id": None, "start_time": start_time, "end_time": end_time,
         "title": judul, "status": 1, "source": 0, "images": images,
         "total_product": len(grup), "global_discount_id": 0, "enable_bidding_nomination": False},
        kunci="data",
    )
    new_pid = resp["data"].get("promotion_id")
    for ch in _chunks(grup, 50):
        api_post(config.URL_UPDATE_HARGA, config.grab_headers(session), session["params"],
                 {"promotion_id": new_pid, "discount_model_list": ch}, kunci="data")
    return new_pid


# Bangun discount_model_list dari Sheet (utk BUAT DARI 0): K terisi, K < harga awal,
# dan sumber harga (kolom N) termasuk yang boleh dirubah (Promo Toko / Harga Awal).
def _item_dari_sheet(baris_sheet):
    daftar = []
    for b in baris_sheet:
        K = b.get("harga_akhir"); H = b.get("harga_awal") or 0
        if b.get("sumber", "") not in config.SUMBER_BOLEH_RUBAH:
            continue
        if K and K > 0 and (not H or K < H):
            daftar.append({
                "item_id": b["item_id"], "model_id": b["model_id"],
                "promotion_price": K * config.FAKTOR_HARGA, "user_item_limit": 0,
                "status": config.STATUS_AKTIF, "promotion_stock": 0,
            })
    return daftar


# BUAT PROMO DARI 0 — saat toko belum punya promo toko aktif (dipakai Langkah 2 & 4).
def buat_promo_dari_nol(shop, session, baris_sheet):
    if not getattr(config, "BUAT_PROMO_DARI_NOL", False):
        log("Promo Toko belum ada (BUAT_PROMO_DARI_NOL=False, lewati).", level="warning", toko=shop, modul="promo_toko")
        return

    # Guard anti-dobel: kalau sudah ada promo pengganti yang belum mulai, jangan bikin lagi.
    if ada_promo_belum_mulai(session, config.NAMA_PROMO):
        log("sudah ada promo (belum mulai), lewati buat baru.", level="warning", toko=shop, modul="promo_toko")
        return

    daftar = _item_dari_sheet(baris_sheet)
    if not daftar:
        log("tidak ada produk siap-promo (K<harga awal). Lewati.", level="warning", toko=shop, modul="promo_toko")
        return

    # images = thumbnail preview (gambar cover produk), BUKAN banner upload -> boleh kosong.
    # Pakai config bila diisi; kalau tidak, coba salin dari promo lama; kalau tidak ada juga,
    # biarkan kosong (Shopee isi otomatis, sama seperti buat manual).
    images = list(config.PROMO_IMAGES or [])
    if not images:
        ref = grab_promo_apapun_id(session)
        if ref:
            det = grab_promo_detail(session, ref) or {}
            images = det.get("images", []) or []

    now = int(time.time())
    start_baru = now + 300                     # mulai ~5 menit dari sekarang
    end_baru = start_baru + config.DURASI_PROMO_HARI * 86400
    judul = config.NAMA_PROMO
    kelompok = list(_chunks(daftar, config.MAKS_PRODUK_PER_PROMO))

    log(f"RENCANA (dari 0): {len(daftar)} produk → {len(kelompok)} promo | mulai {_tgl(start_baru)} s/d {_tgl(end_baru)} | judul '{judul}' | gambar: {len(images)}",
        level="detail", toko=shop, modul="promo_toko")

    if config.DRY_RUN or config.DUPLIKAT_PROMO_SIMULASI:
        log("[SIMULASI] tidak membuat promo (DRY_RUN/simulasi).", level="warning", toko=shop, modul="promo_toko")
        return

    for idx, grup in enumerate(kelompok, start=1):
        judul_grup = judul if idx == 1 else f"{judul} ({idx})"
        try:
            new_pid = _buat_promo(session, judul_grup, images, start_baru, end_baru, grup)
            log(f"promo '{judul_grup}' dibuat (id={new_pid}), {len(grup)} produk.", level="live", toko=shop, modul="promo_toko")
        except Exception as e:
            log(f"GAGAL bikin '{judul_grup}': {e}", level="error", toko=shop, modul="promo_toko")


# PROSES DUPLIKAT PROMO — dipanggil per toko oleh orkestrator.
def proses_duplikat_promo(shop, session, baris_sheet):
    pid = grab_promotion_id(shop, session, config.NAMA_PROMO)
    if not pid:
        # Tidak ada promo toko aktif -> coba BUAT DARI 0.
        return buat_promo_dari_nol(shop, session, baris_sheet)

    detail = grab_promo_detail(session, pid)
    if not detail:
        log("gagal baca detail promo.", level="error", toko=shop, modul="promo_toko")
        return

    end_time = int(detail.get("end_time", 0))
    now = int(time.time())
    sisa_hari = (end_time - now) / 86400

    # Belum waktunya?
    if sisa_hari > config.JELANG_EXPIRE_HARI:
        log(f"belum waktunya duplikat (berakhir {_tgl(end_time)}, sisa {sisa_hari:.1f} hari).", level="detail", toko=shop, modul="promo_toko")
        return

    # Sudah ada promo pengganti (belum mulai)? -> jangan dobel.
    if ada_promo_belum_mulai(session, config.NAMA_PROMO):
        log("sudah ada promo pengganti (belum mulai), lewati.", level="warning", toko=shop, modul="promo_toko")
        return

    # Kumpulkan produk (gabungan promo lama + K sheet).
    item_promo = grab_item_promo(shop, session, pid)
    peta_k = {(b["item_id"], b["model_id"]): b["harga_akhir"]
              for b in baris_sheet if b.get("harga_akhir")}
    daftar = _gabung_item(item_promo, peta_k)
    if not daftar:
        log("promo lama kosong, lewati.", level="warning", toko=shop, modul="promo_toko")
        return

    start_baru = end_time
    end_baru = start_baru + config.DURASI_PROMO_HARI * 86400
    judul = str(detail.get("title", config.NAMA_PROMO)).strip()
    images = detail.get("images", []) or []
    kelompok = list(_chunks(daftar, config.MAKS_PRODUK_PER_PROMO))

    log(f"RENCANA duplikat: {len(daftar)} produk → {len(kelompok)} promo | mulai {_tgl(start_baru)} s/d {_tgl(end_baru)} | judul '{judul}'",
        level="detail", toko=shop, modul="promo_toko")

    if config.DRY_RUN or config.DUPLIKAT_PROMO_SIMULASI:
        log("[SIMULASI] tidak membuat promo (DRY_RUN/simulasi). Set MODE_LIVE=True di config untuk eksekusi nyata.",
            level="warning", toko=shop, modul="promo_toko")
        return

    # EKSEKUSI
    for idx, grup in enumerate(kelompok, start=1):
        judul_grup = judul if idx == 1 else f"{judul} ({idx})"
        new_pid = _buat_promo(session, judul_grup, images, start_baru, end_baru, grup)
        log(f"promo '{judul_grup}' dibuat (id={new_pid}), {len(grup)} produk.", level="live", toko=shop, modul="promo_toko")
