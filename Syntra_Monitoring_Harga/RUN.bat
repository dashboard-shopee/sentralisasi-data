@echo off
title Syntra Monitoring Harga
cd /d "%~dp0"
echo ================================================
echo   SYNTRA MONITORING HARGA
echo   Jalanin fase sesuai FASE_AKTIF di config.py
echo   (1=grab  2=rubah  3=verifikasi  4=perpanjang)
echo ================================================
python run.py
echo.
echo === SELESAI. Tekan tombol apa saja untuk menutup. ===
pause >nul
