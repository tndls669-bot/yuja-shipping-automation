"""네이버 커머스API(구 스마트스토어 오픈API) 클라이언트.

인증 방식이 표준 OAuth2 client_credentials와 다르게, client_secret을 bcrypt의
salt로 써서 "client_id_타임스탬프" 문자열을 해시한 값(client_secret_sign)을
같이 보내야 한다(네이버 커머스API센터 표준 스펙).
"""
import base64
import json
import time
import urllib.error
import urllib.parse
import urllib.request

import bcrypt

_TOKEN_URL = "https://api.commerce.naver.com/external/v1/oauth2/token"
_BASE_URL = "https://api.commerce.naver.com/external"


class NaverApiError(RuntimeError):
    pass


def _build_client_secret_sign(client_id: str, client_secret: str, timestamp_ms: str) -> str:
    password = f"{client_id}_{timestamp_ms}".encode("utf-8")
    hashed = bcrypt.hashpw(password, client_secret.encode("utf-8"))
    return base64.b64encode(hashed).decode("utf-8")


def get_access_token(client_id: str, client_secret: str) -> dict:
    """access_token, expires_in(초), token_type을 담은 dict를 반환한다."""
    timestamp_ms = str(int(time.time() * 1000))
    client_secret_sign = _build_client_secret_sign(client_id, client_secret, timestamp_ms)

    body = urllib.parse.urlencode({
        "client_id": client_id,
        "timestamp": timestamp_ms,
        "client_secret_sign": client_secret_sign,
        "grant_type": "client_credentials",
        "type": "SELF",
    })
    request = urllib.request.Request(
        _TOKEN_URL,
        data=body.encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise NaverApiError(f"토큰 발급 실패 ({e.code}): {e.read().decode('utf-8')}") from e


class NaverCommerceClient:
    """액세스 토큰을 만료 전까지 캐시해서 재사용하는 간단한 클라이언트."""

    def __init__(self, client_id: str, client_secret: str):
        self._client_id = client_id
        self._client_secret = client_secret
        self._token = None
        self._token_expires_at = 0.0

    def _ensure_token(self) -> str:
        if self._token is None or time.time() >= self._token_expires_at:
            result = get_access_token(self._client_id, self._client_secret)
            self._token = result["access_token"]
            # 여유를 두고 만료 60초 전에 갱신
            self._token_expires_at = time.time() + result["expires_in"] - 60
        return self._token

    def call(self, path: str, method: str = "GET", params: dict = None, json_body: dict = None) -> dict:
        token = self._ensure_token()
        url = _BASE_URL + path
        if params:
            url += "?" + urllib.parse.urlencode(params)

        headers = {"Authorization": f"Bearer {token}"}
        data = None
        if json_body is not None:
            data = json.dumps(json_body).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = response.read()
                return json.loads(body) if body else {}
        except urllib.error.HTTPError as e:
            raise NaverApiError(f"{method} {path} 실패 ({e.code}): {e.read().decode('utf-8')}") from e
