"""modules/fase2_harga.py — FASE 2 modul HARGA (poin 1-4), lapisan MASALAH (deteksi).

READ-ONLY: klasifikasi tiap variasi ke kasus 1-4 + susun daftar AKSI yg diperlukan.
Eksekusi (Solusi) dilakukan modul terpisah (nyusul) — di sini cuma diagnosa.

Beda vs Fase 2 lama (`update_harga`): lama nentuin aksi dari 1 "sumber harga"; DI SINI
tiap variasi dicek terhadap SEMUA promo yg dia ikuti (dari `harga_promo_konteks`),
tiap promo punya kondisi takedown sendiri (spec RENCANA_FASE2.md poin 3).

Target = pancing/Harga Diskon (baca_baris_rubah). Real = harga_tampil (Fase 1).
Penjualan/hari = rata2 30 hari unit terjual (fact_penjualan Shopee).
"""
import config
from modules import sql_harga as SQL
from modules.log_siklus import log, catat

# Ambang KPI takedown — SATU sumber di config (jangan hardcode di sini). Alias biar
# ringkas + kalau config di-tuning, cukup ubah di config.py.
GARANSI_MARGIN_MIN = config.KPI_GARANSI_MARGIN_MIN   # margin@best < ini -> takedown / jangan pasang
GARANSI_SELISIH   = config.KPI_GARANSI_SELISIH       # best < target-ini -> takedown
FLASH_SELISIH     = config.KPI_FLASH_SELISIH         # flash < target-ini -> takedown
CAMPAIGN_FAKTOR   = config.KPI_CAMPAIGN_FAKTOR       # campaign < target*ini -> takedown
CAMPAIGN_STOK_MIN = config.KPI_CAMPAIGN_STOK_MIN     # stok < ini -> takedown campaign
REM_MAKS_TURUN    = config.KPI_HARGA_MAKS_TURUN_PCT  # target < HargaDiskon×(1-ini) -> REM produk (0.40)
REM_MAKS_UBAH     = config.KPI_HARGA_MAKS_UBAH_PCT   # fraksi produk keubah > ini -> REM TOKO (0.30)


# Jenis promo yg PUNYA handler di modul harga (sisanya = "tak dikenal" -> di-flag).
_JENIS_DIKENAL = {"Promo Toko", "Garansi Harga Terbaik", "Flash Sale", "Campaign"}


def _margin(harga, cost):
    """margin(harga) = 1 - pct - (hpp+biaya)/harga. None kalau harga/cost kosong.
    Rumus & basis IDENTIK kolom margin dashboard."""
    if not harga or harga <= 0 or not cost:
        return None
    return 1.0 - cost["pct"] - (cost["hpp"] + cost["biaya"]) / harga


def _cek_campaign(target, stok, pjh, by_jenis):
    """Poin 3⑤ — audit nominasi CAMPAIGN (dipisah dari _cek_koreksi_turun 17 Jul):
    nominasi campaign nempel SEBELUM sesinya mulai (harga tampil belum berubah → kasus
    'sesuai'), jadi cek ini HARUS jalan juga buat item yg harganya sesuai — kalau nunggu
    koreksi_turun, pelanggaran baru ketauan pas sesi udah live (telat, diskon dalem
    kelanjur tayang). Kriteria: harga < target×0.985 / stok < 30 / stok < pjh."""
    cp = by_jenis.get("Campaign")
    if cp is None:
        return []
    sebab = []
    if cp["harga_promo"] and cp["harga_promo"] < target * CAMPAIGN_FAKTOR:
        sebab.append(f"campaign {cp['harga_promo']} < target*{CAMPAIGN_FAKTOR}")
    if stok < CAMPAIGN_STOK_MIN:
        sebab.append(f"stok {stok} < {CAMPAIGN_STOK_MIN}")
    if pjh and stok < pjh:
        sebab.append(f"stok {stok} < penjualan/hari {pjh:.1f}")
    if sebab:
        return [{"promo": "Campaign", "aksi": "takedown", "sebab": " & ".join(sebab)}]
    return []


