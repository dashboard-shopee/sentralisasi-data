"""modules/log_siklus.py — LOG terpusat bot harga (CMD + dashboard).

Dua jalur, satu vokabuler (fase·toko·modul·aksi·status):
  - log(...)   : cetak baris CMD seragam `[HH:MM:SS] [Fase·Toko·Modul] pesan` (warna per level).
  - catat(...) : NOTABLE event → cetak CMD (via log) + tulis ke siklus_log (dashboard). [M0b]
  - catat_fase(): legacy (dipakai kode lama) — dipertahankan sampai semua pindah ke catat().

Warna = ARTI (fungsional): header=cyan · ok=hijau · warning=kuning · error=merah ·
LIVE=magenta (aksi beneran ke Shopee, biar nonjol) · detail=dim.
Aman-gagal: error pencatatan TIDAK menggagalkan bot.
"""
from datetime import datetime
import colorama; colorama.init()
from sqlalchemy import text
from modules.db import get_engine

# ── Warna per LEVEL (arti, bukan asal) ──
_WARNA = {
    "header":  colorama.Fore.LIGHTCYAN_EX,   # header siklus / fase
    "ok":      colorama.Fore.GREEN,          # sukses / ada perubahan berhasil
    "warning": colorama.Fore.YELLOW,         # warning / skip (kena rem, dilewati)
    "error":   colorama.Fore.RED,            # gagal / error
    "live":    colorama.Fore.MAGENTA,        # AKSI LIVE beneran ke Shopee (nonjol)
    "detail":  colorama.Style.DIM,           # detail minor / progress
}


def _ctx(fase=None, toko=None, modul=None):
    """Rakit prefix [Fase·Toko·Modul] (skip yg kosong)."""
    bits = [str(x) for x in (fase, toko, modul) if x]
    return f"[{'·'.join(bits)}] " if bits else ""


def log(pesan, level="detail", fase=None, toko=None, modul=None):
    """Cetak 1 baris log CMD seragam: [HH:MM:SS] [Fase·Toko·Modul] pesan (warna per level).
    level: header · ok · warning · error · live · detail. Ini pengganti print(colorama) berserakan."""
    waktu = datetime.now().strftime("%H:%M:%S")
    warna = _WARNA.get(level, "")
    print(f"{warna}[{waktu}] {_ctx(fase, toko, modul)}{pesan}{colorama.Style.RESET_ALL}")


def catat_fase(pemicu, status="ok", keterangan=None):
    """LEGACY (struktur siklus_log lama). Dipertahankan sampai semua caller pindah ke catat() [M0b].
    program='harga'. pemicu = grab | rubah_harga | provisioning | fakta_harian | ..."""
    try:
        with get_engine().begin() as c:
            c.execute(
                text("""insert into siklus_log (program, pemicu, status, keterangan)
                        values ('harga', :m, :s, :k)"""),
                {"m": pemicu, "s": status, "k": keterangan},
            )
    except Exception:
        pass
