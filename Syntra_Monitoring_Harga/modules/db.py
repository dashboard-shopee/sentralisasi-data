"""modules/db.py — koneksi Supabase (PostgreSQL) untuk Syntra_Monitoring_Harga.

Pakai DATABASE yang SAMA dengan Syntra_Iklan (Supabase), tapi nulis ke tabel
harga_* saja. Koneksi terpisah (Postgres handle banyak koneksi) -> tidak bentrok.
"""
import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine

# .env ada di root folder Syntra_Monitoring_Harga (parent dari modules/)
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        url = os.getenv("DATABASE_URL", "")
        if not url:
            raise RuntimeError("DATABASE_URL belum diisi di .env Syntra_Monitoring_Harga")
        # Pakai driver psycopg v3 (sama dgn Syntra_Iklan).
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        elif url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+psycopg://", 1)
        _engine = create_engine(url, pool_pre_ping=True)
    return _engine
