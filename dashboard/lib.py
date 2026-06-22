"""
dashboard/lib.py — fondasi bersama semua halaman dashboard.

Berisi: koneksi DB (cached), helper query, formatter angka, CSS global,
komponen UI (kartu KPI, header, empty-state), dan filter periode reusable.
Halaman di folder halaman/ tinggal pakai fungsi-fungsi di sini.
"""

import calendar
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st
from sqlalchemy import bindparam, text

from config.db import get_engine

# ── Palet (tema Shopee) ─────────────────────────────────────────────
ORANGE = "#EE4D2D"
TEAL = "#26A69A"
WIB = timezone(timedelta(hours=7))
GRANS = ["harian", "mingguan", "bulanan", "tahunan"]
GRAN_LABEL = {"harian": "Per Hari", "mingguan": "Per Minggu",
              "bulanan": "Per Bulan", "tahunan": "Per Tahun"}
PALET = ["#EE4D2D", "#FF8A65", "#FFB74D", "#26A69A", "#42A5F5", "#7E57C2",
         "#EC407A", "#66BB6A", "#FFA726", "#8D6E63"]


# ── DB ──────────────────────────────────────────────────────────────
@st.cache_resource
def engine():
    return get_engine()


@st.cache_data(ttl=180)
def q(sql: str, params: dict | None = None) -> pd.DataFrame:
    params = params or {}
    stmt = text(sql)
    exp = [bindparam(k, expanding=True) for k, v in params.items() if isinstance(v, (tuple, list))]
    if exp:
        stmt = stmt.bindparams(*exp)
    with engine().connect() as c:
        return pd.read_sql(stmt, c, params=params)


def ada_data(tabel: str) -> bool:
    """True kalau tabel fakta punya minimal 1 baris (untuk auto-nyala halaman)."""
    try:
        return bool(q(f"select exists(select 1 from {tabel}) ada").iloc[0]["ada"])
    except Exception:
        return False


# ── Formatter ───────────────────────────────────────────────────────
def rp(x) -> str:
    try:
        return "Rp" + f"{float(x):,.0f}".replace(",", ".")
    except (TypeError, ValueError):
        return "Rp0"


def rp_ringkas(x) -> str:
    v = float(x or 0)
    if v >= 1e9:
        return f"Rp{v/1e9:.1f} M".replace(".", ",")
    if v >= 1e6:
        return f"Rp{v/1e6:.1f} jt".replace(".", ",")
    if v >= 1e3:
        return f"Rp{v/1e3:.0f} rb"
    return f"Rp{v:.0f}"


def num_ringkas(x) -> str:
    v = float(x or 0)
    if v >= 1e6:
        return f"{v/1e6:.1f} jt".replace(".", ",")
    if v >= 1e3:
        return f"{v/1e3:.1f} rb".replace(".", ",")
    return f"{int(v)}"


_BULAN_ID = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "Mei", 6: "Jun",
             7: "Jul", 8: "Agu", 9: "Sep", 10: "Okt", 11: "Nov", 12: "Des"}


def _tgl_id(d) -> str:
    return f"{d.day:02d} {_BULAN_ID[d.month]} {d.year}"


def label_periode(periode: str, dt) -> str:
    d = pd.to_datetime(dt)
    # periode_mulai disimpan UTC -> tampilkan dalam WIB biar tanggalnya benar.
    if d.tzinfo is not None:
        d = d.tz_convert("Asia/Jakarta")
    if periode == "tahunan":
        return str(d.year)
    if periode == "bulanan":
        return f"{_BULAN_ID[d.month]} {d.year}"
    if periode == "mingguan":
        return f"{d.day:02d}–{_tgl_id(d + timedelta(days=6))}"
    return _tgl_id(d)


