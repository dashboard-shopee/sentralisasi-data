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


def _cek_koreksi_turun(target, stok, pjh, promos, gar):
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
            aksi = _cek_koreksi_turun(target, stok, pjh, promo.get(key, []), garansi.get(key))
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
