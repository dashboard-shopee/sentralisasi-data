"""
update_harga.py — Layer 4 (LANGKAH 2).

Rubah harga berdasarkan kolom K (harga akhir):
  - Hanya untuk sumber (kolom N) "Promo Toko" / "Harga Awal" (config.SUMBER_BOLEH_RUBAH).
  - K < harga awal  -> set harga promo = K di SEMUA promo toko yang memuat produk
                       (toko bisa punya >1 promo toko). Kalau belum ikut promo toko
                       manapun -> daftarkan ke promo toko utama.
  - K >= harga awal -> promo mustahil: KELUARKAN produk dari SEMUA promo toko,
                       lalu ubah HARGA DASAR ke K (Langkah 4b).

Harga promo = micro-unit (×FAKTOR_HARGA). Harga dasar (quick edit) = STRING rupiah.
Kolom O diisi alasan kalau harga tidak/belum bisa dirubah ("" = berhasil/sesuai).
"""
import requests
import config
from modules.api_util import api_post
from modules.discount_util import grab_semua_promo, grab_item_promo
from modules.log_siklus import log, catat


def _chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def grab_payload(promotion_id, entries):
    return {"promotion_id": promotion_id, "discount_model_list": entries}


# Satu entri discount_model_list. harga = RUPIAH (dikali FAKTOR di sini).
def _entry(item_id, model_id, harga_rupiah, status):
    return {
        "item_id": item_id, "model_id": model_id,
        "promotion_price": int(harga_rupiah) * config.FAKTOR_HARGA,
        "user_item_limit": 0, "status": status, "promotion_stock": 0,
    }


def _updates_alasan(alasan):
    kol_o = config.KOL.get("alasan", "O")
    return [{"range": f"{kol_o}{row}", "values": [[teks]]} for row, teks in alasan.items()]


# Jenis promo yang SUDAH punya handler takedown otomatis (bisa dikeluarkan bot).
# (Campaign lewat browser-context; masih perlu verifikasi live.)
_TAKEDOWN_OTOMATIS = {"Promo Toko", "Flash Sale", "Campaign"}


