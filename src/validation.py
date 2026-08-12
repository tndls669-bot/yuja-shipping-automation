"""검증 단계 — 주소 누락, 전화번호 형식 체크. 이상건은 에러로 중단하지 않고 사유만 모아 반환."""
import re

_PHONE_PATTERN = re.compile(r"^01[016789]\d{7,8}$")


def validate_order(order) -> list[str]:
    issues = []
    if not order.address or order.address == ".":
        issues.append("주소 누락")
    if not order.phone or not _PHONE_PATTERN.match(order.phone):
        issues.append(f"전화번호 형식 이상: {order.phone!r}")
    if order.product_group is None:
        issues.append("품목군 미확인")
    if order.weight_or_qty is None:
        issues.append("중량/수량 누락")
    return issues
