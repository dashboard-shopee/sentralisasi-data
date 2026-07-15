"""
campaign_util.py — Helper untuk Campaign Shopee (Layer 2, penunjang Langkah 4).
Menggunakan browser context (fetch via run_js) untuk menghindari pemblokiran WAF 403.
"""
import time
from modules.log_siklus import log
import config
from urllib.parse import urlencode


def api_post_browser(url, params, payload, kunci="data", attempts=4):
    """
    Mengirimkan request POST API Shopee dari dalam konteks Chrome yang sedang terbuka.
    Menghindari blokir TLS Fingerprint / Akamai WAF.
    """
    from modules.session import get_page
    page = get_page()
    if not page:
        raise RuntimeError("Jendela browser Chrome belum terinisialisasi.")

    # Gabungkan url dengan query params
    full_url = url
    if params:
        query_str = urlencode(params)
        full_url = f"{url}&{query_str}" if "?" in url else f"{url}?{query_str}"

    js_fetch = """
    const url = arguments[0];
    const payload = arguments[1];
    return fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json, text/plain, */*'
        },
        body: JSON.stringify(payload)
    }).then(response => {
        if (!response.ok) {
            return { 'error': 'HTTP error ' + response.status, 'status': response.status };
        }
        return response.json();
    }).catch(error => {
        return { 'error': error.message };
    });
    """

    delay = 2
    for attempt in range(attempts):
        try:
            res = page.run_js(js_fetch, full_url, payload)
            if not isinstance(res, dict):
                raise ValueError(f"Respons bukan dict: {type(res)}")
            
            if "error" in res:
                raise RuntimeError(res["error"])
                
            code = res.get("code")
            msg = res.get("msg", "")

            # Jika terjadi error spesifik dari Shopee (code != 0)
            if code is not None and code != 0:
                # Simpan error agar bisa di-parse oleh caller (seperti error limit produk)
                raise RuntimeError(f"Shopee error {code}: {msg}")

            # Validasi kunci
            if kunci and kunci not in res:
                raise ValueError(f"Kunci '{kunci}' tidak ditemukan di response")
                
            return res
        except Exception as e:
            cuplikan = str(e)
            if attempt < attempts - 1:
                log(f"api_browser gagal → {cuplikan} | coba lagi dalam {delay}s ({attempt+1}/{attempts-1})", level="warning", modul="campaign")
                time.sleep(delay)
                delay = min(delay * 2, 20)
            else:
                raise RuntimeError(f"Gagal memanggil {url} via browser: {cuplikan}")


def get_open_sessions(session, shop, window="nominasi"):
    """
    Mengambil sesi kampanye (gajian sale, tanggal kembar, dll — cuma yg namanya cocok
    config.CAMPAIGN_KEYWORDS) via browser-context (anti-bot aman).
    window="nominasi" (default) -> sesi yg WINDOW NOMINASI-nya buka (buat DAFTAR produk).
    window="sesi"                -> sesi yg lagi BERJALAN (buat TAKEDOWN; nominasi bisa udah
                                    tutup tapi produk masih jalan & perlu di-opt-out).
    """
    from modules.session import get_page
    page = get_page()
    if page:
        # Arahkan browser ke marketing cmt portal agar memiliki referer asal yang sah
        log("mengarahkan browser ke Portal Campaign…", level="detail", toko=shop, modul="campaign")
        page.get("https://seller.shopee.co.id/portal/marketing/cmt/campaign?source=2")
        page.wait(2)

    open_sessions = []
    current_time = int(time.time())

    # 1) Ambil list kampanye landing page
    try:
        res = api_post_browser(
            config.URL_GET_LANDING_CAMPAIGN,
            session["params"],
            {
                "campaign_scene": [],
                "view_flag": 1,
                "pagination": {"offset": 0, "limit": 50, "sort_type": 9},
                "sc_page": 0
            },
            kunci="data"
        )
    except Exception as e:
        log(f"gagal fetch campaign list: {e}", level="error", toko=shop, modul="campaign")
        return []

    campaigns = res.get("data", {}).get("list") or []
    
    # 2) Filter kampanye berdasarkan nama
    for c in campaigns:
        name = str(c.get("name", "")).strip()
        campaign_id = c.get("id")
        
        cocok = False
        for kw in config.CAMPAIGN_KEYWORDS:
            if kw.lower() in name.lower():
                cocok = True
                break
        
        if not cocok:
            continue

        # 3) Fetch sesi di bawah kampanye yang cocok
        try:
            session_res = api_post_browser(
                config.URL_GET_SESSION_LIST,
                session["params"],
                {
                    "campaign_id": str(campaign_id),
                    "view_type": 0,
                    "session_type": 0,
                    "mechanic_label_ids": []
                },
                kunci="data"
            )
        except Exception as e:
            log(f"gagal fetch session untuk campaign {name}: {e}", level="error", toko=shop, modul="campaign")
            continue

        product_sessions = session_res.get("data", {}).get("general", {}).get("product_session") or []
        for s in product_sessions:
            s_name = str(s.get("session_name", "")).strip()
            s_id = s.get("session_id")
            nom_start = int(s.get("nomination_start_time", 0))
            nom_end = int(s.get("nomination_end_time", 0))
            sess_start = int(s.get("session_start_time", 0))
            sess_end = int(s.get("session_end_time", 0))

            aktif = (nom_start <= current_time <= nom_end) if window == "nominasi" \
                else (sess_start <= current_time <= sess_end)
            if aktif:
                open_sessions.append({
                    "campaign_id": str(campaign_id),
                    "campaign_name": name,
                    "session_id": str(s_id),
                    "session_name": s_name,
                    "nomination_start_time": nom_start,
                    "nomination_end_time": nom_end,
                    "session_start_time": sess_start,
                    "session_end_time": sess_end,
                })

    if open_sessions:
        log(f"{len(open_sessions)} sesi kampanye aktif untuk nominasi", level="detail", toko=shop, modul="campaign")
        for s in open_sessions:
            log(f"  sesi {s['session_name']} (ID={s['session_id']}) di bawah '{s['campaign_name']}'", level="detail", toko=shop, modul="campaign")
    else:
        log("tidak ada sesi kampanye aktif yang cocok saat ini", level="warning", toko=shop, modul="campaign")

    return open_sessions