def _cek_koreksi_turun(target, real, stok, pjh, promos, gar, cost):
    """Target < Harga Awal. Cek Promo Toko (set/daftar) + takedown per-promo (garansi/flash/campaign).
    Return list aksi (dict). promos = list {jenis, harga_promo, status, stok} dari konteks.
    cost = {hpp,pct,biaya} SKU ini (buat margin@best garansi)."""
    aksi = []
    by_jenis = {p["jenis"]: p for p in promos}

    # 3a — PROMO TOKO
    pt = by_jenis.get("Promo Toko")
    if pt is None:
        aksi.append({"promo": "Promo Toko", "aksi": "daftar_promo_utama", "ke": target})
    elif pt["harga_promo"] != target:
        aksi.append({"promo": "Promo Toko", "aksi": "set_harga", "dari": pt["harga_promo"], "ke": target})

    # 3b — GARANSI HARGA TERBAIK (per-jam, tabel 'terbaik'/ongoing). Sumber 2-KOLOM (M1):
    #      Terbaik = floor_price · Program = ceiling_price (bidding_info, verified). bid_id buat takedown.
    #      Takedown kalau: Harga TERBAIK < target−500 (undercut) ATAU margin@PROGRAM < 7%.
    #      margin @ PROGRAM (ceiling) = keputusan owner (grilling: tabel 'terbaik' dicek @ Harga Program).
    if gar:
        terbaik = gar.get("terbaik") or gar.get("best") or 0     # Harga Terbaik (floor, reliable M1)
        program = gar.get("program") or 0                        # Harga Program (ceiling)
        sebab = []
        if terbaik and terbaik < target - GARANSI_SELISIH:
            sebab.append(f"Terbaik {terbaik} < target-{GARANSI_SELISIH}")
        m = _margin(program or terbaik, cost)         # margin @ Program (fallback Terbaik kalau Program kosong)
        if m is not None and m < GARANSI_MARGIN_MIN:
            sebab.append(f"margin@program {m*100:.1f}% < {GARANSI_MARGIN_MIN*100:.0f}%")
        if sebab:
            aksi.append({"promo": "Garansi", "aksi": "takedown", "sebab": " & ".join(sebab),
                         "bid_id": (gar or {}).get("bid_id")})

    # 3c — FLASH SALE
    fs = by_jenis.get("Flash Sale")
    if fs is not None:
        sebab = []
        if fs["harga_promo"] and fs["harga_promo"] < target - FLASH_SELISIH:
            sebab.append(f"flash {fs['harga_promo']} < target-{FLASH_SELISIH}")
        if fs["stok"] == 0:
            sebab.append("stok real 0")
        if sebab:
            aksi.append({"promo": "Flash Sale", "aksi": "takedown", "sebab": " & ".join(sebab)})

    # 3d — CAMPAIGN
    aksi.extend(_cek_campaign(target, stok, pjh, by_jenis))

    # PROMO TAK DIKENAL yg nindih harga tampil (mis. "Tipe 1"). Aturan user (sama garansi):
    #   - HOLD (biarin) kalau harga >= target-500 DAN margin >= 7% -> gak apa-apa.
    #   - FLAG (perlu takedown, belum ada handler) kalau harga < target-500 (ATAU margin<7% [PENDING]).
    for p in promos:
        if (p["jenis"] not in _JENIS_DIKENAL and p.get("status") == "aktif"
                and p["harga_promo"] and p["harga_promo"] <= target):
            if p["harga_promo"] < target - GARANSI_SELISIH:   # <target-500 -> masalah
                aksi.append({"promo": p["jenis"], "aksi": "flag_tak_dikenal",
                             "sebab": f"'{p['jenis']}' @{p['harga_promo']} < target-{GARANSI_SELISIH} (belum ada handler; PR: identifikasi)"})
            else:                                              # dalam toleransi -> hold
                aksi.append({"promo": p["jenis"], "aksi": "hold",
                             "sebab": f"'{p['jenis']}' @{p['harga_promo']} masih >= target-{GARANSI_SELISIH} (dibiarkan)"})
            break

    return aksi


