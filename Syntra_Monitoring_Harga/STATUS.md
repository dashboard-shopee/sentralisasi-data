# STATUS — Syntra Monitoring Harga (acuan tunggal progres)

> **Baca file ini dulu tiap mulai kerja.** Legenda: ✅ selesai · 🔧 lagi dikerjain · ⏳ belum · ⏸️ ditunda/PR.
> Arsitektur **3 fase**: 1=Fakta · 2=Masalah+Solusi · 3=Laporan. **Cadence per-MODUL** (bukan per-fase).
> Spec detail: `RENCANA_FASE1.md`, `RENCANA_FASE2.md`. Update terakhir: **10 Jul 2026**.

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

**Pilihan lanjut:**
1. **Provisioning (poin 5)** — daftar produk: paket diskon / voucher (harian) dulu (gak butuh
   data existing), lalu garansi/campaign/flash. Modul upsell udah ADA (`paket_diskon.py`/
   `voucher.py`/`campaign.py`/`garansi.py`/`flash_sale.py`), tinggal dijahit ke orkestrasi.
2. **Verifikasi live 3c/3d** — pas ada sesi flash/campaign aktif + benerin endpoint flash set-item
   (balikin `SKIP_FLASH_TAKEDOWN=False`), + PR: takedown campaign yg nominasi udah tutup (skrg
   pakai `window="sesi"`, tapi belum diuji apakah opt_out valid saat nominasi closed).

**PENTING sebelum ngoding:** ⚠️ Fase 2 WAJIB di data grab FRESH (jangan DB basi). ⚠️ `config.MODE_LIVE=True` (DRY_RUN=False=LIVE) → tes SELALU paksa `config.DRY_RUN=True`. Kolom margin garansi (display) udah dikerjain USER — API+render ada.

**Commands:** `run.py` (scheduler Fase 1) · `grab`/`grab full` (Fase 1 1x) · `kategori` (isi kategori) · `fase2` (Fase 2 Harga DRY) · `rubah`/`verifikasi`/`fase4` (legacy).

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
| Komisi = baca `harga_komisi_toko` (bukan grab, anti-bot) | ✅ |
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
| **5** | **Promo Toko master-detail** (berjalan+akan datang → klik→produk) | ✅ (grab harian + dashboard) |
| 6 | Paket Diskon master-detail + KPI (aktif+akan datang → klik→produk) | ⏳ |
| 7 | Campaign rework (running+upcoming → klik→produk; cek nominasi=0) | ⏳ |

> Detail-mechanism dashboard digeneralisasi (`DETAIL_CFG` di page.tsx) — dukung voucher + promo_toko; tinggal daftarin utk paket/campaign nanti.
> ⚠️ **Garansi margin display (WIP user):** page.tsx tab Garansi udah ada 3 kolom margin (marginCurrent/Best/Program, `f:"margin"`) TAPI API `pusat-promosi` belum return field margin + `fmt` belum handle "margin" → nyambung ke item "margin@best" (hitung margin@harga-promo). Perlu dituntasin bareng modul garansi.

> Pattern master-detail udah ADA & reusable (dibangun utk Voucher): `DETAIL_TABS`+`toggleRow`+expand-row di `web/.../pusat-promosi/page.tsx`, API `tab=<x>_produk`.

---

## FASE 2 — MASALAH + SOLUSI
### Modul HARGA (poin 1–4, per-jam)
| Bagian | Status |
|---|---|
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
| Promo Toko (buat/duplikat + daftar produk baru) | jam | ✅ (bagian eksekusi 3a) |
| Garansi (daftar, kondisi best/margin, batalkan "perlu ditinjau") | harian | ⏳ |
| Paket Diskon (buat/enroll semua) | harian | ⏳ (buat+enroll-semua blm; helper item-level `PD.keluarkan_item`/`masukkan_item` udah ada, dipakai kasus 4) |
| Voucher (buat/enroll semua) | harian | ⏳ (buat+enroll-semua blm; helper `V.keluarkan_item`/`masukkan_item` udah ada, dipakai kasus 4) |
| Campaign (daftar, harga≤target*98.5%, stok>50 & >10×penjualan/hari) | mingguan | ⏳ |
| Flash Sale (maks 50/sesi, per kategori×penjualan, harga real-10) | mingguan | ⏳ |

