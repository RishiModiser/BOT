@echo off
REM Humanex v4.0 Build Script
REM Builds a single-click .exe for Windows

echo ========================================
echo   Humanex v4.0 - EXE Builder
echo ========================================
echo.

REM Check if PyInstaller is installed
pip show pyinstaller >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] PyInstaller not found. Installing...
    pip install pyinstaller
    echo.
)

REM Clean previous builds
echo [+] Cleaning previous builds...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist Humanex.spec del /q Humanex.spec
echo.

REM Build the executable
echo [+] Building Humanex.exe...
echo.
pyinstaller --onefile ^
    --windowed ^
    --name=Humanex ^
    --add-data="configs;configs" ^
    --add-data="scripts;scripts" ^
    --add-data="logs;logs" ^
    --hidden-import=PyQt6 ^
    --hidden-import=playwright ^
    --hidden-import=requests ^
    Humanex_v4.0.py

echo.
if exist dist\Humanex.exe (
    echo [✓] Build successful!
    echo [✓] Executable location: dist\Humanex.exe
    echo.
    echo [i] IMPORTANT NOTES:
    echo     1. Copy dist\Humanex.exe to your desired location
    echo     2. Ensure Playwright browsers are installed:
    echo        playwright install chromium
    echo     3. Create proxies.txt in the same folder as .exe
    echo     4. Double-click Humanex.exe to run
    echo.
) else (
    echo [!] Build failed. Check errors above.
    echo.
)

echo [+] Cleaning up build artifacts...
if exist build rmdir /s /q build
if exist Humanex.spec del /q Humanex.spec

echo.
echo ========================================
echo   Build process complete!
echo ========================================
pause
