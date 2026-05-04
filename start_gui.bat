@echo off
REM PDF2ZH-Next GUI Startup Script
REM Set working directory to script location
cd /d "%~dp0"

REM Set window title
title PDF2ZH-Next - PDF Math Translation Tool

echo ========================================
echo   PDF2ZH-Next - PDF Math Translation Tool
echo   Version: 2.5.0
echo ========================================
echo.

REM Check if virtual environment exists
if not exist "pdf2zh-env\Scripts\python.exe" (
    echo ERROR: Python virtual environment not found
    echo Please ensure the program is correctly installed
    echo.
    pause
    exit /b 1
)

REM Start GUI mode
echo Starting PDF2ZH-Next GUI interface...
echo Please wait, program is initializing...
echo.

REM Launch Desktop GUI mode
pdf2zh-env\Scripts\python.exe -m pdf2zh_next.main --gui --desktop-gui

REM If program exits abnormally, show error information
if errorlevel 1 (
    echo.
    echo Program exited abnormally, error code: %errorlevel%
    echo Please check log information or contact technical support
    echo.
    pause
)
