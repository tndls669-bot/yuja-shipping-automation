"""위탁판매자 이메일 자동 수집 — data/wholesale_senders.txt에 등록된 발신자 주소에서
온 새 이메일을 IMAP으로 가져와 본문(+엑셀 첨부파일)을 텍스트로 변환한다.

이미 처리한 메일은 data/processed_email_ids.json에 기록해두고 건너뛴다
(읽음/안읽음 표시에 의존하지 않음 — 사람이 먼저 열어봐도 중복 처리되지 않게).
"""
import email
import imaplib
import json
import os
import tempfile
from datetime import datetime, timedelta
from email.header import decode_header

from excel_reader import extract_text_from_xlsx
from network_compat import force_ipv4

_IMAP_HOST = "imap.gmail.com"

# 대표님 본인 메일 주소가 위탁판매/전화문자 발신자 목록에 등록되어 있으면, 이 시스템이
# 스스로 보낸 오더 리포트/접수 결과 메일까지 "새 주문"으로 다시 읽어버리는 무한 루프가
# 생긴다. 이 제목으로 시작하는 메일(자동 발송 리포트)은 항상 건너뛴다.
_AUTOMATION_SUBJECT_PREFIX = "[순수유자 발송자동화]"


def load_sender_list(path: str) -> list[str]:
    if not os.path.exists(path):
        return []
    senders = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                senders.append(line.lower())
    return senders


def _load_processed_ids(path: str) -> set:
    if not os.path.exists(path):
        return set()
    with open(path, "r", encoding="utf-8") as f:
        return set(json.load(f))


def _save_processed_ids(path: str, ids: set) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(sorted(ids), f, ensure_ascii=False, indent=2)


def _decode(value) -> str:
    if not value:
        return ""
    parts = decode_header(value)
    return "".join(
        part.decode(enc or "utf-8", errors="ignore") if isinstance(part, bytes) else part
        for part, enc in parts
    )


def _extract_body_and_excel_text(msg) -> str:
    body_parts = []
    excel_parts = []

    for part in msg.walk():
        disposition = part.get_content_disposition()

        if disposition == "attachment":
            filename = _decode(part.get_filename() or "")
            if filename.lower().endswith((".xlsx", ".xls")):
                payload = part.get_payload(decode=True)
                if payload:
                    suffix = os.path.splitext(filename)[1]
                    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                        tmp.write(payload)
                        tmp_path = tmp.name
                    try:
                        excel_parts.append(f"[첨부파일: {filename}]\n{extract_text_from_xlsx(tmp_path)}")
                    except Exception:
                        pass
                    finally:
                        os.remove(tmp_path)
            continue

        if part.get_content_type() == "text/plain" and disposition is None:
            payload = part.get_payload(decode=True)
            if payload:
                charset = part.get_content_charset() or "utf-8"
                body_parts.append(payload.decode(charset, errors="ignore"))

    return "\n\n".join(body_parts + excel_parts).strip()


def fetch_wholesale_emails(
    gmail_address: str,
    app_password: str,
    sender_list: list[str],
    processed_ids_path: str,
    since_days: int = 3,
) -> list[str]:
    if not sender_list:
        return []

    force_ipv4()
    processed_ids = _load_processed_ids(processed_ids_path)
    since_date = (datetime.now() - timedelta(days=since_days)).strftime("%d-%b-%Y")

    new_texts = []
    newly_processed = set()

    imap = imaplib.IMAP4_SSL(_IMAP_HOST)
    try:
        imap.login(gmail_address, app_password)
        imap.select("INBOX", readonly=True)

        for sender in sender_list:
            status, data = imap.search(None, f'(FROM "{sender}" SINCE "{since_date}")')
            if status != "OK":
                continue
            for num in data[0].split():
                status, msg_data = imap.fetch(num, "(RFC822)")
                if status != "OK" or not msg_data or not msg_data[0]:
                    continue
                msg = email.message_from_bytes(msg_data[0][1])
                msg_id = msg.get("Message-ID", f"{sender}-{num.decode()}")
                if msg_id in processed_ids:
                    continue

                subject = _decode(msg.get("Subject", ""))
                if subject.startswith(_AUTOMATION_SUBJECT_PREFIX):
                    newly_processed.add(msg_id)
                    continue

                text = _extract_body_and_excel_text(msg)
                if text:
                    new_texts.append(f"[보낸사람: {sender}] [제목: {subject}]\n{text}")
                newly_processed.add(msg_id)
    finally:
        imap.logout()

    if newly_processed:
        _save_processed_ids(processed_ids_path, processed_ids | newly_processed)

    return new_texts
