# RENCANA IMPLEMENTASI — FASE 1: PENGUMPUL FAKTA

> Bot Syntra Monitoring Harga di-**jahit ulang dari 0** dengan arsitektur **4 fase**:
> **1. Fakta → 2. Masalah → 3. Solusi → 4. Laporan.**
> Dokumen ini = rencana **Fase 1 (Fakta)** saja. Draft — bisa diubah.
>
> Prinsip Fase 1: **READ-ONLY**. Cuma ngumpulin fakta dari Shopee → SQL. TIDAK ada aksi
> ubah harga / takedown / enroll (itu jatah Fase 3 Solusi).

---

## 0. Situasi dalam 4 fase
Scheduler (1 loop 24 jam) tiap siklus akan jalanin ke-4 fase berurutan per toko. **Sekarang kita
bangun Fase 1 dulu**; kerangka `run.py` disiapin biar Fase 2-4 tinggal nyusul. Harvest sesi Shopee
**1× per toko per siklus** dipakai bareng semua fase (paling mahal = buka-tutup browser).

---

## 1. Sumber fakta + cadence (yang dikumpulin Fase 1)

| Tier | Kapan | Fakta | Modul (fungsi BACA yg dipakai) | Tabel tujuan |
|---|---|---|---|---|
| ⏱️ **Jam** | tiap siklus (:05) | harga awal, **harga tampil**, stok, sumber harga, **konteks promo** (nyangkut promo apa) | `grab_produk.grab_produk` (1 sweep) | `harga_olah_data` + `harga_promo_konteks` *(udah ada)* |
| 📅 **Harian** | `jam==JAM_FAKTA_HARIAN` | produk ikut **Garansi** (+bid_id, cspu_id), sesi **Campaign** buka-nominasi + produk kita yg ternominasi (+nomination_id) | `garansi.list_ongoing`, `campaign.open_sessions` + `campaign.get_nominated` | `harga_fakta_garansi`, `harga_fakta_campaign_sesi`, `harga_fakta_campaign_item` |
| 📆 **Mingguan** | `hari==HARI & jam==JAM` | inventaris **Flash Sale** (sesi + item), **Voucher**, **Paket Diskon** — **+ `end_time`** (buat deteksi perlu-perpanjang) | `flash_sale.list_flash_sale`+`items_flash_sale`, `voucher.list_vouchers`, `paket_diskon.list_deals` | `harga_fakta_flash_sesi`, `harga_fakta_flash_item`, `harga_fakta_voucher`, `harga_fakta_paket` |
| 🗓️ **Bulanan** | `tanggal==TGL & jam==JAM` | housekeeping: refresh master katalog + buang baris fakta variasi yg udah gak ada | (internal, SQL) | `harga_all_produk` + prune fakta |

**KOMISI = kasus khusus (lihat §8):** TIDAK di-grab dari Shopee di Fase 1. Sumber kebenaran =
`harga_komisi_toko` (SQL, diedit dashboard). Endpoint gql komisi kena anti-bot `x-sap-sec` (bahkan
read berisiko 403). Tab "Komisi" di Pusat Promosi tampilin data `harga_komisi_toko`.

**HPP = fakta eksternal:** udah di-sync Syntra_Iklan ke `erp_sku_list.hpp` (1×/hari). Fase 1 cukup
BACA dari SQL saat butuh (Fase 2 Masalah), gak grab di sini.

---

## 2. Skema tabel (`db/monitoring_harga.sql`)

### Sudah ada (dipakai ulang, tier jam)
- `harga_olah_data` — PK (toko, item_id, model_id). Grab isi harga/stok/sumber; kolom target & override TIDAK ditimpa.
- `harga_promo_konteks` — keikutsertaan promo per variasi (jenis, campaign_type, promotion_id, harga_promo, status, stok, mulai, berakhir).

### Tabel fakta BARU (tier harian & mingguan). Semua PK natural + `diperbarui_pada timestamptz`.

