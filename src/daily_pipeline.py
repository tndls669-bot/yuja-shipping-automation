"""매일 아침 실행하는 파이프라인.

두 가지 방식으로 주문을 입력받는다:
1. 로컬 파일 — data/inbox/wholesale.txt, data/inbox/phone_text.txt (이 컴퓨터에서 직접 붙여넣기)
2. 이메일 — data/wholesale_senders.txt / data/phone_text_senders.txt에 등록된 주소에서 온
   새 메일을 자동으로 읽어옴 (클라우드 실행 시 이 방식만 쓰게 됨 — 전화/문자 주문은
   대표님이 자신에게 보낸 메일로 인식)

전부 표준 스키마로 파싱 + 검증한 뒤, data/output/{날짜}_orders.csv(정상건)/
{날짜}_issues.csv(이상건)에 저장(개인정보 포함, 로컬/이메일 전용, 깃에는 안 올라감)하고,
개인정보 없는 집계만 data/aggregate_log.csv에 남겨(깃 커밋 대상) 누적 대시보드를 갱신한다.
"""
import os
import shutil
from datetime import date

import json

from aggregate_log import append_packages
from courier_tier import orders_to_packages
from csv_export import write_orders_csv
from cumulative_tracker import compute_cumulative, compute_daily_trend, save_cumulative
from email_fetcher import fetch_wholesale_emails, load_sender_list
from email_sender import send_summary_email
from env_loader import load_env
from generate_dashboard import write_dashboard
from schema import Channel
from text_order_parser import parse_orders_from_text
from validation import validate_order

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_INBOX_DIR = os.path.join(_BASE_DIR, "data", "inbox")
_PROCESSED_DIR = os.path.join(_INBOX_DIR, "processed")
_OUTPUT_DIR = os.path.join(_BASE_DIR, "data", "output")
_CUMULATIVE_PATH = os.path.join(_BASE_DIR, "data", "cumulative_data.json")
_DASHBOARD_PATH = os.path.join(_OUTPUT_DIR, "dashboard.html")
_SENDERS_PATH = os.path.join(_BASE_DIR, "data", "wholesale_senders.txt")
_PROCESSED_EMAIL_IDS_PATH = os.path.join(_BASE_DIR, "data", "processed_email_ids.json")
_PHONE_SENDERS_PATH = os.path.join(_BASE_DIR, "data", "phone_text_senders.txt")
_PROCESSED_PHONE_EMAIL_IDS_PATH = os.path.join(_BASE_DIR, "data", "processed_phone_email_ids.json")
_AGGREGATE_LOG_PATH = os.path.join(_BASE_DIR, "data", "aggregate_log.csv")

_SOURCES = [
    ("wholesale.txt", Channel.WHOLESALE, "wholesale"),
    ("phone_text.txt", Channel.PHONE_TEXT, "phone"),
]


def _read_inbox_file(inbox_dir: str, filename: str) -> str:
    path = os.path.join(inbox_dir, filename)
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def _archive_inbox_file(inbox_dir: str, filename: str, today: str) -> None:
    src = os.path.join(inbox_dir, filename)
    if not os.path.exists(src):
        return
    processed_dir = os.path.join(inbox_dir, "processed")
    os.makedirs(processed_dir, exist_ok=True)
    dst = os.path.join(processed_dir, f"{today}_{filename}")
    shutil.move(src, dst)


def _build_summary(today: str, all_orders, ok_orders, issue_orders, output_dir: str) -> str:
    if not all_orders:
        return f"[{today}] 오늘 처리할 주문이 없습니다 (data/inbox 폴더가 비어있음)."

    lines = [f"[{today}] 총 {len(all_orders)}건 처리 — 정상 {len(ok_orders)}건, 확인필요 {len(issue_orders)}건", ""]

    if ok_orders:
        lines.append(f"■ 정상건 ({len(ok_orders)}건) — {os.path.join(output_dir, f'{today}_orders.csv')}")
        for order in ok_orders:
            product = order.product_group.value if order.product_group else "?"
            lines.append(f"  - {order.recipient_name} / {product} / {order.box_composition}")
        lines.append("")

    if issue_orders:
        lines.append(f"■ 확인필요건 ({len(issue_orders)}건) — {os.path.join(output_dir, f'{today}_issues.csv')}")
        for order, issues in issue_orders:
            lines.append(f"  - {order.original_order_id} ({order.recipient_name or '이름없음'}): {', '.join(issues)}")

    return "\n".join(lines)


def _resolve_season_start_date(cumulative_path: str) -> str:
    if os.path.exists(cumulative_path):
        with open(cumulative_path, "r", encoding="utf-8") as f:
            return json.load(f)["season_start_date"]
    return os.environ.get("SEASON_START_DATE") or date.today().isoformat()


