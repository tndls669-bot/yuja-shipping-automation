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


def calc_boxes(total_kg: float) -> list[tuple[str, float]]:
    if total_kg <= 0:
        return []

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
        elif remaining <= 8:
            boxes.append((BOX_8KG, remaining))
            remaining = 0
        else:
            boxes.append((BOX_8KG, 8))
            remaining = round(remaining - 8, 3)

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