```sql
-- GARANSI (harian) — grain: variasi
create table if not exists harga_fakta_garansi (
  toko text, item_id bigint, model_id bigint,
  bid_id text, cspu_id text,
  current_price bigint, bid_price bigint, stok int,
  diperbarui_pada timestamptz default now(),
  primary key (toko, item_id, model_id)
);

-- CAMPAIGN sesi buka-nominasi (harian) — grain: sesi
create table if not exists harga_fakta_campaign_sesi (
  toko text, campaign_id text, session_id text,
  campaign_name text, session_name text,
  session_start timestamptz, session_end timestamptz, nomination_end timestamptz,
  diperbarui_pada timestamptz default now(),
  primary key (toko, session_id)
);

-- CAMPAIGN produk kita yang ternominasi (harian) — grain: variasi per sesi
create table if not exists harga_fakta_campaign_item (
  toko text, session_id text, item_id bigint, model_id bigint,
  nomination_id text, nominate_status int, campaign_price bigint,
  diperbarui_pada timestamptz default now(),
  primary key (toko, session_id, item_id, model_id)
);

-- FLASH SALE sesi (mingguan) — grain: sesi
create table if not exists harga_fakta_flash_sesi (
  toko text, flash_sale_id bigint, status int, timeslot_id bigint,
  start_time timestamptz, end_time timestamptz, item_count int,
  diperbarui_pada timestamptz default now(),
  primary key (toko, flash_sale_id)
);

-- FLASH SALE item (mingguan) — grain: variasi per sesi
create table if not exists harga_fakta_flash_item (
  toko text, flash_sale_id bigint, item_id bigint, model_id bigint,
  status int, promotion_price bigint, stock int,
  diperbarui_pada timestamptz default now(),
  primary key (toko, flash_sale_id, item_id, model_id)
);

-- VOUCHER (mingguan) — grain: voucher
create table if not exists harga_fakta_voucher (
  toko text, voucher_id bigint, code text, name text,
  discount numeric, min_price bigint, tipe text,
  start_time timestamptz, end_time timestamptz, status int,
  item_scope jsonb,             -- daftar itemid (voucher produk) / null (semua)
  diperbarui_pada timestamptz default now(),
  primary key (toko, voucher_id)
);

-- PAKET DISKON (mingguan) — grain: bundle
create table if not exists harga_fakta_paket (
  toko text, bundle_deal_id bigint, name text, status int,
  start_time timestamptz, end_time timestamptz, tiers jsonb,
  diperbarui_pada timestamptz default now(),
  primary key (toko, bundle_deal_id)
);
```

> **Pola upsert:** tiap grab tier, `DELETE ... WHERE toko=%s` untuk baris tier itu lalu INSERT ulang
> (fakta = snapshot terbaru; baris lama yg hilang otomatis kebuang). Alternatif upsert per-PK + prune
> baris `diperbarui_pada` basi — dipilih saat implementasi (snapshot delete-insert lebih simpel).

---

## 3. `config.py` — tambahan (SEMUA jadwal di config, bisa di-custom)

```python
# ── SCHEDULER 24 JAM (pola sama Syntra_Iklan) ──
MENIT_RUNNING         = "5"       # nembak tiap jam di menit ini
JAM_FAKTA_HARIAN      = "2"       # 02:00 tiap hari  -> grab Garansi + Campaign
HARI_FAKTA_MINGGUAN   = "SENIN"   # hari grab mingguan
JAM_FAKTA_MINGGUAN    = "3"       # 03:00 (di hari mingguan) -> Flash/Voucher/Paket
TANGGAL_FAKTA_BULANAN = "1"       # tanggal grab bulanan
JAM_FAKTA_BULANAN     = "4"       # 04:00 (di tanggal bulanan) -> housekeeping

HARI_ID = {  # map weekday Inggris -> Indonesia (buat banding HARI_*)
  "Monday":"SENIN","Tuesday":"SELASA","Wednesday":"RABU","Thursday":"KAMIS",
  "Friday":"JUMAT","Saturday":"SABTU","Sunday":"MINGGU",
}
```
> Semua nilai string biar aman dibanding `int(...)`. Ganti jam/hari/tanggal = cukup edit sini.

---

## 4. `run.py` — struktur baru (scheduler + tier gating)

Niru `Syntra_Iklan/iklan/run.py`: loop `while True: sleep(3)` (detak, tanpa log), nembak menit
`MENIT_RUNNING`, guard `now.hour != jam_terakhir` (1×/jam), `jam_siklus.kunci()` bekuin jam acuan.

