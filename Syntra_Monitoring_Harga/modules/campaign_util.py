"""
campaign_util.py — Helper untuk Campaign Shopee (Layer 2, penunjang Langkah 4).
Menggunakan browser context (fetch via run_js) untuk menghindari pemblokiran WAF 403.
"""
import time
import json
from modules.log_siklus import log
import config
from urllib.parse import urlencode


def api_post_browser(url, params, payload, kunci="data", attempts=4):
    """
    Mengirimkan request POST API Shopee dari dalam konteks Chrome yang sedang terbuka.
    Menghindari blokir TLS Fingerprint / Akamai WAF.

    ✅ (15 Jul, isolasi test) JS balikin STRING (JSON.stringify), BUKAN object JS mentah —
    versi lama (`return response.json()` langsung) bikin DrissionPage narik properti objek
    itu satu-satu via CDP (Runtime.getProperties), yg kebukti GAGAL ("js result parsing
    error") buat respons gede (mis. banyak produk ternominasi) & mandekin browser abis itu
    (retry berikutnya "Failed to fetch"). Respons berupa STRING dihindarin lewat jalur CDP
    object-walk itu sama sekali -> json.loads() polos di sisi Python.
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
        return response.text().then(txt => JSON.stringify({
            ok: response.ok, status: response.status, body: txt
        }));
    }).catch(error => {
        return JSON.stringify({ error: String(error && error.message || error) });
    });
    """

    delay = 2
    for attempt in range(attempts):
        try:
            raw = page.run_js(js_fetch, full_url, payload)
            if not isinstance(raw, str):
                raise ValueError(f"Respons JS bukan string: {type(raw)}")
            wrap = json.loads(raw)

            if "error" in wrap:
                raise RuntimeError(wrap["error"])
            if not wrap.get("ok"):
                raise RuntimeError(f"HTTP error {wrap.get('status')}")

            try:
                res = json.loads(wrap.get("body") or "")
            except (TypeError, ValueError):
                raise ValueError(f"Body bukan JSON valid: {(wrap.get('body') or '')[:200]}")
            if not isinstance(res, dict):
                raise ValueError(f"Respons bukan dict: {type(res)}")

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


def get_nominated_products(session, shop, campaign_id, session_id, tunggu=8):
    """
    Mengambil semua variasi/model produk yang sudah terdaftar di dalam satu sesi kampanye.

    ✅ (15 Jul, grilling) NAVIGASI BERSUNGGUH, BUKAN fetch injeksi — sniff 15 Jul kebukti
    `nominated_entity_list` WAJIB signature (x-sap-sec dkk) yg CUMA di-generate SDK Shopee
    asli pas render halaman detail sesi; fetch injeksi (requests ATAUPUN run_js) SELALU
    ditolak (90309999) walau headernya udah dibenerin. Tapi pas USER beneran buka halaman
    `/campaign/{id}/session/{id}`, request itu OTOMATIS di-fire Shopee sendiri & lolos mulus.
    Jadi: navigasiin browser ke situ, DENGERIN network (page.listen), tangkep response yg
    lewat OTOMATIS — bukan manggil endpointnya sendiri.
    ⚠️ Cuma nangkep request yg SEMPAT fire dalam window `tunggu` detik IDLE (reset tiap ada
    paket baru) — biasanya cukup buat 1 sesi (page render manggil beberapa kali). Kalau sesi
    punya nominasi lebih banyak dari yg ke-load otomatis (mis. butuh scroll/next-page manual
    di UI), sisanya ga kebaca — WARNING dicetak kalau itu kejadian.
    """
    from modules.session import get_page
    page = get_page()
    if not page:
        raise RuntimeError("Jendela browser Chrome belum terinisialisasi.")

    url = f"https://seller.shopee.co.id/portal/marketing/cmt-product/campaign/{campaign_id}/session/{session_id}?source=2"
    nominated_map = {}
    total_count = 0
    got = 0
    try:
        page.listen.start("nominated_entity_list")
        page.get(url)
        tangkapan = list(page.listen.steps(timeout=tunggu))
    finally:
        try:
            page.listen.stop()
        except Exception:
            pass

    for pkt in tangkapan:
        try:
            body = pkt.response.body
            if isinstance(body, str):
                body = json.loads(body)
            if not isinstance(body, dict):
                continue
        except Exception:
            continue
        data_obj = body.get("data")
        pi = body.get("page_info") or (data_obj or {}).get("page_info") or {}
        total_count = max(total_count, int(pi.get("total_count") or 0))
        if not isinstance(data_obj, dict):
            continue
        entities = data_obj.get("recruiting_entities") or []
        for entity in entities:
            prod = entity.get("product") or {}
            item_id = str(prod.get("item_id", ""))
            models = prod.get("models") or []
            got += len(models)
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

    if total_count and got < total_count:
        log(f"sesi {session_id}: cuma {got}/{total_count} nominasi ketangkep dari auto-load halaman (mgkn butuh scroll manual)",
            level="warning", toko=shop, modul="campaign")
    return nominated_map


