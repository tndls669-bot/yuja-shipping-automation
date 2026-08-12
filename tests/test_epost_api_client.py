import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from epost_api_client import EpostApiError, _parse_response  # noqa: E402


def test_parses_simple_success_response():
    xml = b"""<xsync><custNo><![CDATA[ 0011223344 ]]></custNo></xsync>"""
    result = _parse_response(xml)
    assert result == {"custNo": "0011223344"}


def test_parses_repeated_elements_into_list():
    xml = b"""<xsync>
        <contractInfo><apprNo><![CDATA[ 1018680001 ]]></apprNo></contractInfo>
        <contractInfo><apprNo><![CDATA[ 1018680002 ]]></apprNo></contractInfo>
    </xsync>"""
    result = _parse_response(xml)
    assert isinstance(result["contractInfo"], list)
    assert len(result["contractInfo"]) == 2
    assert result["contractInfo"][0]["apprNo"] == "1018680001"


def test_error_response_raises_epost_api_error():
    xml = "<error><error_code>ERR-123</error_code><message><![CDATA[ 인증키 오류 ]]></message></error>".encode("utf-8")
    try:
        _parse_response(xml)
        assert False, "should have raised"
    except EpostApiError as e:
        assert "ERR-123" in str(e)


if __name__ == "__main__":
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_")]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"\n{len(tests)} tests passed")
