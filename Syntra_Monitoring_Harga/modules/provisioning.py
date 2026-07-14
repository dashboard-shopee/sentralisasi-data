"""modules/provisioning.py — FASE 2 poin 5: PASANG/DAFTAR promo upsell (per-toko, per-modul).

Orkestrasi tipis di atas modul low-level yg SUDAH ada (paket_diskon/voucher/…). Semua DRY_RUN-aware
(modul low-level yg handle). IDEMPOTENT: paket/voucher yg dikelola bot dinamai/di-kode ber-prefix
`config.NAMA_UPSELL` biar ga bikin dobel tiap hari.

Sumber produk = `harga_olah_data` (hasil grab Fase 1) → Fase 1 harus udah jalan (produk di DB).
Cadence: paket & voucher = HARIAN.
"""
import time
import colorama; colorama.init()
import config
from modules import paket_diskon as PD
from modules import voucher as V


def paket(shop, nama_toko, session):
    """Paket Diskon harian (spec 11 Jul). FASE 2 (FASE 1 udah grab deal+item membership):
      1) hitung produk yg BELUM masuk paket manapun = semua produk toko − yg udah terdaftar
         (union item semua deal aktif/mendatang, via PD.item_ids_terdaftar);
      2) reuse paket UPSELL bot yg masih hidup; jelang-expire (H-1) → BUAT BARU (bukan perpanjang);
         belum ada UPSELL → buat baru;
      3) enroll produk belum-masuk ke 1 paket (cap KPI_PAKET_MAKS_ITEM tinggi = efektif 1 paket;
         batas item asli Shopee belum ketemu → overflow cuma jaga2 kalau attach mulai gagal massal).
    Idempotent: dijalanin ulang cuma nambah yg beneran belum masuk. DRY: buat_deal None → lapor rencana."""
    now = int(time.time())
    semua = set(PD.item_ids_toko(nama_toko))
    if not semua:
        print(colorama.Fore.YELLOW + f"[prov paket] [{nama_toko}] 0 produk di olah_data — skip (grab Fase 1 dulu)" + colorama.Style.RESET_ALL)
        return {"paket": None, "produk": 0}

    deals = PD.list_deals(session) or []
    terdaftar = PD.item_ids_terdaftar(session, deals)      # produk yg udah di paket manapun
    belum = sorted(semua - terdaftar)
    kap = PD.baca_kapasitas(session)
    print(colorama.Fore.WHITE + f"[prov paket] [{nama_toko}] {len(semua)} produk | {len(terdaftar)} udah di paket | "
          f"{len(belum)} BELUM | kapasitas {kap}" + colorama.Style.RESET_ALL)

    if not belum:
        print(colorama.Fore.GREEN + f"[prov paket] [{nama_toko}] semua produk udah punya paket ✓ — ga ada yg didaftarin" + colorama.Style.RESET_ALL)
        return {"paket": None, "produk": len(semua), "belum_masuk": 0, "masuk": 0}

    prefix = config.NAMA_UPSELL
    jelang = config.JELANG_EXPIRE_HARI * 86400
    _end = lambda d: int(d.get("end_time") or 0)
    upsell = sorted([d for d in deals if str(d.get("name", "")).startswith(prefix)], key=_end, reverse=True)

    pakai = None
    for d in upsell:
        if _end(d) - now > jelang:                    # masih jauh dari expire → reuse
            pakai = d; break
        # jelang-expire (≤ H-1) → JANGAN reuse; biar jatuh ke buat-baru
        # (keputusan owner 12 Jul: expire = BUAT BARU, bukan perpanjang)

    if pakai:
        bid = pakai.get("bundle_deal_id") or pakai.get("id")
        start = int(pakai.get("start_time") or now)
        end = int(pakai.get("end_time") or now + config.DURASI_PROMO_HARI * 86400)
        baru = False
    else:
        start, end = now + 300, now + config.DURASI_PROMO_HARI * 86400
        bid = PD.buat_deal(session, f"{prefix} {nama_toko}", start, end)   # None kalau DRY_RUN
        if not bid:
            print(colorama.Fore.YELLOW + f"[prov paket] [{nama_toko}] (DRY) bakal BUAT '{prefix} {nama_toko}' + enroll {len(belum)} produk belum-masuk" + colorama.Style.RESET_ALL)
            return {"paket": "DRY-baru", "baru": True, "belum_masuk": len(belum)}
        baru = True

    r = PD.enroll_dengan_overflow(session, belum, bid, nama_toko, start, end, prefix)
    print((colorama.Fore.CYAN if baru else colorama.Fore.GREEN)
          + f"[prov paket] [{nama_toko}] paket {'BARU' if baru else 'reuse'} {bid} → {r}" + colorama.Style.RESET_ALL)
    return {"paket": bid, "baru": baru, **r}


