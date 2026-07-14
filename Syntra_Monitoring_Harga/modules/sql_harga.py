"""modules/sql_harga.py — pengganti sheet_data/sheet_util: baca/tulis SQL (harga_olah_data).

FASE 1: simpan hasil grab produk Shopee ke harga_olah_data (upsert).
Kolom yang diisi grab: toko, item_id, model_id, sku, nama_variasi, nama_produk,
harga_awal, harga_tampil, sumber_harga. Kolom lain (ptag, harga_diskon_db,
harga_pancing, harga_akhir_target, selisih, alasan) = milik dashboard/user ->
TIDAK ditimpa (dipertahankan saat upsert).
"""
import json
from sqlalchemy import text
from modules.db import get_engine
import config

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
    """Upsert list baris hasil grab_produk ke harga_olah_data. Return jumlah baris.
    GUARD: baris toko di luar 10 toko resmi (sub-akun lain) DITOLAK — tidak ditulis."""
    if not rows:
        return 0
    resmi = config.nama_toko_resmi()
    rows = [r for r in rows if (r[0] in resmi)]
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


def db_now():
    """Timestamp now() dari DB (bukan jam app) — buat penanda 'sebelum grab' yg konsisten
    sama diperbarui_pada yg diset now() waktu upsert. Hindari skew jam app vs DB."""
    with get_engine().connect() as c:
        return c.execute(text("select now()")).scalar()


def nolkan_stok_habis(toko, ref_ts):
    """Set stok=0 utk baris harga_olah_data toko ini yg TAK ke-refresh grab barusan
    (diperbarui_pada < ref_ts = variasi jatuh STOK-0, ga muncul lagi di grab berstok).
    AKAR voucher/paket poison: baris stok-0 basi bikin Shopee tolak SELURUH voucher.
    HANYA panggil abis grab LENGKAP (lengkap=True). Return jumlah baris di-nol-in."""
    with get_engine().begin() as c:
        r = c.execute(text("""update harga_olah_data set stok = 0, diperbarui_pada = now()
                              where toko = :t and stok > 0 and diperbarui_pada < :ref"""),
                      {"t": toko, "ref": ref_ts})
        return r.rowcount or 0


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
                from harga_olah_data
                where harga_tampil > 0 and toko = any(:resmi)   -- hanya 10 toko resmi
                group by sku
            )
            update harga_all_produk ap
            set harga_diskon = md.m, diperbarui_pada = now()
            from md
            where upper(ap.sku) = upper(md.sku)
              and md.m > 0
              and coalesce(ap.harga_diskon, 0) <= 0
        """), {"resmi": list(config.nama_toko_resmi())}).rowcount
    return n


def simpan_konteks(toko, konteks):
    """Snapshot keikutsertaan promo 1 toko ke harga_promo_konteks.
    Hapus baris lama toko ini lalu insert ulang -> selalu mencerminkan kondisi
    terkini (promo yang sudah ditinggalkan variasi otomatis hilang). Return jumlah.
    GUARD: toko di luar 10 toko resmi (sub-akun lain) DITOLAK."""
    if not config.is_toko_resmi(toko):
        return 0
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
        # diproses_pada HANYA bump kalau alasan BERUBAH (kalau program tak mengubah baris,
        # waktunya tetap). diperbarui_pada tetap jalan seperti biasa.
        c.execute(text("""update harga_olah_data set
                              diproses_pada = case when coalesce(alasan,'') <> coalesce(:a,'') then now() else diproses_pada end,
                              alasan = :a,
                              diperbarui_pada = now()
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
    """Set (item_id, model_id) variasi STOK <= 0 yg masih nyangkut promo di
    harga_promo_konteks (kandidat takedown). jenis=None -> SEMUA jenis. item stok-0
    tidak ada di harga_olah_data (difilter grab), jadi sumbernya konteks."""
    sql = "select item_id, model_id from harga_promo_konteks where toko = :t and coalesce(stok,0) <= 0"
    params = {"t": toko}
    if jenis is not None:
        sql += " and jenis = :j"
        params["j"] = jenis
    with get_engine().connect() as c:
        rows = c.execute(text(sql), params).fetchall()
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


