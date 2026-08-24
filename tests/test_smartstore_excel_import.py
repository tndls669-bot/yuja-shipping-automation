import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import openpyxl  # noqa: E402

from schema import Channel, ProductGroup  # noqa: E402
from smartstore_excel_import import orders_from_workbook  # noqa: E402

_HEADERS = [
    "상품명", "옵션정보", "수량", "6개월 주문금액", "우편번호", "기본배송지", "상세배송지",
    "수취인연락처2", "수취인연락처1", "배송메세지", "상품주문번호", "주문번호",
    "배송방법(구매자 요청)", "배송방법", "택배사", "송장번호", "수취인명", "발송일",
    "판매채널", "구매자ID", "주문상태", "주문세부상태", "결제위치", "결제일",
    "상품번호", "상품종류", "반품안심케어", "옵션관리코드", "옵션가격", "상품가격",
    "최종 상품별 할인액", "판매자 부담 할인액", "최종 상품별 총 주문금액", "사은품",
    "발주확인일", "발송기한", "발송처리일", "송장출력일", "배송비 형태", "배송비 묶음번호",
    "배송비 유형", "배송비 합계", "제주/도서 추가배송비", "배송비 할인액", "판매자 상품코드",
    "판매자 내부코드1", "판매자 내부코드2", "통합배송지", "구매자연락처", "출고지", "결제수단",
    "네이버페이 주문관리 수수료", "매출연동 수수료", "정산예정금액", "개인통관고유부호",
    "주문일시", "구독신청회차", "구독진행회차", "배송희망일",
]


def _make_workbook(data_rows):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["안내문 (실제로는 병합된 안내 텍스트)"] + [None] * (len(_HEADERS) - 1))
    ws.append(_HEADERS)
    for row in data_rows:
        full_row = [None] * len(_HEADERS)
        for key, value in row.items():
            full_row[_HEADERS.index(key)] = value
        ws.append(full_row)
    return wb


def test_real_yujacheong_row_maps_to_low_sugar():
    wb = _make_workbook([{
        "상품명": "순수유자 유기농 저당유자청 무설탕 500g, 1개",
        "수량": 2,
        "우편번호": "06999",
        "기본배송지": "서울특별시 동작구 동작대로29길 91",
        "상세배송지": "203동1305호",
        "수취인연락처1": "010-3704-0094",
        "상품주문번호": "2026080867140091",
        "수취인명": "조용만",
        "배송메세지": None,
    }])
    orders = orders_from_workbook(wb)
    assert len(orders) == 1
    order = orders[0]
    assert order.channel == Channel.SMARTSTORE
    assert order.original_order_id == "2026080867140091"
    assert order.recipient_name == "조용만"
    assert order.phone == "01037040094"
    assert order.product_group == ProductGroup.YUJACHEONG
    assert order.product_detail == "로우슈거"
    assert order.weight_or_qty == 2
    assert order.box_composition == "1구전용박스×2"
    assert order.postal_code == "06999"
    assert order.address == "서울특별시 동작구 동작대로29길 91"
    assert order.address_detail == "203동1305호"


def test_lemoncello_and_diorganic_keywords_map_correctly():
    wb = _make_workbook([
        {
            "상품명": "순수유자 레몬첼로유자청 300g",
            "수량": 1,
            "상품주문번호": "id-1",
            "수취인명": "홍길동",
            "수취인연락처1": "01011112222",
        },
        {
            "상품명": "순수유자 디오가닉유자청 300g",
            "수량": 3,
            "상품주문번호": "id-2",
            "수취인명": "김철수",
            "수취인연락처1": "01033334444",
        },
    ])
    orders = orders_from_workbook(wb)
    assert orders[0].product_detail == "레몬첼로"
    assert orders[1].product_detail == "디오가닉"
    assert orders[1].weight_or_qty == 3


def test_raw_fruit_weight_parsed_from_product_name():
    wb = _make_workbook([{
        "상품명": "순수유자 청유자 생과 1kg",
        "수량": 3,
        "상품주문번호": "id-3",
        "수취인명": "이영희",
        "수취인연락처1": "01055556666",
    }])
    orders = orders_from_workbook(wb)
    assert orders[0].product_group == ProductGroup.CHEONGYUJA
    assert orders[0].weight_or_qty == 3
    assert orders[0].box_composition == "3kg박스×1(3kg적재)"


def test_option_info_weight_wins_over_product_name_listing_all_options():
    # 실제 스마트스토어 상품명은 "청유자 500g, 1kg, 3kg [옵션선택필수]"처럼 판매 가능한
    # 중량을 전부 나열한다. 구매자가 실제로 고른 중량은 옵션정보에만 있으므로
    # 그쪽을 우선해야 한다 (상품명의 첫 숫자 "500g"를 잘못 집으면 안 됨).
    wb = _make_workbook([
        {
            "상품명": "순수유자 청유자 500g, 1kg, 3kg [옵션선택필수]",
            "옵션정보": "중량: 3kg",
            "수량": 1,
            "상품주문번호": "id-5",
            "수취인명": "정다은",
            "수취인연락처1": "01099998888",
        },
        {
            "상품명": "순수유자 청유자 500g, 1kg, 3kg [옵션선택필수]",
            "옵션정보": "중량: 1kg",
            "수량": 2,
            "상품주문번호": "id-6",
            "수취인명": "최우진",
            "수취인연락처1": "01011119999",
        },
    ])
    orders = orders_from_workbook(wb)
    assert orders[0].weight_or_qty == 3
    assert orders[1].weight_or_qty == 2


def test_unrecognized_product_name_leaves_group_none():
    wb = _make_workbook([{
        "상품명": "포장 부자재 견본",
        "수량": 1,
        "상품주문번호": "id-4",
        "수취인명": "박민수",
        "수취인연락처1": "01077778888",
    }])
    orders = orders_from_workbook(wb)
    assert orders[0].product_group is None
    assert orders[0].weight_or_qty is None
    assert orders[0].box_composition == ""


def test_rows_without_order_id_are_skipped():
    wb = _make_workbook([{"상품명": "순수유자 저당유자청", "수량": 1}])
    orders = orders_from_workbook(wb)
    assert orders == []


if __name__ == "__main__":
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_")]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"\n{len(tests)} tests passed")
