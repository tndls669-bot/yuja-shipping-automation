"""누적 판매 현황을 정적 HTML 대시보드(품목군별 탭)로 렌더링.

data/cumulative_data.json(결정론적으로 재계산된 값)을 읽어 매번 새로 그린다.
챗봇 대화 기억에 의존하지 않으므로 열 때마다 실제 처리 기록과 100% 일치한다.
"""
import html
import json
import os
from datetime import date, datetime

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CUMULATIVE_PATH = os.path.join(_BASE_DIR, "data", "cumulative_data.json")
_DASHBOARD_PATH = os.path.join(_BASE_DIR, "data", "output", "dashboard.html")

_PLATFORM_LABELS = {"스마트스토어": "스마트스토어", "위탁판매자": "위탁판매자", "전화문자": "전화/문자"}
_TIER_LABELS = ["1kg", "3kg(4kg박스)", "8kg"]

_ICONS = {
    "overview": """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6">
        <rect x="3.5" y="3.5" width="17" height="17" rx="1"/>
        <path d="M3.5 9.5h17M9 3.5v17"/></svg>""",
    "cheongyuja": """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6">
        <path d="M12 4c4.4 0 7 3.3 7 7.5S16.4 20 12 20s-7-3.8-7-8.5S7.6 4 12 4Z"/>
        <path d="M12 4c-1.6 2-1.6 12.5 0 16M8.2 7.5c1.6 1 6 1 7.6 0M7.3 15c2.4 1.3 7 1.3 9.4 0"/></svg>""",
    "yuja": """<svg viewBox="0 0 24 24" fill="currentColor" stroke="none">
        <path d="M12 4c4.4 0 7 3.3 7 7.5S16.4 20 12 20s-7-3.8-7-8.5S7.6 4 12 4Z" opacity="0.9"/>
        <path d="M12 2.2c.7 0 1.7.7 1.9 1.8-1.2-.3-2.6-.3-3.8 0 .2-1.1 1.2-1.8 1.9-1.8Z"/></svg>""",
    "yujacheong": """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6">
        <path d="M9.5 3.5h5M10 3.5v2.8L7.3 9.6a2 2 0 0 0-.4 1.2v7.7a2 2 0 0 0 2 2h6.2a2 2 0 0 0 2-2v-7.7a2 2 0 0 0-.4-1.2L14 6.3V3.5"/>
        <path d="M7 14.5h10"/></svg>""",
}


def _fmt(n) -> str:
    if isinstance(n, float) and n.is_integer():
        n = int(n)
    return f"{n:,}" if isinstance(n, int) else f"{n:,.2f}".rstrip("0").rstrip(".")


def _bars(items: dict, color_var: str) -> str:
    max_val = max(items.values()) if items and max(items.values()) > 0 else 1
    rows = []
    for label, value in items.items():
        pct = round((value / max_val) * 100) if max_val else 0
        rows.append(f"""
        <div class="bar-row">
          <span class="bar-label">{html.escape(label)}</span>
          <div class="bar-track"><div class="bar-fill" style="width:{pct}%;background:{color_var}"></div></div>
          <span class="bar-value">{_fmt(value)}</span>
        </div>""")
    return "".join(rows) or '<p class="empty-note">아직 데이터가 없습니다.</p>'


def _stat(label: str, value, unit: str = "") -> str:
    return f"""<div class="stat">
      <div class="stat-label">{html.escape(label)}</div>
      <div class="stat-value">{_fmt(value)}<span class="stat-unit">{html.escape(unit)}</span></div>
    </div>"""


def _trend_container(tab_key: str) -> str:
    return f"""
    <div class="panel trend-panel">
      <h2>일자별 추이</h2>
      <div class="trend-chart-wrap" data-trend-tab="{tab_key}"></div>
    </div>"""


def _overview_panel(state: dict, days_in: int) -> str:
    platform_items = {_PLATFORM_LABELS.get(k, k): v for k, v in state["cumulative_by_platform"].items()}
    return f"""
    <div class="stat-strip">
      {_stat("총 판매 중량", state['total_sales_weight_kg'], "kg")}
      {_stat("총 처리 건수", state['total_sales_units'], "건")}
      {_stat("시즌 경과", days_in, "일")}
    </div>
    {_trend_container("overview")}
    <div class="panel">
      <h2>플랫폼별 누적</h2>
      {_bars(platform_items, "var(--ink-muted)")}
    </div>"""


