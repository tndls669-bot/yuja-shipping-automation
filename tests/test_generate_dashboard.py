import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from generate_dashboard import render_dashboard_html  # noqa: E402


def _sample_state():
    return {
        "season_start_date": "2026-08-01",
        "total_sales_units": 42,
        "total_sales_weight_kg": 187.5,
        "cumulative_by_product": {"청유자": 30, "유자": 0, "유자청": 12},
        "cumulative_weight_by_product": {"청유자": 187.5, "유자": 0},
        "cumulative_by_weight_tier": {"1kg": 10, "3kg(4kg박스)": 15, "8kg": 8},
        "cumulative_by_weight_tier_by_product": {
            "청유자": {"1kg": 10, "3kg(4kg박스)": 15, "8kg": 8},
            "유자": {"1kg": 0, "3kg(4kg박스)": 0, "8kg": 0},
        },
        "cumulative_by_platform": {"스마트스토어": 25, "위탁판매자": 10, "전화문자": 7},
        "cumulative_by_yujacheong_product": {"디오가닉": 5, "로우슈거": 4, "레몬첼로": 3},
    }


def test_render_includes_all_four_tabs():
    html_out = render_dashboard_html(_sample_state(), generated_at=datetime(2026, 8, 9, 9, 0))
    for tab_key in ("overview", "cheongyuja", "yuja", "yujacheong"):
        assert f'data-tab="{tab_key}"' in html_out
        assert f'data-panel="{tab_key}"' in html_out
    for label in ("전체", "청유자", "유자", "유자청"):
        assert label in html_out


def test_render_includes_yujacheong_product_breakdown():
    html_out = render_dashboard_html(_sample_state(), generated_at=datetime(2026, 8, 9, 9, 0))
    assert "디오가닉" in html_out
    assert "로우슈거" in html_out
    assert "레몬첼로" in html_out


def test_render_includes_key_numbers():
    html_out = render_dashboard_html(_sample_state(), generated_at=datetime(2026, 8, 9, 9, 0))
    assert "187.5" in html_out
    assert "42" in html_out
    assert "위탁판매자" in html_out
    assert "<html" in html_out and "</html>" in html_out


def _sample_trend():
    return [
        {"date": "2026-08-05", "total": 3, "청유자": 2, "유자": 0, "유자청": 1},
        {"date": "2026-08-06", "total": 5, "청유자": 3, "유자": 0, "유자청": 2},
        {"date": "2026-08-07", "total": 4, "청유자": 2, "유자": 0, "유자청": 2},
    ]


def test_render_embeds_trend_series_json():
    html_out = render_dashboard_html(_sample_state(), trend=_sample_trend(), generated_at=datetime(2026, 8, 9, 9, 0))
    assert 'id="trend-data"' in html_out
    assert "2026-08-05" in html_out
    assert 'data-trend-tab="overview"' in html_out
    assert 'data-trend-tab="cheongyuja"' in html_out
    assert 'data-trend-tab="yuja"' in html_out
    assert 'data-trend-tab="yujacheong"' in html_out


def test_render_with_no_trend_data_does_not_crash():
    html_out = render_dashboard_html(_sample_state(), trend=[], generated_at=datetime(2026, 8, 9, 9, 0))
    assert '"overview": []' in html_out or '"overview":[]' in html_out.replace(" ", "")


def test_render_handles_zero_state_without_crashing():
    state = {
        "season_start_date": "2026-08-09",
        "total_sales_units": 0,
        "total_sales_weight_kg": 0.0,
        "cumulative_by_product": {"청유자": 0, "유자": 0, "유자청": 0},
        "cumulative_weight_by_product": {"청유자": 0.0, "유자": 0.0},
        "cumulative_by_weight_tier": {"1kg": 0, "3kg(4kg박스)": 0, "8kg": 0},
        "cumulative_by_weight_tier_by_product": {
            "청유자": {"1kg": 0, "3kg(4kg박스)": 0, "8kg": 0},
            "유자": {"1kg": 0, "3kg(4kg박스)": 0, "8kg": 0},
        },
        "cumulative_by_platform": {"스마트스토어": 0, "위탁판매자": 0, "전화문자": 0},
        "cumulative_by_yujacheong_product": {"디오가닉": 0, "로우슈거": 0, "레몬첼로": 0},
    }
    html_out = render_dashboard_html(state)
    assert "<html" in html_out


if __name__ == "__main__":
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_")]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"\n{len(tests)} tests passed")
