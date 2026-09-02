"""Gemini API 저수준 호출 — 표준 라이브러리만 사용해 REST로 직접 호출.

이 환경에서 이 API 호출이 가끔 응답이 느려 타임아웃 나는 게 실제로 관찰됐다(2026-09-01,
팔도맘/남해로부터 위탁 주문 2건이 이것 때문에 조용히 유실된 적 있음 — 호출 쪽이 예외를
못 잡으면 그 이메일은 "처리됨"으로 표시되고 다시는 안 읽힌다). 그래서 여기서 재시도까지
책임진다: 타임아웃/일시적 네트워크 오류면 잠깐 쉬고 최대 2번 더 시도한다.
"""
import json
import time
import urllib.error
import urllib.request

GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DEFAULT_MODEL = "gemini-flash-latest"
_TIMEOUT_SECONDS = 60
_MAX_ATTEMPTS = 3
_RETRY_DELAY_SECONDS = 5


class GeminiError(RuntimeError):
    pass


def _call_once(url: str, payload: dict) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


def call_gemini_json(prompt: str, api_key: str, model: str = DEFAULT_MODEL) -> dict:
    url = f"{GEMINI_ENDPOINT.format(model=model)}?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }

    body = None
    last_error: Exception = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            body = _call_once(url, payload)
            break
        except urllib.error.HTTPError as e:
            raise GeminiError(f"Gemini API 호출 실패 ({e.code}): {e.read().decode('utf-8')}") from e
        except (TimeoutError, urllib.error.URLError, ConnectionError) as e:
            last_error = e
            if attempt < _MAX_ATTEMPTS:
                time.sleep(_RETRY_DELAY_SECONDS)

    if body is None:
        raise GeminiError(f"Gemini API 호출이 {_MAX_ATTEMPTS}번 다 타임아웃/네트워크 오류로 실패했습니다: {last_error}") from last_error

    try:
        text = body["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as e:
        raise GeminiError(f"Gemini 응답 형식이 예상과 다릅니다: {body}") from e

    return json.loads(text)
