# 🧵 BENANG MERAH — Syntra Monitoring Harga

> **Acuan tunggal.** SPEC program (3 fase, per-modul) + PROGRES (penanda simbol).
> ⚠️ **Isi spec DIKUNCI** — jangan nambah/ngubah tanpa perintah owner. Tiap kerja, yang di-update **cuma penanda progres** (jangan nambah tulisan).
> 📝 Penjelasan santai, catatan, temuan teknis, backlog → **`PANDUAN_PROGRAM.md`** (bukan di sini).
> **Penanda:** ✅ jalan · 🔴 live · 🟡 logika beres, belum live · 🔧 dikerjain · ⏳ belum

---

## 🔁 ALUR — 3 FASE (1 program, scheduler jalanin sesuai `config.FASE_AKTIF`)

```
FASE 1 (FAKTA)   → grab data terbaru semua toko (READ-ONLY)
FASE 2 (AKSI)    → benerin harga (poin 1-4, per-jam) + pasang/cabut promo (poin 5, per-cadence)
                   Mode ikut MODE_LIVE (1 saklar): live/DRY SEMUA modul bareng
FASE 3 (LAPORAN) → Loop B: grab-ulang status TERKINI + tulis alasan             🟡 dibikin (belum live)
```
**1 KESATUAN:** double-klik `RUN.bat` → scheduler jalanin fase yg ada di `FASE_AKTIF` (skrg `[1]`).
Orkestrasi = **`siklus_terpadu`** (13 Jul): SATU loop toko, SATU ambil sesi per toko buat semua fase. Fase 2 selalu pakai data FRESH (grab fase 1 barusan).

---

## 📅 JADWAL (kapan modul digerakin)

| Kapan | LIHAT (Fase 1) | TINDAK (Fase 2) |
|---|---|---|
| **Tiap jam** :05 | grab produk, harga, stok + promo toko | **Poin 1–4 (kontrol harga + CABUT, per-produk):** benerin harga · cabut garansi/flash/campaign yg ga aman · keluarin-pasang balik produk dari paket/voucher pas ubah harga awal · set/daftar promo toko |
| **Tiap hari** 02:00 | grab komisi, garansi, voucher, paket, campaign, flash | **Poin 5 (PASANG):** paket 🔴 · voucher · garansi + banding komisi |
| **Tiap minggu** | — (pakai data harian) | **Poin 5 (PASANG):** campaign · flash |

*(Grab ≠ aksi: campaign & flash digrab HARIAN — supaya cabut per-jam pakai data ga basi — tapi PASANG-nya tetap mingguan.)*

**Poin 1–4 (cabut) = TIAP JAM semua promo. Poin 5 (pasang) = per cadence.** Cabut cepet, pasang santai.
*(Fase 1+2 kejahit ke scheduler via `FASE_AKTIF` (`siklus_terpadu`, 1 sesi per toko) — set `FASE_AKTIF=[1,2]` buat nyalain fase 2. Live/DRY ikut **`MODE_LIVE`** (1 saklar, semua modul bareng). Command manual `run.py fase2`/`provisioning` tetap ada.)*

---

## ⚙️ POIN 1–4 — KONTROL HARGA (tiap jam, per produk)

1. Target kosong → skip ("tanpa target").
2. Harga real = target → skip ("sudah sesuai").
3. Harga real ≠ target **&** target < harga awal → cek berurutan:
   - **① Komisi:** aktif? → target diganti jadi **Harga Komisi** (patokan semua promo di bawah).
   - **② Promo Toko:** belum ada → daftarin · udah ada → set harga promo = target.
   - **③ Garansi:** cabut kalau best < target−500 **atau** margin < 7%.
   - **④ Flash:** cabut kalau < target−10 **atau** stok 0.
   - **⑤ Campaign:** cabut kalau < target×98,5% **atau** stok < 30 **atau** stok < pjh.
4. Harga real ≠ target **&** target ≥ harga awal → **UBAH HARGA DASAR:** keluarin produk dari SEMUA promo (promo toko, garansi, paket, voucher, flash, campaign) → ubah harga awal → pasang balik **paket & voucher** (wajib selalu nempel).

---

## 📦 PER-MODUL — spec + progres
Format tiap modul: 👀 LIHAT (Fase 1) · 🔧 CABUT (poin 1–4, tiap jam) · ➕ PASANG (poin 5)
📌 **Grab promo (Promo Toko–Flash) = CUMA yang BERJALAN + AKAN DATANG.** Yang udah BERAKHIR dibuang.

