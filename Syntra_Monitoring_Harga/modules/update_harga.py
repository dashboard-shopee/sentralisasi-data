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
import colorama; colorama.init()
import requests
import config
from modules.api_util import api_post
from modules.discount_util import grab_semua_promo, grab_item_promo


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


# LANGKAH 4b — keluarkan produk dari SEMUA promo toko yang memuatnya, lalu ubah HARGA DASAR ke K.
# daftar = list of (baris, {promotion_id: harga_rupiah_sekarang})
def edit_harga_dasar(shop, session, daftar):
    hasil = {}
    if not getattr(config, "EDIT_HARGA_DASAR_AKTIF", False):
        for b, _ in daftar:
            hasil[b["row"]] = "Harga dasar dikunci (EDIT_HARGA_DASAR_AKTIF=False)"
        return hasil
    if config.DRY_RUN:
        for b, _ in daftar:
            hasil[b["row"]] = "[DRY] akan ubah harga dasar"
        return hasil
    sukses = gagal = 0
    for b, in_promos in daftar:
        item_id, model_id, K, row = b["item_id"], b["model_id"], b["harga_akhir"], b["row"]
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
                      "is_draft": False}, timeout=30,
            )
            data = r.json()
            if data.get("code") == 0:
                sukses += 1; hasil[row] = ""
                print(colorama.Fore.CYAN + f"[harga dasar diubah] [{shop}] - {item_id}/{model_id} -> {config.fmt_angka(K)}" + colorama.Style.RESET_ALL)
            else:
                gagal += 1
                pesan = data.get("user_message") or data.get("msg") or "ditolak Shopee"
                hasil[row] = "Tidak bisa ubah harga dasar - produk masih ikut promosi lain"
                print(colorama.Fore.YELLOW + f"[harga dasar - dilewati] [{shop}] - {item_id}/{model_id}: {str(pesan)[:110]}" + colorama.Style.RESET_ALL)
        except Exception as e:
            gagal += 1
            hasil[row] = f"Gagal ubah harga dasar: {type(e).__name__}"
            print(colorama.Fore.YELLOW + f"[harga dasar - dilewati] [{shop}] - {item_id}/{model_id}: {type(e).__name__}" + colorama.Style.RESET_ALL)
    print(colorama.Fore.CYAN + f"[harga dasar] [{shop}] - {sukses} berhasil, {gagal} dilewati (ikut promosi lain)." + colorama.Style.RESET_ALL)
    return hasil


