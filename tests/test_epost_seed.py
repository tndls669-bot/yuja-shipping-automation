import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from epost_seed import seed128_encrypt_hex  # noqa: E402


def test_matches_official_manual_example():
    # 우체국 계약소포 OpenAPI 매뉴얼(2023.12) p.2 검증 예시
    result = seed128_encrypt_hex("1234567890abcdefghijkl", "123abc가나다")
    assert result == "8522ad534acc61cb88090b7e62c5183b"


def test_short_plaintext_pads_to_one_block():
    result = seed128_encrypt_hex("1234567890abcdef", "custNo=001")  # 10바이트
    assert len(result) == 32  # 1블록(16바이트) 패딩 -> hex 32자리


def test_plaintext_over_16_bytes_uses_two_blocks():
    result = seed128_encrypt_hex("1234567890abcdef", "custNo=0011223344")  # 17바이트
    assert len(result) == 64  # 2블록(32바이트) -> hex 64자리


def test_output_is_deterministic():
    a = seed128_encrypt_hex("mysecretkey12345", "memberID=user01")
    b = seed128_encrypt_hex("mysecretkey12345", "memberID=user01")
    assert a == b


if __name__ == "__main__":
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_")]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"\n{len(tests)} tests passed")
