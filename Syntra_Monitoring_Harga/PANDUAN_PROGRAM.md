# 📘 Panduan Gampang — Program Syntra Monitoring Harga

> Buat lo yang pengen ngerti program ini kerjanya gimana, **tanpa pusing istilah teknis**.
> Baca santai. Kalau ada yang ga sesuai sama mau lo, tinggal bilang, kita rubah.
>
> ⚠️ **`STATUS.md` = BENANG MERAH program ini — JANGAN diotak-atik sembarangan.** Itu PARAMETER kita buat tau
> sejauh mana program udah ditangani (spec 3 fase + penanda progres). Tiap ada perubahan, update DUA-duanya:
> penanda progres di STATUS.md + detail/catatannya di file PANDUAN ini. Kalau PANDUAN beda sama STATUS → samain ke STATUS.
> **Pembagian:** STATUS = spec + progres ringkas (simbol) · PANDUAN = penjelasan + intent owner + catatan/detail teknis.

---

## 1. Ini program apa sih, sederhananya?

Bayangin lo punya **karyawan robot** yang jagain toko Shopee lo **24 jam**. Kerjaannya cuma satu tujuan:

> **Mastiin harga jual & semua promo di toko lo selalu bener, tanpa lo harus ngecek manual satu-satu.**

Lo kan punya banyak produk, banyak toko, banyak jenis promo (diskon, voucher, flash sale, dll). Ngatur itu semua manual = capek, gampang kelewat, gampang salah. Robot ini yang ngerjain otomatis.

---

## 2. Robotnya kerja lewat 3 tahap (3 "Fase")

Gampangnya kayak alur kerja karyawan:

| Fase | Ibaratnya | Kerjaannya |
|---|---|---|
| **Fase 1 — FAKTA** | *"Ngecek dulu"* | Ngumpulin data: produk apa aja, harganya berapa, stok berapa, lagi ikut promo apa aja. Cuma **NGELIAT**, ga ngubah apa-apa. |
| **Fase 2 — TINDAKAN** | *"Baru bertindak"* | Dari data tadi, robot mutusin & **ngelakuin**: benerin harga, pasang/cabut promo. |
| **Fase 3 — LAPORAN** | *"Lapor ke bos"* | Ngasih tau lo: tadi robot ngapain aja, hasilnya gimana. *(ini belum dibikin)* |

Intinya: **liat dulu (1) → bertindak (2) → lapor (3).** Robot ga bisa bertindak bener kalau datanya (Fase 1) ga lengkap/basi. Makanya Fase 1 penting banget.

---

## 3. Ada 7 jenis promo yang diurus robot

Toko Shopee lo punya macam-macam promo. Robot ngurus 7 jenis ini:

1. **Komisi (Affiliate)** — bayar komisi ke affiliate biar produk lo dipromosiin orang.
2. **Promo Toko** — diskon langsung dari toko.
3. **Garansi Harga Terbaik** — jaminan harga termurah.
4. **Paket Diskon** — beli banyak lebih murah (beli 2 diskon 1%, dst). *Upsell.*
5. **Voucher** — kupon diskon.
6. **Campaign** — ikut event/kampanye Shopee.
7. **Flash Sale** — diskon kilat waktu terbatas.

**Penting — tiap promo punya 2 macam kerjaan dengan jadwal BEDA:**

- **① CABUT / benerin harga (poin 1–4) → TIAP JAM, level PER-PRODUK.** Ada 2 sebab:
  - **Harga promo kemurahan / stok abis** → **garansi, flash, campaign** dicabut biar ga rugi.
  - **Mau ubah harga awal produk** → produk **dikeluarin dari SEMUA promo** (termasuk **paket & voucher**), harga diubah, terus **paket & voucher dipasang balik** (2 ini wajib selalu nempel).
  Semua ini **per-PRODUK** (bukan matiin voucher/paket/promo rame-rame) dan jalan **tiap jam**.
- **② PASANG promo baru (poin 5) → jadwalnya per modul:**
  - *Tiap hari:* komisi, garansi, paket, voucher.
  - *Tiap minggu:* campaign, flash sale.

Contoh **Campaign**: kalau harganya kemurahan → **dicabut tiap jam**; tapi **pasang** campaign baru cuma **tiap minggu**. Contoh **Voucher/Paket**: produknya **dikeluarin-dipasang balik per-produk tiap jam** kalau harga awalnya berubah; tapi **daftarin produk baru** ke voucher/paket cuma **tiap hari**. Jadi 1 promo bisa punya 2 jadwal. Ini yang disebut **"cadence per-modul"**.

