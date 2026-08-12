import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from schema import (  # noqa: E402
    Channel,
    ProductGroup,
    build_standard_order,
    compute_box_composition,
    full_address,
    normalize_phone,
)


def test_normalize_phone_strips_hyphens_and_spaces():
    assert normalize_phone("010-1234-5678") == "01012345678"
    assert normalize_phone("010 1234 5678") == "01012345678"


def test_compute_box_composition_yujacheong_is_bottle_count():
    assert compute_box_composition(ProductGroup.YUJACHEONG, 3) == "1구전용박스×3"


def test_compute_box_composition_raw_product_uses_box_calc():
    result = compute_box_composition(ProductGroup.CHEONGYUJA, 5)
    assert result == "3kg박스×1(4kg적재)+1kg박스×1(1kg적재)"


def test_build_standard_order_fills_box_composition():
    order = build_standard_order(
        channel=Channel.SMARTSTORE,
        original_order_id="2026081001",
        product_group=ProductGroup.YUJA,
        recipient_name="홍길동",
        phone="010-1111-2222",
        address="전남 고흥군 ...",
        postal_code="59554",
        weight_or_qty=7,
    )
    assert order.phone == "01011112222"
    assert order.box_composition == "8kg박스×1(7kg적재)"
    assert order.channel == Channel.SMARTSTORE


def test_build_standard_order_missing_address_becomes_dot():
    order = build_standard_order(
        channel=Channel.PHONE_TEXT,
        original_order_id="manual-0001",
        product_group=ProductGroup.YUJACHEONG,
        recipient_name="김철수",
        phone="01033334444",
        address="",
        postal_code="",
        weight_or_qty=2,
    )
    assert order.address == "."
    assert order.box_composition == "1구전용박스×2"


def test_full_address_combines_base_and_detail():
    order = build_standard_order(
        channel=Channel.SMARTSTORE,
        original_order_id="2026081002",
        product_group=ProductGroup.YUJA,
        recipient_name="홍길동",
        phone="010-1111-2222",
        address="전남 고흥군 도덕면 고흥로 540-32",
        postal_code="59554",
        weight_or_qty=7,
        address_detail="203동 1305호",
    )
    assert order.address == "전남 고흥군 도덕면 고흥로 540-32"
    assert order.address_detail == "203동 1305호"
    assert full_address(order) == "전남 고흥군 도덕면 고흥로 540-32 203동 1305호"


def test_full_address_with_no_detail_is_just_base():
    order = build_standard_order(
        channel=Channel.SMARTSTORE,
        original_order_id="2026081003",
        product_group=ProductGroup.YUJA,
        recipient_name="홍길동",
        phone="010-1111-2222",
        address="전남 고흥군 도덕면 고흥로 540-32",
        postal_code="59554",
        weight_or_qty=7,
    )
    assert full_address(order) == "전남 고흥군 도덕면 고흥로 540-32"


if __name__ == "__main__":
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_")]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"\n{len(tests)} tests passed")
