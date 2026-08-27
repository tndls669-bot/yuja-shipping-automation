import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from schema import Channel, ProductGroup, build_standard_order  # noqa: E402
from validation import validate_order  # noqa: E402


def _order(phone, address="전남 고흥군 ...", product_group=ProductGroup.CHEONGYUJA, weight_or_qty=3, postal_code="59554"):
    return build_standard_order(
        Channel.WHOLESALE, "id-1", product_group, "홍길동", phone, address, postal_code, weight_or_qty,
    )


def test_normal_mobile_number_passes():
    assert validate_order(_order("010-1234-5678")) == []


def test_safe_number_0502_passes():
    # 안심번호(가상번호) — 위탁판매/택배 발송 시 실제 연락처 대신 흔히 쓰임
    assert validate_order(_order("0502-1361-7051")) == []


def test_safe_number_0504_passes():
    assert validate_order(_order("0504-123-45678")) == []


def test_garbage_phone_is_flagged():
    issues = validate_order(_order("123"))
    assert any("전화번호" in i for i in issues)


def test_missing_address_is_flagged():
    order = _order("010-1234-5678", address="")
    assert "주소 누락" in validate_order(order)


def test_missing_postal_code_is_flagged():
    # 우체국 API가 우편번호 없이는 접수를 거부하므로(recZip 필수) 1단계에서 미리 걸러야 함
    order = _order("010-1234-5678", postal_code="")
    assert "우편번호 누락" in validate_order(order)


if __name__ == "__main__":
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_")]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"\n{len(tests)} tests passed")
