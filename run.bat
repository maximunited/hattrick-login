@echo off
set PYTHONUTF8=1

if exist .env (
    for /f "delims=" %%x in (.env) do (set "%%x")
)

if not exist "%~dp0venv\Scripts\activate.bat" (
    echo Setting up virtual environment...
    python -m venv "%~dp0venv"
    call "%~dp0venv\Scripts\activate.bat"
    pip install -r "%~dp0requirements.txt"
) else (
    call "%~dp0venv\Scripts\activate.bat"
)

python hattrick_login.py %*