_B36 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _b36(n, lebar):
    s = ""
    n = int(n)
    while n:
        s = _B36[n % 36] + s
        n //= 36
    return s.rjust(lebar, "0")[-lebar:]


def _kode_voucher(vouchers, username, now, idx):
    """Kode = PREFIX_TOKO (4 char, WAJIB — aturan Shopee) + 'U' + band (1 char b36) +
    day-of-year (2 char b36) [+ 1 char pembeda kalau nabrak] = 8-9 char (custom maks 5).
    Kode ga boleh dobel sama voucher yg ada (1400101001) — cek ke list, bump kalau kepake.
    Deteksi punya-bot via NAMA, bukan kode."""
    doy = int(time.strftime("%j", time.localtime(now)))
    base = V.prefix_kode_toko(vouchers, username) + "U" + _b36(idx, 1) + _b36(doy, 2)
    ada = {str(v.get("voucher_code") or "").upper() for v in (vouchers or [])}
    if base not in ada:
        return base
    for a in range(36):
        if base + _b36(a, 1) not in ada:
            return base + _b36(a, 1)
    return base + "Z"


def voucher(shop, nama_toko, session):
    """Voucher PRODUK per-BAND harga (KPI owner 13 Jul) — maksa pembeli ambil >1 pcs.
      Band: 1..14999 (KPI_VOUCHER_BAND1_MAKS), lanjut per 20rb (KPI_VOUCHER_BAND_LEBAR),
      grid FIX. Min belanja = batas atas band + 1 (1-14999→15rb · 15000-34999→35rb · dst).
      ⚠️ CAP 2×AOV (keputusan owner 13 Jul): band yg min belanjanya > 2×AOV×buffer
      (V.min_price_toko) DIBUANG — produk mahal (≥ batas band terakhir yg lolos) TANPA
      voucher, biar ga ngelanggar aturan Shopee min order ≤ 2×AOV & poin ≥2 pcs kejaga.
      Harga acuan per ITEM = MAX target antar model (harga_akhir; fallback harga_real)
      → harga berubah = item PINDAH band (items voucher di-reconcile tambah/keluar tiap run).
      ⚠️ Band > KPI_VOUCHER_MAKS_ITEM (500) item DIPECAH jadi >1 voucher (Shopee tolak
      voucher >~570 item — verified 13 Jul). Slot: 'UPSELL <toko> B<low>' (chunk 0) ·
      '...B<low>#2/#3' (lanjutan), min belanja & diskon sama. Idempotent via NAMA slot.
      Jelang-expire (H-1) → buat baru nyambung. Voucher UPSELL yg ga match slot manapun
      (skema lama / band kebuang cap) → coba diakhiri (voucher jalan gagal → warning manual).
      DRY_RUN-aware (modul voucher handle)."""
    from modules import sql_harga as SQL
    now = int(time.time())
    jelang = config.JELANG_EXPIRE_HARI * 86400

    # 1) harga acuan per ITEM (MAX antar model; target kalau ada, else harga real) + stok per item.
    #    ⚠️ Shopee TOLAK voucher produk kalau ada 1 aja item STOK 0 (verified 13 Jul: item 2197126886
    #    stok-0 bikin SELURUH create ERROR_PARAM) → item stok-0 DIBUANG. Butuh stok FRESH: fase 1
    #    grab+store harus jalan dulu (di siklus_terpadu grab duluan). NOTE: harga_olah_data cuma nyimpen
    #    variasi berstok≥1 (grab_produk filter STOK_MINIMAL) → item yg SEMUA modelnya stok-0 otomatis
    #    ga ada barisnya = kebuang; stok_item guard buat jaga2 kalau ada baris stok-0 nyelip.
    harga, stok_item = {}, {}
    for b in SQL.baca_baris_rubah(nama_toko):
        h = b["harga_akhir"] or b["harga_real"]
        if h > 0:
            harga[b["item_id"]] = max(harga.get(b["item_id"], 0), h)
            stok_item[b["item_id"]] = max(stok_item.get(b["item_id"], 0), int(b.get("stok") or 0))
    n_stok0 = sum(1 for i in harga if stok_item.get(i, 0) <= 0)
    if n_stok0:
        harga = {i: h for i, h in harga.items() if stok_item.get(i, 0) > 0}
        print(colorama.Fore.WHITE + f"[prov voucher] [{nama_toko}] {n_stok0} produk stok-0 dibuang dari voucher (Shopee tolak)" + colorama.Style.RESET_ALL)
    if not harga:
        print(colorama.Fore.YELLOW + f"[prov voucher] [{nama_toko}] 0 produk berstok+berharga di olah_data — skip (grab Fase 1 dulu?)" + colorama.Style.RESET_ALL)
        return {"voucher": None, "produk": 0}

    cap = V.min_price_toko(nama_toko)          # 2×AOV×buffer — batas min belanja (aturan Shopee)
    if cap <= 0:
        print(colorama.Fore.YELLOW + f"[prov voucher] [{nama_toko}] AOV kosong (fact_pesanan) — cap 2×AOV ga bisa dihitung, skip" + colorama.Style.RESET_ALL)
        return {"voucher": None, "produk": len(harga), "cap": 0}

    semua_band = V.bagi_produk_per_band(harga)
    bands = [(low, high, ids) for low, high, ids in semua_band if ids and high + 1 <= cap]
    tanpa = sum(len(ids) for low, high, ids in semua_band if ids and high + 1 > cap)
    if tanpa:
        print(colorama.Fore.WHITE + f"[prov voucher] [{nama_toko}] {tanpa} produk mahal (band min > cap Rp{cap:,}) TANPA voucher (keputusan owner)" + colorama.Style.RESET_ALL)

    # 2) band → SLOT: item > KPI_VOUCHER_MAKS_ITEM dipecah (Shopee tolak voucher >~570 item).
    #    1 slot = 1 voucher. Band gede jadi >1 voucher (min belanja & diskon SAMA, item dibagi).
    #    Nama: "UPSELL <toko> B<low>" (chunk 0, kompat lama) · "...B<low>#2/#3.." (chunk lanjut).
    awalan = f"{config.NAMA_UPSELL} {nama_toko} B"
    MAKS = config.KPI_VOUCHER_MAKS_ITEM
    slots = []                                  # (nama_slot, min_b, ids_chunk)
    for low, high, ids in bands:
        min_b = high + 1
        ids_sorted = sorted(ids)
        for k in range(0, max(len(ids_sorted), 1), MAKS):
            chunk = ids_sorted[k:k + MAKS]
            nama = f"{awalan}{low}" + (f"#{k // MAKS + 1}" if k else "")
            slots.append((nama, min_b, chunk))

    # voucher UPSELL existing → petakan by NAMA persis (biar cocok per slot)
    vouchers = V.list_vouchers(session, promotion_type=0) or []
    ours = [v for v in vouchers
            if str(v.get("name") or "").startswith(config.NAMA_UPSELL)
            and int(v.get("end_time") or 0) > now]
    peta = {}
    for v in ours:
        peta.setdefault(str(v.get("name") or ""), []).append(v)

    buat = tambah_n = keluar_n = diakhiri = gagal = 0
    dipakai, sudah_diakhiri = set(), set()
    for idx, (nama_slot, min_b, chunk) in enumerate(slots):
        ids = set(chunk)
        kandidat = peta.get(nama_slot) or []
        # prioritas: min belanja cocok & masih segar → reuse; else yg ada (nyambung/diganti)
        v = next((x for x in kandidat
                  if int(float(x.get("min_price") or 0)) == min_b
                  and int(x.get("end_time") or 0) - now > jelang), None) or (kandidat[0] if kandidat else None)
        vid = (v.get("voucher_id") or v.get("id")) if v else None
        segar = bool(v) and int(v.get("end_time") or 0) - now > jelang
        min_sama = bool(v) and int(float(v.get("min_price") or 0)) == min_b

        if v and segar and min_sama:
            # reuse → reconcile items (produk pindah band/slot ikut harga terbaru)
            dipakai.add(vid)
            det = V.get_voucher(session, vid)
            skrg = {int(x.get("itemid")) for x in ((det.get("rule") or {}).get("items") or [])
                    if isinstance(x, dict) and x.get("itemid")}
            tambah, keluar = ids - skrg, skrg - ids
            try:
                if tambah:
                    V.masukkan_item(session, vid, tambah, detail=det); tambah_n += len(tambah)
                if keluar:
                    det = V.get_voucher(session, vid) if tambah else det   # detail fresh abis PUT
                    V.keluarkan_item(session, vid, keluar, detail=det); keluar_n += len(keluar)
            except Exception as e:
                print(colorama.Fore.RED + f"[prov voucher] [{nama_toko}] {nama_slot} reconcile GAGAL: {e}" + colorama.Style.RESET_ALL)
            continue

        if v and segar:                      # min belanja geser → ganti
            if V.akhiri_voucher(session, vid):
                diakhiri += 1
            sudah_diakhiri.add(vid)
            start = now + 300
        elif v:                              # jelang-expire → buat baru nyambung
            dipakai.add(vid)                 # biarin mati sendiri, jangan diakhiri
            start = int(v.get("end_time") or 0)
        else:
            start = now + 300
        kode = _kode_voucher(vouchers, shop, now, idx)
        try:
            vidbaru = V.buat_voucher(session, nama_slot, kode, start,
                                     start + config.KPI_VOUCHER_DURASI_HARI * 86400,
                                     discount=config.KPI_VOUCHER_DISKON_PCT, min_price=min_b,
                                     max_value=None, item_ids=sorted(ids), **V.TIPE["produk"])
            buat += 1
            vouchers.append({"voucher_code": kode})   # cegah kode dobel di slot berikutnya (1 sesi)
        except Exception as e:
            gagal += 1
            print(colorama.Fore.RED + f"[prov voucher] [{nama_toko}] {nama_slot} buat GAGAL: {e}" + colorama.Style.RESET_ALL)

    # 3) voucher UPSELL yg ga kepakai band manapun → akhiri (skema lama / band ilang / dobel)
    for v in ours:
        vid = v.get("voucher_id") or v.get("id")
        if vid not in dipakai and vid not in sudah_diakhiri:
            if V.akhiri_voucher(session, vid):
                diakhiri += 1
            sudah_diakhiri.add(vid)

    warna = colorama.Fore.RED if gagal else colorama.Fore.CYAN
    print(warna + f"[prov voucher] [{nama_toko}] {len(harga)} produk → {len(bands)} band / {len(slots)} slot | "
          f"buat {buat} · item +{tambah_n}/−{keluar_n} · diakhiri {diakhiri}"
          + (f" · ⚠️ {gagal} GAGAL" if gagal else "") + colorama.Style.RESET_ALL)
    return {"produk": len(harga), "band": len(bands), "slot": len(slots), "buat": buat,
            "tambah": tambah_n, "keluar": keluar_n, "diakhiri": diakhiri, "gagal": gagal}


