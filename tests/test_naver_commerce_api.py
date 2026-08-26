import io
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import bcrypt  # noqa: E402

import naver_commerce_api as api  # noqa: E402


def test_client_secret_sign_uses_secret_as_bcrypt_salt():
    # 네이버 커머스API 표준 스펙: client_secret을 bcrypt salt로 써서
    # "client_id_타임스탬프"를 해시한 뒤 base64 인코딩한 값을 보낸다.
    client_id = "abc123"
    client_secret = "$2a$04$5sVcyHZL5jBJg71ipzgXDe"  # 실제 발급받은 것과 같은 형식(더미 값)
    timestamp = "1700000000000"

    sign = api._build_client_secret_sign(client_id, client_secret, timestamp)

    import base64
    decoded = base64.b64decode(sign)
    expected = bcrypt.hashpw(f"{client_id}_{timestamp}".encode("utf-8"), client_secret.encode("utf-8"))
    assert decoded == expected


class _FakeResponse:
    def __init__(self, body: bytes):
        self._body = body
        self.status = 200

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_client_caches_token_until_expiry(monkeypatch):
    calls = {"n": 0}

    def fake_urlopen(request, timeout=None):
        calls["n"] += 1
        return _FakeResponse(json.dumps({
            "access_token": f"token-{calls['n']}", "expires_in": 10799, "token_type": "Bearer",
        }).encode("utf-8"))

    monkeypatch.setattr(api.urllib.request, "urlopen", fake_urlopen)

    client = api.NaverCommerceClient("id", "$2a$04$5sVcyHZL5jBJg71ipzgXDe")
    token1 = client._ensure_token()
    token2 = client._ensure_token()

    assert token1 == token2 == "token-1"
    assert calls["n"] == 1  # 두 번째 호출은 캐시된 토큰을 그대로 씀


def test_client_call_sends_bearer_header_and_parses_json(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout=None):
        if "oauth2/token" in request.full_url:
            return _FakeResponse(json.dumps({
                "access_token": "tok", "expires_in": 10799, "token_type": "Bearer",
            }).encode("utf-8"))
        captured["headers"] = dict(request.header_items())
        captured["url"] = request.full_url
        return _FakeResponse(json.dumps({"data": {"ok": True}}).encode("utf-8"))

    monkeypatch.setattr(api.urllib.request, "urlopen", fake_urlopen)

    client = api.NaverCommerceClient("id", "$2a$04$5sVcyHZL5jBJg71ipzgXDe")
    result = client.call("/v1/some/path", params={"a": "1"})

    assert result == {"data": {"ok": True}}
    assert captured["headers"]["Authorization"] == "Bearer tok"
    assert "a=1" in captured["url"]


if __name__ == "__main__":
    import types

    class _MonkeyPatch:
        def __init__(self):
            self._undo = []

        def setattr(self, obj, name, value):
            self._undo.append((obj, name, getattr(obj, name)))
            setattr(obj, name, value)

        def undo(self):
            for obj, name, old in reversed(self._undo):
                setattr(obj, name, old)

    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_")]
    passed = 0
    for t in tests:
        mp = _MonkeyPatch()
        try:
            if "monkeypatch" in t.__code__.co_varnames[:t.__code__.co_argcount]:
                t(mp)
            else:
                t()
            print(f"PASS {t.__name__}")
            passed += 1
        finally:
            mp.undo()
    print(f"\n{passed} tests passed")
