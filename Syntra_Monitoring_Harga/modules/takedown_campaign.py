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

Alur (16 Jul, S2: TANPA browser — semua endpoint jalur ini lolos requests polos):
  1. get_open_sessions(window="sesi") -> sesi campaign yg LAGI BERJALAN (nominasi bisa
     udah tutup tapi produk masih jalan & harganya masih terkunci -> perlu di-opt-out).
  2. SQL.baca_campaign_item(shop, sid) -> cocokkan (item,model) target -> nomination_id
     -> takedown_products (opt-out) -> hapus baris DB.

Scope CUMA campaign yg namanya cocok config.CAMPAIGN_KEYWORDS (tanggal kembar/gajian/
6.6..12.12 dst — grilling 15 Jul: campaign kecil/ga relevan Shopee di-skip total, ga
perlu di-automasi).
"""
from modules.log_siklus import log
import config


def takedown_dari_campaign(session, shop, i, kunci_set, nama_toko=None):
    """Keluarkan variasi (item_id, model_id) di `kunci_set` dari SEMUA sesi campaign
    aktif yang memuatnya. Return jumlah nominasi ter-takedown (0 kalau tak ada).

    ✅ (16 Jul, S2 optimasi) TANPA BROWSER: semua yg dibutuhin jalur ini — get_open_sessions
    (get_landing + get_session_list) + opt_out — LOLOS requests polos (verif 16 Jul);
    nomination_id dibaca dari DB sendiri (bukan nominated_entity_list yg anti-bot). Jadi
    ga perlu buka_page_toko / segarkan lagi → per-jam lebih cepet & sesi requests ga basi."""
    if not kunci_set:
        return 0
    from modules import campaign_util as C
    from modules import sql_harga as SQL

    nama_toko = nama_toko or shop
    total = 0
    try:
        # ⚠️ (17 Jul) GABUNG dua window: "sesi" (lagi BERJALAN) + "nominasi" (belum mulai tapi
        # nominasi kebuka). Kebukti DRY 17 Jul: item ternominasi di sesi yg BELUM mulai (25 Jul)
        # ke-flag diagnosa tapi ga pernah kesentuh karena window="sesi" doang → cabut harus
        # bisa SEBELUM sesi live (opt_out valid begitu nominate_status 30).
        sesi = C.get_open_sessions(session, shop, window="sesi")
        ada = {s.get("session_id") for s in sesi}
        for s in C.get_open_sessions(session, shop, window="nominasi"):
            if s.get("session_id") not in ada:
                sesi.append(s)
        for s in sesi:
            sid = s.get("session_id")
            if not sid:
                continue
            nominated = SQL.baca_campaign_item(nama_toko, sid)  # {(iid_int,mid_int)->info} dari DB
            nom_ids, pairs = [], []
            for (iid, mid), info in nominated.items():
                if (iid, mid) in kunci_set and info.get("nomination_id"):
                    nom_ids.append(info["nomination_id"])
                    pairs.append((iid, mid))
            if not nom_ids:
                continue
            if config.DRY_RUN:
                log(f"(DRY) {len(nom_ids)} nominasi akan di-takedown dari sesi '{s.get('session_name','')}'",
                    level="warning", toko=shop, modul="campaign")
                total += len(nom_ids)
            else:
                if C.takedown_products(session, shop, sid, nom_ids):
                    total += len(nom_ids)
                    # bersihin baris DB biar diagnosa jam berikutnya ga nge-flag zombie
                    try:
                        SQL.hapus_campaign_item(nama_toko, sid, pairs)
                    except Exception as e:
                        log(f"gagal hapus baris takedown dari DB: {type(e).__name__}", level="error", toko=shop, modul="campaign")
    except Exception as e:
        log(f"takedown campaign gagal: {type(e).__name__}: {str(e)[:120]}", level="error", toko=shop, modul="campaign")
    return total
