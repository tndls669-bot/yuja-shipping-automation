import csv
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import daily_pipeline  # noqa: E402
import text_order_parser  # noqa: E402


def _stub_per_call(responses):
    calls = {"i": 0}

    def fake_call_gemini_json(prompt, api_key, model=None):
        result = responses[calls["i"]]
        calls["i"] += 1
        return result
    return fake_call_gemini_json


def _run(inbox_dir, output_dir, **kwargs):
    kwargs.setdefault("send_email", False)
    kwargs.setdefault("fetch_emails", False)
    kwargs.setdefault("cumulative_path", os.path.join(output_dir, "cumulative_data.json"))
    kwargs.setdefault("dashboard_path", os.path.join(output_dir, "dashboard.html"))
    kwargs.setdefault("log_path", os.path.join(output_dir, "aggregate_log.csv"))
    daily_pipeline.run("dummy-key", inbox_dir=inbox_dir, output_dir=output_dir, **kwargs)


def test_processes_both_channels_and_splits_ok_vs_issues():
    text_order_parser.call_gemini_json = _stub_per_call([
        [  # wholesale.txt -> 1 order, valid
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
        [  # phone_text.txt -> 1 order, missing address -> flagged
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

    with tempfile.TemporaryDirectory() as inbox_dir, tempfile.TemporaryDirectory() as output_dir:
        with open(os.path.join(inbox_dir, "wholesale.txt"), "w", encoding="utf-8") as f:
            f.write("위탁판매자 이메일 본문 예시")
        with open(os.path.join(inbox_dir, "phone_text.txt"), "w", encoding="utf-8") as f:
            f.write("전화문자 뭉치 예시")

        _run(inbox_dir, output_dir)

        output_files = os.listdir(output_dir)
        orders_file = [f for f in output_files if f.endswith("_orders.csv")][0]
        issues_file = [f for f in output_files if f.endswith("_issues.csv")][0]

        with open(os.path.join(output_dir, orders_file), encoding="utf-8-sig") as f:
            rows = list(csv.reader(f))
        assert rows[1][4] == "홍길동"

        with open(os.path.join(output_dir, issues_file), encoding="utf-8-sig") as f:
            rows = list(csv.reader(f))
        assert rows[1][4] == "박순자"

        assert not os.path.exists(os.path.join(inbox_dir, "wholesale.txt"))
        assert not os.path.exists(os.path.join(inbox_dir, "phone_text.txt"))
        assert len(os.listdir(os.path.join(inbox_dir, "processed"))) == 2

        assert os.path.exists(os.path.join(output_dir, "dashboard.html"))


def test_second_run_same_day_appends_instead_of_overwriting():
    text_order_parser.call_gemini_json = _stub_per_call([
        [
            {
                "recipient_name": "1차주문",
                "phone": "01011112222",
                "address": "주소1",
                "postal_code": "11111",
                "product_group": "유자청",
                "weight_or_qty": 1,
                "delivery_message": None,
                "scheduled_delivery": False,
            }
        ],
        [
            {
                "recipient_name": "2차주문",
                "phone": "01033334444",
                "address": "주소2",
                "postal_code": "22222",
                "product_group": "유자청",
                "weight_or_qty": 1,
                "delivery_message": None,
                "scheduled_delivery": False,
            }
        ],
    ])

    with tempfile.TemporaryDirectory() as inbox_dir, tempfile.TemporaryDirectory() as output_dir:
        with open(os.path.join(inbox_dir, "phone_text.txt"), "w", encoding="utf-8") as f:
            f.write("1차 텍스트")
        _run(inbox_dir, output_dir)

        with open(os.path.join(inbox_dir, "phone_text.txt"), "w", encoding="utf-8") as f:
            f.write("2차 텍스트 (같은 날 재실행)")
        _run(inbox_dir, output_dir)

        orders_file = [f for f in os.listdir(output_dir) if f.endswith("_orders.csv")][0]
        with open(os.path.join(output_dir, orders_file), encoding="utf-8-sig") as f:
            rows = list(csv.reader(f))

        names = [row[4] for row in rows[1:]]
        assert names == ["1차주문", "2차주문"]
        assert sum(1 for row in rows if row and row[0] == "채널구분") == 1


def test_sends_email_when_credentials_present():
    text_order_parser.call_gemini_json = _stub_per_call([
        [
            {
                "recipient_name": "홍길동",
                "phone": "01012345678",
                "address": "주소",
                "postal_code": "11111",
                "product_group": "유자청",
                "weight_or_qty": 1,
                "delivery_message": None,
                "scheduled_delivery": False,
            }
        ],
    ])

    sent = {}

    def fake_send(subject, body, gmail_address, app_password, to_addr=None):
        sent["subject"] = subject
        sent["body"] = body

    old_env = {k: os.environ.get(k) for k in ("GMAIL_ADDRESS", "GMAIL_APP_PASSWORD")}
    os.environ["GMAIL_ADDRESS"] = "test@gmail.com"
    os.environ["GMAIL_APP_PASSWORD"] = "fake-app-password"
    daily_pipeline.send_summary_email = fake_send

    try:
        with tempfile.TemporaryDirectory() as inbox_dir, tempfile.TemporaryDirectory() as output_dir:
            with open(os.path.join(inbox_dir, "phone_text.txt"), "w", encoding="utf-8") as f:
                f.write("텍스트")
            _run(inbox_dir, output_dir, send_email=True)
    finally:
        for k, v in old_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    assert "홍길동" in sent["body"]
    assert "순수유자" in sent["subject"]


def test_fetched_wholesale_emails_are_parsed_and_merged():
    text_order_parser.call_gemini_json = _stub_per_call([
        [
            {
                "recipient_name": "메일주문자",
                "phone": "01077778888",
                "address": "주소",
                "postal_code": "44444",
                "product_group": "청유자",
                "weight_or_qty": 2,
                "delivery_message": None,
                "scheduled_delivery": False,
            }
        ],
    ])

    daily_pipeline.load_sender_list = lambda path: ["seller@example.com"]
    daily_pipeline.fetch_wholesale_emails = lambda *a, **k: ["[보낸사람: seller@example.com] 주문 내용..."]

    old_env = {k: os.environ.get(k) for k in ("GMAIL_ADDRESS", "GMAIL_APP_PASSWORD")}
    os.environ["GMAIL_ADDRESS"] = "test@gmail.com"
    os.environ["GMAIL_APP_PASSWORD"] = "fake-app-password"

    try:
        with tempfile.TemporaryDirectory() as inbox_dir, tempfile.TemporaryDirectory() as output_dir:
            _run(inbox_dir, output_dir, fetch_emails=True)

            orders_file = [f for f in os.listdir(output_dir) if f.endswith("_orders.csv")][0]
            with open(os.path.join(output_dir, orders_file), encoding="utf-8-sig") as f:
                rows = list(csv.reader(f))
            assert rows[1][4] == "메일주문자"
            assert rows[1][1].startswith("wholesale-") and "mail001" in rows[1][1]
    finally:
        for k, v in old_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def test_empty_inbox_produces_dashboard_but_no_order_files():
    with tempfile.TemporaryDirectory() as inbox_dir, tempfile.TemporaryDirectory() as output_dir:
        _run(inbox_dir, output_dir)
        files = os.listdir(output_dir)
        assert not any(f.endswith("_orders.csv") or f.endswith("_issues.csv") for f in files)
        assert "dashboard.html" in files


if __name__ == "__main__":
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_")]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"\n{len(tests)} tests passed")
