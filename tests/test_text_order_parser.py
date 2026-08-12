import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import text_order_parser  # noqa: E402
from schema import Channel, ProductGroup  # noqa: E402


def _stub(extracted_list):
    def fake_call_gemini_json(prompt, api_key, model=None):
        return extracted_list
    return fake_call_gemini_json


def test_single_order_text_returns_one_element_list():
    text_order_parser.call_gemini_json = _stub([
        {
            "recipient_name": "홍길동",
            "phone": "010-1234-5678",
            "address": "전남 고흥군 도덕면 ...",
            "postal_code": "59554",
            "product_group": "청유자",
            "weight_or_qty": 7,
            "delivery_message": None,
            "scheduled_delivery": False,
        }
    ])
    orders = text_order_parser.parse_orders_from_text(
        "이메일 본문 예시", Channel.WHOLESALE, "wholesale-20260809", api_key="dummy"
    )
    assert len(orders) == 1
    assert orders[0].original_order_id == "wholesale-20260809-001"
    assert orders[0].channel == Channel.WHOLESALE
    assert orders[0].box_composition == "8kg박스×1(7kg적재)"


def test_phone_text_blob_splits_into_multiple_orders():
    text_order_parser.call_gemini_json = _stub([
        {
            "recipient_name": "김철수",
            "phone": "01099998888",
            "address": "광주 서구 ...",
            "postal_code": "61945",
            "product_group": "유자청",
            "weight_or_qty": 3,
            "delivery_message": None,
            "scheduled_delivery": False,
        },
        {
            "recipient_name": "이영희",
            "phone": "01055556666",
            "address": "서울 마포구 ...",
            "postal_code": "04000",
            "product_group": "유자",
            "weight_or_qty": 2,
            "delivery_message": "경비실에 맡겨주세요",
            "scheduled_delivery": True,
        },
    ])
    orders = text_order_parser.parse_orders_from_text(
        "오늘 통화/문자 주문 뭉치...", Channel.PHONE_TEXT, "phone-20260809", api_key="dummy"
    )
    assert len(orders) == 2
    assert [o.original_order_id for o in orders] == ["phone-20260809-001", "phone-20260809-002"]
    assert all(o.channel == Channel.PHONE_TEXT for o in orders)
    assert orders[0].box_composition == "1구전용박스×3"
    assert orders[1].product_group == ProductGroup.YUJA
    assert orders[1].scheduled_delivery is True


def test_yujacheong_product_detail_is_extracted():
    text_order_parser.call_gemini_json = _stub([
        {
            "recipient_name": "박민수",
            "phone": "01011112222",
            "address": "서울 강남구 ...",
            "postal_code": "06000",
            "product_group": "유자청",
            "product_detail": "레몬첼로",
            "weight_or_qty": 2,
            "delivery_message": None,
            "scheduled_delivery": False,
        }
    ])
    orders = text_order_parser.parse_orders_from_text(
        "이메일 본문 예시", Channel.WHOLESALE, "wholesale-20260809", api_key="dummy"
    )
    assert orders[0].product_detail == "레몬첼로"


def test_product_detail_ignored_for_non_yujacheong():
    text_order_parser.call_gemini_json = _stub([
        {
            "recipient_name": "박민수",
            "phone": "01011112222",
            "address": "서울 강남구 ...",
            "postal_code": "06000",
            "product_group": "청유자",
            "product_detail": "레몬첼로",
            "weight_or_qty": 2,
            "delivery_message": None,
            "scheduled_delivery": False,
        }
    ])
    orders = text_order_parser.parse_orders_from_text(
        "이메일 본문 예시", Channel.WHOLESALE, "wholesale-20260809", api_key="dummy"
    )
    assert orders[0].product_detail is None


def test_address_detail_is_extracted_separately():
    text_order_parser.call_gemini_json = _stub([
        {
            "recipient_name": "박민수",
            "phone": "01011112222",
            "address": "전남 고흥군 도덕면 고흥로 540-32",
            "address_detail": "203동 1305호",
            "postal_code": "59554",
            "product_group": "청유자",
            "weight_or_qty": 2,
            "delivery_message": None,
            "scheduled_delivery": False,
        }
    ])
    orders = text_order_parser.parse_orders_from_text(
        "이메일 본문 예시", Channel.WHOLESALE, "wholesale-20260809", api_key="dummy"
    )
    assert orders[0].address == "전남 고흥군 도덕면 고흥로 540-32"
    assert orders[0].address_detail == "203동 1305호"


def test_empty_text_returns_empty_list():
    text_order_parser.call_gemini_json = _stub([])
    orders = text_order_parser.parse_orders_from_text(
        "그냥 안부 인사 텍스트", Channel.PHONE_TEXT, "phone-20260809", api_key="dummy"
    )
    assert orders == []


if __name__ == "__main__":
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_")]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"\n{len(tests)} tests passed")
