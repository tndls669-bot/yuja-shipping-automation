"""표준 스키마 주문 리스트 ↔ CSV (설계 문서의 표준 스키마 컬럼 그대로).

이 CSV는 1단계가 만드는 "오늘 주문" 리포트이자, 2단계가 실제로 우체국에 접수할 때 읽는
원본이기도 하다. 즉 대표님이 엑셀로 이 파일을 열어 주문을 합치거나 주소를 고치거나
특정 건을 지우면, 2단계는 그 수정된 내용 그대로 접수한다.
"""
import csv

_HEADERS = [
    "채널구분",
    "주문처",
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
                o.order_source,
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


def read_orders_csv(path: str) -> list:
    """write_orders_csv의 역함수. 박스구성은 (사람이 중량만 고치고 박스구성 텍스트는
    안 고칠 수 있으므로) 신뢰하지 않고 중량/수량으로부터 항상 다시 계산한다."""
    import os

    from schema import Channel, ProductGroup, StandardOrder, compute_box_composition, normalize_phone

    if not os.path.exists(path):
        return []

    orders = []
    with open(path, "r", newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if not row.get("원주문번호"):
                continue

            product_group_raw = row.get("품목군") or None
            product_group = ProductGroup(product_group_raw) if product_group_raw else None

            weight_raw = row.get("중량또는수량")
            weight_or_qty = float(weight_raw) if weight_raw not in (None, "") else None

            box_composition = ""
            if product_group is not None and weight_or_qty is not None:
                try:
                    box_composition = compute_box_composition(product_group, weight_or_qty)
                except ValueError:
                    # 중량이 비정상적으로 크면(칸 밀림 등 CSV 손상) 여기서 통째로 실패시켜
                    # 다른 정상 주문까지 못 읽게 만들지 않는다 — box_composition은 비워두고
                    # weight_or_qty는 그대로 넘겨서 validate_order가 확인필요로 걸러내게 한다.
                    box_composition = ""

            orders.append(StandardOrder(
                channel=Channel(row["채널구분"]),
                original_order_id=row["원주문번호"],
                product_group=product_group,
                recipient_name=row.get("받는사람") or "",
                phone=normalize_phone(row.get("전화번호") or ""),
                address=row.get("주소") or ".",
                postal_code=row.get("우편번호") or "",
                weight_or_qty=weight_or_qty,
                box_composition=box_composition,
                delivery_message=row.get("배송메시지") or "",
                scheduled_delivery=row.get("지정일여부") == "Y",
                product_detail=row.get("세부품목") or None,
                address_detail=row.get("상세주소") or "",
                order_source=row.get("주문처") or "",
            ))
    return orders
