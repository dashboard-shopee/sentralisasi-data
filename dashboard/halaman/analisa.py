"""
Halaman Analisa — bandingkan Penjualan vs Iklan dalam satu grafik.

Time picker ala Shopee: pilih granularitas (harian/mingguan/bulanan/tahunan),
lalu pilih rentang "Dari–Sampai" (default ke periode TERBARU). Pilih variabel
lewat pop-up. Grafik: metrik Rupiah/jumlah = BATANG (sumbu kiri),
rasio (ROAS/CTR/%) = GARIS (sumbu kanan).
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

import lib

# key -> (label, kolom_df, sumbu, warna)
METRIK = {
    "omzet":       ("💰 Omzet Penjualan", "omzet", "kiri", "#EE4D2D"),
    "unit":        ("📦 Unit Terjual", "unit", "kiri", "#FF8A65"),
    "pengunjung":  ("👁️ Pengunjung", "pengunjung", "kiri", "#FFB74D"),
    "omzet_iklan": ("💵 Omzet dari Iklan", "omzet_iklan", "kiri", "#26A69A"),
    "biaya_iklan": ("💸 Biaya Iklan", "biaya_iklan", "kiri", "#EC407A"),
    "dilihat":     ("📺 Iklan Dilihat", "dilihat", "kiri", "#42A5F5"),
    "klik":        ("🖱️ Klik Iklan", "klik", "kiri", "#7E57C2"),
    "konversi":    ("🛒 Konversi Iklan", "konversi", "kiri", "#8D6E63"),
    "roas":        ("📈 ROAS", "roas", "kanan", "#D81B60"),
    "ctr":         ("🎯 CTR (%)", "ctr", "kanan", "#1E88E5"),
    "acos":        ("💹 ACOS (%)", "acos", "kanan", "#8E24AA"),
    "cr_jual":     ("✅ Konversi Penjualan (%)", "cr_jual", "kanan", "#43A047"),
}
GRUP = {
    "📦 Penjualan": ["omzet", "unit", "pengunjung", "cr_jual"],
    "📢 Iklan": ["biaya_iklan", "omzet_iklan", "dilihat", "klik", "konversi"],
    "⚡ Rasio / Efisiensi": ["roas", "ctr", "acos"],
}
DEFAULT = ["omzet", "biaya_iklan", "roas"]
JENDELA = {"harian": 14, "mingguan": 12, "bulanan": 12, "tahunan": 6}  # default lebar window


def _ambil_seri(periode, a, b, toko):
    args = {"p": periode, "a": a, "b": b, "toko": tuple(toko)}
    pj = lib.q("""
        select f.periode_mulai waktu, sum(f.penjualan) omzet, sum(f.unit_pesanan) unit,
               sum(f.pengunjung) pengunjung, sum(f.keranjang) keranjang
        from fact_penjualan f join dim_toko t on t.toko_id=f.toko_id
        where f.periode=:p and f.periode_mulai between :a and :b and t.nama in :toko
        group by f.periode_mulai
    """, args)
    ik = lib.q("""
        select f.periode_mulai waktu, sum(f.omzet_iklan) omzet_iklan, sum(f.biaya_iklan) biaya_iklan,
               sum(f.dilihat) dilihat, sum(f.klik) klik, sum(f.konversi) konversi
        from fact_iklan f join dim_toko t on t.toko_id=f.toko_id
        where f.periode=:p and f.periode_mulai between :a and :b and t.nama in :toko
        group by f.periode_mulai
    """, args)
    df = pd.merge(pj, ik, on="waktu", how="outer").sort_values("waktu")
    if df.empty:
        return df
    for c in ["omzet", "unit", "pengunjung", "keranjang", "omzet_iklan",
              "biaya_iklan", "dilihat", "klik", "konversi"]:
        df[c] = pd.to_numeric(df.get(c), errors="coerce").fillna(0)
    df["roas"] = df.apply(lambda r: r.omzet_iklan / r.biaya_iklan if r.biaya_iklan else 0, axis=1)
    df["ctr"] = df.apply(lambda r: r.klik / r.dilihat * 100 if r.dilihat else 0, axis=1)
    df["acos"] = df.apply(lambda r: r.biaya_iklan / r.omzet_iklan * 100 if r.omzet_iklan else 0, axis=1)
    df["cr_jual"] = df.apply(lambda r: r.unit / r.pengunjung * 100 if r.pengunjung else 0, axis=1)
    df["label"] = df["waktu"].apply(lambda d: lib.label_periode(periode, d))
    return df


def render():
    lib.header("📊 Analisa Penjualan vs Iklan",
               "Bandingkan omzet & pengeluaran iklan · pilih variabel & rentang sesukamu")
    if not lib.ada_data("fact_penjualan"):
        lib.empty_state("Belum ada data", "Jalankan backfill dulu.")
        return

    # ── Filter standar (granularitas + kalender + toko) ────────────
    f = lib.filter_bar("fact_penjualan", "an", mode="trend")
    if not f["toko"]:
        st.info("Pilih minimal satu toko.")
        return
    if f["periode"] not in f["punya"]:
        lib.empty_state(f"Data {f['periode']} belum ada",
                        "Backfill granularitas ini belum jalan. Pilih granularitas lain.")
        return
    periode, a, b, toko = f["periode"], f["a"], f["b"], f["toko"]

    # ── Pemilih variabel (pop-up) ──────────────────────────────────
    top = st.columns([3, 1])
    top[0].markdown(f"**Periode:** {f['caption']}  ·  {len(toko)} toko")
    with top[1].popover("⚙️ Pilih Variabel", use_container_width=True):
        st.caption("Centang yang mau ditampilkan:")
        pilih = []
        for grup, keys in GRUP.items():
            st.markdown(f"**{grup}**")
            for k in keys:
                if st.checkbox(METRIK[k][0], value=(k in DEFAULT), key=f"chk_{k}"):
                    pilih.append(k)
    if not pilih:
        st.warning("Pilih minimal satu variabel di tombol ⚙️ Pilih Variabel.")
        return

    df = _ambil_seri(periode, a, b, toko)
    if df.empty:
        lib.empty_state("Tidak ada data di rentang ini", "Lebarkan rentang atau ganti granularitas.")
        return

    # ── KPI ringkas ────────────────────────────────────────────────
    t_omzet, t_biaya = df["omzet"].sum(), df["biaya_iklan"].sum()
    t_oik, t_unit = df["omzet_iklan"].sum(), df["unit"].sum()
    roas_all = (t_oik / t_biaya) if t_biaya else 0
    acos_all = (t_biaya / t_omzet * 100) if t_omzet else 0
    lib.kpi_row([
        {"ikon": "💰", "label": "Total Omzet", "nilai": lib.rp_ringkas(t_omzet),
         "sub": lib.rp(t_omzet), "sub_warna": "#999"},
        {"ikon": "💸", "label": "Biaya Iklan", "nilai": lib.rp_ringkas(t_biaya),
         "sub": lib.rp(t_biaya), "sub_warna": "#999"},
        {"ikon": "💵", "label": "Omzet dari Iklan", "nilai": lib.rp_ringkas(t_oik)},
        {"ikon": "📈", "label": "ROAS", "nilai": f"{roas_all:.2f}", "sub": f"ACOS {acos_all:.1f}%",
         "sub_warna": lib.ORANGE if roas_all < 1 else lib.TEAL},
        {"ikon": "📦", "label": "Unit Terjual", "nilai": lib.num_ringkas(t_unit)},
    ])

    if t_biaya == 0 and any(METRIK[k][2] == "kanan" or k in ("biaya_iklan", "omzet_iklan", "dilihat", "klik", "konversi") for k in pilih):
        st.info("ℹ️ Data **iklan** belum ada di SQL — garis/batang iklan masih 0. "
                "Akan terisi setelah backfill iklan dijalankan.")

    # ── Grafik: batang (Rp/jumlah) + garis (rasio) ────────────────
    st.write("")
    with st.container(border=True):
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        ada_kanan = False
        for k in pilih:
            label, kol, sumbu, warna = METRIK[k]
            if sumbu == "kiri":
                fig.add_trace(go.Bar(x=df["label"], y=df[kol], name=label,
                                     marker_color=warna, opacity=.9), secondary_y=False)
            else:
                ada_kanan = True
                fig.add_trace(go.Scatter(x=df["label"], y=df[kol], name=label, mode="lines+markers",
                                         line=dict(color=warna, width=3.5),
                                         marker=dict(size=7)), secondary_y=True)
        lib.style_fig(fig, 460)
        fig.update_layout(barmode="group", bargap=.28, hovermode="x unified")
        fig.update_yaxes(title_text="Rp / Jumlah", secondary_y=False, rangemode="tozero")
        if ada_kanan:
            # ROAS/% tidak mungkin < 0 -> sumbu kanan mulai dari 0.
            fig.update_yaxes(title_text="Rasio (ROAS / %)", secondary_y=True,
                             showgrid=False, rangemode="tozero")
        st.plotly_chart(fig, use_container_width=True)

    with st.expander("📋 Lihat tabel data"):
        tampil = df[["label"] + [METRIK[k][1] for k in pilih]].copy()
        tampil.columns = ["Periode"] + [METRIK[k][0] for k in pilih]
        st.dataframe(tampil, use_container_width=True, hide_index=True)
