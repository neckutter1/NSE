@echo off
setlocal

echo [NSE] Installing dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo [NSE] pip install failed. Aborting.
    pause
    exit /b 1
)

echo.
echo [NSE] Building executable...

if exist "art\NSE.ico" (
    echo [NSE] Icon found - including in build.
    pyinstaller ^
        --noconfirm ^
        --onefile ^
        --windowed ^
        --name NSE ^
        --collect-all customtkinter ^
        --add-data "art;art" ^
        --icon "art\NSE.ico" ^
        main.py
) else (
    echo [NSE] No icon found at art\NSE.ico - building without icon.
    pyinstaller ^
        --noconfirm ^
        --onefile ^
        --windowed ^
        --name NSE ^
        --collect-all customtkinter ^
        main.py
)

if errorlevel 1 (
    echo.
    echo [NSE] Build FAILED.
    pause
    exit /b 1
)

echo.
echo [NSE] Generating SHA-256 hash...
for /f "skip=1 tokens=*" %%H in ('certutil -hashfile dist\NSE.exe SHA256') do (
    if not defined NSE_HASH set "NSE_HASH=%%H"
)

if not defined NSE_HASH (
    echo [NSE] WARNING: Could not compute hash.
    set "NSE_HASH=UNKNOWN"
)

echo [NSE] SHA-256: %NSE_HASH%

echo.
echo [NSE] Writing RELEASE_NOTES.txt...
(
    echo NSE - Neck Switch Engage
    echo Version: 1.0.0
    echo Copyright ^(C^) 2026
    echo.
    echo ---------------------------------------------------------------
    echo OFFICIAL BEHAVIOR
    echo ---------------------------------------------------------------
    echo ENGAGE  = DisplaySwitch.exe /internal
    echo RESTORE = DisplaySwitch.exe /extend
    echo.
    echo ---------------------------------------------------------------
    echo DISTRIBUTION
    echo ---------------------------------------------------------------
    echo This is a portable single-file executable.
    echo No installer required. No admin rights required.
    echo No network access. No telemetry. No background service.
    echo.
    echo WARNING: Only download NSE.exe from the official release
    echo location. Verify the SHA-256 hash before running any copy
    echo obtained from a third party.
    echo.
    echo ---------------------------------------------------------------
    echo SHA-256 CHECKSUM
    echo ---------------------------------------------------------------
    echo %NSE_HASH%
    echo.
    echo File: dist\NSE.exe
) > RELEASE_NOTES.txt

echo.
echo [NSE] Build complete.
echo [NSE] Output:  dist\NSE.exe
echo [NSE] Notes:   RELEASE_NOTES.txt
echo [NSE] SHA-256: %NSE_HASH%
pause
