@echo off
setlocal
cd /d "%~dp0"

echo Starting Paytm Vyapar AI...
echo.

if not exist "data" mkdir data

start "Vyapar AI Backend" cmd /k "cd /d %~dp0backend && set PYTHONPATH=%~dp0backend && py -3 -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
timeout /t 2 >nul
start "Vyapar AI Frontend" cmd /k "cd /d %~dp0frontend && npx vite --host 127.0.0.1 --port 5173"

echo Backend: http://127.0.0.1:8000
echo Frontend: http://127.0.0.1:5173
echo.
echo Put secrets only in backend\.env
echo See docs\NO_CARD_SETUP_GUIDE.md for Sarvam / Inngest / Langfuse setup.
endlocal
