# RENCANA IMPLEMENTASI — Jahit Modul Promo/Upsell ke `run.py`

> **Untuk:** Fable (developer yang menggarap).
> **Konteks:** Semua modul promo/upsell (`paket_diskon.py`, `voucher.py`, `campaign.py`,
> `garansi.py`, `flash_sale_daftar.py`) **sudah dibangun & berdiri sendiri** (dites terpisah,
> requests-based, DRY_RUN-aware). Yang belum: **dijahit ke orkestrator `run.py`** biar jalan
> otomatis per-toko. Modul `komisi_api.py` ADA tapi butuh jalur UI-automation (SDK-sign) — **jangan
> dijahit dulu**, prioritas rendah.
> **Baca dulu:** `HANDOFF.md` §10 (detail tiap modul & endpoint) sebelum mulai.

---

## 0. Prinsip yang WAJIB dipatuhi (jangan dilanggar)

1. **Loop PER-TOKO, harvest sesi 1×.** Ikuti pola `run.py` sekarang: `grab_session()` sekali per
   toko, lalu SEMUA aksi (harga + upsell) pakai sesi itu, baru pindah toko. JANGAN harvest ulang
   per-modul (boros browser + rawan race port 9556).
2. **Hormatin `config.DRY_RUN`.** Semua modul sudah DRY_RUN-aware — jangan bypass. Default `MODE_LIVE`
   di `config.py` menentukan. Tes upsell baru WAJIB `MODE_LIVE=False` + 1 toko dulu (`TOKO_AKTIF=["kimmioshop"]`).
3. **Allowlist 10 toko.** `config.daftar_toko_aktif()` sudah membatasi. Jangan tembak toko di luar itu.
4. **Anti-hang.** Semua request pakai timeout tuple `(15, 60)` — sudah dipasang di tiap modul. Jangan
   ganti ke timeout tunggal.
5. **Jangan campur aduk dengan Fase harga (1–4).** Upsell = fase TERPISAH (lihat §2), dijalankan
   dengan jadwal beda (harga = tiap jam; upsell = harian/mingguan). Jangan bikin upsell jalan tiap jam.
6. **Catat tiap fase ke `siklus_log`** via `modules.log_siklus.catat_fase(pemicu, status, keterangan)`
   biar muncul di dashboard menu Log & /produk/harga. Pakai pemicu string baru per modul (lihat §2).

---

## 1. Verifikasi PRA-JAHIT (lakukan SEBELUM nulis kode orkestrasi)

Beberapa endpoint belum 100% diverifikasi live. Konfirmasi dulu (1 toko, DRY_RUN=False, manual)
biar nggak jahit sesuatu yang ternyata patah:

| # | Yang diverifikasi | Cara | Kalau gagal |
|---|---|---|---|
| A | **Campaign `submit`** (commit nominasi) | Lihat §3 (penjelasan verif submit campaign) | Cek header submit; kalau kena `x-sap-sec` → campaign submit butuh UI-automation (kecil kemungkinannya) |
| B | **Flash sale end-to-end** (`bikin_sesi` → `set_items` → `set_item_sequence`) | `flash_sale_daftar.daftar_mingguan(session,"kimmioshop",maks_sesi=1)` LIVE 1 sesi | `set_item_sequence` diketahui pernah `param error 1400101700` → sudah di-catch non-fatal; kalau `bikin_sesi`/`set_items` gagal, re-sniff endpoint |
| C | **Voucher tipe** ikuti_toko vs pembeli_baru | create 1 voucher tiap tipe, cek hasil di UI Shopee | payload 2 tipe nyaris sama (lihat `voucher.TIPE`) — betulin param pembeda |
| D | **`get_product_selector` flash** balikin item eligible | panggil `flash_sale_daftar._peta_selector(session)` | kalau kosong/URL salah, re-sniff endpoint selector |

> **Catatan:** `paket_diskon` (create), `campaign` (read + preview/add), `garansi` (list_ongoing)
> sudah TERBUKTI live 3 Jul — tinggal dijahit. `komisi` = SKIP (butuh UI-automation).

