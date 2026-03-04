@echo off
setlocal

echo.
echo ============================================
echo   Building DrawTablet ASMR
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
    --name "DrawTablet ASMR" ^
    --add-data "sounds;sounds" ^
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
echo   Output: dist\DrawTablet ASMR.exe
echo ============================================
echo.
pause
