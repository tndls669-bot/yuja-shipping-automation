"""1단계(노트북 전용) — 오늘 주문 처리.

data/inbox/{오늘날짜}/위탁판매, data/inbox/{오늘날짜}/전화문자 폴더에 넣어둔 파일(엑셀/텍스트)과
등록된 발신자 이메일(위탁판매자, 대표님 본인 문자용 메일)을 모두 읽어 표준 주문으로 파싱한다.

우체국 접수는 하지 않는다(2단계 local_step2_epost_submit.py 담당). 대신 접수 대기 목록을
data/inbox/{날짜}/output/pending_epost_orders.json에 저장해두고, 오늘 처리된 주문을
모두 정리한 "오더 리포트" 메일(CSV 첨부)을 보낸다.
"""
import json
import os
from datetime import date

from aggregate_log import append_packages
from courier_tier import orders_to_packages
from csv_export import write_orders_csv
from cumulative_tracker import compute_cumulative, compute_daily_trend, save_cumulative
from email_fetcher import fetch_wholesale_emails, load_sender_list
from email_sender import send_summary_email
from env_loader import load_env
from excel_reader import extract_text_from_xlsx
from generate_dashboard import write_dashboard
from schema import Channel, order_to_dict
from text_order_parser import parse_orders_from_text
from validation import validate_order

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_INBOX_ROOT = os.path.join(_BASE_DIR, "data", "inbox")
_CUMULATIVE_PATH = os.path.join(_BASE_DIR, "data", "cumulative_data.json")
_DASHBOARD_PATH = os.path.join(_BASE_DIR, "data", "output", "dashboard.html")
_SENDERS_PATH = os.path.join(_BASE_DIR, "data", "wholesale_senders.txt")
_PROCESSED_EMAIL_IDS_PATH = os.path.join(_BASE_DIR, "data", "processed_email_ids.json")
_PHONE_SENDERS_PATH = os.path.join(_BASE_DIR, "data", "phone_text_senders.txt")
_PROCESSED_PHONE_EMAIL_IDS_PATH = os.path.join(_BASE_DIR, "data", "processed_phone_email_ids.json")
_AGGREGATE_LOG_PATH = os.path.join(_BASE_DIR, "data", "aggregate_log.csv")

_SUBFOLDERS = [
    ("위탁판매", Channel.WHOLESALE, "wholesale"),
    ("전화문자", Channel.PHONE_TEXT, "phone"),
]


def today_dir(today: str, inbox_root: str = _INBOX_ROOT) -> str:
    return os.path.join(inbox_root, today)


def ensure_folders(day_dir: str) -> None:
    for name, _, _ in _SUBFOLDERS:
        os.makedirs(os.path.join(day_dir, name), exist_ok=True)
    os.makedirs(os.path.join(day_dir, "output"), exist_ok=True)


def _read_folder_text(folder: str) -> str:
    if not os.path.isdir(folder):
        return ""
    parts = []
    for name in sorted(os.listdir(folder)):
        path = os.path.join(folder, name)
        if not os.path.isfile(path):
            continue
        lower = name.lower()
        if lower.endswith((".xlsx", ".xls")):
            try:
                parts.append(f"[파일: {name}]\n{extract_text_from_xlsx(path)}")
            except Exception:
                continue
        elif lower.endswith(".txt"):
            with open(path, "r", encoding="utf-8") as f:
                text = f.read().strip()
            if text:
                parts.append(f"[파일: {name}]\n{text}")
    return "\n\n".join(parts)


def _archive_folder(folder: str) -> None:
    if not os.path.isdir(folder):
        return
    processed_dir = os.path.join(folder, "processed")
    os.makedirs(processed_dir, exist_ok=True)
    for name in os.listdir(folder):
        src = os.path.join(folder, name)
        if os.path.isfile(src):
            os.replace(src, os.path.join(processed_dir, name))


def _fetch_email_texts(senders_path: str, processed_ids_path: str) -> list[str]:
    gmail_address = os.environ.get("GMAIL_ADDRESS")
    app_password = os.environ.get("GMAIL_APP_PASSWORD")
    if not gmail_address or not app_password:
        return []
    sender_list = load_sender_list(senders_path)
    if not sender_list:
        return []
    return fetch_wholesale_emails(gmail_address, app_password, sender_list, processed_ids_path)


def _save_pending(output_dir: str, orders: list) -> None:
    if not orders:
        return
    path = os.path.join(output_dir, "pending_epost_orders.json")
    existing = []
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            existing = json.load(f)
    existing.extend(order_to_dict(o) for o in orders)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)


def _update_cumulative_and_dashboard(log_path: str, cumulative_path: str, dashboard_path: str) -> dict:
    if os.path.exists(cumulative_path):
        with open(cumulative_path, "r", encoding="utf-8") as f:
            season_start_date = json.load(f)["season_start_date"]
    else:
        season_start_date = os.environ.get("SEASON_START_DATE") or date.today().isoformat()

    state = compute_cumulative(season_start_date, log_path=log_path)
    save_cumulative(state, path=cumulative_path)
    trend = compute_daily_trend(log_path=log_path)
    write_dashboard(state, trend=trend, path=dashboard_path)
    return state


