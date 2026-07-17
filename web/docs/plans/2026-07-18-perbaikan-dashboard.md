# Perbaikan Dashboard (spec owner 18 Jul) — Implementation Plan

> **For agentic workers:** kerjain task-by-task urut, commit+push per task (Vercel auto-deploy),
> `npx tsc --noEmit` + `npm run build` wajib lolos sebelum commit. Repo web TIDAK punya test suite —
> verifikasi = build + (kalau bisa) probe API shape. Checkbox buat tracking.

**Goal:** 30-an perbaikan dashboard dari owner (18 Jul): UX tabel (freeze header, warna KPI,
filter/sort), kelengkapan data promo per-produk, standarisasi ekspansi promo (search SKU + kode
produk/variasi + penanda warna katalog), riwayat bersih (no-op ga dicatet), log per-modul bisa drill.

**Keputusan owner (AskUserQuestion 18 Jul):**
- Margin: `<0%` merah · `0–8%` oranye · `8–20%` hijau · `>20%` biru.
- Warna harga toko: dibanding **Harga Diskon induk** — bawah=merah · sama=hitam · atas=biru.
- Harga & margin: **sort per kolom + filter rentang** dua-duanya.
- Log modul: riwayat drill **+ bot nyatet daftar SKU per aksi** (detail JSON `catat()`).

**Konstanta reuse:** `SHOP_ID_BY_NAME` (ServerTable.tsx:243) + pola URL
`https://shopee.co.id/product/<shopId>/<itemId>` (dipakai riset-kompetitor & thumbnail).

## Global Constraints
- Bahasa UI Indonesia santai-profesional; gaya visual ngikutin komponen existing (card, chip, badge).
- JANGAN bikin util/komponen dobel — freeze-header & penanda katalog dibikin SEKALI, dipake semua tabel.
- API route: kolom baru via SQL join ke `harga_olah_data`/`harga_all_produk` (sku induk = `ap.sku`;
  kode produk = `item_id`; kode variasi = `model_id`; SKU variasi = `ho.sku`).
- Riwayat: penulisan riwayat di-skip kalau `nilai_baru == nilai_lama` ATAU input dibatalin —
  cek di CLIENT (jangan fire API) DAN guard di API (defense in depth).
- Commit per task, pesan santai + `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

---

## Task 1 — Freeze header SEMUA tabel (A1a)
**Files:** `web/src/components/ServerTable.tsx` + halaman dgn tabel inline:
`app/produk/harga/page.tsx` (olah data), `app/produk/pusat-promosi/page.tsx`, `app/log/page.tsx`
(tabel kecil kalau ada), halaman komisi/riwayat (cek `app/produk/harga` sub-tab).
- [ ] Ganti wrapper tabel jadi `max-h-[70vh] overflow-auto` + `thead` pakai `sticky top-0 z-10 bg-<warna existing>`.
- [ ] Pastiin bg thead solid (bukan transparan) biar teks ga numpuk pas scroll.
- [ ] Build + commit.

## Task 2 — All Produk: link Shopee, warna margin/harga, filter+sort (A1b-e)
**Files:** `web/src/components/ServerTable.tsx`, `app/api/produk/harga/route.ts`
- [ ] Kolom harga per-toko: render jadi `<a>` ke `https://shopee.co.id/product/<SHOP_ID_BY_NAME[toko]>/<item_id>`
      (butuh item_id per sel — cek payload kolom toko; kalau cuma harga, extend API kirim `{harga, itemId}`).
- [ ] Warna margin 4 level: `<0` `text-[#e11d48]` · `0–8` oranye `text-[#f59e0b]` · `8–20` hijau
      `text-[#047857]` · `>20` biru `text-[#2563eb]`. Terapkan di semua sel margin (All Produk + Garansi dashboard).
- [ ] Warna harga toko vs Harga Diskon induk: `< diskon` merah · `== diskon` default hitam · `> diskon` biru.
- [ ] Sort: klik header kolom harga-diskon/harga-toko/margin → orderBy server-side (route udah support sort? cek `allowed`).
- [ ] Filter rentang: input min/maks utk margin & harga (query param baru di route + UI kecil di toolbar).
- [ ] Build + commit.

## Task 3 — All Produk: update massal info + riwayat bersih (A1f-g)
**Files:** `app/produk/harga/page.tsx` (modal update massal), `app/api/produk/harga/route.ts` (PUT/riwayat)
- [ ] Modal update massal by SKU induk: sesudah SKU diketik, tampilkan **harga net, margin, harga diskon
      sekarang** (fetch 1 baris ringkas) sebelum user submit.
- [ ] Edit harga diskon/pancing: batal (blur tanpa enter / nilai == lama) → JANGAN panggil API, JANGAN
      masuk riwayat. Guard juga di API: `if (baru === lama) skip insert riwayat`.
- [ ] Build + commit.

## Task 4 — Olah data: filter Sumber Harga + detail promo lengkap (A2)
**Files:** `app/produk/harga/page.tsx`, `app/api/produk/harga/route.ts`, `app/api/produk/pusat-promosi/route.ts`
- [ ] Filter Sumber Harga: dedup (muncul 2 → 1), TAMBAH `Campaign` + `Flash Sale`, BUANG `Paket Diskon`.
      (Nilai `sumber_harga` diisi bot dari konteks — cek nilai distinct di DB; kalau campaign/flash belum
      pernah muncul sbg sumber, tetep daftarin di opsi filter.)
