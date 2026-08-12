"""Gemini API 저수준 호출 — 표준 라이브러리만 사용해 REST로 직접 호출."""
import json
import urllib.error
import urllib.request

GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DEFAULT_MODEL = "gemini-flash-latest"


class GeminiError(RuntimeError):
    pass


def call_gemini_json(prompt: str, api_key: str, model: str = DEFAULT_MODEL) -> dict:
    url = f"{GEMINI_ENDPOINT.format(model=model)}?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise GeminiError(f"Gemini API 호출 실패 ({e.code}): {e.read().decode('utf-8')}") from e

    try:
        text = body["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as e:
        raise GeminiError(f"Gemini 응답 형식이 예상과 다릅니다: {body}") from e

    return json.loads(text)
