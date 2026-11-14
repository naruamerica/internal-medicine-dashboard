@echo off
chcp 65001 > nul
echo ======================================================================
echo   Internal Medicine Citation & Research Trend Dashboard (Online)
echo ======================================================================
echo.

cd /d "%~dp0"

echo [1/2] ダッシュボード（Streamlit）を起動しています...
start /b python -m streamlit run app.py --server.headless=true --server.port=8502 --server.address=127.0.0.1 > streamlit_stdout.log 2> streamlit_error.log

echo アプリの起動を待機しています（約6秒）...
timeout /t 6 > nul

echo.
echo [2/2] オンライン公開URLを発行しています...
echo.
echo ----------------------------------------------------------------------
echo  画面下に表示される「https://xxxx.trycloudflare.com」のURLをコピーし、
echo  お使いのブラウザ（PCやスマートフォン）に貼り付けてアクセスしてください。
echo.
echo  ※ ご自身のPC上であれば http://localhost:8502 でも開けます。
echo ----------------------------------------------------------------------
echo.
echo  初期ログイン情報:
echo    Login ID : n-ogasawara
echo    Password : 2020408
echo.
echo  ※ アプリを終了する場合は、このウィンドウを閉じてください。
echo ----------------------------------------------------------------------
echo.

.\bin\cloudflared.exe tunnel --url http://127.0.0.1:8502

pause
