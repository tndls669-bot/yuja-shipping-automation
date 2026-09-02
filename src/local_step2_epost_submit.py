"""2단계(노트북 전용) — 우체국 접수 확정.

1단계(local_step1_process_orders.py)가 만든 오늘 주문 CSV(data/inbox/{날짜}/output/
{날짜}_orders.csv)를 읽어 실제 우체국 계약소포 API로 접수하고, 발급된 송장번호를
정리한 결과(CSV 첨부)를 메일로 보낸다. 이 CSV는 대표님이 엑셀로 직접 열어 주문을
합치거나 주소를 고치거나 특정 건을 빼고 저장할 수 있고, 2단계는 그 상태 그대로 접수한다.

이미 접수 결과 CSV({날짜}_epost_result.csv)에 "접수완료"로 기록된 주문번호는 자동으로
건너뛰므로, 하루에 여러 번 실행해도(1단계를 다시 돌려 새 주문이 추가된 경우 등) 중복
접수되지 않는다.

접수 직후 운송장번호가 포함된 A4 포장용 인쇄 시트({날짜}_print.html)도 같이 만들어
메일에 첨부한다 — 접수 전에는 운송장번호가 없어 쓸모가 없으므로, 이 인쇄 시트는 항상
접수 *후*에만 만들어진다.

위탁판매자(팔도맘/남해로부터 등) 채널 주문이 접수되면, wholesale_senders.txt에 등록된
그 업체 이메일로 운송장번호 안내 메일도 자동으로 보낸다 — 스마트스토어는 네이버 발송처리
API로 대체되지만, 위탁판매자는 그런 API가 없어 이메일 통보가 유일한 방법이기 때문이다.

실제 배송비가 발생하는 되돌릴 수 없는 동작이므로, 1단계의 오더 리포트를 먼저
확인한 뒤 대표님이 직접 이 스크립트를 실행해야 한다(자동 실행 아님).
"""
import csv
import os
from datetime import date

from courier_tier import Package, orders_to_packages
from csv_export import read_orders_csv
from email_sender import send_summary_email
from env_loader import load_env
from epost_api_client import insert_order
from epost_order_submit import package_to_order_params
from local_step1_process_orders import today_dir
from naver_commerce_api import NaverCommerceClient
from naver_dispatch_api import dispatch_orders
from naver_dispatch_export import write_naver_dispatch_excel
from print_sheet import write_print_sheet
from schema import Channel
from validation import validate_order
from uglyus_dispatch_export import write_uglyus_dispatch_excel

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_RESULT_HEADERS = ["원주문번호", "받는사람", "품목", "박스/구간", "송장번호", "상태"]


def _already_submitted_ids(result_csv: str) -> set:
    if not os.path.exists(result_csv):
        return set()
    with open(result_csv, "r", newline="", encoding="utf-8-sig") as f:
        return {row["원주문번호"] for row in csv.DictReader(f) if row.get("상태") == "접수완료"}


