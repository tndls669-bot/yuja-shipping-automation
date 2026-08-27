import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from naver_dispatch_api import dispatch_orders  # noqa: E402


class _FakeClient:
    def __init__(self, response):
        self._response = response
        self.calls = []

    def call(self, path, method="GET", params=None, json_body=None):
        self.calls.append((path, method, params, json_body))
        return self._response


def test_empty_mapping_skips_api_call():
    client = _FakeClient({})
    result = dispatch_orders(client, {})
    assert result == {"success_ids": [], "fail_infos": []}
    assert client.calls == []


def test_builds_request_with_required_fields_and_epost_company_code():
    client = _FakeClient({"data": {"successProductOrderIds": ["id-1"], "failProductOrderInfos": []}})
    dispatch_orders(client, {"id-1": "6890166983948"})

    path, method, params, body = client.calls[0]
    assert path == "/v1/pay-order/seller/product-orders/dispatch"
    assert method == "POST"
    item = body["dispatchProductOrders"][0]
    assert item["productOrderId"] == "id-1"
    assert item["trackingNumber"] == "6890166983948"
    assert item["deliveryCompanyCode"] == "EPOST"
    assert item["deliveryMethod"] == "DELIVERY"
    assert "dispatchDate" in item  # 네이버 API가 필수로 요구함(실제 검증됨)


def test_parses_success_and_failure_lists_from_response():
    client = _FakeClient({
        "data": {
            "successProductOrderIds": ["id-1", "id-2"],
            "failProductOrderInfos": [{"productOrderId": "id-3", "message": "이미 발송처리됨"}],
        }
    })
    result = dispatch_orders(client, {"id-1": "t1", "id-2": "t2", "id-3": "t3"})
    assert result["success_ids"] == ["id-1", "id-2"]
    assert result["fail_infos"] == [{"productOrderId": "id-3", "message": "이미 발송처리됨"}]


if __name__ == "__main__":
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_")]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"\n{len(tests)} tests passed")