def _raw_product_panel(state: dict, product: str, tab_key: str, color_var: str) -> str:
    count = state["cumulative_by_product"].get(product, 0)
    weight = state["cumulative_weight_by_product"].get(product, 0)
    tiers = state["cumulative_by_weight_tier_by_product"].get(product, {})
    tiers_ordered = {k: tiers.get(k, 0) for k in _TIER_LABELS}
    return f"""
    <div class="stat-strip stat-strip-2">
      {_stat("누적 판매 중량", weight, "kg")}
      {_stat("누적 건수", count, "건")}
    </div>
    {_trend_container(tab_key)}
    <div class="panel">
      <h2>박스 중량대별 누적</h2>
      {_bars(tiers_ordered, color_var)}
    </div>"""


def _yujacheong_panel(state: dict, color_var: str) -> str:
    count = state["cumulative_by_product"].get("유자청", 0)
    by_product = state["cumulative_by_yujacheong_product"]
    return f"""
    <div class="stat-strip stat-strip-2">
      {_stat("누적 판매 병수", count, "병")}
      {_stat("제품 종류", len([v for v in by_product.values() if v > 0]), f"/ {len(by_product)}종")}
    </div>
    {_trend_container("yujacheong")}
    <div class="panel">
      <h2>제품별 누적</h2>
      {_bars(by_product, color_var)}
    </div>"""


def _trend_series_json(trend: list) -> str:
    series_by_tab = {
        "overview": [{"date": row["date"], "value": row["total"]} for row in trend],
        "cheongyuja": [{"date": row["date"], "value": row.get("청유자", 0)} for row in trend],
        "yuja": [{"date": row["date"], "value": row.get("유자", 0)} for row in trend],
        "yujacheong": [{"date": row["date"], "value": row.get("유자청", 0)} for row in trend],
    }
    return json.dumps(series_by_tab, ensure_ascii=False)


def render_dashboard_html(state: dict, trend: list = None, generated_at: datetime = None) -> str:
    generated_at = generated_at or datetime.now()
    trend = trend or []
    season_start = date.fromisoformat(state["season_start_date"])
    days_in = max((date.today() - season_start).days + 1, 0)

    tabs = [
        ("overview", "전체", "var(--ink)", _overview_panel(state, days_in)),
        ("cheongyuja", "청유자", "var(--green)", _raw_product_panel(state, "청유자", "cheongyuja", "var(--green)")),
        ("yuja", "유자", "var(--gold)", _raw_product_panel(state, "유자", "yuja", "var(--gold)")),
        ("yujacheong", "유자청", "var(--amber)", _yujacheong_panel(state, "var(--amber)")),
    ]

    tab_buttons = "".join(
        f"""<button class="tab-btn{' active' if i == 0 else ''}" data-tab="{key}"
              style="--tab-accent:{accent}" role="tab" aria-selected="{'true' if i == 0 else 'false'}">
          <span class="tab-icon">{_ICONS[key]}</span>{html.escape(label)}
        </button>"""
        for i, (key, label, accent, _panel) in enumerate(tabs)
    )
    tab_panels = "".join(
        f'<section class="tab-panel{" active" if i == 0 else ""}" data-panel="{key}">{panel}</section>'
        for i, (key, _label, _accent, panel) in enumerate(tabs)
    )

    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>유자 누적 판매 현황</title>
<style>
:root {{
  --bg: #efeedf;
  --surface: #fbfaf1;
  --ink: #23241a;
  --ink-muted: #6e6c56;
  --line: #dad6be;
  --green: #4b7a3d;
  --gold: #b9821a;
  --amber: #a9631b;
  --radius: 4px;
}}
@media (prefers-color-scheme: dark) {{
  :root {{
    --bg: #14170f; --surface: #1d2116; --ink: #eeead8; --ink-muted: #a7a386; --line: #33362a;
    --green: #7fb466; --gold: #f2b93d; --amber: #d08a3e;
  }}
}}
:root[data-theme="dark"] {{
  --bg: #14170f; --surface: #1d2116; --ink: #eeead8; --ink-muted: #a7a386; --line: #33362a;
  --green: #7fb466; --gold: #f2b93d; --amber: #d08a3e;
}}
:root[data-theme="light"] {{
  --bg: #efeedf; --surface: #fbfaf1; --ink: #23241a; --ink-muted: #6e6c56; --line: #dad6be;
  --green: #4b7a3d; --gold: #b9821a; --amber: #a9631b;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font-family: -apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", "Malgun Gothic", "Segoe UI", sans-serif;
  padding: 32px 20px 60px;
}}
.wrap {{ max-width: 760px; margin: 0 auto; }}
.eyebrow {{
  font-family: ui-monospace, "SF Mono", "Cascadia Code", Consolas, monospace;
  font-size: 12px; letter-spacing: 0.14em; text-transform: uppercase; color: var(--ink-muted);
}}
h1 {{ font-size: 26px; font-weight: 700; margin: 6px 0 2px; text-wrap: balance; }}
.subline {{ color: var(--ink-muted); font-size: 14px; margin-bottom: 24px; }}

