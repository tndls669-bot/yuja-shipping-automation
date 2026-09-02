"""표준 스키마 패키지 → 우체국 계약소포 소포신청(InsertOrder) API 파라미터 변환.

주문 하나가 여러 패키지(박스)로 쪼개질 수 있으므로 courier_tier.orders_to_packages로
먼저 분해한 뒤, 패키지 단위로 이 파라미터를 만들어 API를 한 번씩 호출한다
(실제 호출 루프는 local_step2_epost_submit.run()에 있다).
"""
import math

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
