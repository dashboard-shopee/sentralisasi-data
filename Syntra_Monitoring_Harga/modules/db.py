"""modules/db.py — koneksi Supabase (PostgreSQL) untuk Syntra_Monitoring_Harga.

Pakai DATABASE yang SAMA dengan Syntra_Iklan (Supabase), tapi nulis ke tabel
harga_* saja. Koneksi terpisah (Postgres handle banyak koneksi) -> tidak bentrok.
"""
import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool

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
        # NullPool: buka-pakai-TUTUP tiap operasi, TIDAK nahan koneksi idle.
        # Wajib buat Supabase Session Pooler (limit 15 client, DIBAGI bareng ETL iklan +
        # dashboard). QueuePool default nahan ~5 koneksi idle -> pas bot nunggu HTTP lama
        # (mis. campaign), idle-nya numpuk bentrok proses lain -> EMAXCONNSESSION.
        # Bot ini sekuensial (1 koneksi sesaat cukup) jadi NullPool aman & hemat slot.
        _engine = create_engine(url, poolclass=NullPool, pool_pre_ping=True)
    return _engine
