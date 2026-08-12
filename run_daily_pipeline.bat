@echo off
set PYTHONIOENCODING=utf-8
echo ==== %date% %time% ==== >> "C:\yuja-shipping-automation\data\output\run_log.txt"
"C:\Users\tndls\AppData\Local\Programs\Python\Python312\python.exe" "C:\yuja-shipping-automation\src\daily_pipeline.py" >> "C:\yuja-shipping-automation\data\output\run_log.txt" 2>&1
