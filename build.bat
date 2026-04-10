@echo off
setlocal
cd /d "%~dp0"

set "PYTHON=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"

echo.
echo ============================================
echo   Building SketchASMR
echo ============================================
echo.
echo Project dir: %CD%
echo One-file exe embeds the "sounds" folder; dist\ will only show SketchASMR.exe.
echo.

"%PYTHON%" -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies.
    pause
    exit /b 1
)

echo.
echo Building portable executable...
echo.

"%PYTHON%" -m PyInstaller ^
    --noconfirm ^
    --onefile ^
    --windowed ^
    --name "SketchASMR" ^
    --add-data "sounds;sounds" ^
    --add-data "icon.png;." ^
    --icon "icon.ico" ^
    --hidden-import PyQt6.sip ^
    --hidden-import yt_dlp ^
    --hidden-import numpy ^
    --hidden-import pygame.sndarray ^
    sketch_asmr.py

if errorlevel 1 (
    echo.
    echo ERROR: PyInstaller build failed.
    pause
    exit /b 1
)

echo.
echo ============================================
echo   Build complete!
echo   Output: dist\SketchASMR.exe
echo ============================================
echo.
pause
