import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from schema import Channel, ProductGroup  # noqa: E402
from uglyus_order_import import parse_uglyus_table  # noqa: E402

_REAL_EMAIL_TEXT = """[보낸사람: farm@uglyus.co.kr] [제목: [어글리어스] 주문서]
안녕하세요, 영농조합법인 순수 채수인님.
어글리어스입니다.

8월 25일 오전 9시 마감분 주문서를 전달드립니다.

[첨부파일: 주문서.xlsx]
[시트: 주문서]
상태 | 상품명 | 상품주문번호 | 배송방법 | 택배사 | 송장번호 | 구매자명 | 구매자연락처 | 수취인명 | 수취인연락처1 | 수취인연락처2 | 옵션정보 | 수량 | 우편번호 | 배송지 | 배송메세지 | 기본주소 | 상세주소 | 선물번호 | 도서산간지역 | 품절유무
READY | 유기농 청유자 1kg | 687372 | 택배,등기,소포 |  |  | 이지은🌈김이든 | 01053031970 | 이지은 | 01053031970 |  | 유기농 청유자 1kg | 1 | 13560 | 경기 성남시 분당구 정자로 2 903호 |  | 경기 성남시 분당구 정자로 2 | 903호 |  | N | N
READY | 저당유자청 | 687373 | 택배,등기,소포 |  |  | 김철수 | 01033334444 | 김철수 | 01033334444 |  | 저당유자청 500g | 2 | 06999 | 서울 동작구 |  | 서울 동작구 | 101호 |  | N | N
"""


def test_recognizes_real_uglyus_table_and_extracts_real_order_id():
    orders = parse_uglyus_table(_REAL_EMAIL_TEXT)
    assert orders is not None
    assert len(orders) == 2

    first = orders[0]
    assert first.channel == Channel.WHOLESALE
    assert first.original_order_id == "687372"
    assert first.recipient_name == "이지은"
    assert first.phone == "01053031970"
    assert first.product_group == ProductGroup.CHEONGYUJA
    assert first.weight_or_qty == 1.0
    assert first.postal_code == "13560"
    assert first.address == "경기 성남시 분당구 정자로 2"
    assert first.address_detail == "903호"


def test_low_sugar_yujacheong_uses_quantity_not_weight():
    orders = parse_uglyus_table(_REAL_EMAIL_TEXT)
    second = orders[1]
    assert second.original_order_id == "687373"
    assert second.product_group == ProductGroup.YUJACHEONG
    assert second.product_detail == "로우슈거"
    assert second.weight_or_qty == 2


def test_returns_none_when_no_matching_table_found():
    assert parse_uglyus_table("그냥 평범한 문자 주문 텍스트입니다.") is None


def test_rows_without_order_id_are_skipped():
    text = (
        "상태 | 상품명 | 상품주문번호 | 수취인명 | 수취인연락처1 | 옵션정보 | 수량\n"
        "READY | 청유자 |  | 홍길동 | 01011112222 | 1kg | 1\n"
    )
    orders = parse_uglyus_table(text)
    assert orders == []


if __name__ == "__main__":
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_")]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"\n{len(tests)} tests passed")
