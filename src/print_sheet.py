"""우체국 접수 완료 후 A4 인쇄용 포장 시트를 렌더링.

접수 전 리포트가 아니라 접수 *후* 결과(운송장번호 포함)를 기준으로 만든다 — 포장대에서
이 종이를 보고 박스에 붙은 운송장과 대조하며 확인하는 용도라, 운송장번호 없이는 쓸모가
없기 때문이다. local_step2_epost_submit.run()이 접수 직후 자동으로 만든다.
"""
import html
import os
from datetime import datetime

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _row_html(idx: int, package, tracking_no: str, status: str) -> str:
    order = package.order
    note = order.delivery_message or ""
    note_cell = f'<td class="note">{html.escape(note)}</td>' if note else '<td class="note"></td>'
    failed = status != "접수완료"

    return f"""<tr class="{'has-note' if note else ''} {'failed' if failed else ''}">
      <td class="num">{idx}</td>
      <td>{html.escape(order.recipient_name)}</td>
      <td>{html.escape(order.phone)}</td>
      <td>{html.escape(package.label)}</td>
      <td class="num">{html.escape(tracking_no or '-')}</td>
      {note_cell}
      <td>{html.escape(status)}</td>
    </tr>"""


def _summary_html(entries: list) -> str:
    """포장 전에 종류별로 몇 개씩 필요한지 한눈에 보이는 개수 요약(접수완료 건만)."""
    from collections import Counter

    counts = Counter(p.label for p, _, status in entries if status == "접수완료")
    if not counts:
        return ""

    rows = "".join(
        f'<tr><td>{html.escape(label)}</td><td class="num">{count}개</td></tr>'
        for label, count in sorted(counts.items())
    )
    total = sum(counts.values())
    return f"""
  <table class="summary">
    <thead><tr><th>종류</th><th>수량</th></tr></thead>
    <tbody>
      {rows}
      <tr class="summary-total"><td>합계</td><td class="num">{total}개</td></tr>
    </tbody>
  </table>"""


def render_print_sheet_html(entries: list, today: str, generated_at: datetime = None) -> str:
    """entries: (package, tracking_no, status) 튜플 리스트."""
    generated_at = generated_at or datetime.now()
    note_count = sum(1 for p, _, _ in entries if p.order.delivery_message)
    fail_count = sum(1 for _, _, status in entries if status != "접수완료")
    summary = _summary_html(entries)

    rows = "".join(
        _row_html(i, p, tracking_no, status) for i, (p, tracking_no, status) in enumerate(entries, start=1)
    ) or '<tr><td colspan="7" class="empty">접수된 주문이 없습니다.</td></tr>'

    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>{html.escape(today)} 접수 완료 포장 시트</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 16px;
    font-family: "Malgun Gothic", "Apple SD Gothic Neo", sans-serif;
    color: #111; font-size: 12px;
  }}
  h1 {{ font-size: 18px; margin: 0 0 4px; }}
  .meta {{ font-size: 12px; color: #444; margin-bottom: 14px; }}
  .meta strong {{ color: #000; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th, td {{ border: 1px solid #999; padding: 5px 6px; text-align: left; vertical-align: top; }}
  th {{ background: #eee; font-size: 11px; }}
  td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  td.note {{ min-width: 90px; }}
  tr.has-note td.note {{ font-weight: 700; }}
  tr.has-note {{ background: #fff6da; }}
  tr.failed {{ background: #ffe3e3; }}
  td.empty {{ text-align: center; color: #666; padding: 20px; }}

  table.summary {{ width: auto; min-width: 280px; margin-bottom: 18px; }}
  table.summary th {{ background: #333; color: #fff; }}
  tr.summary-total td {{ font-weight: 700; background: #f0f0f0; }}

  @page {{ size: A4; margin: 12mm; }}
  @media print {{
    body {{ padding: 0; }}
    tr {{ page-break-inside: avoid; }}
    thead {{ display: table-header-group; }}
    table.summary {{ page-break-after: always; }}
  }}
</style>
</head>
<body>
  <h1>{html.escape(today)} 접수 완료 포장 시트</h1>
  <div class="meta">
    총 <strong>{len(entries)}건</strong>
    / 요청사항 있는 건 <strong>{note_count}건</strong> (노란 행)
    {f'/ 접수 실패 <strong>{fail_count}건</strong> (빨간 행, 재시도 필요)' if fail_count else ''}
    &nbsp;·&nbsp; 출력 {generated_at.strftime('%Y-%m-%d %H:%M')}
  </div>
  {summary}
  <table>
    <thead>
      <tr>
        <th>#</th><th>받는사람</th><th>연락처</th><th>품목/박스</th>
        <th>운송장번호</th><th>특이사항</th><th>상태</th>
      </tr>
    </thead>
    <tbody>
      {rows}
    </tbody>
  </table>
</body>
</html>"""


def write_print_sheet(entries: list, today: str, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(render_print_sheet_html(entries, today))
