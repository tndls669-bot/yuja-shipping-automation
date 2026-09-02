"""네이버 스마트스토어 '선택주문발주발송관리' 엑셀 다운로드 파일 → 표준 스키마.

커머스API 연동 전까지, 판매자센터에서 수동으로 다운로드한 이 엑셀 파일을 읽어
같은 파이프라인에 태울 수 있게 해주는 임시 노드. 나중에 커머스API가 연결되면
이 모듈은 그대로 두고 daily_pipeline에 API 조회 노드만 추가하면 된다.

상품명 → 품목군/세부품목/중량 매칭 규칙은 product_parsing.py에 공용으로 있다
(어글리어스 등 다른 위탁판매자 주문서 파서와 공유).
"""
import io

import msoffcrypto
import openpyxl

from product_parsing import classify_product, extract_weight_kg
from schema import Channel, ProductGroup, StandardOrder, compute_box_composition, normalize_phone

_HEADER_ROW_INDEX = 2  # 1-based: 1행은 안내문, 2행이 실제 헤더
_ORDER_ID_COL = "상품주문번호"


def orders_from_workbook(wb) -> list[StandardOrder]:
    ws = wb.worksheets[0]
    rows = list(ws.iter_rows(values_only=True))
    header = rows[_HEADER_ROW_INDEX - 1]
    col = {name: idx for idx, name in enumerate(header) if name is not None}

    orders = []
    for row in rows[_HEADER_ROW_INDEX:]:
        if not row or col.get(_ORDER_ID_COL) is None or row[col[_ORDER_ID_COL]] is None:
            continue

        def get(field, default=None):
            idx = col.get(field)
            return row[idx] if idx is not None else default

        product_name = get("상품명")
        option_info = get("옵션정보")
        qty = get("수량") or 1
        product_group, product_detail = classify_product(product_name)

        if product_group == ProductGroup.YUJACHEONG:
            weight_or_qty = qty
        elif product_group in (ProductGroup.CHEONGYUJA, ProductGroup.YUJA):
            weight_or_qty = extract_weight_kg(product_name, option_info, qty)
        else:
            weight_or_qty = None

        box_composition = ""
        if product_group is not None and weight_or_qty is not None:
            box_composition = compute_box_composition(product_group, weight_or_qty)

        address = get("기본배송지") or ""
        address_detail = get("상세배송지") or ""

        phone = get("수취인연락처1") or get("수취인연락처2") or ""
        postal_code = get("우편번호")

        orders.append(StandardOrder(
            channel=Channel.SMARTSTORE,
            original_order_id=str(row[col[_ORDER_ID_COL]]),
            product_group=product_group,
            recipient_name=get("수취인명") or "",
            phone=normalize_phone(str(phone)),
            address=address if address.strip() else ".",
            postal_code=str(postal_code) if postal_code is not None else "",
            weight_or_qty=weight_or_qty,
            box_composition=box_composition,
            delivery_message=get("배송메세지") or "",
            scheduled_delivery=bool(get("배송희망일")),
            product_detail=product_detail,
            address_detail=address_detail,
            order_source="네이버스마트스토어",
        ))

    return orders


def load_orders_from_encrypted_xlsx(file_path: str, password: str) -> list[StandardOrder]:
    decrypted = io.BytesIO()
    with open(file_path, "rb") as f:
        office_file = msoffcrypto.OfficeFile(f)
        office_file.load_key(password=password)
        office_file.decrypt(decrypted)

    wb = openpyxl.load_workbook(decrypted, data_only=True)
    return orders_from_workbook(wb)
