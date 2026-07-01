"""modules/blokir.py — cek flag RESMI Shopee: item keblok utk ubah promo/harga?

Endpoint (terverifikasi sniff): POST get_campaign_info_by_item_list
  body {"item_id_list":[...]} -> data.campaign_info[<item_id>].is_blocked_for_promotion

Ground-truth: kalau is_blocked_for_promotion=True, ubah harga/promo item itu
kemungkinan DITOLAK Shopee (lagi ikut campaign/flash sale/garansi yg mengunci).
Dipakai Fase 2 utk menandai/menjelaskan alasan sebelum mencoba ubah harga.
Berbasis `requests` (pakai sesi hasil grab) — tidak buka browser.
"""
import config
from modules.api_util import api_post


def cek_blokir(session, item_ids, chunk=100):
    """Return set(item_id:int) yang is_blocked_for_promotion=True."""
    ids = list(dict.fromkeys(int(i) for i in item_ids if i))
    if not ids:
        return set()
    blocked = set()
    params = {**session["params"], "version": "2.0.1"}
    headers = config.grab_headers(session)
    for i in range(0, len(ids), chunk):
        c = ids[i:i + chunk]
        data = api_post(config.URL_CEK_BLOKIR, headers, params,
                        {"item_id_list": c}, kunci="data")["data"]
        info = data.get("campaign_info") or {}
        for iid, v in info.items():
            if isinstance(v, dict) and v.get("is_blocked_for_promotion"):
                try:
                    blocked.add(int(iid))
                except (TypeError, ValueError):
                    pass
    return blocked