.tabs {{
  display: flex; gap: 6px; margin-bottom: 20px; border-bottom: 1px solid var(--line);
  overflow-x: auto;
}}
.tab-btn {{
  display: flex; align-items: center; gap: 7px;
  background: none; border: none; cursor: pointer;
  font: inherit; font-size: 14px; font-weight: 600; color: var(--ink-muted);
  padding: 9px 4px 11px; margin-bottom: -1px;
  border-bottom: 2px solid transparent;
  white-space: nowrap;
  transition: color 0.15s ease, border-color 0.15s ease;
}}
.tab-btn .tab-icon {{ width: 17px; height: 17px; display: inline-flex; opacity: 0.75; }}
.tab-btn:hover {{ color: var(--ink); }}
.tab-btn.active {{ color: var(--tab-accent); border-bottom-color: var(--tab-accent); }}
.tab-btn.active .tab-icon {{ opacity: 1; }}
.tab-btn:focus-visible {{ outline: 2px solid var(--tab-accent); outline-offset: 2px; }}

.tab-panel {{ display: none; }}
.tab-panel.active {{ display: block; animation: rise 0.28s ease both; }}
@media (prefers-reduced-motion: reduce) {{ .tab-panel.active {{ animation: none; }} }}
@keyframes rise {{ from {{ opacity: 0; transform: translateY(6px); }} to {{ opacity: 1; transform: none; }} }}

.stat-strip {{
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 1px;
  background: var(--line); border: 1px solid var(--line); border-radius: var(--radius);
  overflow: hidden; margin-bottom: 16px;
}}
.stat-strip-2 {{ grid-template-columns: repeat(2, 1fr); }}
.stat {{ background: var(--surface); padding: 16px 16px; }}
.stat-label {{
  font-family: ui-monospace, "SF Mono", Consolas, monospace; font-size: 11px;
  letter-spacing: 0.06em; text-transform: uppercase; color: var(--ink-muted); margin-bottom: 8px;
}}
.stat-value {{
  font-family: ui-monospace, "SF Mono", Consolas, monospace; font-variant-numeric: tabular-nums;
  font-size: 28px; font-weight: 600;
}}
.stat-unit {{ font-size: 13px; color: var(--ink-muted); margin-left: 3px; }}

.panel {{ background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius); padding: 16px 18px 18px; }}
.panel h2 {{
  font-size: 12px; font-weight: 700; letter-spacing: 0.05em; margin: 0 0 12px;
  color: var(--ink-muted); text-transform: uppercase;
}}
.bar-row {{ display: grid; grid-template-columns: 100px 1fr 48px; align-items: center; gap: 10px; padding: 7px 0; }}
.bar-label {{ font-size: 13px; }}
.bar-track {{ height: 8px; background: var(--bg); border: 1px solid var(--line); border-radius: 2px; overflow: hidden; }}
.bar-fill {{ height: 100%; transition: width 0.4s ease; }}
.bar-value {{ font-family: ui-monospace, "SF Mono", Consolas, monospace; font-variant-numeric: tabular-nums; font-size: 13px; text-align: right; }}
.empty-note {{ color: var(--ink-muted); font-size: 13px; margin: 4px 0; }}

.trend-panel {{ padding-bottom: 8px; }}
.trend-chart-wrap {{ position: relative; }}
.trend-svg {{ display: block; width: 100%; height: auto; overflow: visible; }}
.trend-grid {{ stroke: var(--line); stroke-width: 1; }}
.trend-axis-label {{ fill: var(--ink-muted); font-size: 10px; font-family: ui-monospace, "SF Mono", Consolas, monospace; }}
.trend-crosshair {{ stroke: var(--ink-muted); stroke-width: 1; opacity: 0; pointer-events: none; }}
.trend-endpoint-ring, .trend-hover-ring {{ stroke: var(--surface); stroke-width: 2; }}
.trend-tooltip {{
  position: absolute; top: 4px; transform: translateX(-50%);
  background: var(--ink); color: var(--surface);
  font-size: 12px; line-height: 1.4; padding: 6px 9px; border-radius: 3px;
  pointer-events: none; opacity: 0; white-space: nowrap;
  transition: opacity 0.1s ease;
}}
.trend-tooltip strong {{ font-family: ui-monospace, "SF Mono", Consolas, monospace; font-variant-numeric: tabular-nums; margin-right: 6px; }}
.trend-tooltip span {{ opacity: 0.75; }}

