# STATUS — Syntra Monitoring Harga (acuan tunggal progres)

> **Baca file ini dulu tiap mulai kerja.** Legenda: ✅ selesai · 🔧 lagi dikerjain · ⏳ belum · ⏸️ ditunda/PR.
> Arsitektur **3 fase**: 1=Fakta · 2=Masalah+Solusi · 3=Laporan. **Cadence per-MODUL** (bukan per-fase).
> Spec detail: `RENCANA_FASE1.md`, `RENCANA_FASE2.md`. Update terakhir: **9 Jul 2026**.

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
| **5** | **Promo Toko master-detail** (aktif+akan datang → klik→produk) | ⏳ **(lagi dibahas)** |
| 6 | Paket Diskon master-detail + KPI (aktif+akan datang → klik→produk) | ⏳ |
| 7 | Campaign rework (running+upcoming → klik→produk; cek nominasi=0) | ⏳ |

> Pattern master-detail udah ADA & reusable (dibangun utk Voucher): `DETAIL_TABS`+`toggleRow`+expand-row di `web/.../pusat-promosi/page.tsx`, API `tab=<x>_produk`.

---

## FASE 2 — MASALAH + SOLUSI
### Modul HARGA (poin 1–4, per-jam)
| Bagian | Status |
|---|---|
| DETEKSI/diagnosa (kasus tanpa_target/sesuai/koreksi_turun/harga_dasar + cek semua promo) | ✅ (read-only) |
| Guard promo tak-dikenal "Tipe 1" (hold ≥target-500, flag <target-500) | ✅ |
| **3a Eksekusi Promo Toko** (lifecycle buat/duplikat + set/daftar) | ✅ DRY-RUN |
| **4 Harga Dasar** (takedown semua promo → ubah base → pasang lagi paket+voucher) | ⏳ **(next)** |
| 3b Takedown Garansi (best<target-500 / margin<7%) | ⏳ (margin@best detail pending) |
| 3c Takedown Flash (flash<target-10 / stok 0) | ⏳ |
| 3d Takedown Campaign (price<target*98.5% / stok<30 / stok<penjualan/hari) | ⏳ |

### Provisioning (poin 5)
| Modul | Cadence | Status |
|---|---|---|
| Promo Toko (buat/duplikat + daftar produk baru) | jam | ✅ (bagian eksekusi 3a) |
| Garansi (daftar, kondisi best/margin, batalkan "perlu ditinjau") | harian | ⏳ |
| Paket Diskon (buat/enroll semua) | harian | ⏳ |
| Voucher (buat/enroll semua) | harian | ⏳ |
| Campaign (daftar, harga≤target*98.5%, stok>50 & >10×penjualan/hari) | mingguan | ⏳ |
| Flash Sale (maks 50/sesi, per kategori×penjualan, harga real-10) | mingguan | ⏳ |

### Wiring
| Item | Status |
|---|---|
| Jahit Fase 2 ke `run.py` (per-toko: grab→diagnosa→eksekusi) | ⏳ (masih modul terpisah, blm di run.py) |

---

## FASE 3 — LAPORAN
| Item | Status |
|---|---|
| Verdict + audit hasil aksi ke dashboard | ⏳ (belum mulai) |

---

## ⏸️ PR / DITUNDA (jangan lupa)
- ⏸️ **Identifikasi "Tipe 1"** (campaign_type=1) — sniff pas aktif lagi (udah berakhir 8 Jul). Sementara: guard hold/flash.
- ⏸️ **Margin<7% guard** (garansi + promo tak dikenal) — hitung margin@harga-promo, masih STUB.
- ⏸️ **Perpanjang promo toko** — dianggap tak bisa extend (temuan lama) → duplikat. Verifikasi endpoint kalau perlu.
- ⏸️ Garansi "perlu ditinjau" → batalkan (detail pas modul garansi).
- ⏸️ Paket/Voucher aturan enroll detail; Campaign/Flash pemilihan produk per-kategori.
- ⏸️ Kategori isi awal (`run.py kategori`) — user jalanin (get_product_info sensitif anti-bot).

---

## Urutan kerja Fase 2 (disepakati)
1. Harga poin 1-4 (🔧 3a ✅, next: 4 Harga Dasar → 3b/c/d takedown)
2. Garansi provisioning (+ detail margin@best)
3. Paket + Voucher provisioning
4. Campaign + Flash provisioning
5. Jahit ke run.py + Fase 3 Laporan
