@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
echo ==== 오늘 주문 처리 시작 ====
"C:\Users\tndls\AppData\Local\Programs\Python\Python312\python.exe" "C:\yuja-shipping-automation\src\local_step1_process_orders.py"
echo.
echo ==== 완료 (창을 닫으려면 아무 키나 누르세요) ====
pause >nul