footer {{ margin-top: 24px; padding-top: 14px; border-top: 1px solid var(--line); font-size: 12px; color: var(--ink-muted); line-height: 1.6; }}
</style>
</head>
<body>
<div class="wrap">
  <div class="eyebrow">SOONSU YUJA · SEASON TRACKER</div>
  <h1>유자 누적 판매 현황</h1>
  <div class="subline">시즌 시작 {html.escape(state['season_start_date'])} · {days_in}일째</div>

  <div class="tabs" role="tablist">{tab_buttons}</div>
  {tab_panels}

  <footer>
    data/output 폴더의 실제 처리 기록에서 매번 새로 계산됩니다 (대화 기억에 의존하지 않음) · 생성 시각 {generated_at.strftime('%Y-%m-%d %H:%M')}
  </footer>
</div>
<script type="application/json" id="trend-data">{_trend_series_json(trend)}</script>
<script>
document.querySelectorAll('.tab-btn').forEach(function (btn) {{
  btn.addEventListener('click', function () {{
    document.querySelectorAll('.tab-btn').forEach(function (b) {{ b.classList.remove('active'); b.setAttribute('aria-selected', 'false'); }});
    document.querySelectorAll('.tab-panel').forEach(function (p) {{ p.classList.remove('active'); }});
    btn.classList.add('active');
    btn.setAttribute('aria-selected', 'true');
    document.querySelector('.tab-panel[data-panel="' + btn.dataset.tab + '"]').classList.add('active');
  }});
}});

