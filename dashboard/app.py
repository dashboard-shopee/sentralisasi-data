"""
dashboard/app.py — entry dashboard Shopee Multi-Toko (multi-halaman).

Jalankan dari root project:
    streamlit run dashboard/app.py

Menambah sumber data baru = tambah 1 file di halaman/ + 1 baris st.Page di bawah.
Halaman membaca dari SQL; yang tabelnya masih kosong tampil sebagai "menunggu"
dan otomatis nyala saat datanya masuk.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st

st.set_page_config(page_title="Dashboard Shopee Multi-Toko", page_icon="🛒", layout="wide")

import os  # noqa: E402

import lib  # noqa: E402

lib.inject_css()


def _gate() -> bool:
    """Password gate untuk versi online. Kalau tidak ada password diset (lokal),
    dashboard terbuka. Di Streamlit Cloud, set secret `password`."""
    pw = None
    try:
        pw = st.secrets.get("password")
    except Exception:
        pw = None
    pw = pw or os.getenv("DASH_PASSWORD")
    if not pw:
        return True  # lokal / belum diset -> buka
    if st.session_state.get("_auth"):
        return True
    st.markdown("### 🔒 Dashboard Shopee Multi-Toko")
    x = st.text_input("Password", type="password")
    if st.button("Masuk"):
        if x == pw:
            st.session_state["_auth"] = True
            st.rerun()
        else:
            st.error("Password salah.")
    return False


if not _gate():
    st.stop()

from halaman import analisa, harga, iklan, kompetitor, penjualan, pesanan, ringkasan  # noqa: E402

nav = st.navigation([
    st.Page(ringkasan.render, title="Ringkasan", icon="🏠", url_path="ringkasan", default=True),
    st.Page(analisa.render, title="Analisa", icon="📊", url_path="analisa"),
    st.Page(penjualan.render, title="Penjualan", icon="📦", url_path="penjualan"),
    st.Page(pesanan.render, title="Pesanan", icon="🛒", url_path="pesanan"),
    st.Page(iklan.render, title="Iklan", icon="📢", url_path="iklan"),
    st.Page(harga.render, title="Harga", icon="🏷️", url_path="harga"),
    st.Page(kompetitor.render, title="Kompetitor", icon="🔍", url_path="kompetitor"),
])
nav.run()