# LANGKAH 4b — keluarkan produk dari SEMUA promo (toko + flash sale + dll) lalu ubah HARGA DASAR ke K.
# Harga dasar TIDAK bisa diubah kalau produk masih nyangkut promosi/campaign apa pun,
# jadi takedown dulu: Promo Toko + Flash Sale otomatis; Paket Diskon/Garansi/Campaign
# (belum ada endpoint takedown) -> ditandai jelas di alasan biar bisa ditindak.
# daftar = list of (baris, {promotion_id: harga_rupiah_sekarang})
def edit_harga_dasar(shop, session, daftar, nama_toko=None):
    hasil = {}
    if not getattr(config, "EDIT_HARGA_DASAR_AKTIF", False):
        for b, _ in daftar:
            hasil[b["row"]] = "Harga dasar dikunci (EDIT_HARGA_DASAR_AKTIF=False)"
        return hasil

    # Konteks promo tiap item (dari grab) -> tahu promo apa saja yg nyangkut.
    from modules.sql_harga import baca_promo_item
    kunci = {(b["item_id"], b["model_id"]) for b, _ in daftar}
    promo_item = baca_promo_item(nama_toko or shop, kunci)

    # TAKEDOWN FLASH SALE (semua item base-edit yang ikut flash sale) — sekali jalan.
    fs_kunci = {k for k in kunci if "Flash Sale" in promo_item.get(k, set())}
    if fs_kunci:
        try:
            from modules.flash_sale import takedown_items as fs_takedown
            fs_takedown(session, shop, nama_toko or shop, fs_kunci)
        except Exception as e:
            log(f"takedown flash sale gagal: {type(e).__name__}", level="error", fase="F2", toko=shop, modul="harga")

    # TAKEDOWN CAMPAIGN (browser-context) — item base-edit yang ikut campaign bulanan.
    # ⚠️ gate MODUL_AKTIF: buka_page_toko (browser baru) kebukti (15 Jul) NGERUSAK token
    # sesi `requests` yg lagi dipake — jangan jalan kalau campaign dimatiin.
    camp_kunci = {k for k in kunci if any("Campaign" in j for j in promo_item.get(k, set()))} \
        if "campaign" in config.MODUL_AKTIF else set()
    if camp_kunci:
        try:
            from modules.takedown_campaign import takedown_dari_campaign
            idx = (config.SHOP_DATABASE.get(shop) or {}).get("i", 0)
            takedown_dari_campaign(session, shop, idx, camp_kunci, nama_toko=nama_toko or shop)
        except Exception as e:
            log(f"takedown campaign gagal: {type(e).__name__}", level="error", fase="F2", toko=shop, modul="harga")

    if config.DRY_RUN:
        for b, _ in daftar:
            key = (b["item_id"], b["model_id"])
            blocker = promo_item.get(key, set()) - _TAKEDOWN_OTOMATIS
            hasil[b["row"]] = (f"[DRY] takedown {', '.join(sorted(promo_item.get(key, set()))) or 'promo'} lalu ubah harga dasar"
                               + (f" | BLOCKER manual: {', '.join(sorted(blocker))}" if blocker else ""))
        return hasil
    sukses = gagal = 0
    for b, in_promos in daftar:
        item_id, model_id, K, row = b["item_id"], b["model_id"], b["harga_akhir"], b["row"]
        key = (item_id, model_id)
        blocker = promo_item.get(key, set()) - _TAKEDOWN_OTOMATIS   # jenis tanpa handler
        try:
            # 1) keluarkan dari SEMUA promo toko yang memuat produk ini
            for pid, harga in in_promos.items():
                try:
                    api_post(config.URL_UPDATE_HARGA, config.grab_headers(session), session["params"],
                             grab_payload(pid, [_entry(item_id, model_id, harga or 1, config.STATUS_NONAKTIF)]),
                             kunci="data", attempts=1)
                except Exception:
                    pass
            # 2) ubah harga dasar (request langsung, cek code, tanpa retry)
            r = requests.post(
                config.URL_EDIT_HARGA_DASAR, params=session["params"], headers=config.grab_headers(session),
                json={"product_id": item_id, "product_info": {"model_list": [{"id": model_id, "price": str(K)}]},
                      "is_draft": False}, timeout=(15, 30),   # (connect, read) anti-hang SSL
            )
            data = r.json()
            if data.get("code") == 0:
                sukses += 1; hasil[row] = ""
                log(f"harga dasar {item_id}/{model_id} → {config.fmt_angka(K)}", level="live", fase="F2", toko=shop, modul="harga")
            else:
                gagal += 1
                pesan = data.get("user_message") or data.get("msg") or "ditolak Shopee"
                if blocker:
                    hasil[row] = f"Harga dasar keblok {', '.join(sorted(blocker))} - perlu takedown (belum otomatis)"
                else:
                    hasil[row] = "Tidak bisa ubah harga dasar - produk masih ikut promosi lain"
                log(f"harga dasar {item_id}/{model_id} dilewati: {str(pesan)[:90]}", level="warning", fase="F2", toko=shop, modul="harga")
        except Exception as e:
            gagal += 1
            hasil[row] = f"Gagal ubah harga dasar: {type(e).__name__}"
            log(f"harga dasar {item_id}/{model_id} dilewati: {type(e).__name__}", level="warning", fase="F2", toko=shop, modul="harga")
    if sukses or gagal:
        catat(f"{sukses} harga dasar diubah, {gagal} dilewati", status="live" if sukses else "skip",
              fase="F2", toko=shop, modul="harga", detail={"sukses": sukses, "gagal": gagal, "jenis": "harga_dasar"})
    return hasil


