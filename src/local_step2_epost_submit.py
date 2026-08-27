"""2단계(노트북 전용) — 우체국 접수 확정.

1단계(local_step1_process_orders.py)가 저장해둔 접수 대기 목록
(data/inbox/{날짜}/output/pending_epost_orders.json)을 실제 우체국 계약소포 API로
접수하고, 발급된 송장번호를 정리한 결과(CSV 첨부)를 메일로 보낸다.

실제 배송비가 발생하는 되돌릴 수 없는 동작이므로, 1단계의 오더 리포트를 먼저
확인한 뒤 대표님이 직접 이 스크립트를 실행해야 한다(자동 실행 아님).
"""
import csv
import json
import os
from datetime import date

from courier_tier import orders_to_packages
from email_sender import send_summary_email
from env_loader import load_env
from epost_api_client import insert_order
from epost_order_submit import package_to_order_params
from local_step1_process_orders import today_dir
from naver_dispatch_export import write_naver_dispatch_excel
from schema import order_from_dict
from uglyus_dispatch_export import write_uglyus_dispatch_excel

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_RESULT_HEADERS = ["원주문번호", "받는사람", "품목", "박스/구간", "송장번호", "상태"]


def _load_pending(output_dir: str) -> tuple[str, list]:
    path = os.path.join(output_dir, "pending_epost_orders.json")
    if not os.path.exists(path):
        return path, []
    with open(path, "r", encoding="utf-8") as f:
        return path, json.load(f)


def run(today: str = None, send_email: bool = True) -> str:
    today = today or date.today().isoformat()
    output_dir = os.path.join(today_dir(today), "output")
    pending_path, pending = _load_pending(output_dir)

    if not pending:
        msg = f"[{today}] 접수 대기 중인 주문이 없습니다. (1단계를 먼저 실행했는지 확인하세요)"
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

    orders = [order_from_dict(d) for d in pending]

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

    attachments = [result_csv]
    naver_xlsx = os.path.join(output_dir, f"{today}_네이버발송처리.xlsx")
    if write_naver_dispatch_excel(submit_results, naver_xlsx) > 0:
        attachments.append(naver_xlsx)
    uglyus_xlsx = os.path.join(output_dir, f"{today}_어글리어스송장등록.xlsx")
    if write_uglyus_dispatch_excel(submit_results, uglyus_xlsx) > 0:
        attachments.append(uglyus_xlsx)

    os.remove(pending_path)

    lines = [f"[{today}] 우체국 접수 결과 — 총 {len(rows)}건 (성공 {len(rows) - error_count}, 실패 {error_count})", ""]
    for r in rows:
        status = f" - {r[5]}" if r[5] != "접수완료" else ""
        lines.append(f"  - {r[1]} / {r[2]} / 송장번호: {r[4] or '(실패)'}{status}")
    if error_count:
        lines.append("")
        lines.append(f"⚠ {error_count}건 접수 실패 — 확인 후 재시도 필요")
    if naver_xlsx in attachments:
        lines.append("")
        lines.append("네이버 스마트스토어 발주발송관리 > 엑셀 일괄발송에 첨부된 엑셀 파일을 그대로 업로드하세요.")
    if uglyus_xlsx in attachments:
        lines.append("")
        lines.append("어글리어스 송장 등록 페이지(메일/카톡으로 오는 링크)에 첨부된 엑셀 파일을 그대로 업로드하세요.")
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
