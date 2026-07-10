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