```python
def siklus_fase1():
    jam_siklus.kunci()
    skr = jam_siklus.now()
    jam  = skr.hour
    hari = config.HARI_ID[skr.strftime("%A")]
    tgl  = skr.day
    for username, info in toko_aktif().items():
        for percobaan in range(1, 4):                 # retry sesi 3x (pola iklan)
            try:
                sesi = grab_session(username, info["i"])
                # ── TIER JAM (selalu) ──
                fakta_produk(username, sesi)           # grab_produk -> olah_data + konteks
                # ── TIER HARIAN ──
                if jam == int(config.JAM_FAKTA_HARIAN):
                    fakta_garansi(username, sesi)
                    fakta_campaign(username, sesi)
                # ── TIER MINGGUAN ──
                if hari == config.HARI_FAKTA_MINGGUAN and jam == int(config.JAM_FAKTA_MINGGUAN):
                    fakta_flash(username, sesi)
                    fakta_voucher(username, sesi)
                    fakta_paket(username, sesi)
                # ── TIER BULANAN ──
                if tgl == int(config.TANGGAL_FAKTA_BULANAN) and jam == int(config.JAM_FAKTA_BULANAN):
                    housekeeping(username, sesi)
                break
            except SesiKedaluwarsa:
                if percobaan == 3: log("skip toko"); 
            except Exception as e:
                log(f"[{username}] gagal: {e}"); break
        close_session()
    # catat timestamp tiap tier ke siklus_log (dashboard Log)
    catat_siklus("harga", "fakta_jam")
    if jam == int(config.JAM_FAKTA_HARIAN):        catat_siklus("harga", "fakta_harian")
    if hari==config.HARI_FAKTA_MINGGUAN and jam==int(config.JAM_FAKTA_MINGGUAN): catat_siklus("harga","fakta_mingguan")
    if tgl==int(config.TANGGAL_FAKTA_BULANAN) and jam==int(config.JAM_FAKTA_BULANAN): catat_siklus("harga","fakta_bulanan")

def main():
    if argv=="login":  buka_login(); return
    if argv=="grab":   siklus_fase1(); return      # tes 1 siklus SEKARANG (manual)
    # SCHEDULER
    jam_terakhir=None
    while True:
        time.sleep(3)
        now=datetime.now()
        if now.minute==int(config.MENIT_RUNNING) and now.hour!=jam_terakhir:
            jam_terakhir=now.hour
            try: siklus_fase1()
            except Exception as e: log(f"siklus gagal, skip: {e}")
```
> `python run.py grab` = tes 1 siklus manual (tier ngikut jam saat itu — bisa dipaksa dgn set jam config
> sementara). Nanti Fase 2/3/4 dipanggil setelah `fakta_produk` di dalam loop yang sama.

---

## 5. Collector Fase 1 (wrapper tipis) + SQL writer

Tiap `fakta_*` = panggil fungsi baca modul → serahkan ke writer `sql_harga.simpan_fakta_*`.
Semua **read-only ke Shopee**. Fungsi baca-nya **udah ada** (tinggal dipanggil):

| Collector | Panggil | Writer baru di `sql_harga.py` |
|---|---|---|
| `fakta_produk` | `grab_produk.grab_produk` | `simpan_olah_data` + `simpan_konteks` *(udah ada)* |
| `fakta_garansi` | `garansi.list_ongoing` | `simpan_fakta_garansi(toko, hasil)` |
| `fakta_campaign` | `campaign.open_sessions` → loop `campaign.get_nominated` | `simpan_fakta_campaign_sesi` + `simpan_fakta_campaign_item` |
| `fakta_flash` | `flash_sale.list_flash_sale` → `items_flash_sale` | `simpan_fakta_flash_sesi` + `simpan_fakta_flash_item` |
| `fakta_voucher` | `voucher.list_vouchers` | `simpan_fakta_voucher` (normalisasi field dari raw) |
| `fakta_paket` | `paket_diskon.list_deals` | `simpan_fakta_paket` |
| `housekeeping` | (SQL) | refresh `harga_all_produk` + prune fakta yatim |

