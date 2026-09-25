@echo off
echo ===================================================================
echo   Starting SheetMerge Pro - Outreach CRM ^& Deliverability Engine
echo ===================================================================
cd /d "%~dp0"
python -m pip install -r backend\requirements.txt
start http://localhost:8000
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
pause
