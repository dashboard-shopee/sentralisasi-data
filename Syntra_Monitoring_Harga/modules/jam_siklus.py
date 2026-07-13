"""modules/jam_siklus.py — waktu acuan DIBEKUKAN sekali di awal tiap siklus.

Port dari Syntra_Iklan/iklan/jam_siklus.py. Semua gating jadwal Fase 1
(harian/mingguan/bulanan) baca dari now() di sini, BUKAN datetime.now() live,
jadi siklus yang lama & nyeberang jam tetap ikut jadwal saat MULAI.
"""
from datetime import datetime

_waktu = None
_simulasi = None   # kalau diisi (run.py tes): kunci() SELALU balik ke waktu ini


def kunci():
    """Bekukan waktu acuan siklus = sekarang. Panggil di awal tiap siklus.
    Kalau lagi mode simulasi (set_simulasi), waktu acuan = waktu simulasi."""
    global _waktu
    _waktu = _simulasi or datetime.now()
    return _waktu


def set_simulasi(dt):
    """Paksa waktu acuan (dipakai `run.py tes` — simulasi jam/hari biar tier
    harian/mingguan bisa dites kapan aja). Berlaku sampai proses mati."""
    global _simulasi, _waktu
    _simulasi = dt
    _waktu = dt


def now():
    return _waktu if _waktu is not None else datetime.now()