def _build_report(today: str, ok_orders: list, issue_orders: list, cumulative_state: dict) -> str:
    if not ok_orders and not issue_orders:
        return f"[{today}] 오늘 처리할 주문이 없습니다."

    lines = [f"[{today}] 오더 리포트 — 정상 {len(ok_orders)}건, 확인필요 {len(issue_orders)}건", ""]

    if ok_orders:
        lines.append(f"■ 정상건 ({len(ok_orders)}건, 우체국 접수 대기 중 — 2단계 접수 확정 필요)")
        for o in ok_orders:
            product = o.product_group.value if o.product_group else "?"
            detail = f" {o.product_detail}" if o.product_detail else ""
            lines.append(
                f"  - {o.recipient_name} ({o.channel.value}) / {product}{detail} / "
                f"{o.box_composition} / {o.address} {o.address_detail}".strip()
            )
        lines.append("")

    if issue_orders:
        lines.append(f"■ 확인필요건 ({len(issue_orders)}건, 접수 대기 목록에서 제외됨)")
        for order, issues in issue_orders:
            lines.append(f"  - {order.original_order_id} ({order.recipient_name or '이름없음'}): {', '.join(issues)}")
        lines.append("")

    lines.append(
        f"■ 시즌 누적 (시작일 {cumulative_state['season_start_date']})\n"
        f"  총 {cumulative_state['total_sales_weight_kg']:g}kg / {cumulative_state['total_sales_units']}건"
    )
    return "\n".join(lines)


def run(
    api_key: str,
    today: str = None,
    inbox_root: str = _INBOX_ROOT,
    send_email: bool = True,
    senders_path: str = _SENDERS_PATH,
    processed_email_ids_path: str = _PROCESSED_EMAIL_IDS_PATH,
    phone_senders_path: str = _PHONE_SENDERS_PATH,
    processed_phone_email_ids_path: str = _PROCESSED_PHONE_EMAIL_IDS_PATH,
    log_path: str = _AGGREGATE_LOG_PATH,
    cumulative_path: str = _CUMULATIVE_PATH,
    dashboard_path: str = _DASHBOARD_PATH,
) -> None:
    today = today or date.today().isoformat()
    day_dir = today_dir(today, inbox_root)
    ensure_folders(day_dir)
    output_dir = os.path.join(day_dir, "output")

    all_orders = []
    for subfolder, channel, prefix in _SUBFOLDERS:
        folder = os.path.join(day_dir, subfolder)
        text = _read_folder_text(folder)
        if not text:
            continue
        orders = parse_orders_from_text(text, channel, f"{prefix}-{today.replace('-', '')}", api_key=api_key)
        all_orders.extend(orders)
        _archive_folder(folder)

    wholesale_texts = _fetch_email_texts(senders_path, processed_email_ids_path)
    for i, text in enumerate(wholesale_texts, start=1):
        orders = parse_orders_from_text(
            text, Channel.WHOLESALE, f"wholesale-{today.replace('-', '')}-mail{i:03d}", api_key=api_key
        )
        all_orders.extend(orders)

    phone_texts = _fetch_email_texts(phone_senders_path, processed_phone_email_ids_path)
    for i, text in enumerate(phone_texts, start=1):
        orders = parse_orders_from_text(
            text, Channel.PHONE_TEXT, f"phone-{today.replace('-', '')}-mail{i:03d}", api_key=api_key
        )
        all_orders.extend(orders)

    ok_orders, issue_orders = [], []
    for order in all_orders:
        issues = validate_order(order)
        if issues:
            issue_orders.append((order, issues))
        else:
            ok_orders.append(order)

    orders_csv_path = os.path.join(output_dir, f"{today}_orders.csv")
    if all_orders:
        if ok_orders:
            write_orders_csv(ok_orders, orders_csv_path, append=True)
        if issue_orders:
            write_orders_csv([o for o, _ in issue_orders], os.path.join(output_dir, f"{today}_issues.csv"), append=True)

    if ok_orders:
        append_packages(orders_to_packages(ok_orders), today, log_path)
        _save_pending(output_dir, ok_orders)

    cumulative_state = _update_cumulative_and_dashboard(log_path, cumulative_path, dashboard_path)
    report = _build_report(today, ok_orders, issue_orders, cumulative_state)
    print(report)

    if send_email:
        gmail_address = os.environ.get("GMAIL_ADDRESS")
        app_password = os.environ.get("GMAIL_APP_PASSWORD")
        if gmail_address and app_password:
            attachments = [orders_csv_path] if ok_orders and os.path.exists(orders_csv_path) else None
            try:
                send_summary_email(
                    f"[순수유자 발송자동화] {today} 오더 리포트", report, gmail_address, app_password,
                    attachments=attachments,
                )
                print("  이메일 발송 완료")
            except Exception as e:
                print(f"  이메일 발송 실패: {e}")
        else:
            print("  (이메일 미발송: GMAIL_ADDRESS/GMAIL_APP_PASSWORD 미설정)")


if __name__ == "__main__":
    load_env(os.path.join(_BASE_DIR, ".env"))
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise SystemExit("GEMINI_API_KEY가 없습니다 (.env 파일 확인).")
    run(key)