### Wiring
| Item | Status |
|---|---|
| Command `python run.py fase2` (grab→diagnosa→eksekusi promo toko+harga dasar+takedown flash/campaign, DRY-RUN paksa) | ✅ |
| Masuk SCHEDULER otomatis (per-jam) | ⏳ (nunggu verifikasi live — poin 1–4 udah lengkap DRY) |

---

## FASE 3 — LAPORAN
| Item | Status |
|---|---|
| Verdict + audit hasil aksi ke dashboard | ⏳ (belum mulai) |

---

## ⏸️ PR / PEKERJAAN RUMAH (jangan lupa — bahas &/atau koding)
- 🗣️⭐ **KOMISI — integrasi ke skema FASE 1 & FASE 2** (bahas detail dulu bareng, BARU koding). **Kondisi skrg:** komisi cuma DIBACA dari `harga_komisi_toko` (proteksi harga: skip item komisi); `komisi_api.py` (baca/set/takedown/baca_aktif, endpoint verified) ada tapi jadi TOOL MANUAL; komisi di `config.SUMBER_SKIP_PR` → Fase 2 belum nyentuh. Cuma **YARRA** aktif skrg. **Yang perlu diputusin:** (a) Fase 1 komisi di-grab jadi FAKTA (`harga_fakta_komisi`) + dashboard, atau tetap dashboard-input? (b) Fase 2 komisi diapain — provisioning set-rate / takedown / audit? cadence? (c) aturan rate per toko (target & sumbernya) (d) komisi ngefek ke margin/keputusan takedown harga atau enggak?
- 🗣️ **Arah lanjut Fase 2** (abis poin 1–4 DRY lengkap): mulai **provisioning** (paket/voucher dulu) ATAU **verifikasi live 3c/3d** dulu?
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
- ⏳ Kategori isi awal (user jalanin) · realign cadence voucher/paket → harian (pas jahit Fase 2)
- 🗣️ **Komisi jadi fakta?** (PR: bahas dulu)

**FASE 2 — MASALAH + SOLUSI** (deteksi per-jam + eksekusi)  ◀ **KITA DI SINI**
1. ✅ **Harga poin 1–4 (DRY)** — 3a promo toko, 4 harga dasar (+paket/voucher takedown+re-add), 3b garansi, 3c flash, 3d campaign. **Verifikasi LIVE ⏳** (+ benerin endpoint flash).
2. ⏳ **Garansi provisioning** (daftar, kondisi best/margin, batalin "perlu ditinjau") + tuntasin margin@best display.
3. ⏳ **Paket + Voucher provisioning** (buat + enroll SEMUA produk; helper item-level udah ada).
4. ⏳ **Campaign + Flash provisioning** (daftar per-kategori×penjualan; pemilihan produk).
5. 🗣️ **Komisi Fase 2** (PR: bahas dulu) — provisioning/takedown/audit rate.

**FASE 3 — LAPORAN** (verdict + audit hasil aksi ke dashboard)
- ⏳ Belum mulai (nunggu Fase 2 jalan live).

**JAHIT AKHIR:** semua modul Fase 2 masuk SCHEDULER per-cadence + Fase 3 laporan otomatis.

## KPI terpusat (config.py — blok "KPI PER-MODUL")
Semua ambang bisnis Fase 2 (pasang & takedown) SATU sumber di `config.py` (prefix `KPI_*`).
Modul BACA dari sana (jangan hardcode). Takedown harga: `KPI_GARANSI_SELISIH/MARGIN_MIN`,
`KPI_FLASH_SELISIH`, `KPI_CAMPAIGN_FAKTOR/STOK_MIN`. Pasang: `KPI_PAKET_TIER/USAGE_LIMIT`,
`KPI_VOUCHER_*` (diskon/min_price faktor+buffer/band), `KPI_FLASH_*` (maks produk/stok/potong/slot),
`KPI_CAMPAIGN_PASANG_*`. Yg pasang campaign/flash blm diwiring (provisioning ⏳) tapi KPI-nya udah siap.
