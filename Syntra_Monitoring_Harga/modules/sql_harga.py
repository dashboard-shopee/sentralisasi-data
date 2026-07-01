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
         harga_awal, harga_tampil, sumber_harga, stok, diperbarui_pada)
    values
        (:toko, :item_id, :model_id, :sku, :nama_variasi, :nama_produk,
         :harga_awal, :harga_tampil, :sumber, :stok, now())
    on conflict (toko, item_id, model_id) do update set
        sku = excluded.sku,
        nama_variasi = excluded.nama_variasi,
        nama_produk = excluded.nama_produk,
        harga_awal = excluded.harga_awal,
        harga_tampil = excluded.harga_tampil,
        sumber_harga = excluded.sumber_harga,
        stok = excluded.stok,
        diperbarui_pada = now()
""")


def _baris_ke_param(r):
    # r = [toko, item_id, model_id, sku, nama_variasi, nama_produk, harga_awal, harga_tampil, sumber, stok]
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
        "stok": (r[9] if len(r) > 9 and r[9] is not None else 0),
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


_SQL_KONTEKS_INSERT = text("""
    insert into harga_promo_konteks
        (toko, item_id, model_id, jenis, campaign_type, promotion_id,
         harga_promo, status, stok, mulai, berakhir, diperbarui_pada)
    values
        (:toko, :item_id, :model_id, :jenis, :campaign_type, :promotion_id,
         :harga_promo, :status, :stok, :mulai, :berakhir, now())
    on conflict (toko, item_id, model_id, jenis, promotion_id) do update set
        campaign_type = excluded.campaign_type,
        harga_promo = excluded.harga_promo,
        status = excluded.status,
        stok = excluded.stok,
        mulai = excluded.mulai,
        berakhir = excluded.berakhir,
        diperbarui_pada = now()
""")


def isi_harga_diskon_kosong():
    """Isi harga_all_produk.harga_diskon = MODE(harga_tampil, abaikan 0) HANYA utk SKU
    yang harga_diskon-nya masih KOSONG (<=0) TAPI harga real antar toko sudah ada.
    Nilai yg sudah terisi TIDAK ditimpa (stabil). custom_harga_diskon tetap prioritas
    saat dibaca. Dipanggil tiap Fase 1 grab. Return jumlah sku terisi."""
    with get_engine().begin() as c:
        n = c.execute(text("""
            with md as (
                select sku, mode() within group (order by harga_tampil) as m
                from harga_olah_data where harga_tampil > 0 group by sku
            )
            update harga_all_produk ap
            set harga_diskon = md.m, diperbarui_pada = now()
            from md
            where upper(ap.sku) = upper(md.sku)
              and md.m > 0
              and coalesce(ap.harga_diskon, 0) <= 0
        """)).rowcount
    return n


def simpan_konteks(toko, konteks):
    """Snapshot keikutsertaan promo 1 toko ke harga_promo_konteks.
    Hapus baris lama toko ini lalu insert ulang -> selalu mencerminkan kondisi
    terkini (promo yang sudah ditinggalkan variasi otomatis hilang). Return jumlah."""
    with get_engine().begin() as c:
        c.execute(text("delete from harga_promo_konteks where toko = :t"), {"t": toko})
        if not konteks:
            return 0
        # dedup dalam batch (PK: toko+item+model+jenis+promotion_id)
        seen = {}
        for k in konteks:
            key = (k["toko"], k["item_id"], k["model_id"], k["jenis"], k.get("promotion_id", ""))
            seen[key] = {
                "toko": k["toko"],
                "item_id": int(k["item_id"]),
                "model_id": int(k["model_id"] or 0),
                "jenis": k["jenis"],
                "campaign_type": k.get("campaign_type"),
                "promotion_id": str(k.get("promotion_id", "") or ""),
                "harga_promo": k.get("harga_promo", 0) or 0,
                "status": k.get("status"),
                "stok": k.get("stok", 0) or 0,
                "mulai": k.get("mulai"),
                "berakhir": k.get("berakhir"),
            }
        params = list(seen.values())
        c.execute(_SQL_KONTEKS_INSERT, params)
    return len(params)


# ── FASE 2 (rubah harga) — baca target dari SQL, tulis alasan balik ──
# TARGET = harga_pancing bila ADA (>0), kalau tidak -> "Harga Diskon" (per-SKU, TERSIMPAN).
#   - harga_pancing efektif = coalesce(custom_harga_pancing, harga_pancing)
#   - Harga Diskon efektif   = coalesce(custom_harga_diskon, harga_diskon)  [STORED, stabil]
#   harga_diskon di-inisialisasi dari mode & diisi tiap grab utk yg kosong (isi_harga_diskon_kosong).
#   custom_harga_diskon = override manual (prioritas). Nilai pancing/diskon di-SET dari dashboard.
# Dibandingkan dengan "Harga Real" (harga_tampil hasil Fase 1). Beda -> dirubah.
# Join by SKU (harga_all_produk.sku <-> harga_olah_data.sku). Tidak ada 'K'/sheet/mode-live lagi.
_SQL_BARIS_RUBAH = text("""
    select ho.item_id, ho.model_id, ho.sku, ho.harga_awal, ho.harga_tampil,
           ho.sumber_harga, ho.stok,
           coalesce(
               nullif(coalesce(ap.custom_harga_pancing, ap.harga_pancing), 0),   -- pancing (kalau ada)
               nullif(coalesce(ap.custom_harga_diskon, ap.harga_diskon), 0)      -- else Harga Diskon (stored)
           ) as target
    from harga_olah_data ho
    left join harga_all_produk ap on upper(ap.sku) = upper(ho.sku)
    where ho.toko = :t
