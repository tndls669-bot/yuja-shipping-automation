import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import openpyxl  # noqa: E402

from excel_reader import extract_text_from_xlsx  # noqa: E402


def _make_sample_xlsx(path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "주문서"
    ws.append(["받는사람", "전화번호", "주소", "품목", "수량/중량"])
    ws.append(["홍길동", "010-1234-5678", "전남 고흥군 ...", "청유자", 5])
    ws.append([None, None, None, None, None])
    ws.append(["김철수", "010-9999-8888", "광주 서구 ...", "유자청", 3])
    wb.save(path)


def test_extract_text_includes_sheet_name_and_rows():
    with tempfile.TemporaryDirectory() as tmp_dir:
        path = os.path.join(tmp_dir, "sample.xlsx")
        _make_sample_xlsx(path)
        text = extract_text_from_xlsx(path)

    assert "[시트: 주문서]" in text
    assert "홍길동 | 010-1234-5678" in text
    assert "김철수 | 010-9999-8888" in text


def test_extract_text_skips_fully_empty_rows():
    with tempfile.TemporaryDirectory() as tmp_dir:
        path = os.path.join(tmp_dir, "sample.xlsx")
        _make_sample_xlsx(path)
        text = extract_text_from_xlsx(path)

    lines = text.splitlines()
    assert all(line.strip() != "" or line == "" for line in lines)
    assert " |  |  |  | " not in text


if __name__ == "__main__":
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_")]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"\n{len(tests)} tests passed")