# ── CSS global ──────────────────────────────────────────────────────
def inject_css():
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
        html, body, [class*="css"] {{ font-family: 'Inter', system-ui, sans-serif; }}
        .stApp {{ background: #F4F5F9; }}
        #MainMenu, footer, header[data-testid="stHeader"] {{ display: none; }}
        .block-container {{ padding-top: 1.4rem; padding-bottom: 2rem; max-width: 1320px; }}

        /* Sidebar bersih */
        section[data-testid="stSidebar"] {{ background:#fff; border-right:1px solid #ECEEF3; }}
        section[data-testid="stSidebar"] .block-container {{ padding-top: 1.2rem; }}

        /* Header card */
        .judul-bar {{
            display:flex; align-items:center; gap:14px; background:#fff;
            padding:18px 22px; border-radius:22px; margin-bottom:20px;
            box-shadow:0 6px 24px rgba(20,23,40,.05);
        }}
        .judul-ikon {{
            width:48px; height:48px; border-radius:14px; flex:0 0 48px;
            display:flex; align-items:center; justify-content:center; font-size:24px;
            background:linear-gradient(135deg,{ORANGE},#FF8A65); color:#fff;
        }}
        .judul-bar h1 {{ margin:0; font-size:1.4rem; font-weight:800; color:#16181F; }}
        .judul-bar p {{ margin:2px 0 0; color:#9AA0AB; font-size:.84rem; }}

        /* Baris KPI: flex wrap -> turun baris otomatis kalau sempit */
        .kpi-grid {{ display:flex; flex-wrap:wrap; gap:12px; margin-bottom:8px; }}
        .kpi-grid .kpi {{ flex:1 1 150px; }}
        /* Kartu KPI */
        .kpi {{
            background:#fff; border:none; border-radius:18px; padding:16px 16px;
            box-shadow:0 6px 22px rgba(20,23,40,.05); overflow:hidden;
        }}
        .kpi-ikon {{
            width:34px; height:34px; border-radius:10px; display:flex; align-items:center;
            justify-content:center; font-size:16px; background:#F4F5F9; margin-bottom:9px;
        }}
        .kpi-label {{ color:#9AA0AB; font-size:.74rem; font-weight:600; white-space:nowrap;
            overflow:hidden; text-overflow:ellipsis; }}
        .kpi-nilai {{ color:#16181F; font-size:1.3rem; font-weight:800; line-height:1.2;
            letter-spacing:-.3px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
        .kpi-sub {{ font-size:.72rem; margin-top:3px; font-weight:600; white-space:nowrap;
            overflow:hidden; text-overflow:ellipsis; }}
        .badge-on {{ color:{TEAL}; font-weight:700; }}
        .badge-off {{ color:#C2C6CE; font-weight:700; }}

        /* Container 'border=True' jadi kartu lembut */
        div[data-testid="stVerticalBlockBorderWrapper"] {{
            background:#fff; border:none !important; border-radius:20px;
            box-shadow:0 6px 22px rgba(20,23,40,.05); padding:6px 4px;
        }}
        /* Tabel & expander */
        div[data-testid="stExpander"] {{ border:none; border-radius:16px; box-shadow:0 4px 16px rgba(20,23,40,.04); }}
        h5 {{ color:#16181F; font-weight:700; }}

        /* Grid kalender di sidebar: rapatkan kolom + tombol kompak biar angka muat */
        section[data-testid="stSidebar"] div[data-testid="stHorizontalBlock"] {{ gap:.18rem; }}
        section[data-testid="stSidebar"] .stButton button {{
            padding:2px 0; min-height:32px; border-radius:8px; line-height:1;
        }}
        section[data-testid="stSidebar"] .stButton button p {{
            font-size:.74rem; white-space:nowrap; font-weight:600;
        }}
        section[data-testid="stSidebar"] .stButton button div {{ overflow:visible; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


# ── Komponen UI ─────────────────────────────────────────────────────
def header(judul: str, sub: str = ""):
    # Ambil emoji depan judul (kalau ada) jadi ikon chip.
    parts = judul.split(" ", 1)
    if len(parts) == 2 and not parts[0].isascii():
        ikon, judul = parts[0], parts[1]
    else:
        ikon = "🛒"
    st.markdown(
        f"<div class='judul-bar'><div class='judul-ikon'>{ikon}</div>"
        f"<div><h1>{judul}</h1><p>{sub}</p></div></div>",
        unsafe_allow_html=True,
    )


def style_fig(fig, height: int = 360, rounded: bool = True):
    """Tema grafik konsisten (gaya fintech: bersih, bar rounded, grid tipis)."""
    fig.update_layout(
        height=height, margin=dict(l=4, r=4, t=10, b=4),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, system-ui, sans-serif", size=12, color="#16181F"),
        legend=dict(orientation="h", y=-.2, x=0, font=dict(size=11)),
        hoverlabel=dict(bgcolor="white", font_size=12, bordercolor="#ECEEF3"),
    )
    if rounded:
        fig.update_layout(barcornerradius=7)
    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(showgrid=True, gridcolor="#EFF1F5", zeroline=False)
    return fig


def kpi(col, ikon: str, label: str, nilai: str, sub: str = "", sub_warna: str = TEAL):
    sub_html = f"<div class='kpi-sub' style='color:{sub_warna}'>{sub}</div>" if sub else ""
    col.markdown(
        f"<div class='kpi'><div class='kpi-ikon'>{ikon}</div>"
        f"<div class='kpi-label'>{label}</div>"
        f"<div class='kpi-nilai'>{nilai}</div>{sub_html}</div>",
        unsafe_allow_html=True,
    )


def kpi_row(cards: list):
    """Render beberapa KPI dalam 1 grid responsif (wrap otomatis, anti-kepotong).
    cards: list dict {ikon, label, nilai, sub?, sub_warna?}."""
    html = "<div class='kpi-grid'>"
    for c in cards:
        sub = (f"<div class='kpi-sub' style='color:{c.get('sub_warna', TEAL)}'>{c['sub']}</div>"
               if c.get("sub") else "")
        html += (f"<div class='kpi'><div class='kpi-ikon'>{c['ikon']}</div>"
                 f"<div class='kpi-label'>{c['label']}</div>"
                 f"<div class='kpi-nilai'>{c['nilai']}</div>{sub}</div>")
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def empty_state(judul: str, pesan: str):
    st.markdown(
        f"<div style='text-align:center;padding:70px 20px;color:#aaa'>"
        f"<div style='font-size:48px'>📭</div>"
        f"<h3 style='color:#888'>{judul}</h3><p>{pesan}</p></div>",
        unsafe_allow_html=True,
    )


def daftar_toko() -> list:
    return q("select nama from dim_toko order by shop_index")["nama"].tolist()


def _senin(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _pair(v):
    if isinstance(v, (list, tuple)):
        if len(v) == 2:
            return v[0], v[1]
        if len(v) == 1:
            return v[0], v[0]
    return v, v


def _wib_mid(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, tzinfo=WIB)


def _mundur_bulan(d: date, n: int) -> date:
    y, m = d.year, d.month - n
    while m <= 0:
        m += 12
        y -= 1
    return date(y, m, 1)


def _grid_bulan(key: str, mx: date):
    """Grid bulan klik (Jan..Des) + navigasi tahun. Return (date,date) bulan terpilih."""
    nk, sk = f"{key}_navy", f"{key}_selb"
    if nk not in st.session_state:
        st.session_state[nk] = mx.year
    if sk not in st.session_state:
        st.session_state[sk] = (mx.year, mx.month)
    c1, c2, c3 = st.columns([1, 2, 1])
    y = st.session_state[nk]
    if c1.button("‹", key=f"{key}_yp", use_container_width=True):
        y -= 1
    if c3.button("›", key=f"{key}_yn", use_container_width=True):
        y += 1
    st.session_state[nk] = y
    c2.markdown(f"<div style='text-align:center;font-weight:700;padding-top:5px'>{y}</div>",
                unsafe_allow_html=True)
    klik = None
    for r in range(4):
        cols = st.columns(3)
        for i in range(3):
            m = r * 3 + i + 1
            sel = st.session_state[sk] == (y, m)
            if cols[i].button(_BULAN_ID[m], key=f"{key}_m{m}",
                              type="primary" if sel else "secondary", use_container_width=True):
                klik = (y, m)
    if klik:
        st.session_state[sk] = klik
        st.rerun()
    yy, mm = st.session_state[sk]
    return date(yy, mm, 1), date(yy, mm, 1)


def _grid_tahun(key: str, mx: date):
    """Grid tahun klik. Return (date,date) 1 Jan tahun terpilih."""
    sk = f"{key}_selt"
    if sk not in st.session_state:
        st.session_state[sk] = mx.year
    tahun = list(range(2025, max(2028, mx.year + 1) + 1))
    klik = None
    for r in range(0, len(tahun), 3):
        cols = st.columns(3)
        for i, yy in enumerate(tahun[r:r + 3]):
            sel = st.session_state[sk] == yy
            if cols[i].button(str(yy), key=f"{key}_t{yy}",
                              type="primary" if sel else "secondary", use_container_width=True):
                klik = yy
    if klik:
        st.session_state[sk] = klik
        st.rerun()
    y = st.session_state[sk]
    return date(y, 1, 1), date(y, 1, 1)


def _grid_hari(key: str, mx: date, minggu: bool = False):
    """Grid hari klik (Senin-pertama) + nav bulan. minggu=True -> klik hari pilih
    1 minggu Senin→Minggu. Return (date,date)."""
    nk, sk = f"{key}_navhm", f"{key}_seld"
    if nk not in st.session_state:
        st.session_state[nk] = (mx.year, mx.month)
    if sk not in st.session_state:
        st.session_state[sk] = mx
    ny, nm = st.session_state[nk]
    c1, c2, c3 = st.columns([1, 3, 1])
    if c1.button("‹", key=f"{key}_mp", use_container_width=True):
        nm -= 1
        if nm < 1:
            nm = 12; ny -= 1
    if c3.button("›", key=f"{key}_mn", use_container_width=True):
        nm += 1
        if nm > 12:
            nm = 1; ny += 1
    st.session_state[nk] = (ny, nm)
    c2.markdown(f"<div style='text-align:center;font-weight:700;padding-top:5px'>{_BULAN_ID[nm]} {ny}</div>",
                unsafe_allow_html=True)
    hdr = st.columns(7)
    for i, d in enumerate(["Sn", "Sl", "Rb", "Km", "Jm", "Sb", "Mg"]):
        warna = "#EE4D2D" if i == 6 else "#9AA0AB"
        hdr[i].markdown(f"<div style='text-align:center;color:{warna};font-size:.68rem;font-weight:600'>{d}</div>",
                        unsafe_allow_html=True)
    klik = None
    for week in calendar.Calendar(firstweekday=0).monthdatescalendar(ny, nm):
        cols = st.columns(7)
        for i, d in enumerate(week):
            if d.month != nm:
                cols[i].markdown(f"<div style='text-align:center;color:#D5D8DE;font-size:.74rem;padding:7px 0'>{d.day}</div>",
                                 unsafe_allow_html=True)
                continue
            sel = (_senin(st.session_state[sk]) == _senin(d)) if minggu else (st.session_state[sk] == d)
            if cols[i].button(str(d.day), key=f"{key}_d{d.isoformat()}",
                              type="primary" if sel else "secondary", use_container_width=True):
                klik = d
    if klik:
        st.session_state[sk] = klik
        st.rerun()
    d = st.session_state[sk]
    if minggu:
        m = _senin(d)
        return m, m
    return d, d


def pilih_waktu(periode: str, key: str, mode: str, mx: date):
    """Picker preset+kalender ala Shopee untuk semua granularity. mode 'satu'
    (overview, default 1 periode) | 'trend' (Analisa, default rentang lebih lebar).
    mx = tanggal data TERBARU untuk granularity ini. Return (a, b, caption)."""
    mn = date(2025, 1, 1)
    hi = datetime.now(WIB).date()
    satu = (mode == "satu")
    pk = f"{key}_pre_{periode}"

    if periode == "harian":
        opsi = ["Kemarin", "7 hari terakhir", "30 hari terakhir", "Pilih tanggal"]
        pre = st.radio("Pilih cepat", opsi, index=0 if satu else 1, key=pk)
        if pre == opsi[0]:
            s = e = mx
        elif pre == opsi[1]:
            e = mx; s = max(mn, mx - timedelta(days=6))
        elif pre == opsi[2]:
            e = mx; s = max(mn, mx - timedelta(days=29))
        else:
            s, e = _grid_hari(key, mx, minggu=False)
        cap = _tgl_id(s) if s == e else f"{_tgl_id(s)} – {_tgl_id(e)}"
        return _wib_mid(s), _wib_mid(e), cap

    if periode == "mingguan":
        opsi = ["Minggu ini", "4 minggu terakhir", "12 minggu terakhir", "Pilih minggu"]
        pre = st.radio("Pilih cepat", opsi, index=0 if satu else 2, key=pk)
        w = _senin(mx)
        if pre == opsi[0]:
            s = e = w
        elif pre == opsi[1]:
            e = w; s = w - timedelta(days=7 * 3)
        elif pre == opsi[2]:
            e = w; s = w - timedelta(days=7 * 11)
        else:
            s, e = _grid_hari(key, mx, minggu=True)
        cap = (f"Senin {_tgl_id(s)} – Minggu {_tgl_id(e + timedelta(days=6))}" if s == e
               else f"Minggu {_tgl_id(s)} – {_tgl_id(e + timedelta(days=6))}")
        return _wib_mid(s), _wib_mid(e), cap

    if periode == "bulanan":
        opsi = ["Pilih bulan", "3 bulan terakhir", "6 bulan terakhir", "12 bulan terakhir"]
        pre = st.radio("Pilih cepat", opsi, index=0 if satu else 3, key=pk)
        m = date(mx.year, mx.month, 1)
        if pre == opsi[1]:
            e = m; s = _mundur_bulan(m, 2)
        elif pre == opsi[2]:
            e = m; s = _mundur_bulan(m, 5)
        elif pre == opsi[3]:
            e = m; s = _mundur_bulan(m, 11)
        else:  # grid klik bulan
            s, e = _grid_bulan(key, mx)
        cap = (f"{_BULAN_ID[s.month]} {s.year}" if s == e
               else f"{_BULAN_ID[s.month]} {s.year} – {_BULAN_ID[e.month]} {e.year}")
        return _wib_mid(s), _wib_mid(e), cap

    # tahunan
    opsi = ["Pilih tahun", "Semua tahun"]
    pre = st.radio("Pilih cepat", opsi, index=0 if satu else 1, key=pk)
    if pre == opsi[1]:
        s = date(2025, 1, 1); e = date(mx.year, 1, 1)
    else:  # grid klik tahun
        s, e = _grid_tahun(key, mx)
    cap = f"{s.year}" if s.year == e.year else f"{s.year} – {e.year}"
    return _wib_mid(s), _wib_mid(e), cap


def filter_bar(tabel: str, key: str, mode: str = "satu") -> dict:
    """Filter standar semua halaman: granularitas (4 opsi SELALU ada) + kalender
    + toko. mode 'satu' (overview, default 1 periode) | 'trend' (Analisa)."""
    punya = set(q(f"select distinct periode from {tabel}")["periode"].tolist()) if ada_data(tabel) else set()
    default = next((g for g in GRANS if g in punya), "bulanan")
    with st.sidebar:
        st.subheader("📅 Periode Data")
        seg = getattr(st, "segmented_control", None)
        if seg is not None:
            periode = seg("Tipe", GRANS, format_func=lambda g: GRAN_LABEL[g],
                          default=default, key=f"{key}_g", label_visibility="collapsed")
            if periode is None:
                periode = default
        else:
            periode = st.radio("Tipe", GRANS, index=GRANS.index(default),
                               format_func=lambda g: GRAN_LABEL[g], key=f"{key}_g")
        if periode in punya:
            m = q(f"select max(periode_mulai) m from {tabel} where periode=:p", {"p": periode}).iloc[0]["m"]
            mx = pd.to_datetime(m).tz_convert("Asia/Jakarta").date()
        else:
            mx = datetime.now(WIB).date()
        a, b, caption = pilih_waktu(periode, key, mode, mx)
        semua = daftar_toko()
        toko = st.multiselect("Toko", semua, default=semua, key=f"{key}_toko")
    return {"periode": periode, "a": a, "b": b, "toko": toko, "caption": caption, "punya": punya}