def diagnosa_toko(nama_toko):
    """Klasifikasi semua variasi 1 toko ke kasus 1-4 + daftar aksi. READ-ONLY.
    Return list dict {item_id, model_id, sku, target, real, harga_awal, stok, pjh, kasus, aksi,
    komisi_patokan}.

    ⭐ POIN 3·0 KOMISI (anchor, dicek PALING DULU): kalau SKU punya komisi aktif di
    `harga_komisi_toko` (harga_jual>0), TARGET beralih dari pancing/harga-diskon → **harga_jual**
    (harga komisi). Jadi SEMUA promo (kasus 1-4) pakai harga komisi sbg patokan. Sumber SQL Syntra,
    no anti-bot. (Sinkronisasi set/takedown komisi ke Shopee = bagian C, kena anti-bot, terpisah.)"""
    baris = SQL.baca_baris_rubah(nama_toko)
    promo = SQL.baca_promo_detail(nama_toko)
    camp = SQL.baca_campaign_item(nama_toko)   # {(item,model): {campaign_price micro, ...}}
    for (iid, mid), cv in camp.items():
        harga = int((cv.get("campaign_price") or 0)) // config.FAKTOR_HARGA
        if harga <= 0:
            continue
        promo.setdefault((iid, mid), []).append({
            "jenis": "Campaign", "harga_promo": harga, "status": "aktif",
            "stok": 0,   # stok diisi dari baris di loop bawah (b["stok"])
        })
    garansi = SQL.baca_garansi_best(nama_toko)
    penjualan = SQL.baca_penjualan_per_hari([b["item_id"] for b in baris])
    biaya = SQL.baca_biaya_sku([b["sku"] for b in baris])
    komisi = SQL.baca_komisi_patokan(config.username_dari_nama(nama_toko))   # {SKU_UPPER: {harga_jual, persen}} — SYNTRA
    shopee_kom = SQL.baca_komisi_shopee_aktif(nama_toko)                     # set(item_id) komisi aktif di SHOPEE

    out = []
    for b in baris:
        key = (b["item_id"], b["model_id"])
        real, H, stok = b["harga_real"], b["harga_awal"], b["stok"]
        pjh = penjualan.get(b["item_id"], 0.0)

        # POIN 3·0 — komisi aktif -> harga komisi (harga_jual) jadi TARGET (patokan semua promo).
        kom = komisi.get((b["sku"] or "").strip().upper())
        komisi_patokan = kom["harga_jual"] if (kom and kom["harga_jual"] > 0) else None
        target = komisi_patokan if komisi_patokan else b["harga_akhir"]
        hd = b.get("harga_diskon", 0)          # Harga Diskon MENTAH (acuan rem 40%)
        # Trigger komisi Shopee (tanpa patokan Syntra): produk komisi-aktif di Shopee tapi harga_jual
        # belum diisi → bot ga tau Harga Komisi → JAGA harga (jangan diubah, tunggu owner isi patokan).
        shopee_hold = (b["item_id"] in shopee_kom) and not komisi_patokan

        if not target or target <= 0:
            kasus, aksi = "tanpa_target", []
        elif shopee_hold:
            kasus, aksi = "komisi_hold", []
        elif real == target:
            # 'sesuai' TETAP diaudit nominasi campaign-nya (17 Jul): nominasi nempel pas
            # harga masih on-target — pelanggaran KPI campaign harus kecabut SEBELUM sesi live.
            kasus = "sesuai"
            aksi = _cek_campaign(target, stok, pjh,
                                 {p["jenis"]: p for p in promo.get(key, [])})
        elif hd > 0 and target < hd * (1 - REM_MAKS_TURUN):
            # REM 40% (per-produk): target di bawah 60% Harga Diskon = curiga pancing/komisi salah
            # input → JANGAN diubah (jaring pengaman, keputusan owner). Komisi ≥ Diskon jd ga bakal
            # salah-trigger; yg keneb rem = pancing kompetitor yg kelewat rendah.
            kasus, aksi = "rem_turun", []
        elif H and target < H:
            kasus = "koreksi_turun"
            cost = biaya.get((b["sku"] or "").strip().upper())
            aksi = _cek_koreksi_turun(target, real, stok, pjh, promo.get(key, []), garansi.get(key), cost)
        else:   # target >= harga awal (atau harga awal 0)
            kasus = "harga_dasar"
            aksi = [{"aksi": "ubah_harga_dasar", "ke": target,
                     "keluarkan": "SEMUA promo", "pasang_lagi": ["Paket Diskon", "Voucher"]}]

        out.append({"item_id": b["item_id"], "model_id": b["model_id"], "sku": b["sku"],
                    "target": target, "real": real, "harga_awal": H, "harga_diskon": hd, "stok": stok,
                    "pjh": round(pjh, 1), "kasus": kasus, "aksi": aksi,
                    "komisi_patokan": komisi_patokan})
    return out