---

## 2. Desain orkestrasi — tambah "Fase Upsell" TERPISAH

Jangan tambal ke `FASE_AKTIF` [1–4] (itu siklus harga tiap jam). Buat jalur upsell sendiri.

### 2a. Config baru (`config.py`, blok PENGATURAN UTAMA)
```python
# ── UPSELL (promo non-harga) — jalur & jadwal TERPISAH dari fase harga ──
UPSELL_AKTIF = []          # modul upsell yg dijalankan saat `python run.py upsell`.
                            # pilihan: "paket_diskon","voucher","campaign","garansi_optout","flash_sale"
                            # []  = semua yang di UPSELL_DEFAULT
UPSELL_DEFAULT = ["paket_diskon", "voucher", "campaign", "garansi_optout"]
                            # flash_sale TIDAK default (mingguan, jalankan manual/terjadwal sendiri)

# Jadwal saran (dokumentasi; scheduler eksternal via Task Scheduler / RUN_UPSELL.bat):
#   paket_diskon + voucher : HARIAN (auto-renew H-1 sebelum mati, else bikin baru)
#   campaign               : HARIAN (nominasi ke sesi yg lagi buka window)
#   garansi_optout         : tiap siklus harga (opsional; atau harian) — buang item auto-lower
#   flash_sale             : MINGGUAN (grab slot 7 hari, rotasi produk)
```

### 2b. Entry point baru di `run.py`
Tambah cabang argumen (di blok `if __name__ == "__main__"`):
```python
elif arg in ("upsell", "promo"):
    jalankan_upsell(config.UPSELL_AKTIF or config.UPSELL_DEFAULT)
elif arg in ("flash", "flash_sale"):
    jalankan_upsell(["flash_sale"])   # mingguan, dipisah
```

### 2c. Fungsi orkestrator baru `jalankan_upsell(modul_list)` di `run.py`
Struktur MENIRU `jalankan_semua()` (loop per-toko, harvest 1×, try/except per toko, catat_fase di akhir):
```python
def jalankan_upsell(modul_list):
    toko = config.daftar_toko_aktif()
    mode = "DRY-RUN" if config.DRY_RUN else "LIVE"
    T = {m: {"ok": 0, "gagal": 0} for m in modul_list}
    for username, info in toko.items():
        nama = info["name"]
        try:
            session = grab_session(shop=username, i=info["i"])   # HARVEST 1×
            if "paket_diskon"   in modul_list: _upsell_paket_diskon(username, info, session, T)
            if "voucher"        in modul_list: _upsell_voucher(username, info, session, T)
            if "campaign"       in modul_list: _upsell_campaign(username, info, session, T)
            if "garansi_optout" in modul_list: _upsell_garansi_optout(username, info, session, T)
            if "flash_sale"     in modul_list: _upsell_flash(username, info, session, T)
        except Exception as e:
            print(... f"[{nama}] GAGAL upsell: {e}")
    close_session()
    for m in modul_list:
        catat_fase(f"upsell_{m}", keterangan=f"{T[m]['ok']} ok, {T[m]['gagal']} gagal | {mode}")
```

---

## 3. Wiring per-modul (fungsi `_upsell_*` yang harus ditulis)

Semua fungsi ambil `(username, info, session, T)` dan panggil orkestrator internal masing-masing modul.
Sumber produk = `harga_olah_data` (hasil grab Fase 1) — jadi **Fase 1 grab harus sudah jalan** sebelum upsell
(produk toko ada di DB). Kalau upsell dijalankan terpisah dari grab, pastikan DB sudah terisi grab terbaru.

