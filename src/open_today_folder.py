"""오늘 날짜의 주문 폴더(위탁판매/전화문자/output)를 만들고 탐색기로 연다.

주문이 들어올 때마다 이 폴더를 열어서 파일을 끌어다 놓으면 되고,
실행은 1_오늘주문처리.bat이 담당한다.
"""
import os
from datetime import date

from local_step1_process_orders import ensure_folders, today_dir

if __name__ == "__main__":
    today = date.today().isoformat()
    day_dir = today_dir(today)
    ensure_folders(day_dir)
    os.startfile(day_dir)
    print(f"오늘 폴더를 열었습니다: {day_dir}")
