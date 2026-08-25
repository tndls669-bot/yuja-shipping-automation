"""어글리어스(위탁판매) 주문서 → 표준 스키마.

어글리어스는 매일 오전 9시 10분에 주문서 엑셀을 메일로 자동 발송한다(공급자 안내문
2026-08-25 기준). 이메일 첨부파일은 email_fetcher가 excel_reader로 이미
"셀 | 셀 | 셀" 형태 텍스트로 바꿔서 넘겨주므로, 그 텍스트에서 표를 찾아 정확한 컬럼
매핑으로 바로 처리한다(실제 상품주문번호를 정확히 잡아야 어글리어스 자체 송장 등록
페이지에서 매칭이 되기 때문에 AI 파싱보다 이 방식이 안전하다).

어글리어스가 표 컬럼 구성을 바꾸면 _REQUIRED_COLS에 없는 새 필수 컬럼이 생겨
감지가 안 될 수 있다 — 그 경우 이 모듈이 아니라 기존 AI 파싱으로 자동 대체된다
(parse_uglyus_table이 None을 반환하면 호출 쪽에서 Gemini로 넘김).
"""
from schema import Channel, ProductGroup, StandardOrder, compute_box_composition, normalize_phone
from product_parsing import classify_product, extract_weight_kg

_REQUIRED_COLS = ("상품주문번호", "수취인명", "옵션정보")


def _split_row(line: str) -> list[str]:
    return [c.strip() for c in line.split("|")]


def parse_uglyus_table(text: str) -> list[StandardOrder] | None:
    """text 안에서 어글리어스 주문서 표를 찾아 파싱한다. 표를 못 찾으면 None."""
    lines = [line for line in text.splitlines() if line.strip()]

    header = None
    header_idx = None
    for i, line in enumerate(lines):
        if "|" not in line:
            continue
        cells = _split_row(line)
        if all(col in cells for col in _REQUIRED_COLS):
            header = cells
            header_idx = i
            break
    if header is None:
        return None

    col = {name: idx for idx, name in enumerate(header)}

    def get(cells, field, default=""):
        idx = col.get(field)
        if idx is None or idx >= len(cells):
            return default
        return cells[idx] or default

    orders = []
    for line in lines[header_idx + 1:]:
        if "|" not in line:
            continue
        cells = _split_row(line)
        order_id = get(cells, "상품주문번호")
        if not order_id:
            continue

        product_name = get(cells, "상품명")
        option_info = get(cells, "옵션정보")
        qty = float(get(cells, "수량", "1") or "1")
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

        phone = get(cells, "수취인연락처1") or get(cells, "수취인연락처2")
        address = get(cells, "기본주소") or get(cells, "배송지")

        orders.append(StandardOrder(
            channel=Channel.WHOLESALE,
            original_order_id=order_id,
            product_group=product_group,
            recipient_name=get(cells, "수취인명"),
            phone=normalize_phone(phone),
            address=address if address.strip() else ".",
            postal_code=get(cells, "우편번호"),
            weight_or_qty=weight_or_qty,
            box_composition=box_composition,
            delivery_message=get(cells, "배송메세지"),
            product_detail=product_detail,
            address_detail=get(cells, "상세주소"),
        ))

    return orders
