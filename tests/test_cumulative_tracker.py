import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from aggregate_log import append_packages  # noqa: E402
from courier_tier import orders_to_packages  # noqa: E402
from cumulative_tracker import compute_cumulative, compute_daily_trend  # noqa: E402
from schema import Channel, ProductGroup, YujacheongProduct, build_standard_order  # noqa: E402


def _sample_orders():
    return [
        build_standard_order(
            Channel.WHOLESALE, "wholesale-001", ProductGroup.CHEONGYUJA,
            "홍길동", "01011112222", "주소1", "11111", 7,
        ),
        # 5kg는 3kg박스(4kg적재)+1kg박스(1kg적재) 2박스로 나뉜다 (box_calc 규칙)
        build_standard_order(
            Channel.SMARTSTORE, "smartstore-001", ProductGroup.YUJA,
            "김철수", "01033334444", "주소2", "22222", 5,
        ),
        build_standard_order(
            Channel.PHONE_TEXT, "phone-001", ProductGroup.YUJACHEONG,
            "이영희", "01055556666", "주소3", "33333", 3,
            product_detail=YujacheongProduct.LEMONCELLO.value,
        ),
    ]


def test_compute_cumulative_aggregates_across_products_tiers_platforms():
    with tempfile.TemporaryDirectory() as tmp_dir:
        log_path = os.path.join(tmp_dir, "aggregate_log.csv")
        append_packages(orders_to_packages(_sample_orders()), "2026-08-09", log_path)
        state = compute_cumulative(season_start_date="2026-08-15", log_path=log_path)

    assert state["season_start_date"] == "2026-08-15"
    assert state["total_sales_units"] == 4  # 청유자 1박스 + 유자 2박스(5kg 분할) + 유자청 1
    assert state["total_sales_weight_kg"] == 12  # 7 + 5, 유자청은 kg가 아니므로 제외
    assert state["cumulative_by_product"] == {"청유자": 1, "유자": 2, "유자청": 1}
    assert state["cumulative_by_weight_tier"] == {"1kg": 1, "3kg(4kg박스)": 1, "8kg": 1}
    assert state["cumulative_by_platform"] == {"스마트스토어": 2, "위탁판매자": 1, "전화문자": 1}
    assert state["cumulative_by_yujacheong_product"] == {"디오가닉": 0, "로우슈거": 0, "레몬첼로": 1}
    assert state["cumulative_weight_by_product"] == {"청유자": 7, "유자": 5}
    assert state["cumulative_by_weight_tier_by_product"]["청유자"] == {"1kg": 0, "3kg(4kg박스)": 0, "8kg": 1}
    assert state["cumulative_by_weight_tier_by_product"]["유자"] == {"1kg": 1, "3kg(4kg박스)": 1, "8kg": 0}


def test_compute_cumulative_reads_multiple_days_and_sums_them():
    with tempfile.TemporaryDirectory() as tmp_dir:
        log_path = os.path.join(tmp_dir, "aggregate_log.csv")
        append_packages(orders_to_packages(_sample_orders()[:1]), "2026-08-09", log_path)
        append_packages(orders_to_packages(_sample_orders()[:1]), "2026-08-10", log_path)
        state = compute_cumulative(season_start_date="2026-08-15", log_path=log_path)

    assert state["total_sales_units"] == 2
    assert state["total_sales_weight_kg"] == 14


def test_multi_box_order_counts_as_multiple_units():
    big_order = build_standard_order(
        Channel.WHOLESALE, "id-big", ProductGroup.CHEONGYUJA, "박민수", "01077778888", "주소", "44444", 12,
    )
    with tempfile.TemporaryDirectory() as tmp_dir:
        log_path = os.path.join(tmp_dir, "aggregate_log.csv")
        append_packages(orders_to_packages([big_order]), "2026-08-09", log_path)
        state = compute_cumulative(season_start_date="2026-08-15", log_path=log_path)

    assert state["total_sales_units"] == 2  # 12kg -> 8kg박스 + 3kg박스, 박스(패키지) 단위로 집계
    assert state["cumulative_by_weight_tier"] == {"1kg": 0, "3kg(4kg박스)": 1, "8kg": 1}


def test_compute_daily_trend_returns_one_row_per_day_sorted_by_date():
    with tempfile.TemporaryDirectory() as tmp_dir:
        log_path = os.path.join(tmp_dir, "aggregate_log.csv")
        append_packages(orders_to_packages(_sample_orders()), "2026-08-10", log_path)
        append_packages(orders_to_packages(_sample_orders()[:1]), "2026-08-09", log_path)
        trend = compute_daily_trend(log_path=log_path)

    assert [row["date"] for row in trend] == ["2026-08-09", "2026-08-10"]
    assert trend[0]["total"] == 1
    assert trend[0]["청유자"] == 1
    assert trend[1]["total"] == 4  # 청유자 1박스 + 유자 2박스(5kg 분할) + 유자청 1
    assert trend[1]["유자청"] == 1


def test_compute_cumulative_empty_log_returns_zeroed_state():
    with tempfile.TemporaryDirectory() as tmp_dir:
        log_path = os.path.join(tmp_dir, "aggregate_log.csv")
        state = compute_cumulative(season_start_date="2026-08-15", log_path=log_path)

    assert state["total_sales_units"] == 0
    assert state["total_sales_weight_kg"] == 0.0


if __name__ == "__main__":
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_")]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"\n{len(tests)} tests passed")
