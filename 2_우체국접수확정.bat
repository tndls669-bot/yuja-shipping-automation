@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
echo ==== 우체국 접수 확정 (실제 배송비가 발생합니다) ====
set /p CONFIRM=오더 리포트를 확인했고 실제로 접수하시겠습니까? (Y/N):
if /i not "%CONFIRM%"=="Y" (
    echo 취소되었습니다.
    pause >nul
    exit /b
)
"C:\Users\tndls\AppData\Local\Programs\Python\Python312\python.exe" "C:\yuja-shipping-automation\src\local_step2_epost_submit.py"
echo.
echo ==== 완료 (창을 닫으려면 아무 키나 누르세요) ====
pause >nul
