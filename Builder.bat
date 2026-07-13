@echo off
cd /d %~dp0
title Checking Python installation...
python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo Python is not installed!
    goto ERROR
)
title Checking libraries...
for %%p in (customtkinter pillow pyaes urllib3) do (
    echo Checking '%%p'...
    python -c "import %%p" > nul 2>&1
    if errorlevel 1 (
        echo Installing %%p...
        python -m pip install %%p > nul
    )
)
echo Checking 'pycryptodome'...
python -c "import Crypto" > nul 2>&1
if errorlevel 1 (
    echo Installing pycryptodome...
    python -m pip install pycryptodome > nul
)
cls
title Starting builder...
python gui.py
if %errorlevel% neq 0 goto ERROR
exit
:ERROR
color 4 && title [Error]
pause > nul
