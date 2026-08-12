"""우체국 계약고객 '신규접수' 업로드 양식(.xls)에 발송 패키지를 채워넣는다.

biz.epost.go.kr에서 받은 빈 템플릿의 헤더를 그대로 읽어서 같은 컬럼 순서로
데이터 행만 추가한다 — 템플릿 형식이 바뀌어도 헤더 이름 매칭이라 크게 안 깨진다.
"수취인 주소" 헤더가 템플릿에 두 번 나오는 건 기본주소/상세주소 칸이라 확인됨.

택배비 계약이 2kg/5kg/10kg 구간별로 되어 있어서, 구간마다 별도 파일로 업로드해야
한다 — 그래서 이 모듈은 courier_tier로 주문을 패키지 단위로 쪼갠 뒤 구간별로
파일을 나눠서 저장한다(구간에 해당하는 패키지가 없으면 그 구간 파일은 안 만든다).
"""
import os

import xlrd
import xlwt

from courier_tier import TIERS, orders_to_packages

_FIELD_MAP = {
    "상품명": "product_label",
    "수취인명": "recipient_name",
    "수취인 우편번호": "postal_code",
    "수취인 전화번호": "phone_formatted",
    "수취인 이동통신": "phone_formatted",
    "배송메세지": "delivery_message",
}


def _format_phone(phone: str) -> str:
    digits = phone or ""
    if len(digits) == 11:
        return f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"
    if len(digits) == 10:
        return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
    return digits


def _write_packages(packages: list, headers: list, address_cols: list, ws) -> None:
    for row_idx, package in enumerate(packages, start=1):
        order = package.order
        values = {
            "product_label": package.label,
            "recipient_name": order.recipient_name,
            "postal_code": order.postal_code,
            "phone_formatted": _format_phone(order.phone),
            "delivery_message": order.delivery_message,
        }
        for col, header in enumerate(headers):
            field = _FIELD_MAP.get(header)
            if field:
                ws.write(row_idx, col, values.get(field, ""))
        if len(address_cols) >= 1:
            ws.write(row_idx, address_cols[0], order.address)
        if len(address_cols) >= 2:
            ws.write(row_idx, address_cols[1], order.address_detail)


def fill_epost_template(packages: list, template_path: str, output_path: str) -> None:
    src = xlrd.open_workbook(template_path)
    sheet = src.sheet_by_index(0)
    headers = sheet.row_values(0)
    address_cols = [i for i, h in enumerate(headers) if h == "수취인 주소"]

    wb = xlwt.Workbook(encoding="utf-8")
    ws = wb.add_sheet("sheet1")
    for col, header in enumerate(headers):
        ws.write(0, col, header)

    _write_packages(packages, headers, address_cols, ws)
    wb.save(output_path)


def export_epost_files_by_tier(orders: list, template_path: str, output_dir: str, date_str: str) -> dict:
    packages = orders_to_packages(orders)
    written = {}

    for tier in TIERS:
        tier_packages = [p for p in packages if p.tier == tier]
        if not tier_packages:
            continue
        output_path = os.path.join(output_dir, f"우체국_접수_{date_str}_{tier}.xls")
        fill_epost_template(tier_packages, template_path, output_path)
        written[tier] = output_path

    unclassified = [p for p in packages if p.tier is None]
    if unclassified:
        output_path = os.path.join(output_dir, f"우체국_접수_{date_str}_확인필요.xls")
        fill_epost_template(unclassified, template_path, output_path)
        written["확인필요"] = output_path

    return written
