@echo off
REM Jalankan dashboard Shopee Multi-Toko (Streamlit). Browser kebuka otomatis.
cd /d "%~dp0.."
echo ============================================
echo   DASHBOARD SHOPEE MULTI-TOKO
echo   Browser akan terbuka. Tutup jendela ini untuk mematikan dashboard.
echo ============================================
python -m streamlit run dashboard/app.py
pause >nul