### 3.1 `_upsell_paket_diskon` — 1 paket "beli banyak diskon" per toko
```python
import time
from modules import paket_diskon as PD
def _upsell_paket_diskon(username, info, session, T):
    nama = info["name"]
    now = int(time.time())
    deals = PD.list_deals(session)
    aktif = [d for d in deals if d.get("name","").startswith("UPSELL") and int(d.get("end_time") or 0) > now]
    if aktif:
        # sudah ada paket UPSELL berjalan → cukup enroll produk baru (validate+attach)
        bid = aktif[0]["bundle_deal_id"]
        r = PD.enroll_semua(session, PD.item_ids_toko(nama), bid,
                            aktif[0]["start_time"], aktif[0]["end_time"])
    else:
        # bikin paket baru 180 hari
        start, end = now + 300, now + 180*86400
        bid = PD.buat_deal(session, f"UPSELL {nama}", start, end)   # None kalau DRY_RUN
        if bid:
            r = PD.enroll_semua(session, PD.item_ids_toko(nama), bid, start, end)
    T["paket_diskon"]["ok"] += 1
```
**Aturan:** 1 toko = 1 paket bernama `UPSELL <toko>` (biar idempotent — jangan bikin duplikat tiap hari).
Tier default `2→1%, 3→2%, 7→3%` (`PD.TIER_DEFAULT`).

### 3.2 `_upsell_voucher` — auto-renew H-1 / bikin baru
```python
from modules import voucher as V
def _upsell_voucher(username, info, session, T):
    nama = info["name"]; now = int(time.time())
    vouchers = V.list_vouchers(session)
    ours = [v for v in vouchers if str(v.get("voucher_code","")).startswith("UP")]
    if any(V.perlu_perpanjang(v, now) for v in ours):
        for v in ours:
            if V.perlu_perpanjang(v, now):
                V.perpanjang_voucher(session, v["voucher_id"], now + 30*86400)
    elif not ours:
        mp = V.min_price_toko(nama)                 # = 2×AOV×0.97
        V.buat_voucher(session, f"UPSELL {nama}", "UP"+..., now+300, now+30*86400,
                       discount=2, min_price=mp, max_value=None, **V.TIPE["ikuti_toko"])
    T["voucher"]["ok"] += 1
```
**Aturan:** kode voucher prefix `UP` (idempotent). `min_price = V.min_price_toko(nama)` (jangan hardcode).
Untuk voucher PRODUK per-band, pakai `V.bagi_produk_per_band()` (lihat §10.3 handoff) — fase lanjutan,
mulai dari voucher ikuti_toko dulu.
⚠️ **Verifikasi C dulu** sebelum pakai `TIPE["pembeli_baru"]`.

### 3.3 `_upsell_campaign` — nominasi semua produk ke sesi yang buka window
```python
from modules import campaign as C
def _upsell_campaign(username, info, session, T):
    nama = info["name"]
    sesi = C.open_sessions(session, keywords=config.CAMPAIGN_KEYWORDS)  # cuma sesi buka nominasi
    for s in sesi:
        already = C.get_nominated(session, s["session_id"])            # skip yg sudah ternominasi
        prod = [p for p in C.produk_toko(nama)
                if not all((str(p["item_id"]), str(m)) in already for m in p["models"])]
        C.nominate(session, s["session_id"], prod)
    T["campaign"]["ok"] += 1
```
**Aturan:** hanya sesi dengan `nomination_start ≤ now ≤ nomination_end` (sudah difilter `open_sessions`).
Skip produk yang sudah ternominasi (hemat + hindari error). ⚠️ **Verifikasi A dulu** (submit).

### 3.4 `_upsell_garansi_optout` — buang item yang di-auto-lower Garansi
Ini NYELESAIN PR harga §9 #4 (Garansi auto-nurunin harga → koreksi harga percuma).
```python
from modules import garansi as G
def _upsell_garansi_optout(username, info, session, T):
    ongoing = G.list_ongoing(session)                 # {(item,model): {bid_id,...}}
    if ongoing:
        G.withdraw_produk(session, set(ongoing.keys()), ongoing=ongoing)  # opt-out SEMUA
    T["garansi_optout"]["ok"] += 1
```
**Aturan:** untuk kontrol harga, kita mau SEMUA produk KELUAR dari Garansi (biar harga bot tidak
ditarik balik). Kalau nanti mau selektif (cuma yang bentrok target), filter `kunci_set`-nya.
**Urutan penting:** jalankan `garansi_optout` **SEBELUM** Fase 2 (rubah harga) kalau digabung —
biar saat bot set harga, Garansi sudah tidak menarik balik. Kalau upsell jalur terpisah, jadwalkan
opt-out tepat sebelum siklus harga.

