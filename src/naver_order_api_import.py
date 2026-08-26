"""네이버 커머스API로 조회한 주문 → 표준 스키마.

수동으로 엑셀을 다운로드하던 smartstore_excel_import.py를 대체하는 실시간 조회 경로.
상품명→품목군/중량 분류 로직은 product_parsing.py를 공유해서 쓴다.
"""
from schema import Channel, ProductGroup, StandardOrder, compute_box_composition, normalize_phone
from product_parsing import classify_product, extract_weight_kg

NEW_ORDER_STATUS = "PAYED"  # 결제완료 — 아직 발주확인/발송처리 전인 신규 주문


def fetch_new_order_ids(client, since_iso: str) -> list[str]:
    """since_iso 이후 상태가 바뀐 주문 중 신규 결제(PAYED) 건의 productOrderId 목록."""
    result = client.call(
        "/v1/pay-order/seller/product-orders/last-changed-statuses",
        params={"lastChangedFrom": since_iso},
    )
    statuses = result.get("data", {}).get("lastChangeStatuses", [])
    return [
        s["productOrderId"] for s in statuses
        if s.get("productOrderStatus") == NEW_ORDER_STATUS
    ]


def fetch_order_details(client, product_order_ids: list[str]) -> list[dict]:
    """productOrderId 목록 → 전체 주문 상세 정보(원본 API 응답의 data 배열)."""
    if not product_order_ids:
        return []
    result = client.call(
        "/v1/pay-order/seller/product-orders/query",
        method="POST",
        json_body={"productOrderIds": product_order_ids},
    )
    return result.get("data", [])


def order_detail_to_standard_order(detail: dict) -> StandardOrder:
    product_order = detail["productOrder"]
    shipping = product_order["shippingAddress"]

    product_name = product_order.get("productName", "")
    option_info = product_order.get("productOption", "")
    qty = product_order.get("quantity") or 1
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

    return StandardOrder(
        channel=Channel.SMARTSTORE,
        original_order_id=product_order["productOrderId"],
        product_group=product_group,
        recipient_name=shipping.get("name", ""),
        phone=normalize_phone(shipping.get("tel1") or shipping.get("tel2") or ""),
        address=shipping.get("baseAddress") or ".",
        postal_code=shipping.get("zipCode", ""),
        weight_or_qty=weight_or_qty,
        box_composition=box_composition,
        delivery_message="",
        product_detail=product_detail,
        address_detail=shipping.get("detailedAddress", ""),
    )


def fetch_new_orders(client, since_iso: str) -> list[StandardOrder]:
    ids = fetch_new_order_ids(client, since_iso)
    details = fetch_order_details(client, ids)
    return [order_detail_to_standard_order(d) for d in details]
