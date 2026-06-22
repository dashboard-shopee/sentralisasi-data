"""
config/db.py — koneksi ke database Supabase (PostgreSQL).

Baca DATABASE_URL dari .env, kembalikan SQLAlchemy engine (driver psycopg3).
Semua akses DB di project ini lewat get_engine().
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

# Muat .env dari root project (parent dari folder config/).
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", "")


def get_engine() -> Engine:
    """Engine SQLAlchemy ke Supabase. SSL dipaksa (wajib di Supabase)."""
    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL belum diisi di .env. "
            "Ambil connection string (Session pooler) dari tombol 'Connect' di Supabase."
        )
    # Pakai driver psycopg v3.
    url = DATABASE_URL
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)

    return create_engine(
        url,
        pool_pre_ping=True,
        connect_args={"sslmode": "require"},
    )
