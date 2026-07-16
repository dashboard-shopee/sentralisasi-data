"""modules/takedown_campaign.py — keluarkan variasi dari CAMPAIGN Shopee (Fase 2B).

Campaign bulanan (tanggal kembar / gajian / 6.6 dst) MENGUNCI harga item -> harga
dasar tidak bisa diubah selama item masih dinominasikan. Ini melepasnya via
campaign_util (browser-context / run_js, wajib lolos anti-bot Shopee).

✅ (15 Jul, grilling "gua mau full otomatis") nomination_id TIDAK dibaca live dari
`nominated_entity_list` lagi — endpoint itu signature-locked (90309999 kalau di-fetch-
injeksi) DAN kalau dipancing pakai klik tab beneran malah kena verify/traffic/error
(captcha WAF Shopee, kebukti live). Sumber kebenaran sekarang = DB KITA SENDIRI
(harga_fakta_campaign_item), dicatet nominate() pas staging (preview/add) via
preview_list yg aman (auto-fire pas navigasi biasa, gak perlu klik).

Alur:
  1. buka_page_toko(shop, i)                  -> browser aktif pada sub-toko itu.
  2. get_open_sessions(window="sesi") -> sesi campaign yg LAGI BERJALAN (nominasi bisa
     udah tutup tapi produk masih jalan & harganya masih terkunci -> perlu di-opt-out).
  3. SQL.baca_campaign_item(shop, sid) -> cocokkan (item,model) target -> nomination_id
     -> takedown_products (opt-out, aman/no-signature).
  4. tutup_page().

Scope CUMA campaign yg namanya cocok config.CAMPAIGN_KEYWORDS (tanggal kembar/gajian/
6.6..12.12 dst — grilling 15 Jul: campaign kecil/ga relevan Shopee di-skip total, ga
perlu di-automasi).
"""
from modules.log_siklus import log
import config


def takedown_dari_campaign(session, shop, i, kunci_set, nama_toko=None):
    """Keluarkan variasi (item_id, model_id) di `kunci_set` dari SEMUA sesi campaign
    aktif yang memuatnya. Return jumlah nominasi ter-takedown (0 kalau tak ada)."""
    if not kunci_set:
        return 0
    from modules.session import buka_page_toko, tutup_page, segarkan_abis_browser_context
    from modules import campaign_util as C
    from modules import sql_harga as SQL

    nama_toko = nama_toko or shop
    total = 0
    try:
        buka_page_toko(shop, i)                       # browser-context ON (anti-bot)
        sesi = C.get_open_sessions(session, shop, window="sesi")   # sesi BERJALAN (buat takedown)
        for s in sesi:
            sid = s.get("session_id")
            if not sid:
                continue
            nominated = SQL.baca_campaign_item(nama_toko, sid)  # {(iid_int,mid_int)->info} dari DB
            nom_ids = []
            for (iid, mid), info in nominated.items():
                if (iid, mid) in kunci_set and info.get("nomination_id"):
                    nom_ids.append(info["nomination_id"])
            if not nom_ids:
                continue
            if config.DRY_RUN:
                log(f"(DRY) {len(nom_ids)} nominasi akan di-takedown dari sesi '{s.get('session_name','')}'",
                    level="warning", toko=shop, modul="campaign")
                total += len(nom_ids)
            else:
                if C.takedown_products(session, shop, sid, nom_ids):
                    total += len(nom_ids)
    except Exception as e:
        log(f"takedown campaign gagal: {type(e).__name__}: {str(e)[:120]}", level="error", toko=shop, modul="campaign")
    finally:
        try:
            tutup_page()
        except Exception:
            pass
        segarkan_abis_browser_context(session, shop)
    return total
