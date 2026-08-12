import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from aggregate_log import append_packages, read_rows  # noqa: E402
from courier_tier import orders_to_packages  # noqa: E402
from schema import Channel, ProductGroup, build_standard_order  # noqa: E402


def test_append_and_read_contains_no_pii_fields():
    order = build_standard_order(
        Channel.SMARTSTORE, "2026080867140091", ProductGroup.YUJACHEONG,
        "조용만", "01037040094", "서울특별시 동작구 동작대로29길 91", "06999", 2,
        product_detail="로우슈거",
    )
    packages = orders_to_packages([order])

    with tempfile.TemporaryDirectory() as tmp_dir:
        path = os.path.join(tmp_dir, "aggregate_log.csv")
        append_packages(packages, "2026-08-09", path)

        with open(path, encoding="utf-8-sig") as f:
            content = f.read()

        assert "조용만" not in content
        assert "01037040094" not in content
        assert "동작대로" not in content

        rows = list(read_rows(path))
        assert len(rows) == 1
        assert rows[0]["날짜"] == "2026-08-09"
        assert rows[0]["채널구분"] == "스마트스토어"
        assert rows[0]["품목군"] == "유자청"
        assert rows[0]["세부품목"] == "로우슈거"
        assert rows[0]["박스타입"] == "1구전용박스"
        assert rows[0]["적재중량또는수량"] == "1.4"


def test_append_accumulates_across_multiple_calls():
    order1 = build_standard_order(
        Channel.WHOLESALE, "id-1", ProductGroup.CHEONGYUJA, "홍길동", "01011112222", "주소", "11111", 7,
    )
    order2 = build_standard_order(
        Channel.PHONE_TEXT, "id-2", ProductGroup.YUJA, "김철수", "01033334444", "주소", "22222", 3,
    )

    with tempfile.TemporaryDirectory() as tmp_dir:
        path = os.path.join(tmp_dir, "aggregate_log.csv")
        append_packages(orders_to_packages([order1]), "2026-08-09", path)
        append_packages(orders_to_packages([order2]), "2026-08-10", path)

        rows = list(read_rows(path))
        assert len(rows) == 2
        assert rows[0]["날짜"] == "2026-08-09"
        assert rows[1]["날짜"] == "2026-08-10"


def test_empty_packages_does_not_create_file():
    with tempfile.TemporaryDirectory() as tmp_dir:
        path = os.path.join(tmp_dir, "aggregate_log.csv")
        append_packages([], "2026-08-09", path)
        assert not os.path.exists(path)
        assert list(read_rows(path)) == []


if __name__ == "__main__":
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_")]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"\n{len(tests)} tests passed")
