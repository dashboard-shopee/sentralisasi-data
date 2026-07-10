"""modules/provisioning.py — FASE 2 poin 5: PASANG/DAFTAR promo upsell (per-toko, per-modul).

Orkestrasi tipis di atas modul low-level yg SUDAH ada (paket_diskon/voucher/…). Semua DRY_RUN-aware
(modul low-level yg handle). IDEMPOTENT: paket/voucher yg dikelola bot dinamai/di-kode ber-prefix
`config.NAMA_UPSELL` biar ga bikin dobel tiap hari.

Sumber produk = `harga_olah_data` (hasil grab Fase 1) → Fase 1 harus udah jalan (produk di DB).
Cadence: paket & voucher = HARIAN.
"""
import re
import time
import colorama; colorama.init()
import config
from modules import paket_diskon as PD
from modules import voucher as V


def paket(shop, nama_toko, session):
    """Paket Diskon harian — pastikan ADA 1 paket `UPSELL <toko>` + enroll SEMUA produk toko.
    Idempotent: kalau paket UPSELL yg masih berjalan udah ada → reuse + enroll (attach idempotent);
    kalau belum ada → buat baru (DURASI_PROMO_HARI) + enroll. DRY_RUN: buat_deal balik None →
    cukup lapor rencana (ga bisa enroll tanpa bid). Return ringkasan."""
    now = int(time.time())
    item_ids = PD.item_ids_toko(nama_toko)
    if not item_ids:
        print(colorama.Fore.YELLOW + f"[prov paket] [{nama_toko}] 0 produk di olah_data — skip (grab Fase 1 dulu)" + colorama.Style.RESET_ALL)
        return {"paket": None, "produk": 0}

    deals = PD.list_deals(session) or []
    prefix = config.NAMA_UPSELL
    aktif = [d for d in deals
             if str(d.get("name", "")).startswith(prefix) and int(d.get("end_time") or 0) > now]

    if aktif:
        d0 = aktif[0]
        bid = d0.get("bundle_deal_id") or d0.get("id")
        start = int(d0.get("start_time") or now)
        end = int(d0.get("end_time") or now + config.DURASI_PROMO_HARI * 86400)
        r = PD.enroll_semua(session, item_ids, bid, start, end)
        print(colorama.Fore.GREEN + f"[prov paket] [{nama_toko}] reuse '{d0.get('name')}' (id {bid}) → {r}" + colorama.Style.RESET_ALL)
        return {"paket": bid, "baru": False, **r}

    # belum ada paket UPSELL berjalan → buat baru
    start, end = now + 300, now + config.DURASI_PROMO_HARI * 86400
    bid = PD.buat_deal(session, f"{prefix} {nama_toko}", start, end)   # None kalau DRY_RUN
    if not bid:
        print(colorama.Fore.YELLOW + f"[prov paket] [{nama_toko}] (DRY) bakal BUAT '{prefix} {nama_toko}' + enroll {len(item_ids)} produk" + colorama.Style.RESET_ALL)
        return {"paket": "DRY-baru", "baru": True, "produk": len(item_ids)}
    r = PD.enroll_semua(session, item_ids, bid, start, end)
    print(colorama.Fore.CYAN + f"[prov paket] [{nama_toko}] paket BARU {bid} → {r}" + colorama.Style.RESET_ALL)
    return {"paket": bid, "baru": True, **r}


def _kode_voucher(nama_toko):
    """Kode voucher deterministik ber-prefix UP (alnum, maks 14) — buat idempotent (deteksi via prefix)."""
    return ("UP" + re.sub(r"[^A-Za-z0-9]", "", nama_toko).upper())[:14]