- [ ] Klik produk → panel promo nyangkut: lengkapi jadi 8 jenis (Harga Awal, Promo Toko, Garansi,
      Flash Sale, Campaign, Komisi, Paket Diskon, Voucher) — query gabung dari tabel fakta masing2
      (`harga_promo_konteks`, `harga_fakta_garansi`, `harga_fakta_flash_item`+sesi,
      `harga_fakta_campaign_item` (INGAT ÷100000 micro), `harga_komisi_toko`/fakta komisi,
      paket membership, voucher item_scope). Jenis yg kosong ga usah dirender.
- [ ] Build + commit.

## Task 5 — Komisi: standarisasi tombol, riwayat bersih, modal harga (A3)
**Files:** halaman komisi (`app/produk/harga/page.tsx` sub-tab ATAU file terpisah — cari `parent sku`)
- [ ] Tombol "tambah by parent sku" & "hapus": samain gaya dgn All Produk (kelas tombol standar).
- [ ] Input rekomendasi/jual: batal ATAU nilai sama → no API call, no riwayat (client+API guard).
- [ ] Klik kolom jual (edit per SKU induk): tampilkan **harga saat ini + rekomendasi** di modal.
- [ ] Build + commit.

## Task 6 — Riwayat: satuan % komisi + skip no-op (A4)
**Files:** halaman riwayat + API riwayatnya
- [ ] Baris perubahan komisi: format `X%` (bukan Rp).
- [ ] No-op (nilai sama) ga dicatet — guard API (source of truth; UI Task 3/5 udah nge-skip duluan).
- [ ] Build + commit.

## Task 7 — Komponen bersama ekspansi promo: search SKU + kode + warna katalog (B umum)
**Files:** `app/produk/pusat-promosi/page.tsx` (+ `app/api/produk/pusat-promosi/route.ts`)
- [ ] Bikin SATU komponen/util utk tabel ekspansi promo: (a) input search by SKU (filter client),
      (b) kolom **Kode Produk** (item_id) + **Kode Variasi** (model_id), (c) penanda warna per
      item_id (strip kiri / dot warna, palet siklus ~10 warna by hash item_id) biar 1 katalog keliatan satu.
- [ ] API ekspansi (promo_toko/campaign/flash/voucher/paket/garansi/komisi produk): pastiin kirim
      `item_id` + `model_id` (+ sku) di tiap baris.
- [ ] Terapkan ke ekspansi: Promo Toko (B1), Campaign (B3), Voucher (B5), Paket (B6), Komisi (B7 — kode
      variasi+produk aja tanpa search), Flash (ikut sekalian biar seragam).
- [ ] Build + commit.

## Task 8 — Garansi: header/kolom (B2)
**Files:** `app/produk/pusat-promosi/page.tsx` (+route)
- [ ] Header "Margin" → "Margin Program"; rapihin tampilan kolom Harga Program + Margin Program.
- [ ] Bawah Nama Produk: SKU Induk (`ap.sku` via join item). Bawah Kode Variasi: SKU Variasi (`ho.sku`).
- [ ] Kolom **Kode** sesudah kolom Variasi: kode produk (atas) + kode variasi (bawah).
- [ ] Build + commit.

## Task 9 — Campaign & Flash list (B3 kolom, B4)
**Files:** `app/produk/pusat-promosi/page.tsx` (+route)
- [ ] Campaign: tambah kolom **Sesi Berakhir** (`session_end`); urutan kolom: Tutup Nominasi PINDAH
      ke SEBELUM Mulai Sesi.
- [ ] Flash: kolom baru sesudah Status: **"Jalan/Mendatang"** — badge `Berjalan` (start<=now<=end) /
      `Mendatang` (start>now) / `Berakhir` (end<now) dari start_time/end_time.
- [ ] Build + commit.

## Task 10 — Voucher & Paket format (B5, B6)
**Files:** `app/produk/pusat-promosi/page.tsx` (+route)
- [ ] Voucher kolom Diskon: `X%` vs `RpX` (deteksi tipe diskon dari data voucher — persen kecil vs
      nominal; cek field `discount` + tipe di fakta; SFP `discount=1000` = Rp).
- [ ] Voucher kolom Berakhir + Paket kolom Mulai/Berakhir: sertakan jam:menit (`dd MMM yy HH:mm`).
- [ ] Build + commit.

## Task 11 — Log per-modul drill + bot nyatet SKU (C1)
**Files:** `app/log/page.tsx`, `app/api/log/route.ts`, bot: `modules/fase2_harga.py`,
`modules/provisioning.py`, `modules/takedown_campaign.py`, `modules/flash_sale.py`, `run.py`
- [ ] API: `modulTerakhir` → tambah `history` (N event terakhir per modul, dari hargaEvents yg udah ke-parse).
- [ ] UI: kartu modul klik → riwayat expand (kaya kartu trigger: waktu + toko + aksi + status + detail).
- [ ] Bot: `catat(...)` eksekusi (set harga promo toko, takedown garansi/flash/campaign, provisioning
      paket/voucher/campaign/flash) sertain `detail={"sku": [...]}` / daftar (item,model,aksi) —
      cap ±50 SKU per event biar jsonb ga bengkak.
- [ ] UI detail: render daftar toko+sku+aksi pas expand event.
- [ ] Build + commit (web) & syntax check + commit (bot).

## Self-review notes
- Task 7 = fondasi B1/B3/B5/B6/B7 — kerjain SEBELUM Task 8-10 nyentuh halaman yg sama biar ga konflik.
- Urutan eksekusi: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11.
- `campaign_price` micro (÷100000) — jangan keulang bug 17 Jul.
- Freeze header (Task 1) nyentuh semua halaman — kerjain duluan biar task lain ga rebase ulang.