# Kasus yg BENERAN ngubah harga (buat hitung rem toko + dashboard).
_KASUS_UBAH = ("koreksi_turun", "harga_dasar")


def kena_rem_toko(diagnosa):
    """REM 30% (per-TOKO): kalau fraksi produk yg BAKAL keubah harga > KPI_HARGA_MAKS_UBAH_PCT,
    curiga data ngaco (grab meleset dll) → SKIP eksekusi SELURUH toko biar ga kebakaran massal.
    Return (kena:bool, frac:float, n_ubah:int, total:int)."""
    total = len(diagnosa) or 1
    n_ubah = sum(1 for d in diagnosa if d.get("kasus") in _KASUS_UBAH)
    frac = n_ubah / total
    return (frac > REM_MAKS_UBAH), frac, n_ubah, total


def bangun_alasan(d):
    """Rakit teks ALASAN 1 variasi dari diagnosa (kenapa harga segini + aksi apa) — buat
    kolom harga_olah_data.alasan (dibaca dashboard/laporan). Gabung 1 baris, ringkas.
    Contoh: 'Target 7.900 (komisi aktif). Promo toko 9.000→7.900. Garansi dicabut (margin 5%<7%).'"""
    F = config.fmt_angka
    kasus = d.get("kasus")
    if kasus == "tanpa_target":
        return "Tanpa target (Harga Diskon kosong) — harga tidak diubah"
    if kasus == "komisi_hold":
        return ("Komisi AKTIF di Shopee (belum ada patokan Harga Jual di dashboard) — "
                "harga DIJAGA, tidak diubah. Isi Harga Jual komisi biar bot bisa patok.")
    src = "komisi aktif" if d.get("komisi_patokan") else "Harga Diskon"
    bits = [f"Target {F(d.get('target'))} ({src})"]
    if kasus == "rem_turun":
        pct = int(REM_MAKS_TURUN * 100)
        bits.append(f"⛔ DIREM — di bawah {100-pct}% Harga Diskon {F(d.get('harga_diskon'))} "
                    "(curiga pancing/komisi salah), harga TIDAK diubah")
        return ". ".join(bits) + "."
    if kasus == "sesuai":
        bits.append("sudah sesuai — tak ada perubahan")
        return ". ".join(bits) + "."
    if kasus == "harga_dasar":
        bits.append(f"target ≥ harga awal {F(d.get('harga_awal'))} → ubah HARGA DASAR "
                    "(keluar semua promo; paket+voucher dipasang balik oleh provisioning harian, band ikut harga baru)")
        return ". ".join(bits) + "."
    # koreksi_turun → jabarin aksi per-promo
    for a in d.get("aksi", []):
        nama = a.get("promo") or a.get("aksi") or ""
        act = a.get("aksi")
        if act == "set_harga":
            bits.append(f"Promo toko {F(a.get('dari'))}→{F(a.get('ke'))}")
        elif act == "daftar_promo_utama":
            bits.append(f"Daftar promo toko @ {F(a.get('ke'))}")
        elif act == "takedown":
            bits.append(f"{nama} dicabut ({a.get('sebab','')})")
        elif act == "flag_tak_dikenal":
            bits.append(f"{nama} perlu dicabut manual ({a.get('sebab','')})")
        elif act == "hold":
            bits.append(f"{nama} dibiarkan ({a.get('sebab','')})")
    if len(bits) == 1:
        bits.append("perlu koreksi turun (belum ada aksi promo cocok)")
    return ". ".join(bits) + "."


def alasan_dari_diagnosa(diagnosa):
    """{(item_id, model_id): teks alasan} dari list diagnosa — buat SQL.tulis_alasan."""
    return {(d["item_id"], d["model_id"]): bangun_alasan(d) for d in diagnosa}


