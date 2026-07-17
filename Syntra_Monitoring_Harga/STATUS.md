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

## 📍 PROGRES SEKARANG (update 17 Jul mlm) — SIAP RUNNING 10 TOKO
**Status: production-ready** (`MODE_LIVE=True` · `TOKO_AKTIF=[]` 10 toko). Tinggal `RUN.bat`.
⚠️ `MODUL_AKTIF` skrg TANPA garansi/campaign/flash (pilihan owner buat run awal) — modul itu +
CABUT-nya mati sampe dimasukin lagi (termasuk cabut 6 item tes pending-review + item lama di 957815).
- 🔧 **Config = control panel** — double-klik `RUN.bat` → scheduler · **`tes_harga.bat`** → tes 1 siklus SEKARANG (`JAM_TES=FULL` = semua tier dipaksa). Atur di `config.py`: `FASE_AKTIF` · `TOKO_AKTIF` · `MODUL_AKTIF` · jam trigger.
- ✅ **Paket** verified live + 17 Jul: **cap 2000/paket** (temuan owner, overflow → paket #2) · **ZIO/BEVERRA UNBLOCKED** (list error 1400101507 + kapasitas 0 → anggap kosong, lanjut buat; DRY: ZIO bakal enroll 935)
- ✅ **Voucher per-BAND + cap 2×AOV** verified live 13 Jul kimmioshop + 17 Jul BEVERRA (bisect poison LIVE) · **overflow >500 dipecah PER-KATEGORI UTUH** (spec owner 17 Jul; NOMIDE: B1 424 campur + B1#2 105 full 1 kategori) · produk mahal (band > cap 2×AOV) tetep TANPA voucher (keputusan owner 17 Jul)
- ✅ **Komisi grab** — FIXED 17 Jul (akar: body gql telat dibaca = kosong → drain berkala; live-verified YARRA 10 item kesimpen)
- ✅ Promo Toko — nyambung (Shopee kasih ct=8 di API produk)
- ✅ **Flash CABUT** — wire (ct=7) + self-heal stop→hapus→recreate produk sama TERVERIFIKASI LIVE 16 Jul (sesi 481492786769946→481954642538724 slot sama) · 17 Jul: sesi AKAN DATANG ikut diaudit (inject fakta flash ke diagnosa, 259 item DRY, exclude pelanggar pas daftar ulang)
- 🆕 **17 Jul (spec owner):** campaign daftar pakai **aturan Senin** (>1 hari: Senin minggu mulai · 1 hari: Senin terakhir sebelum tutup nominasi · kelewat=skip) · halaman /log clean (tabel event dibuang, ganti heartbeat per-modul) · keterangan fase 3 = kolom Alasan di halaman olah data (udah ada)
- ✅ **Garansi CABUT** — wire + withdraw TERVERIFIKASI LIVE 16 Jul di Alialia (count 168→167, bid ilang, lalu restore)
- ✅ **Campaign CABUT** — verified live 16-17 Jul: jalur per-jam FULL requests polos · **2 jalur (17 Jul mlm, rekaman owner): pending → `withdraw_entity` per-id (endpoint tombol batalkan UI), approved → opt_out batch** (fallback silang, jaga2 status basi) · liat sesi belum-mulai · bukti hidup statistik polos · **KPI pakai HARGA NET PENJUAL (`seller_offer_price`) — display murah krn Subsidi Shopee (`rebate_price`) = AMAN, jangan dicabut (spec owner)**
- 🔧 **Campaign PASANG** — gate KPI vs ceiling LIVE-PROVEN + aturan Senin. 🔴 Ceiling Shopee (0,85-0,98×tampil, dinamis) < KPI 0,985 di semua tes → bot skip semua (SESUAI spec "ga bisa daftar → skip"). Lead belum diuji: owner bisa daftar 1,5% via upload massal Excel — jalur Excel belum di-sniff.
- 📡 **Kesimpulan full-API (17 Jul, konklusif):** write + sesi + COUNT nominasi (get_session_list/statistics) = polos semua; baca DETAIL nominasi (nomination_id) = signature-locked PERMANEN (3 endpoint direplay payload identik → 90309999) → navigate-listen otomatis, dan cuma buat sesi ber-count>0. Alur bot = identik alur manual owner (rekaman 17 Jul).
- ✅ **Fase 3 (laporan)** — LIVE 17 Jul: siklus penuh fase 1→2→3 kimmioshop, 1217 alasan terkini ketulis DB (verified)
- ✅ **Poin 1–4 harga** — fase2 LIVE 17 Jul (ACC owner): promo toko 2 entri 0 gagal + campaign cabut (item lama 49909255539 dicabut SEMUA sesi, verified re-read). ⚠️ kasus `harga_dasar` (ubah harga awal) belum ada kejadian → jalur itu belum keuji live. ⚠️ opt_out FAKE-SUCCESS di status pending-review (10) → takedown skrg cuma cabut status 30, sisanya ditunda otomatis

**⚠️ NEXT SESSION:** baca PANDUAN §11 "HANDOFF" — **RENCANA BESAR 7 MILESTONE** (grilling 13–14 Jul, 29 keputusan). Progres: M−1 ✅ · M0 ✅ (log terpusat `log()`+`catat()` event, jalur siklus + semua modul low-level via `log()` CMD seragam, dashboard `/log` tabel event, prune log >30hr) · M1 ✅ (garansi 2-kolom · voucher fe_status · stok-habis→0 = akar voucher poison KELAR · auto-isi harga diskon) · M2 ✅ (Loop A→B · Fase 3 grab-ulang · alasan per-produk ke DB) · M3 ✅ logika (rem 30/40% gate · komisi peg +trigger Shopee `komisi_hold` · garansi takedown jam 2-kolom margin@Program · poin 4 re-attach→provisioning harian) — ⚠️ **BELUM LIVE, tes scope 1 toko + DRY dulu** ·
**M4 🔧 LIVE-tested 15 Jul (scope kimmioshop):** garansi/voucher/paket ✅ (1171/1174 harga sesuai, voucher `fe_status=2` BERLANGSUNG terverifikasi) · flash ✅ — ketauan bug per-model (harga model murah ke-max-in ke harga model mahal, fix `siapkan_produk`/`_entri`) + self-heal real-time ditambah (sniff 15 Jul: `set_shop_flash_sale` status=0 = HAPUS sesi, beda dari status=2=stop; alur skrg stop→hapus→bikin sesi baru di slot sama→daftar ulang produk sehat, TERVERIFIKASI slot beneran kebuka lagi abis dihapus — 23 sesi lama dihapus, provisioning ulang berhasil isi 23 sesi baru) ·
**⚠️ SISA PR (17 Jul mlm — kecil, bukan blocker running):**
1. `MODUL_AKTIF` masukin lagi `garansi`+`campaign`+`flash` pas run awal udah lancar (biar full + cabut 6 item pending & item lama 957815 jalan otomatis)
2. Campaign pasang: bakal skip semua selama KPI 1,5% < diskon minta Shopee — lead: sniff jalur upload massal Excel (owner klaim bisa 1,5% lewat situ)
3. Kasus `harga_dasar` (ubah harga awal) belum pernah kejadian live — pantau pas pertama muncul
4. Komisi SET/CABUT ke Shopee = manual owner (anti-bot; patokan harga komisi udah otomatis kepake)
5. Rem paket "list kosong palsu" belum ketemu kejadian nyata (standby, mock-verified)