(function () {{
  var SVG_NS = 'http://www.w3.org/2000/svg';
  var trendData = JSON.parse(document.getElementById('trend-data').textContent);
  var tabColors = {{ overview: 'var(--ink-muted)', cheongyuja: 'var(--green)', yuja: 'var(--gold)', yujacheong: 'var(--amber)' }};

  function renderTrendChart(root, series, color) {{
    var W = 640, H = 148, padL = 4, padR = 4, padT = 10, padB = 22;
    var innerW = W - padL - padR, innerH = H - padT - padB;
    var n = series.length;

    if (n === 0) {{
      var empty = document.createElement('p');
      empty.className = 'empty-note';
      empty.textContent = '아직 데이터가 없습니다.';
      root.appendChild(empty);
      return;
    }}

    var maxV = 1;
    series.forEach(function (d) {{ if (d.value > maxV) maxV = d.value; }});

    function xAt(i) {{ return n === 1 ? padL + innerW / 2 : padL + (i / (n - 1)) * innerW; }}
    function yAt(v) {{ return padT + innerH - (v / maxV) * innerH; }}

    var svg = document.createElementNS(SVG_NS, 'svg');
    svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
    svg.setAttribute('class', 'trend-svg');
    svg.setAttribute('preserveAspectRatio', 'none');

    [0, maxV].forEach(function (v) {{
      var line = document.createElementNS(SVG_NS, 'line');
      line.setAttribute('x1', padL); line.setAttribute('x2', W - padR);
      line.setAttribute('y1', yAt(v)); line.setAttribute('y2', yAt(v));
      line.setAttribute('class', 'trend-grid');
      svg.appendChild(line);
    }});

    var linePts = series.map(function (d, i) {{ return xAt(i) + ',' + yAt(d.value); }}).join(' ');
    var areaPts = xAt(0) + ',' + yAt(0) + ' ' + linePts + ' ' + xAt(n - 1) + ',' + yAt(0);

    var area = document.createElementNS(SVG_NS, 'polygon');
    area.setAttribute('points', areaPts);
    area.style.fill = color;
    area.style.opacity = '0.12';
    svg.appendChild(area);

    var poly = document.createElementNS(SVG_NS, 'polyline');
    poly.setAttribute('points', linePts);
    poly.setAttribute('fill', 'none');
    poly.style.stroke = color;
    poly.setAttribute('stroke-width', '2');
    poly.setAttribute('stroke-linejoin', 'round');
    poly.setAttribute('stroke-linecap', 'round');
    svg.appendChild(poly);

    var endRing = document.createElementNS(SVG_NS, 'circle');
    endRing.setAttribute('cx', xAt(n - 1)); endRing.setAttribute('cy', yAt(series[n - 1].value));
    endRing.setAttribute('r', 6); endRing.setAttribute('class', 'trend-endpoint-ring');
    endRing.style.fill = color;
    svg.appendChild(endRing);
    var endDot = document.createElementNS(SVG_NS, 'circle');
    endDot.setAttribute('cx', xAt(n - 1)); endDot.setAttribute('cy', yAt(series[n - 1].value));
    endDot.setAttribute('r', 4);
    endDot.style.fill = color;
    svg.appendChild(endDot);

    var firstLabel = document.createElementNS(SVG_NS, 'text');
    firstLabel.setAttribute('x', padL); firstLabel.setAttribute('y', H - 4);
    firstLabel.setAttribute('class', 'trend-axis-label');
    firstLabel.textContent = series[0].date.slice(5);
    svg.appendChild(firstLabel);

    var lastLabel = document.createElementNS(SVG_NS, 'text');
    lastLabel.setAttribute('x', W - padR); lastLabel.setAttribute('y', H - 4);
    lastLabel.setAttribute('text-anchor', 'end');
    lastLabel.setAttribute('class', 'trend-axis-label');
    lastLabel.textContent = series[n - 1].date.slice(5);
    svg.appendChild(lastLabel);

    var crosshair = document.createElementNS(SVG_NS, 'line');
    crosshair.setAttribute('y1', padT); crosshair.setAttribute('y2', H - padB);
    crosshair.setAttribute('class', 'trend-crosshair');
    svg.appendChild(crosshair);

    var hoverDot = document.createElementNS(SVG_NS, 'circle');
    hoverDot.setAttribute('r', 4); hoverDot.setAttribute('class', 'trend-hover-ring');
    hoverDot.style.fill = color; hoverDot.style.opacity = '0';
    svg.appendChild(hoverDot);

    var hit = document.createElementNS(SVG_NS, 'rect');
    hit.setAttribute('x', 0); hit.setAttribute('y', 0);
    hit.setAttribute('width', W); hit.setAttribute('height', H);
    hit.setAttribute('fill', 'transparent');
    svg.appendChild(hit);

    root.appendChild(svg);

    var tooltip = document.createElement('div');
    tooltip.className = 'trend-tooltip';
    root.appendChild(tooltip);

    function showAt(idx) {{
      var d = series[idx];
      crosshair.setAttribute('x1', xAt(idx)); crosshair.setAttribute('x2', xAt(idx));
      crosshair.style.opacity = '1';
      hoverDot.setAttribute('cx', xAt(idx)); hoverDot.setAttribute('cy', yAt(d.value));
      hoverDot.style.opacity = '1';
      tooltip.textContent = '';
      var strong = document.createElement('strong');
      strong.textContent = d.value + '건';
      var span = document.createElement('span');
      span.textContent = d.date;
      tooltip.appendChild(strong);
      tooltip.appendChild(span);
      tooltip.style.opacity = '1';
      tooltip.style.left = ((xAt(idx) / W) * 100) + '%';
    }}
    function hideTooltip() {{
      crosshair.style.opacity = '0';
      hoverDot.style.opacity = '0';
      tooltip.style.opacity = '0';
    }}
    function pointerToIndex(evt) {{
      var rect = svg.getBoundingClientRect();
      var clientX = evt.touches ? evt.touches[0].clientX : evt.clientX;
      var relX = ((clientX - rect.left) / rect.width) * W;
      var idx = Math.round(((relX - padL) / innerW) * (n - 1));
      return Math.max(0, Math.min(n - 1, idx));
    }}
    hit.addEventListener('pointermove', function (evt) {{ showAt(pointerToIndex(evt)); }});
    hit.addEventListener('pointerleave', hideTooltip);
    hit.addEventListener('focus', function () {{ showAt(n - 1); }});
    hit.addEventListener('blur', hideTooltip);
  }}

  document.querySelectorAll('.trend-chart-wrap').forEach(function (root) {{
    var tab = root.getAttribute('data-trend-tab');
    renderTrendChart(root, trendData[tab] || [], tabColors[tab]);
  }});
}})();
</script>
</body>
</html>"""


def write_dashboard(state: dict, trend: list = None, path: str = _DASHBOARD_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(render_dashboard_html(state, trend=trend))


if __name__ == "__main__":
    from cumulative_tracker import compute_daily_trend

    with open(_CUMULATIVE_PATH, "r", encoding="utf-8") as f:
        state = json.load(f)
    write_dashboard(state, trend=compute_daily_trend())
    print(f"대시보드 생성: {_DASHBOARD_PATH}")