def verifikasi_toko(toko):
    """FASE 3: banding Harga Real (harga_tampil terkini, HARUS sudah re-grab) vs
    Target (pancing/Harga Diskon) per variasi 1 toko, tulis verdict ke kolom `alasan`:
      - target kosong           -> alasan tidak diubah (biarkan apa adanya)
      - real == target          -> '' (terverifikasi/sesuai)
      - real != target          -> 'Belum sesuai: real X != diskon Y (sumber Z)'
    Return (n_sesuai, n_belum, n_tanpa_target)."""
    with get_engine().begin() as c:
        # tulis verdict langsung via SQL (target dihitung sama seperti _SQL_BARIS_RUBAH)
        c.execute(text("""
            with tgt as (
                select ho.item_id, ho.model_id, ho.harga_tampil, ho.sumber_harga,
                       coalesce(
                           nullif(coalesce(ap.custom_harga_pancing, ap.harga_pancing), 0),
                           nullif(coalesce(ap.custom_harga_diskon, ap.harga_diskon), 0)
                       ) as target
                from harga_olah_data ho
                left join harga_all_produk ap on upper(ap.sku) = upper(ho.sku)
                where ho.toko = :t
            ),
            blk as (
                -- promo penindih per ITEM yg BENAR-BENAR AKTIF (selain Promo Toko).
                -- ⚠️ WAJIB filter status='aktif': Paket Diskon yg NONAKTIF tidak ngeblok apa pun,
                --    dulu tanpa filter ini 326 item salah dicap "keblok Paket Diskon" (padahal mati).
                select item_id, string_agg(distinct jenis, ', ' order by jenis) j
                from harga_promo_konteks
                where toko = :t and jenis <> 'Promo Toko' and coalesce(status,'') = 'aktif'
                group by item_id
            ),
            v as (
                select t.item_id, t.model_id, t.target, t.harga_tampil,
                    case when t.harga_tampil = t.target then ''
                         else 'Belum sesuai'
                              || case when b.j is not null then ' (keblok: ' || b.j || ')'
                                      else ' (sumber ' || coalesce(nullif(t.sumber_harga,''),'?') || ')' end
                              || ': real ' || t.harga_tampil::bigint
                              || ' != diskon ' || t.target::bigint
                    end as verdict
                from tgt t left join blk b on b.item_id = t.item_id
                where coalesce(t.target,0) > 0
            )
            update harga_olah_data ho set
                diproses_pada = case when v.verdict is distinct from ho.alasan then now() else ho.diproses_pada end,
                alasan = v.verdict,
                selisih = v.target - ho.harga_tampil,
                diperbarui_pada = now()
            from v
            where ho.toko = :t and ho.item_id = v.item_id and ho.model_id = v.model_id
        """), {"t": toko})
        # hitung ringkasan
        r = c.execute(text("""
            with tgt as (
                select ho.harga_tampil, coalesce(
                           nullif(coalesce(ap.custom_harga_pancing, ap.harga_pancing), 0),
                           nullif(coalesce(ap.custom_harga_diskon, ap.harga_diskon), 0)) as target
                from harga_olah_data ho
                left join harga_all_produk ap on upper(ap.sku) = upper(ho.sku)
                where ho.toko = :t)
            select count(*) filter (where coalesce(target,0) > 0 and harga_tampil = target) sesuai,
                   count(*) filter (where coalesce(target,0) > 0 and harga_tampil <> target) belum,
                   count(*) filter (where coalesce(target,0) <= 0) tanpa_target
            from tgt
        """), {"t": toko}).one()
    return int(r.sesuai), int(r.belum), int(r.tanpa_target)


# ══════════════════════════════════════════════════════════════════
#  FASE 1 (PENGUMPUL FAKTA) — writer tabel fakta per-program.
#  Pola SNAPSHOT: hapus baris toko lalu insert ulang -> selalu terkini
#  (fakta yg sudah hilang otomatis kebuang). READ-ONLY ke Shopee.
#  GUARD: toko di luar 10 toko resmi ditolak.
# ══════════════════════════════════════════════════════════════════

