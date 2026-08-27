"""네이버 커머스API로 발송처리(송장 등록)를 직접 호출 — 엑셀 업로드를 대체.

2026-08-27 실제 호출로 확인한 스펙:
- POST /v1/pay-order/seller/product-orders/dispatch
- body: {"dispatchProductOrders": [{productOrderId, deliveryMethod, deliveryCompanyCode,
  trackingNumber, dispatchDate}, ...]}  (dispatchDate 필수, ISO 8601)
- 응답: {"data": {"successProductOrderIds": [...], "failProductOrderInfos": [...]}}
- 택배사 코드는 실제 주문 상세의 expectedDeliveryCompany 필드에서 확인한 값을 그대로 씀("EPOST").
"""
from datetime import datetime

_DELIVERY_COMPANY_CODE = "EPOST"
_DELIVERY_METHOD = "DELIVERY"


def dispatch_orders(client, product_order_id_to_tracking: dict) -> dict:
    """{productOrderId: trackingNumber} 매핑을 네이버에 발송처리로 등록한다.

    반환값: {"success_ids": [...], "fail_infos": [...]} (fail_infos는 네이버가 돌려준 원본 실패 정보)
    """
    if not product_order_id_to_tracking:
        return {"success_ids": [], "fail_infos": []}

    now_iso = datetime.now().astimezone().isoformat(timespec="milliseconds")
    body = {
        "dispatchProductOrders": [
            {
                "productOrderId": product_order_id,
                "deliveryMethod": _DELIVERY_METHOD,
                "deliveryCompanyCode": _DELIVERY_COMPANY_CODE,
                "trackingNumber": tracking_number,
                "dispatchDate": now_iso,
            }
            for product_order_id, tracking_number in product_order_id_to_tracking.items()
        ]
    }
    result = client.call("/v1/pay-order/seller/product-orders/dispatch", method="POST", json_body=body)
    data = result.get("data", {})
    return {
        "success_ids": data.get("successProductOrderIds", []),
        "fail_infos": data.get("failProductOrderInfos", []),
    }
