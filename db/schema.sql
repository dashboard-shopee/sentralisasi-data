-- ============================================================
--  SENTRALISASI DATA — Skema PostgreSQL (Supabase)  v2
--  Satu sumber kebenaran untuk data 3 program otomasi Shopee.
--  Model: star schema. Istilah Indonesia. Sumber data = API Shopee
--  (program nulis langsung ke sini), bukan parsing Sheet.
--
--  Granularity periode: realtime | harian | mingguan | bulanan | tahunan
--  Metrik inti = kolom sendiri (cepat untuk dashboard).
--  Kolom `extra jsonb` = ruang untuk variabel laporan baru tanpa ubah skema.
-- ============================================================

-- ====================== DIMENSI =============================

create table if not exists dim_toko (
    toko_id      serial primary key,
    username     text unique not null,        -- key Shopee, mis. 'kimmioshop'
    nama         text not null,
    shop_index   int,
    aktif        boolean default true,
    dibuat_pada  timestamptz default now()
);

create table if not exists dim_produk (
    produk_id        bigint primary key,      -- item_id Shopee (unik global)
    toko_id          int references dim_toko(toko_id),
    nama_produk      text,
    sku_induk        text,
    diperbarui_pada  timestamptz default now()
);

create table if not exists dim_variasi (
    model_id      bigint primary key,
    produk_id     bigint references dim_produk(produk_id),
    nama_variasi  text,
    sku           text
);

-- ====================== FAKTA ===============================

-- [Program 01] Performa penjualan / produk (sumber: API product/performance).
-- Header sheet asal: Pengunjung(Kunjungan), Pengunjung(Keranjang),
-- Produk(Pesanan Siap Dikirim), Penjualan(IDR).
create table if not exists fact_penjualan (
    id              bigserial primary key,
    toko_id         int references dim_toko(toko_id),
    produk_id       bigint references dim_produk(produk_id),
    periode         text not null
                    check (periode in ('realtime','harian','mingguan','bulanan','tahunan')),
    periode_mulai   timestamptz not null,     -- realtime = jam; lainnya = awal periode
    periode_selesai timestamptz,
    pengunjung      bigint,                    -- kunjungan (uv)
    keranjang       bigint,                    -- menambahkan ke keranjang (add_to_cart_buyers)
    unit_pesanan    int,                       -- kuantitas terjual (confirmed_units)
    penjualan       numeric,                   -- IDR (confirmed_sales)
    pesanan         int,                       -- JUMLAH ORDER (confirmed_orders) — 1 order bisa banyak unit
    pembeli         int,                       -- pembeli unik (confirmed_buyers)
    extra           jsonb default '{}'::jsonb, -- metrik kaya lain (ctr, pv, conv rate, dst)
    dimuat_pada     timestamptz default now(),
    unique (produk_id, periode, periode_mulai)
);

-- [Program 01] Performa iklan (sumber: API homepage/query).
-- Header sheet asal: Dilihat, Jumlah Klik, Konversi, Omzet Penjualan, Biaya.
create table if not exists fact_iklan (
    id              bigserial primary key,
    toko_id         int references dim_toko(toko_id),
    produk_id       bigint references dim_produk(produk_id),  -- nullable: level toko
    periode         text not null
                    check (periode in ('realtime','harian','mingguan','bulanan','tahunan')),
    periode_mulai   timestamptz not null,
    periode_selesai timestamptz,
    dilihat         bigint,                    -- impresi
    klik            bigint,
    konversi        int,                       -- pesanan dari iklan
    omzet_iklan     numeric,                   -- omzet penjualan dari iklan
    biaya_iklan     numeric,                   -- biaya iklan
    roas            numeric,                   -- omzet_iklan / biaya_iklan
    extra           jsonb default '{}'::jsonb,
    dimuat_pada     timestamptz default now(),
    unique (produk_id, periode, periode_mulai)
);

-- [Program 02] Monitoring harga (sumber: API search_product_list) — snapshot.
create table if not exists fact_harga (
    id            bigserial primary key,
    toko_id       int references dim_toko(toko_id),
    item_id       bigint,
    model_id      bigint,
    sku           text,
    nama_produk   text,
    nama_variasi  text,
    harga_awal    numeric,                     -- origin price (kolom H)
    harga_target  numeric,                     -- harga akhir / rumus user (kolom K)
    harga_tampil  numeric,                     -- yang muncul ke pembeli (kolom L)
    sumber_harga  text,                        -- Promo Toko / Harga Awal / dst (kolom N)
    extra         jsonb default '{}'::jsonb,
    diambil_pada  timestamptz default now()
);

-- [Program 01] Pesanan per toko (sumber: API order/sales — DISIAPKAN, penarikan menyusul).
-- Level toko (bukan per produk): jumlah & status pesanan per periode.
create table if not exists fact_pesanan (
    id              bigserial primary key,
    toko_id         int references dim_toko(toko_id),
    periode         text not null
                    check (periode in ('realtime','harian','mingguan','bulanan','tahunan')),
    periode_mulai   timestamptz not null,
    periode_selesai timestamptz,
    jumlah_pesanan  int,                       -- total pesanan dibuat
    pesanan_siap    int,                       -- pesanan siap dikirim / dibayar
    pesanan_batal   int,                       -- dibatalkan
    pembeli         int,                       -- jumlah pembeli unik
    omzet_pesanan   numeric,                   -- nilai pesanan (Rp)
    extra           jsonb default '{}'::jsonb,
    dimuat_pada     timestamptz default now(),
    unique (toko_id, periode, periode_mulai)
);

-- [Program 03] Riset kompetitor — produk serupa per market.
create table if not exists fact_kompetitor (
    id            bigserial primary key,
    market        text,                        -- WP / Best Seller / PL
    produk_acuan  text,
    toko_pesaing  text,
    nama_produk   text,
    harga         numeric,
    terjual       int,
    rating        numeric,
    url           text,
    extra         jsonb default '{}'::jsonb,
    diambil_pada  timestamptz default now()
);

-- ====================== INDEX ===============================
create index if not exists idx_penjualan_toko_periode on fact_penjualan (toko_id, periode, periode_mulai);
create index if not exists idx_iklan_toko_periode     on fact_iklan (toko_id, periode, periode_mulai);
create index if not exists idx_harga_toko             on fact_harga (toko_id, diambil_pada);
create index if not exists idx_kompetitor_market      on fact_kompetitor (market, diambil_pada);
create index if not exists idx_pesanan_toko_periode   on fact_pesanan (toko_id, periode, periode_mulai);
