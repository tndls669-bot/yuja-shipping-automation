"""위탁판매자가 엑셀 파일로 보낸 주문서 → 텍스트 뭉치로 변환.

시트/열 구성이 판매자마다 제각각이라 고정 컬럼 매핑 대신, 시트 내용을
표 형태 텍스트로 펼쳐서 text_order_parser의 Gemini 프롬프트에 그대로 넣는다.
"""
import openpyxl


def extract_text_from_xlsx(file_path: str) -> str:
    workbook = openpyxl.load_workbook(file_path, data_only=True)
    lines = []

    for sheet in workbook.worksheets:
        lines.append(f"[시트: {sheet.title}]")
        for row in sheet.iter_rows(values_only=True):
            if all(cell is None for cell in row):
                continue
            cells = ["" if cell is None else str(cell) for cell in row]
            lines.append(" | ".join(cells))

    return "\n".join(lines)
