"""modules/fakta.py — FASE 1 (PENGUMPUL FAKTA). READ-ONLY.

Tiap fungsi = panggil fungsi-BACA modul yg sudah ada -> tulis ke tabel fakta SQL.
TIDAK ada aksi tulis ke Shopee (ubah harga/takedown/enroll = Fase 3 Solusi).

Cadence (di-gate run.py):
  - TIER JAM     : fakta_produk (harga + stok + konteks promo)
  - TIER HARIAN  : fakta_garansi, fakta_campaign
  - TIER MINGGUAN: fakta_flash, fakta_voucher, fakta_paket
  - TIER BULANAN : housekeeping (prune fakta yatim)

Catatan KOMISI: TIDAK di-grab dari Shopee di sini (endpoint gql kena anti-bot
x-sap-sec, read pun berisiko 403). Sumber kebenaran komisi = harga_komisi_toko
(SQL, diedit dashboard). Lihat RENCANA_FASE1.md §8.
"""
from datetime import datetime, timezone

import colorama; colorama.init()

import config
from modules.grab_produk import grab_produk
from modules import sql_harga as SQL


def _iso(epoch):
    """Epoch detik -> ISO string (buat kolom timestamptz). 0/None/negatif -> None."""
    try:
        n = int(epoch or 0)
    except (ValueError, TypeError):
        return None
    if n <= 0:
        return None
    return datetime.fromtimestamp(n, tz=timezone.utc).isoformat()


def _log(nama, teks, warna=colorama.Fore.WHITE):
    print(warna + f"[fakta] [{nama}] {teks}" + colorama.Style.RESET_ALL)


# ── TIER JAM: produk (harga + stok) + konteks promo ──
def fakta_produk(username, nama_toko, session):
    """grab_produk -> harga_olah_data + harga_promo_konteks. Return (n_variasi, n_konteks)."""
    rows, konteks = grab_produk(shop=username, nama_toko=nama_toko, session=session)
    n = SQL.simpan_olah_data(rows)
    nk = SQL.simpan_konteks(nama_toko, konteks)
    return n, nk


# ── TIER HARIAN: Garansi Harga Terbaik ──
def fakta_garansi(nama_toko, session):
    """garansi.list_ongoing -> harga_fakta_garansi. Return jumlah variasi."""
    from modules import garansi
    ongoing = garansi.list_ongoing(session)      # {(item,model): {bid_id,cspu_id,current_price,bid_price,stok}}
    baris = [{
        "item_id": item, "model_id": model,
        "bid_id": v.get("bid_id") or None, "cspu_id": v.get("cspu_id") or None,
        "current_price": v.get("current_price", 0) or 0,
        "bid_price": v.get("bid_price", 0) or 0,
        "best_price": v.get("best_price", 0) or 0,
        "stok": v.get("stok", 0) or 0,
    } for (item, model), v in ongoing.items()]
    n = SQL.simpan_fakta_garansi(nama_toko, baris)
    _log(nama_toko, f"Garansi: {n} variasi", colorama.Fore.LIGHTGREEN_EX)
    return n


# ── TIER HARIAN: Campaign (sesi buka-nominasi + produk ternominasi) ──
def fakta_campaign(nama_toko, session):
    """campaign.open_sessions + get_nominated -> fakta_campaign_sesi + _item.
    Return (n_sesi, n_item)."""
    from modules import campaign
    sesi_list = campaign.open_sessions(session)
    baris_sesi, baris_item = [], []
    for s in sesi_list:
        sid = str(s.get("session_id"))
        baris_sesi.append({
            "campaign_id": str(s.get("campaign_id", "")),
            "session_id": sid,
            "campaign_name": s.get("campaign_name") or None,
            "session_name": s.get("session_name") or None,
            "session_start": _iso(s.get("session_start")),
            "session_end": _iso(s.get("session_end")),
            "nomination_end": _iso(s.get("nomination_end")),
        })
        try:
            nominasi = campaign.get_nominated(session, sid)   # {(item_str,model_str): {...}}
        except Exception as e:
            _log(nama_toko, f"get_nominated sesi {sid} gagal: {type(e).__name__}", colorama.Fore.RED)
            nominasi = {}
        for (iid, mid), v in nominasi.items():
            try:
                item, model = int(iid), int(mid)
            except (TypeError, ValueError):
                continue
            baris_item.append({
                "session_id": sid, "item_id": item, "model_id": model,
                "nomination_id": str(v.get("nomination_id") or "") or None,
                "nominate_status": v.get("nominate_status"),
                "campaign_price": v.get("campaign_price", 0) or 0,
            })
    ns = SQL.simpan_fakta_campaign_sesi(nama_toko, baris_sesi)
    ni = SQL.simpan_fakta_campaign_item(nama_toko, baris_item)
    _log(nama_toko, f"Campaign: {ns} sesi buka-nominasi, {ni} produk ternominasi", colorama.Fore.LIGHTGREEN_EX)
    return ns, ni


