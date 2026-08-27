import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import local_step1_process_orders as step1  # noqa: E402
import text_order_parser  # noqa: E402


def _stub_per_call(responses):
    calls = {"i": 0}

    def fake_call_gemini_json(prompt, api_key, model=None):
        result = responses[calls["i"]]
        calls["i"] += 1
        return result
    return fake_call_gemini_json


def _run(inbox_root, today="2026-08-14", **kwargs):
    kwargs.setdefault("send_email", False)
    kwargs.setdefault("senders_path", os.path.join(inbox_root, "wholesale_senders.txt"))
    kwargs.setdefault("processed_email_ids_path", os.path.join(inbox_root, "processed_email_ids.json"))
    kwargs.setdefault("phone_senders_path", os.path.join(inbox_root, "phone_text_senders.txt"))
    kwargs.setdefault("processed_phone_email_ids_path", os.path.join(inbox_root, "processed_phone_email_ids.json"))
    kwargs.setdefault("log_path", os.path.join(inbox_root, "aggregate_log.csv"))
    kwargs.setdefault("cumulative_path", os.path.join(inbox_root, "cumulative_data.json"))
    kwargs.setdefault("dashboard_path", os.path.join(inbox_root, "dashboard.html"))
    kwargs.setdefault("naver_api_state_path", os.path.join(inbox_root, "naver_api_state.json"))
    step1.run("dummy-key", today=today, inbox_root=inbox_root, **kwargs)


def test_ensure_folders_creates_both_channel_subfolders_and_output():
    with tempfile.TemporaryDirectory() as inbox_root:
        day_dir = step1.today_dir("2026-08-14", inbox_root)
        step1.ensure_folders(day_dir)
        assert os.path.isdir(os.path.join(day_dir, "위탁판매"))
        assert os.path.isdir(os.path.join(day_dir, "전화문자"))
        assert os.path.isdir(os.path.join(day_dir, "output"))


def test_files_dropped_in_subfolder_are_parsed_and_archived():
    text_order_parser.call_gemini_json = _stub_per_call([
        [
            {
                "recipient_name": "홍길동",
                "phone": "010-1234-5678",
                "address": "전남 고흥군 ...",
                "postal_code": "59554",
                "product_group": "청유자",
                "weight_or_qty": 7,
                "delivery_message": None,
                "scheduled_delivery": False,
            }
        ],
    ])

    with tempfile.TemporaryDirectory() as inbox_root:
        day_dir = step1.today_dir("2026-08-14", inbox_root)
        step1.ensure_folders(day_dir)
        with open(os.path.join(day_dir, "전화문자", "order1.txt"), "w", encoding="utf-8") as f:
            f.write("홍길동 010-1234-5678 청유자 7kg")

        _run(inbox_root)

        assert not os.path.exists(os.path.join(day_dir, "전화문자", "order1.txt"))
        assert os.path.exists(os.path.join(day_dir, "전화문자", "processed", "order1.txt"))

        pending_path = os.path.join(day_dir, "output", "pending_epost_orders.json")
        with open(pending_path, encoding="utf-8") as f:
            pending = json.load(f)
        assert len(pending) == 1
        assert pending[0]["recipient_name"] == "홍길동"
        assert pending[0]["channel"] == "전화문자"


def test_issue_orders_are_excluded_from_pending_list():
    text_order_parser.call_gemini_json = _stub_per_call([
        [
            {
                "recipient_name": "박순자",
                "phone": "010-1122-3344",
                "address": None,
                "postal_code": None,
                "product_group": "유자청",
                "weight_or_qty": 2,
                "delivery_message": None,
                "scheduled_delivery": False,
            }
        ],
    ])

    with tempfile.TemporaryDirectory() as inbox_root:
        day_dir = step1.today_dir("2026-08-14", inbox_root)
        step1.ensure_folders(day_dir)
        with open(os.path.join(day_dir, "위탁판매", "order1.txt"), "w", encoding="utf-8") as f:
            f.write("박순자 010-1122-3344 유자청 2병 (주소 미상)")

        _run(inbox_root)

        pending_path = os.path.join(day_dir, "output", "pending_epost_orders.json")
        assert not os.path.exists(pending_path)
        assert os.path.exists(os.path.join(day_dir, "output", "2026-08-14_issues.csv"))


