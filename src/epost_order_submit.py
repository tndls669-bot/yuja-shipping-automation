"""표준 스키마 주문 → 우체국 계약소포 소포신청(InsertOrder) API 파라미터 변환 및 호출.

주문 하나가 여러 패키지(박스)로 쪼개질 수 있으므로 courier_tier.orders_to_packages로
먼저 분해한 뒤, 패키지 단위로 API를 한 번씩 호출한다.
"""
import math

from courier_tier import orders_to_packages
from epost_api_client import insert_order

_CONTENT_CODE_AGRI = "021"  # 농/수/축산물(일반) — 원물/유자청 전부 이 코드로 충분


def package_to_order_params(
    package,
    cust_no: str,
    appr_no: str,
    office_ser: str,
    order_comp_nm: str,
    test_yn: bool = False,
) -> dict:
    order = package.order
    weight_kg = package.weight_kg or 1
    weight_int = max(1, min(30, math.ceil(weight_kg)))

    params = {
        "custNo": cust_no,
        "apprNo": appr_no,
        "payType": "1",
        "reqType": "1",
        "officeSer": office_ser,
        "weight": str(weight_int),
        "microYn": "N",
        "packngMtrCd": "01",
        "orderNo": order.original_order_id,
        "ordCompNm": order_comp_nm,
        "recNm": order.recipient_name,
        "recZip": order.postal_code,
        "recAddr1": order.address,
        "recAddr2": order.address_detail if order.address_detail else ".",
        "recMob": order.phone,
        "contCd": _CONTENT_CODE_AGRI,
        "goodsNm": package.label,
        "printYn": "N",
    }
    if order.delivery_message:
        params["delivMsg"] = order.delivery_message
    if test_yn:
        params["testYn"] = "Y"
    return params


def submit_orders(
    orders: list,
    auth_key: str,
    security_key: str,
    cust_no: str,
    appr_no: str,
    office_ser: str,
    order_comp_nm: str,
    test_yn: bool = False,
) -> list:
    results = []
    for package in orders_to_packages(orders):
        params = package_to_order_params(package, cust_no, appr_no, office_ser, order_comp_nm, test_yn)
        response = insert_order(auth_key, security_key, params)
        results.append((package, response))
    return results