""")


def baca_baris_rubah(toko):
    """Baris siap-proses update_harga utk 1 toko (by NAMA toko). row = (item_id, model_id).
    harga_akhir = TARGET (pancing kalau ada, else Harga Diskon), harga_real = harga tampil (Fase 1)."""
    with get_engine().connect() as c:
        rows = c.execute(_SQL_BARIS_RUBAH, {"t": toko}).fetchall()
    out = []
    for r in rows:
        out.append({
            "row": (int(r.item_id), int(r.model_id)),   # kunci alasan
            "item_id": int(r.item_id),
            "model_id": int(r.model_id),
            "sku": (r.sku or "").strip(),
            "harga_awal": int(r.harga_awal or 0),
            "harga_akhir": int(r.target or 0),          # TARGET = pancing/Harga Diskon
            "harga_real": int(r.harga_tampil or 0),     # Harga Real (pembanding)
            "sumber": r.sumber_harga or "",
            "stok": int(r.stok or 0),
        })
    return out


def tulis_alasan(toko, alasan):
    """alasan = {(item_id, model_id): teks} -> tulis kolom alasan harga_olah_data."""
    if not alasan:
        return 0
    params = [{"t": toko, "i": int(k[0]), "m": int(k[1]), "a": (v or None)}
              for k, v in alasan.items()]
    with get_engine().begin() as c:
        c.execute(text("""update harga_olah_data set alasan = :a, diperbarui_pada = now()
                          where toko = :t and item_id = :i and model_id = :m"""), params)
    return len(params)


def baca_proteksi_komisi(username_toko):
    """SKU yang komisi affiliate-nya AKTIF utk 1 toko (jangan diubah harganya).
    Komisi dianggap AKTIF hanya bila kolom 'Harga Jual' (harga_jual) toko itu TERISI (>0);
    kalau kosong -> toko tsb tidak mengaktifkan komisi utk sku itu (harga boleh dirubah)."""
    with get_engine().connect() as c:
        rows = c.execute(text("""select sku from harga_komisi_toko
                                 where username_toko = :u and coalesce(harga_jual,0) > 0"""),
                         {"u": username_toko}).fetchall()
    return {(r.sku or "").strip().upper() for r in rows if r.sku}


# ── FASE 2A: stok habis (takedown), HPP guard, state & audit ──
def baca_stok_habis(toko, jenis="Promo Toko"):
    """Set (item_id, model_id) variasi STOK <= 0 yg masih nyangkut promo `jenis`
    di harga_promo_konteks (kandidat takedown). item stok-0 tidak ada di
    harga_olah_data (difilter grab), jadi sumbernya konteks."""
    with get_engine().connect() as c:
        rows = c.execute(text("""
            select item_id, model_id from harga_promo_konteks
            where toko = :t and jenis = :j and coalesce(stok,0) <= 0
        """), {"t": toko, "j": jenis}).fetchall()
    return {(int(r.item_id), int(r.model_id)) for r in rows}


def baca_promo_item(toko, kunci_set=None):
    """{(item_id, model_id): set(jenis)} keikutsertaan promo per variasi dari konteks.
    Dipakai Fase 2B: sebelum ubah harga dasar, tahu promo apa saja yg nyangkut
    (Promo Toko / Paket Diskon / Garansi / Flash Sale / Campaign / ...)."""
    with get_engine().connect() as c:
        rows = c.execute(text("""select item_id, model_id, jenis
                                 from harga_promo_konteks where toko = :t"""),
                         {"t": toko}).fetchall()
    out = {}
    for r in rows:
        key = (int(r.item_id), int(r.model_id))
        if kunci_set is not None and key not in kunci_set:
            continue
        out.setdefault(key, set()).add(r.jenis)
    return out


def baca_hpp_per_sku(skus):
    """{SKU_UPPER: hpp} dari erp_sku_list utk daftar sku (guard 'jangan jual < modal')."""
    skus = [s.strip() for s in skus if s and s.strip()]
    if not skus:
        return {}
    with get_engine().connect() as c:
        rows = c.execute(text("""
            select upper(sku) sku, hpp from erp_sku_list
            where hpp is not null and hpp > 0 and upper(sku) = any(:skus)
        """), {"skus": [s.upper() for s in skus]}).fetchall()
    return {r.sku: float(r.hpp) for r in rows}


def catat_takedown_stok(toko, entri):
    """Upsert state takedown stok-habis. entri = list of
    {item_id, model_id, jenis, harga_terakhir}. waktu_register di-reset NULL
    (baris ini kembali berstatus 'lagi di-takedown')."""
    if not entri:
        return 0
    params = [{
        "t": toko, "i": int(e["item_id"]), "m": int(e["model_id"]),
        "j": e.get("jenis", "Promo Toko"), "h": e.get("harga_terakhir", 0) or 0,
    } for e in entri]
    with get_engine().begin() as c:
        c.execute(text("""
            insert into harga_stok_takedown
                (toko, item_id, model_id, jenis, harga_terakhir, waktu_takedown, waktu_register)
            values (:t, :i, :m, :j, :h, now(), null)
            on conflict (toko, item_id, model_id, jenis) do update set
                harga_terakhir = excluded.harga_terakhir,
                waktu_takedown = now(),
                waktu_register = null
        """), params)
    return len(params)


def tandai_register_ulang(toko, kunci):
    """Tandai variasi sudah di-register ulang (stok kembali). kunci = list (item_id, model_id)."""
    if not kunci:
        return 0
    params = [{"t": toko, "i": int(k[0]), "m": int(k[1])} for k in kunci]
    with get_engine().begin() as c:
        c.execute(text("""update harga_stok_takedown set waktu_register = now()
                          where toko = :t and item_id = :i and model_id = :m
                            and waktu_register is null"""), params)
    return len(params)


def baca_takedown_aktif(toko):
    """Set (item_id, model_id) yg SEDANG di-takedown karena stok habis (belum di-register ulang)."""
    with get_engine().connect() as c:
        rows = c.execute(text("""select item_id, model_id from harga_stok_takedown
                                 where toko = :t and waktu_register is null"""),
                         {"t": toko}).fetchall()
    return {(int(r.item_id), int(r.model_id)) for r in rows}


def catat_riwayat(entri):
    """Audit ke harga_riwayat_update. entri = list of
    {sku, aksi, nilai_lama, nilai_baru, username}."""
    if not entri:
        return 0
    params = [{
        "sku": (e.get("sku") or "-"), "aksi": e.get("aksi", ""),
        "lama": e.get("nilai_lama"), "baru": e.get("nilai_baru"),
        "user": e.get("username", "bot-harga"),
    } for e in entri]
    with get_engine().begin() as c:
        c.execute(text("""insert into harga_riwayat_update
                          (sku, aksi, nilai_lama, nilai_baru, username)
                          values (:sku, :aksi, :lama, :baru, :user)"""), params)
    return len(params)
