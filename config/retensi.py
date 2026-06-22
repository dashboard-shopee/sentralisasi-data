"""
config/retensi.py — kebijakan retensi data (berapa lama disimpan di SQL).

Ubah angka di sini kapan saja; scripts/retensi.py membacanya. Data yang lewat
batas akan diarsipkan ke file dulu (kalau ARSIP_SEBELUM_HAPUS = True) baru dihapus.
"""

# Berapa hari ke belakang tiap granularity disimpan di SQL.
# None = simpan selamanya (tidak pernah dihapus).
RETENSI_HARI = {
    "realtime": 30,      # snapshot per jam — buat monitoring intraday
    "harian": 180,       # ~6 bulan
    "mingguan": 730,     # ~2 tahun
    "bulanan": 1825,     # ~5 tahun
    "tahunan": None,     # selamanya
}

# Arsipkan ke file (CSV gzip) sebelum dihapus dari SQL?
ARSIP_SEBELUM_HAPUS = True
ARSIP_DIR = "data/arsip"