---

## 4. Aturan emas: "Harga Komisi jadi patokan"

Ini konsep penting. Kalau sebuah produk lagi **aktif komisi**, maka:

> **Harga komisi jadi PATOKAN buat semua promo produk itu.**

Contoh: produk A harga komisinya Rp32.999. Maka robot bakal atur semua promo (promo toko, dll) **ngikut Rp32.999**, bukan harga target biasa. Kenapa? Biar ga rugi — jangan sampai lo bayar komisi tapi jualnya kemurahan.

Kalau produk **ga ada komisi aktif**, robot pakai "harga target" biasa yang lo tentuin.

---

## 5. Gimana robot mutusin soal harga? (logika poin 1–4, TIAP JAM)

Buat tiap produk, robot ngecek **berurutan** gini:

1. **Ga ada target harga?** → dilewatin ("tanpa target").
2. **Harga real udah = target?** → udah bener, dilewatin ("sudah sesuai").
3. **Harga real ≠ target, DAN target < harga asli?** → robot rapihin. Dicek satu-satu:
   - **① Komisi (paling utama, dicek DULUAN):** ada komisi aktif di halaman komisi ga? Kalau **ADA** → **target langsung diganti jadi Harga Komisi**, dan semua promo di bawah ini **patokannya jadi harga komisi** (bukan target lagi). Kalau harga sekarang beda dari harga komisi → disamain.
   - **② Promo Toko:** produk **belum ada** di promo toko → **daftarin** ke promo utama. **Udah ada** → **set harga promo toko = target**.
   - **③ Garansi Terbaik:** **cabut** kalau Harga Terbaik **< target − Rp500** ATAU margin **< 7%**.
   - **④ Flash Sale:** harusnya target − Rp10; **cabut** kalau **< target − Rp10** ATAU **stok 0**.
   - **⑤ Campaign:** harusnya target × 98,5%; **cabut** kalau **< target × 98,5%** ATAU **stok < 30** ATAU **stok < penjualan/hari**.
4. **Harga real ≠ target, DAN target ≥ harga asli?** → **UBAH HARGA DASAR:** keluarin produk dari **SEMUA promo dulu** (promo toko, garansi, paket, voucher, flash, campaign) → ubah harga asli → **pasang balik cuma paket & voucher** (2 promo ini wajib selalu nempel, sisanya nggak).

> 💡 **Kunci poin 3:** komisi dicek **paling awal**. Kalau produk aktif komisi, harga komisi jadi patokan buat SEMUA promo di bawahnya. Kalau nggak, baru pakai target biasa.

Angka batasnya (misal "garansi dicabut kalau untung di bawah 7%") semua bisa lo atur di satu tempat (`config.py`), ga usah ngoprek kode.

---

## 6. 🎯 SEKARANG UDAH SAMPAI MANA? (jujur)

Gambaran gede: **mesinnya udah jadi hampir semua. Sekarang tahap "dites beneran satu-satu."**

| Bagian | Status | Artinya |
|---|---|---|
| **Fase 1 (kumpulin data)** | 🟢 **~95% jalan** | Dipakai tiap hari, udah reliable. |
| **Fase 2 (tindakan) — logika** | 🟢 **100% dibikin** | Semua aturan udah ditulis & lulus **simulasi**. |
| **Fase 2 — tes beneran (live)** | 🟡 **baru mulai** | Paket ✅ lulus. 6 modul lain **antre**. |
| **Fase 3 (laporan)** | 🔴 **belum mulai** | Nunggu Fase 2 kelar dites. |

**Ibarat bikin mobil:** mobilnya udah jadi, mesin udah nyala di garasi (= simulasi jalan). Sekarang kita bawa ke jalan raya, **tes satu sistem per satu** (rem dulu, baru setir, dst). Baru "Paket Diskon" yang udah lulus tes jalan raya. Sisanya nyusul.

*(Status detail per promo + spec lengkap ada di `STATUS.md`.)*

---

## 7. ❓ "Kok Fase 1 dibenerin lagi? Kok masih ada yang belum beres?"

Ini yang bikin lo emosi, dan wajar. Gua jelasin jujur:

**Ini NORMAL, dan bukan berarti programnya ancur.** Ini justru tanda kita lagi di tahap yang bener.

Waktu kita **tes Paket Diskon beneran** (bukan simulasi) buat pertama kali, ketahuan ada 1 "kabel" yang ga kepasang bener: fungsi buat baca daftar paket **balik kosong** — padahal paketnya jelas ada. Ini **cuma ketahuan pas dites beneran di Shopee**, ga akan keliatan di simulasi. Udah gua benerin, dan sekarang jalan.

