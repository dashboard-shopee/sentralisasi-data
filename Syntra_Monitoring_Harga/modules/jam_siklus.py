"""modules/jam_siklus.py — waktu acuan DIBEKUKAN sekali di awal tiap siklus.

Port dari Syntra_Iklan/iklan/jam_siklus.py. Semua gating jadwal Fase 1
(harian/mingguan/bulanan) baca dari now() di sini, BUKAN datetime.now() live,
jadi siklus yang lama & nyeberang jam tetap ikut jadwal saat MULAI.
"""
from datetime import datetime

_waktu = None


def kunci():
    """Bekukan waktu acuan siklus = sekarang. Panggil di awal tiap siklus."""
    global _waktu
    _waktu = datetime.now()
    return _waktu


def now():
    return _waktu if _waktu is not None else datetime.now()