def get_nominated_products(session, shop, session_id):
    """
    Mengambil semua variasi/model produk yang sudah terdaftar di dalam satu sesi kampanye.
    """
    nominated_map = {}
    page_num = 1
    page_size = 50

    while True:
        try:
            res = api_post_browser(
                config.URL_GET_NOMINATED_LIST,
                session["params"],
                {
                    "session_id": str(session_id),
                    "entity_type": [2],
                    "entity_tab": 0,
                    "page_num": page_num,
                    "page_size": page_size
                },
                kunci="page_info"  # Validasi dengan page_info
            )
        except Exception as e:
            log(f"gagal fetch nominated list hal {page_num}: {e}", level="error", toko=shop, modul="campaign")
            break

        data_obj = res.get("data") if isinstance(res, dict) else None
        if not data_obj or not isinstance(data_obj, dict):
            break

        entities = data_obj.get("recruiting_entities") or []
        for entity in entities:
            prod = entity.get("product") or {}
            item_id = str(prod.get("item_id", ""))
            models = prod.get("models") or []
            for m in models:
                model_id = str(m.get("model_id", ""))
                nomination_id = str(m.get("nomination_id", ""))
                nominate_status = m.get("nominate_status")
                campaign_price = m.get("campaign_price")

                nominated_map[(item_id, model_id)] = {
                    "nomination_id": nomination_id,
                    "nominate_status": nominate_status,
                    "campaign_price": campaign_price,
                }

        if len(entities) < page_size:
            break
        page_num += 1

    return nominated_map


def nominate(session, shop, session_id, produk_list, chunk=50):
    """Nominasi produk ke 1 sesi campaign via browser-context (STAGE preview/add per-chunk
    lalu SUBMIT 1x commit — sama alurnya kaya campaign.nominate, cuma lewat api_post_browser
    biar lolos anti-bot). produk_list = [{"item_id": id, "models": [model_id,...]}].
    Return {"staged","committed_model","failed_model"}."""
    if not produk_list:
        return {"staged": 0, "committed_model": 0, "failed_model": 0}
    if getattr(config, "DRY_RUN", False):
        n = sum(len(p["models"]) for p in produk_list)
        log(f"(DRY) nominasi {len(produk_list)} produk ({n} model) → sesi {session_id}", level="warning", toko=shop, modul="campaign")
        return {"staged": len(produk_list), "committed_model": 0, "failed_model": 0}

    staged = 0
    for i in range(0, len(produk_list), chunk):
        c = produk_list[i:i + chunk]
        entities = [{"entity_type": 2,
                     "product": {"item_id": str(p["item_id"]),
                                 "models": [{"item_id": str(p["item_id"]), "model_id": str(m)} for m in p["models"]]}}
                    for p in c]
        try:
            r = api_post_browser(config.URL_PREVIEW_ADD, session["params"],
                {"session_id": str(session_id), "preview_no": "",
                 "entity_list_data": {"recruiting_entities": entities}}, kunci="data")
            staged += int((r.get("data") or {}).get("product_success_num") or 0)
        except Exception as e:
            log(f"preview/add chunk gagal ({len(c)}): {type(e).__name__} — lanjut", level="error", toko=shop, modul="campaign")
    committed = failed = 0
    try:
        r = api_post_browser(config.URL_SUBMIT_NOMINATION, session["params"],
            {"session_id": str(session_id), "entity_type": 2, "confirm_risky": False}, kunci="data")
        pr = (r.get("data") or {}).get("product_result") or {}
        committed = int(pr.get("success_model_num") or 0); failed = int(pr.get("failed_model_num") or 0)
    except Exception as e:
        log(f"submit gagal: {type(e).__name__}", level="error", toko=shop, modul="campaign")
    log(f"sesi {session_id}: stage {staged} produk → commit {committed} model ({failed} gagal)", level="live", toko=shop, modul="campaign")
    return {"staged": staged, "committed_model": committed, "failed_model": failed}


def takedown_products(session, shop, session_id, nomination_ids):
    """
    Melakukan opt-out (takedown/hapus) produk/variasi dari kampanye Shopee.
    """
    if not nomination_ids:
        return True

    chunk_size = 50
    success = True
    for i in range(0, len(nomination_ids), chunk_size):
        chunk = nomination_ids[i:i + chunk_size]
        try:
            api_post_browser(
                config.URL_OPT_OUT_NOMINATION,
                session["params"],
                {
                    "session_id": str(session_id),
                    "nomination_ids": chunk,
                    "reason": "Ingin mengubah produk"
                },
                kunci="data"
            )
            log(f"takedown {len(chunk)} model dari sesi {session_id}", level="live", toko=shop, modul="campaign")
        except Exception as e:
            log(f"gagal opt-out chunk {i//chunk_size + 1}: {e}", level="error", toko=shop, modul="campaign")
            success = False
            
    return success
