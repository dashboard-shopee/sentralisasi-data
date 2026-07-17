"""
campaign_util.py — Helper untuk Campaign Shopee (Layer 2, penunjang Langkah 4).
Menggunakan browser context (fetch via run_js) untuk menghindari pemblokiran WAF 403.
"""
import time
import json
from modules.log_siklus import log
import config
from urllib.parse import urlencode


def _nama_display(shop):
    """username -> nama display; kalau udah display, balikin apa adanya."""
    info = config.SHOP_DATABASE.get(shop)
    return info["name"] if info else shop


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


def _api_post(session, url, payload, kunci="data", attempts=4):
    """Router jalur API campaign (16 Jul, S2 optimasi):
    - Browser-context LAGI KEBUKA → lewat browser (api_post_browser). Wajib, karena abis
      navigasi halaman, token SPC_CDS sesi requests jadi BASI (403) — lihat
      session.segarkan_abis_browser_context.
    - Browser GA kebuka → requests POLOS. Verif 16 Jul: preview/add + preview/edit +
      submit_entity_online + nominated/opt_out + get_landing_page_campaign_list +
      get_session_list semuanya LOLOS polos; cuma preview_list + nominated_entity_list
      (baca nomination_id) yg anti-bot (90309999) wajib navigate-listen.
    Efek: takedown per-jam (get_open_sessions + opt_out + DB) bisa jalan TANPA buka
    browser sama sekali — lebih cepet & sesi requests ga dibasiin."""
    from modules.session import get_page
    if get_page():
        return api_post_browser(url, session["params"], payload, kunci=kunci, attempts=attempts)
    from modules.api_util import api_post
    # ⚠️ jangan lempar session["headers"] mentah — hasil panen ngandung pseudo-header
    # HTTP/2 (":authority" dst) yg ditolak requests (InvalidHeader). Pakai header bersih
    # standar repo (config.grab_headers), sama kaya paket/voucher/garansi.
    return api_post(url, config.grab_headers(session), session["params"], payload, kunci=kunci, attempts=attempts)


