@echo off
chcp 65001 > nul
echo ========================================================
echo   Internal Medicine Citation & Research Trend Dashboard
echo ========================================================
echo.
echo Starting Streamlit Dashboard...
echo.

cd /d "%~dp0"
python -m streamlit run app.py --server.port 8502 --server.address 127.0.0.1

pause