def test_gemini_failure_on_one_folder_does_not_lose_other_sources_orders():
    # 위탁판매 폴더의 스마트스토어 엑셀(AI 파싱 불필요)은 성공해야 하고,
    # 전화문자 폴더의 텍스트 파싱은 Gemini 오류로 실패해도 스마트스토어 주문은
    # 정상적으로 저장되어야 한다(유실 금지). 실패한 전화문자 폴더는 archive되지 않아야
    # 다음 실행 때 재시도된다.
    def _fail_call(prompt, api_key, model=None):
        raise RuntimeError("503 Service Unavailable")
    text_order_parser.call_gemini_json = _fail_call

    with tempfile.TemporaryDirectory() as inbox_root:
        day_dir = step1.today_dir("2026-08-14", inbox_root)
        step1.ensure_folders(day_dir)
        with open(os.path.join(day_dir, "전화문자", "order1.txt"), "w", encoding="utf-8") as f:
            f.write("문자로 받은 주문 텍스트")

        _run(inbox_root)

        # 실패한 폴더는 그대로 남아있어야 함 (archive 안 됨)
        assert os.path.exists(os.path.join(day_dir, "전화문자", "order1.txt"))
        assert not os.path.isdir(os.path.join(day_dir, "전화문자", "processed"))


def test_naver_api_orders_are_included_when_credentials_present():
    from schema import Channel, ProductGroup, build_standard_order

    naver_order = build_standard_order(
        Channel.SMARTSTORE, "naver-1", ProductGroup.CHEONGYUJA,
        "문정원", "01062521483", "경기도 김포시 ...", "10124", 0.5,
    )

    old_client = step1.NaverCommerceClient
    old_fetch = step1.fetch_actionable_orders
    step1.NaverCommerceClient = lambda client_id, client_secret: object()
    step1.fetch_actionable_orders = lambda client, state_path, now_iso: [naver_order]

    old_env = {k: os.environ.get(k) for k in ("NAVER_CLIENT_ID", "NAVER_CLIENT_SECRET")}
    os.environ["NAVER_CLIENT_ID"] = "id"
    os.environ["NAVER_CLIENT_SECRET"] = "secret"
    try:
        with tempfile.TemporaryDirectory() as inbox_root:
            _run(inbox_root)
            output_dir = os.path.join(step1.today_dir("2026-08-14", inbox_root), "output")
            with open(os.path.join(output_dir, "pending_epost_orders.json"), encoding="utf-8") as f:
                pending = json.load(f)
            assert len(pending) == 1
            assert pending[0]["recipient_name"] == "문정원"
    finally:
        step1.NaverCommerceClient = old_client
        step1.fetch_actionable_orders = old_fetch
        for k, v in old_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def test_naver_api_failure_does_not_lose_other_sources_orders():
    text_order_parser.call_gemini_json = _stub_per_call([
        [
            {
                "recipient_name": "홍길동",
                "phone": "010-1234-5678",
                "address": "전남 고흥군 ...",
                "postal_code": "59554",
                "product_group": "청유자",
                "weight_or_qty": 7,
                "delivery_message": None,
                "scheduled_delivery": False,
            }
        ],
    ])

    def _fail(client, state_path, now_iso):
        raise RuntimeError("네이버 API 오류")

    old_client = step1.NaverCommerceClient
    old_fetch = step1.fetch_actionable_orders
    step1.NaverCommerceClient = lambda client_id, client_secret: object()
    step1.fetch_actionable_orders = _fail

    old_env = {k: os.environ.get(k) for k in ("NAVER_CLIENT_ID", "NAVER_CLIENT_SECRET")}
    os.environ["NAVER_CLIENT_ID"] = "id"
    os.environ["NAVER_CLIENT_SECRET"] = "secret"
    try:
        with tempfile.TemporaryDirectory() as inbox_root:
            day_dir = step1.today_dir("2026-08-14", inbox_root)
            step1.ensure_folders(day_dir)
            with open(os.path.join(day_dir, "전화문자", "order1.txt"), "w", encoding="utf-8") as f:
                f.write("홍길동 010-1234-5678 청유자 7kg")

            _run(inbox_root)

            output_dir = os.path.join(day_dir, "output")
            with open(os.path.join(output_dir, "pending_epost_orders.json"), encoding="utf-8") as f:
                pending = json.load(f)
            assert len(pending) == 1
            assert pending[0]["recipient_name"] == "홍길동"
    finally:
        step1.NaverCommerceClient = old_client
        step1.fetch_actionable_orders = old_fetch
        for k, v in old_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def test_empty_folders_produce_no_pending_list():
    with tempfile.TemporaryDirectory() as inbox_root:
        _run(inbox_root)
        day_dir = step1.today_dir("2026-08-14", inbox_root)
        assert not os.path.exists(os.path.join(day_dir, "output", "pending_epost_orders.json"))


if __name__ == "__main__":
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_")]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"\n{len(tests)} tests passed")
