@echo off
chcp 65001 >nul
title SYNTRA Monitoring Harga - TEST RUN (1 siklus sesuai config)
cd /d "%~dp0"
REM ============================================================
REM  TEST RUN - jalanin SATU siklus SEKARANG, PERSIS sesuai config saat ini.
REM  Ga nunggu MENIT_RUNNING. Beda dgn tes_harga.bat yg MAKSA semua tier (FULL);
REM  file ini niru 1 tembakan scheduler asli -> cuma tier yg kena JADWAL JAM INI.
REM
REM  Semua ngikut config.py apa adanya (edit di sana kalau mau ganti scope):
REM    FASE_AKTIF   = fase yg jalan  (1=grab . 2=aksi harga+provisioning)
REM    MODUL_AKTIF  = modul yg jalan (buang dari list = skip)
REM    TOKO_AKTIF   = scope toko     ([]=semua . ["kimmioshop"]=1 toko)
REM    MODE_LIVE    = True=BENERAN ke Shopee . False=DRY simulasi  <-- IKUT CONFIG
REM
REM  Tier per-JAM selalu jalan; tier HARIAN/MINGGUAN cuma kena kalau jam sekarang
REM  == JAM_FAKTA di config (satu jam buat harian & mingguan; mingguan tambah syarat
REM  hari == HARI_FAKTA_MINGGUAN). Persis kayak scheduler.
REM  Butuh paksa semua tier buat tes modul? Pakai tes_harga.bat (JAM_TES=FULL).
REM ============================================================

python run.py tes
echo.
echo ------ SELESAI (exit %errorlevel%) ------
pause