def alasan_terkini(keputusan_a, diagnosa_b):
    """FASE 3: gabung NARASI aksi (diagnosa Loop A `keputusan_a`) + VERIFIKASI status terkini
    (diagnosa Loop B `diagnosa_b`, hasil grab-ulang abis fase 2). Return {(item,model): teks}.
    Suffix: '✓ harga sesuai target' kalau real==target sekarang · '⚠ belum (real X)' kalau belum.
    Kalau produk ga ada di keputusan Loop A (mis. fase 2 skip) → pakai bangun_alasan(b) apa adanya."""
    F = config.fmt_angka
    peta_a = {(d["item_id"], d["model_id"]): d for d in (keputusan_a or [])}
    out = {}
    for b in diagnosa_b:
        key = (b["item_id"], b["model_id"])
        dasar = peta_a.get(key) or b                       # narasi dari Loop A kalau ada
        teks = bangun_alasan(dasar)
        target, real = b.get("target"), b.get("real")
        if not target or target <= 0:
            suffix = ""
        elif real and real == target:
            suffix = " ✓ harga sesuai target."
        else:
            suffix = f" ⚠ belum sesuai (real {F(real)})."
        out[key] = teks + suffix
    return out


def ringkas(diagnosa):
    """Ringkasan jumlah per kasus + per jenis aksi + berapa variasi ke-anchor komisi (log/verifikasi)."""
    from collections import Counter
    kasus = Counter(d["kasus"] for d in diagnosa)
    aksi = Counter(a.get("promo", a.get("aksi")) for d in diagnosa for a in d["aksi"])
    n_komisi = sum(1 for d in diagnosa if d.get("komisi_patokan"))
    if n_komisi:
        kasus["_komisi_anchor"] = n_komisi
    return dict(kasus), dict(aksi)


# ══════════════════════════════════════════════════════════════════
#  SOLUSI — EKSEKUSI (poin 3a Promo Toko). DRY-RUN aware (config.DRY_RUN).
#  Urutan: lifecycle promo toko (buat/duplikat) -> set harga / daftar variasi.
# ══════════════════════════════════════════════════════════════════


def _chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def eksekusi_promo_toko(shop, nama_toko, session, diagnosa):
    """SOLUSI poin 3a. Lifecycle promo toko dulu (buat baru kalau ga ada / duplikat kalau H-1,
    reuse duplikat_promo — perpanjang di-SKIP: promo toko tak bisa extend), lalu set harga=target
    / daftar variasi 'koreksi_turun' ke promo utama. DRY-RUN aware. Return ringkasan."""
    from modules.discount_util import grab_semua_promo, grab_item_promo
    from modules.update_harga import _entry, grab_payload
    from modules.duplikat_promo import proses_duplikat_promo
    from modules.api_util import api_post
    from modules.sql_harga import baca_baris_rubah

    aksi_pt = [(d, a) for d in diagnosa for a in d["aksi"] if a.get("promo") == "Promo Toko"]

    # 1) LIFECYCLE — pastikan promo toko valid (no promo->buat dari 0; H-1->duplikat; masih lama->noop).
    baris = baca_baris_rubah(nama_toko)
    try:
        proses_duplikat_promo(shop, session, baris)
    except Exception as e:
        log(f"lifecycle gagal: {type(e).__name__}: {e}", level="error", fase="F2", toko=nama_toko, modul="promo_toko")

    if not aksi_pt:
        return {"set": 0, "daftar": 0, "terkirim": 0, "promo_toko": 0}

    # 2) Peta promo toko sekarang: {(item,model): {pid: harga}} + tentukan promo UTAMA.
    promos = grab_semua_promo(shop, session)
    if not promos:
        log("belum ada promo toko (mungkin baru dibuat/DRY) — set/daftar ditunda.", level="warning", fase="F2", toko=nama_toko, modul="promo_toko")
        return {"set": 0, "daftar": 0, "terkirim": 0, "promo_toko": 0, "catatan": "promo toko belum ada"}
    pids = [p["promotion_id"] for p in promos]
    primary = next((p["promotion_id"] for p in promos
                    if config.NAMA_PROMO.lower() in str(p.get("name", "")).lower()), pids[0])
    peta = {}
    for pid in pids:
        for it in grab_item_promo(shop, session, pid):
            if it.get("status") == config.STATUS_AKTIF and it.get("item_id"):
                k = (int(it["item_id"]), int(it["model_id"]))
                peta.setdefault(k, {})[pid] = int(it["promotion_price"]) // config.FAKTOR_HARGA

    # 3) Susun update per promo.
    upd_by_pid = {pid: [] for pid in pids}
    n_set = n_daftar = 0
    for d, a in aksi_pt:
        key = (d["item_id"], d["model_id"]); target = d["target"]
        if a["aksi"] == "set_harga":
            target_pids = list(peta.get(key, {}).keys()) or [primary]; n_set += 1
        else:   # daftar_promo_utama
            target_pids = [primary]; n_daftar += 1
        for pid in target_pids:
            if peta.get(key, {}).get(pid) == target:
                continue   # udah pas
            upd_by_pid[pid].append(_entry(d["item_id"], d["model_id"], target, config.STATUS_AKTIF))

    # 4) Kirim (DRY-RUN aware, per chunk 50, 1 chunk gagal tak gugurkan lainnya).
    terkirim = gagal = 0
    for pid, entries in upd_by_pid.items():
        for ch in _chunks(entries, 50):
            if config.DRY_RUN:
                terkirim += len(ch); continue
            try:
                api_post(config.URL_UPDATE_HARGA, config.grab_headers(session), session["params"],
                         grab_payload(pid, ch), kunci="data")
                terkirim += len(ch)
            except Exception as e:
                gagal += len(ch)
                log(f"chunk {pid} gagal ({len(ch)}): {type(e).__name__}", level="error", fase="F2", toko=nama_toko, modul="promo_toko")
    mode = "DRY-RUN" if config.DRY_RUN else "LIVE"
    catat(f"({mode}) set={n_set} daftar={n_daftar} → {terkirim} entri terkirim, {gagal} gagal",
          status="gagal" if gagal else (("live" if terkirim else "ok") if not config.DRY_RUN else "ok"),
          fase="F2", toko=nama_toko, modul="promo_toko",
          detail={"set": n_set, "daftar": n_daftar, "terkirim": terkirim, "gagal": gagal, "dry": config.DRY_RUN})
    return {"set": n_set, "daftar": n_daftar, "terkirim": terkirim, "gagal": gagal, "promo_toko": len(pids)}


