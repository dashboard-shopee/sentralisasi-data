"""Halaman Ringkasan — overview periode terpilih + status koneksi tiap program."""

import plotly.express as px
import streamlit as st

import lib

SUMBER = [
    ("Penjualan Produk", "fact_penjualan", "📦", "produk performance"),
    ("Pesanan", "fact_pesanan", "🛒", "order per toko"),
    ("Iklan", "fact_iklan", "📢", "performa iklan"),
    ("Harga", "fact_harga", "🏷️", "bot Monitoring Harga"),
    ("Kompetitor", "fact_kompetitor", "🔍", "bot Riset Kompetitor"),
]


def render():
    lib.header("🛒 Dashboard Shopee Multi-Toko", "Pusat data 10 toko · sumber tunggal: Supabase (SQL)")

    # ── Status sumber data ─────────────────────────────────────────
    st.markdown("##### 🔌 Status Sumber Data")
    cols = st.columns(len(SUMBER))
    for col, (nama, tabel, ikon, asal) in zip(cols, SUMBER):
        n = lib.q(f"select count(*) c from {tabel}").iloc[0]["c"] if lib.ada_data(tabel) else 0
        status = ("<span class='badge-on'>● TERHUBUNG</span>" if n > 0
                  else "<span class='badge-off'>○ menunggu</span>")
        col.markdown(
            f"<div class='kpi'><div class='kpi-ikon'>{ikon}</div>"
            f"<div class='kpi-label'>{nama}</div>"
            f"<div class='kpi-nilai'>{lib.num_ringkas(n)}</div>"
            f"<div class='kpi-sub'>{status} · {asal}</div></div>",
            unsafe_allow_html=True)

    if not lib.ada_data("fact_penjualan"):
        return

    # ── Filter standar (granularitas + kalender + toko) ────────────
    f = lib.filter_bar("fact_penjualan", "rk")
    if not f["toko"]:
        st.info("Pilih minimal satu toko di sidebar.")
        return

    P = {"p": f["periode"], "a": f["a"], "b": f["b"], "toko": tuple(f["toko"])}
    W = "f.periode=:p and f.periode_mulai between :a and :b and t.nama in :toko"

    if f["periode"] not in f["punya"]:
        lib.empty_state(f"Data {f['periode']} belum ada",
                        "Backfill untuk granularitas ini belum dijalankan. Pilih granularitas lain dulu.")
        return

    st.write("")
    st.markdown(f"##### 📦 Sorotan Penjualan — {f['caption']}")
    k = lib.q(f"""
        select coalesce(sum(f.penjualan),0) omzet, coalesce(sum(f.unit_pesanan),0) unit,
               coalesce(sum(f.pengunjung),0) peng, count(distinct f.produk_id) produk
        from fact_penjualan f join dim_toko t on t.toko_id=f.toko_id where {W}
    """, P).iloc[0]
    cr = (k["unit"] / k["peng"] * 100) if k["peng"] else 0
    lib.kpi_row([
        {"ikon": "💰", "label": "Omzet", "nilai": lib.rp_ringkas(k["omzet"]),
         "sub": lib.rp(k["omzet"]), "sub_warna": "#999"},
        {"ikon": "📦", "label": "Unit Terjual", "nilai": lib.num_ringkas(k["unit"])},
        {"ikon": "👁️", "label": "Pengunjung", "nilai": lib.num_ringkas(k["peng"])},
        {"ikon": "🎯", "label": "Konversi", "nilai": f"{cr:.1f}%"},
        {"ikon": "🏷️", "label": "Produk Aktif", "nilai": lib.num_ringkas(k["produk"])},
    ])

    st.write("")
    per = lib.q(f"""select t.nama toko, sum(f.penjualan) omzet
                    from fact_penjualan f join dim_toko t on t.toko_id=f.toko_id
                    where {W} group by t.nama order by omzet desc nulls last""", P)
    a, b = st.columns([3, 2])
    with a:
        with st.container(border=True):
            st.markdown("**🏪 Omzet per Toko**")
            per["lbl"] = per["omzet"].map(lib.rp_ringkas)
            fig = px.bar(per, x="omzet", y="toko", orientation="h", text="lbl",
                         color_discrete_sequence=[lib.ORANGE])
            fig.update_traces(textposition="auto", cliponaxis=False)
            lib.style_fig(fig, 360)
            fig.update_layout(yaxis={"categoryorder": "total ascending"},
                              xaxis_title=None, yaxis_title=None)
            fig.update_xaxes(showgrid=True, gridcolor="#EFF1F5")
            fig.update_yaxes(showgrid=False)
            st.plotly_chart(fig, use_container_width=True)
    with b:
        with st.container(border=True):
            st.markdown("**🥧 Komposisi**")
            fig = px.pie(per, values="omzet", names="toko", hole=.55, color_discrete_sequence=lib.PALET)
            fig.update_traces(textposition="inside", textinfo="percent")
            fig.update_layout(height=360, margin=dict(l=0, r=0, t=6, b=30),
                              uniformtext_minsize=9, uniformtext_mode="hide",
                              legend=dict(orientation="h", y=-.12, font=dict(size=9)))
            st.plotly_chart(fig, use_container_width=True)

    st.caption("Ganti periode/waktu di sidebar. Buka **Analisa** untuk bandingkan penjualan vs iklan.")
