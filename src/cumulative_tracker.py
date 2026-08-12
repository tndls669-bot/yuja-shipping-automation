"""누적 판매 집계 — 매번 실행할 때마다 PII 없는 집계 로그(aggregate_log.csv) 전체를
다시 읽어서 처음부터 재계산한다. 챗봇 대화 기억에 의존하지 않으므로 데이터가 어긋날 수
없고, 로그 자체에 이름/전화번호/주소가 없어 이 결과물도 개인정보와 무관하다(깃에 커밋 가능).
"""
import json
import os

from aggregate_log import read_rows
from schema import Channel, ProductGroup, YujacheongProduct

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LOG_PATH = os.path.join(_BASE_DIR, "data", "aggregate_log.csv")
_CUMULATIVE_PATH = os.path.join(_BASE_DIR, "data", "cumulative_data.json")

_WEIGHT_TIERS = {"1kg박스": "1kg", "3kg박스": "3kg(4kg박스)", "8kg박스": "8kg"}
_RAW_PRODUCTS = (ProductGroup.CHEONGYUJA.value, ProductGroup.YUJA.value)


def _empty_state(season_start_date: str) -> dict:
    return {
        "season_start_date": season_start_date,
        "total_sales_units": 0,
        "total_sales_weight_kg": 0.0,
        "cumulative_by_product": {g.value: 0 for g in ProductGroup},
        "cumulative_weight_by_product": {p: 0.0 for p in _RAW_PRODUCTS},
        "cumulative_by_weight_tier": {"1kg": 0, "3kg(4kg박스)": 0, "8kg": 0},
        "cumulative_by_weight_tier_by_product": {
            p: {"1kg": 0, "3kg(4kg박스)": 0, "8kg": 0} for p in _RAW_PRODUCTS
        },
        "cumulative_by_platform": {c.value: 0 for c in Channel},
        "cumulative_by_yujacheong_product": {p.value: 0 for p in YujacheongProduct},
    }


def compute_cumulative(season_start_date: str, log_path: str = _LOG_PATH) -> dict:
    state = _empty_state(season_start_date)

    for row in read_rows(log_path):
        state["total_sales_units"] += 1

        channel = row["채널구분"]
        if channel in state["cumulative_by_platform"]:
            state["cumulative_by_platform"][channel] += 1

        product = row["품목군"]
        if product in state["cumulative_by_product"]:
            state["cumulative_by_product"][product] += 1

        if product == ProductGroup.YUJACHEONG.value:
            detail = row.get("세부품목")
            if detail in state["cumulative_by_yujacheong_product"]:
                state["cumulative_by_yujacheong_product"][detail] += 1
            continue

        weight_str = row.get("적재중량또는수량")
        box_type = row.get("박스타입")
        if not weight_str:
            continue
        try:
            weight_kg = float(weight_str)
        except ValueError:
            continue

        state["total_sales_weight_kg"] += weight_kg
        if product in state["cumulative_weight_by_product"]:
            state["cumulative_weight_by_product"][product] += weight_kg

        tier = _WEIGHT_TIERS.get(box_type)
        if tier:
            state["cumulative_by_weight_tier"][tier] += 1
            if product in state["cumulative_by_weight_tier_by_product"]:
                state["cumulative_by_weight_tier_by_product"][product][tier] += 1

    state["total_sales_weight_kg"] = round(state["total_sales_weight_kg"], 2)
    for p in state["cumulative_weight_by_product"]:
        state["cumulative_weight_by_product"][p] = round(state["cumulative_weight_by_product"][p], 2)
    return state


def compute_daily_trend(log_path: str = _LOG_PATH) -> list:
    by_date = {}
    for row in read_rows(log_path):
        date = row["날짜"]
        if date not in by_date:
            by_date[date] = {"date": date, "total": 0, **{g.value: 0 for g in ProductGroup}}
        by_date[date]["total"] += 1
        product = row.get("품목군")
        if product in by_date[date]:
            by_date[date][product] += 1
    return [by_date[d] for d in sorted(by_date)]


def save_cumulative(state: dict, path: str = _CUMULATIVE_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    result = compute_cumulative(season_start_date="2026-08-15")
    save_cumulative(result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