def eksekusi_harga_dasar(shop, nama_toko, session, diagnosa):
    """SOLUSI kasus 4 (Target >= Harga Awal). Harga dasar TAK BISA diubah selama produk masih
    nyangkut promosi APA PUN -> takedown SEMUA promo dulu, ubah base, lalu PASANG LAGI paket +
    voucher (2 ini WAJIB selalu aktif per produk). Urutan:
      1. Garansi withdraw (bid_id dari fakta).
      2. Paket Diskon takedown + Voucher takedown (item-level; deal/voucher dari fakta).
      3. edit_harga_dasar (reuse): takedown Promo Toko + Flash + Campaign -> ubah harga dasar.
      4. RE-ADD paket + voucher utk item yg tadi dikeluarin (ke deal utama / voucher yg sama).
    DRY-RUN aware. Return ringkasan."""
    from modules.discount_util import grab_semua_promo, grab_item_promo
    from modules.update_harga import edit_harga_dasar
    from modules import garansi as G
    from modules import paket_diskon as PD
    from modules import voucher as V

    hd = [d for d in diagnosa if d["kasus"] == "harga_dasar"]
    if not hd:
        return {"harga_dasar": 0}
    hd_items = {d["item_id"] for d in hd}   # paket/voucher = level ITEM (bukan variasi)

    # 1) TAKEDOWN GARANSI (variasi harga-dasar yg ada di fakta garansi) — DRY_RUN aware di modul.
    gar = SQL.baca_garansi_best(nama_toko)
    bids = [gar[(d["item_id"], d["model_id"])]["bid_id"] for d in hd
            if (d["item_id"], d["model_id"]) in gar and gar[(d["item_id"], d["model_id"])].get("bid_id")]
    if bids:
        try:
            G.withdraw(session, bids)
        except Exception as e:
            log(f"withdraw garansi gagal: {type(e).__name__}", level="error", fase="F2", toko=nama_toko, modul="garansi")

    # 2a) TAKEDOWN PAKET DISKON — item yg ikut paket (konteks) keluar dari SEMUA deal aktif.
    paket_aktif = SQL.baca_paket_aktif(nama_toko)
    deal_ids = [p["bundle_deal_id"] for p in paket_aktif]
    tgt_paket = sorted(hd_items & SQL.baca_item_di_paket(nama_toko))
    if tgt_paket and deal_ids:
        try:
            PD.keluarkan_item(session, deal_ids, tgt_paket)
        except Exception as e:
            log(f"takedown paket gagal: {type(e).__name__}", level="error", fase="F2", toko=nama_toko, modul="paket")

    # 2b) TAKEDOWN VOUCHER PRODUK — item yg ada di item_scope voucher, keluar per voucher.
    vouch_item = SQL.baca_voucher_item(nama_toko)                 # {item_id: [voucher_id]}
    vouch_grup = {}                                               # {voucher_id: [item_id]}
    for iid in hd_items:
        for vid in vouch_item.get(iid, []):
            vouch_grup.setdefault(vid, []).append(iid)
    for vid, items in vouch_grup.items():
        try:
            V.keluarkan_item(session, vid, items)
        except Exception as e:
            log(f"takedown voucher {vid} gagal: {type(e).__name__}", level="error", fase="F2", toko=nama_toko, modul="voucher")

    # 3) Bangun daftar (baris + in_promos) + EDIT HARGA DASAR (takedown promo toko/flash/campaign + ubah base).
    baris_map = {(b["item_id"], b["model_id"]): b for b in SQL.baca_baris_rubah(nama_toko)}
    promos = grab_semua_promo(shop, session)
    peta = {}
    for p in promos:
        pid = p["promotion_id"]
        for it in grab_item_promo(shop, session, pid):
            if it.get("item_id"):
                peta.setdefault((int(it["item_id"]), int(it["model_id"])), {})[pid] = int(it["promotion_price"]) // config.FAKTOR_HARGA
    daftar = [(baris_map[(d["item_id"], d["model_id"])], peta.get((d["item_id"], d["model_id"]), {}))
              for d in hd if (d["item_id"], d["model_id"]) in baris_map]
    alasan = edit_harga_dasar(shop, session, daftar, nama_toko=nama_toko)

    # 4) RE-ADD paket + voucher → DISERAHKAN ke PROVISIONING HARIAN (keputusan owner M3).
    #    Alasan: harga awal berubah = produk bisa PINDAH BAND voucher (min-belanja per band).
    #    Re-add inline ke voucher/paket LAMA = salah band. Provisioning harian (poin 5) yg
    #    reconcile: masukin produk ke band voucher yg BENER + paket UPSELL sesuai harga baru.
    #    Gap sementara (produk tanpa paket/voucher s/d provisioning next) diterima — ubah harga
    #    dasar jarang, provisioning harian nutup. (paket_aktif/vouch_grup di atas cuma buat takedown.)
    n_defer_paket = len(tgt_paket)
    n_defer_voucher = sum(len(v) for v in vouch_grup.values())
    if n_defer_paket or n_defer_voucher:
        log(f"re-attach {n_defer_paket} paket + {n_defer_voucher} voucher item DISERAHKAN provisioning harian (band bisa geser ikut harga baru)",
            level="detail", fase="F2", toko=nama_toko, modul="harga")

    mode = "DRY-RUN" if config.DRY_RUN else "LIVE"
    catat(f"({mode}) {len(daftar)} variasi | garansi withdraw {len(bids)} | "
          f"paket takedown {len(tgt_paket)} | voucher takedown {n_defer_voucher} item → re-attach via provisioning harian",
          status=("live" if (not config.DRY_RUN and len(daftar)) else "ok"),
          fase="F2", toko=nama_toko, modul="harga",
          detail={"variasi": len(daftar), "garansi_withdraw": len(bids), "paket_takedown": len(tgt_paket),
                  "voucher_takedown": n_defer_voucher, "reattach": "provisioning_harian", "dry": config.DRY_RUN})
    return {"harga_dasar": len(daftar), "garansi_takedown": len(bids), "alasan": len(alasan),
            "paket_takedown": len(tgt_paket), "voucher_takedown": n_defer_voucher,
            "reattach_via": "provisioning_harian"}


