"""Halaman Penjualan Produk (sumber: fact_penjualan)."""

import plotly.express as px
import streamlit as st

import lib


def render():
    lib.header("📦 Penjualan Produk", "Performa produk per toko · sumber: bot Iklan + backfill historis")

    if not lib.ada_data("fact_penjualan"):
        lib.empty_state("Belum ada data penjualan",
                        "Jalankan backfill atau tunggu bot Iklan mengirim laporan.")
        return

    f = lib.filter_bar("fact_penjualan", "pj")
    if not f["toko"]:
        st.info("Pilih minimal satu toko di sidebar.")
        return
    if f["periode"] not in f["punya"]:
        lib.empty_state(f"Data {f['periode']} belum ada",
                        "Backfill untuk granularitas ini belum dijalankan.")
        return

    P = {"p": f["periode"], "a": f["a"], "b": f["b"], "toko": tuple(f["toko"])}
    W = "f.periode=:p and f.periode_mulai between :a and :b and t.nama in :toko"

    # ── KPI ────────────────────────────────────────────────────────
    k = lib.q(f"""
        select coalesce(sum(f.penjualan),0) omzet, coalesce(sum(f.unit_pesanan),0) unit,
               coalesce(sum(f.pengunjung),0) peng, coalesce(sum(f.keranjang),0) ker,
               count(distinct f.produk_id) produk
        from fact_penjualan f join dim_toko t on t.toko_id=f.toko_id where {W}
    """, P).iloc[0]
    cr = (k["unit"] / k["peng"] * 100) if k["peng"] else 0
    atc = (k["ker"] / k["peng"] * 100) if k["peng"] else 0

    lib.kpi_row([
        {"ikon": "💰", "label": "Omzet", "nilai": lib.rp_ringkas(k["omzet"]),
         "sub": lib.rp(k["omzet"]), "sub_warna": "#999"},
        {"ikon": "📦", "label": "Unit Terjual", "nilai": lib.num_ringkas(k["unit"])},
        {"ikon": "👁️", "label": "Pengunjung", "nilai": lib.num_ringkas(k["peng"])},
        {"ikon": "🎯", "label": "Konversi", "nilai": f"{cr:.1f}%", "sub": f"add-to-cart {atc:.0f}%"},
        {"ikon": "🏷️", "label": "Produk Aktif", "nilai": lib.num_ringkas(k["produk"])},
    ])

    st.write("")

    # ── Tren historis (semua periode dari jenis terpilih) ──────────
    tren = lib.q(f"""
        select f.periode_mulai waktu, sum(f.penjualan) omzet, sum(f.unit_pesanan) unit
        from fact_penjualan f join dim_toko t on t.toko_id=f.toko_id
        where {W}
        group by f.periode_mulai order by f.periode_mulai
    """, P)
    if len(tren) > 1:
        with st.container(border=True):
            st.markdown(f"**📈 Tren Omzet ({f['periode']})**")
            fig = px.area(tren, x="waktu", y="omzet", color_discrete_sequence=[lib.ORANGE])
            fig.update_traces(line_color=lib.ORANGE, fillcolor="rgba(238,77,45,.12)")
            fig.update_layout(height=260, margin=dict(l=0, r=0, t=6, b=0),
                              xaxis_title=None, yaxis_title=None)
            st.plotly_chart(fig, use_container_width=True)

    # ── Per toko: bar + donut ──────────────────────────────────────
    per_toko = lib.q(f"""
        select t.nama toko, sum(f.penjualan) omzet, sum(f.unit_pesanan) unit, sum(f.pengunjung) peng
        from fact_penjualan f join dim_toko t on t.toko_id=f.toko_id where {W}
        group by t.nama order by omzet desc nulls last
    """, P)

    a, b = st.columns([3, 2])
    with a:
        with st.container(border=True):
            st.markdown("**🏪 Omzet per Toko**")
            pt = per_toko.copy()
            pt["lbl"] = pt["omzet"].map(lib.rp_ringkas)
            fig = px.bar(pt, x="omzet", y="toko", orientation="h", text="lbl",
                         color_discrete_sequence=[lib.ORANGE])
            fig.update_traces(textposition="auto", cliponaxis=False)
            fig.update_layout(yaxis={"categoryorder": "total ascending"}, height=360,
                              margin=dict(l=0, r=50, t=6, b=0), xaxis_title=None, yaxis_title=None)
            st.plotly_chart(fig, use_container_width=True)
    with b:
        with st.container(border=True):
            st.markdown("**🥧 Komposisi Omzet**")
            fig = px.pie(per_toko, values="omzet", names="toko", hole=.55,
                         color_discrete_sequence=lib.PALET)
            fig.update_traces(textposition="inside", textinfo="percent")
            fig.update_layout(height=360, margin=dict(l=0, r=0, t=6, b=30),
                              uniformtext_minsize=9, uniformtext_mode="hide",
                              legend=dict(orientation="h", y=-.12, font=dict(size=9)))
            st.plotly_chart(fig, use_container_width=True)

    # ── Tabel ──────────────────────────────────────────────────────
    a, b = st.columns(2)
    with a:
        with st.container(border=True):
            st.markdown("**🏆 Top 15 Produk**")
            top = lib.q(f"""
                select dp.nama_produk Produk, t.nama Toko, f.penjualan omzet, f.unit_pesanan Unit
                from fact_penjualan f join dim_toko t on t.toko_id=f.toko_id
                join dim_produk dp on dp.produk_id=f.produk_id
                where {W} and f.penjualan is not null order by f.penjualan desc limit 15
            """, P)
            top["omzet"] = top["omzet"].map(lib.rp)
            top = top.rename(columns={"omzet": "Omzet"})
            st.dataframe(top, use_container_width=True, hide_index=True)
    with b:
        with st.container(border=True):
            st.markdown("**📊 Ringkasan per Toko**")
            tk = per_toko.copy()
            tk["omzet"] = tk["omzet"].map(lib.rp)
            tk.columns = ["Toko", "Omzet", "Unit", "Pengunjung"]
            st.dataframe(tk, use_container_width=True, hide_index=True)
