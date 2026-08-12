"""우체국 계약소포 OpenAPI 클라이언트 (biz.epost.go.kr 계약고객전용).

요청 파라미터(regData)는 SEED128로 암호화, 응답은 평문 XML(<xsync> 루트)로 온다.
"""
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from epost_seed import seed128_encrypt_hex

BASE_URL = "http://ship.epost.go.kr"


class EpostApiError(RuntimeError):
    pass


def _build_reg_data(security_key: str, params: dict) -> str:
    plaintext = "&".join(f"{k}={v}" for k, v in params.items() if v is not None)
    return seed128_encrypt_hex(security_key, plaintext)


def _xml_to_dict(elem):
    children = list(elem)
    if not children:
        return (elem.text or "").strip()
    result = {}
    for child in children:
        value = _xml_to_dict(child)
        if child.tag in result:
            existing = result[child.tag]
            if isinstance(existing, list):
                existing.append(value)
            else:
                result[child.tag] = [existing, value]
        else:
            result[child.tag] = value
    return result


def _parse_response(xml_bytes: bytes):
    root = ET.fromstring(xml_bytes)
    data = _xml_to_dict(root)
    if isinstance(data, dict) and "error_code" in data:
        raise EpostApiError(f"{data.get('error_code')}: {data.get('message')}")
    return data


def call_api(
    message_name: str,
    auth_key: str,
    security_key: str = None,
    params: dict = None,
    method: str = "GET",
):
    query = {"key": auth_key}
    if params is not None:
        query["regData"] = _build_reg_data(security_key, params)

    url = f"{BASE_URL}/{message_name}"
    headers = {"Connection": "keep-alive", "Host": "ship.epost.go.kr", "User-Agent": "yuja-shipping-automation/1.0"}

    if method == "GET":
        request = urllib.request.Request(url + "?" + urllib.parse.urlencode(query), headers=headers)
    else:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        request = urllib.request.Request(
            url, data=urllib.parse.urlencode(query).encode("utf-8"), headers=headers, method="POST"
        )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read()
    except urllib.error.HTTPError as e:
        body = e.read()

    return _parse_response(body)


def get_cust_no(auth_key: str, security_key: str, member_id: str) -> str:
    result = call_api("api.GetCustNo.jparcel", auth_key, security_key, {"memberID": member_id})
    return result["custNo"]


def get_appr_no(auth_key: str, security_key: str, cust_no: str) -> list:
    result = call_api("api.GetApprNo.jparcel", auth_key, security_key, {"custNo": cust_no})
    contracts = result.get("contractInfo", [])
    return contracts if isinstance(contracts, list) else [contracts]


def get_office_info(auth_key: str, security_key: str, cust_no: str) -> list:
    result = call_api("api.GetOfficeInfo.jparcel", auth_key, security_key, {"custNo": cust_no}, method="POST")
    offices = result.get("officeInfo", [])
    return offices if isinstance(offices, list) else [offices]


def insert_office(auth_key: str, security_key: str, office_params: dict) -> dict:
    return call_api("api.InsertOffice.jparcel", auth_key, security_key, office_params, method="POST")


def insert_order(auth_key: str, security_key: str, order_params: dict) -> dict:
    return call_api("api.InsertOrder.jparcel", auth_key, security_key, order_params, method="POST")