def _kunci_takedown(diagnosa, promo):
    """set (item_id, model_id) variasi 'koreksi_turun' yg diagnosa flag takedown utk `promo`."""
    return {(d["item_id"], d["model_id"]) for d in diagnosa
            for a in d["aksi"] if a.get("promo") == promo and a.get("aksi") == "takedown"}


def eksekusi_takedown_flash(shop, nama_toko, session, diagnosa):
    """SOLUSI poin 3c. Keluarkan variasi 'koreksi_turun' yg flash-nya < target-10 (atau stok
    real 0) dari SEMUA flash sale aktif. flash_sale_id di-resolve on-demand oleh takedown_items
    (peta_item). Sesi yg diakhirin LANGSUNG DIGANTI real-time (slot sama, produk sehat didaftar
    ulang pake data fresh — grilling 15 Jul). DRY-RUN aware.
    ⚠️ config.SKIP_FLASH_TAKEDOWN=True -> di-skip di modul (endpoint set-item ditolak Shopee
    code 1001; PR flash sale). Balikin False setelah endpoint per-item dibenerin."""
    from modules import flash_sale as FS

    kunci = _kunci_takedown(diagnosa, "Flash Sale")
    if not kunci:
        return {"flash_takedown": 0, "flash_target": 0}
    n = FS.takedown_items(session, shop, nama_toko, kunci)
    mode = "DRY-RUN" if config.DRY_RUN else "LIVE"
    catat(f"({mode}) {len(kunci)} variasi target → {n} ter-takedown",
          status=("live" if (not config.DRY_RUN and n) else "ok"),
          fase="F2", toko=nama_toko, modul="flash", detail={"target": len(kunci), "takedown": n, "dry": config.DRY_RUN})
    return {"flash_takedown": n, "flash_target": len(kunci)}


