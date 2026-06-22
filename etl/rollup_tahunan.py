"""
etl/rollup_tahunan.py — bentuk data TAHUNAN dengan menjumlahkan data BULANAN.

Tidak menarik dari Shopee. Murni agregasi di SQL: untuk tiap (produk, tahun)
jumlahkan 12 baris bulanan -> 1 baris periode='tahunan' (periode_mulai = 1 Jan).
Idempotent (upsert) — aman dijalankan berulang.

Catatan: omzet & unit = jumlah persis. pengunjung/keranjang = total kunjungan
setahun (bukan unik), karena dijumlah dari bulanan.

Jalankan:  python -m etl.rollup_tahunan
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import text  # noqa: E402

from config.db import get_engine  # noqa: E402

# Tahun dihitung dalam zona WIB (periode_mulai bulanan = 1 <bulan> 00:00 WIB).
SQL = text("""
    insert into fact_penjualan
        (toko_id, produk_id, periode, periode_mulai,
         pengunjung, keranjang, unit_pesanan, penjualan, pesanan, pembeli, extra)
    select toko_id, produk_id, 'tahunan',
           make_timestamptz(thn::int, 1, 1, 0, 0, 0, 'Asia/Jakarta'),
           sum(pengunjung), sum(keranjang), sum(unit_pesanan), sum(penjualan),
           sum(pesanan), sum(pembeli),
           '{"sumber":"rollup_bulanan"}'::jsonb
    from (
        select toko_id, produk_id,
               extract(year from periode_mulai at time zone 'Asia/Jakarta') thn,
               pengunjung, keranjang, unit_pesanan, penjualan, pesanan, pembeli
        from fact_penjualan
        where periode = 'bulanan'
    ) s
    group by toko_id, produk_id, thn
    on conflict (produk_id, periode, periode_mulai) do update set
        toko_id = excluded.toko_id,
        pengunjung = excluded.pengunjung,
        keranjang = excluded.keranjang,
        unit_pesanan = excluded.unit_pesanan,
        penjualan = excluded.penjualan,
        pesanan = excluded.pesanan,
        pembeli = excluded.pembeli,
        extra = excluded.extra,
        dimuat_pada = now()
""")


SQL_IKLAN = text("""
    insert into fact_iklan
        (toko_id, produk_id, periode, periode_mulai,
         dilihat, klik, konversi, omzet_iklan, biaya_iklan, roas, extra)
    select toko_id, produk_id, 'tahunan',
           make_timestamptz(thn::int, 1, 1, 0, 0, 0, 'Asia/Jakarta'),
           sum(dilihat), sum(klik), sum(konversi), sum(omzet_iklan), sum(biaya_iklan),
           case when sum(biaya_iklan) > 0 then round(sum(omzet_iklan) / sum(biaya_iklan), 4) end,
           '{"sumber":"rollup_bulanan"}'::jsonb
    from (
        select toko_id, produk_id,
               extract(year from periode_mulai at time zone 'Asia/Jakarta') thn,
               dilihat, klik, konversi, omzet_iklan, biaya_iklan
        from fact_iklan
        where periode = 'bulanan'
    ) s
    group by toko_id, produk_id, thn
    on conflict (produk_id, periode, periode_mulai) do update set
        toko_id = excluded.toko_id, dilihat = excluded.dilihat, klik = excluded.klik,
        konversi = excluded.konversi, omzet_iklan = excluded.omzet_iklan,
        biaya_iklan = excluded.biaya_iklan, roas = excluded.roas,
        extra = excluded.extra, dimuat_pada = now()
""")


def main():
    with get_engine().begin() as conn:
        res = conn.execute(SQL)
        print(f"Rollup tahunan PENJUALAN: {res.rowcount} baris.")
        res2 = conn.execute(SQL_IKLAN)
        print(f"Rollup tahunan IKLAN: {res2.rowcount} baris.")
        n = conn.execute(text("select count(*) from fact_penjualan where periode='tahunan'")).scalar()
        ni = conn.execute(text("select count(*) from fact_iklan where periode='tahunan'")).scalar()
        print(f"Total tahunan: penjualan {n}, iklan {ni}")


if __name__ == "__main__":
    main()
