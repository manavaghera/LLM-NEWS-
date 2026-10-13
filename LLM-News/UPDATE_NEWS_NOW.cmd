@echo off
setlocal
title NewsSense News Update

cd /d "%~dp0"
set "PYTHONUTF8=1"
set "PYTHONUNBUFFERED=1"

if not exist ".venv\Scripts\python.exe" (
  echo.
  echo NewsSense could not find .venv\Scripts\python.exe
  echo Run the project setup first, then try this file again.
  echo.
  if not defined NEWSSENSE_NO_PAUSE pause
  exit /b 1
)

echo.
echo ========================================
echo   NewsSense - update the news now
echo ========================================
echo.
echo This can take a while when the free AI provider is busy.
echo The current edition stays online until the new update is verified.
echo.

".venv\Scripts\python.exe" -u "pipeline\daily_update.py" --interval 60 --once --no-audio %*
set "update_result=%ERRORLEVEL%"

echo.
if "%update_result%"=="0" (
  echo News update completed successfully.
  echo Refresh http://127.0.0.1:5173/ to see the latest edition.
) else (
  echo News update failed with exit code %update_result%.
  echo The previously published edition was preserved.
)
echo.

if not defined NEWSSENSE_NO_PAUSE pause
exit /b %update_result%
