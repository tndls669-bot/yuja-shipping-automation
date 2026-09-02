import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from box_calc import calc_boxes, format_box_composition  # noqa: E402


def test_5kg_uses_small_box_combo():
    boxes = calc_boxes(5)
    assert boxes == [("3kg박스", 4), ("1kg박스", 1)], boxes
    assert len(boxes) == 2


def test_7kg_uses_single_8kg_box():
    boxes = calc_boxes(7)
    assert boxes == [("8kg박스", 7)], boxes
    assert len(boxes) == 1


def test_12kg_uses_8kg_plus_3kg():
    boxes = calc_boxes(12)
    assert boxes == [("8kg박스", 8), ("3kg박스", 4)], boxes
    assert len(boxes) == 2


def test_500g_uses_1kg_box():
    boxes = calc_boxes(0.5)
    assert boxes == [("1kg박스", 0.5)], boxes


def test_4kg_exactly_uses_single_3kg_box():
    boxes = calc_boxes(4)
    assert boxes == [("3kg박스", 4)], boxes


def test_zero_or_negative_returns_empty():
    assert calc_boxes(0) == []
    assert calc_boxes(-1) == []


def test_16kg_uses_two_8kg_boxes():
    boxes = calc_boxes(16)
    assert boxes == [("8kg박스", 8), ("8kg박스", 8)], boxes


def test_format_box_composition_groups_same_boxes():
    boxes = calc_boxes(16)
    assert format_box_composition(boxes) == "8kg박스×2(8kg적재)"


def test_format_box_composition_5kg():
    boxes = calc_boxes(5)
    assert format_box_composition(boxes) == "3kg박스×1(4kg적재)+1kg박스×1(1kg적재)"


def test_format_box_composition_empty():
    assert format_box_composition([]) == ""


def test_absurd_weight_raises_instead_of_creating_thousands_of_boxes():
    # 2026-09-01 사고: CSV 칸이 밀려 우편번호(15621)가 중량으로 들어가면서 이 함수가
    # 8kg박스 1954개로 조용히 쪼개버렸고, 그게 전부 실제로 우체국에 접수됐다.
    # 이런 값은 쪼개지 말고 바로 에러로 멈춰야 한다.
    with pytest.raises(ValueError):
        calc_boxes(15621)


if __name__ == "__main__":
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_")]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"\n{len(tests)} tests passed")
