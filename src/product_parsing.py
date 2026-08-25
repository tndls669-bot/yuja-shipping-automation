"""상품명/옵션정보 텍스트에서 품목군/세부품목/중량을 추출하는 공통 로직.

네이버 스마트스토어, 어글리어스 등 엑셀 기반 주문서 파서들이 공유해서 쓴다.
상품명 문구 기준의 키워드 규칙이라, 새로운 상품명 패턴이 나오면 classify_product에
규칙을 추가해야 한다.
"""
import re

from schema import ProductGroup, YujacheongProduct


def classify_product(product_name: str):
    name = product_name or ""
    if "유자청" in name:
        if "저당" in name:
            return ProductGroup.YUJACHEONG, YujacheongProduct.LOW_SUGAR.value
        if "레몬첼로" in name:
            return ProductGroup.YUJACHEONG, YujacheongProduct.LEMONCELLO.value
        if "디오가닉" in name:
            return ProductGroup.YUJACHEONG, YujacheongProduct.DIORGANIC.value
        return ProductGroup.YUJACHEONG, None
    if "청유자" in name:
        return ProductGroup.CHEONGYUJA, None
    if "유자" in name:
        return ProductGroup.YUJA, None
    return None, None


def extract_weight_kg(product_name: str, option_info: str, qty: float):
    # 옵션정보(실제 선택된 값)를 먼저 보고, 없을 때만 상품명에서 찾는다 — 상품명에는
    # "500g, 1kg, 3kg"처럼 선택 가능한 옵션이 전부 나열된 경우가 많기 때문.
    for text in (option_info, product_name):
        match = re.search(r"(\d+(?:\.\d+)?)\s*(kg|g)\b", text or "", re.IGNORECASE)
        if match:
            break
    else:
        return None
    value, unit = match.groups()
    value = float(value)
    if unit.lower() == "g":
        value = value / 1000
    return round(value * qty, 3)