def campaign(shop, nama_toko, session):
    """Campaign mingguan — nominasi produk (yg LOLOS kriteria stok) ke sesi campaign yg lagi buka
    window nominasi. Kriteria: stok > KPI_CAMPAIGN_PASANG_STOK_MIN (50) DAN stok > KPI_CAMPAIGN_
    PASANG_STOK_X_PJH (10) × penjualan/hari. Skip produk yg SEMUA modelnya udah ternominasi.
    ⚠️ harga campaign maks target×0.985 = requirement Shopee saat nominasi/aktivasi (verif live)."""
    from modules import campaign as C
    from modules import sql_harga as SQL
    sesi = C.open_sessions(session, keywords=config.CAMPAIGN_KEYWORDS)   # cuma sesi buka nominasi
    if not sesi:
        print(colorama.Fore.YELLOW + f"[prov campaign] [{nama_toko}] 0 sesi buka nominasi — skip" + colorama.Style.RESET_ALL)
        return {"campaign": 0, "sesi": 0, "lolos": 0}

    prod_all = C.produk_toko(nama_toko)                 # semua produk berstok [{item_id, models}]
    stok = SQL.baca_stok_per_item(nama_toko)            # {item_id: stok}
    pjh = SQL.baca_penjualan_per_hari([p["item_id"] for p in prod_all])
    smin = config.KPI_CAMPAIGN_PASANG_STOK_MIN
    xf = config.KPI_CAMPAIGN_PASANG_STOK_X_PJH
    lolos = [p for p in prod_all
             if stok.get(p["item_id"], 0) > smin and stok.get(p["item_id"], 0) > xf * pjh.get(p["item_id"], 0.0)]
    print(colorama.Fore.WHITE + f"[prov campaign] [{nama_toko}] {len(prod_all)} produk → {len(lolos)} lolos (stok>{smin} & >{xf}×pjh) | {len(sesi)} sesi" + colorama.Style.RESET_ALL)

    total = 0
    for s in sesi:
        sid = s["session_id"]
        already = C.get_nominated(session, sid)         # {(iid_str,mid_str): {...}}
        baru = [p for p in lolos
                if not all((str(p["item_id"]), str(m)) in already for m in p["models"])]
        r = C.nominate(session, sid, baru)
        total += r.get("staged", 0)
    print(colorama.Fore.CYAN + f"[prov campaign] [{nama_toko}] total staged {total} produk ke {len(sesi)} sesi" + colorama.Style.RESET_ALL)
    return {"campaign": total, "sesi": len(sesi), "lolos": len(lolos)}


