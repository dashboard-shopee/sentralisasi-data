"""Halaman Pesanan — order unik per toko (fact_pesanan) + pesanan per produk (fact_penjualan.pesanan)."""

import plotly.express as px
import streamlit as st

import lib


def render():
    lib.header("🛒 Pesanan", "Jumlah ORDER (bukan unit) per toko & per produk")

    if not lib.ada_data("fact_penjualan"):
        lib.empty_state("Belum ada data", "Jalankan backfill dulu.")
        return

    f = lib.filter_bar("fact_penjualan", "ps")
    if not f["toko"]:
        st.info("Pilih minimal satu toko di sidebar.")
        return
    if f["periode"] not in f["punya"]:
        lib.empty_state(f"Data {f['periode']} belum ada", "Pilih granularitas lain.")
        return

    P = {"p": f["periode"], "a": f["a"], "b": f["b"], "toko": tuple(f["toko"])}
    Wp = "f.periode=:p and f.periode_mulai between :a and :b and t.nama in :toko"

    # ── Pesanan per TOKO (order unik, dari fact_pesanan) ───────────
    st.markdown(f"##### 🏪 Pesanan per Toko (order unik) — {f['caption']}")
    per_toko = lib.q(f"""
        select t.nama toko, coalesce(sum(f.jumlah_pesanan),0) pesanan,
               coalesce(sum(f.pesanan_batal),0) batal, coalesce(sum(f.omzet_pesanan),0) omzet
        from fact_pesanan f join dim_toko t on t.toko_id=f.toko_id
        where {Wp} group by t.nama order by pesanan desc
    """, P)

    if per_toko.empty or per_toko["pesanan"].sum() == 0:
        st.info("ℹ️ Pesanan per-toko (order unik) hanya tersedia **~30 hari terakhir** "
                "(batasan Shopee). Pilih periode harian/mingguan terbaru untuk melihatnya. "
                "Pesanan **per produk** di bawah tersedia full history.")
    else:
        tp = int(per_toko["pesanan"].sum()); tb = int(per_toko["batal"].sum())
        tomz = float(per_toko["omzet"].sum())
        avg = (tomz / tp) if tp else 0
        rate_batal = (tb / (tp + tb) * 100) if (tp + tb) else 0
        lib.kpi_row([
            {"ikon": "🛒", "label": "Total Pesanan", "nilai": lib.num_ringkas(tp)},
            {"ikon": "💰", "label": "Omzet Pesanan", "nilai": lib.rp_ringkas(tomz), "sub": lib.rp(tomz), "sub_warna": "#999"},
            {"ikon": "🧾", "label": "Rata2 / Pesanan", "nilai": lib.rp_ringkas(avg)},
            {"ikon": "❌", "label": "Pesanan Batal", "nilai": lib.num_ringkas(tb), "sub": f"{rate_batal:.1f}% dari total", "sub_warna": lib.ORANGE},
        ])
        st.write("")
        with st.container(border=True):
            st.markdown("**Pesanan per Toko**")
            per_toko["lbl"] = per_toko["pesanan"].map(lambda x: lib.num_ringkas(x))
            fig = px.bar(per_toko, x="pesanan", y="toko", orientation="h", text="lbl",
                         color_discrete_sequence=[lib.ORANGE])
            fig.update_traces(textposition="auto", cliponaxis=False)
            lib.style_fig(fig, 340)
            fig.update_layout(yaxis={"categoryorder": "total ascending"}, xaxis_title=None, yaxis_title=None)
            fig.update_xaxes(showgrid=True, gridcolor="#EFF1F5"); fig.update_yaxes(showgrid=False)
            st.plotly_chart(fig, use_container_width=True)

    # ── Pesanan per PRODUK (dari fact_penjualan.pesanan) ───────────
    st.write("")
    st.markdown("##### 📦 Pesanan per Produk (order vs unit)")
    st.caption("‘Pesanan’ = jumlah order; ‘Unit’ = pcs terjual. 1 order bisa beli banyak unit.")
    top = lib.q(f"""
        select dp.nama_produk Produk, t.nama Toko,
               sum(f.pesanan) pesanan, sum(f.unit_pesanan) unit, sum(f.penjualan) omzet
        from fact_penjualan f
        join dim_toko t on t.toko_id=f.toko_id
        join dim_produk dp on dp.produk_id=f.produk_id
        where {Wp} and f.pesanan is not null
        group by dp.nama_produk, t.nama order by pesanan desc nulls last limit 20
    """, P)
    if top.empty:
        st.info("Belum ada data pesanan per produk di periode ini.")
        return
    top["unit/pesanan"] = (top["unit"] / top["pesanan"].replace(0, 1)).round(1)
    top["omzet"] = top["omzet"].map(lib.rp)
    top = top.rename(columns={"produk": "Produk", "toko": "Toko", "pesanan": "Pesanan",
                              "unit": "Unit", "omzet": "Omzet", "unit/pesanan": "Pcs/Order"})
    with st.container(border=True):
        st.markdown("**🏆 Top 20 Produk by Jumlah Pesanan**")
        st.dataframe(top, use_container_width=True, hide_index=True)