def _snapshot_toko(tabel, toko, kolom, baris, pk, jsonb_cols=()):
    """Delete baris toko lalu insert ulang. kolom = urutan kolom (tanpa diperbarui_pada).
    baris = list dict (key = kolom). pk = tuple kolom PK (buat dedup dalam batch).
    jsonb_cols = kolom yang di-cast ke jsonb (nilainya string JSON / None)."""
    if not config.is_toko_resmi(toko):
        return 0
    # dedup dalam batch (PK tak boleh dobel di 1 insert)
    seen = {}
    for b in baris:
        seen[tuple(b[k] for k in pk)] = b
    baris = list(seen.values())
    with get_engine().begin() as c:
        c.execute(text(f"delete from {tabel} where toko = :t"), {"t": toko})
        if not baris:
            return 0
        cols = ", ".join(kolom)
        vals = ", ".join((f"cast(:{k} as jsonb)" if k in jsonb_cols else f":{k}") for k in kolom)
        c.execute(text(f"insert into {tabel} ({cols}, diperbarui_pada) values ({vals}, now())"), baris)
    return len(baris)


def simpan_fakta_garansi(toko, baris):
    """baris = list {item_id, model_id, bid_id, cspu_id, current_price, bid_price, best_price,
    floor_price(Terbaik), ceiling_price(Program), stok}."""
    return _snapshot_toko(
        "harga_fakta_garansi", toko,
        ["toko", "item_id", "model_id", "bid_id", "cspu_id", "current_price", "bid_price",
         "best_price", "floor_price", "ceiling_price", "stok"],
        [{"toko": toko, **b} for b in baris],
        pk=("toko", "item_id", "model_id"))


def simpan_fakta_campaign_sesi(toko, baris):
    """baris = list {campaign_id, session_id, campaign_name, session_name,
    session_start, session_end, nomination_end} (waktu = ISO string / None)."""
    return _snapshot_toko(
        "harga_fakta_campaign_sesi", toko,
        ["toko", "campaign_id", "session_id", "campaign_name", "session_name",
         "session_start", "session_end", "nomination_end"],
        [{"toko": toko, **b} for b in baris],
        pk=("toko", "session_id"))


def simpan_fakta_campaign_item(toko, baris):
    """baris = list {session_id, item_id, model_id, nomination_id, nominate_status, campaign_price}."""
    return _snapshot_toko(
        "harga_fakta_campaign_item", toko,
        ["toko", "session_id", "item_id", "model_id", "nomination_id", "nominate_status", "campaign_price"],
        [{"toko": toko, **b} for b in baris],
        pk=("toko", "session_id", "item_id", "model_id"))


def simpan_fakta_flash_sesi(toko, baris):
    """baris = list {flash_sale_id, status, timeslot_id, start_time, end_time, item_count}."""
    return _snapshot_toko(
        "harga_fakta_flash_sesi", toko,
        ["toko", "flash_sale_id", "status", "timeslot_id", "start_time", "end_time", "item_count"],
        [{"toko": toko, **b} for b in baris],
        pk=("toko", "flash_sale_id"))


def simpan_fakta_flash_item(toko, baris):
    """baris = list {flash_sale_id, item_id, model_id, status, promotion_price, stock}."""
    return _snapshot_toko(
        "harga_fakta_flash_item", toko,
        ["toko", "flash_sale_id", "item_id", "model_id", "status", "promotion_price", "stock"],
        [{"toko": toko, **b} for b in baris],
        pk=("toko", "flash_sale_id", "item_id", "model_id"))


def simpan_fakta_voucher(toko, baris):
    """baris = list {voucher_id, code, name, discount, min_price, tipe,
    start_time, end_time, status, fe_status, item_scope(list/None)}. item_scope -> jsonb."""
    for b in baris:
        sc = b.get("item_scope")
        b["item_scope"] = json.dumps(sc) if sc else None
    return _snapshot_toko(
        "harga_fakta_voucher", toko,
        ["toko", "voucher_id", "code", "name", "discount", "min_price", "tipe",
         "start_time", "end_time", "status", "fe_status", "item_scope"],
        [{"toko": toko, **b} for b in baris],
        pk=("toko", "voucher_id"), jsonb_cols=("item_scope",))


