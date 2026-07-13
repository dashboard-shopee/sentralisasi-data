@echo off
chcp 65001 >nul
title SYNTRA Monitoring Harga - TES 1 SIKLUS
cd /d "%~dp0"
REM ============================================================
REM  TES 1 SIKLUS SEKARANG - ga nunggu MENIT_RUNNING (:05).
REM
REM  Yang jalan ngikut config.py (edit dulu di sana):
REM    FASE_AKTIF   = fase yg dites  (1=grab . 2=aksi harga+provisioning)
REM    MODUL_AKTIF  = modul yg dites (buang dari list = skip)
REM    TOKO_AKTIF   = scope toko     ([]=semua . ["kimmioshop"]=1 toko)
REM    MODE_LIVE    = True=BENERAN ke Shopee . False=DRY simulasi
REM
REM  JAM_TES  = FULL  -> SEMUA tier dipaksa jalan (jam + harian + mingguan),
REM                      ga peduli jam & jadwal. PALING GAMPANG buat tes modul.
REM           = angka 0-23 -> simulasi jam segitu; tier harian/mingguan cuma kena
REM                      kalau angkanya SAMA dgn JAM_FAKTA_HARIAN/MINGGUAN di config
REM           = kosong -> pakai jam sekarang (biasanya tier per-JAM doang)
REM  HARI_TES = hari simulasi buat tier mingguan (SENIN..MINGGU, kosongin = hari ini;
REM             ga kepake kalau JAM_TES=FULL)
REM ============================================================
set JAM_TES=FULL
set HARI_TES=

python run.py tes %JAM_TES% %HARI_TES%
echo.
echo ------ SELESAI (exit %errorlevel%) ------
pause
