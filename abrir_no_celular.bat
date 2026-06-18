@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" -B "src\app.py" --host 0.0.0.0 --port 5055
pause
