"""Halaman Iklan (sumber: fact_iklan). Auto-nyala saat bot Iklan kirim data."""

import plotly.express as px
import streamlit as st

import lib


def render():
    lib.header("📢 Performa Iklan", "ROAS, biaya & omzet iklan per toko · sumber: bot Iklan")

    if not lib.ada_data("fact_iklan"):
        lib.empty_state(
            "Data iklan belum masuk",
            "Akan muncul OTOMATIS saat bot Iklan menjalankan laporan (di JAM_LAPORAN). "
            "Sudah tersambung ke SQL lewat modules/sql_sink.py — tidak perlu setup lagi.")
        return

    f = lib.filter_bar("fact_iklan", "ik")
    if not f["toko"]:
        st.info("Pilih minimal satu toko di sidebar.")
        return
    if f["periode"] not in f["punya"]:
        lib.empty_state(f"Data iklan {f['periode']} belum ada",
                        "Tunggu bot Iklan / backfill iklan untuk granularitas ini.")
        return

    P = {"p": f["periode"], "a": f["a"], "b": f["b"], "toko": tuple(f["toko"])}
    W = "f.periode=:p and f.periode_mulai between :a and :b and t.nama in :toko"

    k = lib.q(f"""
        select coalesce(sum(f.omzet_iklan),0) omzet, coalesce(sum(f.biaya_iklan),0) biaya,
               coalesce(sum(f.dilihat),0) dilihat, coalesce(sum(f.klik),0) klik,
               coalesce(sum(f.konversi),0) konversi
        from fact_iklan f join dim_toko t on t.toko_id=f.toko_id where {W}
    """, P).iloc[0]
    roas = (k["omzet"] / k["biaya"]) if k["biaya"] else 0
    ctr = (k["klik"] / k["dilihat"] * 100) if k["dilihat"] else 0
    acos = (k["biaya"] / k["omzet"] * 100) if k["omzet"] else 0

    lib.kpi_row([
        {"ikon": "💵", "label": "Omzet Iklan", "nilai": lib.rp_ringkas(k["omzet"]),
         "sub": lib.rp(k["omzet"]), "sub_warna": "#999"},
        {"ikon": "💸", "label": "Biaya Iklan", "nilai": lib.rp_ringkas(k["biaya"]),
         "sub": lib.rp(k["biaya"]), "sub_warna": "#999"},
        {"ikon": "📈", "label": "ROAS", "nilai": f"{roas:.2f}", "sub": f"ACOS {acos:.0f}%",
         "sub_warna": lib.ORANGE if roas < 1 else lib.TEAL},
        {"ikon": "🖱️", "label": "Klik", "nilai": lib.num_ringkas(k["klik"]), "sub": f"CTR {ctr:.1f}%"},
        {"ikon": "🛒", "label": "Konversi", "nilai": lib.num_ringkas(k["konversi"])},
    ])

    st.write("")
    per = lib.q(f"""
        select t.nama toko, sum(f.omzet_iklan) omzet, sum(f.biaya_iklan) biaya,
               case when sum(f.biaya_iklan)>0 then sum(f.omzet_iklan)/sum(f.biaya_iklan) else 0 end roas
        from fact_iklan f join dim_toko t on t.toko_id=f.toko_id where {W}
        group by t.nama order by omzet desc nulls last
    """, P)
    a, b = st.columns(2)
    with a:
        with st.container(border=True):
            st.markdown("**💰 Omzet vs Biaya Iklan per Toko**")
            m = per.melt(id_vars="toko", value_vars=["omzet", "biaya"],
                         var_name="jenis", value_name="nilai")
            fig = px.bar(m, x="nilai", y="toko", color="jenis", orientation="h", barmode="group",
                         color_discrete_map={"omzet": lib.TEAL, "biaya": lib.ORANGE})
            fig.update_layout(height=360, margin=dict(l=0, r=0, t=6, b=0),
                              xaxis_title=None, yaxis_title=None, legend_title=None)
            st.plotly_chart(fig, use_container_width=True)
    with b:
        with st.container(border=True):
            st.markdown("**📈 ROAS per Toko**")
            fig = px.bar(per, x="roas", y="toko", orientation="h", text="roas",
                         color_discrete_sequence=[lib.ORANGE])
            fig.update_traces(texttemplate="%{x:.2f}", textposition="auto")
            fig.update_layout(yaxis={"categoryorder": "total ascending"}, height=360,
                              margin=dict(l=0, r=30, t=6, b=0), xaxis_title=None, yaxis_title=None)
            st.plotly_chart(fig, use_container_width=True)

    # ── Semua produk yang diiklankan ───────────────────────────────
    st.write("")
    st.markdown("##### 📋 Semua Produk Diiklankan")
    prod = lib.q(f"""
        select dp.nama_produk Produk, t.nama Toko,
               sum(f.dilihat) dilihat, sum(f.klik) klik, sum(f.konversi) konversi,
               sum(f.omzet_iklan) omzet, sum(f.biaya_iklan) biaya,
               case when sum(f.biaya_iklan)>0 then round(sum(f.omzet_iklan)/sum(f.biaya_iklan),2) else 0 end roas
        from fact_iklan f
        join dim_toko t on t.toko_id=f.toko_id
        join dim_produk dp on dp.produk_id=f.produk_id
        where {W}
        group by dp.nama_produk, t.nama order by biaya desc nulls last
    """, P)
    if prod.empty:
        st.info("Belum ada produk diiklankan di periode ini.")
    else:
        ctr = (prod["klik"] / prod["dilihat"].replace(0, 1) * 100).round(1)
        tampil = prod.copy()
        tampil["CTR"] = ctr.map(lambda x: f"{x}%")
        tampil["omzet"] = tampil["omzet"].map(lib.rp)
        tampil["biaya"] = tampil["biaya"].map(lib.rp)
        tampil = tampil.rename(columns={"produk": "Produk", "toko": "Toko",
                                        "dilihat": "Dilihat", "klik": "Klik", "konversi": "Konversi",
                                        "omzet": "Omzet Iklan", "biaya": "Biaya", "roas": "ROAS"})
        tampil = tampil[["Produk", "Toko", "Dilihat", "Klik", "CTR", "Konversi", "Omzet Iklan", "Biaya", "ROAS"]]
        st.caption(f"{len(tampil)} produk diiklankan · urut by biaya terbesar")
        st.dataframe(tampil, use_container_width=True, hide_index=True)