def eksekusi_takedown_campaign(shop, nama_toko, session, diagnosa):
    """SOLUSI poin 3d. Keluarkan variasi 'koreksi_turun' yg campaign-nya < target*98.5% (atau
    stok<30 / stok<penjualan-hari) dari campaign Shopee.
    ✅ (15 Jul, grilling): balik ke `takedown_campaign.takedown_dari_campaign` (browser-context
    via campaign_util, scoped config.CAMPAIGN_KEYWORDS/tanggal-kembar) — versi `campaign.py`
    (requests polos, semua campaign) DITOLAK Shopee (anti-bot, endpoint get_nominated/opt_out
    wajib signature browser). DRY-RUN aware (guard di takedown_products)."""
    from modules.takedown_campaign import takedown_dari_campaign

    kunci = _kunci_takedown(diagnosa, "Campaign")
    if not kunci:
        return {"campaign_takedown": 0, "campaign_target": 0}

    idx = (config.SHOP_DATABASE.get(shop) or {}).get("i", 0)
    total = takedown_dari_campaign(session, shop, idx, kunci, nama_toko=nama_toko)
    mode = "DRY-RUN" if config.DRY_RUN else "LIVE"
    catat(f"({mode}) {len(kunci)} variasi target → {total} ter-takedown",
          status=("live" if (not config.DRY_RUN and total) else "ok"),
          fase="F2", toko=nama_toko, modul="campaign",
          detail={"target": len(kunci), "takedown": total, "dry": config.DRY_RUN})
    return {"campaign_takedown": total, "campaign_target": len(kunci)}


def eksekusi_takedown_garansi(shop, nama_toko, session, diagnosa):
    """SOLUSI poin 3③. Withdraw variasi 'koreksi_turun' yg garansi-nya undercut (best<target-500)
    atau margin@program<7%. bid_id dibawa langsung di flag diagnosa. DRY-aware (garansi.withdraw)."""
    from modules import garansi as G
    bids = [a["bid_id"] for d in diagnosa for a in d["aksi"]
            if a.get("promo") == "Garansi" and a.get("aksi") == "takedown" and a.get("bid_id")]
    if not bids:
        return {"garansi_takedown": 0, "garansi_target": 0}
    n = G.withdraw(session, bids)[0] if not config.DRY_RUN else 0
    mode = "DRY-RUN" if config.DRY_RUN else "LIVE"
    catat(f"({mode}) {len(bids)} bid garansi target -> {n} ter-withdraw",
          status=("live" if (not config.DRY_RUN and n) else "ok"),
          fase="F2", toko=nama_toko, modul="garansi", detail={"target": len(bids), "withdraw": n, "dry": config.DRY_RUN})
    return {"garansi_takedown": n, "garansi_target": len(bids)}