def voucher(shop, nama_toko, session):
    """Voucher harian — pastikan ADA 1 voucher `UPSELL <toko>` (ikuti_toko, shop-wide).
    Idempotent: kalau voucher ber-kode `UP*` yg masih valid udah ada → auto-perpanjang yg mau mati
    (sisa ≤ 1 hari); kalau belum ada → buat baru. min_price = 2×AOV (V.min_price_toko). DRY_RUN:
    buat/perpanjang balik None/simulasi. Return ringkasan.
    ⚠️ mulai dari tipe `ikuti_toko` (voucher PRODUK per-band = fase lanjutan)."""
    now = int(time.time())
    vouchers = V.list_vouchers(session, promotion_type=0) or []
    ours = [v for v in vouchers
            if str(v.get("voucher_code") or v.get("code") or "").upper().startswith("UP")
            and int(v.get("end_time") or 0) > now]

    if ours:
        diperpanjang = 0
        for v in ours:
            if V.perlu_perpanjang(v, now):
                V.perpanjang_voucher(session, v.get("voucher_id") or v.get("id"),
                                     now + config.DURASI_PROMO_HARI * 86400, voucher_detail=v)
                diperpanjang += 1
        print(colorama.Fore.GREEN + f"[prov voucher] [{nama_toko}] udah ada {len(ours)} voucher UP, {diperpanjang} diperpanjang" + colorama.Style.RESET_ALL)
        return {"voucher": "ada", "jumlah": len(ours), "perpanjang": diperpanjang}

    # belum ada → buat baru (ikuti_toko, shop-wide)
    mp = V.min_price_toko(nama_toko)
    code = _kode_voucher(nama_toko)
    vid = V.buat_voucher(session, f"{config.NAMA_UPSELL} {nama_toko}", code, now + 300,
                         now + config.DURASI_PROMO_HARI * 86400,
                         discount=config.KPI_VOUCHER_DISKON_PCT, min_price=mp, max_value=None,
                         **V.TIPE["ikuti_toko"])
    warna = colorama.Fore.YELLOW if not vid else colorama.Fore.CYAN
    print(warna + f"[prov voucher] [{nama_toko}] {'(DRY) bakal buat' if not vid else 'buat'} voucher '{code}' diskon {config.KPI_VOUCHER_DISKON_PCT}% min Rp{mp:,}" + colorama.Style.RESET_ALL)
    return {"voucher": vid or "DRY-baru", "code": code, "min_price": mp}


def campaign(shop, nama_toko, session):
    """Campaign mingguan — nominasi produk (yg LOLOS kriteria stok) ke sesi campaign yg lagi buka
    window nominasi. Kriteria: stok > KPI_CAMPAIGN_PASANG_STOK_MIN (50) DAN stok > KPI_CAMPAIGN_
    PASANG_STOK_X_PJH (10) × penjualan/hari. Skip produk yg SEMUA modelnya udah ternominasi.
    ⚠️ harga campaign maks target×0.985 = requirement Shopee saat nominasi/aktivasi (verif live)."""
    from modules import campaign as C
    from modules import sql_harga as SQL
    sesi = C.open_sessions(session, keywords=config.CAMPAIGN_KEYWORDS)   # cuma sesi buka nominasi
    if not sesi:
        print(colorama.Fore.YELLOW + f"[prov campaign] [{nama_toko}] 0 sesi buka nominasi — skip" + colorama.Style.RESET_ALL)
        return {"campaign": 0, "sesi": 0, "lolos": 0}

    prod_all = C.produk_toko(nama_toko)                 # semua produk berstok [{item_id, models}]
    stok = SQL.baca_stok_per_item(nama_toko)            # {item_id: stok}
    pjh = SQL.baca_penjualan_per_hari([p["item_id"] for p in prod_all])
    smin = config.KPI_CAMPAIGN_PASANG_STOK_MIN
    xf = config.KPI_CAMPAIGN_PASANG_STOK_X_PJH
    lolos = [p for p in prod_all
             if stok.get(p["item_id"], 0) > smin and stok.get(p["item_id"], 0) > xf * pjh.get(p["item_id"], 0.0)]
    print(colorama.Fore.WHITE + f"[prov campaign] [{nama_toko}] {len(prod_all)} produk → {len(lolos)} lolos (stok>{smin} & >{xf}×pjh) | {len(sesi)} sesi" + colorama.Style.RESET_ALL)

    total = 0
    for s in sesi:
        sid = s["session_id"]
        already = C.get_nominated(session, sid)         # {(iid_str,mid_str): {...}}
        baru = [p for p in lolos
                if not all((str(p["item_id"]), str(m)) in already for m in p["models"])]
        r = C.nominate(session, sid, baru)
        total += r.get("staged", 0)
    print(colorama.Fore.CYAN + f"[prov campaign] [{nama_toko}] total staged {total} produk ke {len(sesi)} sesi" + colorama.Style.RESET_ALL)
    return {"campaign": total, "sesi": len(sesi), "lolos": len(lolos)}


def flash(shop, nama_toko, session):
    """Flash Sale MINGGUAN — daftar produk ke sesi flash (grab slot 7hr, rotasi maks 50/sesi, urut
    kategori+penjualan tertinggi, harga = real−POTONG_HARGA). Reuse `flash_sale_daftar.daftar_mingguan`
    (udah lengkap). ⚠️ verif live endpoint flash (RENCANA §1 B&D — set_item_sequence pernah param-err,
    udah non-fatal). Kriteria stok>KPI_FLASH_PASANG_STOK_MIN / >×pjh = refinement TODO (siapkan_produk
    skrg cuma stok>0)."""
    from modules import flash_sale_daftar as FSD
    r = FSD.daftar_mingguan(session, nama_toko)
    print(colorama.Fore.CYAN + f"[prov flash] [{nama_toko}] → {r}" + colorama.Style.RESET_ALL)
    return {"flash_sesi": r.get("sesi", 0), **r}