Analoginya: pas tes mobil di jalan, ketahuan ada 1 kabel rem kurang nyolok. Itu **bukan mobilnya jelek** — itu tandanya **tes jalan rayanya kerja** (nemuin masalah sebelum lo pake beneran). Kalau kita ga tes, masalah itu diem-diem ada dan baru ketahuan pas udah dipake di 10 toko.

**Jadi "belum beres" di sini artinya:** logikanya udah lengkap, tinggal masing-masing promo **dites beneran satu-satu** biar yakin 100% aman sebelum dinyalain penuh. Kita sengaja pelan-pelan (1 toko dulu, 1 promo dulu) supaya kalau ada yang meleset, dampaknya kecil & gampang dibalikin.

---

## 8. Yang aman kamu tau

- **Robot ga akan ngubah apa-apa tanpa "izin".** Default-nya mode simulasi. Yang beneran dinyalain baru Paket, di 1 toko (Kimmioshop).
- **Bagian paket yang udah dinyalain (nambah produk ke paket, poin 5) ga nurunin harga jual** — makanya aman buat "kelinci percobaan" pertama. *(Cabut per-produk buat ubah harga awal itu bagian modul harga poin 4 — belum dinyalain.)*
- **Semua bisa dibalikin** — kalau ada yang salah, tinggal dimatiin/hapus.
- **Lo pegang kendali.** Tiap promo baru dinyalain penuh setelah lo liat hasilnya & setuju.

---

## 9. Rencana ke depan (biar lo ada bayangan)

1. Tes beneran **Voucher** (aman, ga ngaruh harga). ← berikutnya
2. Terus **Garansi**.
3. Baru yang ngubah harga: **Promo Toko, Campaign, Flash**.
4. Perbaiki bagian **cabut Flash** (endpoint rusak).
5. Kalau ke-7 promo udah lulus tes → nyalain buat **semua 10 toko**.
6. Bikin **Fase 3 (laporan)** biar lo bisa liat robot tiap hari ngapain aja.

---

## 📌 10. SPEC ASLI DARI OWNER (jangan diringkas/diubah)

> Ini penjelasan LANGSUNG dari owner, disimpen apa adanya biar sesi baru langsung paham intent-nya (ga usah dijelasin ulang panjang lebar). **Kalau ada beda sama kode/panduan, ini yang menang.**

**Fase 2 — di tab olah data:**
1. Target kosong? → skip ("tanpa target")
2. Harga Real == Target → skip ("sudah sesuai")
3. Harga Real != Target dan Target < Harga Awal:
   - **Komisi:** Cek apakah ada komisi aktif di halaman komisi. Kalau ada, liat harganya sama atau nggak; kalau nggak, samakan pakai metode di bawah (semua metode promosi). Pokoknya kalau komisi aktif, **Harga target beralih dari target jadi Harga Komisi** — jadi semua promo patokannya harga yang ada di halaman komisi.
   - **Promo toko:** kalau belum ada di promo toko → daftarin ke promo Utama; kalau sudah ada → set HARGA PROMO TOKO = target.
   - **Garansi Harga Terbaik:** kalau garansi Harga Terbaik harganya < target−500 atau kolom margin di olah data < 7% → takedown.
   - **Flash Sale:** harusnya Harga Flash Sale target−10 perak; kalau < target−10 atau stok realnya udah 0 → takedown.
   - **Campaign:** harusnya Harga Campaign target×98,5% (kurangi 1,5%); kalau < target×98,5% atau stok realnya udah < 30, atau stok < penjualan/hari (jangan ambil data penjualan ERP) → takedown.
4. Harga Real != Target dan Target ≥ Harga Awal → **UBAH HARGA DASAR** (keluarin dari SEMUA promo dulu: promo toko, Garansi Harga Terbaik, paket diskon, voucher, flash sale, campaign). Lalu setelah Harga awal dirubah, pasang kembali promo **paket diskon & voucher** karena 2 promo itu harus selalu aktif.

**Poin 1–4 ini deteksi PER JAM.** (Untuk paket & voucher, cabutnya level per-PRODUK — karena untuk rubah harga awal, produk itu harus tetap ditakedown.)

