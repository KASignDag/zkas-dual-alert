@echo off
setlocal
title ZKas Dual Alert Setup

net session >nul 2>&1
if %errorlevel% neq 0 (
  echo Requesting administrator permission...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)

echo.
echo ============================================
echo   ZKas Dual Alert - Plug and Play Setup
echo ============================================
echo.
echo This will:
echo   - Install Dual Alert
echo   - Auto-detect a compatible local bridge
echo   - Register automatic startup
echo   - Optionally pair with your ZKAS.stream dashboard
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0INSTALL.ps1"
if %errorlevel% neq 0 (
  echo.
  echo Setup did not complete successfully.
  pause
  exit /b %errorlevel%
)
echo.
echo Setup complete.
timeout /t 3 >nul
endlocal
