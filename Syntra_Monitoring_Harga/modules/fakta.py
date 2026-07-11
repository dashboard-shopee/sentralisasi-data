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


def fakta_garansi_nom(nama_toko, session):
    """Grab 3 KATEGORI nominasi garansi -> harga_fakta_garansi_nom (buat dashboard Pusat Promosi >
    Garansi 3 tab): rekomendasi (belum-didaftar) + terbaik + perlu_ditinjau. READ-ONLY."""
    from modules import garansi as G
    baris = []
    for it in G.list_rekomendasi(session):                       # (a) belum-didaftar
        for m in (it.get("models") or [{}]):
            baris.append({"item_id": it["item_id"], "model_id": int(m.get("model_id") or 0),
                          "kategori": "rekomendasi", "item_name": it["item_name"],
                          "model_name": m.get("model_name", ""), "floor": it["floor"],
                          "ceiling": it["ceiling"], "stok": it["stok"], "bid_id": None, "bid_status": None})
    for o in G.list_ongoing_status(session):                     # (b) terbaik / (c) perlu_ditinjau
        kat = "terbaik" if o.get("bid_status") == G.BID_STATUS_TERBAIK else "perlu_ditinjau"
        baris.append({"item_id": o["item_id"], "model_id": int(o.get("model_id") or 0),
                      "kategori": kat, "item_name": o["item_name"], "model_name": o["model_name"],
                      "floor": o["floor"], "ceiling": o["ceiling"], "stok": o["stok"],
                      "bid_id": o["bid_id"], "bid_status": o["bid_status"]})
    n = SQL.simpan_fakta_garansi_nom(nama_toko, baris) if baris else 0
    _log(nama_toko, f"Garansi nominasi: {n} baris (rekom+terbaik+perlu-ditinjau)", colorama.Fore.LIGHTGREEN_EX)
    return n


# ── TIER HARIAN: Campaign (grab harian; pasang mingguan) — sesi buka-nominasi + produk ternominasi ──
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


# ── TIER HARIAN: Flash Sale (grab harian; pasang mingguan) — sesi + item ──
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


# ── TIER HARIAN: Voucher ──
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


# ── TIER HARIAN: Paket Diskon ──
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
        items = paket_diskon.baca_item_deal(session, int(bid))   # keanggotaan produk per paket
        baris.append({
            "bundle_deal_id": int(bid),
            "name": d.get("name") or None,
            "status": d.get("status"),
            "start_time": _iso(d.get("start_time")),
            "end_time": _iso(d.get("end_time")),
            "tiers": d.get("additional_tiers") or d.get("tiers") or None,
            "items": items,
            "item_count": len(items),
        })
    n = SQL.simpan_fakta_paket(nama_toko, baris)
    _log(nama_toko, f"Paket Diskon: {n}", colorama.Fore.LIGHTGREEN_EX)
    return n


# ── PROMO TOKO entity (tier JAM) — buat Pusat Promosi master-detail ──
def fakta_promo_toko(username, nama_toko, session):
    """grab_semua_promo (berjalan+akan datang) + detail + item -> harga_fakta_promo_toko(+_item).
    Return (n_promo, n_item)."""
    from modules.discount_util import grab_semua_promo, grab_promo_detail, grab_item_promo
    promos = grab_semua_promo(username, session)
    ent, items = [], []
    for p in promos:
        pid = p.get("promotion_id")
        if not pid:
            continue
        status = "berjalan" if p.get("time_status") == 2 else "akan datang"
        det = grab_promo_detail(session, pid) or {}
        try:
            itlist = grab_item_promo(username, session, pid)
        except Exception as e:
            _log(nama_toko, f"grab_item_promo {pid} gagal: {type(e).__name__}", colorama.Fore.RED)
            itlist = []
        n_item = len({it.get("item_id") for it in itlist if it.get("item_id")})
        ent.append({
            "promotion_id": int(pid), "nama": (p.get("name") or None), "status": status,
            "mulai": _iso(det.get("start_time")), "berakhir": _iso(det.get("end_time")),
            "item_count": n_item,
        })
        for it in itlist:
            if it.get("item_id"):
                items.append({
                    "promotion_id": int(pid), "item_id": int(it["item_id"]),
                    "model_id": int(it.get("model_id") or 0),
                    "harga_promo": int(it.get("promotion_price", 0) or 0) // config.FAKTOR_HARGA,
                })
    ns = SQL.simpan_fakta_promo_toko(nama_toko, ent)
    ni = SQL.simpan_fakta_promo_toko_item(nama_toko, items)
    _log(nama_toko, f"Promo Toko: {ns} promo (berjalan+akan datang), {ni} produk", colorama.Fore.LIGHTGREEN_EX)
    return ns, ni


# ── KATEGORI produk (incremental, tier mingguan / command khusus) ──
def fakta_kategori(nama_toko, session, limit=None):
    """Grab kategori Shopee utk produk yg BELUM punya kategori (incremental). Cap `limit`
    (default config.MAKS_KATEGORI_PER_RUN). Return jumlah produk berhasil diisi."""
    from modules import kategori
    lim = int(limit if limit is not None else getattr(config, "MAKS_KATEGORI_PER_RUN", 800))
    item_ids = SQL.baca_item_tanpa_kategori(nama_toko, lim)
    if not item_ids:
        return 0
    baris, gagal = [], 0
    for iid in item_ids:
        try:
            k = kategori.ambil_kategori(session, iid)
            # Sukses (ada/tidak-ada kategori) -> simpan (item ditandai 'udah diproses' biar
            # tak dicek ulang). Kalau None (draft/tanpa kategori) -> row kategori null.
            baris.append({"item_id": iid, **(k or {"kategori_id": None, "leaf": None, "full": None})})
        except Exception:
            gagal += 1   # error transien/hard -> skip (di-retry siklus berikutnya)
    n = SQL.simpan_kategori(nama_toko, baris)
    ada = sum(1 for b in baris if b.get("full"))
    _log(nama_toko, f"Kategori: +{n} diproses ({ada} ada kategori), {gagal} skip-retry", colorama.Fore.LIGHTGREEN_EX)
    return n


# ── TIER BULANAN: housekeeping ──
def housekeeping():
    """Prune baris fakta yatim (tak ke-refresh > FAKTA_MAKS_UMUR_HARI). Return jumlah terhapus."""
    n = SQL.prune_fakta_yatim(int(getattr(config, "FAKTA_MAKS_UMUR_HARI", 35)))
    print(colorama.Fore.CYAN + f"[fakta] housekeeping: {n} baris fakta yatim di-prune" + colorama.Style.RESET_ALL)
    return n
