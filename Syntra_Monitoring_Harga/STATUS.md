# STATUS — Syntra Monitoring Harga (acuan tunggal progres)

> **Baca file ini dulu tiap mulai kerja.** Legenda: ✅ selesai · 🔧 lagi dikerjain · ⏳ belum · ⏸️ ditunda/PR.
> Arsitektur **3 fase**: 1=Fakta · 2=Masalah+Solusi · 3=Laporan. **Cadence per-MODUL** (bukan per-fase).
> 📌 **FILE INI = SATU-SATUNYA DOKUMENTASI** (mulai 10 Jul) — semua progres + spec + rencana di sini.
> `RENCANA_FASE1/2.md` & `HANDOFF.md` = arsip lama (jangan diandelin lagi). Update terakhir: **10 Jul 2026**.

## ▶️ MULAI DARI SINI (next session)
Lagi di tengah **Fase 2 modul HARGA**. Yang UDAH jadi (DRY-RUN): diagnosa poin 1–4 + eksekusi
Promo Toko (3a) + Harga Dasar (4) + takedown Garansi logika (3b) + **takedown Flash (3c) + Campaign (3d)**
+ margin garansi. **POIN 1–4 LENGKAP (DRY).** Bisa dites:
**`python run.py fase2`** (grab fresh→diagnosa→eksekusi, DRY-RUN dipaksa, 0 perubahan nyata).

**3c/3d baru dikerjain (10 Jul):** `eksekusi_takedown_flash`/`eksekusi_takedown_campaign` di
`fase2_harga.py` + wiring `run.py`. Flash: `flash_sale.takedown_items` (resolve flash_sale_id
on-demand). Campaign: GANTI `takedown_campaign` lama (browser) → `campaign.takedown` (requests+
nomination_id); resolve on-demand `open_sessions(window="sesi")`→`get_nominated`→cocokin (item,model).
⚠️ **UNTESTED live** (skrg flash 0 sesi, campaign 0 nominasi) + `SKIP_FLASH_TAKEDOWN=True`
(endpoint set-item flash ditolak code 1001 → flash takedown ke-skip di modul; PR flash).

**Kasus 4 dilengkapin (10 Jul):** harga dasar sekarang takedown+re-add **Paket Diskon & Voucher**
juga (harga awal tak bisa diubah kalau produk masih di promo apa pun). `eksekusi_harga_dasar`:
garansi withdraw → paket takedown (`PD.keluarkan_item` semua deal) + voucher takedown
(`V.keluarkan_item` per voucher dari `item_scope`) → `edit_harga_dasar` → re-add paket (deal utama)
+ re-add voucher. ⚠️ voucher item-edit + paket deal-membership belum verif live (lihat PR).

**KPI terpusat (10 Jul):** semua ambang pasang & takedown pindah ke `config.py` blok "KPI PER-MODUL"
(prefix `KPI_*`). Modul baca dari config, jangan hardcode.

**RENCANA LENGKAP dikunci (10 Jul):** user kasih spec utuh Fase 1+2+3, direkonsiliasi ke sini
(STATUS = SATU-SATUNYA doc mulai skrg). **Gap terbesar ketemu: KOMISI = PATOKAN HARGA** (poin 3·0).

**KOMISI lagi digarap (10 Jul) — lihat section "🔧 MODUL AKTIF: KOMISI":**
- ✅ **Bagian A (Anchor harga) DONE (DRY)** — komisi aktif → target semua promo = harga komisi
  (`harga_komisi_toko` Syntra, no anti-bot). Verified Yarra 47 variasi.
- ❌ **Bagian B & C (Shopee sync)** — READ **&** WRITE dua-duanya **403 KONFIRMASI** (10 Jul). requests
  mustahil → **WAJIB lewat BROWSER** (DrissionPage: buka halaman komisi, baca tabel + set/takedown klik).
  Next: desain modul browser komisi (bahas dulu).

**Pilihan lanjut:**
1. **Komisi** — anchor harga (poin 3·0, per-jam) + grab Shopee + dashboard #9 + provisioning (harian). Arah udah diputusin, tinggal koding. Nyentuh Fase 1 & Fase 2.
2. **Provisioning (poin 5)** — paket diskon / voucher (harian) dulu (gak butuh data existing), lalu garansi/campaign/flash. Modul low-level udah ADA, tinggal dijahit.
3. **Verifikasi live 3c/3d** — pas ada sesi flash/campaign aktif + benerin endpoint flash (`SKIP_FLASH_TAKEDOWN=False`).