### 1. KOMISI  🔴 *(grab + harga otomatis · set/takedown komisi MANUAL)*
- 👀 *harian:* produk mana aktif komisi (halaman affiliate, semua toko) + banding vs Syntra
- 🔧 *jam:* komisi aktif → harga komisi jadi patokan semua promo
- ➕ *harian:* banding → (a) sesuai · (b) harusnya-dikomisikan · (c) harusnya-dicabut
- 📌 **Yang MANUAL cuma SET/TAKEDOWN komisinya** (bot nuntun via dashboard, API mustahil). **Harga tetap dirubah OTOMATIS** — lewat promo toko atau harga awal, tergantung keadaan.

### 2. PROMO TOKO  🟡
- 👀 *jam:* promo jalan + akan datang + produknya
- 🔧 *jam:* belum ada → daftarin ke promo utama · udah ada → set harga promo = target
- ➕ *jam:* buat/duplikat, masukin produk yg target < harga awal

### 3. GARANSI  🟡
- 👀 *harian:* 3 harga (Kini/Terbaik/Program) + status (belum-daftar / terbaik / perlu-ditinjau)
- 🔧 *jam:* cabut kalau best < target−500 **atau** margin < 7%
- ➕ *harian:* daftar kalau best ≥ target−500 **&** margin ≥ 7% **&** stok > 0 · "perlu ditinjau" → batalin

### 4. PAKET  🔴 *(logika verified LIVE · jalan lewat command `provisioning paket`)*
- 👀 *harian:* paket (berjalan+akan datang) + produk di tiap paket (membership)
- 🔧 *jam:* keluarin-pasang balik produk **per-produk** pas ubah harga awal (poin 4)
- ➕ *harian:* produk belum masuk paket manapun → masukin UPSELL, **target 1 PAKET** (batas item Shopee ga ketauan → ga overflow). Tier 2→1% / 3→2% / 7→3%. Belum ada → buat. Jelang-expire → **buat baru** (bukan perpanjang). Konsolidasi ke 1 paket: **owner hapus paket lain manual**, bot isi sisanya ke UPSELL.

### 5. VOUCHER  🔴 *(PASANG per-band + edit-item verified LIVE 13 Jul)*
- 👀 *harian:* voucher jalan + akan datang
- 🔧 *jam:* keluarin-pasang balik **per-produk** pas ubah harga awal *(edit items verified live)*
- ➕ *harian:* voucher **PRODUK per BAND harga** (spec owner 13 Jul): band 1–14.999 lalu per 20rb (grid FIX), **min belanja = batas atas band + 1** → maksa pembeli ambil **≥2 pcs**. **CAP 2×AOV:** band yg min-nya > 2×AOV dibuang → **produk mahal TANPA voucher** (aturan Shopee min order ≤ 2×AOV). Harga produk berubah → otomatis **pindah voucher band** (reconcile items tiap run). Diskon 2%, 1 voucher per band, jelang-expire (H-1) → **buat baru**.

### 6. CAMPAIGN  🟡
- 👀 *harian:* sesi campaign (berjalan+akan datang) + nominasi *(grab harian, pasang mingguan)*
- 🔧 *jam:* cabut kalau < target×98,5% **atau** stok < 30 **atau** stok < pjh
- ➕ *mingguan:* daftar kalau potongan ≤ target×98,5% **&** stok > 50 **&** stok > 10×pjh

### 7. FLASH  🟡 *(cabut = AKHIRI SESI, endpoint kelar; belum live)*
- 👀 *harian:* sesi flash (berjalan+akan datang) + item *(grab harian, pasang mingguan)*
- 🔧 *jam:* cabut kalau < target−10 **atau** stok 0 → **AKHIRI SESI** (stop_sesi, bukan per-item)
- ➕ *mingguan:* sesi s/d 7 hari; maks 50/sesi, per-kategori penjualan tertinggi; harga kini−10; stok > 50 **atau** > 10×pjh; stok promo maks 350

*(pjh = penjualan/hari rata2 30 hari, dari Shopee BUKAN ERP. "target" jadi Harga Komisi kalau produk aktif komisi.)*

---

## 📊 FASE 3 — LAPORAN  🟡 *(logika beres, belum live)*
**Loop B** (abis Loop A fase1+2 semua toko): grab-ulang SEMUA modul (kaya Fase 1, per tier) →
status TERKINI + tulis **alasan** per produk ke `harga_olah_data.alasan`. Jeda propagasi GRATIS
dari lamanya Loop A (aksi fase 2 udah settle pas balik grab). Alasan = narasi aksi (Loop A) +
verifikasi terkini (`✓ harga sesuai target` / `⚠ belum sesuai (real X)`). Nyala kalau `FASE_AKTIF`
memuat `3`. Heartbeat `laporan` → dashboard /log.

---