**5. Logik pasang promosi:**
- **Komisi (per hari):** ambil data komisi affiliate — produk & toko mana yg komisinya aktif; lalu ambil data Shopee (semua toko) biar tau mana yg harusnya dikomisikan & harganya udah sesuai/belum, dan mana yg harusnya nggak dikomisikan (kalau aktif → takedown komisi + rubah harga). Kalau ada yg harusnya dikomisikan → set komisi + set harga. Karena kalau komisi aktif, **Harga Komisi jadi patokan untuk semuanya (bukan Harga target lagi)**.
- **Promo toko (per jam):** buat baru/duplikat, masukin produk yg belum ada promo toko (Target < Harga Awal).
- **Garansi Harga Terbaik (per hari):** daftarkan kalau harga garansi terbaik nggak lebih < target−500 atau margin < 7% (kalau kondisinya buruk, jangan dipasang). 3 kondisi: belum didaftarkan · dinominasikan (terbaik) · dinominasikan tapi masuk "perlu ditinjau" (ini biasanya ga ditampilin) → **yg kaya gini batalkan aja**. (detail nyusul)
- **Paket diskon (per hari, ga pengaruh harga/stok):** cek udah ada paket diskon apa belum; belum → buat baru + daftarkan semua produk. Kalau udah ada → cek semua produk udah masuk apa belum; kalau belum → masukin.
- **Voucher (per hari, ga pengaruh harga/stok):** sama kaya paket diskon — cek ada/belum; belum → buat; produk belum masuk → masukin.
- **Campaign (per minggu):** pas trigger dipanggil, lihat campaign apa aja yg bisa didaftarkan; daftarkan dengan Harga Campaign maks potongan target×98,5% (kurangi 1,5% — karena ada campaign yg cukup potongan 0,1%), stok > 50, stok > 10×penjualan/hari.
- **Flash sale (per minggu):** ambil semua sesi flash sale s/d minggu depan (sampai trigger manggil lagi); daftarkan produk (maks 50), kalau bisa per kategori dengan penjualan tertinggi; harga turunkan 10 perak dari harga real/kini; stok > 50 atau > 10×penjualan/hari.

**Catatan waktu:** deteksi waktu diatur **PER-MODUL** (bukan per-fase). Fase 1 harus sejalan sama ini.
**Catatan komisi:** set/takedown komisi jadinya **MANUAL**.

---

## 📎 11. CATATAN TEKNIS (buat dev / sesi baru)

### ▶️ HANDOFF — BACA INI DULU (update 13 Jul)

**POSISI SEKARANG:** Fase 1 (grab) udah jalan di **SEMUA 10 toko** (kebukti, 0 anti-bot). **Orkestrasi = `siklus_terpadu`** (13 Jul, permintaan owner): scheduler & `tes` jalanin SATU loop toko — **1 ambil sesi per toko buat SEMUA fase** (dulu 3× buka browser: fase1/harga/provisioning sendiri-sendiri). Fase ikut `FASE_AKTIF`, fase 2 pake data grab barusan (ga grab ulang). Command manual (`grab`/`fase2`/`provisioning`) tetap ada. **Paket & Voucher ✅ verified live.** Owner lagi tes mandiri via `tes_harga.bat`.

**✅ VOUCHER BERES 13 Jul (spec owner per-BAND + CAP 2×AOV, live kimmioshop):**
- **KPI owner:** voucher **PRODUK per BAND harga** — band 1–14.999 lalu per 20rb (grid FIX), **min belanja = batas atas band + 1** (maksa ≥2 pcs). **CAP 2×AOV (koreksi owner):** band yg min-nya > 2×AOV×0.97 (`V.min_price_toko`) DIBUANG → produk mahal TANPA voucher (aturan Shopee: min order ≤ 2×AOV — tercatat dari awal di kode, sempet salah di-drop). Harga berubah → item **pindah band otomatis** (reconcile items tiap run). Jelang-expire = buat baru (konsisten paket; `perpanjang_voucher` dihapus).
- **Grid FIX alasannya:** min belanja voucher BERJALAN ga bisa diedit (`ERROR_VOUCHER_NO_EDIT_PERMISSION`) — grid fix + cap bikin min ga pernah geser.
- Temuan API (probe berjenjang, kimmioshop):
  - **Kode WAJIB prefix toko** (4 char, mis. `KIMM`) + maks 5 custom. Bot: `PREFIX+U+band+doy` (+1 char kalau nabrak — kode ga boleh dobel `1400101001`, termasuk kode voucher yg udah berakhir). Prefix via `V.prefix_kode_toko`. Tanpa prefix → `201600001 ERROR_PARAM` (invalid_data `streamer_ids` = red herring).
  - **`value` & `max_value` WAJIB angka 0** (kaya UI), jangan None.
  - **PUT voucher/ WAJIB body bentuk CREATE bersih** (`V._body_edit`) — kirim respon GET apa adanya = ERROR_PARAM. Voucher BERJALAN: **edit items BOLEH** ✅ (propagasi ~10 dtk) · edit min_price/akhiri **DITOLAK** → akhiri = MANUAL di Seller Center (bot cuma warning).
  - **VERIFIKASI HIDUP = `fe_status`** (GET detail): 1=akan datang · 2=BERLANGSUNG · 3=berakhir. ⚠️ create code=0 BELUM berarti jalan — cek fe_status=2 setelah lewat start. (Voucher API min 90rb > 2×AOV sempet TEMBUS & fe_status=2 → aturan 2×AOV kayanya validasi UI; tapi keputusan owner tetep cap, aman dari sisi tampilan pembeli.)
  - Tipe welcome (`ikuti_toko`/`pembeli_baru`, usecase 3) = maks 1 aktif/toko (`1400101033`) — jangan dipakai upsell. Deteksi punya-bot via **NAMA** prefix `UPSELL`.