def get_preview_nomination_ids(shop, campaign_id, session_id, tunggu=8):
    """
    Nangkep nomination_id produk yg LAGI di draft/preview (belum/baru di-submit) di 1 sesi,
    via navigasi + dengerin `preview_list` (BUKAN `nominated_entity_list`) — endpoint ini
    OTOMATIS fire pas halaman sesi di-buka NORMAL kalau sesi itu punya draft pending (tab
    default-nya "Menunggu Didaftarkan"), jadi bisa dibaca aman TANPA klik (klik tab manual
    kebukti live 15 Jul KENA verify/traffic/error — captcha WAF Shopee, bukan cuma 90309999).

    ✅ (15 Jul, grilling "gua mau full otomatis") INI KUNCI biar nominate() bisa nyatet
    nomination_id-nya SENDIRI pas baru staging (preview/add) — nomination_id udah kebentuk
    dari situ, gak perlu nunggu submit. Dicatet ke DB (harga_fakta_campaign_item) via
    SQL.upsert_fakta_campaign_item supaya takedown_campaign.py bisa lookup dari DB sendiri,
    gak perlu tanya nominated_entity_list (signature-locked) atau klik tab (kena captcha).

    Return {(item_id, model_id): {"nomination_id","nominate_status","campaign_price"}}.
    """
    from modules.session import get_page
    page = get_page()
    if not page:
        raise RuntimeError("Jendela browser Chrome belum terinisialisasi.")

    url = f"https://seller.shopee.co.id/portal/marketing/cmt-product/campaign/{campaign_id}/session/{session_id}?source=2"
    hasil = {}
    try:
        page.listen.start("preview_list")
        page.get(url)
        tangkapan = list(page.listen.steps(timeout=tunggu))
    finally:
        try:
            page.listen.stop()
        except Exception:
            pass

    for pkt in tangkapan:
        try:
            body = pkt.response.body
            if isinstance(body, str):
                body = json.loads(body)
            if not isinstance(body, dict):
                continue
        except Exception:
            continue
        data_obj = body.get("data") or {}
        entities = ((data_obj.get("entity_list_data") or {}).get("recruiting_entities")) or []
        for entity in entities:
            prod = entity.get("product") or {}
            item_id = str(prod.get("item_id", ""))
            for m in (prod.get("models") or []):
                model_id = str(m.get("model_id", ""))
                hasil[(item_id, model_id)] = {
                    "nomination_id": str(m.get("nomination_id", "")),
                    "nominate_status": m.get("nominate_status"),
                    "campaign_price": m.get("campaign_price"),
                }
    return hasil


def nominate(session, shop, session_id, produk_list, chunk=50, campaign_id=None):
    """Nominasi produk ke 1 sesi campaign via browser-context (STAGE preview/add per-chunk
    lalu SUBMIT 1x commit — sama alurnya kaya campaign.nominate, cuma lewat api_post_browser
    biar lolos anti-bot). produk_list = [{"item_id": id, "models": [model_id,...]}].
    ✅ (15 Jul, grilling) `fill_recommend_price: True` + `operate_start_time` — kebukti dari
    sniff aksi manual owner: TANPA ini, campaign_price selalu 0 -> submit_entity_online GAGAL
    100% ("Harga promo harus > 0"). Dengan flag ini, Shopee ITU SENDIRI yang ngitung harga
    rekomendasi per model (verified sniff: item yg sukses dapet campaign_price otomatis).
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
                 "entity_list_data": {"recruiting_entities": entities},
                 "fill_recommend_price": True, "operate_start_time": int(time.time())}, kunci="data")
            staged += int((r.get("data") or {}).get("product_success_num") or 0)
        except Exception as e:
            log(f"preview/add chunk gagal ({len(c)}): {type(e).__name__} — lanjut", level="error", toko=shop, modul="campaign")

    # ✅ catet nomination_id SENDIRI ke DB selagi masih draft (preview_list, aman/no-captcha) —
    # ini sumber kebenaran buat takedown_campaign.py nanti, bukan nominated_entity_list.
    if staged and campaign_id:
        try:
            from modules import sql_harga as SQL
            draf = get_preview_nomination_ids(shop, campaign_id, session_id)
            baris = [{"session_id": session_id, "item_id": iid, "model_id": mid, **info}
                     for (iid, mid), info in draf.items()]
            if baris:
                SQL.upsert_fakta_campaign_item(shop, baris)
                log(f"sesi {session_id}: {len(baris)} nomination_id draft dicatet ke DB", level="detail", toko=shop, modul="campaign")
        except Exception as e:
            log(f"gagal catet nomination_id draft: {type(e).__name__}: {str(e)[:120]}", level="error", toko=shop, modul="campaign")

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
