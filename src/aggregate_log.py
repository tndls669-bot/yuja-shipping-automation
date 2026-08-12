"""개인정보 없는 집계 전용 로그 — 이름/전화번호/주소가 전혀 없는, 통계 계산에만
필요한 값(날짜/채널/품목/박스타입/중량)만 기록한다.

깃 저장소에 커밋되는 유일한 주문 관련 파일이라 여기엔 PII가 절대 섞이면 안 된다.
매번 이 파일 전체를 다시 읽어서 누적/일자별 통계를 재계산하므로(cumulative_tracker),
클라우드 실행 환경처럼 로컬 디스크가 매번 초기화되는 곳에서도 이 파일 하나(git으로
커밋/푸시)만 있으면 그동안의 통계가 그대로 이어진다.
"""
import csv
import os

_HEADERS = ["날짜", "채널구분", "품목군", "세부품목", "박스타입", "적재중량또는수량"]


def append_packages(packages: list, date_str: str, path: str) -> None:
    if not packages:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    write_header = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(_HEADERS)
        for p in packages:
            order = p.order
            writer.writerow([
                date_str,
                order.channel.value,
                order.product_group.value if order.product_group else "",
                order.product_detail or "",
                p.box_type or "",
                p.weight_kg if p.weight_kg is not None else "",
            ])


def read_rows(path: str):
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        yield from csv.DictReader(f)