- Voucher percobaan skema lama udah **dimatiin manual owner** (13 Jul). Voucher tes `ZTES A/B` expire sendiri 14 Jul.
- ⚠️ `config.py` skrg `MODE_LIVE=True` + `TOKO_AKTIF=[]` (semua toko) — **jangan jalanin provisioning tanpa scope dulu!**

**✅ PERUBAHAN 12–13 Jul (UDAH di-commit + push):**
- **Paket:** jelang-expire → buat-baru (`perpanjang_deal` dihapus); `KPI_PAKET_MAKS_ITEM=100000` (cap dilepas — batas item/paket ga ada di API Shopee). Dashboard: paket bisa diklik. Grab: buang deal berakhir.
- **Garansi:** grab fix — floor/ceiling dari `bidding_info` per-model (Harga Terbaik/Program asli). Udah re-grab semua toko.
- **Config refactor (13 Jul):** `config.py` jadi CONTROL PANEL — `FASE_AKTIF` (arsitektur 3-fase, skrg [1]) · `TOKO_AKTIF` · `MODUL_AKTIF` (nyala/matiin modul) · trigger jam. Trigger **bulanan DIHAPUS** (housekeeping → mingguan). Legacy Sheet block dibersihin (cuma `KOL` disisain, dipake `update_harga`). `RUN.bat` echo dibetulin. Scheduler honor `FASE_AKTIF`+`MODUL_AKTIF`. KPI dicek — udah sesuai.
- **⏳ Belum dikerjain (nunggu owner):** konsolidasi paket → owner **hapus manual** paket non-UPSELL tiap toko, baru jalanin `provisioning paket` (bot isi sisanya ke 1 UPSELL).

**▶️ RENCANA BESAR (grilling 13–14 Jul) — 7 MILESTONE, aman→berisiko.**
Spec lengkap 29 keputusan (3 fase · 7 modul · log · config) di plan detail (sesi 14 Jul).
Ringkas per-milestone:
- **M−1 Rekonsiliasi** ✅ (14 Jul) — checkpoint kode bersih. Artifact tes `DIAGV*` di YARRA self-expire.
- **M0 Fondasi** ✅ (14 Jul) — config 3-blok + KPI rem · **log CMD terpusat** `log()` (baris seragam `[jam] [Fase·Toko·Modul] pesan`, warna=arti) + `catat()` (NOTABLE event → CMD + 1 baris `siklus_log`, detail kaya di kolom `detail` jsonb = ADDITIF, ga rombak tabel bersama) · jalur siklus kejahit: `update_harga`/`provisioning`/`fase2_harga` (ringkasan per toko+modul) + `run.py` banner/per-toko + `_aman` · **dashboard `/log`** seksi "⚡ Aktivitas Monitoring Harga" tabel event filterable (toko/modul/status, terbaru atas) · prune `siklus_log` harga >30hr di housekeeping mingguan · **polish TUNTAS**: SEMUA modul low-level (`voucher`/`paket_diskon`/`garansi`/`duplikat_promo`/`discount_util`/`fakta`/`campaign`/`campaign_util`/`flash_sale`/`flash_sale_daftar`/`takedown_campaign`/`api_util`/`grab_produk`/`komisi_api`/`session`) sekarang lewat `log()` — CMD 100% seragam warna=arti. (Fungsi sniff/inspect/komisi-grab manual di `run.py` sengaja dibiarin — tool investigasi ber-`input()`, bukan jalur siklus.)
- **M1 Fase 1 lengkap** 🔧 BERIKUTNYA — Garansi 2-kolom (Terbaik+Program dari `bidding_info`) · Voucher `fe_status` · `_buang_berakhir` semua modul · **produk stok-habis→stok=0** (akar masalah voucher!) · auto-isi harga diskon jalan di Fase 1 & 3.
- **M2 Loop A→B + Fase 3 + alasan** ⏳ — siklus jadi Loop A(fase1+2)→Loop B(fase3, ulang kimmio→beverra) · grab-ulang fase 3 · **tulis `alasan` ke DB** (1 baris/produk gabung, buat laporan).
- **M3 Poin 1–4 harga + REM** ⏳🔴 — rem 30%/40% · komisi peg (+trigger Shopee-aktif) · garansi takedown jam (sumber 2-kolom) · poin 4 re-attach→serahin provisioning harian. PALING RISIKO (harga live).
- **M4 Poin 5 provisioning** ⏳ — verif live per modul: garansi · **voucher (verif poison KELAR abis stok-fix M1)** · paket (fix `baca_item_deal` over-count) · campaign · flash (**sniff endpoint akhiri-SESI** — cabut = akhiri sesi, bukan per-item).
- **M5 Open problems** ⏳🔴 — 3 toko flaky (Topikece/ZIO/BEVERRA: deal numpuk 30-70, list non-deterministik → cleanup + rem anti-dobel) · voucher bisect-on-failure (kalau M4 nunjukin poison non-stok-0) · voucher lama ga bisa diakhirin via API.

