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
FASE 3 (LAPORAN) → rangkum hasil aksi                                          ⏳ belum dibikin
```
**1 KESATUAN:** double-klik `RUN.bat` → scheduler jalanin fase yg ada di `FASE_AKTIF` (skrg `[1]`).
Fase tetap fungsi DISTINCT (siklus_fase1/siklus_fase2) tapi diorkestrasi 1 scheduler. Fase 2 selalu pakai data FRESH.

---

## 📅 JADWAL (kapan modul digerakin)

| Kapan | LIHAT (Fase 1) | TINDAK (Fase 2) |
|---|---|---|
| **Tiap jam** :05 | grab produk, harga, stok + promo toko | **Poin 1–4 (kontrol harga + CABUT, per-produk):** benerin harga · cabut garansi/flash/campaign yg ga aman · keluarin-pasang balik produk dari paket/voucher pas ubah harga awal · set/daftar promo toko |
| **Tiap hari** 02:00 | grab komisi, garansi, voucher, paket, campaign, flash | **Poin 5 (PASANG):** paket 🔴 · voucher · garansi + banding komisi |
| **Tiap minggu** | — (pakai data harian) | **Poin 5 (PASANG):** campaign · flash |

*(Grab ≠ aksi: campaign & flash digrab HARIAN — supaya cabut per-jam pakai data ga basi — tapi PASANG-nya tetap mingguan.)*

**Poin 1–4 (cabut) = TIAP JAM semua promo. Poin 5 (pasang) = per cadence.** Cabut cepet, pasang santai.
*(Fase 2 UDAH kejahit ke scheduler via `FASE_AKTIF` (`siklus_fase2`) — set `FASE_AKTIF=[1,2]` buat nyalain. Default `[1]`. Live/DRY ikut **`MODE_LIVE`** (1 saklar, semua modul bareng). Command manual `run.py fase2`/`provisioning` tetap ada.)*

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

### 5. VOUCHER  🟡 *(← NEXT — lagi dibahas)*
- 👀 *harian:* voucher jalan + akan datang
- 🔧 *jam:* keluarin-pasang balik **per-produk** pas ubah harga awal
- ➕ *harian:* belum ada → buat voucher **SHOP-WIDE** (diskon flat **2% semua produk**, min belanja 2×AOV, auto-perpanjang H-1). Shop-wide = otomatis nutupin semua produk, ga perlu enroll per-produk.
- ⏳ **DECISION PENDING (owner):** voucher mau tetap **perpanjang** (skrg, endpoint jalan) atau **buat-baru** (kaya paket)? Detail di PANDUAN. Belum dites live.

### 6. CAMPAIGN  🟡
- 👀 *harian:* sesi campaign (berjalan+akan datang) + nominasi *(grab harian, pasang mingguan)*
- 🔧 *jam:* cabut kalau < target×98,5% **atau** stok < 30 **atau** stok < pjh
- ➕ *mingguan:* daftar kalau potongan ≤ target×98,5% **&** stok > 50 **&** stok > 10×pjh

### 7. FLASH  🟡 *(cabut: endpoint rusak)*
- 👀 *harian:* sesi flash (berjalan+akan datang) + item *(grab harian, pasang mingguan)*
- 🔧 *jam:* cabut kalau < target−10 **atau** stok 0  ⚠️ endpoint rusak
- ➕ *mingguan:* sesi s/d 7 hari; maks 50/sesi, per-kategori penjualan tertinggi; harga kini−10; stok > 50 **atau** > 10×pjh; stok promo maks 350

*(pjh = penjualan/hari rata2 30 hari, dari Shopee BUKAN ERP. "target" jadi Harga Komisi kalau produk aktif komisi.)*

---

## 📊 FASE 3 — LAPORAN  ⏳
Rangkum aksi robot tiap hari (harga dibenerin, promo dipasang/dicabut) → dashboard.

---

## 📍 PROGRES SEKARANG (update 13 Jul)
Fase 1 (grab) jalan **semua toko** (kebukti, 0 anti-bot). Fase 2 (aksi) = command terpisah, verifikasi live bertahap per-modul.
- 🔧 **Config = control panel** — double-klik `RUN.bat` → scheduler. Atur di `config.py`: `FASE_AKTIF` · `TOKO_AKTIF` · `MODUL_AKTIF` · jam trigger. Trigger bulanan dibuang (housekeeping → mingguan), legacy Sheet dibersihin, KPI dicek sesuai.
- ✅ **Paket** verified live (command manual) — logika beres + refinement 12 Jul (buat-baru, 1 paket, cap dilepas)
- 🟡 **Voucher** = NEXT — logika beres (shop-wide 2%), **nunggu owner putusin perpanjang/buat-baru**, terus tes live
- 🟡 Garansi / Promo Toko / Campaign / Flash — logika beres, belum tes live
- ⏳ Fase 3 (laporan), ⏳ Poin 1–4 harga (logika beres, belum PERNAH diverifikasi live — hati2 pas nyalain MODE_LIVE)

**⚠️ NEXT SESSION:** baca PANDUAN §11 "HANDOFF" — ada decision pending, perubahan belum di-commit, & langkah lanjut.
⚠️ Open lain: takedown flash endpoint RUSAK · paket ZIOSCARF/BEVERRA flaky Shopee (hold).