# UPDATE HARGA — proses semua baris satu toko. Kembalikan list update kolom O (alasan).
def update_harga(shop, session, baris):
    alasan = {}

    if not getattr(config, "UPDATE_HARGA_TERVERIFIKASI", False):
        print(colorama.Fore.RED + f"[update harga] [{shop}] - DIKUNCI: set config.UPDATE_HARGA_TERVERIFIKASI=True dulu." + colorama.Style.RESET_ALL)
        return {}

    # 1) Ambil SEMUA promo toko (toko bisa punya lebih dari satu).
    promos = grab_semua_promo(shop, session)
    if not promos:
        # Tidak ada promo toko sama sekali -> bikin dari 0 + harga dasar (K>=H).
        print(colorama.Fore.CYAN + f"[update harga] [{shop}] - belum ada Promo Toko -> bikin dari 0 dulu." + colorama.Style.RESET_ALL)
        if not config.DRY_RUN:
            from modules.duplikat_promo import buat_promo_dari_nol
            buat_promo_dari_nol(shop, session, baris)
        perlu = [(b, {}) for b in baris
                 if b.get("sumber", "") in config.SUMBER_BOLEH_RUBAH
                 and b.get("harga_akhir") and (b.get("harga_awal") or 0)
                 and b["harga_akhir"] >= b["harga_awal"]]
        if perlu:
            alasan.update(edit_harga_dasar(shop, session, perlu))
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
    print(colorama.Fore.WHITE
          + f"[update harga] [{shop}] - {len(peta_promo)} variasi terdaftar di {len(pids)} promo toko."
          + colorama.Style.RESET_ALL)

    # 3) Susun perubahan
    upd_by_pid = {pid: [] for pid in pids}   # pid -> list entri update harga promo
    row_of = {}                              # (pid,item,model) -> row (untuk tandai gagal)
    perlu_harga_dasar = []                   # list (baris, {pid:harga})
    n = 0
    for b in baris:
        n += 1
        row = b["row"]; item_id = b["item_id"]; model_id = b["model_id"]
        K = b["harga_akhir"]; H = b.get("harga_awal") or 0
        sumber = b.get("sumber", "")
        key = (int(item_id), int(model_id))
        in_promos = peta_promo.get(key, {})

        if sumber not in config.SUMBER_BOLEH_RUBAH:
            alasan[row] = f"Tidak dirubah - harga dari {sumber or 'sumber tidak diketahui'}"
            continue
        if not K or K <= 0:
            alasan[row] = "Tidak ada target (kolom K kosong)"
            continue

        # K >= harga awal -> keluarkan dari semua promo + ubah harga dasar
        if H and K >= H:
            perlu_harga_dasar.append((b, in_promos))
            print(colorama.Fore.CYAN + f"[perlu harga dasar] [{shop}] [{n}] - {item_id}/{model_id} (K {config.fmt_angka(K)} >= harga awal {config.fmt_angka(H)})" + colorama.Style.RESET_ALL)
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
            print(colorama.Fore.GREEN + f"[rubah promo] [{shop}] [{n}] - {item_id}/{model_id} -> {config.fmt_angka(K)} (di {len(target_pids)} promo)" + colorama.Style.RESET_ALL)
        else:
            print(colorama.Style.DIM + colorama.Fore.WHITE + f"[sudah sesuai] [{shop}] [{n}] - {item_id}/{model_id} [{config.fmt_angka(K)}]" + colorama.Style.RESET_ALL)

    # 4) Harga dasar (K>=H)
    if perlu_harga_dasar:
        print(colorama.Fore.CYAN + f"[update harga] [{shop}] - {len(perlu_harga_dasar)} item -> UBAH HARGA DASAR (keluar promo dulu)." + colorama.Style.RESET_ALL)
        alasan.update(edit_harga_dasar(shop, session, perlu_harga_dasar))

    # 5) Kirim update harga promo per promo toko.
    #    Tiap chunk di-try sendiri -> 1 chunk gagal TIDAK menggugurkan chunk lain
    #    (Beverra punya puluhan chunk; dulu 1 error bikin sisanya tidak terkirim).
    total_sukses = total_gagal = total_error = 0
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
                print(colorama.Fore.RED + f"[update harga] [{shop}] - chunk promo {pid} gagal ({len(chunk)} item): {type(e).__name__} - lanjut." + colorama.Style.RESET_ALL)
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
            # Alasan dari pesan error Shopee (mis. "some item has participated in promotion").
            errs = data.get("error_list") or []
            pesan_err = str(errs[0].get("error_message", "")).strip() if (errs and isinstance(errs[0], dict)) else ""
            if "participat" in pesan_err.lower():
                alasan_gagal = "Sudah ikut promosi lain - tidak bisa ditambah ke promo toko"
            elif pesan_err:
                alasan_gagal = f"Gagal masuk promo toko: {pesan_err}"
            else:
                alasan_gagal = "Gagal masuk promo toko"
            for entri in chunk:
                mid = int(entri.get("model_id", 0)); iid = int(entri.get("item_id", 0))
                if mid in fmodels or iid in fitems:
                    total_gagal += 1
                    r = row_of.get((pid, iid, mid))
                    if r:
                        alasan[r] = alasan_gagal
    print(colorama.Fore.GREEN + f"[update harga] [{shop}] - promo: {total_sukses} sukses, {total_gagal} ditolak, {total_error} error-kirim." + colorama.Style.RESET_ALL)

    return alasan