def simpan_fakta_komisi(toko, baris):
    """baris = list {item_id, commission_id, persen, status, item_name} — komisi AFFILIATE
    AKTIF di Shopee (grab BROWSER `komisi_grab`). Snapshot per toko (delete+insert).
    toko = NAMA display (konsisten fakta lain). Kosong -> tabel toko dikosongin (hati2 panggil
    hanya kalau grab sukses)."""
    return _snapshot_toko(
        "harga_fakta_komisi", toko,
        ["toko", "item_id", "commission_id", "persen", "status", "item_name"],
        [{"toko": toko, **b} for b in baris],
        pk=("toko", "item_id"))


def simpan_fakta_garansi_nom(toko, baris):
    """baris = list {item_id, model_id, kategori, item_name, model_name, floor, ceiling, stok,
    bid_id, bid_status} — 3 kategori nominasi garansi (rekomendasi/terbaik/perlu_ditinjau).
    Snapshot per toko. Kosong -> tabel toko dikosongin (panggil hanya kalau grab sukses)."""
    return _snapshot_toko(
        "harga_fakta_garansi_nom", toko,
        ["toko", "item_id", "model_id", "kategori", "item_name", "model_name",
         "floor", "ceiling", "stok", "bid_id", "bid_status"],
        [{"toko": toko, **b} for b in baris],
        pk=("toko", "item_id", "model_id", "kategori"))


def simpan_fakta_paket(toko, baris):
    """baris = list {bundle_deal_id, name, status, start_time, end_time, tiers(list/None),
    items(list/None), item_count(int)}."""
    for b in baris:
        tr = b.get("tiers")
        b["tiers"] = json.dumps(tr) if tr else None
        it = b.get("items")
        b["items"] = json.dumps(it) if it else None
        b.setdefault("item_count", None)
    return _snapshot_toko(
        "harga_fakta_paket", toko,
        ["toko", "bundle_deal_id", "name", "status", "start_time", "end_time", "tiers", "items", "item_count"],
        [{"toko": toko, **b} for b in baris],
        pk=("toko", "bundle_deal_id"), jsonb_cols=("tiers", "items"))


def baca_item_tanpa_kategori(toko, limit):
    """item_id (unik) di 1 toko yg BELUM punya kategori (incremental grab). Return list int."""
    with get_engine().connect() as c:
        rows = c.execute(text("""
            select distinct ho.item_id
            from harga_olah_data ho
            left join harga_produk_kategori k on k.toko = ho.toko and k.item_id = ho.item_id
            where ho.toko = :t and k.item_id is null
            limit :lim
        """), {"t": toko, "lim": int(limit)}).fetchall()
    return [int(r.item_id) for r in rows]


def simpan_kategori(toko, baris):
    """UPSERT kategori per item. baris = list {item_id, kategori_id, leaf, full}.
    GUARD: toko di luar 10 toko resmi ditolak."""
    if not config.is_toko_resmi(toko) or not baris:
        return 0
    params = [{"t": toko, "i": int(b["item_id"]), "kid": b.get("kategori_id"),
               "leaf": b.get("leaf"), "full": b.get("full")} for b in baris]
    with get_engine().begin() as c:
        c.execute(text("""
            insert into harga_produk_kategori
                (toko, item_id, kategori_id, kategori_leaf, kategori_full, diperbarui_pada)
            values (:t, :i, :kid, :leaf, :full, now())
            on conflict (toko, item_id) do update set
                kategori_id = excluded.kategori_id,
                kategori_leaf = excluded.kategori_leaf,
                kategori_full = excluded.kategori_full,
                diperbarui_pada = now()
        """), params)
    return len(params)


def simpan_fakta_promo_toko(toko, baris):
    """baris = list {promotion_id, nama, status, mulai, berakhir, item_count} (waktu ISO/None)."""
    return _snapshot_toko(
        "harga_fakta_promo_toko", toko,
        ["toko", "promotion_id", "nama", "status", "mulai", "berakhir", "item_count"],
        [{"toko": toko, **b} for b in baris],
        pk=("toko", "promotion_id"))


