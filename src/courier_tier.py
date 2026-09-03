"""택배비 계약 구간(2kg/5kg/10kg) 판단 + 주문을 실제 발송 패키지 단위로 분해.

원물(청유자/유자) 한 건의 총 중량이 여러 박스로 나뉘면(예: 12kg → 8kg박스+3kg박스)
각 박스가 별도 소포/운송장이므로 패키지 단위로 쪼갠다. 유자청은 여러 병이 큰 박스
하나에 같이 들어가는 구조라 주문 하나 = 패키지 하나로 유지한다.

박스 타입 → 구간 매핑은 대표님이 알려준 실측 기준(포장 무게 포함)을 그대로 쓴다:
1kg박스 → 2kg 구간, 3kg박스(2~4kg 적재) → 5kg 구간, 8kg박스 → 10kg 구간(그대로 다음 구간).
유자청은 무게를 안 재므로 병당 평균 무게(포장 포함) 추정치로 구간을 계산한다 — 실제
평균 무게가 다르면 YUJACHEONG_BOTTLE_WEIGHT_KG만 조정하면 된다.
"""
from dataclasses import dataclass
from typing import Optional

from box_calc import CHEONGYUJA_8KG_BOX_CAPACITY, calc_boxes
from schema import BOTTLE_BOX, ProductGroup, StandardOrder

TIER_2KG = "2kg"
TIER_5KG = "5kg"
TIER_10KG = "10kg"
TIERS = (TIER_2KG, TIER_5KG, TIER_10KG)

_RAW_BOX_TIER = {
    "1kg박스": TIER_2KG,
    "3kg박스": TIER_5KG,
    "8kg박스": TIER_10KG,
}

YUJACHEONG_BOTTLE_WEIGHT_KG = 0.7  # 병당 평균 무게(포장 포함) 추정치


def _bucket_by_weight(weight_kg: float) -> str:
    if weight_kg <= 2:
        return TIER_2KG
    if weight_kg <= 5:
        return TIER_5KG
    return TIER_10KG


def _format_spec_kg(loaded_kg: float) -> str:
    if loaded_kg < 1:
        return f"{round(loaded_kg * 1000)}g"
    text = f"{loaded_kg:g}"
    return f"{text}kg"


def _goods_label(product_name: str, spec: str, order_source: str) -> str:
    label = f"({product_name},{spec})"
    return f"{label} {order_source}" if order_source else label


@dataclass
class Package:
    order: StandardOrder
    label: str
    tier: Optional[str]
    weight_kg: Optional[float] = None
    box_type: Optional[str] = None


def orders_to_packages(orders: list) -> list:
    packages = []
    for order in orders:
        if order.product_group == ProductGroup.YUJACHEONG:
            bottle_count = int(order.weight_or_qty or 0)
            weight_kg = round(bottle_count * YUJACHEONG_BOTTLE_WEIGHT_KG, 2)
            tier = _bucket_by_weight(weight_kg) if bottle_count else None
            product_name = " ".join(p for p in (order.product_group.value, order.product_detail) if p)
            label = _goods_label(product_name, f"{bottle_count}병", order.order_source)
            packages.append(Package(order, label, tier, weight_kg or None, BOTTLE_BOX))
        elif order.product_group in (ProductGroup.CHEONGYUJA, ProductGroup.YUJA):
            capacity = CHEONGYUJA_8KG_BOX_CAPACITY if order.product_group == ProductGroup.CHEONGYUJA else 8
            boxes = calc_boxes(order.weight_or_qty or 0, eight_kg_box_capacity=capacity)
            if not boxes:
                packages.append(Package(order, order.product_group.value, None))
                continue
            for box_type, loaded_kg in boxes:
                tier = _RAW_BOX_TIER.get(box_type)
                label = _goods_label(order.product_group.value, _format_spec_kg(loaded_kg), order.order_source)
                packages.append(Package(order, label, tier, loaded_kg, box_type))
        else:
            packages.append(Package(order, order.box_composition, None))

    return packages