def get_nomination_statistics(session, session_id):
    """Statistik nominasi 1 sesi via requests POLOS — BUKTI HIDUP MURAH tanpa browser
    (17 Jul, sniff ulang: payload wajib `campaign_scene`, bukan entity_type; verified live:
    nominated_count/seller_nominated_count kebaca polos). nominated_entity_list tetep
    signature-locked (90309999 walau payload identik page) — count ini penggantinya buat
    verifikasi naik/turun. Return dict data (nominated_count, pending_*, rejected_count, ...)."""
    try:
        r = _api_post(session, config.URL_STAT_NOMINASI,
                      {"session_id": str(session_id),
                       "campaign_scene": "CAMPAIGN_SCENE_PRODUCT_PROMOTION_CAMPAIGN"},
                      kunci="data", attempts=2)
        return r.get("data") or {}
    except Exception as e:
        log(f"statistik nominasi sesi {session_id} gagal: {type(e).__name__}", level="warning", modul="campaign")
        return {}


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
        res = _api_post(
            session,
            config.URL_GET_LANDING_CAMPAIGN,
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
            session_res = _api_post(
                session,
                config.URL_GET_SESSION_LIST,
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

        data_sr = session_res.get("data", {}) or {}
        product_sessions = list((data_sr.get("general", {}) or {}).get("product_session") or [])
        for grp in (data_sr.get("list") or []):
            product_sessions.extend(grp.get("product_session") or [])
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
                    "campaign_id": str(s.get("campaign_id") or campaign_id),
                    "campaign_name": name,
                    "session_id": str(s_id),
                    "session_name": s_name,
                    "nomination_start_time": nom_start,
                    "nomination_end_time": nom_end,
                    "session_start_time": sess_start,
                    "session_end_time": sess_end,
                    # (17 Jul, rekaman manual owner) get_session_list ternyata bawa COUNT
                    # nominasi per sesi — gratis, polos, 1 call. None kalau field ga ada.
                    "nominated_count": s.get("nominated_count"),
                    "pending_seller_count": s.get("pending_seller_count"),
                    "approved_count": s.get("approved_count"),
                    "rejected_count": s.get("rejected_count"),
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
                    "original_price": m.get("original_price"),
                    "max_entry_price": (m.get("pricing_application_info") or {}).get("max_campaign_entry_price"),
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

    ✅ (16 Jul, verif) nomination_id STABIL melewati staged(status 10)->committed(status 30):
    sniff bukti id yg SAMA muncul di preview_list (status 10) DAN nominated_entity_list
    (status 30). Jadi opt_out pakai id preview ini VALID — takedown-dari-DB desainnya benar.
    ⚠️ Kegagalan opt_out `10002 not found` = GEJALA SESI TERCEMAR (draft nyangkut / submit
    "1 gagal" berulang), BUKAN id preview-vs-committed. Testbed harus sesi BERSIH.

    ✅ (16 Jul, bedah sniff) preview_list juga bawa `pricing_application_info.
    max_campaign_entry_price` (= reference_price_by_shopee, micro) — CEILING harga campaign.
    Shopee CLAMP campaign_price ke ceiling ini (kebukti live: set 4432, committed 3825 =
    ceiling model itu). Ditangkep di sini sbg `max_entry_price` buat gate KPI di nominate().

    Return {(item_id, model_id): {"nomination_id","nominate_status","campaign_price",
    "max_entry_price"}}.
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
                    "max_entry_price": (m.get("pricing_application_info") or {}).get("max_campaign_entry_price"),
                }
    return hasil


def nominate(session, shop, session_id, produk_list, chunk=50, campaign_id=None):
    """Nominasi produk ke 1 sesi campaign via browser-context. Alur = alur UI manual owner
    (sniff): preview/add (STAGE) → preview_list (ambil nomination_id) → preview/edit (SET
    campaign_price + campaign_stock per nomination_id sesuai KPI) → submit (COMMIT).
      produk_list = [{"item_id": id, "models": [{"model_id": m, "campaign_price": <rupiah>,
                      "campaign_stock": <qty>}, ...]}].
    ✅ (16 Jul, spec owner) harga di-SET eksplisit per KPI (harga per-durasi sesi + stok tiered)
    lewat preview/edit — BUKAN cuma fill_recommend_price. campaign_price → micro (×FAKTOR_HARGA).
    fill_recommend_price di add tetap dipertahankan sbg baseline (cegah Rp0 kalau edit meleset).
    Return {"staged","committed_model","failed_model"}."""
    if not produk_list:
        return {"staged": 0, "committed_model": 0, "failed_model": 0}
    # peta harga(rupiah)+stok per (item,model) buat langkah preview/edit
    hs = {}
    for p in produk_list:
        for m in p["models"]:
            hs[(str(p["item_id"]), str(m["model_id"]))] = (m.get("campaign_price"), m.get("campaign_stock"))
    if getattr(config, "DRY_RUN", False):
        n = sum(len(p["models"]) for p in produk_list)
        log(f"(DRY) nominasi {len(produk_list)} produk ({n} model) → sesi {session_id} "
            f"(harga+stok per-KPI di-set via preview/edit)", level="warning", toko=shop, modul="campaign")
        return {"staged": len(produk_list), "committed_model": 0, "failed_model": 0}

    staged = 0
    preview_no = ""
    for i in range(0, len(produk_list), chunk):
        c = produk_list[i:i + chunk]
        entities = [{"entity_type": 2,
                     "product": {"item_id": str(p["item_id"]),
                                 "models": [{"item_id": str(p["item_id"]), "model_id": str(m["model_id"])} for m in p["models"]]}}
                    for p in c]
        try:
            r = _api_post(session, config.URL_PREVIEW_ADD,
                {"session_id": str(session_id), "preview_no": preview_no,
                 "entity_list_data": {"recruiting_entities": entities},
                 "fill_recommend_price": True, "operate_start_time": int(time.time())}, kunci="data")
            d = r.get("data") or {}
            staged += int(d.get("product_success_num") or 0)
            preview_no = str(d.get("preview_no") or preview_no)   # dipakai buat preview/edit
        except Exception as e:
            log(f"preview/add chunk gagal ({len(c)}): {type(e).__name__} — lanjut", level="error", toko=shop, modul="campaign")

    if not staged:
        log(f"sesi {session_id}: 0 produk ke-stage (semua ditolak preview/add) — skip bersih", level="warning", toko=shop, modul="campaign")
        return {"staged": 0, "committed_model": 0, "failed_model": 0}

    # nomination_id per (item,model) via preview_list (aman/no-captcha)
    draf = get_preview_nomination_ids(shop, campaign_id, session_id) if campaign_id else {}
    # catet ke DB (sumber takedown; campaign_price di-refresh grab harian abis edit)
    if draf:
        try:
            from modules import sql_harga as SQL
            baris = [{"session_id": session_id, "item_id": iid, "model_id": mid, **info}
                     for (iid, mid), info in draf.items()]
            if baris:
                SQL.upsert_fakta_campaign_item(_nama_display(shop), baris)
                log(f"sesi {session_id}: {len(baris)} nomination_id draft dicatet ke DB", level="detail", toko=shop, modul="campaign")
        except Exception as e:
            log(f"gagal catet nomination_id draft: {type(e).__name__}: {str(e)[:120]}", level="error", toko=shop, modul="campaign")

    # ⛔ GATE KPI harga vs CEILING Shopee (16 Jul, bedah sniff + verif live):
    # `max_entry_price` (preview_list) = harga maksimum campaign yg Shopee terima; harga
    # yg di-set LEBIH TINGGI bakal di-CLAMP turun ke ceiling (kebukti: set 4432, committed
    # 3825 = ceiling). Kalau harga KPI (target×faktor) > ceiling → diskon yg Shopee paksa
    # LEBIH DALEM dari KPI → model DILARANG ikut. Endpoint discard-draft GA ADA, jadi
    # jalur skip-bersih = ikut submit dulu → langsung opt_out (endpoint proven).
    lolos, langgar = {}, {}
    for (iid, mid), info in draf.items():
        nomid = info.get("nomination_id")
        hv = hs.get((str(iid), str(mid)))
        if not nomid or not hv:
            continue
        harga_rp, stok = hv
        ceiling = info.get("max_entry_price")
        if harga_rp and ceiling and int(round(harga_rp * config.FAKTOR_HARGA)) > int(ceiling):
            langgar[(iid, mid)] = info
        else:
            lolos[(iid, mid)] = info
    if langgar:
        log(f"sesi {session_id}: {len(langgar)} model GAGAL gate KPI (ceiling Shopee < target×faktor) "
            f"→ di-opt-out abis submit (skip bersih)", level="warning", toko=shop, modul="campaign")

    # SET harga (per-durasi sesi) + stok (tiered) per KPI via preview/edit — CUMA model lolos gate.
    # ⚠️ (16 Jul, verif live) entry HARGA dan STOK DIPISAH — persis alur sniff manual owner:
    # {nomination_ids, campaign_price_type, campaign_price} + {nomination_ids, campaign_stock,
    # purchase_limit}. Versi lama (gabung 1 entry) harga gak nyangkut — TAPI tes itu pakai harga
    # DI ATAS ceiling (mustahil nyangkut apapun formatnya); format pisah tetep dipake (sesuai sniff).
    infos = []
    for (iid, mid), info in lolos.items():
        nomid = info["nomination_id"]
        harga_rp, stok = hs[(str(iid), str(mid))]
        if harga_rp and harga_rp > 0:
            infos.append({"nomination_ids": [str(nomid)], "campaign_price_type": 1,
                          "campaign_price": str(int(round(harga_rp * config.FAKTOR_HARGA)))})
        if stok and stok > 0:
            infos.append({"nomination_ids": [str(nomid)], "campaign_stock": str(int(stok)),
                          "purchase_limit": str(int(stok))})
    if infos and preview_no:
        try:
            _api_post(session, config.URL_PREVIEW_EDIT,
                {"session_id": str(session_id), "preview_no": str(preview_no),
                 "update_product_preview_infos": infos, "types": [2]}, kunci="data")
            log(f"sesi {session_id}: SET harga+stok KPI ({len(infos)} entry pisah)", level="detail", toko=shop, modul="campaign")
        except Exception as e:
            log(f"preview/edit (set harga+stok) gagal: {type(e).__name__}: {str(e)[:120]}", level="error", toko=shop, modul="campaign")

    committed = failed = 0
    try:
        r = _api_post(session, config.URL_SUBMIT_NOMINATION,
            {"session_id": str(session_id), "entity_type": 2, "confirm_risky": False}, kunci="data")
        pr = (r.get("data") or {}).get("product_result") or {}
        committed = int(pr.get("success_model_num") or 0); failed = int(pr.get("failed_model_num") or 0)
    except Exception as e:
        log(f"submit gagal: {type(e).__name__}", level="error", toko=shop, modul="campaign")

    # Model gate-fail: GA di-opt-out inline (17 Jul, bukti hidup): abis submit, nominasi
    # NAHAN di status 10 (pending review) — opt_out di fase itu antara DITOLAK 329400012
    # ATAU lebih bahaya: code=0 TAPI item ga kecabut (FAKE SUCCESS, kebukti verif full-map).
    # Jalur benar: baris DB DIBIARIN → harga committed (= ceiling) < target×0.985 → diagnosa
    # per-jam nge-flag → takedown_dari_campaign nyabut begitu status 30 (approved).
    if langgar:
        log(f"sesi {session_id}: {len(langgar)} model gate-fail dibiarin ke-commit di harga ceiling — "
            f"takedown per-jam bakal nyabut begitu status 30 (opt_out ga mempan selama pending-review)",
            level="warning", toko=shop, modul="campaign")

    log(f"sesi {session_id}: stage {staged} produk → commit {committed} model ({failed} gagal, "
        f"{len(langgar)} gate-fail nunggu cabut per-jam)",
        level="live", toko=shop, modul="campaign")
    return {"staged": staged, "committed_model": committed, "failed_model": failed,
            "gate_langgar": len(langgar)}


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
            _api_post(
                session,
                config.URL_OPT_OUT_NOMINATION,
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