> Writer pola snapshot: `DELETE WHERE toko=%s` lalu `executemany(INSERT ...)`. Konversi epoch→timestamptz
> pakai helper (udah ada `_epoch_iso` di grab_produk — pindahin ke util biar dipakai bareng).

---

## 6. Logging ke dashboard (`siklus_log`)
`catat_siklus("harga", pemicu)` per tier (`fakta_jam`/`fakta_harian`/`fakta_mingguan`/`fakta_bulanan`)
→ muncul di menu **/log** (kartu "Syntra Monitoring Harga") + timestamp kecil di **/produk/harga**.
Ini cuma pencatatan, **bukan** gating (gating tetap by jam/hari/tanggal).

---

## 7. Dashboard (`web/`) — kerjaan terpisah, setelah bot ngisi fakta
1. **Expand row di `/produk/harga`** — tampilan depan TETAP (harga tampil + sumber). Klik baris →
   panel detail: fakta variasi itu ikut promo apa aja. **Read-time JOIN** `harga_promo_konteks` +
   `harga_fakta_*` on `(toko,item_id,model_id)` → gak butuh tabel baru buat expand.
2. **Halaman baru `/produk/pusat-promosi`** (sub-menu Produk) — **tab per modul**:
   `Promo Toko · Paket Diskon · Voucher · Campaign · Garansi · Flash Sale · Komisi`.
   Tiap tab baca 1 tabel `harga_fakta_*` (Komisi baca `harga_komisi_toko`; Promo Toko baca `harga_promo_konteks`).
   API baru: `GET /api/produk/pusat-promosi?tab=...&toko=...` (pagination + search).

---

## 8. KOMISI — kenapa beda (penting)
- Endpoint `affiliateplatform/gql` kena anti-bot `x-sap-sec` (SDK-signed). WRITE pasti 403; READ
  (`GetOpenCampaignProducts`) **berisiko 403 juga** (belum dipastikan lolos via requests).
- Proteksi harga (Fase 2/3) **gak butuh** komisi Shopee — cukup `harga_komisi_toko` (SQL, dashboard).
- **Keputusan Fase 1:** komisi TIDAK di-grab per-jam/harian. Tab Komisi = `harga_komisi_toko`.
- **Opsional (verifikasi live, prioritas rendah):** cek apakah `baca_komisi_aktif` (read gql) lolos
  requests. Kalau lolos → boleh tambah `harga_fakta_komisi` buat reconcile "Shopee vs tab". Kalau
  403 → komisi write/read tetap ranah **UI-automation** (tool manual terpisah, bukan Fase 1).

---

## 9. Urutan implementasi (milestone)
1. **DB**: tambah 7 tabel `harga_fakta_*` ke `db/monitoring_harga.sql` → `python scripts/migrate.py`.
2. **config.py**: tambah blok scheduler (§3).
3. **jam_siklus.py**: bikin (copy dari iklan — bekuin waktu acuan).
4. **sql_harga.py**: tambah writer `simpan_fakta_*` (snapshot delete-insert) + pindah `_epoch_iso` ke util.
5. **run.py**: rombak jadi scheduler + `siklus_fase1` + collector `fakta_*` (§4-5). Verifikasi READ-ONLY.
6. **Tes**: `python run.py grab` 1 toko kecil (Kimmioshop) → cek isi tabel fakta di Supabase.
7. **Log**: pasang `catat_siklus` per tier.
8. **Dashboard**: expand row + halaman Pusat Promosi (§7) — batch terpisah.
9. Update `HANDOFF.md` bot harga + mirror `99. Server/` setelah teruji.

---

## 10. Di LUAR scope Fase 1 (jangan dikerjain di sini)
- Semua **aksi** (ubah harga, takedown, enroll, perpanjang, nominate, opt-out, set komisi) = **Fase 3 Solusi**.
- Deteksi "target vs real", "jual rugi", "keblok promo" = **Fase 2 Masalah**.
- Verdict & audit-log hasil aksi = **Fase 4 Laporan**.
- `blokir.cek_blokir` = dipanggil **on-demand** saat Fase 3 mau ubah harga, bukan dikumpulin rutin.
- Komisi write = UI-automation manual (tool terpisah).
