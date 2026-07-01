-- ============================================================
--  SYNTRA MONITORING HARGA — Skema database (self-contained).
--  Dimiliki & di-apply oleh bot ini sendiri: `python scripts/migrate.py`.
--  (Sebelumnya menumpang di Syntra_Iklan/db/ — dipindah ke sini biar tiap
--   bot mandiri; DB Supabase tetap dibagi, hanya tabel harga_* milik bot ini.)
--  Semua idempoten (create/alter ... if not exists) -> aman dijalankan berkali-kali.
--
--  CATATAN: kolom tambahan harga_all_produk (category, net_price_awal,
--  net_price_detail, harga_diskon, harga_pancing, custom_harga_diskon,
--  custom_harga_pancing, harga_toko) dikelola dashboard (web) via ALTER —
--  TIDAK didefinisikan di sini agar tidak bentrok. Blok ALTER di bawah hanya
--  menjamin kolom yang DIPAKAI bot ini ada.
-- ============================================================

-- 1. Master ALL PRODUK (per-SKU).
create table if not exists harga_all_produk (
    sku              text primary key,
    sku_induk        text,
    nama_produk      text,
    diperbarui_pada  timestamptz default now()
);
-- Kolom yang dipakai bot (target harga) — dijamin ada (dashboard juga memakainya).
alter table harga_all_produk add column if not exists harga_diskon         numeric default 0;
alter table harga_all_produk add column if not exists harga_pancing        numeric default 0;
alter table harga_all_produk add column if not exists custom_harga_diskon  numeric;
alter table harga_all_produk add column if not exists custom_harga_pancing numeric;
alter table harga_all_produk add column if not exists net_price_detail     numeric;

-- 2. Olah Data Harga (per variasi/model per toko).
create table if not exists harga_olah_data (
    toko               text not null,       -- Nama Toko (mis. 'Alialia Store')
    item_id            bigint not null,     -- Kode Produk (Shopee Item ID)
    model_id           bigint not null,     -- Kode Variasi (Shopee Model ID)
    ptag               text,
    sku                text,
    nama_variasi       text,
    nama_produk        text,
    harga_awal         numeric default 0,   -- Origin Price
    harga_diskon_db    numeric default 0,   -- (legacy; tampil dashboard kini join per-SKU)
    harga_pancing      numeric default 0,
    harga_akhir_target numeric default 0,   -- (legacy 'K'; tidak dipakai lagi)
    harga_tampil       numeric default 0,   -- Harga Real saat ini (hasil grab Fase 1)
    selisih            numeric default 0,
    sumber_harga       text,                -- Promo Toko / Harga Awal / dll (label sumber)
    alasan             text,                -- alasan tidak/berhasil ubah harga (Fase 2)
    stok               numeric default 0,   -- stok variasi saat grab (Fase 1)
    diperbarui_pada    timestamptz default now(),
    primary key (toko, item_id, model_id)
);
alter table harga_olah_data add column if not exists stok numeric default 0;

-- 3. Master Produk Komisi affiliate (per-SKU).
create table if not exists harga_komisi_produk (
    sku              text primary key,
    parent_sku       text,
    category         text,
    total_sales      numeric default 0,
    net_price        numeric default 0,
    diperbarui_pada  timestamptz default now()
);

-- 4. Detail Komisi per Toko. Komisi AKTIF = harga_jual > 0.
create table if not exists harga_komisi_toko (
    sku              text references harga_komisi_produk(sku) on delete cascade,
    username_toko    text not null,
    harga_saat_ini   numeric default 0,
    komisi_persen    numeric default 0,
    harga_jual       numeric default 0,
    diperbarui_pada  timestamptz default now(),
    primary key (sku, username_toko)
);

create index if not exists idx_harga_olah_sku on harga_olah_data(sku);
create index if not exists idx_harga_olah_toko on harga_olah_data(toko);
create index if not exists idx_komisi_toko_sku on harga_komisi_toko(sku);

-- 5. Riwayat Update Harga (audit log Fase 2).
create table if not exists harga_riwayat_update (
    id               serial primary key,
    waktu_update     timestamptz default now(),
    sku              text not null,
    aksi             text not null,
    nilai_lama       numeric,
    nilai_baru       numeric,
    username         text not null
);
create index if not exists idx_harga_riwayat_sku on harga_riwayat_update(sku);
create index if not exists idx_harga_riwayat_waktu on harga_riwayat_update(waktu_update desc);

-- 6. KONTEKS PROMO per variasi (Fase 1 full-context).
--    1 baris = satu keikutsertaan promo untuk satu variasi (bisa banyak baris/variasi).
--    Snapshot: baris toko dihapus lalu di-insert ulang tiap grab -> selalu terkini.
--    jenis: Promo Toko / Paket Diskon / Garansi Harga Terbaik / Flash Sale /
--           Voucher / Campaign / Komisi / 'Tipe <n>' (nomor belum dikenali).
create table if not exists harga_promo_konteks (
    toko             text   not null,
    item_id          bigint not null,
    model_id         bigint not null,
    jenis            text   not null,
    campaign_type    integer,
    promotion_id     text   not null default '',
    harga_promo      numeric default 0,
    status           text,
    stok             numeric default 0,
    mulai            timestamptz,
    berakhir         timestamptz,
    diperbarui_pada  timestamptz default now(),
    primary key (toko, item_id, model_id, jenis, promotion_id)
);
create index if not exists idx_promo_konteks_toko on harga_promo_konteks(toko);
create index if not exists idx_promo_konteks_item on harga_promo_konteks(item_id, model_id);
create index if not exists idx_promo_konteks_jenis on harga_promo_konteks(jenis);

-- 7. STATE takedown karena STOK HABIS (Fase 2A).
--    Dicatat saat bot mengeluarkan variasi stok 0 dari promo (audit + tanda
--    daftar-ulang saat stok kembali). waktu_register null = masih di-takedown.
create table if not exists harga_stok_takedown (
    toko             text   not null,
    item_id          bigint not null,
    model_id         bigint not null,
    jenis            text   not null default 'Promo Toko',
    harga_terakhir   numeric default 0,
    waktu_takedown   timestamptz default now(),
    waktu_register   timestamptz,
    primary key (toko, item_id, model_id, jenis)
);
create index if not exists idx_stok_takedown_toko on harga_stok_takedown(toko);
