# RENCANA FASE 2 — MASALAH + SOLUSI (per-modul, per-kasus)

> Arsitektur final **3 fase**: 1=Fakta · **2=Masalah+Solusi** · 3=Laporan.
> **Cadence diatur PER-MODUL, bukan per-fase** → Fase 1 grab ikut di-realign.
> Prinsip: **tiru Fase 2 lama (`update_harga.py`) tapi DIPERLENGKAP.** User mau DETAIL,
> jangan halu. Garap per-modul, jelasin alur sambil ngoding.

**Definisi tetap:** Target = `pancing` kalau ada, else **Harga Diskon** (stored per-SKU).
Real = `harga_tampil` (Fase 1). Margin (olah data) = basis Harga Real.

> ⚠️ **WAJIB — diagnosa/aksi Fase 2 HANYA valid di atas data grab FRESH.** Urutan per-toko:
> **grab (Fase 1) dulu → diagnosa → eksekusi**, pakai sesi & data yg sama-sama baru. JANGAN
> diagnosa di DB basi (contoh nyata 9 Jul: promo "Tipe 1" yg udah berakhir 8 Jul masih
> keliatan di DB basi → 28 variasi salah dicap bermasalah; setelah grab fresh → 0). Promo
> berjadwal yg sudah lewat harus hilang dari konteks fresh dulu.

---

## Cadence per-modul (Fase 1 grab ⟷ Fase 2 aksi selaras)

| Modul | Fase 1 grab | Fase 2 reaktif (harga/takedown) | Fase 2 provisioning |
|---|---|---|---|
| Harga / Promo Toko | jam | **jam** (poin 1–4) | Promo Toko daftar: **jam** |
| Garansi | harian | takedown: **jam** (deteksi dari konteks) | daftar: **harian** |
| Campaign | harian | takedown: **jam** | daftar: **mingguan** |
| Flash Sale | mingguan | takedown: **jam** | daftar: **mingguan** |
| Voucher | **harian** (dari mingguan) | — | daftar: **harian** |
| Paket Diskon | **harian** (dari mingguan) | — | daftar: **harian** |

**Kunci arsitektur:** DETEKSI takedown (jam) baca dari **`harga_promo_konteks`** (di-grab per-jam,
punya harga+status tiap promo per variasi). EKSEKUSI takedown pakai **ID aksi** dari fakta
(bid_id/nomination_id/flash_sale_id, grab harian/mingguan) atau fetch on-demand.

---

## POIN 1–4 — Kontrol harga per variasi (DETEKSI PER-JAM)

| Kasus | Kondisi | Aksi |
|---|---|---|
| 1 | Target kosong | skip "tanpa target" |
| 2 | Real == Target | skip "sudah sesuai" |
| 3 | **Target < Harga Awal** — cek TIAP promo yg variasi ini ikuti: | |
| 3a Promo Toko | belum di promo toko | daftarin ke **Promo Utama** |
| 3a Promo Toko | udah di promo toko | set **Harga Promo Toko = Target** |
| 3b Garansi | best price `< Target−500` **ATAU** margin@best `< 7%` | **takedown garansi** (`seller_withdraw` bid_id) |
| 3c Flash | flash price `< Target−10` **ATAU** stok real `== 0` | **takedown flash** (set status 0) |
| 3d Campaign | campaign price `< Target×0.985` **ATAU** stok real `< 30` **ATAU** stok `<` penjualan/hari | **takedown campaign** (`opt_out` nomination_id) |
| 4 | **Target ≥ Harga Awal** | **UBAH HARGA DASAR**: keluarin dari SEMUA promo (promo toko, garansi, paket, voucher, flash, campaign) → ubah harga awal → **pasang lagi paket diskon + voucher** (2 ini WAJIB selalu aktif) |

**Penjualan/hari** = rata-rata **30 hari** terakhir, **unit terjual**, dari `fact_penjualan`
(Shopee, `produk_id = item_id`, periode harian). BUKAN data ERP.

---

## POIN 5 — Provisioning promo (pasang/daftar)

| Modul | Cadence | Aturan |
|---|---|---|
| Promo Toko | jam | buat/duplikat + masukin produk `Target<HargaAwal` yg belum ada |
| Garansi | harian | pasang **hanya jika** best `≥ Target−500` **DAN** margin@best `≥ 7%`. 3 kondisi: belum-daftar / dinominasi-terbaik / **"perlu ditinjau" → BATALKAN**. (detail nanti) |
| Paket Diskon | harian | belum ada→buat+enroll semua; udah ada→masukin produk yg belum masuk. Tier 2→1%/3→2%/7→3% (handoff §10.2) |
| Voucher | harian | pola sama paket. Band harga per-20rb, min_price=2×AOV (handoff §10.3) |
| Campaign | mingguan | daftar sesi yg buka; harga potongan **maks** `Target×0.985` (boleh 0.1%), stok `>50` **DAN** stok `> 10×`penjualan/hari |
| Flash Sale | mingguan | ambil semua sesi s/d minggu depan; **maks 50 produk**, per kategori × penjualan tertinggi; harga = real/kini `−10`; stok `>50` **ATAU** stok `> 10×`penjualan/hari |

---

## Peta REUSE vs BARU (grounded ke `update_harga.py` lama)

| Bagian | Fase 2 lama | Status utk Fase 2 baru |
|---|---|---|
| Kasus 1/2 (kosong/sesuai) | ✅ ada (`update_harga`) | reuse |
| 3a Promo Toko (set/daftar) | ✅ ada (`peta_promo`, `_entry`, primary) | reuse |
| 4 Harga Dasar (takedown promo→ubah base) | ✅ ada (`edit_harga_dasar`) | reuse + lengkapin (takedown garansi/voucher/paket blm ada) |
| 3d Campaign takedown | ⚠️ ada tapi via browser-context lama (`takedown_campaign`) | GANTI ke `campaign.takedown` (requests, nomination_id) |
| 3c Flash takedown | ⚠️ ada (`flash_sale.takedown_items`) tapi endpoint per-item pernah salah | pakai fakta flash + endpoint yg udah dibenerin |
| 3b Garansi takedown | ❌ lama = SKIP garansi | **BARU** (`garansi.withdraw`, kondisi best/margin) |
| Kondisi per-promo (garansi/flash/campaign paralel) | ❌ lama cuma 1 "sumber" | **BARU** — cek SEMUA promo variasi dari konteks |
| Poin 5 provisioning (semua) | sebagian (`duplikat_promo` promo toko) | modul upsell udah ada (paket/voucher/campaign/garansi/flash) tinggal dijahit |

**Beda utama vs lama:** lama nentuin aksi dari **1 "sumber harga tampil"**; baru **cek SEMUA
promo** yg variasi ikuti (dari `harga_promo_konteks`) + tiap promo punya kondisi takedown sendiri.

---

## Urutan garap (disepakati): mulai **Modul Harga poin 1–4 (per-jam)**
1. **Harga poin 1–4** (klasifikasi + promo toko + harga dasar + takedown garansi/flash/campaign)
2. Garansi provisioning (harian) — + detail margin@best
3. Paket Diskon + Voucher provisioning (harian)
4. Campaign + Flash provisioning (mingguan)

## Item "nanti bahas detail" (jangan lupa)
- Garansi: kondisi "perlu ditinjau" → batalkan; margin@best price presisi (user mau harga PAS)
- Paket/Voucher: aturan enroll detail
- Campaign/Flash: pemilihan produk per-kategori × penjualan tertinggi
