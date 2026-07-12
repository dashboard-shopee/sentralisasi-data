@echo off
title Syntra Monitoring Harga
cd /d "%~dp0"
echo ================================================
echo   SYNTRA MONITORING HARGA - SCHEDULER
echo   Atur di config.py: FASE_AKTIF . TOKO_AKTIF . MODUL_AKTIF . jam trigger
echo   Fase: 1=Fakta(grab)  2=Masalah+Solusi  3=Laporan
echo ================================================
python run.py
echo.
echo === SELESAI. Tekan tombol apa saja untuk menutup. ===
pause >nul
