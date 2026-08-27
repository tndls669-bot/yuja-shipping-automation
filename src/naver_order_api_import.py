"""네이버 커머스API로 조회한 주문 → 표준 스키마.

수동으로 엑셀을 다운로드하던 smartstore_excel_import.py를 대체하는 실시간 조회 경로.
상품명→품목군/중량 분류 로직은 product_parsing.py를 공유해서 쓴다.

주의: last-changed-statuses API는 "최근 상태가 바뀐 것" 위주의 짧은 시간창(하루 안팎)
목록이라, 결제된 뒤 며칠째 그대로 PAYED 상태인 주문은 lastChangedFrom을 계속 앞으로
당기면 놓칠 수 있다(실제로 확인됨). 그래서 fetch_actionable_orders는 "한번 발견한
PAYED 주문 ID는 실제로 접수 전까지 계속 직접 재조회"하는 방식으로 누락을 막는다.
"""
import json
import os
from datetime import datetime, timedelta

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


# API가 "조회 가능한 날짜 범위를 초과했습니다"(에러 104139)로 거부하는 범위가 있어,
# 상태 파일이 아직 없는 첫 실행에는 안전하게 최근 24시간만 조회한다.
_DEFAULT_LOOKBACK_HOURS = 24


def _load_state(state_path: str, now_iso: str) -> dict:
    if not os.path.exists(state_path):
        now = datetime.fromisoformat(now_iso)
        default_since = (now - timedelta(hours=_DEFAULT_LOOKBACK_HOURS)).isoformat(timespec="milliseconds")
        return {"last_checked": default_since, "pending_order_ids": []}
    with open(state_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_state(state_path: str, state: dict) -> None:
    os.makedirs(os.path.dirname(state_path), exist_ok=True)
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def fetch_actionable_orders(client, state_path: str, now_iso: str) -> list[StandardOrder]:
    """아직 접수(발송처리)되지 않은 PAYED 주문을 전부 반환한다.

    새로 결제된 건은 last-changed-statuses로 찾고, 예전에 발견했지만 아직 PAYED
    그대로인 건은 저장해둔 목록으로 계속 추적한다 — 그래야 API의 짧은 조회 시간창
    때문에 며칠째 미접수 상태인 주문을 놓치지 않는다.
    """
    state = _load_state(state_path, now_iso)

    new_ids = fetch_new_order_ids(client, state["last_checked"])
    candidate_ids = sorted(set(state["pending_order_ids"]) | set(new_ids))

    details = fetch_order_details(client, candidate_ids)
    still_payed = [d for d in details if d["productOrder"]["productOrderStatus"] == NEW_ORDER_STATUS]

    state["pending_order_ids"] = [d["productOrder"]["productOrderId"] for d in still_payed]
    state["last_checked"] = now_iso
    _save_state(state_path, state)

    return [order_detail_to_standard_order(d) for d in still_payed]