def flash(shop, nama_toko, session):
    """Flash Sale MINGGUAN — daftar produk ke sesi flash (grab slot 7hr, rotasi maks 50/sesi, urut
    kategori+penjualan tertinggi, harga = real−POTONG_HARGA). Reuse `flash_sale_daftar.daftar_mingguan`
    (udah lengkap). ⚠️ verif live endpoint flash (RENCANA §1 B&D — set_item_sequence pernah param-err,
    udah non-fatal). Kriteria stok>KPI_FLASH_PASANG_STOK_MIN / >×pjh = refinement TODO (siapkan_produk
    skrg cuma stok>0)."""
    from modules import flash_sale_daftar as FSD
    r = FSD.daftar_mingguan(session, nama_toko)
    print(colorama.Fore.CYAN + f"[prov flash] [{nama_toko}] → {r}" + colorama.Style.RESET_ALL)
    return {"flash_sesi": r.get("sesi", 0), **r}


def garansi(shop, nama_toko, session):
    """Garansi Harga Terbaik harian (spec owner 13 Jul — margin dicek di HARGA BEDA per kondisi):
      LOLOS = harga_acuan ≥ target−SELISIH DAN margin(harga_acuan) ≥ MARGIN_MIN.
      (a) REKOMENDASI (belum-daftar): cek @ Harga PROGRAM (ceiling) → LOLOS & stok>0 → DAFTAR
          (bid @ Program). HPP kosong → SKIP.
      (b) TERBAIK (bid_status 30): cek @ Harga PROGRAM → GAGAL (kebukti langgar) → TAKEDOWN.
          LOLOS/HPP-kosong → biarin.
      (c) PERLU-DITINJAU (bid_status 40): cek @ Harga TERBAIK (floor) → LOLOS & stok>0 → RE-DAFTAR
          bid @ Harga Terbaik (turun biar kompetitif). GAGAL → TAKEDOWN (refresh). HPP-kosong /
          stok-0-doang → biarin. DRY_RUN-aware (modul garansi handle)."""
    from modules import garansi as G
    from modules import sql_harga as SQL
    from modules.fase2_harga import _margin

    # KPI garansi dari CONFIG (bisa diubah sewaktu2 di config.py blok "KPI PER-MODUL"):
    SELISIH = config.KPI_GARANSI_SELISIH        # harga acuan minimal target − ini (default 500)
    MARGIN_MIN = config.KPI_GARANSI_MARGIN_MIN  # margin@harga acuan minimal ini (default 0.07 = 7%)

    baris = SQL.baca_baris_rubah(nama_toko)
    tgt = {(b["item_id"], b["model_id"]): b for b in baris}          # target (harga_akhir) + sku per (item,model)
    biaya = SQL.baca_biaya_sku([b["sku"] for b in baris])

    def qualify(harga, item_id, model_id):
        """Status kelayakan garansi DI HARGA ACUAN (Program utk rekom/terbaik, Terbaik utk perlu-tinjau):
          "SKIP"   = ga ada target / harga acuan 0 (produk ga dikelola)
          "GAGAL"  = kebukti langgar KPI (harga < target−SELISIH ATAU margin < MIN) → boleh takedown
          "NO_HPP" = target ada tapi HPP ga kebaca → ga bisa dibuktiin (jangan takedown, jangan daftar)
          "LOLOS"  = harga ≥ target−SELISIH DAN margin ≥ MIN."""
        b = tgt.get((int(item_id), int(model_id)))
        if not b or not b.get("harga_akhir") or harga <= 0:
            return "SKIP"
        if harga < b["harga_akhir"] - SELISIH:      # −500: ga butuh HPP → bisa langsung GAGAL
            return "GAGAL"
        m = _margin(harga, biaya.get((b["sku"] or "").strip().upper()))
        if m is None:                               # HPP ga kebaca
            return "NO_HPP"
        return "GAGAL" if m < MARGIN_MIN else "LOLOS"

    # (a) REKOMENDASI → cek @ Harga PROGRAM (ceiling), enroll bid @ Program (default entri_enroll)
    entri = []
    for it in G.list_rekomendasi(session):
        if it["stok"] <= 0:
            continue
        for m in it["models"]:
            if qualify(it["ceiling"], it["item_id"], m["model_id"]) == "LOLOS":
                entri.append(G.entri_enroll(it["item_id"], it["item_name"], m["model_id"], m["model_name"],
                                            m["cspu_id"], it["floor"], it["ceiling"]))   # bid @ ceiling (Program)
    ok_daftar = G.enroll(session, entri)[0] if entri else 0

    # (b)/(c) ONGOING
    withdraw_ids, redaftar = [], []
    for o in G.list_ongoing_status(session):
        if o["bid_status"] == G.BID_STATUS_TERBAIK:
            if qualify(o["ceiling"], o["item_id"], o["model_id"]) == "GAGAL":   # (b) @Program, kebukti langgar → takedown
                withdraw_ids.append(o["bid_id"])
            # LOLOS / NO_HPP / SKIP → biarin
        elif o["bid_status"] == G.BID_STATUS_PERLU_TINJAU:
            q = qualify(o["floor"], o["item_id"], o["model_id"])                # (c) @Harga Terbaik (floor)
            if q == "LOLOS" and o["stok"] > 0 and o["cspu_id"]:                 # lolos → ajuin ulang, bid @ Terbaik
                redaftar.append(G.entri_enroll(o["item_id"], o["item_name"], o["model_id"], o["model_name"],
                                               o["cspu_id"], o["floor"], o["ceiling"], bid_rp=o["floor"]))
            elif q == "GAGAL":                                                  # kebukti langgar → takedown (refresh)
                withdraw_ids.append(o["bid_id"])
            # NO_HPP / SKIP / (LOLOS tapi stok 0) → biarin

    ok_redaftar = G.enroll(session, redaftar)[0] if redaftar else 0
    ok_takedown = G.withdraw(session, withdraw_ids)[0] if withdraw_ids else 0
    print(colorama.Fore.CYAN + f"[prov garansi] [{nama_toko}] daftar {ok_daftar} + re-daftar {ok_redaftar} + takedown {ok_takedown}" + colorama.Style.RESET_ALL)
    return {"daftar": ok_daftar, "redaftar": ok_redaftar, "takedown": ok_takedown}
