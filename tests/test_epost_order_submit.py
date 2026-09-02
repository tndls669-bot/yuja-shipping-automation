import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from courier_tier import orders_to_packages  # noqa: E402
from epost_order_submit import package_to_order_params  # noqa: E402
from schema import Channel, ProductGroup, build_standard_order  # noqa: E402


def test_maps_yujacheong_order_to_params():
    order = build_standard_order(
        Channel.SMARTSTORE, "2026080867140091", ProductGroup.YUJACHEONG,
        "조용만", "01037040094", "서울특별시 동작구 동작대로29길 91", "06999", 2,
        product_detail="로우슈거", address_detail="203동1305호",
    )
    package = orders_to_packages([order])[0]
    params = package_to_order_params(package, "0005305157", "5026082295", "01", "순수유자", test_yn=True)

    assert params["custNo"] == "0005305157"
    assert params["apprNo"] == "5026082295"
    assert params["officeSer"] == "01"
    assert params["recNm"] == "조용만"
    assert params["recZip"] == "06999"
    assert params["recAddr1"] == "서울특별시 동작구 동작대로29길 91"
    assert params["recAddr2"] == "203동1305호"
    assert params["recMob"] == "01037040094"
    assert params["goodsNm"] == "(유자청 로우슈거,2병)"
    assert params["weight"] == "2"  # 2병 * 0.7kg = 1.4kg -> 올림 2kg
    assert params["testYn"] == "Y"


def test_missing_address_detail_defaults_to_dot():
    order = build_standard_order(
        Channel.WHOLESALE, "id-2", ProductGroup.CHEONGYUJA,
        "김철수", "01033334444", "주소", "22222", 7,
    )
    package = orders_to_packages([order])[0]
    params = package_to_order_params(package, "custno", "apprno", "01", "순수유자")

    assert params["recAddr2"] == "."
    assert params["weight"] == "7"
    assert "testYn" not in params


def test_delivery_message_included_only_when_present():
    order = build_standard_order(
        Channel.WHOLESALE, "id-3", ProductGroup.CHEONGYUJA,
        "이영희", "01055556666", "주소", "33333", 3, delivery_message="문 앞에 놓아주세요",
    )
    package = orders_to_packages([order])[0]
    params = package_to_order_params(package, "custno", "apprno", "01", "순수유자")
    assert params["delivMsg"] == "문 앞에 놓아주세요"


if __name__ == "__main__":
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_")]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"\n{len(tests)} tests passed")
