"""modules/campaign.py — AUTO nominasi / takedown produk ke CAMPAIGN Shopee (cmt).

✅ TERBUKTI LIVE 3 Jul (Kimmioshop): campaign FULL API-able via `requests` (TIDAK kena anti-bot,
beda dgn flash sale/komisi). Semua `mkt/cmt/*`:
  READ:
    get_landing_page_campaign_list {campaign_scene:[],view_flag:1,pagination:{...,sort_type:9},sc_page:0} -> data.list
    commonscene/get_session_list   {campaign_id,view_type:0,session_type:0,mechanic_label_ids:[]} -> data.general.product_session[]
    nominated/nominated_entity_list{session_id,entity_type:[2],entity_tab:0,page_num,page_size} -> recruiting_entities
  NOMINATE (2 langkah):
    preview/add                    {session_id,preview_no:"",entity_list_data:{recruiting_entities:[
                                     {entity_type:2,product:{item_id,models:[{item_id,model_id}]}}]}} -> {preview_no,product_success_num}
    preview/submit_entity_online   {session_id,entity_type:2,confirm_risky:false} -> COMMIT (data.product_result)
  TAKEDOWN:
    nominated/opt_out              {session_id,nomination_ids:[...],reason} -> hapus nominasi

CATATAN:
  - item_id & model_id dikirim sbg STRING (sesuai capture).
  - Nominasi = 2 fase: STAGE semua produk (preview/add) lalu SUBMIT sekali (commit) per sesi.
  - Campaign non-produk balik code 1671500008 -> di-skip.
  - Hormatin config.DRY_RUN.
"""
import time
from modules.log_siklus import log
import config
from modules.api_util import api_post, AntiBotError

ENTITY_PRODUK = 2   # entity_type produk


def _chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


# ── BACA: sesi campaign (window nominasi ATAU sesi berjalan) ──
def open_sessions(session, keywords=None, window="nominasi"):
    """Return list dict sesi campaign yg aktif. keywords (list) opsional -> filter nama
    campaign; None = semua.
    window="nominasi" (default) -> sesi yg WINDOW NOMINASI-nya buka (buat DAFTAR produk).
    window="sesi"                -> sesi yg lagi BERJALAN (buat TAKEDOWN; nominasi bisa udah
                                    tutup tapi produk masih jalan di campaign & perlu di-opt-out)."""
    H = config.grab_headers(session); P = session["params"]
    now = int(time.time())
    try:
        res = api_post(config.URL_GET_LANDING_CAMPAIGN, H, P,
            {"campaign_scene": [], "view_flag": 1,
             "pagination": {"offset": 0, "limit": 50, "sort_type": 9}, "sc_page": 0}, kunci="data")
    except Exception as e:
        log(f"gagal ambil daftar campaign: {type(e).__name__}", level="error", modul="campaign")
        return []
    campaigns = (res.get("data") or {}).get("list") or []
    hasil = []
    for c in campaigns:
        cid, cname = c.get("id"), str(c.get("name", "")).strip()
        if keywords and not any(k.lower() in cname.lower() for k in keywords):
            continue
        try:
            r = api_post(config.URL_GET_SESSION_LIST, H, P,
                {"campaign_id": str(cid), "view_type": 0, "session_type": 0, "mechanic_label_ids": []},
                kunci="data", attempts=1)
        except Exception:
            continue   # campaign non-produk (err 1671500008) dll -> skip
        for s in (((r.get("data") or {}).get("general") or {}).get("product_session") or []):
            ns, ne = int(s.get("nomination_start_time", 0)), int(s.get("nomination_end_time", 0))
            ss, se = int(s.get("session_start_time", 0)), int(s.get("session_end_time", 0))
            aktif = (ns <= now <= ne) if window == "nominasi" else (ss <= now <= se)
            if aktif:
                hasil.append({
                    "campaign_id": str(cid), "campaign_name": cname,
                    "session_id": str(s.get("session_id")), "session_name": str(s.get("session_name", "")).strip(),
                    "session_start": ss, "session_end": se, "nomination_end": ne,
                })
    label = "buka nominasi" if window == "nominasi" else "sesi berjalan"
    log(f"{len(hasil)} {label}", level="detail", modul="campaign")
    return hasil


# ── BACA: produk yang SUDAH ternominasi di 1 sesi ──
def get_nominated(session, session_id, page_size=50):
    """{(item_id, model_id): {nomination_id, nominate_status, campaign_price}}."""
    H = config.grab_headers(session); P = session["params"]
    hasil = {}; page = 1
    while True:
        try:
            r = api_post(config.URL_GET_NOMINATED_LIST, H, P,
                {"session_id": str(session_id), "entity_type": [ENTITY_PRODUK], "entity_tab": 0,
                 "page_num": page, "page_size": page_size}, kunci="data")
        except AntiBotError:
            raise    # gagal permanen → biar caller (fakta_campaign) skip semua sesi, jangan telen
        except Exception:
            break
        ents = ((r.get("data") or {}).get("recruiting_entities")) or []
        for e in ents:
            prod = e.get("product") or {}
            iid = str(prod.get("item_id", ""))
            for m in (prod.get("models") or []):
                hasil[(iid, str(m.get("model_id", "")))] = {
                    "nomination_id": str(m.get("nomination_id", "")),
                    "nominate_status": m.get("nominate_status"),
                    "campaign_price": m.get("campaign_price"),
                }
        if len(ents) < page_size:
            break
        page += 1
    return hasil


