"""1단계(노트북 전용) — 오늘 주문 처리.

data/inbox/{오늘날짜}/위탁판매, data/inbox/{오늘날짜}/전화문자 폴더에 넣어둔 파일(엑셀/텍스트)과
등록된 발신자 이메일(위탁판매자, 대표님 본인 문자용 메일)을 모두 읽어 표준 주문으로 파싱한다.

우체국 접수는 하지 않는다(2단계 local_step2_epost_submit.py 담당). 대신 오늘 처리된 주문을
data/inbox/{날짜}/output/{날짜}_orders.csv에 정리하고 "오더 리포트" 메일(같은 CSV 첨부)을
보낸다. 이 CSV가 곧 2단계의 접수 대상이므로, 대표님이 엑셀로 열어 주문을 합치거나 주소를
고치거나 특정 건을 지우면 2단계는 수정된 그대로 접수한다.
"""
import json
import os
from datetime import date, datetime
from typing import Optional

from aggregate_log import append_packages
from courier_tier import orders_to_packages
from csv_export import read_orders_csv, write_orders_csv
from cumulative_tracker import compute_cumulative, compute_daily_trend, save_cumulative
from email_fetcher import fetch_wholesale_emails, load_sender_list
from email_sender import send_summary_email
from env_loader import load_env
from excel_reader import extract_text_from_xlsx
from generate_dashboard import write_dashboard
from naver_commerce_api import NaverCommerceClient
from naver_order_api_import import fetch_actionable_orders
from schema import Channel, ProductGroup
from smartstore_excel_import import load_orders_from_encrypted_xlsx
from uglyus_order_import import parse_uglyus_table
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
_NAVER_API_STATE_PATH = os.path.join(_BASE_DIR, "data", "naver_api_state.json")

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


def _try_smartstore_import(path: str) -> Optional[list]:
    """네이버 스마트스토어 '선택주문발주발송관리' 암호화 엑셀이면 정확한 컬럼 매핑으로
    바로 StandardOrder 목록을 반환한다(AI 파싱 불필요). 이 형식이 아니면 None."""
    password = os.environ.get("SMARTSTORE_XLSX_PASSWORD", "123123")
    try:
        return load_orders_from_encrypted_xlsx(path, password)
    except Exception:
        return None


def _collect_folder(folder: str) -> tuple[list, str]:
    """폴더 안 파일을 훑어 (스마트스토어 주문 목록, 나머지 파일들의 텍스트 뭉치)로 나눈다."""
    if not os.path.isdir(folder):
        return [], ""
    smartstore_orders = []
    text_parts = []
    for name in sorted(os.listdir(folder)):
        path = os.path.join(folder, name)
        if not os.path.isfile(path):
            continue
        lower = name.lower()
        if lower.endswith((".xlsx", ".xls")):
            orders = _try_smartstore_import(path)
            if orders is not None:
                smartstore_orders.extend(orders)
                continue
            try:
                text_parts.append(f"[파일: {name}]\n{extract_text_from_xlsx(path)}")
            except Exception:
                continue
        elif lower.endswith(".txt"):
            with open(path, "r", encoding="utf-8") as f:
                text = f.read().strip()
            if text:
                text_parts.append(f"[파일: {name}]\n{text}")
    return smartstore_orders, "\n\n".join(text_parts)


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


_PRODUCT_SORT_ORDER = {ProductGroup.CHEONGYUJA: 0, ProductGroup.YUJA: 1, ProductGroup.YUJACHEONG: 2}


def _sort_key(order):
    return (
        _PRODUCT_SORT_ORDER.get(order.product_group, 99),
        order.product_detail or "",
        order.box_composition,
        order.recipient_name,
    )


def _build_product_totals(ok_orders: list) -> list:
    """준비(수확/계량)용 — 박스 종류 안 나누고 품목군 하나로만 합친 총량."""
    from collections import Counter

    order_counts = Counter()
    totals = Counter()
    for o in ok_orders:
        product = o.product_group.value if o.product_group else "?"
        order_counts[product] += 1
        if o.weight_or_qty:
            totals[product] += o.weight_or_qty

    lines = []
    for product in sorted(order_counts):
        unit = "병" if product == ProductGroup.YUJACHEONG.value else "kg"
        total = totals.get(product, 0)
        total_part = f" / 총 {total:g}{unit}" if total else ""
        lines.append(f"  - {product}: {order_counts[product]}건{total_part}")
    return lines