def simpan_fakta_promo_toko_item(toko, baris):
    """baris = list {promotion_id, item_id, model_id, harga_promo}."""
    return _snapshot_toko(
        "harga_fakta_promo_toko_item", toko,
        ["toko", "promotion_id", "item_id", "model_id", "harga_promo"],
        [{"toko": toko, **b} for b in baris],
        pk=("toko", "promotion_id", "item_id", "model_id"))


def prune_fakta_yatim(maks_umur_hari=35):
    """Housekeeping (tier bulanan): buang baris fakta yg TIDAK ke-refresh > maks_umur_hari
    (mis. toko/sesi yg sudah hilang). Aman: baris yg masih di-grab rutin selalu fresh.
    Return total baris terhapus."""
    tabel = ["harga_fakta_garansi", "harga_fakta_campaign_sesi", "harga_fakta_campaign_item",
             "harga_fakta_flash_sesi", "harga_fakta_flash_item", "harga_fakta_voucher",
             "harga_fakta_paket", "harga_fakta_promo_toko", "harga_fakta_promo_toko_item"]
    total = 0
    with get_engine().begin() as c:
        for t in tabel:
            total += c.execute(
                text(f"delete from {t} where diperbarui_pada < now() - (:d || ' days')::interval"),
                {"d": int(maks_umur_hari)}).rowcount
    return total


# ══════════════════════════════════════════════════════════════════
#  FASE 2 (MASALAH+SOLUSI) — reader pendukung diagnosa harga poin 1-4.
# ══════════════════════════════════════════════════════════════════

def baca_penjualan_per_hari(item_ids):
    """{item_id: rata2 unit TERJUAL per hari (30 hari terakhir)} dari fact_penjualan
    (Shopee — produk_id = item_id; metrik unit_pesanan). BUKAN data ERP."""
    ids = [int(i) for i in item_ids if i]
    if not ids:
        return {}
    with get_engine().connect() as c:
        rows = c.execute(text("""
            select produk_id item_id, sum(coalesce(unit_pesanan,0))::numeric / 30.0 per_hari
            from fact_penjualan
            where periode = 'harian'
              and periode_mulai >= now() - interval '30 days'
              and produk_id = any(:ids)
            group by produk_id
        """), {"ids": ids}).fetchall()
    return {int(r.item_id): float(r.per_hari) for r in rows}


def baca_stok_per_item(toko):
    """{item_id: stok} per PRODUK (max stok antar variasi) dari harga_olah_data. Buat kriteria
    provisioning campaign/flash (stok > ambang)."""
    with get_engine().connect() as c:
        rows = c.execute(text("select item_id, max(stok) stok from harga_olah_data where toko=:t group by item_id"),
                         {"t": toko}).fetchall()
    return {int(r.item_id): int(r.stok or 0) for r in rows}


def baca_promo_detail(toko):
    """{(item_id, model_id): [{jenis, harga_promo, status, stok}]} — SEMUA promo yg variasi
    ikuti (dari konteks, di-grab per-jam). Dipakai Fase 2 buat cek takedown per-promo."""
    with get_engine().connect() as c:
        rows = c.execute(text("""select item_id, model_id, jenis, harga_promo, status, stok
                                 from harga_promo_konteks where toko = :t"""), {"t": toko}).fetchall()
    out = {}
    for r in rows:
        out.setdefault((int(r.item_id), int(r.model_id)), []).append({
            "jenis": r.jenis, "harga_promo": int(r.harga_promo or 0),
            "status": r.status, "stok": int(r.stok or 0),
        })
    return out


