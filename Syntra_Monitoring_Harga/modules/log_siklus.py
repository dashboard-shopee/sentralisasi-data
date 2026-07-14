"""modules/log_siklus.py — LOG terpusat bot harga (CMD + dashboard).

Dua jalur, satu vokabuler (fase·toko·modul·aksi·status):
  - log(...)   : cetak baris CMD seragam `[HH:MM:SS] [Fase·Toko·Modul] pesan` (warna per level).
  - catat(...) : NOTABLE event (ada yg BERUBAH) → cetak CMD (via log) + tulis 1 baris ke
                 siklus_log (dashboard). Detail kaya (fase·toko·modul·aksi·hasil) disimpan di
                 kolom `detail` jsonb — ADDITIF, tak ngubah struktur tabel bersama. [M0b]
  - catat_fase(): heartbeat per-fase (1 baris/siklus, "trigger X jalan") — struktur lama, tetap.

Warna = ARTI (fungsional): header=cyan · ok=hijau · warning=kuning · error=merah ·
LIVE=magenta (aksi beneran ke Shopee, biar nonjol) · detail=dim.
Aman-gagal: error pencatatan TIDAK menggagalkan bot.
"""
import json
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


# status → level warna CMD (kalau level tak dipaksa)
_LEVEL_DR_STATUS = {"ok": "ok", "live": "live", "gagal": "error",
                    "skip": "warning", "warning": "warning"}


def catat(aksi, status="ok", fase=None, toko=None, modul=None, keterangan=None,
          detail=None, cmd=True, level=None):
    """NOTABLE event — sesuatu yang BERUBAH (harga dibenerin, promo dipasang/dicabut).
    Cetak 1 baris CMD (via log, kecuali cmd=False) + tulis 1 baris ke siklus_log.

    aksi   : teks pendek apa yang terjadi ("harga 9000→7900", "3 band voucher dibuat").
    fase   : F1/F2/F3 · toko · modul : voucher/paket/garansi/... · status: ok/live/gagal/skip.
    detail : dict/list opsional buat drill-down dashboard.
    Dashboard: program='harga', pemicu=modul|fase, detail={fase,toko,modul,aksi,hasil,...}."""
    if cmd:
        log(aksi, level=level or _LEVEL_DR_STATUS.get(status, "detail"),
            fase=fase, toko=toko, modul=modul)
    try:
        muatan = {"fase": fase, "toko": toko, "modul": modul, "aksi": aksi}
        if isinstance(detail, dict):
            muatan.update(detail)
        elif detail is not None:
            muatan["rincian"] = detail
        with get_engine().begin() as c:
            c.execute(
                text("""insert into siklus_log (program, pemicu, status, keterangan, detail)
                        values ('harga', :m, :s, :k, cast(:d as jsonb))"""),
                {"m": modul or fase or "event", "s": status,
                 "k": keterangan or aksi, "d": json.dumps(muatan, default=str)},
            )
    except Exception:
        pass  # pencatatan TIDAK boleh menggagalkan bot


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
