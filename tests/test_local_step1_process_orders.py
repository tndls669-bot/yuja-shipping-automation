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
