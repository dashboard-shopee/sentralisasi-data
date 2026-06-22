"""
scripts/migrate.py — terapkan ulang db/schema.sql.

Default: hanya buat tabel yang belum ada (aman, tidak menghapus data).
Pakai --reset-fakta untuk DROP & buat ulang tabel fakta (HAPUS isinya) —
berguna saat skema fakta berubah dan datanya masih kosong/boleh dibuang.
Dimensi (dim_*) tidak pernah disentuh.

    python scripts/migrate.py
    python scripts/migrate.py --reset-fakta
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config.db import get_engine  # noqa: E402
from scripts.setup_db import SCHEMA_FILE, seed_toko, split_statements  # noqa: E402

TABEL_FAKTA = ["fact_penjualan", "fact_iklan", "fact_harga", "fact_kompetitor"]


def main(reset_fakta: bool):
    engine = get_engine()
    with engine.begin() as conn:
        if reset_fakta:
            for t in TABEL_FAKTA:
                conn.exec_driver_sql(f"drop table if exists {t} cascade")
            print(f"  Drop tabel fakta: {', '.join(TABEL_FAKTA)}")
        sql = SCHEMA_FILE.read_text(encoding="utf-8")
        for stmt in split_statements(sql):
            conn.exec_driver_sql(stmt)
        print("  Skema diterapkan.")
        seed_toko(conn)
    print("Selesai.")


if __name__ == "__main__":
    main(reset_fakta="--reset-fakta" in sys.argv)
