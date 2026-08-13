"""표준 스키마 — 채널별 주문을 하나의 공통 구조로 통합."""
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Optional

from box_calc import calc_boxes, format_box_composition

BOTTLE_BOX = "1구전용박스"


class Channel(str, Enum):
    SMARTSTORE = "스마트스토어"
    WHOLESALE = "위탁판매자"
    PHONE_TEXT = "전화문자"


class ProductGroup(str, Enum):
    CHEONGYUJA = "청유자"
    YUJA = "유자"
    YUJACHEONG = "유자청"


class YujacheongProduct(str, Enum):
    DIORGANIC = "디오가닉"
    LOW_SUGAR = "로우슈거"
    LEMONCELLO = "레몬첼로"


@dataclass
class StandardOrder:
    channel: Channel
    original_order_id: str
    product_group: Optional[ProductGroup]
    recipient_name: str
    phone: str
    address: str  # 기본주소 (도로명/지번까지)
    postal_code: str
    weight_or_qty: Optional[float]
    box_composition: str = ""
    delivery_message: str = ""
    scheduled_delivery: bool = False
    product_detail: Optional[str] = None  # 유자청일 때만 의미 있음 (디오가닉/로우슈거/레몬첼로)
    address_detail: str = ""  # 상세주소 (동/호수, 층수 등) — 우체국 양식이 기본/상세를 별도 칸으로 요구함


def full_address(order: StandardOrder) -> str:
    return f"{order.address} {order.address_detail}".strip()


def normalize_phone(phone: str) -> str:
    return phone.replace("-", "").replace(" ", "")


def compute_box_composition(product_group: ProductGroup, weight_or_qty: float) -> str:
    if product_group == ProductGroup.YUJACHEONG:
        bottle_count = int(weight_or_qty)
        return f"{BOTTLE_BOX}×{bottle_count}"
    boxes = calc_boxes(weight_or_qty)
    return format_box_composition(boxes)


def build_standard_order(
    channel: Channel,
    original_order_id: str,
    product_group: ProductGroup,
    recipient_name: str,
    phone: str,
    address: str,
    postal_code: str,
    weight_or_qty: float,
    delivery_message: str = "",
    scheduled_delivery: bool = False,
    product_detail: Optional[str] = None,
    address_detail: str = "",
) -> StandardOrder:
    return StandardOrder(
        channel=channel,
        original_order_id=original_order_id,
        product_group=product_group,
        recipient_name=recipient_name,
        phone=normalize_phone(phone),
        address=address if address.strip() else ".",
        postal_code=postal_code,
        weight_or_qty=weight_or_qty,
        box_composition=compute_box_composition(product_group, weight_or_qty),
        delivery_message=delivery_message,
        scheduled_delivery=scheduled_delivery,
        product_detail=product_detail,
        address_detail=address_detail,
    )


def order_to_dict(order: StandardOrder) -> dict:
    """1단계에서 접수 대기 목록(JSON)에 저장할 때 씀 — 2단계가 그대로 복원해서 우체국에 접수."""
    d = asdict(order)
    d["channel"] = order.channel.value
    d["product_group"] = order.product_group.value if order.product_group else None
    return d


def order_from_dict(d: dict) -> StandardOrder:
    return StandardOrder(
        channel=Channel(d["channel"]),
        original_order_id=d["original_order_id"],
        product_group=ProductGroup(d["product_group"]) if d.get("product_group") else None,
        recipient_name=d["recipient_name"],
        phone=d["phone"],
        address=d["address"],
        postal_code=d["postal_code"],
        weight_or_qty=d.get("weight_or_qty"),
        box_composition=d.get("box_composition", ""),
        delivery_message=d.get("delivery_message", ""),
        scheduled_delivery=d.get("scheduled_delivery", False),
        product_detail=d.get("product_detail"),
        address_detail=d.get("address_detail", ""),
    )
