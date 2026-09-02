import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from csv_export import read_orders_csv, write_orders_csv  # noqa: E402
from schema import Channel, ProductGroup, build_standard_order  # noqa: E402
from validation import validate_order  # noqa: E402


def test_round_trip_preserves_order_fields():
    order = build_standard_order(
        Channel.SMARTSTORE, "id-1", ProductGroup.CHEONGYUJA,
        "홍길동", "01012345678", "전남 고흥군 ...", "59554", 3,
        order_source="네이버스마트스토어",
    )
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "orders.csv")
        write_orders_csv([order], path)
        loaded = read_orders_csv(path)

    assert len(loaded) == 1
    assert loaded[0].recipient_name == "홍길동"
    assert loaded[0].order_source == "네이버스마트스토어"
    assert loaded[0].box_composition == "3kg박스×1(3kg적재)"


def test_corrupted_row_with_absurd_weight_does_not_crash_the_whole_read():
    # 2026-09-01 사고 재현: 주소에 쉼표가 있는데 따옴표로 안 감싸면 그 쉼표가 컬럼
    # 구분자로 읽혀서 뒤 칸들이 밀린다 — 이 케이스에서는 우편번호(15621)가 중량 칸으로
    # 들어간다. 이런 한 줄 때문에 같은 파일의 다른 정상 주문까지 못 읽으면 안 된다.
    header = (
        "채널구분,주문처,원주문번호,품목군,세부품목,받는사람,전화번호,주소,상세주소,"
        "우편번호,중량또는수량,박스구성,배송메시지,지정일여부\n"
    )
    good_row = (
        "스마트스토어,네이버스마트스토어,id-1,청유자,,정상주문,01012345678,"
        "서울 어딘가,101호,12345,1.0,1kg박스×1(1kg적재),,\n"
    )
    # 주소 "안산시 (사동, 선경아파트)"의 쉼표가 따옴표 없이 들어가 우편번호(15621)가
    # 중량또는수량 칸으로 밀린 손상된 행.
    corrupted_row = (
        "위탁판매자,남해로부터,id-2,청유자,,박승환,050226788642,"
        "경기도 안산시 상록구 감골2로 58 (사동, 선경아파트),105동 503호,15621,0.5,"
        "1kg박스×1(0.5kg적재),,\n"
    )

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "orders.csv")
        with open(path, "w", encoding="utf-8-sig") as f:
            f.write(header + good_row + corrupted_row)

        orders = read_orders_csv(path)

    assert len(orders) == 2
    good = next(o for o in orders if o.original_order_id == "id-1")
    bad = next(o for o in orders if o.original_order_id == "id-2")

    assert good.recipient_name == "정상주문"
    assert validate_order(good) == []

    # 손상된 행은 weight_or_qty가 비정상적으로 커진 채로 넘어오지만, 조용히 접수되면
    # 안 되므로 validate_order가 반드시 걸러내야 한다.
    issues = validate_order(bad)
    assert any("중량" in i for i in issues)


if __name__ == "__main__":
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_")]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"\n{len(tests)} tests passed")
