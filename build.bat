@echo off
setlocal

echo.
echo ============================================
echo   Building SketchASMR
echo ============================================
echo.

pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies.
    pause
    exit /b 1
)

echo.
echo Building portable executable...
echo.

pyinstaller ^
    --noconfirm ^
    --onefile ^
    --windowed ^
    --name "SketchASMR" ^
    --add-data "sounds;sounds" ^
    --add-data "icon.png;." ^
    --icon "icon.ico" ^
    --hidden-import PyQt6.sip ^
    pen_asmr.py

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