def _full_day_print_entries(output_dir: str, today: str) -> list:
    """포장은 이번 실행분만이 아니라 오늘 접수된 전체를 한 번에 봐야 하므로, 인쇄 시트는
    항상 오늘자 접수 결과 CSV 전체를 다시 읽어 만든다."""
    result_csv = os.path.join(output_dir, f"{today}_epost_result.csv")
    if not os.path.exists(result_csv):
        return []

    orders_by_id = {o.original_order_id: o for o in read_orders_csv(os.path.join(output_dir, f"{today}_orders.csv"))}

    entries = []
    with open(result_csv, "r", newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            order = orders_by_id.get(row["원주문번호"])
            if order is None:
                continue
            package = Package(order=order, label=row["품목"], tier=row["박스/구간"] or None)
            entries.append((package, row["송장번호"], row["상태"]))
    return entries


def _load_pending(output_dir: str, today: str) -> list:
    orders = read_orders_csv(os.path.join(output_dir, f"{today}_orders.csv"))
    done = _already_submitted_ids(os.path.join(output_dir, f"{today}_epost_result.csv"))
    return [o for o in orders if o.original_order_id not in done]


def run(today: str = None, send_email: bool = True) -> str:
    today = today or date.today().isoformat()
    output_dir = os.path.join(today_dir(today), "output")
    orders = _load_pending(output_dir, today)

    if not orders:
        msg = f"[{today}] 접수 대기 중인 주문이 없습니다. (1단계를 먼저 실행했는지, 이미 전부 접수되진 않았는지 확인하세요)"
        print(msg)
        return msg

    # 이 CSV는 대표님이 엑셀로 직접 손댈 수 있어(합치기/수정), 사람 실수로 값이 깨질 수
    # 있다 — 실제로 주소의 쉼표를 따옴표로 안 감싸서 중량 칸에 우편번호가 밀려들어가고,
    # 그 "15,621kg" 주문 하나가 실제로 1,954건 중복 접수된 사고가 있었다(2026-09-01).
    # 접수를 시도하기 전에 반드시 다시 한번 검증해서, 이상한 값은 API를 부르지 않고
    # 먼저 걸러낸다.
    validated = [(o, validate_order(o)) for o in orders]
    invalid = [(o, issues) for o, issues in validated if issues]
    orders = [o for o, issues in validated if not issues]

    if invalid:
        print(f"⚠ 데이터 이상으로 접수에서 제외됨 ({len(invalid)}건, 우체국 API 호출 안 함):")
        for o, issues in invalid:
            print(f"  - {o.original_order_id} ({o.recipient_name}): {', '.join(issues)}")
        print()

    if not orders:
        msg = f"[{today}] 접수 가능한 정상 주문이 없습니다 (전부 데이터 오류로 제외됨, 위 목록 확인 후 CSV 수정 필요)."
        print(msg)
        return msg

    auth_key = os.environ.get("EPOST_AUTH_KEY")
    security_key = os.environ.get("EPOST_SECURITY_KEY")
    cust_no = os.environ.get("EPOST_CUST_NO")
    appr_no = os.environ.get("EPOST_APPR_NO")
    office_ser = os.environ.get("EPOST_OFFICE_SER")
    order_comp_nm = os.environ.get("EPOST_ORDER_COMP_NM", "순수유자")
    if not all([auth_key, security_key, cust_no, appr_no, office_ser]):
        raise SystemExit("우체국 API 키(EPOST_*)가 .env에 설정되어 있지 않습니다.")

    rows = []
    submit_results = []
    error_count = 0
    for package in orders_to_packages(orders):
        params = package_to_order_params(package, cust_no, appr_no, office_ser, order_comp_nm)
        try:
            response = insert_order(auth_key, security_key, params)
            tracking_no = response.get("regiNo", "")
            if not tracking_no:
                # HTTP는 200으로 왔지만 송장번호가 없는 비정상 응답 — 성공으로 잘못
                # 표시하면 안 되니 실패로 취급한다.
                raise RuntimeError(f"송장번호 없이 응답이 왔습니다: {response}")
            rows.append([
                package.order.original_order_id, package.order.recipient_name, package.label,
                package.tier or "", tracking_no, "접수완료",
            ])
            submit_results.append((package, response))
        except Exception as e:
            error_count += 1
            rows.append([
                package.order.original_order_id, package.order.recipient_name, package.label,
                package.tier or "", "", f"실패: {e}",
            ])

    # 하루에 2단계를 여러 번 실행할 수 있으므로(추가 주문 등) 기존 결과를 덮어쓰지 않고 이어붙인다.
    result_csv = os.path.join(output_dir, f"{today}_epost_result.csv")
    write_header = not os.path.exists(result_csv)
    with open(result_csv, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(_RESULT_HEADERS)
        writer.writerows(rows)

    # 스마트스토어 채널은 가능하면 네이버 발송처리 API로 바로 등록한다(엑셀 업로드 불필요).
    # API가 실패하거나 키가 없으면 지금까지처럼 업로드용 엑셀로 대체(fallback)한다.
    naver_dispatched_ids = set()
    naver_dispatch_notes = []
    naver_client_id = os.environ.get("NAVER_CLIENT_ID")
    naver_client_secret = os.environ.get("NAVER_CLIENT_SECRET")
    smartstore_results = [(p, r) for p, r in submit_results if p.order.channel == Channel.SMARTSTORE]
    if naver_client_id and naver_client_secret and smartstore_results:
        try:
            client = NaverCommerceClient(naver_client_id, naver_client_secret)
            tracking_map = {p.order.original_order_id: r["regiNo"] for p, r in smartstore_results}
            dispatch_result = dispatch_orders(client, tracking_map)
            naver_dispatched_ids = set(dispatch_result["success_ids"])
            if naver_dispatched_ids:
                naver_dispatch_notes.append(f"네이버 발송처리 API로 {len(naver_dispatched_ids)}건 자동 등록 완료")
            if dispatch_result["fail_infos"]:
                naver_dispatch_notes.append(f"네이버 발송처리 일부 실패(엑셀로 대체): {dispatch_result['fail_infos']}")
        except Exception as e:
            naver_dispatch_notes.append(f"네이버 발송처리 API 호출 실패 (엑셀로 대체): {e}")

    print_sheet_path = os.path.join(output_dir, f"{today}_print.html")
    write_print_sheet(_full_day_print_entries(output_dir, today), today, print_sheet_path)

    attachments = [result_csv, print_sheet_path]
    naver_fallback_results = [(p, r) for p, r in smartstore_results if p.order.original_order_id not in naver_dispatched_ids]
    naver_xlsx = os.path.join(output_dir, f"{today}_네이버발송처리.xlsx")
    if write_naver_dispatch_excel(naver_fallback_results, naver_xlsx) > 0:
        attachments.append(naver_xlsx)
    uglyus_xlsx = os.path.join(output_dir, f"{today}_어글리어스송장등록.xlsx")
    if write_uglyus_dispatch_excel(submit_results, uglyus_xlsx) > 0:
        attachments.append(uglyus_xlsx)

    lines = [f"[{today}] 우체국 접수 결과 — 총 {len(rows)}건 (성공 {len(rows) - error_count}, 실패 {error_count})", ""]
    for r in rows:
        status = f" - {r[5]}" if r[5] != "접수완료" else ""
        lines.append(f"  - {r[1]} / {r[2]} / 송장번호: {r[4] or '(실패)'}{status}")
    if error_count:
        lines.append("")
        lines.append(f"⚠ {error_count}건 접수 실패 — 확인 후 재시도 필요")
    if naver_dispatch_notes:
        lines.append("")
        lines.extend(naver_dispatch_notes)
    if naver_xlsx in attachments:
        lines.append("")
        lines.append("네이버 스마트스토어 발주발송관리 > 엑셀 일괄발송에 첨부된 엑셀 파일을 그대로 업로드하세요.")
    if uglyus_xlsx in attachments:
        lines.append("")
        lines.append("어글리어스 송장 등록 페이지(메일/카톡으로 오는 링크)에 첨부된 엑셀 파일을 그대로 업로드하세요.")
    lines.append("")
    lines.append(f"포장용 A4 인쇄 시트: {print_sheet_path} (첨부파일, 브라우저로 열어 인쇄)")
    body = "\n".join(lines)
    print(body)

    if send_email:
        gmail_address = os.environ.get("GMAIL_ADDRESS")
        app_password = os.environ.get("GMAIL_APP_PASSWORD")
        if gmail_address and app_password:
            try:
                send_summary_email(
                    f"[순수유자 발송자동화] {today} 우체국 접수 결과", body, gmail_address, app_password,
                    attachments=attachments,
                )
                print("  이메일 발송 완료")
            except Exception as e:
                print(f"  이메일 발송 실패: {e}")
        else:
            print("  (이메일 미발송: GMAIL_ADDRESS/GMAIL_APP_PASSWORD 미설정)")

    return body


if __name__ == "__main__":
    load_env(os.path.join(_BASE_DIR, ".env"))
    run()
