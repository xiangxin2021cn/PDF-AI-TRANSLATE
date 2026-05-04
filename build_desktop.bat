@echo off
REM PDF2ZH-Next Desktop Build Script
setlocal enabledelayedexpansion

echo ========================================
echo   PDF2ZH-Next Desktop Builder
echo   Creating Windows Desktop Application
echo ========================================
echo.

echo Step 1: Installing dependencies...
python -m pip install pywebview pyinstaller

if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)

echo OK Dependencies installed
echo.

echo Step 2: Building desktop application...
echo This may take several minutes...
echo.

python -m PyInstaller pdf2zh_desktop.spec --clean --noconfirm

if errorlevel 1 (
    echo ERROR: Build failed
    pause
    exit /b 1
)

echo.
echo ========================================
echo   Build Completed Successfully!
echo ========================================
echo.

if exist "dist\PDF2ZH-Next-Desktop.exe" (
    echo OK Desktop application created: dist\PDF2ZH-Next-Desktop.exe
    
    for %%A in ("dist\PDF2ZH-Next-Desktop.exe") do (
        set "FILE_SIZE=%%~zA"
        set /a "FILE_SIZE_MB=!FILE_SIZE!/1024/1024"
        echo OK File size: !FILE_SIZE_MB! MB
    )
    
    echo.
    echo The desktop application is ready for distribution!
    echo Users can run it directly without installing Python.
    echo.
    
    set /p "open_folder=Open dist folder? (y/n): "
    if /i "!open_folder!"=="y" (
        explorer "dist"
    )
    
    set /p "test_exe=Test the application now? (y/n): "
    if /i "!test_exe!"=="y" (
        echo.
        echo Starting PDF2ZH-Next Desktop...
        start "" "dist\PDF2ZH-Next-Desktop.exe"
    )
    
) else (
    echo ERROR: Executable was not created
    echo Please check the build output for errors
)

echo.
pause