## 📍 PROGRES SEKARANG (update 13 Jul)
Fase 1 (grab) jalan **semua toko** (kebukti, 0 anti-bot). Orkestrasi = `siklus_terpadu` (1 sesi/toko, semua fase). Verifikasi live bertahap per-modul.
- 🔧 **Config = control panel** — double-klik `RUN.bat` → scheduler · **`tes_harga.bat`** → tes 1 siklus SEKARANG (`JAM_TES=FULL` = semua tier dipaksa). Atur di `config.py`: `FASE_AKTIF` · `TOKO_AKTIF` · `MODUL_AKTIF` · jam trigger.
- ✅ **Paket** verified live (command manual) — logika beres + refinement 12 Jul (buat-baru, 1 paket, cap dilepas)
- ✅ **Voucher per-BAND + cap 2×AOV** verified live 13 Jul di kimmioshop (222 produk → 3 band 🟢 fe_status BERLANGSUNG, 6 produk mahal tanpa voucher, idempoten, pindah-item verified) — sisa: **rollout 9 toko lain**
- 🟡 Garansi / Promo Toko / Campaign / Flash — logika beres, belum tes live
- ⏳ Fase 3 (laporan), ⏳ Poin 1–4 harga (logika beres, belum PERNAH diverifikasi live — hati2 pas nyalain MODE_LIVE)

**⚠️ NEXT SESSION:** baca PANDUAN §11 "HANDOFF" — **RENCANA BESAR 7 MILESTONE** (grilling 13–14 Jul, 29 keputusan). Progres: M−1 ✅ · M0 ✅ (log terpusat `log()`+`catat()` event, jalur siklus + semua modul low-level via `log()` CMD seragam, dashboard `/log` tabel event, prune log >30hr) · M1 ✅ (garansi 2-kolom · voucher fe_status · stok-habis→0 = akar voucher poison KELAR · auto-isi harga diskon) · M2 ✅ (Loop A→B · Fase 3 grab-ulang · alasan per-produk ke DB) · M3 ✅ logika (rem 30/40% gate · komisi peg +trigger Shopee `komisi_hold` · garansi takedown jam 2-kolom margin@Program · poin 4 re-attach→provisioning harian) — ⚠️ **BELUM LIVE, tes scope 1 toko + DRY dulu** ·
**M4 🔧 LIVE-tested 15 Jul (scope kimmioshop):** garansi/voucher/paket ✅ (1171/1174 harga sesuai, voucher `fe_status=2` BERLANGSUNG terverifikasi) · flash ✅ — ketauan bug per-model (harga model murah ke-max-in ke harga model mahal, fix `siapkan_produk`/`_entri`) + self-heal real-time ditambah (sniff 15 Jul: `set_shop_flash_sale` status=0 = HAPUS sesi, beda dari status=2=stop; alur skrg stop→hapus→bikin sesi baru di slot sama→daftar ulang produk sehat, TERVERIFIKASI slot beneran kebuka lagi abis dihapus — 23 sesi lama dihapus, provisioning ulang berhasil isi 23 sesi baru) ·
**campaign ❌ LIVE-tested 15 Jul, GAGAL 2 masalah baru** — (1) `campaign_util.api_post_browser` (fetch via `run_js` di dalem browser) sendiri ga reliable: percobaan pertama "js result parsing error", abis itu SEMUA retry "Failed to fetch" (network-level, browser gagal reach Shopee) — endpoint blm kebukti kerja lewat jalur ini. (2) **LEBIH SERIUS**: `buka_page_toko()` (browser KEDUA dibuka buat campaign, browser PERTAMA masih dipakai `requests` session modul lain) ke-bukti bikin Shopee ROTASI token `SPC_CDS` — abis campaign jalan, SEMUA modul lain (flash/voucher/paket/promo_toko/garansi) langsung "token not found" 403 beruntun. **MITIGASI DARURAT:** `campaign` dicabut dari `MODUL_AKTIF` + semua 4 titik panggil (`eksekusi_takedown_campaign` di 2 tempat, `update_harga.edit_harga_dasar`) di-gate `"campaign" in config.MODUL_AKTIF` biar ga ke-trigger dari data lama pas campaign off. **Campaign PARKIR — jangan nyalain lagi sampe ada solusi buat 2 masalah di atas** (kandidat: cari cara run_js yg lebih stabil, ATAU isolasi total browser campaign dari browser session `requests` — mungkin perlu re-harvest session SETELAH campaign jalan).
⚠️ Open lain: 3 toko flaky deal-numpuk (M5) · voucher bisect-on-fail (M5) · config.py MASIH `MODE_LIVE=True` scope kimmioshop (belum di-revert ke DRY default).
