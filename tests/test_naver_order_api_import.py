import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from schema import Channel, ProductGroup  # noqa: E402
from naver_order_api_import import (  # noqa: E402
    fetch_new_order_ids,
    fetch_order_details,
    fetch_new_orders,
    order_detail_to_standard_order,
)

# 실제 API 응답(2026-08-27 라이브 테스트로 확인한 실제 구조)을 그대로 축약해서 씀.
_REAL_DETAIL_RESPONSE = {
    "data": [
        {
            "order": {
                "orderId": "2026082653038571",
                "ordererName": "문정원",
            },
            "productOrder": {
                "productOrderId": "2026082624511651",
                "quantity": 1,
                "productOrderStatus": "PAYED",
                "productName": "고흥 유기농 청유자 500g, 1kg, 3kg [생산자판매]",
                "productOption": "중량: 500g",
                "shippingAddress": {
                    "name": "문정원",
                    "tel1": "010-6252-1483",
                    "zipCode": "10124",
                    "baseAddress": "경기도 김포시 고촌읍 신기신동로 39-7 (고촌읍)",
                    "detailedAddress": "신곡리 439-6번지",
                },
            },
        }
    ]
}

_LAST_CHANGED_RESPONSE = {
    "data": {
        "lastChangeStatuses": [
            {"productOrderId": "2026082624511651", "productOrderStatus": "PAYED"},
            {"productOrderId": "2026082687149331", "productOrderStatus": "DISPATCHED"},
            {"productOrderId": "2026082041203841", "productOrderStatus": "PURCHASE_DECIDED"},
        ],
        "count": 3,
    }
}


class _FakeClient:
    def __init__(self, responses_by_path):
        self._responses = responses_by_path
        self.calls = []

    def call(self, path, method="GET", params=None, json_body=None):
        self.calls.append((path, method, params, json_body))
        return self._responses[path]


def test_order_detail_to_standard_order_maps_real_shape_correctly():
    order = order_detail_to_standard_order(_REAL_DETAIL_RESPONSE["data"][0])
    assert order.channel == Channel.SMARTSTORE
    assert order.original_order_id == "2026082624511651"
    assert order.recipient_name == "문정원"
    assert order.phone == "01062521483"
    assert order.product_group == ProductGroup.CHEONGYUJA
    assert order.weight_or_qty == 0.5
    assert order.postal_code == "10124"
    assert order.address == "경기도 김포시 고촌읍 신기신동로 39-7 (고촌읍)"
    assert order.address_detail == "신곡리 439-6번지"


def test_fetch_new_order_ids_filters_to_payed_only():
    client = _FakeClient({
        "/v1/pay-order/seller/product-orders/last-changed-statuses": _LAST_CHANGED_RESPONSE,
    })
    ids = fetch_new_order_ids(client, "2026-08-26T00:00:00.000+09:00")
    assert ids == ["2026082624511651"]


def test_fetch_order_details_empty_list_skips_api_call():
    client = _FakeClient({})
    assert fetch_order_details(client, []) == []
    assert client.calls == []


def test_fetch_new_orders_end_to_end_with_fake_client():
    client = _FakeClient({
        "/v1/pay-order/seller/product-orders/last-changed-statuses": _LAST_CHANGED_RESPONSE,
        "/v1/pay-order/seller/product-orders/query": _REAL_DETAIL_RESPONSE,
    })
    orders = fetch_new_orders(client, "2026-08-26T00:00:00.000+09:00")
    assert len(orders) == 1
    assert orders[0].recipient_name == "문정원"


if __name__ == "__main__":
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_")]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"\n{len(tests)} tests passed")