**Keputusan kunci grilling** (biar ga nanya ulang):
- Fase 3 = grab-ulang semua modul abis Fase 2 (Loop B, jeda propagasi dari lamanya loop). Status TERKINI + alasan (bukan histori).
- Garansi: margin dicek per-TABEL (Program utk rekomendasi/terbaik · Terbaik utk perlu-ditinjau); bid re-submit @Terbaik; HPP kosong = biarin (jangan takedown); stok-0 sendiri bukan alasan takedown.
- Voucher poison = item STOK-0 (Shopee tolak seluruh voucher). Fix = stok-habis→0 (M1) + filter. Verif ulang M4.
- Komisi: peg harga kalau aktif Syntra ATAU Shopee. Harga Komisi ≥ Harga Diskon (rem ga salah-trigger).
- Flash cabut = akhiri SESI (50/sesi, collateral diterima). Campaign pasang jalan, verif cabut live.
- Log: tabel event filterable, catet NOTABLE + heartbeat/siklus. CMD = progress+perubahan (model iklan). 1 fungsi `catat()` buat CMD+dashboard.

⚠️ `config.py` skrg `MODE_LIVE=True` + `TOKO_AKTIF=[]` — jangan jalanin tanpa scope!

**CARA JALANIN:**
- Scheduler 24 jam: `python run.py` / double-klik `RUN.bat` (jalan tiap jam di menit `MENIT_RUNNING`).
- **Tes 1 siklus SEKARANG: double-klik `tes_harga.bat`** (`JAM_TES=FULL` = semua tier dipaksa, ga nunggu jadwal · atau `JAM_TES=<jam>` samain sama `JAM_FAKTA_HARIAN` buat simulasi). Setara `python run.py tes [full|jam] [hari]`.
- Command manual tetep ada: `grab`/`grab full` (fase 1 doang) · `fase2` (harga) · `provisioning [modul]`.
- Scope: `config.TOKO_AKTIF` (`[]`=semua 10, `["kimmioshop"]`=1 toko) · `FASE_AKTIF` ([1]=grab · [2]=aksi · [1,2]=dua-duanya) · `MODE_LIVE` (live/DRY).

**ATURAN KERJA (dari owner — WAJIB):**
- **STATUS.md = BENANG MERAH**, spec DIKUNCI. Tiap ada perubahan: update **penanda progres di STATUS** + **detail di PANDUAN ini** (dua-duanya).
- **Jangan HALU** — verifikasi dari kode/probe dulu sebelum ngomong. **Jangan bikin file .md baru.** Komunikasi ke owner **ringkas** (dia gampang overwhelmed).
- Web/dashboard → auto commit+push ke `main` (Vercel). Bot Python → commit **pas owner minta**.