def _update_cumulative_and_dashboard(log_path: str, cumulative_path: str, dashboard_path: str) -> dict:
    season_start_date = _resolve_season_start_date(cumulative_path)
    state = compute_cumulative(season_start_date, log_path=log_path)
    save_cumulative(state, path=cumulative_path)
    trend = compute_daily_trend(log_path=log_path)
    write_dashboard(state, trend=trend, path=dashboard_path)
    return state


def _send_report(today: str, summary: str) -> None:
    gmail_address = os.environ.get("GMAIL_ADDRESS")
    app_password = os.environ.get("GMAIL_APP_PASSWORD")
    if not gmail_address or not app_password:
        print("  (이메일 미발송: GMAIL_ADDRESS/GMAIL_APP_PASSWORD 미설정)")
        return
    try:
        send_summary_email(f"[순수유자 발송자동화] {today} 처리 결과", summary, gmail_address, app_password)
        print("  이메일 발송 완료")
    except Exception as e:
        print(f"  이메일 발송 실패: {e}")


def _fetch_email_texts(senders_path: str, processed_ids_path: str) -> list[str]:
    """지정된 발신자 주소에서 온 새 메일 본문을 가져온다. 위탁판매자 이메일뿐 아니라
    (전화문자 채널처럼) 대표님이 자신에게 보낸 메일을 읽어올 때도 그대로 재사용한다."""
    gmail_address = os.environ.get("GMAIL_ADDRESS")
    app_password = os.environ.get("GMAIL_APP_PASSWORD")
    if not gmail_address or not app_password:
        return []
    sender_list = load_sender_list(senders_path)
    if not sender_list:
        return []
    return fetch_wholesale_emails(gmail_address, app_password, sender_list, processed_ids_path)


def run(
    api_key: str,
    inbox_dir: str = _INBOX_DIR,
    output_dir: str = _OUTPUT_DIR,
    send_email: bool = True,
    cumulative_path: str = _CUMULATIVE_PATH,
    dashboard_path: str = _DASHBOARD_PATH,
    senders_path: str = _SENDERS_PATH,
    processed_email_ids_path: str = _PROCESSED_EMAIL_IDS_PATH,
    phone_senders_path: str = _PHONE_SENDERS_PATH,
    processed_phone_email_ids_path: str = _PROCESSED_PHONE_EMAIL_IDS_PATH,
    log_path: str = _AGGREGATE_LOG_PATH,
    fetch_emails: bool = True,
) -> None:
    today = date.today().isoformat()
    today_compact = today.replace("-", "")
    all_orders = []

    for filename, channel, prefix in _SOURCES:
        text = _read_inbox_file(inbox_dir, filename)
        if not text:
            continue
        orders = parse_orders_from_text(text, channel, f"{prefix}-{today_compact}", api_key=api_key)
        all_orders.extend(orders)
        _archive_inbox_file(inbox_dir, filename, today)

    if fetch_emails:
        wholesale_texts = _fetch_email_texts(senders_path, processed_email_ids_path)
        for i, text in enumerate(wholesale_texts, start=1):
            orders = parse_orders_from_text(
                text, Channel.WHOLESALE, f"wholesale-{today_compact}-mail{i:03d}", api_key=api_key
            )
            all_orders.extend(orders)

        phone_texts = _fetch_email_texts(phone_senders_path, processed_phone_email_ids_path)
        for i, text in enumerate(phone_texts, start=1):
            orders = parse_orders_from_text(
                text, Channel.PHONE_TEXT, f"phone-{today_compact}-mail{i:03d}", api_key=api_key
            )
            all_orders.extend(orders)

    ok_orders = []
    issue_orders = []
    for order in all_orders:
        issues = validate_order(order)
        if issues:
            issue_orders.append((order, issues))
        else:
            ok_orders.append(order)

    if all_orders:
        os.makedirs(output_dir, exist_ok=True)
        if ok_orders:
            write_orders_csv(ok_orders, os.path.join(output_dir, f"{today}_orders.csv"), append=True)
        if issue_orders:
            write_orders_csv([o for o, _ in issue_orders], os.path.join(output_dir, f"{today}_issues.csv"), append=True)

    if ok_orders:
        append_packages(orders_to_packages(ok_orders), today, log_path)

    cumulative_state = _update_cumulative_and_dashboard(log_path, cumulative_path, dashboard_path)

    summary = _build_summary(today, all_orders, ok_orders, issue_orders, output_dir)
    summary += (
        f"\n\n■ 시즌 누적 (시작일 {cumulative_state['season_start_date']})\n"
        f"  총 {cumulative_state['total_sales_weight_kg']:g}kg / {cumulative_state['total_sales_units']}건\n"
        f"  대시보드: {dashboard_path}"
    )
    print(summary)
    if send_email:
        _send_report(today, summary)


if __name__ == "__main__":
    load_env(os.path.join(_BASE_DIR, ".env"))
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise SystemExit("GEMINI_API_KEY가 없습니다 (.env 파일 확인).")
    run(key)