### 3.5 `_upsell_flash` — daftar flash sale mingguan (MINGGUAN, jangan harian)
```python
from modules import flash_sale_daftar as FSD
def _upsell_flash(username, info, session, T):
    r = FSD.daftar_mingguan(session, info["name"])    # grab slot 7hr, rotasi produk 50/sesi
    T["flash_sale"]["ok"] += r.get("sesi", 0)
```
**Aturan:** JALANKAN MINGGUAN (`python run.py flash`), bukan tiap hari — flash sale sesi berlaku
seminggu, daftar tiap hari = tumpuk sesi. Harga flash = `harga_diskon − 10` (sudah di modul).
⚠️ **Verifikasi B & D dulu.**

---

## 4. Scheduler (RUN.bat / Task Scheduler)

Buat 2 .bat baru (nyontek `RUN.bat` yang ada, yang set env lalu `python run.py ...`):
- **`RUN_UPSELL.bat`** → `python run.py upsell` — jadwalkan **HARIAN** (mis. 09:00) via Task Scheduler.
- **`RUN_FLASH.bat`** → `python run.py flash` — jadwalkan **MINGGUAN** (mis. Senin 10:00).

`RUN.bat` yang ada tetap buat siklus harga (tiap jam). Ketiganya CMD/proses terpisah tapi tetap
port 9556 → **jangan jadwalkan bentrok jam** dengan siklus harga (kasih selisih menit; harvest sesi
tidak boleh barengan di port yang sama).

---

## 5. Urutan pengerjaan yang disarankan (biar aman & bisa dites bertahap)

1. **Verifikasi §1 (A–D)** manual 1 toko. Catat hasil.
2. Tambah config §2a + entry point §2b + kerangka `jalankan_upsell` §2c (belum panggil modul).
3. Jahit `garansi_optout` (§3.4) dulu — paling simpel & langsung berguna (nyelesain PR harga §9 #4).
   Tes DRY → LIVE 1 toko.
4. Jahit `paket_diskon` (§3.1) → tes DRY → LIVE Kimmioshop (toko terkecil).
5. Jahit `campaign` (§3.3) setelah verif A lolos.
6. Jahit `voucher` (§3.2) setelah verif C lolos (mulai ikuti_toko).
7. Jahit `flash_sale` (§3.5) setelah verif B & D lolos. Tes `maks_sesi=1` dulu.
8. Buat .bat + daftarkan Task Scheduler (§4).
9. Update `HANDOFF.md` §10.9 (tandai modul yang sudah dijahit) + mirror ke `99. server/`.

---

## 6. Checklist "Definition of Done"
- [ ] `python run.py upsell` jalan DRY 1 toko tanpa error, log rencana masuk akal.
- [ ] `python run.py upsell` LIVE Kimmioshop: paket diskon + voucher kebikin, garansi opt-out jalan.
- [ ] `python run.py flash` LIVE Kimmioshop `maks_sesi=1`: 1 sesi kebikin, produk masuk.
- [ ] Tiap modul nyatet ke `siklus_log` (cek dashboard /log).
- [ ] DRY_RUN benar-benar tidak mengubah Shopee (verifikasi di UI).
- [ ] Idempotent: jalankan 2× tidak bikin paket/voucher duplikat.
- [ ] `.bat` + Task Scheduler terpasang, jam tidak bentrok siklus harga.
- [ ] `komisi` TIDAK dijahit (masih butuh UI-automation — biarkan di TODO).
