"""Halaman Harga (sumber: fact_harga). Auto-nyala saat program Monitoring Harga jalan."""

import plotly.express as px
import streamlit as st

import lib


def render():
    lib.header("🏷️ Monitoring Harga", "Harga & promo per produk · sumber: bot Monitoring Harga")

    if not lib.ada_data("fact_harga"):
        lib.empty_state(
            "Data harga belum masuk",
            "Akan muncul OTOMATIS setelah program 'Otomatisasi Monitoring Harga' "
            "disambungkan ke SQL (Bagian C). Tabel fact_harga sudah siap menampung.")
        return

    # Snapshot terbaru
    snap = lib.q("select max(diambil_pada) m from fact_harga").iloc[0]["m"]
    semua = lib.daftar_toko()
    with st.sidebar:
        st.subheader("Filter")
        toko = st.multiselect("Toko", semua, default=semua, key="hg_toko")
    if not toko:
        st.info("Pilih minimal satu toko.")
        return

    P = {"s": snap, "toko": tuple(toko)}
    W = "f.diambil_pada=:s and t.nama in :toko"
    k = lib.q(f"""
        select count(*) n, count(distinct f.item_id) produk,
               avg(f.harga_tampil) avg_tampil
        from fact_harga f join dim_toko t on t.toko_id=f.toko_id where {W}
    """, P).iloc[0]
    c = st.columns(3)
    lib.kpi(c[0], "🏷️", "Variasi Terpantau", lib.num_ringkas(k["n"]))
    lib.kpi(c[1], "📦", "Produk", lib.num_ringkas(k["produk"]))
    lib.kpi(c[2], "💲", "Harga Tampil Rata2", lib.rp_ringkas(k["avg_tampil"]))

    st.write("")
    with st.container(border=True):
        st.markdown("**Komposisi Sumber Harga**")
        src = lib.q(f"""select coalesce(f.sumber_harga,'(kosong)') sumber, count(*) n
                        from fact_harga f join dim_toko t on t.toko_id=f.toko_id
                        where {W} group by 1 order by n desc""", P)
        fig = px.bar(src, x="n", y="sumber", orientation="h", color_discrete_sequence=[lib.ORANGE])
        fig.update_layout(height=300, margin=dict(l=0, r=0, t=6, b=0), xaxis_title=None, yaxis_title=None)
        st.plotly_chart(fig, use_container_width=True)
