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


def _database_url() -> str:
    """Ambil DATABASE_URL dari env (.env lokal) ATAU st.secrets (Streamlit Cloud)."""
    url = os.getenv("DATABASE_URL", "")
    if not url:
        try:
            import streamlit as st  # hanya ada saat jalan di dashboard / Cloud
            url = st.secrets.get("DATABASE_URL", "")
        except Exception:
            url = ""
    return url


def get_engine() -> Engine:
    """Engine SQLAlchemy ke Supabase. SSL dipaksa (wajib di Supabase)."""
    url = _database_url()
    if not url:
        raise RuntimeError(
            "DATABASE_URL belum diisi (.env lokal / Secrets Streamlit Cloud)."
        )
    # Pakai driver psycopg v3.
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)

    return create_engine(
        url,
        pool_pre_ping=True,
        connect_args={"sslmode": "require"},
    )
