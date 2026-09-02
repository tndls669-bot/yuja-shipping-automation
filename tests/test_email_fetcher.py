import email as email_module
import json
import os
import sys
import tempfile
from email.mime.text import MIMEText

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import email_fetcher  # noqa: E402


class _FakeImap:
    """imaplib.IMAP4_SSL을 흉내내는 최소 스텁 — 등록된 메시지 목록에서 검색/조회만 지원."""

    def __init__(self, messages):
        # messages: {sender: [MIMEText, ...]}
        self._messages = messages
        self._flat = []
        for sender, msgs in messages.items():
            for i, msg in enumerate(msgs):
                self._flat.append((sender, str(i).encode(), msg))

    def login(self, *args, **kwargs):
        pass

    def select(self, *args, **kwargs):
        pass

    def search(self, charset, query):
        nums = [num for sender, num, _ in self._flat if f'"{sender}"' in query]
        return "OK", [b" ".join(nums)]

    def fetch(self, num, spec):
        for sender, n, msg in self._flat:
            if n == num:
                return "OK", [(b"1", msg.as_bytes())]
        return "NO", None

    def logout(self):
        pass


def _make_msg(subject, body, msg_id):
    msg = MIMEText(body, _charset="utf-8")
    msg["Subject"] = subject
    msg["Message-ID"] = msg_id
    return msg


def test_automation_report_email_is_skipped_but_marked_processed():
    sender = "tndls669@gmail.com"
    messages = {
        sender: [
            _make_msg("[순수유자 발송자동화] 2026-08-25 오더 리포트", "정상건 목록...", "<report-1@gmail.com>"),
            _make_msg("오늘 문자 주문", "홍길동 010-1234-5678 청유자 3kg", "<order-1@gmail.com>"),
        ]
    }
    email_fetcher.imaplib.IMAP4_SSL = lambda host: _FakeImap(messages)

    with tempfile.TemporaryDirectory() as tmp:
        ids_path = os.path.join(tmp, "processed.json")
        entries = email_fetcher.fetch_wholesale_emails("me@gmail.com", "pw", [(sender, sender)], ids_path)

        assert len(entries) == 1
        assert "홍길동" in entries[0][1]
        assert "오더 리포트" not in "".join(text for _, text in entries)

        with open(ids_path, encoding="utf-8") as f:
            processed = json.load(f)
        assert "<report-1@gmail.com>" in processed
        assert "<order-1@gmail.com>" in processed


def test_second_run_does_not_refetch_already_processed_report():
    sender = "tndls669@gmail.com"
    messages = {sender: [_make_msg("[순수유자 발송자동화] 결과", "...", "<report-2@gmail.com>")]}
    email_fetcher.imaplib.IMAP4_SSL = lambda host: _FakeImap(messages)

    with tempfile.TemporaryDirectory() as tmp:
        ids_path = os.path.join(tmp, "processed.json")
        email_fetcher.fetch_wholesale_emails("me@gmail.com", "pw", [(sender, sender)], ids_path)
        entries = email_fetcher.fetch_wholesale_emails("me@gmail.com", "pw", [(sender, sender)], ids_path)
        assert entries == []


if __name__ == "__main__":
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_")]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"\n{len(tests)} tests passed")