# ── TIER MINGGUAN: Flash Sale (sesi + item) ──
def fakta_flash(nama_toko, session):
    """flash_sale.list_flash_sale + items_flash_sale -> fakta_flash_sesi + _item.
    Return (n_sesi, n_item)."""
    from modules import flash_sale as FS
    sesi_list = FS.list_flash_sale(session, hanya_aktif=True)
    baris_sesi, baris_item = [], []
    for f in sesi_list:
        fsid = f.get("flash_sale_id")
        if fsid is None:
            continue
        baris_sesi.append({
            "flash_sale_id": int(fsid),
            "status": f.get("status"),
            "timeslot_id": f.get("timeslot_id"),
            "start_time": _iso(f.get("start_time")),
            "end_time": _iso(f.get("end_time")),
            "item_count": f.get("item_count", 0) or 0,
        })
        try:
            items = FS.items_flash_sale(session, fsid)
        except Exception as e:
            _log(nama_toko, f"items_flash_sale {fsid} gagal: {type(e).__name__}", colorama.Fore.RED)
            items = []
        for it in items:
            try:
                item, model = int(it.get("item_id") or 0), int(it.get("model_id") or 0)
            except (TypeError, ValueError):
                continue
            baris_item.append({
                "flash_sale_id": int(fsid), "item_id": item, "model_id": model,
                "status": it.get("status"),
                "promotion_price": it.get("promotion_price", 0) or 0,
                "stock": it.get("stock", 0) or 0,
            })
    ns = SQL.simpan_fakta_flash_sesi(nama_toko, baris_sesi)
    ni = SQL.simpan_fakta_flash_item(nama_toko, baris_item)
    _log(nama_toko, f"Flash Sale: {ns} sesi, {ni} item", colorama.Fore.LIGHTGREEN_EX)
    return ns, ni


# ── TIER MINGGUAN: Voucher ──
def _num(x):
    """Rupiah/persen string ('50000.00') -> float; None/'' -> None."""
    if x in (None, "", "None"):
        return None
    try:
        return float(x)
    except (ValueError, TypeError):
        return None


def _norm_voucher(v):
    """Normalisasi 1 voucher raw -> dict standar. Field verified via sniff 6 Jul:
    voucher_id, voucher_code, name, discount, value, min_price, start/end_time, status,
    use_type, rule.items (voucher produk)."""
    rule = v.get("rule") or {}
    items = rule.get("items") if isinstance(rule, dict) else None
    item_scope = [int(i.get("itemid")) for i in items
                  if isinstance(i, dict) and i.get("itemid")] if items else None
    return {
        "voucher_id": int(v.get("voucher_id") or v.get("id") or 0),
        "code": v.get("voucher_code") or v.get("code") or None,
        "name": v.get("name") or None,
        "discount": _num(v.get("discount")) or _num(v.get("value")),
        "min_price": _num(v.get("min_price")),
        "tipe": str(v.get("use_type")) if v.get("use_type") is not None else None,
        "start_time": _iso(v.get("start_time")),
        "end_time": _iso(v.get("end_time")),
        "status": v.get("status"),
        "item_scope": item_scope,
    }


def fakta_voucher(nama_toko, session):
    """voucher.list_vouchers -> harga_fakta_voucher. HANYA voucher BERJALAN (promotion_type=2)
    + AKAN DATANG (promotion_type=1) — yg BERAKHIR di-skip. Return jumlah voucher."""
    from modules import voucher
    seen = {}
    for pt in (2, 1):   # 2=berjalan, 1=akan datang (0=semua termasuk berakhir -> TIDAK dipakai)
        for v in (voucher.list_vouchers(session, promotion_type=pt) or []):
            if not isinstance(v, dict):
                continue
            b = _norm_voucher(v)
            if b["voucher_id"]:
                seen[b["voucher_id"]] = b
    n = SQL.simpan_fakta_voucher(nama_toko, list(seen.values()))
    _log(nama_toko, f"Voucher: {n} (berjalan+akan datang)", colorama.Fore.LIGHTGREEN_EX)
    return n


# ── TIER MINGGUAN: Paket Diskon ──
def fakta_paket(nama_toko, session):
    """paket_diskon.list_deals -> harga_fakta_paket. Return jumlah bundle."""
    from modules import paket_diskon
    raw = paket_diskon.list_deals(session) or []
    baris = []
    for d in raw:
        if not isinstance(d, dict):
            continue
        bid = d.get("bundle_deal_id") or d.get("id")
        if not bid:
            continue
        baris.append({
            "bundle_deal_id": int(bid),
            "name": d.get("name") or None,
            "status": d.get("status"),
            "start_time": _iso(d.get("start_time")),
            "end_time": _iso(d.get("end_time")),
            "tiers": d.get("additional_tiers") or d.get("tiers") or None,
        })
    n = SQL.simpan_fakta_paket(nama_toko, baris)
    _log(nama_toko, f"Paket Diskon: {n}", colorama.Fore.LIGHTGREEN_EX)
    return n


# ── TIER BULANAN: housekeeping ──
def housekeeping():
    """Prune baris fakta yatim (tak ke-refresh > FAKTA_MAKS_UMUR_HARI). Return jumlah terhapus."""
    n = SQL.prune_fakta_yatim(int(getattr(config, "FAKTA_MAKS_UMUR_HARI", 35)))
    print(colorama.Fore.CYAN + f"[fakta] housekeeping: {n} baris fakta yatim di-prune" + colorama.Style.RESET_ALL)
    return n