# UPDATE HARGA — proses semua baris satu toko. Kembalikan list update kolom O (alasan).
# Target harga tiap baris = b["harga_akhir"] (= Harga Diskon), pembanding b["harga_real"].
def update_harga(shop, session, baris, nama_toko=None):
    alasan = {}
    nama_toko = nama_toko or shop     # kunci toko utk state (samakan dgn konteks/olah_data)

    if not getattr(config, "UPDATE_HARGA_TERVERIFIKASI", False):
        log("DIKUNCI: set config.UPDATE_HARGA_TERVERIFIKASI=True dulu.", level="error", fase="F2", toko=shop, modul="harga")
        return {}

    # 1) Ambil SEMUA promo toko (toko bisa punya lebih dari satu).
    promos = grab_semua_promo(shop, session)
    if not promos:
        # Tidak ada promo toko sama sekali -> bikin dari 0 + harga dasar (K>=H).
        log("belum ada Promo Toko → bikin dari 0 dulu.", level="detail", fase="F2", toko=shop, modul="harga")
        if not config.DRY_RUN:
            from modules.duplikat_promo import buat_promo_dari_nol
            buat_promo_dari_nol(shop, session, baris)
        perlu = [(b, {}) for b in baris
                 if b.get("sumber", "") in config.SUMBER_BOLEH_RUBAH
                 and b.get("harga_akhir") and (b.get("harga_awal") or 0)
                 and b["harga_akhir"] >= b["harga_awal"]]
        if perlu:
            alasan.update(edit_harga_dasar(shop, session, perlu, nama_toko=nama_toko))
        return alasan

    pids = [p["promotion_id"] for p in promos]
    # promo toko UTAMA (untuk produk baru): cocok NAMA_PROMO, kalau tidak ada -> yang pertama (berjalan).
    primary = next((p["promotion_id"] for p in promos
                    if config.NAMA_PROMO.lower() in p["name"].lower()), pids[0])

    # 2) Peta produk -> di promo toko mana saja + harganya: {(item,model): {pid: harga}}
    peta_promo = {}
    for pid in pids:
        for it in grab_item_promo(shop, session, pid):
            if it.get("status") == config.STATUS_AKTIF and it.get("item_id"):
                key = (int(it["item_id"]), int(it["model_id"]))
                peta_promo.setdefault(key, {})[pid] = int(it["promotion_price"]) // config.FAKTOR_HARGA
    log(f"{len(peta_promo)} variasi terdaftar di {len(pids)} promo toko.", level="detail", fase="F2", toko=shop, modul="harga")

    # CATATAN: variasi STOK 0 di PROMO TOKO SENGAJA TIDAK dikeluarkan (biar tetap ikut
    # promo saat restock). Takedown stok-0 hanya untuk Campaign/Flash Sale (yang menahan
    # stok terpisah) -> ditangani terpisah di run.py, bukan di sini.
    upd_by_pid = {pid: [] for pid in pids}   # pid -> list entri update harga promo

    # 3) Susun perubahan
    row_of = {}                              # (pid,item,model) -> row (untuk tandai gagal)
    perlu_harga_dasar = []                   # list (baris, {pid:harga})
    takedown_sumber = {}                     # jenis -> set(key) promo penindih yg perlu di-takedown lalu koreksi
    n = 0
    for b in baris:
        n += 1
        row = b["row"]; item_id = b["item_id"]; model_id = b["model_id"]
        K = b["harga_akhir"]; H = b.get("harga_awal") or 0
        sumber = b.get("sumber", "")
        key = (int(item_id), int(model_id))
        in_promos = peta_promo.get(key, {})

        if not K or K <= 0:
            alasan[row] = "Tidak ada Harga Diskon (target kosong)"
            continue

        # SHORT-CIRCUIT — Harga Real (harga_tampil Fase 1) sudah = Harga Diskon -> tidak perlu diubah
        # (apa pun sumbernya; termasuk Garansi/Promo yang kebetulan sudah pas).
        real = b.get("harga_real", 0)
        if real and real == K:
            alasan[row] = ""      # sudah sesuai
            log(f"[{n}] {item_id}/{model_id} real=diskon {config.fmt_angka(K)} (sesuai)", level="detail", fase="F2", toko=shop, modul="harga")
            continue

        # Harga real != target -> PERLU KOREKSI. Tangani sesuai SUMBER harga tampil:
        #   Promo Toko / Harga Awal        -> lanjut koreksi (promo toko / harga dasar)
        #   Campaign                       -> takedown dulu, lalu koreksi (fall-through)
        #   Paket Diskon / Promosi Lain    -> FLAG "perlu takedown" (endpoint belum ada, PR)
        #   Garansi Harga Terbaik / lainnya-> SKIP (ditangani PR terpisah: auto-lower/opt-out)
        if sumber not in config.SUMBER_BOLEH_RUBAH:
            if sumber in config.SUMBER_TAKEDOWN_OTOMATIS:
                takedown_sumber.setdefault(sumber, set()).add(key)   # Campaign: takedown lalu koreksi (fall-through)
            elif sumber in config.SUMBER_BLOKIR_MANUAL:
                alasan[row] = f"Harga dikunci {sumber} - perlu takedown (endpoint belum ada)"
                continue
            else:
                alasan[row] = f"Dilewati - harga dari {sumber or 'sumber lain'} (ditangani PR terpisah)"
                continue

        # K >= harga awal -> keluarkan dari semua promo + ubah harga dasar
        if H and K >= H:
            perlu_harga_dasar.append((b, in_promos))
            log(f"[{n}] {item_id}/{model_id} perlu harga dasar (K {config.fmt_angka(K)} ≥ awal {config.fmt_angka(H)})", level="detail", fase="F2", toko=shop, modul="harga")
            continue

        # K < harga awal -> set harga promo = K di SEMUA promo toko yg memuat produk;
        # kalau belum di promo manapun -> daftarkan ke promo toko utama.
        target_pids = list(in_promos.keys()) or [primary]
        butuh = False
        for pid in target_pids:
            if in_promos.get(pid) == K:
                continue
            upd_by_pid[pid].append(_entry(item_id, model_id, K, config.STATUS_AKTIF))
            row_of[(pid, key[0], key[1])] = row
            butuh = True
        alasan[row] = ""
        if butuh:
            log(f"[{n}] {item_id}/{model_id} → {config.fmt_angka(K)} (di {len(target_pids)} promo)", level="ok", fase="F2", toko=shop, modul="harga")
        else:
            log(f"[{n}] {item_id}/{model_id} {config.fmt_angka(K)} (sudah sesuai)", level="detail", fase="F2", toko=shop, modul="harga")

    # 3b) TAKEDOWN promo PENINDIH (Campaign) sebelum harga toko/dasar berlaku -> harga ikut Harga Diskon.
    if takedown_sumber.get("Campaign"):
        camp = takedown_sumber["Campaign"]
        log(f"{len(camp)} item dikunci Campaign → takedown dulu.", level="live", fase="F2", toko=shop, modul="harga")
        try:
            from modules.takedown_campaign import takedown_dari_campaign
            idx = (config.SHOP_DATABASE.get(shop) or {}).get("i", 0)
            takedown_dari_campaign(session, shop, idx, camp, nama_toko=nama_toko or shop)
        except Exception as e:
            log(f"takedown campaign gagal: {type(e).__name__}", level="error", fase="F2", toko=shop, modul="harga")

    # 4) Harga dasar (K>=H)
    if perlu_harga_dasar:
        log(f"{len(perlu_harga_dasar)} item → UBAH HARGA DASAR (keluar promo dulu).", level="detail", fase="F2", toko=shop, modul="harga")
        alasan.update(edit_harga_dasar(shop, session, perlu_harga_dasar, nama_toko=nama_toko))

    # 5) Kirim update harga promo per promo toko.
    #    Tiap chunk di-try sendiri -> 1 chunk gagal TIDAK menggugurkan chunk lain
    #    (Beverra punya puluhan chunk; dulu 1 error bikin sisanya tidak terkirim).
    total_sukses = total_gagal = total_error = 0
    tolak_detail = {}     # pesan_error_ASLI_Shopee -> list "item/model" (buat diagnosa akurat)
    for pid, entries in upd_by_pid.items():
        for chunk in _chunks(entries, 50):
            if config.DRY_RUN:
                total_sukses += len(chunk)   # simulasi: anggap berhasil, tidak kirim
                continue
            try:
                data = api_post(config.URL_UPDATE_HARGA, config.grab_headers(session), session["params"],
                                grab_payload(pid, chunk), kunci="data")["data"]
            except Exception as e:
                # Chunk ini gagal terkirim -> tandai semua barisnya, LANJUT chunk berikutnya.
                total_error += len(chunk)
                for entri in chunk:
                    r = row_of.get((pid, int(entri.get("item_id", 0)), int(entri.get("model_id", 0))))
                    if r:
                        alasan[r] = "Gagal kirim ke promo toko (error koneksi/API) - coba lagi"
                log(f"chunk promo {pid} gagal ({len(chunk)} item): {type(e).__name__} — lanjut.", level="error", fase="F2", toko=shop, modul="harga")
                continue
            total_sukses += int(data.get("success_count", 0))
            # ⚠️ failed_item_list & failed_model_list = array ANGKA id polos (bukan dict,
            #    dan TIDAK sejajar indeks). Tandai baris bila model_id / item_id-nya gagal.
            fmodels, fitems = set(), set()
            for x in (data.get("failed_model_list") or []):
                try: fmodels.add(int(x.get("model_id")) if isinstance(x, dict) else int(x))
                except (TypeError, ValueError): pass
            for x in (data.get("failed_item_list") or []):
                try: fitems.add(int(x.get("item_id")) if isinstance(x, dict) else int(x))
                except (TypeError, ValueError): pass
            # Pesan error ASLI Shopee (kumpulkan SEMUA, bukan cuma [0]) -> diagnosa akurat.
            errs = data.get("error_list") or []
            pesan_list = [str(x.get("error_message", "")).strip()
                          for x in errs if isinstance(x, dict) and x.get("error_message")]
            pesan_err = pesan_list[0] if pesan_list else ""
            if "participat" in pesan_err.lower():
                alasan_gagal = "Sudah ikut promosi lain - tidak bisa ditambah ke promo toko"
            elif pesan_err:
                alasan_gagal = f"Ditolak Shopee: {pesan_err}"
            else:
                alasan_gagal = "Gagal masuk promo toko"
            for entri in chunk:
                mid = int(entri.get("model_id", 0)); iid = int(entri.get("item_id", 0))
                if mid in fmodels or iid in fitems:
                    total_gagal += 1
                    r = row_of.get((pid, iid, mid))
                    if r:
                        alasan[r] = alasan_gagal
                    # simpan alasan ASLI Shopee per item (buat ringkasan diagnosa)
                    tolak_detail.setdefault(pesan_err or "(tanpa pesan)", []).append(f"{iid}/{mid}")
    if total_sukses or total_gagal or total_error:
        catat(f"promo toko: {total_sukses} harga dirubah, {total_gagal} ditolak, {total_error} error-kirim",
              status="live" if total_sukses else ("gagal" if (total_gagal or total_error) else "ok"),
              fase="F2", toko=shop, modul="harga",
              detail={"sukses": total_sukses, "ditolak": total_gagal, "error": total_error, "jenis": "promo_toko",
                      "tolak": {m: len(c) for m, c in tolak_detail.items()} or None})
    # RINCIAN PENOLAKAN ASLI SHOPEE -> biar tahu blocker SEBENARNYA (bukan tebakan Fase 3).
    if tolak_detail:
        log("alasan asli penolakan Shopee:", level="warning", fase="F2", toko=shop, modul="harga")
        for msg, contoh in sorted(tolak_detail.items(), key=lambda kv: -len(kv[1])):
            log(f"  \"{msg[:120]}\"  ×{len(contoh)}  (contoh: {', '.join(contoh[:5])})", level="warning", fase="F2", toko=shop, modul="harga")

    return alasan
