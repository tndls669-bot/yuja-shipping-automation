import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import xlrd  # noqa: E402
import xlwt  # noqa: E402

from courier_tier import orders_to_packages  # noqa: E402
from epost_template_export import export_epost_files_by_tier, fill_epost_template  # noqa: E402
from schema import Channel, ProductGroup, build_standard_order  # noqa: E402

_REAL_HEADERS = [
    "미반영필드 1", "상품명", "수취인명", "수취인 우편번호", "수취인 주소", "수취인 주소",
    "수취인 전화번호", "수취인 이동통신", "배송메세지", "미반영필드 2",
]


def _make_template(path):
    wb = xlwt.Workbook()
    ws = wb.add_sheet("sheet1")
    for col, header in enumerate(_REAL_HEADERS):
        ws.write(0, col, header)
    wb.save(path)


def test_fills_template_rows_matching_real_header_layout():
    order = build_standard_order(
        Channel.SMARTSTORE, "2026080867140091", ProductGroup.YUJACHEONG,
        "조용만", "01037040094", "서울특별시 동작구 동작대로29길 91", "06999", 2,
        product_detail="로우슈거",
        address_detail="203동1305호",
    )
    packages = orders_to_packages([order])

    with tempfile.TemporaryDirectory() as tmp_dir:
        template_path = os.path.join(tmp_dir, "template.xls")
        output_path = os.path.join(tmp_dir, "filled.xls")
        _make_template(template_path)

        fill_epost_template(packages, template_path, output_path)

        wb = xlrd.open_workbook(output_path)
        sheet = wb.sheet_by_index(0)

        assert sheet.row_values(0) == _REAL_HEADERS
        row = sheet.row_values(1)
        assert row[1] == "유자청 로우슈거 1구전용박스×2"
        assert row[2] == "조용만"
        assert row[3] == "06999"
        assert row[4] == "서울특별시 동작구 동작대로29길 91"
        assert row[5] == "203동1305호"
        assert row[6] == "010-3704-0094"
        assert row[7] == "010-3704-0094"
        assert row[0] == ""
        assert row[9] == ""


def test_multi_box_order_produces_multiple_rows_one_per_package():
    order = build_standard_order(
        Channel.WHOLESALE, "id-2", ProductGroup.CHEONGYUJA,
        "김철수", "01033334444", "주소2", "22222", 12,
    )
    packages = orders_to_packages([order])

    with tempfile.TemporaryDirectory() as tmp_dir:
        template_path = os.path.join(tmp_dir, "template.xls")
        output_path = os.path.join(tmp_dir, "filled.xls")
        _make_template(template_path)

        fill_epost_template(packages, template_path, output_path)

        wb = xlrd.open_workbook(output_path)
        sheet = wb.sheet_by_index(0)
        assert sheet.nrows == 3
        assert sheet.row_values(1)[2] == "김철수"
        assert sheet.row_values(2)[2] == "김철수"
        labels = {sheet.row_values(1)[1], sheet.row_values(2)[1]}
        assert labels == {"청유자 8kg박스(8kg적재)", "청유자 3kg박스(4kg적재)"}


def test_export_by_tier_writes_one_file_per_tier_present_today():
    orders = [
        build_standard_order(
            Channel.SMARTSTORE, "id-1", ProductGroup.YUJACHEONG,
            "조용만", "01037040094", "주소1", "11111", 2, product_detail="로우슈거",
        ),
        build_standard_order(
            Channel.SMARTSTORE, "id-2", ProductGroup.YUJACHEONG,
            "송호연", "01031760402", "주소2", "22222", 1, product_detail="로우슈거",
        ),
    ]

    with tempfile.TemporaryDirectory() as tmp_dir:
        template_path = os.path.join(tmp_dir, "template.xls")
        _make_template(template_path)

        written = export_epost_files_by_tier(orders, template_path, tmp_dir, "2026-08-09")

        assert list(written.keys()) == ["2kg"]
        wb = xlrd.open_workbook(written["2kg"])
        sheet = wb.sheet_by_index(0)
        assert sheet.nrows == 3


def test_export_by_tier_splits_mixed_weights_into_separate_files():
    orders = [
        build_standard_order(
            Channel.WHOLESALE, "id-1", ProductGroup.CHEONGYUJA, "홍길동", "01011112222", "주소1", "11111", 0.5,
        ),
        build_standard_order(
            Channel.WHOLESALE, "id-2", ProductGroup.YUJA, "김철수", "01033334444", "주소2", "22222", 3,
        ),
        build_standard_order(
            Channel.WHOLESALE, "id-3", ProductGroup.CHEONGYUJA, "이영희", "01055556666", "주소3", "33333", 7,
        ),
    ]

    with tempfile.TemporaryDirectory() as tmp_dir:
        template_path = os.path.join(tmp_dir, "template.xls")
        _make_template(template_path)

        written = export_epost_files_by_tier(orders, template_path, tmp_dir, "2026-08-09")

        assert set(written.keys()) == {"2kg", "5kg", "10kg"}
        for tier, path in written.items():
            wb = xlrd.open_workbook(path)
            assert wb.sheet_by_index(0).nrows == 2  # 헤더 1 + 데이터 1


if __name__ == "__main__":
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_")]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"\n{len(tests)} tests passed")