def baca_biaya_sku(skus):
    """{SKU_UPPER: {hpp, pct, biaya}} komponen biaya per SKU — buat hitung margin di harga MANA PUN:
    margin(harga) = 1 - pct - (hpp + biaya)/harga. Rumus & basis IDENTIK kolom margin dashboard
    (kalkulator_settings + erp_sku_list.hpp + erp_shopee_metrics)."""
    ss = [s.strip().upper() for s in skus if s and s.strip()]
    if not ss:
        return {}
    with get_engine().connect() as c:
        rows = c.execute(text("""
            with kalk as (
              select
                coalesce((select value::numeric from kalkulator_settings where key='batch_packing_fee'),400) packing_fee,
                coalesce((select value::numeric from kalkulator_settings where key='batch_service_fee'),1250) service_fee,
                coalesce((select value::numeric from kalkulator_settings where key='batch_admin_fee_pct'),0.16)
                 + coalesce((select value::numeric from kalkulator_settings where key='batch_discount_ads_pct'),0.06)
                 + coalesce((select value::numeric from kalkulator_settings where key='batch_salary_pct'),0.08)
                 + coalesce((select value::numeric from kalkulator_settings where key='batch_commission_pct'),0.0) total_pct_biaya)
            select upper(h.sku) sku_u, coalesce(e.hpp,0)::numeric hpp, k.total_pct_biaya pct,
              (k.packing_fee + (case when coalesce(sm.total_qty,0) > 0
                 then k.service_fee * coalesce(sm.total_orders,0) / sm.total_qty else k.service_fee end))::numeric biaya
            from harga_all_produk h
            left join erp_sku_list e on h.sku = e.sku
            left join erp_shopee_metrics sm on h.sku = sm.sku
            cross join kalk k
            where upper(h.sku) = any(:skus)
        """), {"skus": ss}).fetchall()
    return {r.sku_u: {"hpp": float(r.hpp), "pct": float(r.pct), "biaya": float(r.biaya)} for r in rows}


def baca_garansi_best(toko):
    """{(item_id, model_id): {best(=Terbaik), terbaik, program, bid_id}} dari fakta garansi.
    best = alias terbaik (kompat konsumer lama). terbaik=floor_price · program=ceiling_price."""
    with get_engine().connect() as c:
        rows = c.execute(text("""select item_id, model_id, best_price, floor_price, ceiling_price, bid_id
                                 from harga_fakta_garansi where toko = :t"""), {"t": toko}).fetchall()
    out = {}
    for r in rows:
        terbaik = int(r.floor_price or r.best_price or 0)
        out[(int(r.item_id), int(r.model_id))] = {
            "best": terbaik, "terbaik": terbaik, "program": int(r.ceiling_price or 0), "bid_id": r.bid_id}
    return out


def baca_komisi_patokan(username_toko):
    """{SKU_UPPER: {harga_jual, persen}} produk yg KOMISI-nya AKTIF (`harga_jual > 0`) di toko ini,
    dari `harga_komisi_toko` (SYNTRA = sumber kebenaran komisi; NO anti-bot). Komisi aktif ⇒
    `harga_jual` jadi PATOKAN harga → target Fase 2 beralih ke sini (poin 3·0). `username_toko` =
    username (mis. 'yarrastore'); kolom tabel `username_toko`. Toko tanpa komisi -> {} (mayoritas)."""
    if not username_toko:
        return {}
    with get_engine().connect() as c:
        rows = c.execute(text("""select upper(sku) sku_u, harga_jual, komisi_persen
                                 from harga_komisi_toko
                                 where lower(username_toko) = lower(:u) and harga_jual > 0"""),
                         {"u": username_toko}).fetchall()
    return {r.sku_u: {"harga_jual": int(r.harga_jual or 0), "persen": float(r.komisi_persen or 0)}
            for r in rows}


