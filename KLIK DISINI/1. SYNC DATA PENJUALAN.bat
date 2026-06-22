@echo off
REM Tarik data penjualan dari Google Sheet -> SQL (Supabase). READ-ONLY ke Sheet.
cd /d "%~dp0.."
echo ============================================
echo   SYNC PENJUALAN  (Sheet Input Produk -^> SQL)
echo ============================================
python -m etl.penjualan
echo.
echo Selesai. Tekan tombol apa saja untuk menutup.
pause >nul