### Cara kerja modul (Fase 2)
- **PAKET (per hari):** semua produk toko − yg udah di paket manapun = "belum masuk" → enroll ke 1 paket "UPSELL" (tier 2→1%/3→2%/7→3%). Belum ada → buat; jelang-expire → buat-baru. Idempotent (nama prefix "UPSELL"). Konsolidasi 1 paket = owner hapus paket lain manual.
- **VOUCHER (per hari, ✅ live 13 Jul):** harga acuan per ITEM = MAX target antar model (`harga_akhir`, fallback `harga_real`) → bagi ke BAND grid fix (`bands_harga`: 1–14.999 lalu per 20rb), **buang band yg min-nya > cap 2×AOV** (`min_price_toko`; produk mahal tanpa voucher). Per band: voucher **PRODUK** nama `UPSELL <toko> B<low>` (idempotent via nama), min belanja = **batas atas band + 1**, diskon 2%, durasi `KPI_VOUCHER_DURASI_HARI` (90). Reuse → **reconcile items** (item pindah band ikut harga; propagasi ~10 dtk). Jelang-expire → buat baru nyambung. Ga match band → coba akhiri (voucher jalan pasti gagal → warning akhiri manual). Kode = `PREFIX_TOKO+U+band+doy` (mis. KIMMU05E). AOV kosong → skip + warning.

---

**Keputusan penting:**
- **Komisi set/takedown = MANUAL (final).** Write komisi via API mustahil (anti-bot `x-sap-sec` SDK-generated; requests/XHR/fetch/apollo semua 403; DOM-click fragile). Bot cuma nuntun via dashboard #9. Rubah harga produk komisi tetap OTOMATIS (Anchor A: komisi aktif `harga_komisi_toko.harga_jual>0` → target=harga_jual). Komisi READ bisa via browser-listen (`komisi_grab`).
- **Paket (beres 11 Jul):** `list_deals` wajib param `offset`/`limit`/`time_status` (dulu GET polos → balik 0). Item membership via `GET bundle_deal/item/`. `provisioning.paket` rework: belum-masuk = semua produk − union item semua deal → enroll UPSELL (reuse/buat/overflow). `max_active_count=1000` paket aktif. Tool: `sniff_paket.py`. Verified live Kimmioshop.
- **Fix dashboard (12 Jul):**
  - **GARANSI nominasi** — floor/ceiling ambil dari **`bidding_info.floor_price/ceiling_price` per-MODEL** (= Harga Terbaik Saya / Harga Program Saya asli; verified probe CREAM Alialia: 11.469 / 12.059). Dulu salah ambil `item_floor/ceiling_price` (rentang IZIN per-item, mis. 5.9rb). Fix di `garansi.list_ongoing_status`.
  - **PAKET grab** buang deal BERAKHIR via `end_time` (`_buang_berakhir`) — Shopee kadang tetap balikin deal ended walau filter time_status.
  - **PAKET tab dashboard** bisa diklik → detail produk di dalam paket (`paket_produk` API + entri `DETAIL_CFG` di page.tsx, pola sama voucher).
  - ⚠️ garansi & paket perlu **RE-GRAB** biar data lama (salah) di DB kebenerin.
- **Keputusan Paket (12 Jul):**
  - **Konsolidasi ke 1 paket** — bot cuma kelola 1 paket "UPSELL", enroll produk yg belum masuk paket manapun. Paket diskon LAIN (non-UPSELL) → **owner hapus manual** (Shopee: 1 produk cuma 1 bundle deal; abis dihapus, produknya otomatis ke-enroll ke UPSELL next run). Bot GA auto-hapus paket owner (aman).
  - **Jelang-expire = BUAT BARU** (bukan perpanjang; fungsi `perpanjang_deal` dihapus).
  - **Batas item/paket = GA ADA di API Shopee** (cek 12 Jul: detail cuma `usage_limit`+tier, ga ada max-item; `max_active_count=1000` itu batas jumlah DEAL bukan item). Paket #5 lama muat 227 produk lancar. → `KPI_PAKET_MAKS_ITEM=100000` (efektif 1 paket, ga overflow). Kalau nanti attach gagal massal (deal penuh) → baru ketauan angka asli, turunin.

**Kode error / anti-bot:**
- `1400101531` = item udah di bundle deal lain (Shopee: 1 produk cuma 1 bundle deal).
- `90309999` (HTTP 403) = anti-bot, kena kalau sesi browser dibuka kekencengan beruntun. bundle_deal TIDAK kena.

