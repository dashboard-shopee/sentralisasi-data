"""
scripts/setup_db.py — buat semua tabel di Supabase dari db/schema.sql,
lalu isi (seed) 10 toko ke dim_toko.

Jalankan sekali (boleh diulang — idempotent):
    python scripts/setup_db.py
"""

import sys
from pathlib import Path

# Biar bisa import package config/ saat dijalankan langsung.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import re  # noqa: E402

from sqlalchemy import text  # noqa: E402

from config.db import get_engine  # noqa: E402

SCHEMA_FILE = ROOT / "db" / "schema.sql"


def split_statements(sql: str) -> list[str]:
    """Pecah skrip SQL jadi statement. Buang komentar baris (--) dulu supaya
    titik koma di dalam komentar tidak salah memotong statement."""
    tanpa_komentar = re.sub(r"--[^\n]*", "", sql)
    return [s.strip() for s in tanpa_komentar.split(";") if s.strip()]

# Daftar 10 toko (sumber: config.py program "01 Otomatisasi Iklan").
# (username, nama tampilan, shop_index)
TOKO = [
    ("kimmioshop", "Kimmioshop", 1),
    ("lolly0310", "lollysweet", 2),
    ("ravellashop", "Ravella Shop", 3),
    ("topikece2023", "Topikece Store", 4),
    ("alialiastore", "Alialia Store", 5),
    ("oliolio.id", "OLIOLIO.ID", 6),
    ("nomidestore", "NOMIDE STORE", 7),
    ("yarrastore", "YARRA STORE", 8),
    ("zioscarf", "ZIOSCARF SUPPLIER HIJAB IMPORT", 9),
    ("beverra", "BEVERRA OFFICIAL STORE", 10),
]


def buat_tabel(conn):
    """Eksekusi schema.sql, statement per statement."""
    sql = SCHEMA_FILE.read_text(encoding="utf-8")
    statements = split_statements(sql)
    for stmt in statements:
        conn.exec_driver_sql(stmt)
    print(f"  OK — {len(statements)} statement skema dieksekusi.")


def seed_toko(conn):
    """Isi/segarkan dim_toko (idempotent via ON CONFLICT username)."""
    q = text(
        """
        insert into dim_toko (username, nama, shop_index)
        values (:username, :nama, :shop_index)
        on conflict (username) do update
            set nama = excluded.nama,
                shop_index = excluded.shop_index
        """
    )
    for username, nama, idx in TOKO:
        conn.execute(q, {"username": username, "nama": nama, "shop_index": idx})
    print(f"  OK — {len(TOKO)} toko di dim_toko.")


def main():
    print("Menghubungkan ke Supabase...")
    engine = get_engine()
    with engine.begin() as conn:
        print("Membuat tabel dari db/schema.sql...")
        buat_tabel(conn)
        print("Mengisi data toko...")
        seed_toko(conn)
    print("\nSelesai. Database siap dipakai.")


if __name__ == "__main__":
    main()
