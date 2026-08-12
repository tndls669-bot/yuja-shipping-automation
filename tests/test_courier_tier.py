import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from courier_tier import TIER_2KG, TIER_5KG, TIER_10KG, orders_to_packages  # noqa: E402
from schema import Channel, ProductGroup, StandardOrder, build_standard_order  # noqa: E402


def test_1kg_box_maps_to_2kg_tier():
    order = build_standard_order(
        Channel.SMARTSTORE, "id-1", ProductGroup.CHEONGYUJA, "홍길동", "01011112222", "주소", "11111", 0.5,
    )
    packages = orders_to_packages([order])
    assert len(packages) == 1
    assert packages[0].tier == TIER_2KG
    assert packages[0].weight_kg == 0.5


def test_3kg_box_maps_to_5kg_tier_regardless_of_loaded_weight():
    for weight in (2, 3, 4):
        order = build_standard_order(
            Channel.SMARTSTORE, "id-1", ProductGroup.YUJA, "홍길동", "01011112222", "주소", "11111", weight,
        )
        packages = orders_to_packages([order])
        assert len(packages) == 1, weight
        assert packages[0].tier == TIER_5KG, weight


def test_8kg_box_maps_to_10kg_tier():
    order = build_standard_order(
        Channel.SMARTSTORE, "id-1", ProductGroup.CHEONGYUJA, "홍길동", "01011112222", "주소", "11111", 7,
    )
    packages = orders_to_packages([order])
    assert packages[0].tier == TIER_10KG


def test_multi_box_order_splits_into_separate_packages_with_own_tiers():
    order = build_standard_order(
        Channel.WHOLESALE, "id-1", ProductGroup.CHEONGYUJA, "김철수", "01033334444", "주소", "22222", 12,
    )
    packages = orders_to_packages([order])
    assert len(packages) == 2
    tiers = {p.tier for p in packages}
    assert tiers == {TIER_5KG, TIER_10KG}
    assert all(p.order is order for p in packages)


def test_yujacheong_bottles_stay_as_one_package_and_use_estimated_weight():
    light_order = build_standard_order(
        Channel.PHONE_TEXT, "id-1", ProductGroup.YUJACHEONG, "이영희", "01055556666", "주소", "33333", 2,
        product_detail="레몬첼로",
    )
    heavy_order = build_standard_order(
        Channel.PHONE_TEXT, "id-2", ProductGroup.YUJACHEONG, "박민수", "01077778888", "주소", "44444", 10,
        product_detail="디오가닉",
    )
    light_packages = orders_to_packages([light_order])
    heavy_packages = orders_to_packages([heavy_order])

    assert len(light_packages) == 1
    assert light_packages[0].tier == TIER_2KG  # 2 * 0.7 = 1.4kg
    assert light_packages[0].weight_kg == 1.4

    assert len(heavy_packages) == 1
    assert heavy_packages[0].tier == TIER_10KG  # 10 * 0.7 = 7kg


def test_unclassified_product_group_gets_no_tier():
    order = StandardOrder(
        channel=Channel.WHOLESALE,
        original_order_id="id-1",
        product_group=None,
        recipient_name="홍길동",
        phone="01011112222",
        address="주소",
        postal_code="11111",
        weight_or_qty=None,
    )
    packages = orders_to_packages([order])
    assert packages[0].tier is None


if __name__ == "__main__":
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_")]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"\n{len(tests)} tests passed")