**Backlog / PR (kerjain pas relevan):**
- [Flash] endpoint takedown per-item RUSAK (`set_shop_flash_sale_items` ditolak 1001 → `SKIP_FLASH_TAKEDOWN=True`). Re-sniff endpoint remove-item.
- [Flash/Campaign] verifikasi LIVE takedown belum kebukti (0 sesi/nominasi pas dites).
- [Campaign] withdraw pas nominasi udah tutup belum diuji.
- ✅ [Voucher] edit item voucher aktif VERIFIED 13 Jul (`PUT voucher/` body bentuk create, propagasi ~10 dtk).
- [Voucher] durasi >90 hari belum dites (skrg `KPI_VOUCHER_DURASI_HARI=90`, verified).
- [Voucher] AKHIRI voucher berjalan via API ga bisa (PUT end_time & min_price ditolak) — re-sniff endpoint "Akhiri" UI kalau nanti kepake sering (skrg cukup manual, kasusnya jarang).
- [Paket] endpoint perpanjang deal belum di-sniff (skrg fallback buat-baru); konfirmasi cap item/paket (guess 1000).
- ⏸️ **[Paket] ZIOSCARF & BEVERRA** — `bundle_deal/list/` sering balik `1400101507 database unavailable` (flaky/mostly-down di sisi SHOPEE, khusus 2 akun ini). **Request kita udah BENAR** (probe sempet tembus code=0; param/session identik toko lain, bukan port/browser/bug). Retry 7x beruntun gagal. **Keputusan (12 Jul): HOLD** — serahin ke grab harian (auto-retry), jangan dipaksa. 8 toko lain paket-nya OK.
- [Komisi] peta SKU→item_id lengkap (SKU stok-0 hilang).
- [Dashboard] DETAIL_CFG campaign (paket ✅ udah). [Kategori] isi awal (user jalanin).
- ✅ "Fase 1 harus sejalan" BERES (12 Jul) — semua promo grab harian/per-jam; stok dari grab produk per-jam.

**Config = CONTROL PANEL (`config.py`) — jalanin: double-klik `RUN.bat`:**
- `MODE_LIVE` = **SATU saklar** (True=SEMUA modul live · False=SEMUA DRY simulasi). `DRY_RUN` turunan otomatis.
- `FASE_AKTIF` — fase yg dijalanin scheduler (1=Fakta · 2=aksi harga+provisioning · 3=laporan belum). Orkestrasi = **`siklus_terpadu`** (1 loop toko, 1 sesi per toko, semua fase); set `[1,2]` buat nyalain Fase 2. ⚠️ Fase 2 aktif = harga poin 1–4 ikut jalan (GA ke-gate `MODUL_AKTIF`).
- `TOKO_AKTIF` (`[]`=semua 10 · `["kimmioshop"]`=1 toko) · `MODUL_AKTIF` (list modul yg di-grab & diproses; buang = skip).
- Trigger: `MENIT_RUNNING` · `JAM_FAKTA_HARIAN` · `HARI_FAKTA_MINGGUAN`+`JAM_FAKTA_MINGGUAN`. (bulanan DIHAPUS.)
- **🔴 `MODE_LIVE` = SATU saklar live/DRY** — True: SEMUA modul (harga + provisioning) beneran ke Shopee; False: semua simulasi. Rem paksa-DRY & env `PROV_LIVE` **udah dihapus** (13 Jul). ⚠️ Modul selain paket belum diverifikasi live — pas nyalain, scope `TOKO_AKTIF`/`MODUL_AKTIF` dulu. Command manual tetap ada. `SKIP_FLASH_TAKEDOWN=True`.

**Commands:** `run.py` (scheduler) · `tes [jam|full] [hari]` (**tes_harga.bat** — 1 siklus SEKARANG, fase+modul ikut config. `tes full` = SEMUA tier dipaksa (paling gampang); `tes <jam> [hari]` = simulasi via `jam_siklus.set_simulasi`, tier harian/mingguan kena cuma kalau jam-nya SAMA dgn `JAM_FAKTA_*`) · `grab`/`grab full` · `kategori` · `fase2` · `provisioning [modul]` · `komisi_grab` · `*_sniff`.
⚠️ Poin 1–4 harga di Fase 2 **GA ke-gate MODUL_AKTIF** (selalu jalan kalau fase 2 aktif) — mau tes provisioning doang tanpa harga? pakai `provisioning [modul]`, jangan nyalain fase 2.
**KPI:** semua ambang di `config.py` blok "KPI PER-MODUL" (`KPI_*`), modul BACA dari sana (jangan hardcode).

---

📌 *Spec resmi + progres = `STATUS.md`. File ini = penjelasan + intent owner + catatan teknis.*
*Ada yang ga sesuai sama mau lo? Bilang aja, kita betulin.*
