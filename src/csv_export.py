"""표준 스키마 주문 리스트 → CSV 저장 (설계 문서의 표준 스키마 컬럼 그대로)."""
import csv

_HEADERS = [
    "채널구분",
    "원주문번호",
    "품목군",
    "세부품목",
    "받는사람",
    "전화번호",
    "주소",
    "상세주소",
    "우편번호",
    "중량또는수량",
    "박스구성",
    "배송메시지",
    "지정일여부",
]


def write_orders_csv(orders, path: str, append: bool = False) -> None:
    import os

    write_header = not (append and os.path.exists(path))
    mode = "a" if append else "w"
    with open(path, mode, newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(_HEADERS)
        for o in orders:
            writer.writerow([
                o.channel.value,
                o.original_order_id,
                o.product_group.value if o.product_group else "",
                o.product_detail or "",
                o.recipient_name,
                o.phone,
                o.address,
                o.address_detail,
                o.postal_code,
                o.weight_or_qty if o.weight_or_qty is not None else "",
                o.box_composition,
                o.delivery_message,
                "Y" if o.scheduled_delivery else "",
            ])
