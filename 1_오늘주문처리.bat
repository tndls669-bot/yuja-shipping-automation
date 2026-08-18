@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
echo Processing today's orders...
"C:\Users\tndls\AppData\Local\Programs\Python\Python312\python.exe" "C:\yuja-shipping-automation\src\local_step1_process_orders.py"
echo.
echo Done. Press any key to close this window.
pause >nul