def banding_komisi(nama_toko):
    """#9 — banding komisi SYNTRA ("harusnya", `harga_komisi_toko`) vs SHOPEE ("aktual",
    `harga_fakta_komisi`) per ITEM. SKU Syntra dipetakan ke item_id via `harga_olah_data`.
    Return list {item_id, item_name, syntra_komisi, syntra_persen, shopee_komisi, shopee_persen, verdict}.
    verdict: 'sesuai' (dua-dua aktif) / 'belum_dikomisikan' (Syntra ya, Shopee belum) /
    'harusnya_dicabut' (Shopee aktif, Syntra ngga).
    ⚠️ LIMITASI: peta SKU->item_id lewat `harga_olah_data` yg STOK-FILTERED (variasi stok 0 tak
    ke-grab) -> SKU komisi yg semua variasinya stok 0 TIDAK muncul (contoh Yarra: 43/58 SKU ke-map
    -> 10 item). Belum ada peta SKU->item lengkap di DB (harga_all_produk tanpa item_id). PR."""
    username = config.username_dari_nama(nama_toko)
    with get_engine().connect() as c:
        # SYNTRA: item_id yg punya >=1 SKU harga_jual>0 (petakan sku->item_id via olah_data)
        syntra = c.execute(text("""
            select o.item_id, max(k.komisi_persen) persen
            from harga_komisi_toko k
            join harga_olah_data o on upper(o.sku) = upper(k.sku) and o.toko = :nama
            where lower(k.username_toko) = lower(:u) and k.harga_jual > 0
            group by o.item_id
        """), {"nama": nama_toko, "u": username or nama_toko}).fetchall()
        shopee = c.execute(text("""select item_id, persen, item_name
                                   from harga_fakta_komisi where toko = :nama"""),
                           {"nama": nama_toko}).fetchall()
    syntra_map = {int(r.item_id): float(r.persen or 0) for r in syntra}
    shopee_map = {int(r.item_id): {"persen": float(r.persen or 0), "name": r.item_name} for r in shopee}
    out = []
    for iid in sorted(set(syntra_map) | set(shopee_map)):
        s_ada, p_ada = iid in syntra_map, iid in shopee_map
        verdict = "sesuai" if (s_ada and p_ada) else ("belum_dikomisikan" if s_ada else "harusnya_dicabut")
        out.append({
            "item_id": iid, "item_name": shopee_map.get(iid, {}).get("name", ""),
            "syntra_komisi": s_ada, "syntra_persen": syntra_map.get(iid),
            "shopee_komisi": p_ada, "shopee_persen": shopee_map.get(iid, {}).get("persen"),
            "verdict": verdict,
        })
    return out


def baca_item_di_paket(toko):
    """set(item_id) yg lagi ikut PAKET DISKON (dari konteks jenis='Paket Diskon'). Konteks TIDAK
    simpan bundle_deal_id (ongoing_campaigns ct=3 promotion_id kosong) -> cukup tau item-nya
    ikut paket; deal-id di-resolve dari fakta paket saat takedown/re-add."""
    with get_engine().connect() as c:
        rows = c.execute(text("""select distinct item_id from harga_promo_konteks
                                 where toko = :t and jenis = 'Paket Diskon'"""), {"t": toko}).fetchall()
    return {int(r.item_id) for r in rows}


def baca_paket_aktif(toko):
    """list {bundle_deal_id, start, end} paket toko (dari fakta, epoch detik). Buat iterasi
    takedown (PUT status=2 ke tiap deal) + pilih deal utama buat re-add."""
    with get_engine().connect() as c:
        rows = c.execute(text("""select bundle_deal_id,
                                        extract(epoch from start_time)::bigint st,
                                        extract(epoch from end_time)::bigint et
                                 from harga_fakta_paket where toko = :t"""), {"t": toko}).fetchall()
    return [{"bundle_deal_id": int(r.bundle_deal_id), "start": int(r.st or 0), "end": int(r.et or 0)}
            for r in rows]


def baca_voucher_item(toko):
    """{item_id: [voucher_id,...]} — voucher PRODUK yg memuat tiap item (dari item_scope fakta).
    voucher shop-wide (item_scope null) DILEWATI (tak nempel produk tertentu -> tak blokir harga dasar)."""
    with get_engine().connect() as c:
        rows = c.execute(text("""select voucher_id, item_scope from harga_fakta_voucher
                                 where toko = :t and item_scope is not null"""), {"t": toko}).fetchall()
    out = {}
    for r in rows:
        for iid in (r.item_scope or []):
            try:
                out.setdefault(int(iid), []).append(int(r.voucher_id))
            except (TypeError, ValueError):
                continue
    return out


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
