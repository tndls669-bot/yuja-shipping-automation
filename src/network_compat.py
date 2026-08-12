"""일부 클라우드 실행 환경(샌드박스)은 IPv6 소켓을 지원하지 않는다.
imaplib/smtplib가 DNS 조회 결과 중 기본으로 먼저 시도하는 AF_INET6 주소에서
'Address family not supported by protocol' 에러로 실패하는 것을 막기 위해
DNS 조회 결과를 IPv4만 쓰도록 제한한다.
"""
import socket

_original_getaddrinfo = socket.getaddrinfo
_patched = False


def force_ipv4() -> None:
    global _patched
    if _patched:
        return

    def _ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        return _original_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)

    socket.getaddrinfo = _ipv4_getaddrinfo
    _patched = True
