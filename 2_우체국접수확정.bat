@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
echo Post office submission (this charges real shipping fees and cannot be undone)
set /p CONFIRM=Did you check the order report and want to submit now? (Y/N):
if /i not "%CONFIRM%"=="Y" (
    echo Cancelled.
    pause >nul
    exit /b
)
"C:\Users\tndls\AppData\Local\Programs\Python\Python312\python.exe" "C:\yuja-shipping-automation\src\local_step2_epost_submit.py"
echo.
echo Done. Press any key to close this window.
pause >nul