# ── NOMINASI: stage (preview/add) semua produk lalu submit (commit) ──
def nominate(session, session_id, produk_list, chunk=50):
    """produk_list = [{"item_id": id, "models": [model_id,...]}]. STAGE per-chunk lalu SUBMIT 1x.
    Return dict ringkasan {staged, committed_model, failed_model}."""
    if not produk_list:
        return {"staged": 0, "committed_model": 0, "failed_model": 0}
    H = config.grab_headers(session); P = session["params"]
    if getattr(config, "DRY_RUN", False):
        n = sum(len(p["models"]) for p in produk_list)
        log(f"(DRY) nominasi {len(produk_list)} produk ({n} model) → sesi {session_id}", level="warning", modul="campaign")
        return {"staged": len(produk_list), "committed_model": 0, "failed_model": 0}

    staged = 0
    for c in _chunks(produk_list, chunk):
        entities = [{"entity_type": ENTITY_PRODUK,
                     "product": {"item_id": str(p["item_id"]),
                                 "models": [{"item_id": str(p["item_id"]), "model_id": str(m)} for m in p["models"]]}}
                    for p in c]
        try:
            r = api_post(config.URL_PREVIEW_ADD, H, P,
                {"session_id": str(session_id), "preview_no": "",
                 "entity_list_data": {"recruiting_entities": entities}}, kunci="data")
            staged += int((r.get("data") or {}).get("product_success_num") or 0)
        except Exception as e:
            log(f"preview/add chunk gagal ({len(c)}): {type(e).__name__} — lanjut", level="error", modul="campaign")
    # COMMIT sekali
    committed = failed = 0
    try:
        r = api_post(config.URL_SUBMIT_NOMINATION, H, P,
            {"session_id": str(session_id), "entity_type": ENTITY_PRODUK, "confirm_risky": False}, kunci="data")
        pr = (r.get("data") or {}).get("product_result") or {}
        committed = int(pr.get("success_model_num") or 0); failed = int(pr.get("failed_model_num") or 0)
    except Exception as e:
        log(f"submit gagal: {type(e).__name__}", level="error", modul="campaign")
    log(f"sesi {session_id}: stage {staged} produk → commit {committed} model ({failed} gagal)", level="live", modul="campaign")
    return {"staged": staged, "committed_model": committed, "failed_model": failed}


# ── TAKEDOWN: keluarkan produk dari sesi (pakai nomination_id) ──
def takedown(session, session_id, nomination_ids, reason="Ingin mengubah produk", chunk=50):
    if not nomination_ids:
        return 0
    H = config.grab_headers(session); P = session["params"]
    if getattr(config, "DRY_RUN", False):
        log(f"(DRY) takedown {len(nomination_ids)} dari sesi {session_id}", level="warning", modul="campaign")
        return 0
    n = 0
    for c in _chunks([str(x) for x in nomination_ids], chunk):
        try:
            api_post(config.URL_OPT_OUT_NOMINATION, H, P,
                {"session_id": str(session_id), "nomination_ids": c, "reason": reason}, kunci="data")
            n += len(c)
            log(f"takedown {len(c)} dari sesi {session_id}", level="live", modul="campaign")
        except Exception as e:
            log(f"takedown chunk gagal ({len(c)}): {type(e).__name__}", level="error", modul="campaign")
    return n


# ── Sumber produk: SEMUA produk toko (item_id + model_id) dari harga_olah_data ──
def produk_toko(nama_toko, hanya_berstok=True):
    """[{"item_id": id, "models": [model_id,...]}] dari harga_olah_data."""
    from sqlalchemy import text
    from modules.db import get_engine
    sql = "select item_id, array_agg(distinct model_id) mids from harga_olah_data where toko=:t"
    if hanya_berstok:
        sql += " and stok > 0"
    sql += " group by item_id"
    with get_engine().connect() as c:
        rows = c.execute(text(sql), {"t": nama_toko}).fetchall()
    return [{"item_id": int(r.item_id), "models": [int(m) for m in r.mids]} for r in rows]


# ── ORKESTRATOR: nominasiin SEMUA produk toko ke 1 sesi ──
def nominate_semua(session, session_id, nama_toko):
    prod = produk_toko(nama_toko)
    log(f"nominasi {len(prod)} produk → sesi {session_id}…", level="detail", toko=nama_toko, modul="campaign")
    return nominate(session, session_id, prod)
