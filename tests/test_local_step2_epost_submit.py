import csv
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import openpyxl  # noqa: E402

import local_step1_process_orders as step1  # noqa: E402
import local_step2_epost_submit as step2  # noqa: E402
from schema import Channel, ProductGroup, build_standard_order, order_to_dict  # noqa: E402


def _set_epost_env():
    os.environ["EPOST_AUTH_KEY"] = "auth"
    os.environ["EPOST_SECURITY_KEY"] = "security"
    os.environ["EPOST_CUST_NO"] = "cust"
    os.environ["EPOST_APPR_NO"] = "appr"
    os.environ["EPOST_OFFICE_SER"] = "01"


def _write_pending(inbox_root, today, orders):
    day_dir = step1.today_dir(today, inbox_root)
    output_dir = os.path.join(day_dir, "output")
    os.makedirs(output_dir, exist_ok=True)
    with open(os.path.join(output_dir, "pending_epost_orders.json"), "w", encoding="utf-8") as f:
        json.dump([order_to_dict(o) for o in orders], f, ensure_ascii=False)
    return output_dir


def test_no_pending_file_reports_nothing_to_submit():
    with tempfile.TemporaryDirectory() as inbox_root:
        original_today_dir = step2.today_dir
        step2.today_dir = lambda today: step1.today_dir(today, inbox_root)
        try:
            result = step2.run(today="2026-08-14", send_email=False)
        finally:
            step2.today_dir = original_today_dir
        assert "접수 대기 중인 주문이 없습니다" in result


def test_successful_submission_writes_result_csv_and_clears_pending():
    order = build_standard_order(
        Channel.PHONE_TEXT, "phone-1", ProductGroup.YUJACHEONG,
        "홍길동", "01012345678", "전남 고흥군 ...", "59554", 2,
    )

    with tempfile.TemporaryDirectory() as inbox_root:
        output_dir = _write_pending(inbox_root, "2026-08-14", [order])
        _set_epost_env()

        original_today_dir = step2.today_dir
        original_insert_order = step2.insert_order
        step2.today_dir = lambda today: step1.today_dir(today, inbox_root)
        step2.insert_order = lambda auth_key, security_key, params: {"regiNo": "6890161633630"}
        try:
            result = step2.run(today="2026-08-14", send_email=False)
        finally:
            step2.today_dir = original_today_dir
            step2.insert_order = original_insert_order

        assert "6890161633630" in result
        assert not os.path.exists(os.path.join(output_dir, "pending_epost_orders.json"))

        with open(os.path.join(output_dir, "2026-08-14_epost_result.csv"), encoding="utf-8-sig") as f:
            rows = list(csv.reader(f))
        assert rows[1][0] == "phone-1"
        assert rows[1][1] == "홍길동"
        assert rows[1][4] == "6890161633630"
        assert rows[1][5] == "접수완료"


def test_api_failure_is_recorded_but_does_not_crash():
    order = build_standard_order(
        Channel.WHOLESALE, "wholesale-1", ProductGroup.CHEONGYUJA,
        "김철수", "01033334444", "전남 고흥군 ...", "59554", 7,
    )

    with tempfile.TemporaryDirectory() as inbox_root:
        output_dir = _write_pending(inbox_root, "2026-08-14", [order])
        _set_epost_env()

        def _fail(auth_key, security_key, params):
            raise RuntimeError("우체국 서버 오류")

        original_today_dir = step2.today_dir
        original_insert_order = step2.insert_order
        step2.today_dir = lambda today: step1.today_dir(today, inbox_root)
        step2.insert_order = _fail
        try:
            result = step2.run(today="2026-08-14", send_email=False)
        finally:
            step2.today_dir = original_today_dir
            step2.insert_order = original_insert_order

        assert "실패 1" in result
        with open(os.path.join(output_dir, "2026-08-14_epost_result.csv"), encoding="utf-8-sig") as f:
            rows = list(csv.reader(f))
        assert "실패" in rows[1][5]


def test_smartstore_orders_produce_naver_dispatch_excel():
    order = build_standard_order(
        Channel.SMARTSTORE, "2026082512345", ProductGroup.CHEONGYUJA,
        "정다은", "01099998888", "전남 고흥군 ...", "59554", 3,
    )

    with tempfile.TemporaryDirectory() as inbox_root:
        output_dir = _write_pending(inbox_root, "2026-08-14", [order])
        _set_epost_env()

        original_today_dir = step2.today_dir
        original_insert_order = step2.insert_order
        step2.today_dir = lambda today: step1.today_dir(today, inbox_root)
        step2.insert_order = lambda auth_key, security_key, params: {"regiNo": "6890166064699"}
        try:
            step2.run(today="2026-08-14", send_email=False)
        finally:
            step2.today_dir = original_today_dir
            step2.insert_order = original_insert_order

        dispatch_path = os.path.join(output_dir, "2026-08-14_네이버발송처리.xlsx")
        assert os.path.exists(dispatch_path)
        wb = openpyxl.load_workbook(dispatch_path)
        ws = wb["발송처리"]
        assert [c.value for c in ws[2]] == ["2026082512345", "택배,등기,소포", "우체국택배", "6890166064699"]


if __name__ == "__main__":
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_")]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"\n{len(tests)} tests passed")
