"""modules/log_siklus.py — catat jejak tiap FASE bot harga ke tabel siklus_log.

Dipakai semua fase (grab, rubah_harga, verifikasi, duplikat_promo, kampanye) biar
ketahuan KAPAN tiap fase jalan (tampil di dashboard: halaman Harga + menu Log).
Aman-gagal: error pencatatan TIDAK menggagalkan bot.
"""
from sqlalchemy import text
from modules.db import get_engine


def catat_fase(pemicu, status="ok", keterangan=None):
    """program='harga'. pemicu = grab | rubah_harga | verifikasi | duplikat_promo | kampanye."""
    try:
        with get_engine().begin() as c:
            c.execute(
                text("""insert into siklus_log (program, pemicu, status, keterangan)
                        values ('harga', :m, :s, :k)"""),
                {"m": pemicu, "s": status, "k": keterangan},
            )
    except Exception:
        pass