**PENTING sebelum ngoding:** ⚠️ Fase 2 WAJIB di data grab FRESH (jangan DB basi). ⚠️ `config.MODE_LIVE=True` (DRY_RUN=False=LIVE) → tes SELALU paksa `config.DRY_RUN=True`. Kolom margin garansi (display) udah dikerjain USER — API+render ada.

**Commands:** `run.py` (scheduler Fase 1) · `grab`/`grab full` (Fase 1 1x) · `kategori` (isi kategori) · `fase2` (Fase 2 Harga DRY) · **`komisi_cek`** (verif READ komisi Shopee, read-only) · `rubah`/`verifikasi`/`fase4` (legacy).

---

## PRINSIP (jangan dilanggar)
- ✅ **Fase 2 WAJIB jalan di data grab FRESH** (grab → diagnosa → eksekusi, sesi & data sama-sama baru). Jangan diagnosa di DB basi (kasus "Tipe 1" 9 Jul).
- ✅ **DRY-RUN default** (`config.DRY_RUN` dari env `HARGA_LIVE`; catatan: `config.MODE_LIVE` skrg =True → live). Tes selalu paksa DRY dulu.
- ✅ **Cadence per-modul** (lihat tabel di `RENCANA_FASE2.md`).

---

## FASE 1 — FAKTA (Pengumpul Fakta)
| Item | Status |
|---|---|
| Core: grab produk+stok+konteks (tier jam) + scheduler 24 jam + jam_siklus | ✅ |
| Tabel fakta: garansi / campaign(sesi+item) / flash(sesi+item) / voucher / paket | ✅ |
| Komisi = baca `harga_komisi_toko` Syntra (proteksi harga: skip item komisi) | ✅ (baca doang) |
| **Komisi GRAB dari Shopee** (semua toko, `komisi_api.baca_komisi_aktif`) + dashboard banding | ⏳ (bagian #9) |
| Kategori Shopee (get_product_info) — modul+tabel+command+tier | ✅ |
| **Kategori: isi awal semua toko** (`python run.py kategori`) | ⏳ (user jalanin) |
| Cadence realign: Voucher & Paket mingguan → **harian** | ⏳ (pas jahit Fase 2) |

### Fase 1 — Backlog perbaikan (9 item, disepakati 8 Jul)
| # | Item | Status |
|---|---|---|
| 1 | Log fix (pemicu grab + fakta_harian/mingguan/bulanan, hapus duplikat) | ✅ |
| 2 | Voucher filter (berjalan+akan datang) + **klik→produk** | ✅ |
| 3 | Garansi 3 harga (Kini/Terbaik/Program) | ✅ |
| 4 | Flash fix (end_time>=now, buang over-fetch Yarra) | ✅ |
| 8 | Urutan tab by cadence | ✅ |
| **5** | **Promo Toko master-detail** (promo-level aktif+akan datang → klik→produk, grab `get_discount_list`) | ✅ (grab harian + dashboard, dikonfirmasi user 10 Jul) |
| 6 | Paket Diskon master-detail + KPI (aktif+akan datang → klik→produk; item per bundle) | ⏳ |
| 7 | Campaign rework (running+upcoming → klik→produk; cek kenapa nominasi 0) | ⏳ |
| **9** | **Komisi tab banding** — master per-ITEM (verdict Syntra vs Shopee) → klik detail SKU. Sumber Shopee = browser grab (bypass anti-bot). | ✅ (dashboard + jadwal harian; verifikasi visual user) |

> Detail-mechanism dashboard digeneralisasi (`DETAIL_CFG` di page.tsx) — dukung voucher + promo_toko; tinggal daftarin utk paket/campaign nanti.
> ⚠️ **Garansi margin display (WIP user):** page.tsx tab Garansi udah ada 3 kolom margin (marginCurrent/Best/Program, `f:"margin"`) TAPI API `pusat-promosi` belum return field margin + `fmt` belum handle "margin" → nyambung ke item "margin@best" (hitung margin@harga-promo). Perlu dituntasin bareng modul garansi.

> Pattern master-detail udah ADA & reusable (dibangun utk Voucher): `DETAIL_TABS`+`toggleRow`+expand-row di `web/.../pusat-promosi/page.tsx`, API `tab=<x>_produk`.

---

## FASE 2 — MASALAH + SOLUSI
### Modul HARGA (poin 1–4, per-jam)
| Bagian | Status |
|---|---|
| **3·0 KOMISI = PATOKAN HARGA** ⭐ — komisi aktif (`harga_jual>0`) → **target := harga_jual** utk SEMUA promo | ✅ **BAGIAN A DONE (DRY, 10 Jul)**. `diagnosa_toko` override target dari `SQL.baca_komisi_patokan` (Syntra SQL, no anti-bot). Verified live-DB: Yarra 47 variasi ke-anchor (harga komisi 32999/10%), Kimmioshop 0. Field baru `komisi_patokan` + `ringkas` hitung `_komisi_anchor`. (Samakan komisi Shopee = bagian C, terpisah.) |
| DETEKSI/diagnosa (kasus tanpa_target/sesuai/koreksi_turun/harga_dasar + cek semua promo) | ✅ (read-only) |
| Guard promo tak-dikenal "Tipe 1" (hold ≥target-500, flag <target-500) | ✅ |
| **3a Eksekusi Promo Toko** (lifecycle buat/duplikat + set/daftar) | ✅ DRY-RUN |
| **4 Harga Dasar** | ✅ core+paket+voucher (DRY). Urutan: garansi withdraw → **paket takedown** (`PD.keluarkan_item` ke semua deal aktif) + **voucher takedown** (`V.keluarkan_item` per voucher dari `item_scope`) → `edit_harga_dasar` (promo toko/flash/campaign→ubah base) → **re-add paket** (deal utama) + **re-add voucher** (voucher sama). ⚠️ voucher item-edit belum verif live (PR). Tes DRY penuh Beverra (7 kasus) belum. |
| 3b Takedown Garansi (best<target-500 / margin@best<7%) | ✅ logika (margin@best wired, sumber FAKTA+bid_id). Modul garansi penuh ⏳ |
| **3c Takedown Flash** (flash<target-10 / stok 0) | ✅ DRY (`eksekusi_takedown_flash`→`flash_sale.takedown_items`). ⚠️ ke-skip live (`SKIP_FLASH_TAKEDOWN=True`, endpoint set-item ditolak 1001, PR flash) |
| **3d Takedown Campaign** (price<target*98.5% / stok<30 / stok<penjualan/hari) | ✅ DRY (`eksekusi_takedown_campaign`→`campaign.takedown` requests+nomination_id, GANTI browser lama). Resolve on-demand `open_sessions(window="sesi")`. Untested live (0 nominasi skrg) |

### Provisioning (poin 5)
| Modul | Cadence | Status |
|---|---|---|
| **Komisi** — set/takedown **MANUAL** (dashboard #9 nuntun; API mustahil) + **rubah harga OTOMATIS** (Anchor A) | harian | ✅ (grab+banding+anchor auto; enroll manual) |
| Promo Toko (buat/duplikat + daftar produk baru) | jam | ✅ (bagian eksekusi 3a) |
| Garansi (daftar, kondisi best/margin, batalkan "perlu ditinjau") | harian | ⏳ |
| Paket Diskon (buat/enroll semua) | harian | ✅ **DRY** (`provisioning.paket` — idempotent `UPSELL <toko>`, buat/reuse + `enroll_semua`. Verified DRY Kimmioshop 221 produk, tier 2→1/3→2/7→3%). Untested LIVE. |
| Voucher (buat/enroll semua) | harian | ✅ **DRY** (`provisioning.voucher` — idempotent kode `UP*`, ikuti_toko shop-wide, auto-perpanjang H-1 / buat baru. min_price=2×AOV. Verified DRY Kimmioshop). ⚠️ tipe ikuti_toko dulu (voucher PRODUK per-band nyusul); durasi reuse DURASI_PROMO_HARI (180d, verif live). |
| Campaign (daftar, harga≤target*98.5%, stok>50 & >10×penjualan/hari) | mingguan | ⏳ |
| Flash Sale (maks 50/sesi, per kategori×penjualan, harga real-10) | mingguan | ⏳ |

### Wiring
| Item | Status |
|---|---|
| Command `python run.py fase2` (grab→diagnosa→eksekusi promo toko+harga dasar+takedown flash/campaign, DRY-RUN paksa) | ✅ |
| Masuk SCHEDULER otomatis (per-jam) | ⏳ (nunggu verifikasi live — poin 1–4 udah lengkap DRY) |

---

## 🔧 MODUL AKTIF: KOMISI (lagi digarap — bahas per-bagian, ga halu)

### Sumber data (VERIFIED dari kode, 10 Jul)
- **SYNTRA = patokan "harusnya"**: SQL `harga_komisi_toko` (sku, username_toko, harga_saat_ini, komisi_persen, **harga_jual**). **Komisi aktif = `harga_jual > 0`**. Diedit di dashboard SYNTRA. → nentuin produk mana HARUSNYA dikomisikan + harga komisi (=harga_jual) + persen. **NO anti-bot (SQL murni).**
- **SHOPEE = kenyataan "aktual"**: `komisi_api.baca_komisi_aktif`/`baca_komisi_items` (gql) → item yg BENERAN aktif komisi (item_id, commission_id, persen, status).

### ⚠️ KENDALA ANTI-BOT (verified) + ✅ SOLUSI BROWSER-LISTEN (TERBUKTI 10 Jul)
Endpoint `affiliateplatform/gql` WAJIB header `x-sap-sec` dari SDK JS Shopee (cuma ke-generate pas halaman ASLI kebuka).
- **`requests`/session-grab: 403 KONFIRMASI** (`komisi_cek` 10 Jul, err 90309999) — READ **&** WRITE dua-duanya mustahil via requests.
- ✅ **SOLUSI: browser-listen** (`komisi_grab`, TERBUKTI 10 Jul) — buka halaman komisi **`/portal/web-seller-affiliate/open_campaign`**, JS-nya manggil gql ber-SDK sendiri, `page.listen` tangkap **response**-nya (bypass anti-bot, no perlu tanda tangan sendiri). **READ KOMISI SHOPEE ✅ JALAN.**

### Struktur data komisi Shopee (dari `komisi_grab`, VERIFIED)
- Op **`GetOpenCampaignProducts`** → `data.GetOpenCampaignProducts.{itemList, totalCount, cursor, modelsMap}`.
- Item AKTIF: `{itemId, itemName, commissionId, commissionStatus:"CommissionStatusOngoing", commissionRate:10000 (=10%), period...}`. commId `0`/status Unknown = daftar rekomendasi (belum aktif) → di-skip.
- 🔎 **Temuan Yarra: Shopee cuma 6 item komisi AKTIF, Syntra `harga_komisi_toko` 58 SKU** → gap gede (harusnya dikomisikan tapi belum). INI yg #9 mau tampilin.

### Pecahan modul + kelayakan
| Bagian | Sumber | Anti-bot? | Kelayakan |
|---|---|---|---|
| **A. Anchor harga** (poin 3·0): komisi aktif → target = harga komisi (patokan semua promo) | `harga_komisi_toko` (SQL) | TIDAK | ✅ **DONE (DRY, 10 Jul)** — verified Yarra 47 variasi |
| **B. Grab Shopee aktual + dashboard banding** (#9) | browser-listen `komisi_grab` | ✅ bypass | ✅ **READ TERBUKTI** (6 item Yarra) — tinggal simpan ke fakta + dashboard |
| **C. Sync otomatis** (set/takedown komisi ikut Syntra) | browser (navigate+klik) | ✅ bypass | ⏳ pola sama B, nyusul |

### Progres & langkah
- ✅ **A (Anchor) SELESAI (DRY)** — `diagnosa_toko` + `SQL.baca_komisi_patokan` + `config.username_dari_nama`. Verified Yarra 47 variasi.
- ✅ **B (READ Shopee) TERBUKTI via browser** — `run.py komisi_grab` (buka `/portal/web-seller-affiliate/open_campaign` → `page.listen` tangkap `GetOpenCampaignProducts` → parse item aktif). Dump `__komisi_shopee_<toko>.json` + **SIMPAN ke `harga_fakta_komisi`** (snapshot per toko). Verified Yarra 6 item.
- ✅ **BANDING (#9 data-layer)** — `SQL.banding_komisi(nama_toko)` (bot) + SQL identik di dashboard API. Verdict `sesuai`/`belum_dikomisikan`/`harusnya_dicabut`. Verified Yarra: **6 sesuai, 4 belum_dikomisikan, 0 dicabut**. ⚠️ LIMITASI: peta SKU→item_id via olah_data (stok-filtered) → 43/58 SKU ke-map (SKU stok-0 hilang). PR: peta SKU→item lengkap.
- ✅ **DASHBOARD #9 (tab Komisi)** — `web/.../pusat-promosi`: master **per-ITEM** (verdict badge ✅/⚠️/❌ + komisi Syntra% vs Shopee% + jml SKU) → klik **expand → detail SKU variasi** (`komisi_produk`). Grain per-item, verified SQL live + `tsc` clean. Verifikasi visual: user (butuh login).
- ✅ **JADWAL HARIAN** — `grab_komisi_browser(interaktif=False)` masuk scheduler tier HARIAN (abis loop fase1, browser bebas). CLI `komisi_grab` tetap interaktif (jeda manual).
- 🔧 **C (set/takedown) — INVESTIGASI TUNTAS (10 Jul)**. Op WRITE asli (dari sniff `komisi_sniff`):
  - **SET** = `CreateOpenCampaigns` — vars `{items:[{itemId,itemName}], commissionRate:<%×1000>, startNow:true, pageSource:19, campaignChannelSource:1}` → resp `isAllSuccess:true`.
  - **TAKEDOWN** = `RemoveOpenCampaigns` — vars `{commissionIds:[...], campaignPageSource:19, campaignChannelSource:1}` → resp `isAllSuccess:true`. (UI ada modal "Yakin hapus? pembayaran distop 00:00 tgl-X" tapi komisi LANGSUNG kecabut.)
  - Signature header: `x-sap-sec`+`x-sap-ri`+`af-ac-enc-dat` (per-req, SDK-generated) + `af-ac-enc-sz-token` (session-stabil) + `x-sz-sdk-version`.
  - ❌ **API-injeksi MATI — INVESTIGASI TUNTAS (semua dicoba 10 Jul):**
    - `requests` biasa → 403. `sync XHR` via run_js → status 0. `fetch` via run_js → 403 → redirect (window ke-wipe).
    - Apollo client (`komisi_apollo` probe): app ini **VUE** (bukan React/Apollo), `__APOLLO_CLIENT__` **gak ke-expose**. Ada `__sap_hook_fetch`/`__monitor_sap_fetch` → `window.fetch` di-wrap TAPI cuma **monitoring**, bukan signer.
    - Bukti final: kick localStorage OK dalam 1 call (`kicked=PENDING`), tapi `after_kick=null` → tiap fetch-inject bikin halaman **redirect** (unsigned→403). Signing `x-sap-sec` ada di **layer request internal app (axios instance)**, bukan `window.fetch` global → **mustahil direplikasi dari luar**.
  - **DOM-automation dicoba (user pilih ini):** `takedown_komisi_browser` (dry/modal/live). ✅ **Row-matching SOLID** — search-free: ambil teks tiap baris via JS, cocokin nama produk, temuin `<div>'Hapus'` yg bener (verified idx cocok 2 produk). ❌ **Tapi klik→modal→confirm FRAGILE**: klik Hapus inkonsisten micu popup promo ("Telusuri Sekarang") ATAU **halaman ERROR** ("Kembali ke Halaman Utama") — kemungkinan **anti-bot challenge** krn halaman komisi dikunjungi automation belasan kali beruntun. Modal konfirmasi "Yakin Menghapus?" belum ke-capture bersih.
  - ⚖️ **ASSESSMENT JUJUR:** row-matching bisa, tapi finalisasi klik+modal butuh banyak iterasi + tetap fragile (popup promo random, anti-bot challenge, Shopee ubah UI). ROI rendah (Yarra doang, 6 produk, gap 4, jarang berubah).
  - ✅ **TES TERAKHIR (halaman PRODUK, 10 Jul):** set komisi dari halaman Produk (`?productType=ams_commission`) pakai op **`SetOpenCampaigns`** TAPI **tetap `/v3/affiliateplatform/gql` + anti-bot sig lengkap**. Endpoint lain = cuma loading. **KESIMPULAN FINAL: SEMUA jalur set/takedown komisi (affiliate & produk, semua op) mentok di gql anti-bot yg sama. API MUSTAHIL, titik.**
  - ✅ **KEPUTUSAN FINAL (user, 10 Jul):** **set/takedown komisi = MANUAL** (dituntun dashboard #9 verdict; bot GAK nulis komisi — API mustahil, DOM fragile). **RUBAH HARGA produk komisi = OTOMATIS** → udah kepasang via **Anchor A** (`diagnosa_toko`: komisi aktif → target=harga_jual) + eksekusi Fase 2 (`set_harga` promo toko dll). Verified DRY Yarra: 47 produk ke-anchor, **15 di antaranya bot otomatis rubah harga ke harga komisi** (mis. GL-FNF-6 real 28.999→32.999). Tool DOM-auto (`takedown_komisi_browser`) di-arsipin (kalau suatu saat mau). **KOMISI C = SELESAI.**

---

## FASE 3 — LAPORAN
| Item | Status |
|---|---|
| Verdict + audit hasil aksi ke dashboard | ⏳ (belum mulai) |

---

## ⏸️ PR / PEKERJAAN RUMAH (jangan lupa — bahas &/atau koding)
- ✅🗣️ **KOMISI — arah UDAH diputusin (10 Jul), tinggal koding** (spec masuk `RENCANA_FASE2.md`). Ringkas: (1) **Fase 1** grab komisi Shopee semua toko → dashboard tab Komisi **2 tabel banding** (Syntra vs Shopee) [#9]; (2) **Fase 2 per-jam** komisi aktif → **Harga Komisi = patokan** semua promo (poin 3·0); (3) **Fase 2 harian** banding → set/takedown komisi + rubah harga. **Sub-detail masih perlu dibahas pas ngoding:** aturan enroll komisi presisi (produk mana yg "harusnya dikomisikan"), sumber harga komisi Syntra (tabel/kolom mana), handling multi-toko. Cuma **YARRA** aktif skrg.
- 🗣️ **Arah lanjut Fase 2** (abis poin 1–4 DRY lengkap): mulai **provisioning** (paket/voucher dulu) ATAU **verifikasi live 3c/3d** dulu ATAU **Komisi (anchor+dashboard)** dulu?
- ⏸️ **[3c] Endpoint takedown FLASH per-item** — `set_shop_flash_sale_items` ditolak Shopee (code 1001 "spex common error") 100% → `config.SKIP_FLASH_TAKEDOWN=True` bikin `flash_sale.takedown_items` ke-skip total. Kode diagnosa+eksekusi (`eksekusi_takedown_flash`) UDAH siap. **PR: re-sniff endpoint remove-item flash yg benar** (kandidat: `set_shop_flash_sale` level-SESI `{flash_sale_id,time_slot_id,status}`), lalu balikin `SKIP_FLASH_TAKEDOWN=False`. Sampai itu, flash takedown TIDAK jalan walau LIVE.
- ⏸️ **[3c/3d] Verifikasi LIVE takedown flash & campaign** — belum kebukti end-to-end (saat dikerjain 10 Jul: flash 0 sesi, campaign 0 nominasi). Tes ulang pas ada sesi/nominasi aktif.
- ⏸️ **[3d] Campaign takedown saat window NOMINASI udah tutup** — `eksekusi_takedown_campaign` pakai `open_sessions(window="sesi")` (sesi berjalan) buat resolve `nomination_id`. **BELUM diuji** apakah `opt_out` valid kalau nominasi udah closed tapi produk masih jalan. Kalau ditolak → cari endpoint withdraw lain / cache nomination_id pas nominasi masih buka.
- ⏸️ **[kasus 4] Verifikasi LIVE edit item VOUCHER aktif** — `voucher._set_item_voucher` (keluarkan/masukkan item) pakai `PUT voucher/` (jalur sama `perpanjang_voucher`). **BELUM diverifikasi** Shopee ngebolehin edit `rule.items` voucher yg lagi BERJALAN (banyak platform ngunci item voucher aktif). Kalau ditolak → cari endpoint edit-item voucher khusus / stop+buat-ulang voucher.
- ⏸️ **[kasus 4] Paket: deal-id per item tak diketahui** — konteks `ongoing_campaigns` ct=3 `promotion_id` KOSONG (dikonfirmasi sniff), jadi takedown paket = PUT status=2 ke SEMUA deal aktif (no-op kalau item tak di deal itu) + re-add ke **deal utama** (`baca_paket_aktif()[0]`). Konsekuensi: item bisa pindah konsolidasi ke deal utama. **PR: kalau perlu presisi, sniff endpoint "list item dalam 1 bundle_deal"** biar tau deal asal per item.
- ⏸️ **Identifikasi "Tipe 1"** (campaign_type=1) — sniff pas aktif lagi (udah berakhir 8 Jul). Sementara: guard hold/flash.
- ✅ **Margin garansi** — display dashboard (3 kolom, rumus identik) + Fase 2 `_margin`/`baca_biaya_sku` (bot). Temuan: "Harga Terbaik" Shopee sering margin NEGATIF (jual rugi) → takedown bener.
- ⏸️ **Garansi konteks vs fakta 0 overlap** — konteks `campaign_type=11` (86 var Alialia) TIDAK sama dgn fakta `get_ongoing_list` (46 var). Fase 2 pakai FAKTA. **PR: investigasi campaign_type=11 itu apa** + konsistensi.
- ⏸️ **Margin<7% guard promo tak-dikenal (Tipe 1)** — masih pakai best only, margin belum (butuh harga promo Tipe 1).
- ⏸️ **Perpanjang promo toko** — dianggap tak bisa extend (temuan lama) → duplikat. Verifikasi endpoint kalau perlu.
- ⏸️ Garansi "perlu ditinjau" → batalkan (detail pas modul garansi).
- ⏸️ Paket/Voucher aturan enroll detail; Campaign/Flash pemilihan produk per-kategori.
- ⏸️ Kategori isi awal (`run.py kategori`) — user jalanin (get_product_info sensitif anti-bot).

---

## 🧵 PETA JALAN (benang merah pembuatan Syntra Monitoring Harga)
> Urutan besar bikin program. Panah **◀ KITA DI SINI** = posisi sekarang. Tiap langkah nyambung:
> Fase 1 ngumpulin fakta → Fase 2 pakai fakta buat deteksi+aksi → Fase 3 laporin hasil aksi.

**FASE 1 — FAKTA** (pengumpul data, jadi bahan Fase 2)
- ✅ Core grab + scheduler + tabel fakta (garansi/campaign/flash/voucher/paket) + kategori
- ✅ #5 Promo Toko master-detail · **#9 Komisi (banding + grab browser + jadwal harian)** · ⏳ #6 Paket · #7 Campaign
- ⏳ Kategori isi awal (user jalanin) · realign cadence voucher/paket → harian (pas jahit Fase 2)

**FASE 2 — MASALAH + SOLUSI** (deteksi PER-MODUL: per-jam / harian / mingguan)  ◀ **KITA DI SINI**
0. ✅ **KOMISI SELESAI** — harga komisi = PATOKAN (Anchor A, per-jam) → bot **otomatis rubah harga** produk komisi ke harga komisi (verified). Set/takedown komisi = **MANUAL** (dashboard #9 nuntun; API mustahil). Grab Shopee + banding = auto.
1. ✅ **Harga poin 1–4 (DRY)** — 3a promo toko, 4 harga dasar (+paket/voucher takedown+re-add), 3b garansi, 3c flash, 3d campaign. **Verifikasi LIVE ⏳** (+ benerin endpoint flash). ✅ target udah ikut komisi (poin 0 anchor).
2. 🔧 **Provisioning poin 5** (`modules/provisioning.py` + `run.py provisioning`, DRY paksa): ✅ **Paket + Voucher DRY** · ⏳ Campaign · Flash · Garansi. Untested LIVE.
3. ⏳ **Garansi provisioning** (harian) — daftar kondisi best/margin, batalin "perlu ditinjau" + tuntasin margin@best display.
4. ⏳ **Campaign + Flash provisioning** (mingguan) — daftar per-kategori×penjualan; pemilihan produk.

**FASE 3 — LAPORAN** (verdict + audit hasil aksi ke dashboard)
- ⏳ Belum mulai (nunggu Fase 2 jalan live).

**JAHIT AKHIR:** semua modul Fase 2 masuk SCHEDULER per-cadence + Fase 3 laporan otomatis.

## KPI terpusat (config.py — blok "KPI PER-MODUL")
Semua ambang bisnis Fase 2 (pasang & takedown) SATU sumber di `config.py` (prefix `KPI_*`).
Modul BACA dari sana (jangan hardcode). Takedown harga: `KPI_GARANSI_SELISIH/MARGIN_MIN`,
`KPI_FLASH_SELISIH`, `KPI_CAMPAIGN_FAKTOR/STOK_MIN`. Pasang: `KPI_PAKET_TIER/USAGE_LIMIT`,
`KPI_VOUCHER_*` (diskon/min_price faktor+buffer/band), `KPI_FLASH_*` (maks produk/stok/potong/slot),
`KPI_CAMPAIGN_PASANG_*`. Yg pasang campaign/flash blm diwiring (provisioning ⏳) tapi KPI-nya udah siap.
