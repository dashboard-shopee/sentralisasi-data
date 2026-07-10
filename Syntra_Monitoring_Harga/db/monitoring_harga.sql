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
    diproses_pada      timestamptz,         -- kapan Fase 2/3 terakhir MENGUBAH alasan baris ini (bukan tiap grab)
    primary key (toko, item_id, model_id)
);
alter table harga_olah_data add column if not exists stok numeric default 0;
alter table harga_olah_data add column if not exists diproses_pada timestamptz;

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

-- ============================================================
--  FASE 1 (PENGUMPUL FAKTA) — tabel fakta per-program.
--  Diisi READ-ONLY oleh bot (tier harian/mingguan). Pola snapshot:
--  baris toko dihapus lalu di-insert ulang tiap grab -> selalu terkini.
--  Kolom 'toko' = NAMA toko (mis. 'Kimmioshop') biar bisa JOIN dgn
--  harga_olah_data / harga_promo_konteks on (toko, item_id, model_id).
--  Sumber render: halaman dashboard "Pusat Promosi" (tab per modul) +
--  expand row di /produk/harga.
-- ============================================================

-- 8. FAKTA GARANSI HARGA TERBAIK (harian) — grain: variasi. Sumber: garansi.list_ongoing.
create table if not exists harga_fakta_garansi (
    toko             text   not null,
    item_id          bigint not null,
    model_id         bigint not null,
    bid_id           text,
    cspu_id          text,
    current_price    numeric default 0,   -- Harga Kini (harga tampil Shopee)
    bid_price        numeric default 0,   -- Harga Program (garansi yg diset)
    best_price       numeric default 0,   -- Harga Terbaik (rekomendasi terendah Shopee)
    stok             numeric default 0,
    diperbarui_pada  timestamptz default now(),
    primary key (toko, item_id, model_id)
);
alter table harga_fakta_garansi add column if not exists best_price numeric default 0;
create index if not exists idx_fakta_garansi_toko on harga_fakta_garansi(toko);

-- 9. FAKTA CAMPAIGN — sesi buka-nominasi (harian). Grain: sesi. Sumber: campaign.open_sessions.
create table if not exists harga_fakta_campaign_sesi (
    toko             text not null,
    campaign_id      text not null,
    session_id       text not null,
    campaign_name    text,
    session_name     text,
    session_start    timestamptz,
    session_end      timestamptz,
    nomination_end   timestamptz,
    diperbarui_pada  timestamptz default now(),
    primary key (toko, session_id)
);
create index if not exists idx_fakta_camp_sesi_toko on harga_fakta_campaign_sesi(toko);

-- 10. FAKTA CAMPAIGN — produk kita yang ternominasi (harian). Grain: variasi/sesi. Sumber: campaign.get_nominated.
create table if not exists harga_fakta_campaign_item (
    toko             text   not null,
    session_id       text   not null,
    item_id          bigint not null,
    model_id         bigint not null,
    nomination_id    text,
    nominate_status  integer,
    campaign_price   numeric default 0,
    diperbarui_pada  timestamptz default now(),
    primary key (toko, session_id, item_id, model_id)
);
create index if not exists idx_fakta_camp_item_toko on harga_fakta_campaign_item(toko);
create index if not exists idx_fakta_camp_item_key on harga_fakta_campaign_item(item_id, model_id);

-- 11. FAKTA FLASH SALE — sesi (mingguan). Grain: sesi. Sumber: flash_sale.list_flash_sale.
create table if not exists harga_fakta_flash_sesi (
    toko             text   not null,
    flash_sale_id    bigint not null,
    status           integer,
    timeslot_id      bigint,
    start_time       timestamptz,
    end_time         timestamptz,
    item_count       integer default 0,
    diperbarui_pada  timestamptz default now(),
    primary key (toko, flash_sale_id)
);
create index if not exists idx_fakta_flash_sesi_toko on harga_fakta_flash_sesi(toko);

-- 12. FAKTA FLASH SALE — item (mingguan). Grain: variasi/sesi. Sumber: flash_sale.items_flash_sale.
create table if not exists harga_fakta_flash_item (
    toko             text   not null,
    flash_sale_id    bigint not null,
    item_id          bigint not null,
    model_id         bigint not null,
    status           integer,
    promotion_price  numeric default 0,
    stock            numeric default 0,
    diperbarui_pada  timestamptz default now(),
    primary key (toko, flash_sale_id, item_id, model_id)
);
create index if not exists idx_fakta_flash_item_toko on harga_fakta_flash_item(toko);
create index if not exists idx_fakta_flash_item_key on harga_fakta_flash_item(item_id, model_id);

-- 13. FAKTA VOUCHER (mingguan). Grain: voucher. Sumber: voucher.list_vouchers.
--     item_scope = jsonb daftar itemid (voucher produk) atau null (semua produk).
create table if not exists harga_fakta_voucher (
    toko             text   not null,
    voucher_id       bigint not null,
    code             text,
    name             text,
    discount         numeric,
    min_price        numeric,
    tipe             text,
    start_time       timestamptz,
    end_time         timestamptz,
    status           integer,
    item_scope       jsonb,
    diperbarui_pada  timestamptz default now(),
    primary key (toko, voucher_id)
);
create index if not exists idx_fakta_voucher_toko on harga_fakta_voucher(toko);

