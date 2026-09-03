"""박스 계산 노드 — 원물(청유자/유자) 총 중량을 박스 조합으로 변환."""
from collections import Counter

BOX_1KG = "1kg박스"
BOX_3KG = "3kg박스"
BOX_8KG = "8kg박스"

# 1kg박스+3kg박스 조합으로 커버 가능한 최대 중량(1+4). 이 범위를 넘으면
# 8kg박스를 쓰는 게 박스 개수상 유리해지므로 그 지점부터 전환한다.
# 설계 문서의 그리디 의사코드를 그대로 따르면 5kg 예시가 8kg박스 1개(5kg적재)로
# 계산되어 문서의 검증 예시("1kg+3kg = 2박스, 지시받은 대로")와 어긋난다.
# 대표님 확인 결과 검증 예시가 맞는 규칙이라, remaining이 (4, 5] 구간일 때는
# 8kg박스로 건너뛰지 않고 3kg박스(4kg적재)+1kg박스로 채우도록 분기를 추가했다.
_SMALL_BOX_MAX_COMBINED = 5


_MAX_REASONABLE_KG = 50  # 이보다 크면 데이터 오류로 보고 즉시 멈춘다(원인: 2026-09-01 사고 참고)

# 품목별 "8kg박스" 실제 최대 적재량. 밀도가 달라 상자 용적 기준(8kg)을 넘겨 담을 수 있는
# 품목이 있다 — 청유자(녹색, 밀도 높음)는 10kg까지 확인됨(대표님 확인, 2026-09-03).
CHEONGYUJA_8KG_BOX_CAPACITY = 10


def calc_boxes(total_kg: float, eight_kg_box_capacity: float = 8) -> list[tuple[str, float]]:
    """eight_kg_box_capacity: "8kg박스" 하나에 실제로 담을 수 있는 최대 중량. 품목마다
    밀도가 달라서 상자 용적 기준인 8kg를 넘겨 담을 수 있다 — 청유자(녹색, 밀도 높음)는
    10kg까지 확인됨(대표님 확인, 2026-09-03). 유자(노란유자)는 기존대로 8kg이 한계."""
    if total_kg <= 0:
        return []
    if total_kg > _MAX_REASONABLE_KG:
        # 실제 사고 사례: CSV를 손으로 고치다 우편번호가 중량 칸으로 밀려 들어가
        # 15,621kg짜리 "주문"이 생겼고, 이 함수가 그걸 8kg박스 1954개로 쪼개서
        # 전부 우체국에 실제 접수해버렸다. 한 건이 이 정도로 무거울 리 없으니
        # 조용히 계속 쪼개지 말고 바로 에러로 멈춘다.
        raise ValueError(f"중량이 비정상적으로 큽니다({total_kg}kg) — 데이터 오류 의심, 접수 전 확인 필요")

    boxes: list[tuple[str, float]] = []
    remaining = round(total_kg, 3)

    while remaining > 0:
        if remaining <= 1:
            boxes.append((BOX_1KG, remaining))
            remaining = 0
        elif remaining <= 4:
            boxes.append((BOX_3KG, remaining))
            remaining = 0
        elif remaining <= _SMALL_BOX_MAX_COMBINED:
            boxes.append((BOX_3KG, 4))
            boxes.append((BOX_1KG, round(remaining - 4, 3)))
            remaining = 0
        elif remaining <= eight_kg_box_capacity:
            boxes.append((BOX_8KG, remaining))
            remaining = 0
        else:
            boxes.append((BOX_8KG, eight_kg_box_capacity))
            remaining = round(remaining - eight_kg_box_capacity, 3)

    return boxes


def _fmt_kg(kg: float) -> str:
    return str(int(kg)) if float(kg).is_integer() else str(kg)


def format_box_composition(boxes: list[tuple[str, float]]) -> str:
    if not boxes:
        return ""
    counts = Counter(boxes)
    parts = [
        f"{box_type}×{count}({_fmt_kg(loaded)}kg적재)"
        for (box_type, loaded), count in counts.items()
    ]
    return "+".join(parts)
