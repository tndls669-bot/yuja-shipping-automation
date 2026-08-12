"""자유 형식 텍스트(위탁판매자 이메일 본문, 전화/문자 주문 텍스트 뭉치) → 표준 스키마 파싱 노드.

하나의 텍스트 안에 주문이 여러 건 섞여 있을 수 있으므로(전화/문자 뭉치, 여러 건을 모은 이메일)
항상 리스트로 추출한다. 한 건짜리 텍스트를 넣어도 원소 1개짜리 리스트가 나온다.
"""
from gemini_client import DEFAULT_MODEL, call_gemini_json
from schema import (
    Channel,
    ProductGroup,
    StandardOrder,
    YujacheongProduct,
    compute_box_composition,
    normalize_phone,
)

_PRODUCT_GROUPS = ", ".join(g.value for g in ProductGroup)
_YUJACHEONG_PRODUCTS = ", ".join(p.value for p in YujacheongProduct)

_PROMPT_TEMPLATE = """다음은 순수유자(유자 농장)에 들어온 주문 관련 텍스트입니다.
위탁판매자가 보낸 이메일이거나, 전화/문자로 받은 주문을 대표님이 정리해서 붙여넣은 텍스트일 수 있습니다.
텍스트 안에 주문이 한 건일 수도, 여러 건이 섞여 있을 수도 있습니다. 발견되는 주문을 모두 찾아
아래 필드를 가진 객체들의 JSON 배열로만 반환하세요. 설명이나 다른 텍스트는 절대 포함하지 마세요.
주문이 하나도 없으면 빈 배열 []을 반환하세요.

각 주문 객체의 필드:
- recipient_name: 받는사람 이름 (문자열, 없으면 null)
- phone: 받는사람 전화번호 (문자열, 없으면 null)
- address: 배송지 기본주소 — 동/호수, 층수 등 상세주소는 제외하고 도로명(지번) 주소까지만 (문자열, 없으면 null)
- address_detail: 배송지 상세주소 — 동/호수, 층수 등 (문자열, 없으면 null)
- postal_code: 우편번호 (문자열, 없으면 null)
- product_group: 다음 중 정확히 하나 — {product_groups} (본문에서 유추 안 되면 null)
- product_detail: product_group이 "유자청"인 경우에만, 다음 중 정확히 하나 — {yujacheong_products} (구분 안 되면 null). 그 외 품목군이면 항상 null.
- weight_or_qty: 원물(청유자/유자)이면 총 중량(kg) 숫자, 유자청이면 병 수량 숫자 (없으면 null)
- delivery_message: 배송 관련 특이사항 (없으면 null)
- scheduled_delivery: 순차발송/지정일 문구가 있으면 true, 아니면 false

텍스트:
---
{order_text}
---

JSON 배열만 반환하세요."""


def parse_orders_from_text(
    order_text: str,
    channel: Channel,
    order_id_prefix: str,
    api_key: str,
    model: str = DEFAULT_MODEL,
) -> list[StandardOrder]:
    prompt = _PROMPT_TEMPLATE.format(
        product_groups=_PRODUCT_GROUPS, yujacheong_products=_YUJACHEONG_PRODUCTS, order_text=order_text
    )
    extracted_list = call_gemini_json(prompt, api_key, model)
    if not isinstance(extracted_list, list):
        extracted_list = [extracted_list]

    return [
        _to_standard_order(extracted, channel, f"{order_id_prefix}-{i:03d}")
        for i, extracted in enumerate(extracted_list, start=1)
    ]


def _to_standard_order(extracted: dict, channel: Channel, original_order_id: str) -> StandardOrder:
    product_group_raw = extracted.get("product_group")
    try:
        product_group = ProductGroup(product_group_raw) if product_group_raw else None
    except ValueError:
        product_group = None

    weight_or_qty = extracted.get("weight_or_qty")
    phone = extracted.get("phone") or ""
    address = extracted.get("address") or ""
    address_detail = extracted.get("address_detail") or ""

    product_detail_raw = extracted.get("product_detail")
    product_detail = None
    if product_group == ProductGroup.YUJACHEONG and product_detail_raw:
        try:
            product_detail = YujacheongProduct(product_detail_raw).value
        except ValueError:
            product_detail = None

    box_composition = ""
    if product_group is not None and weight_or_qty is not None:
        box_composition = compute_box_composition(product_group, weight_or_qty)

    return StandardOrder(
        channel=channel,
        original_order_id=original_order_id,
        product_group=product_group,
        recipient_name=extracted.get("recipient_name") or "",
        phone=normalize_phone(phone),
        address=address if address.strip() else ".",
        postal_code=extracted.get("postal_code") or "",
        weight_or_qty=weight_or_qty,
        box_composition=box_composition,
        delivery_message=extracted.get("delivery_message") or "",
        scheduled_delivery=bool(extracted.get("scheduled_delivery")),
        product_detail=product_detail,
        address_detail=address_detail,
    )
