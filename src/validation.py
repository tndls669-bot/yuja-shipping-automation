"""검증 단계 — 주소 누락, 전화번호 형식 체크. 이상건은 에러로 중단하지 않고 사유만 모아 반환."""
import re

# 010 등 일반 휴대폰 번호 + 0504/0502 등 안심번호(가상번호, 개인정보 보호용으로
# 위탁판매/택배 발송 시 흔히 쓰임) 형식을 모두 정상으로 인정한다.
_PHONE_PATTERN = re.compile(r"^(01[016789]\d{7,8}|050\d{8,9})$")


def validate_order(order) -> list[str]:
    issues = []
    if not order.address or order.address == ".":
        issues.append("주소 누락")
    if not order.postal_code:
        # 우체국 API가 우편번호 없이는 접수 자체를 거부한다(실제로 이 문제로 접수
        # 실패가 난 적이 있음) — 여기서 미리 걸러야 2단계에서 뒤늦게 실패하지 않는다.
        issues.append("우편번호 누락")
    if not order.phone or not _PHONE_PATTERN.match(order.phone):
        issues.append(f"전화번호 형식 이상: {order.phone!r}")
    if order.product_group is None:
        issues.append("품목군 미확인")
    if order.weight_or_qty is None:
        issues.append("중량/수량 누락")
    return issues
