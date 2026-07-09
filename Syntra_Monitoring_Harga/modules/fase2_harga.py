"""modules/fase2_harga.py — FASE 2 modul HARGA (poin 1-4), lapisan MASALAH (deteksi).

READ-ONLY: klasifikasi tiap variasi ke kasus 1-4 + susun daftar AKSI yg diperlukan.
Eksekusi (Solusi) dilakukan modul terpisah (nyusul) — di sini cuma diagnosa.

Beda vs Fase 2 lama (`update_harga`): lama nentuin aksi dari 1 "sumber harga"; DI SINI
tiap variasi dicek terhadap SEMUA promo yg dia ikuti (dari `harga_promo_konteks`),
tiap promo punya kondisi takedown sendiri (spec RENCANA_FASE2.md poin 3).

Target = pancing/Harga Diskon (baca_baris_rubah). Real = harga_tampil (Fase 1).
Penjualan/hari = rata2 30 hari unit terjual (fact_penjualan Shopee).
"""
from modules import sql_harga as SQL

# Ambang (dari spec; taruh konstanta biar gampang di-tuning nanti).
GARANSI_MARGIN_MIN = 0.07        # margin@best < 7% -> takedown / jangan pasang
GARANSI_SELISIH = 500            # best < target-500 -> takedown
FLASH_SELISIH = 10               # flash harusnya target-10; < itu -> takedown
CAMPAIGN_FAKTOR = 0.985          # campaign harusnya <= target*98.5%; < itu -> takedown
CAMPAIGN_STOK_MIN = 30           # stok < 30 -> takedown campaign


# Jenis promo yg PUNYA handler di modul harga (sisanya = "tak dikenal" -> di-flag).
_JENIS_DIKENAL = {"Promo Toko", "Garansi Harga Terbaik", "Flash Sale", "Campaign"}


def _cek_koreksi_turun(target, real, stok, pjh, promos, gar):
    """Target < Harga Awal. Cek Promo Toko (set/daftar) + takedown per-promo (garansi/flash/campaign).
    Return list aksi (dict). promos = list {jenis, harga_promo, status, stok} dari konteks."""
    aksi = []
    by_jenis = {p["jenis"]: p for p in promos}

    # 3a — PROMO TOKO
    pt = by_jenis.get("Promo Toko")
    if pt is None:
        aksi.append({"promo": "Promo Toko", "aksi": "daftar_promo_utama", "ke": target})
    elif pt["harga_promo"] != target:
        aksi.append({"promo": "Promo Toko", "aksi": "set_harga", "dari": pt["harga_promo"], "ke": target})

    # 3b — GARANSI HARGA TERBAIK (kondisi pakai BEST price dari fakta garansi)
    if "Garansi Harga Terbaik" in by_jenis:
        best = (gar or {}).get("best", 0)
        sebab = []
        if best and best < target - GARANSI_SELISIH:
            sebab.append(f"best {best} < target-{GARANSI_SELISIH}")
        # margin@best < 7% -> DETAIL PENDING (dihitung pas modul garansi; user mau presisi)
        # sebab.append("margin@best <7%")  # <-- nanti
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
    cp = by_jenis.get("Campaign")
    if cp is not None:
        sebab = []
        if cp["harga_promo"] and cp["harga_promo"] < target * CAMPAIGN_FAKTOR:
            sebab.append(f"campaign {cp['harga_promo']} < target*{CAMPAIGN_FAKTOR}")
        if stok < CAMPAIGN_STOK_MIN:
            sebab.append(f"stok {stok} < {CAMPAIGN_STOK_MIN}")
        if pjh and stok < pjh:
            sebab.append(f"stok {stok} < penjualan/hari {pjh:.1f}")
        if sebab:
            aksi.append({"promo": "Campaign", "aksi": "takedown", "sebab": " & ".join(sebab)})

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
    Return list dict {item_id, model_id, sku, target, real, harga_awal, stok, pjh, kasus, aksi}."""
    baris = SQL.baca_baris_rubah(nama_toko)
    promo = SQL.baca_promo_detail(nama_toko)
    garansi = SQL.baca_garansi_best(nama_toko)
    penjualan = SQL.baca_penjualan_per_hari([b["item_id"] for b in baris])

    out = []
    for b in baris:
        key = (b["item_id"], b["model_id"])
        target, real, H, stok = b["harga_akhir"], b["harga_real"], b["harga_awal"], b["stok"]
        pjh = penjualan.get(b["item_id"], 0.0)

        if not target or target <= 0:
            kasus, aksi = "tanpa_target", []
        elif real == target:
            kasus, aksi = "sesuai", []
        elif H and target < H:
            kasus = "koreksi_turun"
            aksi = _cek_koreksi_turun(target, real, stok, pjh, promo.get(key, []), garansi.get(key))
        else:   # target >= harga awal (atau harga awal 0)
            kasus = "harga_dasar"
            aksi = [{"aksi": "ubah_harga_dasar", "ke": target,
                     "keluarkan": "SEMUA promo", "pasang_lagi": ["Paket Diskon", "Voucher"]}]

        out.append({"item_id": b["item_id"], "model_id": b["model_id"], "sku": b["sku"],
                    "target": target, "real": real, "harga_awal": H, "stok": stok,
                    "pjh": round(pjh, 1), "kasus": kasus, "aksi": aksi})
    return out


def ringkas(diagnosa):
    """Ringkasan jumlah per kasus + per jenis aksi (buat log/verifikasi)."""
    from collections import Counter
    kasus = Counter(d["kasus"] for d in diagnosa)
    aksi = Counter(a.get("promo", a.get("aksi")) for d in diagnosa for a in d["aksi"])
    return dict(kasus), dict(aksi)


# ══════════════════════════════════════════════════════════════════
#  SOLUSI — EKSEKUSI (poin 3a Promo Toko). DRY-RUN aware (config.DRY_RUN).
#  Urutan: lifecycle promo toko (buat/duplikat) -> set harga / daftar variasi.
# ══════════════════════════════════════════════════════════════════
import config  # noqa: E402


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
        print(f"[promo toko] [{nama_toko}] lifecycle gagal: {type(e).__name__}: {e}")

    if not aksi_pt:
        return {"set": 0, "daftar": 0, "terkirim": 0, "promo_toko": 0}

    # 2) Peta promo toko sekarang: {(item,model): {pid: harga}} + tentukan promo UTAMA.
    promos = grab_semua_promo(shop, session)
    if not promos:
        print(f"[promo toko] [{nama_toko}] belum ada promo toko (mungkin baru dibuat/DRY) — set/daftar ditunda.")
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
                print(f"[promo toko] [{nama_toko}] chunk {pid} gagal ({len(ch)}): {type(e).__name__}")
    mode = "DRY-RUN" if config.DRY_RUN else "LIVE"
    print(f"[promo toko] [{nama_toko}] ({mode}) set={n_set} daftar={n_daftar} -> {terkirim} entri terkirim, {gagal} gagal")
    return {"set": n_set, "daftar": n_daftar, "terkirim": terkirim, "gagal": gagal, "promo_toko": len(pids)}
