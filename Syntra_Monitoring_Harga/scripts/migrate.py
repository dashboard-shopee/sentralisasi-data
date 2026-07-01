"""scripts/migrate.py — terapkan skema DB milik Syntra_Monitoring_Harga.

Self-contained: pakai db/monitoring_harga.sql (bukan menumpang Syntra_Iklan).
Semua statement idempoten (create/alter ... if not exists) -> aman berkali-kali.

    cd Syntra_Monitoring_Harga
    python scripts/migrate.py
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules.db import get_engine  # noqa: E402

SCHEMA_FILE = ROOT / "db" / "monitoring_harga.sql"


def split_statements(sql: str) -> list:
    """Pecah skrip jadi statement; buang komentar baris (--) dulu agar ';'
    di dalam komentar tidak salah memotong."""
    tanpa_komentar = re.sub(r"--[^\n]*", "", sql)
    return [s.strip() for s in tanpa_komentar.split(";") if s.strip()]


def main():
    if not SCHEMA_FILE.exists():
        raise SystemExit(f"Skema tidak ditemukan: {SCHEMA_FILE}")
    engine = get_engine()
    with engine.begin() as conn:
        for stmt in split_statements(SCHEMA_FILE.read_text(encoding="utf-8")):
            conn.exec_driver_sql(stmt)
    print(f"  Skema diterapkan dari {SCHEMA_FILE.name} (idempoten).")
    print("Selesai.")


if __name__ == "__main__":
    main()