-- 14. FAKTA PAKET DISKON (mingguan). Grain: bundle. Sumber: paket_diskon.list_deals.
create table if not exists harga_fakta_paket (
    toko             text   not null,
    bundle_deal_id   bigint not null,
    name             text,
    status           integer,
    start_time       timestamptz,
    end_time         timestamptz,
    tiers            jsonb,
    diperbarui_pada  timestamptz default now(),
    primary key (toko, bundle_deal_id)
);
create index if not exists idx_fakta_paket_toko on harga_fakta_paket(toko);

-- 14b. FAKTA KOMISI AFFILIATE Shopee (harian). Grain: item. Sumber: BROWSER grab
--      (run.py komisi_grab -> GetOpenCampaignProducts, bypass anti-bot gql). Komisi AKTIF =
--      commissionStatus 'CommissionStatusOngoing' + commission_id valid. Dibanding vs
--      harga_komisi_toko (Syntra "harusnya") di dashboard #9. persen: 10000/1000 = 10.0.
create table if not exists harga_fakta_komisi (
    toko             text   not null,
    item_id          bigint not null,
    commission_id    text,
    persen           numeric default 0,
    status           text,
    item_name        text,
    diperbarui_pada  timestamptz default now(),
    primary key (toko, item_id)
);
create index if not exists idx_fakta_komisi_toko on harga_fakta_komisi(toko);

-- 14c. FAKTA GARANSI NOMINASI (harian) — 3 kategori halaman Nominasi Produk. Grain: item/model.
--     Sumber: garansi.list_rekomendasi (belum-didaftar) + list_ongoing_status (bid_status 30/40).
--     kategori: 'rekomendasi' (belum didaftar) | 'terbaik' (winning, muncul customer) | 'perlu_ditinjau'.
--     floor = Harga Terbaik (best), ceiling = Harga Program. Buat dashboard Pusat Promosi > Garansi (3 tab).
create table if not exists harga_fakta_garansi_nom (
    toko             text   not null,
    item_id          bigint not null,
    model_id         bigint not null default 0,
    kategori         text   not null,
    item_name        text,
    model_name       text,
    floor            numeric default 0,
    ceiling          numeric default 0,
    stok             numeric default 0,
    bid_id           text,
    bid_status       integer,
    diperbarui_pada  timestamptz default now(),
    primary key (toko, item_id, model_id, kategori)
);
create index if not exists idx_fakta_garansi_nom_toko on harga_fakta_garansi_nom(toko, kategori);

-- 15. KATEGORI Shopee per produk (Fase 1, incremental). Grain: item (bukan variasi).
--     Sumber: get_product_info (category_path + category_path_name_list). UPSERT (bukan
--     snapshot) — diisi bertahap cuma utk produk yg belum punya kategori.
create table if not exists harga_produk_kategori (
    toko             text   not null,
    item_id          bigint not null,
    kategori_id      bigint,             -- id kategori daun (paling spesifik)
    kategori_leaf    text,               -- nama kategori daun (mis. 'Tempat Pensil')
    kategori_full    text,               -- path lengkap ('Buku & Alat Tulis > ... > Tempat Pensil')
    diperbarui_pada  timestamptz default now(),
    primary key (toko, item_id)
);
create index if not exists idx_produk_kategori_toko on harga_produk_kategori(toko);

-- 16. FAKTA PROMO TOKO — entity promo (berjalan + akan datang), buat Pusat Promosi master-detail.
--     Sumber: discount_util.grab_semua_promo + grab_promo_detail. Cadence: harian.
create table if not exists harga_fakta_promo_toko (
    toko             text   not null,
    promotion_id     bigint not null,
    nama             text,
    status           text,               -- 'berjalan' / 'akan datang'
    mulai            timestamptz,
    berakhir         timestamptz,
    item_count       integer default 0,
    diperbarui_pada  timestamptz default now(),
    primary key (toko, promotion_id)
);
create index if not exists idx_fakta_promo_toko_toko on harga_fakta_promo_toko(toko);

-- 17. FAKTA PROMO TOKO — produk di tiap promo (buat expand klik->produk). Sumber: grab_item_promo.
create table if not exists harga_fakta_promo_toko_item (
    toko             text   not null,
    promotion_id     bigint not null,
    item_id          bigint not null,
    model_id         bigint not null,
    harga_promo      numeric default 0,
    diperbarui_pada  timestamptz default now(),
    primary key (toko, promotion_id, item_id, model_id)
);
create index if not exists idx_fakta_pt_item_toko on harga_fakta_promo_toko_item(toko);
create index if not exists idx_fakta_pt_item_promo on harga_fakta_promo_toko_item(toko, promotion_id);
