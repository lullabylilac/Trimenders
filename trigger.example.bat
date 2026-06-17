@echo off
chcp 65001 > nul

set "VIDEO_PATH=%~f1"
set "PYTHON_EXE=%CARENOTE_PYTHON_EXE%"
set "SCRIPT_PATH=%CARENOTE_SEND_VIDEO_SCRIPT%"
set "LOG_FILE=%CARENOTE_TRIGGER_LOG_FILE%"

if "%PYTHON_EXE%"=="" set "PYTHON_EXE=python"
if "%SCRIPT_PATH%"=="" set "SCRIPT_PATH=%~dp0send_video.py"
if "%LOG_FILE%"=="" set "LOG_FILE=%~dp0logs\trigger.log"

for %%I in ("%LOG_FILE%") do set "LOG_DIR=%%~dpI"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

echo [%date% %time%] trigger started: "%VIDEO_PATH%" >> "%LOG_FILE%"

if "%VIDEO_PATH%"=="" (
    echo [%date% %time%] error: video path is empty >> "%LOG_FILE%"
    exit /b 1
)

if not exist "%VIDEO_PATH%" (
    echo [%date% %time%] error: video file not found: "%VIDEO_PATH%" >> "%LOG_FILE%"
    exit /b 1
)

if not exist "%SCRIPT_PATH%" (
    echo [%date% %time%] error: script not found: "%SCRIPT_PATH%" >> "%LOG_FILE%"
    exit /b 1
)

"%PYTHON_EXE%" "%SCRIPT_PATH%" "%VIDEO_PATH%" >> "%LOG_FILE%" 2>&1

echo [%date% %time%] trigger finished: errorlevel=%ERRORLEVEL% >> "%LOG_FILE%"
exit /b %ERRORLEVEL%
