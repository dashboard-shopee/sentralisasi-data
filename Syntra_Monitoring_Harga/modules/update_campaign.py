"""
update_campaign.py — Langkah 4: Otomatisasi Kampanye Bulanan Shopee.
Mengelola pendaftaran (nomination) dan takedown (opt-out) produk dari Kampanye Shopee.
"""
import time
import re
import colorama; colorama.init()
import config
from modules.sheet_util import ambil_worksheet
from modules.komisi_util import proteksi_komisi
import modules.sheet_data as sheet_data
from modules.campaign_util import (
    get_open_sessions,
    get_nominated_products,
    takedown_products,
    api_post_browser
)


def _angka(v):
    """Bersihkan string angka Sheet -> int. '7.500' / '7500' / '' -> int atau 0."""
    if v in (None, "", "None"):
        return 0
    s = str(v).strip().replace(".", "").replace("Rp", "").replace(" ", "").replace(",", "")
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return 0


def nominate_with_limits(session, shop, session_id, items_dict, sheet_updates):
    """
    Mendaftarkan produk ke kampanye Shopee setelah memverifikasi batas harga (max entry price).
    Jika harga target (K) melebihi batas, akan diterapkan diskon otomatis maks 2%.
    Jika jumlah nominasi melebihi batas sisa kuota sesi kampanye, list akan dipotong secara otomatis.
    """
    items_to_process = {item_id: list(models) for item_id, models in items_dict.items()}

    while True:
        # Cek apakah items_to_process kosong
        if not any(items_to_process.values()):
            break

        recruiting_entities = []
        for item_id, models in items_to_process.items():
            if models:
                recruiting_entities.append({
                    "entity_type": 2,
                    "product": {
                        "item_id": str(item_id),
                        "models": [
                            {
                                "item_id": str(m["item_id"]),
                                "model_id": str(m["model_id"]),
                                "seller_offer_price": str(m["seller_offer_price"]),
                                "campaign_stock": str(m["campaign_stock"]),
                                "purchase_limit": "10"
                            } for m in models
                        ]
                    }
                })

        if not recruiting_entities:
            break

        preview_no = None
        limit_error_found = False
        allowed_count = 0

        # 1) Tambahkan ke Preview/Draft (Lewat browser fetch)
        try:
            add_res = api_post_browser(
                config.URL_PREVIEW_ADD,
                session["params"],
                {
                    "session_id": str(session_id),
                    "preview_no": "",
                    "entity_list_data": {
                        "recruiting_entities": recruiting_entities
                    },
                    "fill_recommend_price": False,
                    "operate_start_time": int(time.time())
                },
                kunci="data"
            )
            preview_no = add_res.get("data", {}).get("preview_no")
        except Exception as e:
            err_msg = str(e)
            if "329400028" in err_msg:
                match = re.search(r"and (\d+) products? more", err_msg)
                if match:
                    allowed_count = int(match.group(1))
                else:
                    allowed_count = max(len(recruiting_entities) // 2, 1)
                limit_error_found = True
            else:
                print(colorama.Fore.RED + f"[campaign] [{shop}] - Gagal add_to_preview: {e}" + colorama.Style.RESET_ALL)
                return

        # Handle jika kuota campaign penuh
        if limit_error_found:
            if allowed_count == 0:
                print(colorama.Fore.YELLOW + f"[campaign] [{shop}] - Sesi kampanye penuh (0 slot tersisa). Melewati sisa pendaftaran." + colorama.Style.RESET_ALL)
                for item_id, models in items_to_process.items():
                    for m in models:
                        sheet_updates.append({"range": f"{config.KOL['alasan']}{m['row']}", "values": [["Gagal daftar - kuota sesi kampanye penuh"]]})
                return

            print(colorama.Fore.YELLOW + f"[campaign] [{shop}] - Kuota sesi hampir habis. Mengurangi jumlah nominasi ke {allowed_count} model..." + colorama.Style.RESET_ALL)
            sliced_items = {}
            count = 0
            for item_id, models in items_to_process.items():
                for m in models:
                    if count < allowed_count:
                        sliced_items.setdefault(item_id, []).append(m)
                        count += 1
                    else:
                        sheet_updates.append({"range": f"{config.KOL['alasan']}{m['row']}", "values": [["Gagal daftar - kuota sesi kampanye penuh"]]})
            
            items_to_process = sliced_items
            continue  # Coba lagi dengan data yang sudah di-slice

        break

    if not preview_no:
        return

    # 2) Ambil daftar draft preview untuk memeriksa limit harga kampanye
    try:
        preview_res = api_post_browser(
            config.URL_PREVIEW_LIST,
            session["params"],
            {
                "session_id": str(session_id),
                "entity_type": [2]
            },
            kunci="data"
        )
    except Exception as e:
        print(colorama.Fore.RED + f"[campaign] [{shop}] - Gagal get_preview_list: {e}" + colorama.Style.RESET_ALL)
        return

    entities = preview_res.get("data", {}).get("entity_list_data", {}).get("recruiting_entities") or []
    
    # Bangun map pencocokan model asli
    orig_models = {}
    for item_id, models in items_to_process.items():
        for m in models:
            orig_models[(str(item_id), str(m["model_id"]))] = m

    models_to_submit = []
    has_changes = False

    for entity in entities:
        prod = entity.get("product") or {}
        item_id = str(prod.get("item_id", ""))
        models = prod.get("models") or []
        
        valid_models_for_item = []
        for m in models:
            m_id = str(m.get("model_id", ""))
            key = (item_id, m_id)
            if key not in orig_models:
                continue

            orig_m = orig_models[key]
            row_num = orig_m["row"]
            K = orig_m["K"]

            pricing_info = m.get("pricing_application_info") or {}
            max_price_micro = pricing_info.get("max_campaign_entry_price")
            our_price_micro = orig_m["seller_offer_price"]

            if max_price_micro is not None and our_price_micro > max_price_micro:
                max_price = max_price_micro / 100000.0
                discount_pct = (K - max_price) / float(K)

                if discount_pct <= config.CAMPAIGN_DISCOUNT_TOLERANCE:
                    # Terapkan max_campaign_entry_price karena masih dalam toleransi 2%
                    updated_price_micro = max_price_micro
                    valid_models_for_item.append({
                        "item_id": item_id,
                        "model_id": m_id,
                        "seller_offer_price": str(updated_price_micro),
                        "campaign_stock": str(orig_m["campaign_stock"]),
                        "purchase_limit": "10"
                    })
                    has_changes = True
                    disc_pct_rounded = 1 if discount_pct <= 0.01 else 2
                    print(colorama.Fore.GREEN 
                          + f"[campaign] [{shop}] - Model {item_id}/{m_id} SKU {orig_m['sku_raw']}: K ({K}) > limit ({max_price}). Diskon {disc_pct_rounded}% diterapkan ({int(max_price)})" 
                          + colorama.Style.RESET_ALL)
                    sheet_updates.append({"range": f"{config.KOL['alasan']}{row_num}", "values": [[f"Daftar campaign (diskon {disc_pct_rounded}%)"]]})
                else:
                    # Kebutuhan diskon melebihi toleransi 2%, lewati model ini
                    reason = f"Gagal daftar - butuh diskon >2% untuk masuk campaign (K={K}, max={int(max_price)})"
                    sheet_updates.append({"range": f"{config.KOL['alasan']}{row_num}", "values": [[reason]]})
                    print(colorama.Fore.RED + f"[campaign] [{shop}] - Model {item_id}/{m_id} SKU {orig_m['sku_raw']}: {reason}" + colorama.Style.RESET_ALL)
            else:
                # Harga K aman di bawah limit campaign
                valid_models_for_item.append({
                    "item_id": item_id,
                    "model_id": m_id,
                    "seller_offer_price": str(our_price_micro),
                    "campaign_stock": str(orig_m["campaign_stock"]),
                    "purchase_limit": "10"
                })
                sheet_updates.append({"range": f"{config.KOL['alasan']}{row_num}", "values": [["Daftar campaign (diskon 0%)"]]})

        if valid_models_for_item:
            models_to_submit.append({
                "entity_type": 2,
                "product": {
                    "item_id": item_id,
                    "models": valid_models_for_item
                }
            })

    if not models_to_submit:
        return

    # 3) Jika ada penyesuaian harga atau pemotongan, update draft previewnya dulu
    if has_changes:
        try:
            api_post_browser(
                config.URL_PREVIEW_ADD,
                session["params"],
                {
                    "session_id": str(session_id),
                    "preview_no": preview_no,
                    "entity_list_data": {
                        "recruiting_entities": models_to_submit
                    },
                    "fill_recommend_price": False,
                    "operate_start_time": int(time.time())
                },
                kunci="data"
            )
        except Exception as e:
            print(colorama.Fore.RED + f"[campaign] [{shop}] - Gagal update draft preview: {e}" + colorama.Style.RESET_ALL)
            return

    # 4) Submit draft secara resmi
    try:
        submit_res = api_post_browser(
            config.URL_SUBMIT_NOMINATION,
            session["params"],
            {
                "session_id": str(session_id),
                "entity_type": 2,
                "confirm_risky": False
            },
            kunci="data"
        )
        prod_res = submit_res.get("data", {}).get("product_result") or {}
        success_count = prod_res.get("success_model_num", 0)
        failed_count = prod_res.get("failed_model_num", 0)
        print(colorama.Fore.GREEN
              + f"[campaign] [{shop}] - Berhasil submit {success_count} model (Gagal: {failed_count}) di sesi {session_id}"
              + colorama.Style.RESET_ALL)
    except Exception as e:
        print(colorama.Fore.RED + f"[campaign] [{shop}] - Gagal submit_entity_online: {e}" + colorama.Style.RESET_ALL)


def update_campaign(shop, session, baris):
    """
    Logika utama Langkah 4: otomatisasi pendaftaran & takedown kampanye bulanan Shopee.
    """
    sheet_updates = []
    
    # 1) Ambil daftar sesi kampanye terbuka untuk toko ini
    sessions = get_open_sessions(session, shop)
    if not sessions:
        return []

    # 2) Dapatkan data master stok dan penjualan harian dari tab ALL PRODUK
    try:
        ws_all = ambil_worksheet(config.TAB_ALL_PRODUK)
        all_rows = ws_all.get_all_values()
    except Exception as e:
        print(colorama.Fore.RED + f"[campaign] [{shop}] - Gagal membaca tab ALL PRODUK: {e}" + colorama.Style.RESET_ALL)
        return []

    all_produk_map = {}
    for i, row in enumerate(all_rows):
        if i < 2:  # baris 1-2 header
            continue
        if len(row) > 7:
            sku = str(row[1]).strip().lower()
            stok = _angka(row[5])
            sales = _angka(row[7])  # kolom H ('Totasl Sales')
            if sku:
                all_produk_map[sku] = {"stok": stok, "sales": sales}

    # 3) Dapatkan proteksi komisi
    try:
        prot = proteksi_komisi()
    except Exception:
        prot = {}

    shop_display_name = config.SHOP_DATABASE[shop]["name"]

    # 4) Proses tiap sesi kampanye terbuka
    for s in sessions:
        session_id = s["session_id"]
        session_name = s["session_name"]
        print(colorama.Fore.WHITE + f"[campaign] [{shop}] - Memproses sesi: {session_name}" + colorama.Style.RESET_ALL)

        # Ambil semua produk yang sudah dinominasikan di sesi ini
        nominated_map = get_nominated_products(session, shop, session_id)

        nomination_ids_to_takedown = []
        items_to_nominate = {}

        for b in baris:
            item_id = str(b["item_id"])
            model_id = str(b["model_id"])
            sku = b["sku"]
            K = b["harga_akhir"]
            H = b["harga_awal"]
            row_num = b["row"]

            # Cek proteksi komisi
            sku_upper = str(sku).strip().upper()
            if shop_display_name in prot and sku_upper in prot[shop_display_name]["skus"]:
                continue

            sku_lower = str(sku).strip().lower()
            all_info = all_produk_map.get(sku_lower, {"stok": 0, "sales": 0})
            stok_real = all_info["stok"]
            sales_total = all_info["sales"]
            sales_per_day = sales_total / 30.0

            is_nominated = (item_id, model_id) in nominated_map

            if is_nominated:
                # Logika Takedown
                nom_info = nominated_map[(item_id, model_id)]
                nomination_id = nom_info["nomination_id"]
                current_nominated_price = nom_info["campaign_price"] / 100000

                # Cek pengecualian takedown
                is_override = stok_real > (sales_per_day * 5.0)

                takedown_reason = None
                if not is_override:
                    if stok_real <= 20:
                        takedown_reason = f"Takedown - stok ({stok_real}) <= 20"
                    elif stok_real < sales_per_day:
                        takedown_reason = f"Takedown - stok ({stok_real}) < sales per day ({sales_per_day:.2f})"

                if not takedown_reason:
                    if K is not None and H is not None:
                        if K >= H:
                            takedown_reason = f"Takedown - harga target K ({K}) >= harga awal H ({H})"
                        else:
                            # Cek kesesuaian harga target K dengan harga terdaftar (toleransi diskon maks 2%)
                            diff_pct = (K - current_nominated_price) / float(K)
                            if not (0 <= diff_pct <= config.CAMPAIGN_DISCOUNT_TOLERANCE):
                                takedown_reason = f"Takedown - harga K ({K}) tidak sesuai dengan harga terdaftar ({int(current_nominated_price)})"

                if takedown_reason:
                    nomination_ids_to_takedown.append(nomination_id)
                    sheet_updates.append({"range": f"{config.KOL['alasan']}{row_num}", "values": [[takedown_reason]]})
                    print(colorama.Fore.YELLOW 
                          + f"[campaign] [{shop}] - Model {item_id}/{model_id} SKU {sku}: {takedown_reason}" 
                          + colorama.Style.RESET_ALL)
            else:
                # Logika Pendaftaran (Nomination)
                if K is not None and H is not None:
                    if K < H and stok_real >= 50:
                        # Tentukan alokasi stok kampanye berdasarkan stok real
                        if stok_real >= 1000:
                            campaign_stock = 100
                        elif stok_real >= 500:
                            campaign_stock = 50
                        elif stok_real >= 250:
                            campaign_stock = 25
                        else:
                            campaign_stock = 5

                        items_to_nominate.setdefault(item_id, []).append({
                            "item_id": item_id,
                            "model_id": model_id,
                            "seller_offer_price": K * 100000, # micro-unit
                            "campaign_stock": campaign_stock,
                            "row": row_num,
                            "K": K,
                            "sku_raw": sku
                        })

        # Eksekusi Takedown produk
        if nomination_ids_to_takedown:
            takedown_products(session, shop, session_id, nomination_ids_to_takedown)

        # Eksekusi Pendaftaran produk dengan memverifikasi limit harga kampanye
        if items_to_nominate:
            nominate_with_limits(session, shop, session_id, items_to_nominate, sheet_updates)

    return sheet_updates