def _build_today_breakdown(ok_orders: list) -> list:
    from collections import Counter

    counts = Counter()
    weights = Counter()
    for o in ok_orders:
        product = o.product_group.value if o.product_group else "?"
        detail = f" {o.product_detail}" if o.product_detail else ""
        key = f"{product}{detail} / {o.box_composition or '-'}"
        counts[key] += 1
        if o.weight_or_qty and o.product_group in (ProductGroup.CHEONGYUJA, ProductGroup.YUJA):
            weights[key] += o.weight_or_qty

    lines = []
    for key in sorted(counts):
        w = weights.get(key, 0)
        w_part = f" (합계 {w:g}kg)" if w else ""
        lines.append(f"  - {key} × {counts[key]}건{w_part}")
    return lines


def _build_report(today: str, ok_orders: list, issue_orders: list, cumulative_state: dict, failed_sources: list = None) -> str:
    failed_sources = failed_sources or []

    if not ok_orders and not issue_orders:
        base = f"[{today}] 오늘 처리할 주문이 없습니다."
        if failed_sources:
            base += "\n\n⚠ 처리 실패한 소스 (재시도 필요):\n" + "\n".join(f"  - {f}" for f in failed_sources)
        return base

    lines = [f"[{today}] 오더 리포트 — 정상 {len(ok_orders)}건, 확인필요 {len(issue_orders)}건", ""]

    if ok_orders:
        lines.append("■ 오늘 주문 종류별 요약")
        lines.append("[품목별 합계 — 준비용]")
        lines.extend(_build_product_totals(ok_orders))
        lines.append("")
        lines.append("[박스 종류별 세부내역]")
        lines.extend(_build_today_breakdown(ok_orders))
        lines.append("")

    if ok_orders:
        lines.append(f"■ 정상건 ({len(ok_orders)}건, 우체국 접수 대기 중 — 2단계 접수 확정 필요, 종류별 정렬됨)")
        for o in ok_orders:
            product = o.product_group.value if o.product_group else "?"
            detail = f" {o.product_detail}" if o.product_detail else ""
            line = (
                f"  - {o.recipient_name} ({o.channel.value}) / {product}{detail} / "
                f"{o.box_composition} / {o.address} {o.address_detail}".strip()
            )
            if o.delivery_message:
                line += f" / ★요청사항: {o.delivery_message}"
            lines.append(line)
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

    if failed_sources:
        lines.append("")
        lines.append("⚠ 처리 실패한 소스 (재시도 필요):")
        lines.extend(f"  - {f}" for f in failed_sources)

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
    naver_api_state_path: str = _NAVER_API_STATE_PATH,
) -> None:
    today = today or date.today().isoformat()
    day_dir = today_dir(today, inbox_root)
    ensure_folders(day_dir)
    output_dir = os.path.join(day_dir, "output")

    # 소스 하나(예: Gemini 일시 장애)가 실패해도 이미 성공적으로 처리한 다른 소스의
    # 주문은 절대 유실되면 안 된다. 소스별로 개별 try/except로 감싸고, 성공한 소스만
    # 폴더 비우기(archive)를 하거나 다음 실행 때 재시도되도록 남겨둔다.
    all_orders = []
    failed_sources = []

    for subfolder, channel, prefix in _SUBFOLDERS:
        folder = os.path.join(day_dir, subfolder)
        smartstore_orders, text = _collect_folder(folder)
        try:
            text_orders = []
            if text:
                text_orders = parse_orders_from_text(
                    text, channel, f"{prefix}-{today.replace('-', '')}", api_key=api_key
                )
        except Exception as e:
            failed_sources.append(f"{subfolder} 폴더 텍스트 파싱 실패 (파일은 그대로 남겨둠, 다음 실행 때 재시도됨): {e}")
        else:
            for o in smartstore_orders:
                o.order_source = "네이버스마트스토어"
            for o in text_orders:
                o.order_source = channel.value
            if smartstore_orders:
                # 스마트스토어 엑셀은 이미 실제 주문번호/컬럼이 정확히 매핑되어 있어 AI 파싱이 불필요.
                all_orders.extend(smartstore_orders)
            all_orders.extend(text_orders)
            if smartstore_orders or text:
                _archive_folder(folder)

    run_id = datetime.now().strftime("%H%M%S")

    def _fetch_and_parse(senders_path_, processed_ids_path_, channel, prefix):
        entries = _fetch_email_texts(senders_path_, processed_ids_path_)
        for i, (label, text) in enumerate(entries, start=1):
            # 어글리어스 등 알려진 위탁판매자 주문서 표 형식이면 AI 파싱 없이 정확한
            # 컬럼 매핑으로 바로 처리한다(실제 주문번호를 정확히 잡아야 하기 때문).
            uglyus_orders = parse_uglyus_table(text)
            if uglyus_orders is not None:
                for o in uglyus_orders:
                    o.order_source = label
                all_orders.extend(uglyus_orders)
                continue
            try:
                orders = parse_orders_from_text(
                    text, channel, f"{prefix}-{today.replace('-', '')}-{run_id}{i:03d}", api_key=api_key
                )
            except Exception as e:
                # 메일은 이미 "처리됨"으로 표시돼 다시 못 읽어오므로, 원문을 잃지 않게 파일로 남긴다.
                # 이 저장 자체가 실패해도(디스크 오류 등) failed_sources 기록만은 반드시 남겨서
                # 주문이 아무 흔적 없이 조용히 사라지는 일이 없게 한다.
                recovery_path = os.path.join(output_dir, f"재처리필요_{prefix}_{run_id}{i:03d}.txt")
                try:
                    os.makedirs(output_dir, exist_ok=True)
                    with open(recovery_path, "w", encoding="utf-8") as f:
                        f.write(text)
                    failed_sources.append(f"메일 {i}번({prefix}, {label}) 파싱 실패 — 원문을 {recovery_path}에 저장함: {e}")
                except Exception as save_error:
                    failed_sources.append(
                        f"메일 {i}번({prefix}, {label}) 파싱 실패, 원문 저장도 실패({save_error}) — 원본 이메일은 이미 처리됨 표시됨: {e}"
                    )
            else:
                for o in orders:
                    o.order_source = label
                all_orders.extend(orders)

    _fetch_and_parse(senders_path, processed_email_ids_path, Channel.WHOLESALE, "wholesale")
    _fetch_and_parse(phone_senders_path, processed_phone_email_ids_path, Channel.PHONE_TEXT, "phone")

    naver_client_id = os.environ.get("NAVER_CLIENT_ID")
    naver_client_secret = os.environ.get("NAVER_CLIENT_SECRET")
    if naver_client_id and naver_client_secret:
        try:
            client = NaverCommerceClient(naver_client_id, naver_client_secret)
            now_iso = datetime.now().astimezone().isoformat(timespec="milliseconds")
            naver_orders = fetch_actionable_orders(client, naver_api_state_path, now_iso)
            all_orders.extend(naver_orders)
        except Exception as e:
            failed_sources.append(f"네이버 커머스API 주문 조회 실패 (다음 실행 때 자동 재시도됨): {e}")

    ok_orders, issue_orders = [], []
    for order in all_orders:
        issues = validate_order(order)
        if issues:
            issue_orders.append((order, issues))
        else:
            ok_orders.append(order)

    ok_orders.sort(key=_sort_key)
    issue_orders.sort(key=lambda pair: _sort_key(pair[0]))

    orders_csv_path = os.path.join(output_dir, f"{today}_orders.csv")
    issues_csv_path = os.path.join(output_dir, f"{today}_issues.csv")

    # 네이버 API처럼 매 실행마다 "아직 발송 안 된 건"을 통째로 다시 돌려주는 소스가 있어,
    # 오늘자 CSV에 이미 적힌 주문번호는 다시 쓰지 않는다 — 안 그러면 1단계를 하루에 여러 번
    # 돌릴 때마다 같은 주문이 중복으로 쌓이고, 대표님이 CSV에서 직접 합치거나 고친 내용도
    # 다음 실행 때 다시 겹쳐 써질 수 있다.
    already_ok_ids = {o.original_order_id for o in read_orders_csv(orders_csv_path)} if os.path.exists(orders_csv_path) else set()
    already_issue_ids = {o.original_order_id for o in read_orders_csv(issues_csv_path)} if os.path.exists(issues_csv_path) else set()
    new_ok_orders = [o for o in ok_orders if o.original_order_id not in already_ok_ids]
    new_issue_orders = [(o, iss) for o, iss in issue_orders if o.original_order_id not in already_issue_ids]

    if new_ok_orders:
        write_orders_csv(new_ok_orders, orders_csv_path, append=True)
    if new_issue_orders:
        write_orders_csv([o for o, _ in new_issue_orders], issues_csv_path, append=True)

    if new_ok_orders:
        append_packages(orders_to_packages(new_ok_orders), today, log_path)

    # 리포트는 이번 실행에서 새로 찾은 것만이 아니라, 오늘 CSV에 쌓인 전체 현황(대표님이
    # 엑셀로 직접 고친 내용 포함)을 그대로 보여준다.
    report_ok_orders = read_orders_csv(orders_csv_path) if os.path.exists(orders_csv_path) else []
    report_ok_orders.sort(key=_sort_key)

    cumulative_state = _update_cumulative_and_dashboard(log_path, cumulative_path, dashboard_path)
    report = _build_report(today, report_ok_orders, new_issue_orders, cumulative_state, failed_sources)
    print(report)

    if send_email:
        gmail_address = os.environ.get("GMAIL_ADDRESS")
        app_password = os.environ.get("GMAIL_APP_PASSWORD")
        if gmail_address and app_password:
            attachments = [orders_csv_path] if report_ok_orders and os.path.exists(orders_csv_path) else None
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
