@echo off
cd /d "%~dp0backend"
".venv\Scripts\python.exe" -m uvicorn main:app --reload --host 127.0.0.1 --port 8001
pause
