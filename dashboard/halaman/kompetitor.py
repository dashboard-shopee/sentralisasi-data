"""Halaman Kompetitor (sumber: fact_kompetitor). Auto-nyala saat program Riset Kompetitor jalan."""

import streamlit as st

import lib


def render():
    lib.header("🔍 Riset Kompetitor", "Produk serupa pesaing per market · sumber: bot Riset Kompetitor")

    if not lib.ada_data("fact_kompetitor"):
        lib.empty_state(
            "Data kompetitor belum masuk",
            "Akan muncul OTOMATIS setelah program 'Otomatisasi Riset Kompetitor' "
            "disambungkan ke SQL (Bagian D). Tabel fact_kompetitor sudah siap menampung.")
        return

    semua_market = lib.q("select distinct market from fact_kompetitor where market is not null order by 1")["market"].tolist()
    with st.sidebar:
        st.subheader("Filter")
        market = st.multiselect("Market", semua_market, default=semua_market, key="kp_market")
    if not market:
        st.info("Pilih minimal satu market.")
        return

    P = {"m": tuple(market)}
    k = lib.q("""select count(*) n, count(distinct toko_pesaing) toko, avg(harga) avg_harga
                 from fact_kompetitor where market in :m""", P).iloc[0]
    c = st.columns(3)
    lib.kpi(c[0], "🔍", "Produk Pesaing", lib.num_ringkas(k["n"]))
    lib.kpi(c[1], "🏪", "Toko Pesaing", lib.num_ringkas(k["toko"]))
    lib.kpi(c[2], "💲", "Harga Rata2", lib.rp_ringkas(k["avg_harga"]))

    st.write("")
    with st.container(border=True):
        st.markdown("**Daftar Produk Pesaing (terbaru)**")
        df = lib.q("""select market, toko_pesaing as toko, nama_produk as produk, harga, terjual, rating
                      from fact_kompetitor where market in :m order by diambil_pada desc limit 200""", P)
        st.dataframe(df, use_container_width=True, hide_index=True)
